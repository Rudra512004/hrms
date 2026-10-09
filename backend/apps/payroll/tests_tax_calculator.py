"""
Phase 6.9C Authoritative Test Suite:
Tax Calculation & Progressive TDS Engine.

Covers all 42 required test scenarios:
- Rule Engine (1-10)
- Old Regime (11-16)
- New Regime (17-19)
- TDS Engine & Equalization (20-26)
- Employee Lifecycle (27-31)
- Payroll Integration & Immutability (32-36)
- Security & Multi-Tenant Isolation (37-40)
- Audit & Decimal Precision (41-42)
"""
from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework import status

from apps.organization.models import Organization, Branch
from apps.employees.models import Employee, EmploymentStatus
from apps.payroll.models import (
    FinancialYear,
    TaxDeclarationCategory,
    TaxDeclaration,
    InvestmentDeclaration,
    TaxRuleConfiguration,
    TaxSlab,
    TaxSurchargeSlab,
    TaxRuleDeductionApplicability,
    PayrollPeriod,
    PayrollRecord,
    Payslip,
    PayslipLine,
    CompensationHistory,
)
from apps.payroll.tax_calculator import (
    calculate_slab_tax,
    calculate_rebate,
    calculate_surcharge,
    calculate_cess,
    calculate_annual_tax,
    TaxCalculationService,
    TaxCalculationException,
)
from apps.payroll.services import generate_payroll_for_period, issue_payslips_for_period
from apps.payroll.services_tax import TaxDeclarationService
from apps.authorization.models import Permission, Role, RolePermission, UserRole
from apps.audit.models import AuditLog

User = get_user_model()


