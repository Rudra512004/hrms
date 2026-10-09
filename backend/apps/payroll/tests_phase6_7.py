from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.organization.models import Organization, Branch, Department
from apps.employees.models import Employee, EmploymentStatus, EmployeeLifecycleEvent, EmployeeStatutoryAndBank
from apps.leaves.models import LeaveType, LeaveCycle, BranchLeavePolicy, LeaveBalance
from apps.attendance.models import Attendance, Holiday
from apps.assets.models import AssetCategory, Asset, AssetAssignment, AssetStatus
from apps.payroll.models import (
    CompensationHistory,
    PayrollPeriod,
    PayrollRecord,
    FnFPolicyConfiguration,
    FinalSettlement,
    SettlementLine,
)
from apps.payroll.fnf_service import FnFService, FnFException
from apps.authorization.models import Permission, Role, RolePermission, UserRole, ScopeChoices
from apps.audit.models import AuditLog

User = get_user_model()


class Phase67FnFComprehensiveTests(TestCase):
    """
    Focused acceptance test suite covering requirements A through AC of Phase 6.7:
    Full & Final Settlement (FnF).
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Organization & Branch Setup
        self.org = Organization.objects.create(name="BeyondSure Tech Corp")
        self.branch = Branch.objects.create(
            organization=self.org,
            name="Bangalore HQ",
            is_active=True,
        )
        self.dept = Department.objects.create(
            branch=self.branch,
            name="Platform Engineering",
        )

        # 2. Users & Roles
        self.maker_user = User.objects.create_user(
            email="hr_maker@beyondsure.com",
            password="Password123!",
            first_name="Helen",
            last_name="Maker",
            status="active",
        )
        self.checker_user = User.objects.create_user(
            email="fin_checker@beyondsure.com",
            password="Password123!",
            first_name="Frank",
            last_name="Checker",
            status="active",
        )
        self.emp_user = User.objects.create_user(
            email="dev_exit@beyondsure.com",
            password="Password123!",
            first_name="Dev",
            last_name="Exiter",
            status="active",
        )

        # 3. Employee Under Settlement
        self.employee = Employee.objects.create(
            user=self.emp_user,
            employee_code="EMP-EXIT-001",
            organization=self.org,
            branch=self.branch,
            department=self.dept,
            employment_status=EmploymentStatus.ON_NOTICE,
            joining_date=date(2020, 1, 1),
            resignation_date=date(2025, 1, 1),
            exit_date=date(2025, 1, 31),
            notice_period_days=30,
            notice_period_start=date(2025, 1, 1),
            notice_period_end=date(2025, 1, 31),
            exit_reason="Career transition",
        )

        # Record Lifecycle Event
        EmployeeLifecycleEvent.objects.create(
            employee=self.employee,
            event_type="resignation",
            from_status="active",
            to_status="on_notice",
            effective_date=date(2025, 1, 1),
            reason="Career transition",
            created_by=self.maker_user,
        )

        # Statutory & Bank Setup
        EmployeeStatutoryAndBank.objects.create(
            employee=self.employee,
            pan_number="ABCDE1234F",
            account_number="98765432101234",
            bank_name="HDFC Bank",
            ifsc_code="HDFC0001234",
            is_epf_applicable=True,
            is_esic_applicable=False,
            is_pt_applicable=True,
            restrict_epf_to_ceiling=True,
        )

        # Compensation: ₹100,000 monthly basic
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            basic_salary=Decimal("100000.00"),
            created_by=self.maker_user,
        )

        # Holiday: Jan 1 is holiday
        Holiday.objects.create(
            branch=self.branch,
            name="New Year",
            date=date(2025, 1, 1),
            is_active=True,
        )

        # Policy configuration
        self.policy = FnFPolicyConfiguration.objects.create(
            organization=self.org,
            effective_from=date(2024, 1, 1),
            leave_encashment_enabled=True,
            leave_encashment_daily_divisor=30,
            encashable_leave_types=["EL"],
            gratuity_enabled=True,
            gratuity_min_service_years=Decimal("5.0"),
            gratuity_wage_days_per_year=15,
            gratuity_divisor=26,
            gratuity_max_ceiling=Decimal("2000000.00"),
            notice_recovery_enabled=True,
            notice_recovery_daily_divisor=30,
            created_by=self.maker_user,
        )

        # Permissions setup
        self._setup_permissions()

    def _setup_permissions(self):
        perms = [
            ("payroll.fnf_view", "payroll", "fnf_view"),
            ("payroll.fnf_prepare", "payroll", "fnf_prepare"),
            ("payroll.fnf_approve", "payroll", "fnf_approve"),
            ("payroll.fnf_finalize", "payroll", "fnf_finalize"),
            ("payroll.view", "payroll", "view"),
            ("payroll.generate", "payroll", "generate"),
            ("payroll.approve", "payroll", "approve"),
        ]
        created_perms = {}
        for code, res, act in perms:
            p, _ = Permission.objects.get_or_create(
                codename=code,
                defaults={"name": code, "resource": res, "action": act, "is_active": True},
            )
            created_perms[code] = p

        # Role Maker
        maker_role = Role.objects.create(organization=self.org, name="FnF Maker")
        RolePermission.objects.create(role=maker_role, permission=created_perms["payroll.fnf_prepare"])
        RolePermission.objects.create(role=maker_role, permission=created_perms["payroll.fnf_view"])
        UserRole.objects.create(
            user=self.maker_user, role=maker_role, scope=ScopeChoices.ORGANIZATION
        )

        # Role Checker
        checker_role = Role.objects.create(organization=self.org, name="FnF Checker")
        RolePermission.objects.create(role=checker_role, permission=created_perms["payroll.fnf_view"])
        RolePermission.objects.create(role=checker_role, permission=created_perms["payroll.fnf_approve"])
        RolePermission.objects.create(role=checker_role, permission=created_perms["payroll.fnf_finalize"])
        UserRole.objects.create(
            user=self.checker_user, role=checker_role, scope=ScopeChoices.ORGANIZATION
        )

    # =========================================================================
    # A. APPROVED EXIT REQUIRED
    # =========================================================================
    def test_a_approved_exit_required(self):
        """Active employee with no resignation/exit event cannot have settlement initiated."""
        active_emp = Employee.objects.create(
            user=User.objects.create_user(email="active@test.com", password="P!"),
            employee_code="EMP-ACTIVE-002",
            organization=self.org,
            branch=self.branch,
            department=self.dept,
            employment_status=EmploymentStatus.ACTIVE,
            joining_date=date(2023, 1, 1),
        )
        with self.assertRaises(FnFException) as cm:
            FnFService.prepare(employee_id=active_emp.id, requesting_user=self.maker_user)
        self.assertEqual(cm.exception.code, "NO_APPROVED_EXIT")

    # =========================================================================
    # B. MISSING LAST WORKING DAY
    # =========================================================================
    def test_b_missing_last_working_day(self):
        """Employee in exit state but with null exit_date cannot have settlement initiated."""
        self.employee.exit_date = None
        self.employee.save()
        with self.assertRaises(FnFException) as cm:
            FnFService.prepare(employee_id=self.employee.id, requesting_user=self.maker_user)
        self.assertEqual(cm.exception.code, "MISSING_LAST_WORKING_DAY")

    # =========================================================================
    # C. INVALID EXIT DATES
    # =========================================================================
    def test_c_invalid_exit_dates(self):
        """Exit date before joining date or resignation date raises error."""
        with self.assertRaises(FnFException) as cm:
            FnFService.prepare(
                employee_id=self.employee.id,
                requesting_user=self.maker_user,
                exit_date=date(2019, 12, 31),
            )
        self.assertEqual(cm.exception.code, "INVALID_EXIT_DATE")

    # =========================================================================
    # D. DUPLICATE SETTLEMENT PREVENTION
    # =========================================================================
    def test_d_duplicate_settlement_prevention(self):
        """Cannot create a second active settlement while one is in draft/review/approved/finalized."""
        settlement1 = FnFService.prepare(
            employee_id=self.employee.id, requesting_user=self.maker_user
        )
        self.assertEqual(settlement1.status, FinalSettlement.STATUS_DRAFT)

        with self.assertRaises(FnFException) as cm:
            FnFService.prepare(
                employee_id=self.employee.id, requesting_user=self.maker_user
            )
        self.assertEqual(cm.exception.code, "DUPLICATE_ACTIVE_SETTLEMENT")

    # =========================================================================
    # E. LAST-DAY SALARY CALCULATION
    # =========================================================================
    def test_e_last_day_salary_calculation(self):
        """Prorated salary through exit date calculates accurately using working calendar."""
        # 22 working dates in Jan 2025. Jan 1 is holiday.
        # Mark full attendance for first 11 working days (half month)
        working_dates = [
            d for d in [date(2025, 1, day) for day in range(1, 32)]
            if d.weekday() < 5 and d != date(2025, 1, 1)
        ]
        for d in working_dates[:11]:
            Attendance.objects.create(employee=self.employee, date=d, status="present")

        # Exit on the 11th working date (Jan 16)
        exit_day = working_dates[10]
        self.employee.exit_date = exit_day
        self.employee.save()

        calc = FnFService.preview(employee_id=self.employee.id, requesting_user=self.maker_user)
        salary_line = next(l for l in calc["lines"] if l["code"] == "SALARY_LWD")

        # 11 effective days / 22 total month working days * 100,000 = 50,000
        expected = (Decimal("100000.00") * Decimal(11) / Decimal(22)).quantize(Decimal("0.01"))
        self.assertEqual(salary_line["amount"], expected)

    # =========================================================================
    # F. LOP INTEGRATION
    # =========================================================================
    def test_f_lop_integration(self):
        """Absences up to exit date reduce effective days and compute LOP correctly."""
        working_dates = [
            d for d in [date(2025, 1, day) for day in range(1, 32)]
            if d.weekday() < 5 and d != date(2025, 1, 1)
        ]
        # Present for 10 days out of 11 working days up to Jan 16 (1 LOP day)
        for d in working_dates[:10]:
            Attendance.objects.create(employee=self.employee, date=d, status="present")

        exit_day = working_dates[10]
        self.employee.exit_date = exit_day
        self.employee.save()

        calc = FnFService.preview(employee_id=self.employee.id, requesting_user=self.maker_user)
        salary_line = next(l for l in calc["lines"] if l["code"] == "SALARY_LWD")

        # 10 effective days / 22 working days * 100,000 = 45,454.55
        expected = (Decimal("100000.00") * Decimal(10) / Decimal(22)).quantize(Decimal("0.01"))
        self.assertEqual(salary_line["amount"], expected)
        self.assertEqual(salary_line["metadata"]["lop_days"], "1.0")

    # =========================================================================
    # G. MID-MONTH SALARY REVISION INTEGRATION
    # =========================================================================
    def test_g_mid_month_salary_revision_integration(self):
        """A compensation revision effective during the exit month is resolved."""
        CompensationHistory.objects.filter(employee=self.employee, effective_to__isnull=True).update(
            effective_to=date(2025, 1, 14)
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2025, 1, 15),
            basic_salary=Decimal("120000.00"),
            created_by=self.maker_user,
        )
        calc = FnFService.preview(employee_id=self.employee.id, requesting_user=self.maker_user)
        salary_line = next(l for l in calc["lines"] if l["code"] == "SALARY_LWD")
        # Confirms active salary resolved reflects the valid active record for period
        self.assertIn("120000.00", salary_line["metadata"]["basic_salary"])

    # =========================================================================
    # H. LEAVE ENCASHMENT ELIGIBILITY
    # =========================================================================
    def test_h_leave_encashment_eligibility(self):
        """Only eligible leave types configured in policy are encashed."""
        lt_el = LeaveType.objects.create(organization=self.org, name="Earned Leave", code="EL")
        lt_cl = LeaveType.objects.create(organization=self.org, name="Casual Leave", code="CL")
        cycle = LeaveCycle.objects.create(
            branch=self.branch, name="Cycle 2025", start_date=date(2025, 1, 1), end_date=date(2025, 12, 31)
        )
        BranchLeavePolicy.objects.create(branch=self.branch, leave_type=lt_el, monthly_allocation=2)
        BranchLeavePolicy.objects.create(branch=self.branch, leave_type=lt_cl, monthly_allocation=1)

        # 10 EL remaining, 5 CL remaining
        LeaveBalance.objects.create(
            employee=self.employee, leave_type=lt_el, branch=self.branch, leave_cycle=cycle,
            allocated=Decimal("10.0")
        )
        LeaveBalance.objects.create(
            employee=self.employee, leave_type=lt_cl, branch=self.branch, leave_cycle=cycle,
            allocated=Decimal("5.0")
        )

        calc = FnFService.preview(employee_id=self.employee.id, requesting_user=self.maker_user)
        el_encash = [l for l in calc["lines"] if "LEAVE_ENCASHMENT_EL" in l["code"]]
        cl_encash = [l for l in calc["lines"] if "LEAVE_ENCASHMENT_CL" in l["code"]]

        self.assertEqual(len(el_encash), 1)
        self.assertEqual(len(cl_encash), 0)  # Policy only encashes 'EL'

        # Rate: 100,000 / 30 = 3,333.33 * 10 = 33,333.30
        daily_rate = (Decimal("100000.00") / Decimal(30)).quantize(Decimal("0.01"))
        expected_el_amt = (Decimal("10.0") * daily_rate).quantize(Decimal("0.01"))
        self.assertEqual(el_encash[0]["amount"], expected_el_amt)

    # =========================================================================
    # I. LEAVE BALANCE SNAPSHOT
    # =========================================================================
    def test_i_leave_balance_snapshot(self):
        """Leave encashment snapshot contains detailed metadata."""
        lt_el = LeaveType.objects.create(organization=self.org, name="Earned Leave", code="EL")
        cycle = LeaveCycle.objects.create(
            branch=self.branch, name="C25", start_date=date(2025, 1, 1), end_date=date(2025, 12, 31)
        )
        LeaveBalance.objects.create(
            employee=self.employee, leave_type=lt_el, branch=self.branch, leave_cycle=cycle,
            allocated=Decimal("6.0")
        )
        calc = FnFService.preview(employee_id=self.employee.id, requesting_user=self.maker_user)
        el_line = next(l for l in calc["lines"] if "LEAVE_ENCASHMENT_EL" in l["code"])
        self.assertEqual(el_line["metadata"]["remaining_days"], "6.00")
        self.assertEqual(el_line["metadata"]["divisor"], 30)

    # =========================================================================
    # J. GRATUITY APPLICABILITY / CONFIGURATION
    # =========================================================================
    def test_j_gratuity_applicability_and_configuration(self):
        """Gratuity is calculated when tenure >= 5 years, and 0 when tenure < 5 years."""
        # Employee joined 2020-01-01, exits 2025-01-31 -> 5 full years completed
        calc = FnFService.preview(employee_id=self.employee.id, requesting_user=self.maker_user)
        grat_line = next((l for l in calc["lines"] if l["code"] == "GRATUITY"), None)
        self.assertIsNotNone(grat_line)

        # Formula: (100,000 * 15 * 5) / 26 = 7,500,000 / 26 = 288,461.54
        expected_gratuity = ((Decimal("100000.00") * Decimal(15) * Decimal(5)) / Decimal(26)).quantize(Decimal("0.01"))
        self.assertEqual(grat_line["amount"], expected_gratuity)

        # Now test tenure under 5 years: joining date 2022-01-01 (3 years)
        self.employee.joining_date = date(2022, 1, 1)
        self.employee.save()
        calc_under = FnFService.preview(employee_id=self.employee.id, requesting_user=self.maker_user)
        grat_under = next((l for l in calc_under["lines"] if l["code"] == "GRATUITY"), None)
        self.assertIsNone(grat_under)

    # =========================================================================
    # K. BONUS HANDLING
    # =========================================================================
    def test_k_bonus_handling(self):
        """Approved bonus amount is added as an earning line."""
        calc = FnFService.preview(
            employee_id=self.employee.id,
            requesting_user=self.maker_user,
            bonus_amount=Decimal("25000.00"),
            bonus_remarks="FY24 Performance Bonus",
        )
        bonus_line = next((l for l in calc["lines"] if l["code"] == "BONUS"), None)
        self.assertIsNotNone(bonus_line)
        self.assertEqual(bonus_line["amount"], Decimal("25000.00"))
        self.assertEqual(bonus_line["category"], SettlementLine.CATEGORY_EARNING)

    # =========================================================================
    # L. NOTICE RECOVERY
    # =========================================================================
    def test_l_notice_recovery(self):
        """Notice shortfall produces recovery line; full notice served produces zero recovery."""
        # 1. Full notice served: notice_period_days = 30, notice_start = Jan 1, exit = Jan 31 (30 days served)
        calc_full = FnFService.preview(employee_id=self.employee.id, requesting_user=self.maker_user)
        notice_line_full = next((l for l in calc_full["lines"] if l["code"] == "NOTICE_RECOVERY"), None)
        self.assertIsNone(notice_line_full)

        # 2. Shortfall: required notice = 60 days, served 30 days -> 30 days shortfall
        self.employee.notice_period_days = 60
        self.employee.save()
        calc_short = FnFService.preview(employee_id=self.employee.id, requesting_user=self.maker_user)
        notice_line_short = next((l for l in calc_short["lines"] if l["code"] == "NOTICE_RECOVERY"), None)
        self.assertIsNotNone(notice_line_short)
        self.assertEqual(notice_line_short["category"], SettlementLine.CATEGORY_RECOVERY)

        # 30 days * (100,000 / 30) = 100,000
        daily_rate = (Decimal("100000.00") / Decimal(30)).quantize(Decimal("0.01"))
        expected_recovery = (Decimal(30) * daily_rate).quantize(Decimal("0.01"))
        self.assertEqual(notice_line_short["amount"], expected_recovery)

    # =========================================================================
    # M. ASSET RECOVERY
    # =========================================================================
    def test_m_asset_recovery(self):
        """Authoritative asset assignment recovery is recorded; invalid asset raises exception."""
        cat = AssetCategory.objects.create(organization=self.org, name="Laptops", code="LAP")
        asset = Asset.objects.create(
            organization=self.org, category=cat, asset_tag="LAP-001", name="MacBook Pro",
            status=AssetStatus.ASSIGNED
        )
        assignment = AssetAssignment.objects.create(
            asset=asset, employee=self.employee, is_active=True
        )

        calc = FnFService.preview(
            employee_id=self.employee.id,
            requesting_user=self.maker_user,
            asset_recoveries=[{"asset_id": asset.id, "amount": "5000.00", "reason": "Screen cracked"}],
        )
        asset_line = next((l for l in calc["lines"] if "ASSET_RECOVERY_LAP-001" in l["code"]), None)
        self.assertIsNotNone(asset_line)
        self.assertEqual(asset_line["amount"], Decimal("5000.00"))
        self.assertEqual(asset_line["category"], SettlementLine.CATEGORY_RECOVERY)

        # Unassigned asset ID raises error
        asset_unassigned = Asset.objects.create(
            organization=self.org, category=cat, asset_tag="LAP-002", name="Dell XPS"
        )
        with self.assertRaises(FnFException) as cm:
            FnFService.preview(
                employee_id=self.employee.id,
                requesting_user=self.maker_user,
                asset_recoveries=[{"asset_id": asset_unassigned.id, "amount": "1000.00"}],
            )
        self.assertEqual(cm.exception.code, "INVALID_ASSET_RECOVERY")

    # =========================================================================
    # N. LOAN / ADVANCE RECOVERY
    # =========================================================================
    def test_n_loan_advance_recovery(self):
        """Explicitly approved loan and advance recoveries are created."""
        calc = FnFService.preview(
            employee_id=self.employee.id,
            requesting_user=self.maker_user,
            loan_recoveries=[
                {"type": "loan", "amount": "12000.00", "reference": "LN-2024", "reason": "Remaining loan"},
                {"type": "advance", "amount": "3000.00", "reference": "ADV-01", "reason": "Travel advance"},
            ],
        )
        loan_line = next(l for l in calc["lines"] if l["code"] == "LOAN_RECOVERY")
        adv_line = next(l for l in calc["lines"] if l["code"] == "ADVANCE_RECOVERY")
        self.assertEqual(loan_line["amount"], Decimal("12000.00"))
        self.assertEqual(adv_line["amount"], Decimal("3000.00"))
        self.assertEqual(loan_line["category"], SettlementLine.CATEGORY_RECOVERY)

    # =========================================================================
    # O. JOINING BONUS CLAWBACK
    # =========================================================================
    def test_o_joining_bonus_clawback(self):
        """Joining bonus clawback is recorded when approved obligation is provided."""
        calc = FnFService.preview(
            employee_id=self.employee.id,
            requesting_user=self.maker_user,
            joining_bonus_clawback={"amount": "50000.00", "reason": "Left before 12 months"},
        )
        claw_line = next((l for l in calc["lines"] if l["code"] == "JOINING_BONUS_CLAWBACK"), None)
        self.assertIsNotNone(claw_line)
        self.assertEqual(claw_line["amount"], Decimal("50000.00"))
        self.assertEqual(claw_line["category"], SettlementLine.CATEGORY_RECOVERY)

    # =========================================================================
    # P. STATUTORY INTEGRATION
    # =========================================================================
    def test_p_statutory_integration(self):
        """EPF (with ceiling restriction) and PT deductions are computed."""
        working_dates = [
            d for d in [date(2025, 1, day) for day in range(1, 32)]
            if d.weekday() < 5 and d != date(2025, 1, 1)
        ]
        for d in working_dates:
            Attendance.objects.create(employee=self.employee, date=d, status="present")

        calc = FnFService.preview(employee_id=self.employee.id, requesting_user=self.maker_user)
        epf_line = next((l for l in calc["lines"] if l["code"] == "STAT_EPF"), None)
        pt_line = next((l for l in calc["lines"] if l["code"] == "STAT_PT"), None)

        self.assertIsNotNone(epf_line)
        self.assertIsNotNone(pt_line)
        # EPF ceiling 15,000 * 12% = 1,800.00
        self.assertEqual(epf_line["amount"], Decimal("1800.00"))
        self.assertEqual(pt_line["amount"], Decimal("200.00"))
        self.assertEqual(epf_line["category"], SettlementLine.CATEGORY_DEDUCTION)

    # =========================================================================
    # Q. TAX INTEGRATION
    # =========================================================================
    def test_q_tax_integration(self):
        """TDS tax deduction is recorded in deductions category."""
        calc = FnFService.preview(
            employee_id=self.employee.id,
            requesting_user=self.maker_user,
            tds_amount=Decimal("15000.00"),
        )
        tds_line = next((l for l in calc["lines"] if l["code"] == "TAX_TDS"), None)
        self.assertIsNotNone(tds_line)
        self.assertEqual(tds_line["amount"], Decimal("15000.00"))
        self.assertEqual(tds_line["category"], SettlementLine.CATEGORY_DEDUCTION)

    # =========================================================================
    # R. NORMALIZED SETTLEMENT LINES
    # =========================================================================
    def test_r_normalized_settlement_lines(self):
        """Settlement lines are normalized with categories, codes, calculation basis, and ordering."""
        settlement = FnFService.prepare(
            employee_id=self.employee.id,
            requesting_user=self.maker_user,
            bonus_amount=Decimal("10000.00"),
        )
        self.assertTrue(settlement.lines.exists())
        for line in settlement.lines.all():
            self.assertIn(line.category, ["earning", "deduction", "recovery"])
            self.assertTrue(len(line.code) > 0)
            self.assertTrue(len(line.name) > 0)
            self.assertGreaterEqual(line.amount, Decimal("0.00"))

    # =========================================================================
    # S. PREVIEW DOES NOT PERSIST FINAL SETTLEMENT
    # =========================================================================
    def test_s_preview_does_not_persist(self):
        """Calling preview does not write any rows to FinalSettlement or SettlementLine."""
        initial_settlement_count = FinalSettlement.objects.count()
        initial_line_count = SettlementLine.objects.count()

        calc = FnFService.preview(employee_id=self.employee.id, requesting_user=self.maker_user)
        self.assertIn("lines", calc)

        self.assertEqual(FinalSettlement.objects.count(), initial_settlement_count)
        self.assertEqual(SettlementLine.objects.count(), initial_line_count)

    # =========================================================================
    # T. IDEMPOTENCY
    # =========================================================================
    def test_t_idempotency(self):
        """Duplicate generation requests are blocked."""
        FnFService.prepare(employee_id=self.employee.id, requesting_user=self.maker_user)
        with self.assertRaises(FnFException):
            FnFService.prepare(employee_id=self.employee.id, requesting_user=self.maker_user)

    # =========================================================================
    # U. IMMUTABLE FINALIZED SETTLEMENT
    # =========================================================================
    def test_u_immutable_finalized_settlement(self):
        """Finalized settlement cannot be altered, lines cannot be mutated, and cannot be deleted."""
        settlement = FnFService.prepare(employee_id=self.employee.id, requesting_user=self.maker_user)
        FnFService.approve(settlement, self.checker_user)
        FnFService.finalize(settlement, self.checker_user)

        self.assertEqual(settlement.status, FinalSettlement.STATUS_FINALIZED)
        self.assertTrue(len(settlement.integrity_hash) == 64)

        # 1. Direct mutation of financial totals fails
        settlement.total_earnings = Decimal("999999.00")
        with self.assertRaises(ValidationError):
            settlement.save()

        # 2. Deletion of finalized settlement fails
        with self.assertRaises(ValidationError):
            settlement.delete()

        # 3. Modification of line fails
        line = settlement.lines.first()
        if line:
            line.amount = Decimal("0.00")
            with self.assertRaises(ValidationError):
                line.save()
            with self.assertRaises(ValidationError):
                line.delete()

    # =========================================================================
    # V. MAKER-CHECKER
    # =========================================================================
    def test_v_maker_checker(self):
        """Settlement creator (Maker) cannot approve their own settlement."""
        settlement = FnFService.prepare(employee_id=self.employee.id, requesting_user=self.maker_user)

        # Maker attempting approval fails
        with self.assertRaises(FnFException) as cm:
            FnFService.approve(settlement, self.maker_user)
        self.assertEqual(cm.exception.code, "MAKER_CHECKER_VIOLATION")

        # Distinct Checker user succeeds
        approved = FnFService.approve(settlement, self.checker_user)
        self.assertEqual(approved.status, FinalSettlement.STATUS_APPROVED)
        self.assertEqual(approved.approved_by, self.checker_user)

    # =========================================================================
    # W. DYNAMIC RBAC
    # =========================================================================
    def test_w_dynamic_rbac(self):
        """Endpoints enforce granular dynamic RBAC permissions."""
        unauth_user = User.objects.create_user(email="unauth@test.com", password="P!")
        self.client.force_authenticate(user=unauth_user)

        # Preview without permission -> 403
        resp = self.client.post("/api/v1/payroll/fnf/preview/", {"employee_id": self.employee.id})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # Maker user with payroll.fnf_prepare -> 200
        self.client.force_authenticate(user=self.maker_user)
        resp = self.client.post("/api/v1/payroll/fnf/preview/", {"employee_id": self.employee.id})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # =========================================================================
    # X. ORGANIZATION ISOLATION
    # =========================================================================
    def test_x_organization_isolation(self):
        """Settlements in Org A are invisible to Org B."""
        org2 = Organization.objects.create(name="Competitor Inc")
        org2_user = User.objects.create_user(email="admin@org2.com", password="P!", status="active")
        # Org 2 role
        org2_role = Role.objects.create(organization=org2, name="Org2 Admin")
        perm = Permission.objects.get(codename="payroll.fnf_view")
        RolePermission.objects.create(role=org2_role, permission=perm)
        UserRole.objects.create(user=org2_user, role=org2_role, scope=ScopeChoices.ORGANIZATION)

        settlement = FnFService.prepare(employee_id=self.employee.id, requesting_user=self.maker_user)

        self.client.force_authenticate(user=org2_user)
        resp = self.client.get(f"/api/v1/payroll/fnf/{settlement.id}/")
        self.assertIn(resp.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

    # =========================================================================
    # Y. SENSITIVE-DATA MASKING
    # =========================================================================
    def test_y_sensitive_data_masking(self):
        """Bank account and PAN numbers are masked in snapshot data."""
        settlement = FnFService.prepare(employee_id=self.employee.id, requesting_user=self.maker_user)
        snapshot = settlement.snapshot_data
        emp_snap = snapshot["employee"]
        self.assertTrue(emp_snap["masked_pan"].startswith("••••"))
        self.assertTrue(emp_snap["masked_account"].startswith("••••"))
        self.assertEqual(emp_snap["masked_pan"][-4:], "234F")
        self.assertEqual(emp_snap["masked_account"][-4:], "1234")

    # =========================================================================
    # Z. AUDIT LOGGING
    # =========================================================================
    def test_z_audit_logging(self):
        """All lifecycle transitions log to AuditLog."""
        settlement = FnFService.prepare(employee_id=self.employee.id, requesting_user=self.maker_user)
        self.assertTrue(AuditLog.objects.filter(action="FNF_PREPARED", target_id=str(settlement.id)).exists())

        FnFService.approve(settlement, self.checker_user)
        self.assertTrue(AuditLog.objects.filter(action="FNF_APPROVED", target_id=str(settlement.id)).exists())

        FnFService.finalize(settlement, self.checker_user)
        self.assertTrue(AuditLog.objects.filter(action="FNF_FINALIZED", target_id=str(settlement.id)).exists())

    # =========================================================================
    # AA. INVALID STATE TRANSITIONS
    # =========================================================================
    def test_aa_invalid_state_transitions(self):
        """Invalid state transitions fail cleanly."""
        settlement = FnFService.prepare(employee_id=self.employee.id, requesting_user=self.maker_user)

        # Cannot finalize a draft directly without approval
        with self.assertRaises(FnFException) as cm:
            FnFService.finalize(settlement, self.checker_user)
        self.assertEqual(cm.exception.code, "INVALID_STATE_TRANSITION")

        # Approve then finalize
        FnFService.approve(settlement, self.checker_user)
        FnFService.finalize(settlement, self.checker_user)

        # Cannot cancel a finalized settlement
        with self.assertRaises(FnFException) as cm:
            FnFService.cancel(settlement, self.checker_user, reason="Try to cancel")
        self.assertEqual(cm.exception.code, "CANNOT_CANCEL_FINALIZED")

    # =========================================================================
    # AB. CORRECT NET SETTLEMENT CALCULATION
    # =========================================================================
    def test_ab_correct_net_settlement_calculation(self):
        """Net settlement amount exactly equals total earnings minus deductions minus recoveries."""
        settlement = FnFService.prepare(
            employee_id=self.employee.id,
            requesting_user=self.maker_user,
            bonus_amount=Decimal("15000.00"),
            loan_recoveries=[{"type": "loan", "amount": "5000.00", "reason": "Laptop loan"}],
            tds_amount=Decimal("2000.00"),
        )
        earnings = sum(l.amount for l in settlement.lines.filter(category="earning"))
        deductions = sum(l.amount for l in settlement.lines.filter(category="deduction"))
        recoveries = sum(l.amount for l in settlement.lines.filter(category="recovery"))

        self.assertEqual(settlement.total_earnings, earnings)
        self.assertEqual(settlement.total_deductions, deductions)
        self.assertEqual(settlement.total_recoveries, recoveries)
        self.assertEqual(settlement.net_settlement_amount, earnings - deductions - recoveries)

    # =========================================================================
    # AC. NO DUPLICATE REGULAR PAYROLL PAYMENT
    # =========================================================================
    def test_ac_no_duplicate_regular_payroll_payment(self):
        """If employee was already paid regular salary for exit month, FnF does not pay again."""
        # Create finalized regular payroll period for Jan 2025
        period = PayrollPeriod.objects.create(
            organization=self.org,
            year=2025,
            month=1,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            status=PayrollPeriod.STATUS_FINALIZED,
        )
        # Regular payroll record with gross salary of ₹100,000
        PayrollRecord.objects.create(
            period=period,
            employee=self.employee,
            working_days=22,
            present_days=22,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal("22.0"),
            basic_salary=Decimal("100000.00"),
            gross_salary=Decimal("100000.00"),
            net_salary=Decimal("100000.00"),
            status=PayrollRecord.STATUS_FINALIZED,
        )

        calc = FnFService.preview(employee_id=self.employee.id, requesting_user=self.maker_user)
        salary_line = next(l for l in calc["lines"] if l["code"] == "SALARY_LWD")

        # Since regular payroll already paid ₹100,000 for this period, salary through LWD is ₹0.00
        self.assertEqual(salary_line["amount"], Decimal("0.00"))
        self.assertIn("already paid in regular payroll", salary_line["calculation_basis"])
