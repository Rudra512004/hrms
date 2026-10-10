"""
Authoritative Tax Calculation and Progressive TDS Engine for BeyondSure HRMS.

Phase: P6.9C
Adheres to:
- Pure Decimal arithmetic (zero binary floating-point)
- Configurable, versioned, effective-dated tax rules
- Separation of preview vs. persist
- Audit snapshotting
- Organization/multi-tenant isolation
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Tuple, Optional, Sequence
from datetime import date
from django.utils import timezone
from django.db.models import Q, Sum

from apps.payroll.models import (
    PayrollPeriod,
    PayrollRecord,
    FinancialYear,
    TaxRuleConfiguration,
    TaxSlab,
    TaxSurchargeSlab,
    TaxRuleDeductionApplicability,
    TaxDeclarationCategory,
    TaxDeclaration,
    CompensationHistory,
)
from apps.employees.models import Employee
from apps.payroll.services_tax import TaxDeclarationService


class TaxCalculationException(Exception):
    """Raised when tax calculation cannot proceed due to missing or invalid inputs/rules."""
    def __init__(self, message: str, code: str = 'TAX_CALCULATION_ERROR'):
        super().__init__(message)
        self.message = message
        self.code = code


def calculate_slab_tax(
    taxable_income: Decimal,
    slabs: Sequence[TaxSlab]
) -> Tuple[Decimal, List[Dict[str, Any]]]:
    """
    Computes slab-wise tax on taxable_income across sorted slabs.
    Returns (total_slab_tax, list_of_applied_slab_breakdowns).
    """
    if taxable_income <= Decimal('0.00'):
        return Decimal('0.00'), []

    total_tax = Decimal('0.00')
    breakdowns = []

    # Sort slabs by slab_order
    sorted_slabs = sorted(slabs, key=lambda s: s.slab_order)

    for slab in sorted_slabs:
        if taxable_income <= slab.lower_limit:
            break

        upper = slab.upper_limit if slab.upper_limit is not None else taxable_income
        portion = max(Decimal('0.00'), min(taxable_income, upper) - slab.lower_limit)
        slab_tax = (portion * slab.rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_tax += slab_tax

        breakdowns.append({
            'slab_order': slab.slab_order,
            'lower_limit': str(slab.lower_limit),
            'upper_limit': str(slab.upper_limit) if slab.upper_limit is not None else None,
            'rate': str(slab.rate),
            'taxable_amount': str(portion),
            'tax_amount': str(slab_tax),
        })

    return total_tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), breakdowns


def calculate_rebate(
    taxable_income: Decimal,
    tax_before_rebate: Decimal,
    threshold: Decimal,
    max_rebate: Decimal
) -> Decimal:
    """
    Calculates relief under Section 87A or configured rebate rule.
    If taxable_income <= threshold, rebate is min(tax_before_rebate, max_rebate).
    """
    if threshold > Decimal('0.00') and taxable_income <= threshold:
        rebate = min(tax_before_rebate, max_rebate)
        return max(Decimal('0.00'), rebate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return Decimal('0.00')


def calculate_surcharge(
    taxable_income: Decimal,
    tax_after_rebate: Decimal,
    surcharge_slabs: Sequence[TaxSurchargeSlab]
) -> Decimal:
    """
    Applies highest applicable surcharge bracket based on taxable_income.
    """
    if not surcharge_slabs or tax_after_rebate <= Decimal('0.00'):
        return Decimal('0.00')

    # Find highest matching threshold
    applicable = [s for s in surcharge_slabs if taxable_income > s.threshold_amount]
    if not applicable:
        return Decimal('0.00')

    applicable_slab = max(applicable, key=lambda s: s.threshold_amount)
    surcharge = (tax_after_rebate * applicable_slab.rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return surcharge


def calculate_cess(tax_after_surcharge: Decimal, cess_rate: Optional[Decimal]) -> Decimal:
    """
    Calculates Health & Education Cess on tax after surcharge using the explicitly configured cess_rate.
    Raises TaxCalculationException if cess_rate is missing or None.
    """
    if cess_rate is None:
        raise TaxCalculationException(
            "Cess rate must be explicitly configured and cannot be None.",
            code='MISSING_CESS_CONFIG'
        )
    if tax_after_surcharge <= Decimal('0.00') or cess_rate <= Decimal('0.0000'):
        return Decimal('0.00')
    return (tax_after_surcharge * cess_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_annual_tax(
    gross_taxable: Decimal,
    verified_inputs: Dict[str, Any],
    rule_config: TaxRuleConfiguration
) -> Dict[str, Any]:
    """
    Executes the complete annual tax calculation pipeline:
    Gross Taxable Earnings
      ↓
    Standard Deduction
      ↓
    Eligible Deductions (Capped by Rule/Category Applicability)
      ↓
    Taxable Income (Rounded Section 288A)
      ↓
    Slab Tax
      ↓
    Rebate (Section 87A)
      ↓
    Surcharge
      ↓
    Cess
      ↓
    Annual Tax Liability
    """
    # 0. Validate rule completeness
    if rule_config.cess_rate is None:
        raise TaxCalculationException(
            f"Tax rule configuration '{rule_config.version_identifier}' is incomplete: cess_rate is not configured.",
            code='INCOMPLETE_TAX_RULE_CONFIG'
        )

    # 1. Standard deduction
    std_deduction = min(gross_taxable, rule_config.standard_deduction)
    income_after_std = max(Decimal('0.00'), gross_taxable - std_deduction)

    # 2. Eligible Deductions
    verified_cats = verified_inputs.get('categories', {})
    applied_deductions: Dict[str, Decimal] = {}
    total_deductions = Decimal('0.00')

    # Load deduction rules defined on this rule config
    rule_deductions = {r.category_code: r for r in rule_config.deduction_rules.all()}

    # Also load catalog categories for statutory max_limits and default applicability
    catalog_cats = {
        c.code: c for c in TaxDeclarationCategory.objects.filter(
            organization=rule_config.organization,
            is_active=True
        )
    }

    for cat_code, verified_amt in verified_cats.items():
        if verified_amt <= Decimal('0.00'):
            continue

        cat_obj = catalog_cats.get(cat_code)
        rule_obj = rule_deductions.get(cat_code)

        # Check applicability
        is_allowed = True
        cap: Optional[Decimal] = None

        if rule_obj is not None:
            is_allowed = rule_obj.is_allowed
            cap = rule_obj.max_deductible_limit
            if cap is None and cat_obj:
                cap = cat_obj.max_limit
        elif cat_obj is not None:
            if cat_obj.regime_applicability != TaxDeclarationCategory.REGIME_BOTH:
                if cat_obj.regime_applicability != rule_config.regime:
                    is_allowed = False
            cap = cat_obj.max_limit
        else:
            # Unrecognized category not in catalog or rule
            is_allowed = False

        if not is_allowed:
            applied_deductions[cat_code] = Decimal('0.00')
            continue

        deductible = verified_amt
        if cap is not None:
            deductible = min(deductible, cap)

        applied_deductions[cat_code] = deductible
        total_deductions += deductible

    # Deductions cannot reduce taxable income below 0
    effective_deductions = min(income_after_std, total_deductions)
    taxable_income = max(Decimal('0.00'), income_after_std - effective_deductions)
    # Section 288A: rounded to nearest integer
    taxable_income = taxable_income.quantize(Decimal('1.00'), rounding=ROUND_HALF_UP)

    # 3. Slab tax
    tax_before_rebate, slabs_detail = calculate_slab_tax(taxable_income, rule_config.slabs.all())

    # 4. Rebate
    rebate = calculate_rebate(
        taxable_income,
        tax_before_rebate,
        rule_config.rebate_income_threshold,
        rule_config.max_rebate_amount
    )
    tax_after_rebate = max(Decimal('0.00'), tax_before_rebate - rebate)

    # 5. Surcharge
    surcharge = calculate_surcharge(
        taxable_income,
        tax_after_rebate,
        rule_config.surcharge_slabs.all()
    )
    tax_after_surcharge = tax_after_rebate + surcharge

    # 6. Cess
    if rule_config.cess_rate is None:
        raise TaxCalculationException(
            f"Tax rule configuration '{rule_config.version_identifier}' is incomplete: cess_rate is not configured.",
            code='INCOMPLETE_TAX_RULE_CONFIG'
        )
    cess = calculate_cess(tax_after_surcharge, rule_config.cess_rate)

    # 7. Annual tax liability (Section 288B rounded to nearest integer)
    annual_tax = (tax_after_surcharge + cess).quantize(Decimal('1.00'), rounding=ROUND_HALF_UP)

    return {
        'gross_taxable': gross_taxable,
        'standard_deduction': std_deduction,
        'income_after_standard_deduction': income_after_std,
        'eligible_deductions': applied_deductions,
        'total_eligible_deductions': total_deductions,
        'taxable_income': taxable_income,
        'tax_before_rebate': tax_before_rebate,
        'rebate': rebate,
        'tax_after_rebate': tax_after_rebate,
        'surcharge': surcharge,
        'tax_after_surcharge': tax_after_surcharge,
        'cess': cess,
        'annual_tax': annual_tax,
        'slabs_applied': slabs_detail,
    }


class TaxCalculationService:
    """
    Authoritative service orchestrating annual projections, YTD deduction reconciliation,
    remaining-month equalization, and monthly TDS output.
    """

    @staticmethod
    def get_active_tax_rule(
        organization,
        financial_year: FinancialYear,
        regime: str,
        as_of_date: Optional[date] = None
    ) -> TaxRuleConfiguration:
        """
        Retrieves the authoritative active TaxRuleConfiguration for an organization,
        financial year, and regime as of a given date.
        Defaults as_of_date to financial_year.start_date if not specified.
        Validates slabs and rule configuration completeness before returning.
        """
        if as_of_date is None:
            as_of_date = financial_year.start_date

        rule = TaxRuleConfiguration.objects.filter(
            organization=organization,
            financial_year=financial_year,
            regime=regime,
            is_active=True,
            effective_from__lte=as_of_date,
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=as_of_date)
        ).order_by('-effective_from', '-created_at').first()

        if not rule:
            raise TaxCalculationException(
                f"No active tax rule configuration found for organization '{organization.name}', "
                f"financial year '{financial_year.name}', regime '{regime}' as of {as_of_date}.",
                code='MISSING_TAX_RULE_CONFIG'
            )

        # Validate slabs integrity
        rule.validate_slabs()

        # Validate rule configuration completeness
        if rule.cess_rate is None:
            raise TaxCalculationException(
                f"Tax rule configuration '{rule.version_identifier}' is incomplete: cess_rate is not configured.",
                code='INCOMPLETE_TAX_RULE_CONFIG'
            )

        return rule

    @staticmethod
    def get_remaining_tds_months(
        employee: Employee,
        period: PayrollPeriod,
        financial_year: FinancialYear
    ) -> int:
        """
        Calculates the number of remaining payroll periods for equalizing TDS,
        including the current period.
        Accounts for:
        - Financial year end date
        - Employee exit date (if exiting during the financial year)
        Returns an integer >= 1.
        """
        ceiling_date = financial_year.end_date
        if employee.exit_date and employee.exit_date < ceiling_date:
            ceiling_date = employee.exit_date

        if period.end_date > ceiling_date:
            return 1

        months_diff = (ceiling_date.year - period.year) * 12 + (ceiling_date.month - period.month) + 1
        return max(1, months_diff)

    @staticmethod
    def calculate_ytd_tds(
        employee: Employee,
        financial_year: FinancialYear,
        exclude_period_id: Optional[int] = None
    ) -> Decimal:
        """
        Calculates the cumulative TDS already deducted from authoritative finalized
        payroll records within the given financial year.
        Excludes the given period (e.g. current period being generated/previewed).
        """
        records = PayrollRecord.objects.filter(
            employee=employee,
            period__organization=financial_year.organization,
            period__start_date__gte=financial_year.start_date,
            period__end_date__lte=financial_year.end_date,
            status=PayrollRecord.STATUS_FINALIZED,
        )
        if exclude_period_id:
            records = records.exclude(period_id=exclude_period_id)

        total = records.aggregate(total_tds=Sum('tds_amount'))['total_tds']
        return (total or Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def project_annual_taxable_earnings(
        employee: Employee,
        period: PayrollPeriod,
        financial_year: FinancialYear,
        current_period_gross: Decimal
    ) -> Decimal:
        """
        Projects annual taxable earnings based on:
        1. Past finalized earnings in the current FY (or active compensation where unfinalized).
        2. Current period actual gross earnings.
        3. Future projected earnings based on effective compensation history up to min(fy_end, exit_date).
        """
        effective_start = financial_year.start_date
        if employee.joining_date and employee.joining_date > effective_start:
            effective_start = employee.joining_date

        effective_end = financial_year.end_date
        if employee.exit_date and employee.exit_date < effective_end:
            effective_end = employee.exit_date

        # Generate sequence of (year, month) from effective_start to effective_end
        months = []
        cur_y = effective_start.year
        cur_m = effective_start.month
        end_y = effective_end.year
        end_m = effective_end.month

        while (cur_y < end_y) or (cur_y == end_y and cur_m <= end_m):
            months.append((cur_y, cur_m))
            cur_m += 1
            if cur_m > 12:
                cur_m = 1
                cur_y += 1

        total_earnings = Decimal('0.00')

        for y, m in months:
            if y == period.year and m == period.month:
                total_earnings += current_period_gross
            elif (y < period.year) or (y == period.year and m < period.month):
                # Prior period: look for finalized record
                fin_rec = PayrollRecord.objects.filter(
                    employee=employee,
                    period__organization=financial_year.organization,
                    period__year=y,
                    period__month=m,
                    status=PayrollRecord.STATUS_FINALIZED,
                ).first()
                if fin_rec:
                    total_earnings += fin_rec.gross_salary
                else:
                    # Fallback to compensation active as of this month
                    m_date = date(y, m, 15)
                    comp = CompensationHistory.objects.filter(
                        employee=employee,
                        effective_from__lte=m_date,
                    ).filter(
                        Q(effective_to__isnull=True) | Q(effective_to__gte=m_date)
                    ).order_by('-effective_from').first()
                    if comp:
                        total_earnings += comp.basic_salary
            else:
                # Future period: look for scheduled/active compensation
                m_date = date(y, m, 15)
                comp = CompensationHistory.objects.filter(
                    employee=employee,
                    effective_from__lte=m_date,
                ).filter(
                    Q(effective_to__isnull=True) | Q(effective_to__gte=m_date)
                ).order_by('-effective_from').first()
                if comp:
                    total_earnings += comp.basic_salary

        return total_earnings.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_monthly_tds(
        cls,
        employee: Employee,
        period: PayrollPeriod,
        current_gross: Optional[Decimal] = None,
        preview: bool = False
    ) -> Dict[str, Any]:
        """
        Calculates monthly TDS for an employee for a specific payroll period.
        Returns full structured calculation data and audit snapshot.
        """
        # 1. Resolve Financial Year for period
        fy = FinancialYear.objects.filter(
            organization=period.organization,
            start_date__lte=period.start_date,
            end_date__gte=period.end_date,
            is_active=True,
        ).first()

        if not fy:
            raise TaxCalculationException(
                f"No active financial year found covering payroll period "
                f"{period.start_date} to {period.end_date} for organization '{period.organization.name}'.",
                code='MISSING_FINANCIAL_YEAR'
            )

        # 2. Retrieve verified declaration inputs
        declaration_inputs = TaxDeclarationService.get_verified_declaration_inputs(employee, fy)
        regime = declaration_inputs.get('tax_regime', TaxDeclaration.REGIME_NEW)

        # 3. Retrieve active tax rule configuration
        rule_config = cls.get_active_tax_rule(
            organization=period.organization,
            financial_year=fy,
            regime=regime,
            as_of_date=period.start_date
        )

        # 4. Resolve current period gross
        if current_gross is None:
            existing_record = PayrollRecord.objects.filter(period=period, employee=employee).first()
            if existing_record:
                current_gross = existing_record.gross_salary
            else:
                current_gross = Decimal('0.00')

        # 5. Project annual taxable earnings
        projected_gross = cls.project_annual_taxable_earnings(employee, period, fy, current_gross)

        # 6. Execute annual tax calculation pipeline
        annual_calc = calculate_annual_tax(projected_gross, declaration_inputs, rule_config)
        annual_tax = annual_calc['annual_tax']

        # 7. Compute YTD TDS already deducted
        ytd_tds = cls.calculate_ytd_tds(employee, fy, exclude_period_id=period.id)

        # 8. Remaining tax liability
        remaining_liability = max(Decimal('0.00'), annual_tax - ytd_tds)

        # 9. Remaining months equalization
        remaining_months = cls.get_remaining_tds_months(employee, period, fy)

        if remaining_liability <= Decimal('0.00'):
            monthly_tds = Decimal('0.00')
        elif remaining_months <= 1:
            # Final month adjustment
            monthly_tds = remaining_liability
        else:
            monthly_tds = (remaining_liability / Decimal(remaining_months)).quantize(
                Decimal('1.00'), rounding=ROUND_HALF_UP
            )
            # Ensure monthly TDS does not exceed remaining liability
            monthly_tds = min(monthly_tds, remaining_liability)

        # 10. Assemble complete audit snapshot
        snapshot = {
            'financial_year_id': fy.id,
            'financial_year_name': fy.name,
            'regime': regime,
            'tax_rule_version': rule_config.version_identifier,
            'tax_rule_id': rule_config.id,
            'projected_annual_gross': str(projected_gross),
            'standard_deduction': str(annual_calc['standard_deduction']),
            'eligible_deductions': {k: str(v) for k, v in annual_calc['eligible_deductions'].items()},
            'total_eligible_deductions': str(annual_calc['total_eligible_deductions']),
            'taxable_income': str(annual_calc['taxable_income']),
            'tax_before_rebate': str(annual_calc['tax_before_rebate']),
            'rebate': str(annual_calc['rebate']),
            'tax_after_rebate': str(annual_calc['tax_after_rebate']),
            'surcharge': str(annual_calc['surcharge']),
            'cess': str(annual_calc['cess']),
            'annual_tax_liability': str(annual_tax),
            'ytd_tds': str(ytd_tds),
            'remaining_tax_liability': str(remaining_liability),
            'remaining_tds_months': remaining_months,
            'monthly_tds': str(monthly_tds),
            'slabs_applied': annual_calc['slabs_applied'],
            'has_verified_declaration': declaration_inputs.get('has_verified_declaration', False),
            'declaration_id': declaration_inputs.get('declaration_id'),
            'calculation_timestamp': timezone.now().isoformat(),
        }

        return {
            'employee_id': employee.id,
            'period_id': period.id,
            'financial_year': fy.name,
            'regime': regime,
            'tax_rule_version': rule_config.version_identifier,
            'projected_gross': projected_gross,
            'standard_deduction': annual_calc['standard_deduction'],
            'total_eligible_deductions': annual_calc['total_eligible_deductions'],
            'taxable_income': annual_calc['taxable_income'],
            'tax_before_rebate': annual_calc['tax_before_rebate'],
            'rebate': annual_calc['rebate'],
            'surcharge': annual_calc['surcharge'],
            'cess': annual_calc['cess'],
            'annual_tax': annual_tax,
            'ytd_tds': ytd_tds,
            'remaining_tax': remaining_liability,
            'remaining_months': remaining_months,
            'monthly_tds': monthly_tds,
            'deductions_used': annual_calc['eligible_deductions'],
            'snapshot': snapshot,
        }