class Phase69CTaxEngineTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # 1. Organizations
        self.org1 = Organization.objects.create(name="BeyondSure Tech Corp")
        self.org2 = Organization.objects.create(name="Competitor Global")

        self.branch1 = Branch.objects.create(
            organization=self.org1,
            name="Bangalore HQ",
            is_active=True,
        )
        self.branch2 = Branch.objects.create(
            organization=self.org2,
            name="Mumbai Office",
            is_active=True,
        )

        # 2. Financial Years
        self.fy24 = FinancialYear.objects.create(
            organization=self.org1,
            name="FY 2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_active=True,
        )
        self.fy25 = FinancialYear.objects.create(
            organization=self.org1,
            name="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            is_active=True,
        )
        self.fy_org2 = FinancialYear.objects.create(
            organization=self.org2,
            name="FY 2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_active=True,
        )

        # 3. Tax Categories
        self.cat_80c = TaxDeclarationCategory.objects.create(
            organization=self.org1,
            code="80C",
            name="Section 80C Deductions",
            max_limit=Decimal("150000.00"),
            regime_applicability="OLD",
        )
        self.cat_80d = TaxDeclarationCategory.objects.create(
            organization=self.org1,
            code="80D",
            name="Medical Insurance Premium",
            max_limit=Decimal("25000.00"),
            regime_applicability="OLD",
        )
        self.cat_hra = TaxDeclarationCategory.objects.create(
            organization=self.org1,
            code="HRA",
            name="House Rent Allowance Exemption",
            max_limit=Decimal("100000.00"),
            regime_applicability="OLD",
        )

        # 4. Tax Rule Configurations (Test Fixtures)
        # Old Regime Rule
        self.rule_old = TaxRuleConfiguration.objects.create(
            organization=self.org1,
            financial_year=self.fy24,
            regime=TaxRuleConfiguration.REGIME_OLD,
            version_identifier="FY24-OLD-v1.0",
            effective_from=date(2024, 4, 1),
            effective_to=date(2025, 3, 31),
            standard_deduction=Decimal("50000.00"),
            rebate_income_threshold=Decimal("500000.00"),
            max_rebate_amount=Decimal("12500.00"),
            cess_rate=Decimal("0.0400"),
            is_active=True,
            description="Configured Old Regime Test Rule",
        )
        TaxSlab.objects.create(rule_configuration=self.rule_old, slab_order=1, lower_limit=Decimal("0.00"), upper_limit=Decimal("250000.00"), rate=Decimal("0.0000"))
        TaxSlab.objects.create(rule_configuration=self.rule_old, slab_order=2, lower_limit=Decimal("250000.00"), upper_limit=Decimal("500000.00"), rate=Decimal("0.0500"))
        TaxSlab.objects.create(rule_configuration=self.rule_old, slab_order=3, lower_limit=Decimal("500000.00"), upper_limit=Decimal("1000000.00"), rate=Decimal("0.2000"))
        TaxSlab.objects.create(rule_configuration=self.rule_old, slab_order=4, lower_limit=Decimal("1000000.00"), upper_limit=None, rate=Decimal("0.3000"))

        TaxRuleDeductionApplicability.objects.create(rule_configuration=self.rule_old, category_code="80C", is_allowed=True, max_deductible_limit=Decimal("150000.00"))
        TaxRuleDeductionApplicability.objects.create(rule_configuration=self.rule_old, category_code="80D", is_allowed=True, max_deductible_limit=Decimal("25000.00"))
        TaxRuleDeductionApplicability.objects.create(rule_configuration=self.rule_old, category_code="HRA", is_allowed=True, max_deductible_limit=Decimal("100000.00"))

        # New Regime Rule
        self.rule_new = TaxRuleConfiguration.objects.create(
            organization=self.org1,
            financial_year=self.fy24,
            regime=TaxRuleConfiguration.REGIME_NEW,
            version_identifier="FY24-NEW-v1.0",
            effective_from=date(2024, 4, 1),
            effective_to=date(2025, 3, 31),
            standard_deduction=Decimal("75000.00"),
            rebate_income_threshold=Decimal("700000.00"),
            max_rebate_amount=Decimal("25000.00"),
            cess_rate=Decimal("0.0400"),
            is_active=True,
            description="Configured New Regime Test Rule",
        )
        TaxSlab.objects.create(rule_configuration=self.rule_new, slab_order=1, lower_limit=Decimal("0.00"), upper_limit=Decimal("300000.00"), rate=Decimal("0.0000"))
        TaxSlab.objects.create(rule_configuration=self.rule_new, slab_order=2, lower_limit=Decimal("300000.00"), upper_limit=Decimal("700000.00"), rate=Decimal("0.0500"))
        TaxSlab.objects.create(rule_configuration=self.rule_new, slab_order=3, lower_limit=Decimal("700000.00"), upper_limit=Decimal("1000000.00"), rate=Decimal("0.1000"))
        TaxSlab.objects.create(rule_configuration=self.rule_new, slab_order=4, lower_limit=Decimal("1000000.00"), upper_limit=Decimal("1200000.00"), rate=Decimal("0.1500"))
        TaxSlab.objects.create(rule_configuration=self.rule_new, slab_order=5, lower_limit=Decimal("1200000.00"), upper_limit=Decimal("1500000.00"), rate=Decimal("0.2000"))
        TaxSlab.objects.create(rule_configuration=self.rule_new, slab_order=6, lower_limit=Decimal("1500000.00"), upper_limit=None, rate=Decimal("0.3000"))

        # Disallow 80C & 80D under new regime
        TaxRuleDeductionApplicability.objects.create(rule_configuration=self.rule_new, category_code="80C", is_allowed=False)
        TaxRuleDeductionApplicability.objects.create(rule_configuration=self.rule_new, category_code="80D", is_allowed=False)

        # 5. Users & Employees
        self.user1 = User.objects.create_user(email="emp1@beyondsure.com", password="Password123!", status="active")
        self.emp1 = Employee.objects.create(
            user=self.user1,
            organization=self.org1,
            branch=self.branch1,
            employee_code="EMP-101",
            joining_date=date(2024, 4, 1),
            employment_status=EmploymentStatus.ACTIVE,
        )
        self.comp1 = CompensationHistory.objects.create(
            employee=self.emp1,
            effective_from=date(2024, 4, 1),
            basic_salary=Decimal("100000.00"),  # Annual 12,00,000
        )

        # Employee 2 (Org 1)
        self.user2 = User.objects.create_user(email="emp2@beyondsure.com", password="Password123!", status="active")
        self.emp2 = Employee.objects.create(
            user=self.user2,
            organization=self.org1,
            branch=self.branch1,
            employee_code="EMP-102",
            joining_date=date(2024, 4, 1),
            employment_status=EmploymentStatus.ACTIVE,
        )
        self.comp2 = CompensationHistory.objects.create(
            employee=self.emp2,
            effective_from=date(2024, 4, 1),
            basic_salary=Decimal("40000.00"),  # Annual 4,80,000 (Low income / Zero tax)
        )

        # Org 2 Employee
        self.user_org2 = User.objects.create_user(email="emp_org2@competitor.com", password="Password123!", status="active")
        self.emp_org2 = Employee.objects.create(
            user=self.user_org2,
            organization=self.org2,
            branch=self.branch2,
            employee_code="COMP-201",
            joining_date=date(2024, 4, 1),
            employment_status=EmploymentStatus.ACTIVE,
        )

        # RBAC Setup
        self.admin_user = User.objects.create_user(email="admin@beyondsure.com", password="Password123!", status="active")
        self.emp_admin = Employee.objects.create(
            user=self.admin_user,
            organization=self.org1,
            employee_code="ADM-001",
            employment_status=EmploymentStatus.ACTIVE,
        )
        self.unauth_user = User.objects.create_user(email="unauth@beyondsure.com", password="Password123!", status="active")
        self.emp_unauth = Employee.objects.create(
            user=self.unauth_user,
            organization=self.org1,
            employee_code="UNAUTH-001",
            employment_status=EmploymentStatus.ACTIVE,
        )

        self.tax_admin_role = Role.objects.create(organization=self.org1, name="Tax Administrator")
        p_cfg, _ = Permission.objects.get_or_create(codename="payroll.tax_configure", defaults={"name": "Configure Tax", "resource": "payroll", "action": "tax_configure"})
        p_calc, _ = Permission.objects.get_or_create(codename="payroll.tax_calculate", defaults={"name": "Calc Tax", "resource": "payroll", "action": "tax_calculate"})
        p_view, _ = Permission.objects.get_or_create(codename="payroll.tax_view", defaults={"name": "View Tax", "resource": "payroll", "action": "tax_view"})
        RolePermission.objects.create(role=self.tax_admin_role, permission=p_cfg)
        RolePermission.objects.create(role=self.tax_admin_role, permission=p_calc)
        RolePermission.objects.create(role=self.tax_admin_role, permission=p_view)
        UserRole.objects.create(user=self.admin_user, role=self.tax_admin_role)

        # Payroll Period 1 (April 2024)
        self.period_apr = PayrollPeriod.objects.create(
            organization=self.org1,
            year=2024,
            month=4,
            start_date=date(2024, 4, 1),
            end_date=date(2024, 4, 30),
            status=PayrollPeriod.STATUS_DRAFT,
        )

    # =========================================================================
    # RULE ENGINE (1-10)
    # =========================================================================

    def test_1_correct_slab_selection(self):
        """1. Correct slab selection: taxable income spanning across multiple slabs."""
        # Income = 8,00,000 under Old Regime
        # 0 - 2,50,000 @ 0% = 0
        # 2,50,000 - 5,00,000 @ 5% = 12,500
        # 5,00,000 - 8,00,000 @ 20% = 60,000
        # Total = 72,500
        tax, details = calculate_slab_tax(Decimal("800000.00"), self.rule_old.slabs.all())
        self.assertEqual(tax, Decimal("72500.00"))
        self.assertEqual(len(details), 3)

    def test_2_boundary_below_slab(self):
        """2. Boundary below slab: taxable income strictly below lowest taxable threshold."""
        tax, details = calculate_slab_tax(Decimal("200000.00"), self.rule_old.slabs.all())
        self.assertEqual(tax, Decimal("0.00"))

    def test_3_exact_slab_boundary(self):
        """3. Exact slab boundary: taxable income exactly at ₹2,50,000 and ₹5,00,000."""
        tax_250k, _ = calculate_slab_tax(Decimal("250000.00"), self.rule_old.slabs.all())
        self.assertEqual(tax_250k, Decimal("0.00"))

        tax_500k, _ = calculate_slab_tax(Decimal("500000.00"), self.rule_old.slabs.all())
        self.assertEqual(tax_500k, Decimal("12500.00"))

    def test_4_boundary_above_slab(self):
        """4. Boundary above slab: taxable income crossing boundary by ₹1."""
        tax, _ = calculate_slab_tax(Decimal("250001.00"), self.rule_old.slabs.all())
        # ₹1 * 5% = 0.05
        self.assertEqual(tax, Decimal("0.05"))

    def test_5_invalid_overlapping_slabs(self):
        """5. Invalid overlapping slabs: configuration validation detects overlaps."""
        cfg = TaxRuleConfiguration.objects.create(
            organization=self.org1,
            financial_year=self.fy25,
            regime=TaxRuleConfiguration.REGIME_NEW,
            version_identifier="INVALID-OVERLAP",
            effective_from=date(2025, 4, 1),
        )
        TaxSlab.objects.create(rule_configuration=cfg, slab_order=1, lower_limit=Decimal("0.00"), upper_limit=Decimal("300000.00"), rate=Decimal("0.0000"))
        TaxSlab.objects.create(rule_configuration=cfg, slab_order=2, lower_limit=Decimal("250000.00"), upper_limit=Decimal("600000.00"), rate=Decimal("0.0500"))

        with self.assertRaises(ValidationError):
            cfg.validate_slabs()

    def test_6_invalid_negative_rates(self):
        """6. Invalid negative rates: slab rate cannot be negative."""
        slab = TaxSlab(rule_configuration=self.rule_old, slab_order=99, lower_limit=Decimal("0.00"), upper_limit=Decimal("100.00"), rate=Decimal("-0.0500"))
        with self.assertRaises(ValidationError):
            slab.clean()

    def test_7_missing_rule_configuration(self):
        """7. Missing rule configuration: engine raises TaxCalculationException safely."""
        with self.assertRaises(TaxCalculationException) as ctx:
            TaxCalculationService.get_active_tax_rule(
                organization=self.org1,
                financial_year=self.fy25,  # FY25 has no rules created yet
                regime="OLD",
                as_of_date=date(2025, 5, 1)
            )
        self.assertEqual(ctx.exception.code, 'MISSING_TAX_RULE_CONFIG')

    def test_8_financial_year_rule_selection(self):
        """8. Financial-year rule selection: selects correct rule for the FY."""
        rule = TaxCalculationService.get_active_tax_rule(
            organization=self.org1,
            financial_year=self.fy24,
            regime=TaxRuleConfiguration.REGIME_OLD,
            as_of_date=date(2024, 6, 1)
        )
        self.assertEqual(rule.version_identifier, "FY24-OLD-v1.0")
        self.assertEqual(rule.financial_year, self.fy24)

    def test_9_regime_rule_selection(self):
        """9. Regime rule selection: selects OLD vs NEW accurately."""
        r_old = TaxCalculationService.get_active_tax_rule(self.org1, self.fy24, "OLD")
        r_new = TaxCalculationService.get_active_tax_rule(self.org1, self.fy24, "NEW")
        self.assertEqual(r_old.regime, "OLD")
        self.assertEqual(r_new.regime, "NEW")
        self.assertEqual(r_new.standard_deduction, Decimal("75000.00"))

    def test_10_rule_version_selection(self):
        """10. Rule version selection: effective dating prioritizes active version for the period date."""
        # Create a second version active from Oct 1
        r_v2 = TaxRuleConfiguration.objects.create(
            organization=self.org1,
            financial_year=self.fy24,
            regime=TaxRuleConfiguration.REGIME_NEW,
            version_identifier="FY24-NEW-v2.0",
            effective_from=date(2024, 10, 1),
            effective_to=date(2025, 3, 31),
            standard_deduction=Decimal("80000.00"),
            is_active=True,
        )
        TaxSlab.objects.create(rule_configuration=r_v2, slab_order=1, lower_limit=Decimal("0.00"), upper_limit=None, rate=Decimal("0.1000"))

        # As of May: should get v1.0
        v_may = TaxCalculationService.get_active_tax_rule(self.org1, self.fy24, "NEW", as_of_date=date(2024, 5, 1))
        self.assertEqual(v_may.version_identifier, "FY24-NEW-v1.0")

        # As of November: should get v2.0
        v_nov = TaxCalculationService.get_active_tax_rule(self.org1, self.fy24, "NEW", as_of_date=date(2024, 11, 1))
        self.assertEqual(v_nov.version_identifier, "FY24-NEW-v2.0")

    # =========================================================================
    # OLD REGIME (11-16)
    # =========================================================================

    def test_11_taxable_income(self):
        """11. Old regime taxable income: gross minus standard deduction minus eligible verified deductions."""
        verified_inputs = {
            'has_verified_declaration': True,
            'tax_regime': 'OLD',
            'categories': {'80C': Decimal("100000.00")},
        }
        res = calculate_annual_tax(
            gross_taxable=Decimal("1000000.00"),
            verified_inputs=verified_inputs,
            rule_config=self.rule_old,
        )
        # Gross = 10,00,000, Std Ded = 50,000 -> 9,50,000; 80C = 1,00,000 -> Taxable = 8,50,000
        self.assertEqual(res['taxable_income'], Decimal("850000.00"))

    def test_12_standard_deduction(self):
        """12. Standard deduction: properly subtracted from gross income."""
        res = calculate_annual_tax(
            gross_taxable=Decimal("600000.00"),
            verified_inputs={'categories': {}},
            rule_config=self.rule_old,
        )
        self.assertEqual(res['standard_deduction'], Decimal("50000.00"))
        self.assertEqual(res['taxable_income'], Decimal("550000.00"))

    def test_13_verified_eligible_deductions(self):
        """13. Verified eligible deductions: caps applied properly to 80C and 80D."""
        verified_inputs = {
            'categories': {
                '80C': Decimal("200000.00"),  # Cap is 150,000
                '80D': Decimal("300000.00"),  # Cap is 25,000
            }
        }
        res = calculate_annual_tax(
            gross_taxable=Decimal("1200000.00"),
            verified_inputs=verified_inputs,
            rule_config=self.rule_old,
        )
        self.assertEqual(res['eligible_deductions']['80C'], Decimal("150000.00"))
        self.assertEqual(res['eligible_deductions']['80D'], Decimal("25000.00"))
        self.assertEqual(res['total_eligible_deductions'], Decimal("175000.00"))

    def test_14_ineligible_declaration_category(self):
        """14. Ineligible declaration category: disallowed category produces zero deduction."""
        verified_inputs = {'categories': {'UNKNOWN_SECTION': Decimal("50000.00")}}
        res = calculate_annual_tax(
            gross_taxable=Decimal("800000.00"),
            verified_inputs=verified_inputs,
            rule_config=self.rule_old,
        )
        self.assertEqual(res['total_eligible_deductions'], Decimal("0.00"))

    def test_15_rejected_declaration_excluded(self):
        """15. Rejected declaration excluded: TaxDeclarationService ignores rejected declarations."""
        decl = TaxDeclaration.objects.create(
            organization=self.org1,
            employee=self.emp1,
            financial_year=self.fy24,
            tax_regime=TaxDeclaration.REGIME_OLD,
            status=TaxDeclaration.STATUS_REJECTED,
        )
        InvestmentDeclaration.objects.create(
            declaration=decl,
            category=self.cat_80c,
            category_code="80C",
            declared_amount=Decimal("100000.00"),
            verified_amount=Decimal("100000.00"),
        )
        inputs = TaxDeclarationService.get_verified_declaration_inputs(self.emp1, self.fy24)
        self.assertFalse(inputs['has_verified_declaration'])
        self.assertEqual(inputs['total_verified_deductions'], Decimal("0.00"))

    def test_16_draft_declaration_excluded(self):
        """16. Draft declaration excluded: Draft declarations do not enter tax calculation."""
        decl = TaxDeclaration.objects.create(
            organization=self.org1,
            employee=self.emp1,
            financial_year=self.fy24,
            tax_regime=TaxDeclaration.REGIME_OLD,
            status=TaxDeclaration.STATUS_DRAFT,
        )
        InvestmentDeclaration.objects.create(
            declaration=decl,
            category=self.cat_80c,
            category_code="80C",
            declared_amount=Decimal("50000.00"),
        )
        inputs = TaxDeclarationService.get_verified_declaration_inputs(self.emp1, self.fy24)
        self.assertFalse(inputs['has_verified_declaration'])

    # =========================================================================
    # NEW REGIME (17-19)
    # =========================================================================

    def test_17_new_regime_taxable_income(self):
        """17. New-regime taxable income: uses New regime standard deduction (₹75,000)."""
        res = calculate_annual_tax(
            gross_taxable=Decimal("1200000.00"),
            verified_inputs={'categories': {}},
            rule_config=self.rule_new,
        )
        self.assertEqual(res['standard_deduction'], Decimal("75000.00"))
        self.assertEqual(res['taxable_income'], Decimal("1125000.00"))

    def test_18_new_regime_deduction_applicability(self):
        """18. New-regime deduction applicability: 80C and 80D disallowed under rule config."""
        verified_inputs = {'categories': {'80C': Decimal("150000.00"), '80D': Decimal("25000.00")}}
        res = calculate_annual_tax(
            gross_taxable=Decimal("1200000.00"),
            verified_inputs=verified_inputs,
            rule_config=self.rule_new,
        )
        self.assertEqual(res['eligible_deductions'].get('80C'), Decimal("0.00"))
        self.assertEqual(res['eligible_deductions'].get('80D'), Decimal("0.00"))
        self.assertEqual(res['total_eligible_deductions'], Decimal("0.00"))

    def test_19_old_only_deduction_excluded(self):
        """19. Old-only deduction excluded: verified 80C declaration produces 0 deduction in New Regime."""
        decl = TaxDeclaration.objects.create(
            organization=self.org1,
            employee=self.emp1,
            financial_year=self.fy24,
            tax_regime=TaxDeclaration.REGIME_NEW,
            status=TaxDeclaration.STATUS_VERIFIED,
        )
        InvestmentDeclaration.objects.create(
            declaration=decl,
            category=self.cat_80c,
            category_code="80C",
            declared_amount=Decimal("150000.00"),
            verified_amount=Decimal("150000.00"),
            status=InvestmentDeclaration.STATUS_VERIFIED,
        )
        calc = TaxCalculationService.calculate_monthly_tds(self.emp1, self.period_apr, current_gross=Decimal("100000.00"), preview=True)
        self.assertEqual(calc['total_eligible_deductions'], Decimal("0.00"))

    # =========================================================================
    # TDS ENGINE & EQUALIZATION (20-26)
    # =========================================================================

    def test_20_annual_tax_projection(self):
        """20. Annual tax projection: projects 12 months salary accurately."""
        # emp1 salary = 1,00,000/mo -> projected annual = 12,00,000
        calc = TaxCalculationService.calculate_monthly_tds(self.emp1, self.period_apr, current_gross=Decimal("100000.00"), preview=True)
        self.assertEqual(calc['projected_gross'], Decimal("1200000.00"))

    def test_21_ytd_tds(self):
        """21. YTD TDS: correctly aggregates TDS from finalized historical payroll periods."""
        # Period 1 Finalized
        self.period_apr.status = PayrollPeriod.STATUS_FINALIZED
        self.period_apr.save()
        PayrollRecord.objects.create(
            period=self.period_apr,
            employee=self.emp1,
            working_days=22,
            present_days=22,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal("22.0"),
            basic_salary=Decimal("100000.00"),
            gross_salary=Decimal("100000.00"),
            tds_amount=Decimal("7500.00"),
            net_salary=Decimal("92500.00"),
            status=PayrollRecord.STATUS_FINALIZED,
        )

        # Period 2 (May)
        period_may = PayrollPeriod.objects.create(
            organization=self.org1,
            year=2024,
            month=5,
            start_date=date(2024, 5, 1),
            end_date=date(2024, 5, 31),
            status=PayrollPeriod.STATUS_DRAFT,
        )
        ytd = TaxCalculationService.calculate_ytd_tds(self.emp1, self.fy24, exclude_period_id=period_may.id)
        self.assertEqual(ytd, Decimal("7500.00"))

    def test_22_remaining_liability(self):
        """22. Remaining liability: projected annual tax minus YTD TDS."""
        # Annual tax on 12L under New Regime (std ded 75k -> 11.25L taxable):
        # 0 - 3L: 0
        # 3L - 7L (4L @ 5%): 20,000
        # 7L - 10L (3L @ 10%): 30,000
        # 10L - 11.25L (1.25L @ 15%): 18,750
        # Subtotal: 68,750; Cess 4%: 2,750; Total: 71,500
        # If YTD TDS = 7,500 -> Remaining = 64,000
        self.period_apr.status = PayrollPeriod.STATUS_FINALIZED
        self.period_apr.save()
        PayrollRecord.objects.create(
            period=self.period_apr,
            employee=self.emp1,
            working_days=22,
            present_days=22,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal("22.0"),
            basic_salary=Decimal("100000.00"),
            gross_salary=Decimal("100000.00"),
            tds_amount=Decimal("7500.00"),
            net_salary=Decimal("92500.00"),
            status=PayrollRecord.STATUS_FINALIZED,
        )
        period_may = PayrollPeriod.objects.create(
            organization=self.org1,
            year=2024,
            month=5,
            start_date=date(2024, 5, 1),
            end_date=date(2024, 5, 31),
            status=PayrollPeriod.STATUS_DRAFT,
        )
        calc = TaxCalculationService.calculate_monthly_tds(self.emp1, period_may, current_gross=Decimal("100000.00"), preview=True)
        self.assertEqual(calc['annual_tax'], Decimal("71500.00"))
        self.assertEqual(calc['ytd_tds'], Decimal("7500.00"))
        self.assertEqual(calc['remaining_tax'], Decimal("64000.00"))

    def test_23_remaining_month_equalization(self):
        """23. Remaining-month equalization: divides remaining tax liability over remaining 11 months."""
        self.period_apr.status = PayrollPeriod.STATUS_FINALIZED
        self.period_apr.save()
        PayrollRecord.objects.create(
            period=self.period_apr,
            employee=self.emp1,
            working_days=22,
            present_days=22,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal("22.0"),
            basic_salary=Decimal("100000.00"),
            gross_salary=Decimal("100000.00"),
            tds_amount=Decimal("7150.00"),
            net_salary=Decimal("92850.00"),
            status=PayrollRecord.STATUS_FINALIZED,
        )
        period_may = PayrollPeriod.objects.create(
            organization=self.org1,
            year=2024,
            month=5,
            start_date=date(2024, 5, 1),
            end_date=date(2024, 5, 31),
            status=PayrollPeriod.STATUS_DRAFT,
        )
        calc = TaxCalculationService.calculate_monthly_tds(self.emp1, period_may, current_gross=Decimal("100000.00"), preview=True)
        self.assertEqual(calc['remaining_months'], 11)  # May 2024 to Mar 2025 = 11 months
        # Remaining: 71,500 - 7,150 = 64,350 / 11 = 5,850
        self.assertEqual(calc['monthly_tds'], Decimal("5850.00"))

    def test_24_final_month_adjustment(self):
        """24. Final-month adjustment: in March (month 12), monthly TDS equals full remaining liability."""
        period_mar = PayrollPeriod.objects.create(
            organization=self.org1,
            year=2025,
            month=3,
            start_date=date(2025, 3, 1),
            end_date=date(2025, 3, 31),
            status=PayrollPeriod.STATUS_DRAFT,
        )
        calc = TaxCalculationService.calculate_monthly_tds(self.emp1, period_mar, current_gross=Decimal("100000.00"), preview=True)
        self.assertEqual(calc['remaining_months'], 1)
        self.assertEqual(calc['monthly_tds'], calc['remaining_tax'])

    def test_25_ytd_tds_greater_than_annual_liability(self):
        """25. YTD TDS greater than annual liability: over-withholding yields 0 monthly TDS (no negative TDS)."""
        self.period_apr.status = PayrollPeriod.STATUS_FINALIZED
        self.period_apr.save()
        PayrollRecord.objects.create(
            period=self.period_apr,
            employee=self.emp1,
            working_days=22,
            present_days=22,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal("22.0"),
            basic_salary=Decimal("100000.00"),
            gross_salary=Decimal("100000.00"),
            tds_amount=Decimal("90000.00"),  # Excess deduction
            net_salary=Decimal("10000.00"),
            status=PayrollRecord.STATUS_FINALIZED,
        )
        period_may = PayrollPeriod.objects.create(
            organization=self.org1,
            year=2024,
            month=5,
            start_date=date(2024, 5, 1),
            end_date=date(2024, 5, 31),
            status=PayrollPeriod.STATUS_DRAFT,
        )
        calc = TaxCalculationService.calculate_monthly_tds(self.emp1, period_may, current_gross=Decimal("100000.00"), preview=True)
        self.assertEqual(calc['remaining_tax'], Decimal("0.00"))
        self.assertEqual(calc['monthly_tds'], Decimal("0.00"))

    def test_26_zero_tax(self):
        """26. Zero tax: employee below threshold/eligible for full rebate has 0 tax and 0 monthly TDS."""
        # emp2 has basic 40,000/mo -> 4,80,000 annual.
        # std ded 75,000 -> 4,05,000 taxable.
        # rebate threshold is 7,00,000, so rebate wipes out tax.
        calc = TaxCalculationService.calculate_monthly_tds(self.emp2, self.period_apr, current_gross=Decimal("40000.00"), preview=True)
        self.assertEqual(calc['annual_tax'], Decimal("0.00"))
        self.assertEqual(calc['monthly_tds'], Decimal("0.00"))

    # =========================================================================
    # EMPLOYEE LIFECYCLE (27-31)
    # =========================================================================

    def test_27_mid_year_joiner(self):
        """27. Mid-year joiner: joined in Nov 2024, remaining months = 5 (Nov, Dec, Jan, Feb, Mar)."""
        user_joiner = User.objects.create_user(email="joiner@beyondsure.com", password="Password123!", status="active")
        emp_joiner = Employee.objects.create(
            user=user_joiner,
            organization=self.org1,
            branch=self.branch1,
            employee_code="EMP-JOINER",
            joining_date=date(2024, 11, 1),
            employment_status=EmploymentStatus.ACTIVE,
        )
        CompensationHistory.objects.create(
            employee=emp_joiner,
            effective_from=date(2024, 11, 1),
            basic_salary=Decimal("100000.00"),
        )
        period_nov = PayrollPeriod.objects.create(
            organization=self.org1,
            year=2024,
            month=11,
            start_date=date(2024, 11, 1),
            end_date=date(2024, 11, 30),
            status=PayrollPeriod.STATUS_DRAFT,
        )
        calc = TaxCalculationService.calculate_monthly_tds(emp_joiner, period_nov, current_gross=Decimal("100000.00"), preview=True)
        # Nov to Mar = 5 months; projected gross = 5 * 1,00,000 = 5,00,000
        self.assertEqual(calc['remaining_months'], 5)
        self.assertEqual(calc['projected_gross'], Decimal("500000.00"))

    def test_28_early_exit(self):
        """28. Early exit: exiting in Dec 2024, remaining months stop at December."""
        self.emp1.exit_date = date(2024, 12, 31)
        self.emp1.save()

        period_oct = PayrollPeriod.objects.create(
            organization=self.org1,
            year=2024,
            month=10,
            start_date=date(2024, 10, 1),
            end_date=date(2024, 10, 31),
            status=PayrollPeriod.STATUS_DRAFT,
        )
        rem_months = TaxCalculationService.get_remaining_tds_months(self.emp1, period_oct, self.fy24)
        # Oct, Nov, Dec = 3 months
        self.assertEqual(rem_months, 3)

    def test_29_mid_year_salary_revision(self):
        """29. Mid-year salary revision: salary increment in Oct updates future projection without altering past payroll."""
        # Historic April finalized
        self.period_apr.status = PayrollPeriod.STATUS_FINALIZED
        self.period_apr.save()
        PayrollRecord.objects.create(
            period=self.period_apr,
            employee=self.emp1,
            working_days=22,
            present_days=22,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal("22.0"),
            basic_salary=Decimal("100000.00"),
            gross_salary=Decimal("100000.00"),
            tds_amount=Decimal("5958.00"),
            net_salary=Decimal("94042.00"),
            status=PayrollRecord.STATUS_FINALIZED,
        )

        # Salary revision effective Oct 1: 1,50,000
        CompensationHistory.objects.create(
            employee=self.emp1,
            effective_from=date(2024, 10, 1),
            basic_salary=Decimal("150000.00"),
        )
        period_oct = PayrollPeriod.objects.create(
            organization=self.org1,
            year=2024,
            month=10,
            start_date=date(2024, 10, 1),
            end_date=date(2024, 10, 31),
            status=PayrollPeriod.STATUS_DRAFT,
        )
        calc = TaxCalculationService.calculate_monthly_tds(self.emp1, period_oct, current_gross=Decimal("150000.00"), preview=True)
        # Projection incorporates higher future salary
        self.assertGreater(calc['projected_gross'], Decimal("1200000.00"))

    def test_30_backdated_salary_change(self):
        """30. Backdated salary change: handles updated compensation record without mutating finalized historical records."""
        # Finalized April record remains untouched
        self.period_apr.status = PayrollPeriod.STATUS_FINALIZED
        self.period_apr.save()
        rec = PayrollRecord.objects.create(
            period=self.period_apr,
            employee=self.emp1,
            working_days=22,
            present_days=22,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal("22.0"),
            basic_salary=Decimal("100000.00"),
            gross_salary=Decimal("100000.00"),
            tds_amount=Decimal("5958.00"),
            net_salary=Decimal("94042.00"),
            status=PayrollRecord.STATUS_FINALIZED,
        )

        # Backdated increment
        CompensationHistory.objects.create(
            employee=self.emp1,
            effective_from=date(2024, 4, 1),
            basic_salary=Decimal("120000.00"),
        )
        rec.refresh_from_db()
        self.assertEqual(rec.basic_salary, Decimal("100000.00"))
        self.assertEqual(rec.tds_amount, Decimal("5958.00"))

    def test_31_declaration_change_after_previous_payroll(self):
        """31. Declaration change after previous payroll: re-equalizes remaining tax liability across future months."""
        # Period 1 April processed with 0 declarations (New Regime)
        self.period_apr.status = PayrollPeriod.STATUS_FINALIZED
        self.period_apr.save()
        PayrollRecord.objects.create(
            period=self.period_apr,
            employee=self.emp1,
            working_days=22,
            present_days=22,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal("22.0"),
            basic_salary=Decimal("100000.00"),
            gross_salary=Decimal("100000.00"),
            tds_amount=Decimal("5958.00"),
            net_salary=Decimal("94042.00"),
            status=PayrollRecord.STATUS_FINALIZED,
        )

        # In May, employee submits Old Regime verified declaration with 80C & 80D
        decl = TaxDeclaration.objects.create(
            organization=self.org1,
            employee=self.emp1,
            financial_year=self.fy24,
            tax_regime=TaxDeclaration.REGIME_OLD,
            status=TaxDeclaration.STATUS_VERIFIED,
        )
        InvestmentDeclaration.objects.create(
            declaration=decl,
            category=self.cat_80c,
            category_code="80C",
            declared_amount=Decimal("150000.00"),
            verified_amount=Decimal("150000.00"),
            status=InvestmentDeclaration.STATUS_VERIFIED,
        )
        InvestmentDeclaration.objects.create(
            declaration=decl,
            category=self.cat_80d,
            category_code="80D",
            declared_amount=Decimal("25000.00"),
            verified_amount=Decimal("25000.00"),
            status=InvestmentDeclaration.STATUS_VERIFIED,
        )

        period_may = PayrollPeriod.objects.create(
            organization=self.org1,
            year=2024,
            month=5,
            start_date=date(2024, 5, 1),
            end_date=date(2024, 5, 31),
            status=PayrollPeriod.STATUS_DRAFT,
        )
        calc_may = TaxCalculationService.calculate_monthly_tds(self.emp1, period_may, current_gross=Decimal("100000.00"), preview=True)
        self.assertEqual(calc_may['regime'], "OLD")
        self.assertEqual(calc_may['total_eligible_deductions'], Decimal("175000.00"))
        # Historical April payroll remains unchanged
        rec_apr = PayrollRecord.objects.get(period=self.period_apr, employee=self.emp1)
        self.assertEqual(rec_apr.tds_amount, Decimal("5958.00"))

    # =========================================================================
    # PAYROLL INTEGRATION & IMMUTABILITY (32-36)
    # =========================================================================

    def test_32_tds_payroll_line_generated_correctly(self):
        """32. TDS payroll line generated correctly: PayslipLine with category='deduction' and code='TDS'."""
        generate_payroll_for_period(self.period_apr)
        self.period_apr.status = PayrollPeriod.STATUS_FINALIZED
        self.period_apr.save()
        self.period_apr.records.update(status=PayrollRecord.STATUS_FINALIZED)

        payslips = issue_payslips_for_period(self.period_apr)
        payslip_emp1 = [p for p in payslips if p.employee_code == "EMP-101"][0]

        tds_line = payslip_emp1.lines.filter(component_code="TDS").first()
        self.assertIsNotNone(tds_line)
        self.assertEqual(tds_line.category, PayslipLine.CATEGORY_DEDUCTION)
        self.assertGreater(tds_line.amount, Decimal("0.00"))

    def test_33_preview_does_not_persist(self):
        """33. Preview does not persist: API preview returns calculation without creating DB records."""
        initial_records_count = PayrollRecord.objects.count()
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post("/api/v1/payroll/tax/engine/preview/", {
            "employee_id": self.emp1.id,
            "period_id": self.period_apr.id,
            "current_gross": "100000.00"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(PayrollRecord.objects.count(), initial_records_count)

    def test_34_calculation_is_idempotent(self):
        """34. Calculation is idempotent: running generate_payroll_for_period twice yields identical results."""
        run1 = generate_payroll_for_period(self.period_apr)
        rec1 = PayrollRecord.objects.get(period=self.period_apr, employee=self.emp1)
        tds1 = rec1.tds_amount

        run2 = generate_payroll_for_period(self.period_apr)
        rec2 = PayrollRecord.objects.get(period=self.period_apr, employee=self.emp1)
        tds2 = rec2.tds_amount

        self.assertEqual(tds1, tds2)

    def test_35_finalized_payroll_remains_immutable(self):
        """35. Finalized payroll remains immutable: cannot re-generate finalized period."""
        generate_payroll_for_period(self.period_apr)
        self.period_apr.status = PayrollPeriod.STATUS_FINALIZED
        self.period_apr.save()

        with self.assertRaises(ValueError):
            generate_payroll_for_period(self.period_apr)

    def test_36_tax_snapshot_contains_rule_version_and_inputs(self):
        """36. Tax snapshot contains rule version, inputs, and calculation details."""
        generate_payroll_for_period(self.period_apr)
        rec = PayrollRecord.objects.get(period=self.period_apr, employee=self.emp1)
        snapshot = rec.tax_calculation_snapshot

        self.assertEqual(snapshot['tax_rule_version'], "FY24-NEW-v1.0")
        self.assertEqual(snapshot['regime'], "NEW")
        self.assertIn('taxable_income', snapshot)
        self.assertIn('annual_tax_liability', snapshot)
        self.assertIn('monthly_tds', snapshot)
        self.assertIn('slabs_applied', snapshot)
        self.assertIn('calculation_timestamp', snapshot)

    # =========================================================================
    # SECURITY & MULTI-TENANT ISOLATION (37-40)
    # =========================================================================

    def test_37_organization_isolation(self):
        """37. Organization isolation: Org 1 rules cannot be accessed or applied to Org 2."""
        with self.assertRaises(TaxCalculationException):
            # Org 2 employee cannot use Org 1 rule
            TaxCalculationService.get_active_tax_rule(
                organization=self.org2,
                financial_year=self.fy_org2,
                regime="NEW",
            )

    def test_38_employee_isolation(self):
        """38. Employee isolation: cross-tenant calculation preview returns 404."""
        self.client.force_authenticate(user=self.admin_user)
        # Attempting to calculate for emp_org2 in org1 context
        response = self.client.post("/api/v1/payroll/tax/engine/preview/", {
            "employee_id": self.emp_org2.id,
            "period_id": self.period_apr.id,
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_39_unauthorized_tax_configuration_access(self):
        """39. Unauthorized tax configuration access: unprivileged user cannot create tax rules."""
        self.client.force_authenticate(user=self.unauth_user)
        response = self.client.post("/api/v1/payroll/tax/rules/", {
            "financial_year": self.fy25.id,
            "regime": "NEW",
            "version_identifier": "HACK-RULE",
            "effective_from": "2025-04-01",
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_40_unauthorized_calculation_access(self):
        """40. Unauthorized calculation access: user without tax_calculate permission cannot preview."""
        self.client.force_authenticate(user=self.unauth_user)
        response = self.client.post("/api/v1/payroll/tax/engine/preview/", {
            "employee_id": self.emp1.id,
            "period_id": self.period_apr.id,
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # =========================================================================
    # AUDIT & DECIMAL PRECISION (41-42)
    # =========================================================================

    def test_41_rule_configuration_audit(self):
        """41. Rule configuration audit: creating a tax rule writes an AuditLog entry."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post("/api/v1/payroll/tax/rules/", {
            "financial_year": self.fy25.id,
            "regime": "NEW",
            "version_identifier": "AUDITED-v1.0",
            "effective_from": "2025-04-01",
            "standard_deduction": "75000.00",
            "rebate_income_threshold": "700000.00",
            "max_rebate_amount": "25000.00",
            "cess_rate": "0.0400",
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        audit_entry = AuditLog.objects.filter(
            action="TAX_RULE_CONFIG_CREATED",
            organization=self.org1,
        ).first()
        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry.actor, self.admin_user)

    def test_42_decimal_precision_no_float(self):
        """42. Decimal precision: calculations maintain exact Decimal precision without float inaccuracies."""
        res = calculate_annual_tax(
            gross_taxable=Decimal("1234567.89"),
            verified_inputs={'categories': {}},
            rule_config=self.rule_new,
        )
        self.assertIsInstance(res['gross_taxable'], Decimal)
        self.assertIsInstance(res['taxable_income'], Decimal)
        self.assertIsInstance(res['annual_tax'], Decimal)
        self.assertIsInstance(res['cess'], Decimal)
