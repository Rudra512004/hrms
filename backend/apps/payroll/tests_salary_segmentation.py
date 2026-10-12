"""
Authoritative regression test suite for Phase 6 — Effective-Dated Salary Segmentation.

Covers all 18 required scenarios:
1. Salary increase effective on first day.
2. Salary increase effective in the middle of period.
3. Salary decrease effective in the middle of period.
4. Salary revision effective on last day.
5. Revision effective immediately after period ends.
6. Multiple salary revisions within one period.
7. Attendance distributed across multiple segments.
8. Approved paid leave and unpaid leave across segments.
9. LOP across segment boundaries.
10. Formula-based salary components across revisions.
11. Missing compensation coverage.
12. Overlapping or ambiguous compensation assignments.
13. FnF exit during a period containing a salary revision.
14. Regular payroll followed by FnF.
15. FnF followed by regular payroll.
16. Snapshot preservation after compensation master data changes.
17. No-revision regression behavior.
18. Decimal rounding and segment-total reconciliation.
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.organization.models import Organization, Branch, Department
from apps.employees.models import Employee, EmploymentStatus, EmployeeLifecycleEvent, EmployeeStatutoryAndBank
from apps.attendance.models import Attendance, Holiday
from apps.leaves.models import LeaveType, LeaveBalance, LeaveRequest, LeaveCycle, BranchLeavePolicy
from apps.payroll.models import (
    CompensationHistory,
    PayrollPeriod,
    PayrollRecord,
    Payslip,
    PayslipLine,
    FinalSettlement,
    SettlementLine,
    FnFPolicyConfiguration,
    SalaryComponent,
    SalaryStructure,
    SalaryStructureComponent,
)
from apps.payroll.segmentation_service import (
    SalarySegmentationService,
    MissingCompensationCoverageError,
    AmbiguousCompensationAssignmentError,
)
from apps.payroll.services import generate_payroll_for_period, issue_payslips_for_period, _working_days_in_period
from apps.payroll.fnf_service import FnFService

User = get_user_model()


class SalarySegmentationComprehensiveTestSuite(TestCase):
    """Authoritative tests verifying effective-dated salary segmentation across payroll and FnF."""

    def setUp(self):
        self.org = Organization.objects.create(name="BeyondSure Corp")
        self.branch = Branch.objects.create(organization=self.org, name="Bengaluru HQ")
        self.dept = Department.objects.create(branch=self.branch, name="Engineering")

        self.user = User.objects.create_user(
            email="emp.segmented@beyondsure.com",
            password="SecurePassword123!",
            first_name="Rudra",
            last_name="Dev",
            status="active"
        )
        self.maker_user = User.objects.create_user(
            email="hr.maker@beyondsure.com",
            password="SecurePassword123!",
            first_name="HR",
            last_name="Maker",
            status="active"
        )
        self.checker_user = User.objects.create_user(
            email="fin.checker@beyondsure.com",
            password="SecurePassword123!",
            first_name="Fin",
            last_name="Checker",
            status="active"
        )
        from apps.authorization.models import Role, UserRole, ScopeChoices
        admin_role = Role.objects.create(organization=self.org, name="Payroll Admin")
        UserRole.objects.create(user=self.maker_user, role=admin_role, scope=ScopeChoices.ORGANIZATION)
        UserRole.objects.create(user=self.checker_user, role=admin_role, scope=ScopeChoices.ORGANIZATION)

        self.employee = Employee.objects.create(
            user=self.user,
            employee_code="EMP-SEG-001",
            organization=self.org,
            branch=self.branch,
            department=self.dept,
            employment_status=EmploymentStatus.ACTIVE,
            joining_date=date(2024, 1, 1),
        )

        EmployeeStatutoryAndBank.objects.create(
            employee=self.employee,
            pan_number="ABCDE1234F",
            account_number="12345678901234",
            bank_name="HDFC Bank",
            ifsc_code="HDFC0001234",
            is_epf_applicable=False,
            is_esic_applicable=False,
            is_pt_applicable=False,
        )

        # October 2024 payroll period (2024-10-01 to 2024-10-31)
        self.period_oct = PayrollPeriod.objects.create(
            organization=self.org,
            year=2024,
            month=10,
            start_date=date(2024, 10, 1),
            end_date=date(2024, 10, 31),
            status=PayrollPeriod.STATUS_DRAFT,
        )

        # Oct 2 Holiday (Gandhi Jayanti) -> 22 working days in Oct 2024
        Holiday.objects.create(
            branch=self.branch,
            name="Gandhi Jayanti",
            date=date(2024, 10, 2),
            is_active=True,
        )

        # Default FnF Policy
        FnFPolicyConfiguration.objects.create(
            organization=self.org,
            branch=None,
            effective_from=date(2024, 1, 1),
            leave_encashment_enabled=True,
            leave_encashment_daily_divisor=30,
            encashable_leave_types=[],
            gratuity_enabled=False,
            notice_recovery_enabled=False,
            is_active=True,
        )

    def _mark_attendance(self, start_date: date, end_date: date, status="present"):
        """Utility to mark attendance for working weekdays in [start_date, end_date]."""
        curr = start_date
        while curr <= end_date:
            if curr.weekday() < 5 and curr != date(2024, 10, 2):
                Attendance.objects.create(
                    employee=self.employee,
                    date=curr,
                    status=status
                )
            curr += timedelta(days=1)

    # =========================================================================
    # 1. SALARY INCREASE EFFECTIVE ON FIRST DAY OF PERIOD
    # =========================================================================
    def test_01_salary_increase_effective_on_first_day(self):
        """A revision starting on day 1 applies cleanly across the whole period in a single segment."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 9, 30),
            basic_salary=Decimal("30000.00"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 1),
            effective_to=None,
            basic_salary=Decimal("36000.00"),
        )
        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 31))

        records = generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)
        self.assertEqual(len(records), 1)
        rec = records[0]

        # 22 working days * 36,000 / 22 = 36,000
        self.assertEqual(rec.working_days, 22)
        self.assertEqual(rec.effective_days, Decimal("22.0"))
        self.assertEqual(rec.basic_salary, Decimal("36000.00"))
        self.assertEqual(rec.gross_salary, Decimal("36000.00"))
        self.assertFalse(rec.salary_segmentation_snapshot["is_segmented"])
        self.assertEqual(len(rec.salary_segmentation_snapshot["segments"]), 1)
        self.assertEqual(rec.salary_segmentation_snapshot["segments"][0]["basic_salary"], "36000.00")

    # =========================================================================
    # 2. SALARY INCREASE IN THE MIDDLE OF PERIOD
    # =========================================================================
    def test_02_salary_increase_in_middle_of_period(self):
        """Revision on Oct 16 splits into 2 segments: 10 days @ 30k + 12 days @ 36k."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 15),
            basic_salary=Decimal("30000.00"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 16),
            effective_to=None,
            basic_salary=Decimal("36000.00"),
        )
        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 31))

        records = generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)
        rec = records[0]

        # Independent expectation:
        # Seg 1: 30000 * 10 / 22 = 13636.36
        # Seg 2: 36000 * 12 / 22 = 19636.36
        # Total = 33272.72
        expected_gross = Decimal("33272.72")
        self.assertEqual(rec.gross_salary, expected_gross)
        self.assertEqual(rec.working_days, 22)
        self.assertEqual(rec.effective_days, Decimal("22.0"))
        self.assertTrue(rec.salary_segmentation_snapshot["is_segmented"])
        self.assertEqual(rec.salary_segmentation_snapshot["segments_count"], 2)

        seg1 = rec.salary_segmentation_snapshot["segments"][0]
        seg2 = rec.salary_segmentation_snapshot["segments"][1]
        self.assertEqual(seg1["working_days"], 10)
        self.assertEqual(seg1["gross_earned"], "13636.36")
        self.assertEqual(seg2["working_days"], 12)
        self.assertEqual(seg2["gross_earned"], "19636.36")

    # =========================================================================
    # 3. SALARY DECREASE IN THE MIDDLE OF PERIOD
    # =========================================================================
    def test_03_salary_decrease_in_middle_of_period(self):
        """Salary reduction on Oct 16: 10 days @ 36k + 12 days @ 30k."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 15),
            basic_salary=Decimal("36000.00"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 16),
            effective_to=None,
            basic_salary=Decimal("30000.00"),
        )
        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 31))

        records = generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)
        rec = records[0]

        # Seg 1: 36000 * 10 / 22 = 16363.64
        # Seg 2: 30000 * 12 / 22 = 16363.64
        # Total = 32727.28
        expected_gross = Decimal("32727.28")
        self.assertEqual(rec.gross_salary, expected_gross)
        self.assertTrue(rec.salary_segmentation_snapshot["is_segmented"])

    # =========================================================================
    # 4. SALARY REVISION EFFECTIVE ON LAST DAY OF PERIOD
    # =========================================================================
    def test_04_salary_revision_effective_on_last_day(self):
        """Revision on Oct 31: 21 days @ 30k + 1 day @ 60k."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 30),
            basic_salary=Decimal("30000.00"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 31),
            effective_to=None,
            basic_salary=Decimal("60000.00"),
        )
        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 31))

        records = generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)
        rec = records[0]

        # Seg 1: 30000 * 21 / 22 = 28636.36
        # Seg 2: 60000 * 1 / 22 = 2727.27
        # Total = 31363.63
        expected_gross = Decimal("31363.63")
        self.assertEqual(rec.gross_salary, expected_gross)
        self.assertEqual(rec.salary_segmentation_snapshot["segments_count"], 2)
        self.assertEqual(rec.salary_segmentation_snapshot["segments"][1]["working_days"], 1)

    # =========================================================================
    # 5. REVISION EFFECTIVE IMMEDIATELY AFTER PERIOD ENDS
    # =========================================================================
    def test_05_revision_effective_immediately_after_period_ends(self):
        """Revision effective Nov 1 does not affect October payroll."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 31),
            basic_salary=Decimal("30000.00"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 11, 1),
            effective_to=None,
            basic_salary=Decimal("45000.00"),
        )
        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 31))

        records = generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)
        rec = records[0]

        self.assertEqual(rec.gross_salary, Decimal("30000.00"))
        self.assertFalse(rec.salary_segmentation_snapshot["is_segmented"])
        self.assertEqual(rec.salary_segmentation_snapshot["segments_count"], 1)

    # =========================================================================
    # 6. MULTIPLE SALARY REVISIONS WITHIN ONE PERIOD
    # =========================================================================
    def test_06_multiple_salary_revisions_within_one_period(self):
        """Three segments in October: Oct 1-10 @ 30k, Oct 11-20 @ 33k, Oct 21-31 @ 36k."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 10),
            basic_salary=Decimal("30000.00"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 11),
            effective_to=date(2024, 10, 20),
            basic_salary=Decimal("33000.00"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 21),
            effective_to=None,
            basic_salary=Decimal("36000.00"),
        )
        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 31))

        records = generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)
        rec = records[0]

        # Working days:
        # Oct 1-10: 7 working days (Oct 1 Tue, Oct 2 Hol, Oct 3-4 Thu-Fri, Oct 7-10 Mon-Thu)
        # Oct 11-20: 6 working days (Oct 11 Fri, Oct 14-18 Mon-Fri)
        # Oct 21-31: 9 working days (Oct 21-25 Mon-Fri, Oct 28-31 Mon-Thu)
        # Total = 7 + 6 + 9 = 22
        # Seg 1: 30000 * 7 / 22 = 9545.45
        # Seg 2: 33000 * 6 / 22 = 9000.00
        # Seg 3: 36000 * 9 / 22 = 14727.27
        # Total = 9545.45 + 9000.00 + 14727.27 = 33272.72
        expected_gross = Decimal("33272.72")
        self.assertEqual(rec.gross_salary, expected_gross)
        self.assertEqual(rec.salary_segmentation_snapshot["segments_count"], 3)

    # =========================================================================
    # 7. ATTENDANCE DISTRIBUTED ACROSS MULTIPLE SEGMENTS
    # =========================================================================
    def test_07_attendance_distributed_across_multiple_segments(self):
        """Segment 1: 8 present out of 10. Segment 2: 12 present out of 12."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 15),
            basic_salary=Decimal("30000.00"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 16),
            effective_to=None,
            basic_salary=Decimal("36000.00"),
        )
        # Mark present for Oct 4-15 (8 days present: Oct 1 and 3 absent, Oct 2 holiday)
        self._mark_attendance(date(2024, 10, 4), date(2024, 10, 15))
        # Mark full present for Oct 16-31 (12 days present)
        self._mark_attendance(date(2024, 10, 16), date(2024, 10, 31))

        records = generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)
        rec = records[0]

        # Seg 1: 30000 * 8 / 22 = 10909.09
        # Seg 2: 36000 * 12 / 22 = 19636.36
        # Total = 10909.09 + 19636.36 = 30545.45
        expected_gross = Decimal("30545.45")
        self.assertEqual(rec.gross_salary, expected_gross)
        self.assertEqual(rec.effective_days, Decimal("20.0"))
        self.assertEqual(rec.absent_days, 2)

    # =========================================================================
    # 8. APPROVED PAID LEAVE AND UNPAID LEAVE ACROSS SEGMENTS
    # =========================================================================
    def test_08_approved_paid_leave_and_unpaid_leave_across_segments(self):
        """Paid leave in Seg 1 (credited as paid) and unexcused absence in Seg 2 (LOP)."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 15),
            basic_salary=Decimal("30000.00"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 16),
            effective_to=None,
            basic_salary=Decimal("36000.00"),
        )
        # In Seg 1: 8 days present, 2 days approved leave (Oct 14-15) -> 10 paid days
        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 11))
        lt = LeaveType.objects.create(organization=self.org, name="Annual Leave")
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=lt,
            start_date=date(2024, 10, 14),
            end_date=date(2024, 10, 15),
            status="approved",
        )

        # In Seg 2: 10 days present, 2 days absent (unpaid) out of 12 working days
        self._mark_attendance(date(2024, 10, 16), date(2024, 10, 29))  # Oct 30, 31 absent

        records = generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)
        rec = records[0]

        # Seg 1: 30000 * 10 / 22 = 13636.36
        # Seg 2: 36000 * 10 / 22 = 16363.64
        # Total = 30000.00
        expected_gross = Decimal("30000.00")
        self.assertEqual(rec.gross_salary, expected_gross)
        self.assertEqual(rec.effective_days, Decimal("20.0"))
        self.assertEqual(rec.leave_days, 2)
        self.assertEqual(rec.absent_days, 2)

    # =========================================================================
    # 9. LOP ACROSS SEGMENT BOUNDARIES
    # =========================================================================
    def test_09_lop_across_segment_boundaries(self):
        """Absence spanning Oct 15 (last day of Seg 1) and Oct 16 (first day of Seg 2)."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 15),
            basic_salary=Decimal("30000.00"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 16),
            effective_to=None,
            basic_salary=Decimal("36000.00"),
        )
        # All present except Oct 15 and Oct 16
        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 14))
        self._mark_attendance(date(2024, 10, 17), date(2024, 10, 31))

        records = generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)
        rec = records[0]

        # Seg 1: 9 present out of 10 -> 30000 * 9 / 22 = 12272.73
        # Seg 2: 11 present out of 12 -> 36000 * 11 / 22 = 18000.00
        # Total = 30272.73
        expected_gross = Decimal("30272.73")
        self.assertEqual(rec.gross_salary, expected_gross)

        seg1 = rec.salary_segmentation_snapshot["segments"][0]
        seg2 = rec.salary_segmentation_snapshot["segments"][1]
        self.assertEqual(seg1["lop_days"], "1.0")
        self.assertEqual(seg2["lop_days"], "1.0")

    # =========================================================================
    # 10. FORMULA-BASED SALARY COMPONENTS ACROSS REVISIONS
    # =========================================================================
    def test_10_formula_based_salary_components_across_revisions(self):
        """Salary structure with HRA = BASIC * 0.40 and flat Special Allowance = 2200."""
        struct = SalaryStructure.objects.create(organization=self.org, name="Standard Engineering")
        comp_hra = SalaryComponent.objects.create(
            organization=self.org,
            name="House Rent Allowance",
            code="HRA",
            kind="earning",
            calculation_type="formula",
            formula_expression="BASIC * 0.40",
            is_prorated=True,
        )
        comp_sa = SalaryComponent.objects.create(
            organization=self.org,
            name="Special Allowance",
            code="SPECIAL",
            kind="earning",
            calculation_type="flat",
            is_prorated=True,
        )
        SalaryStructureComponent.objects.create(structure=struct, component=comp_hra, order=1)
        SalaryStructureComponent.objects.create(structure=struct, component=comp_sa, amount=Decimal("2200.00"), order=2)

        CompensationHistory.objects.create(
            employee=self.employee,
            salary_structure=struct,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 15),
            basic_salary=Decimal("30000.00"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            salary_structure=struct,
            effective_from=date(2024, 10, 16),
            effective_to=None,
            basic_salary=Decimal("36000.00"),
        )
        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 31))

        records = generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)
        rec = records[0]

        # Seg 1 (10/22):
        # Basic: 30000 * 10 / 22 = 13636.36
        # HRA: 12000 * 10 / 22 = 5454.55
        # Special: 2200 * 10 / 22 = 1000.00
        # Seg 1 total = 20090.91
        # Seg 2 (12/22):
        # Basic: 36000 * 12 / 22 = 19636.36
        # HRA: 14400 * 12 / 22 = 7854.55
        # Special: 2200 * 12 / 22 = 1200.00
        # Seg 2 total = 28690.91
        # Total = 20090.91 + 28690.91 = 48781.82
        expected_gross = Decimal("48781.82")
        self.assertEqual(rec.gross_salary, expected_gross)

    # =========================================================================
    # 11. MISSING COMPENSATION COVERAGE
    # =========================================================================
    def test_11_missing_compensation_coverage_raises_error(self):
        """A gap in compensation history raises MissingCompensationCoverageError."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 10),
            basic_salary=Decimal("30000.00"),
        )
        # Gap: Oct 11 to Oct 15 has no assignment
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 16),
            effective_to=None,
            basic_salary=Decimal("36000.00"),
        )
        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 31))

        with self.assertRaises(MissingCompensationCoverageError):
            generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)

    # =========================================================================
    # 12. OVERLAPPING OR AMBIGUOUS COMPENSATION ASSIGNMENTS
    # =========================================================================
    def test_12_overlapping_compensation_assignments_raises_error(self):
        """Overlapping compensation records raise AmbiguousCompensationAssignmentError."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 20),
            basic_salary=Decimal("30000.00"),
        )
        # Overlap: Oct 16 to Oct 20 covered by both records
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 16),
            effective_to=None,
            basic_salary=Decimal("36000.00"),
        )
        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 31))

        with self.assertRaises(AmbiguousCompensationAssignmentError):
            generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)

    # =========================================================================
    # 13. FNF EXIT DURING A PERIOD CONTAINING A SALARY REVISION
    # =========================================================================
    def test_13_fnf_exit_during_period_with_salary_revision(self):
        """FnF for exit on Oct 20 slices into Seg 1 (Oct 1-15) and Seg 2 (Oct 16-20)."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 15),
            basic_salary=Decimal("30000.00"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 16),
            effective_to=None,
            basic_salary=Decimal("36000.00"),
        )
        # Set employee in approved exit on Oct 20
        self.employee.employment_status = EmploymentStatus.ON_NOTICE
        self.employee.resignation_date = date(2024, 9, 20)
        self.employee.exit_date = date(2024, 10, 20)
        self.employee.save()

        EmployeeLifecycleEvent.objects.create(
            employee=self.employee,
            event_type="resignation",
            effective_date=date(2024, 9, 20),
            created_by=self.maker_user,
        )

        # Mark attendance up to Oct 20 (Oct 1-15 = 10 days, Oct 16-18 = 3 days, Oct 19-20 weekend)
        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 20))

        calc = FnFService.preview(employee_id=self.employee.id, requesting_user=self.maker_user)
        salary_line = next(l for l in calc["lines"] if l["code"] == "SALARY_LWD")

        # Seg 1: 30000 * 10 / 22 = 13636.36
        # Seg 2: 36000 * 3 / 22 = 4909.09
        # Total = 18545.45
        expected_gross = Decimal("18545.45")
        self.assertEqual(salary_line["amount"], expected_gross)
        self.assertTrue(salary_line["metadata"]["is_segmented"])
        self.assertEqual(len(salary_line["metadata"]["segments"]), 2)

    # =========================================================================
    # 14. REGULAR PAYROLL FOLLOWED BY FNF
    # =========================================================================
    def test_14_regular_payroll_followed_by_fnf(self):
        """When regular payroll has finalized, FnF offsets the already-paid gross and disburses zero excess."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 15),
            basic_salary=Decimal("30000.00"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 16),
            effective_to=None,
            basic_salary=Decimal("36000.00"),
        )
        self.employee.employment_status = EmploymentStatus.ON_NOTICE
        self.employee.resignation_date = date(2024, 9, 20)
        self.employee.exit_date = date(2024, 10, 20)
        self.employee.save()

        EmployeeLifecycleEvent.objects.create(
            employee=self.employee,
            event_type="resignation",
            effective_date=date(2024, 9, 20),
            created_by=self.maker_user,
        )

        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 20))

        # 1. Run regular payroll first
        records = generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)
        self.period_oct.status = PayrollPeriod.STATUS_FINALIZED
        self.period_oct.save()
        rec = records[0]
        rec.status = PayrollRecord.STATUS_FINALIZED
        rec.save()

        # Regular payroll computed ₹18545.45
        self.assertEqual(rec.gross_salary, Decimal("18545.45"))

        # 2. Run FnF settlement preview
        calc = FnFService.preview(employee_id=self.employee.id, requesting_user=self.maker_user)
        salary_line = next(l for l in calc["lines"] if l["code"] == "SALARY_LWD")

        # FnF sees gross_salary_lwd (18545.45) - already_paid (18545.45) = 0.00
        self.assertEqual(salary_line["amount"], Decimal("0.00"))
        self.assertEqual(salary_line["metadata"]["already_paid_regular_payroll"], "18545.45")

    # =========================================================================
    # 15. FNF FOLLOWED BY REGULAR PAYROLL
    # =========================================================================
    def test_15_fnf_followed_by_regular_payroll(self):
        """When FnF settles salary for the period first, regular payroll skips the employee."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 15),
            basic_salary=Decimal("30000.00"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 16),
            effective_to=None,
            basic_salary=Decimal("36000.00"),
        )
        self.employee.employment_status = EmploymentStatus.ON_NOTICE
        self.employee.resignation_date = date(2024, 9, 20)
        self.employee.exit_date = date(2024, 10, 20)
        self.employee.save()

        EmployeeLifecycleEvent.objects.create(
            employee=self.employee,
            event_type="resignation",
            effective_date=date(2024, 9, 20),
            created_by=self.maker_user,
        )

        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 20))

        settlement = FnFService.prepare(employee_id=self.employee.id, requesting_user=self.maker_user)
        FnFService.approve(settlement=settlement, requesting_user=self.checker_user)

        # 2. Run regular payroll
        records = generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)
        # Employee was skipped because period salary was settled in FnF
        self.assertEqual(len(records), 0)

    # =========================================================================
    # 16. SNAPSHOT PRESERVATION AFTER COMPENSATION MASTER DATA CHANGES
    # =========================================================================
    def test_16_snapshot_preservation_after_master_data_changes(self):
        """Editing master CompensationHistory after payroll generation does not alter historical record snapshot."""
        ch1 = CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 15),
            basic_salary=Decimal("30000.00"),
        )
        ch2 = CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 16),
            effective_to=None,
            basic_salary=Decimal("36000.00"),
        )
        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 31))

        records = generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)
        rec = records[0]
        self.period_oct.status = PayrollPeriod.STATUS_FINALIZED
        self.period_oct.save()
        rec.status = PayrollRecord.STATUS_FINALIZED
        rec.save()

        orig_gross = rec.gross_salary
        orig_snapshot = dict(rec.salary_segmentation_snapshot)

        # Admin creates retroactive or new compensation record in November
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 11, 1),
            effective_to=None,
            basic_salary=Decimal("50000.00"),
        )

        rec.refresh_from_db()
        self.assertEqual(rec.gross_salary, orig_gross)
        self.assertEqual(rec.salary_segmentation_snapshot, orig_snapshot)

    # =========================================================================
    # 17. NO-REVISION REGRESSION BEHAVIOR
    # =========================================================================
    def test_17_no_revision_regression_behavior(self):
        """A standard month with no revisions produces identical results to single-rate formula."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=None,
            basic_salary=Decimal("50000.00"),
        )
        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 31))

        records = generate_payroll_for_period(self.period_oct, requesting_user=self.maker_user)
        rec = records[0]

        self.assertEqual(rec.gross_salary, Decimal("50000.00"))
        self.assertEqual(rec.basic_salary, Decimal("50000.00"))
        self.assertEqual(rec.working_days, 22)
        self.assertEqual(rec.effective_days, Decimal("22.0"))
        self.assertFalse(rec.salary_segmentation_snapshot["is_segmented"])
        self.assertEqual(rec.salary_segmentation_snapshot["segments_count"], 1)

    # =========================================================================
    # 18. DECIMAL ROUNDING AND SEGMENT-TOTAL RECONCILIATION
    # =========================================================================
    def test_18_decimal_rounding_and_segment_total_reconciliation(self):
        """Segment gross earnings sum exactly to total_gross without penny drift."""
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 10, 7),
            basic_salary=Decimal("23333.33"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 8),
            effective_to=date(2024, 10, 20),
            basic_salary=Decimal("31111.11"),
        )
        CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2024, 10, 21),
            effective_to=None,
            basic_salary=Decimal("41999.99"),
        )
        self._mark_attendance(date(2024, 10, 1), date(2024, 10, 31))

        summary = SalarySegmentationService.calculate_segments(
            employee=self.employee,
            start_date=date(2024, 10, 1),
            end_date=date(2024, 10, 31),
            total_period_working_days=22,
        )

        summed_segments_gross = sum(s.gross_earned for s in summary.segments)
        self.assertEqual(summed_segments_gross, summary.total_gross)
        for s in summary.segments:
            # Each segment amount must be a 2-decimal rounded figure
            self.assertEqual(s.gross_earned, s.gross_earned.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
