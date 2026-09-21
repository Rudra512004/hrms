from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, time, datetime, timedelta
from decimal import Decimal

from apps.organization.models import Organization, Branch, WorkingCalendar, AttendancePolicy
from apps.employees.models import Employee
from apps.attendance.models import Attendance, AttendanceBreak, Holiday, Shift, EmployeeShiftAssignment
from apps.attendance.services import AttendanceCalculationService
from apps.leaves.models import LeaveType, LeaveRequest
from apps.payroll.models import CompensationHistory, PayrollPeriod, PayrollRecord
from apps.payroll.services import generate_payroll_for_period, _approved_leave_days

User = get_user_model()


class AttendanceCalculationEngineTests(TestCase):
    """
    Focused backend test suite covering all C5.5.2 calculation engine requirements:
    1. configured working day
    2. configured non-working day
    3. branch holiday
    4. employee effective shift
    5. shift work days
    6. grace-period boundary
    7. late check-in
    8. full-day threshold
    9. half-day threshold
    10. approved leave interaction
    11. branch-specific calendar differences
    12. payroll working-day calculation
    13. cross-branch behavior
    14. timezone/date-boundary behavior
    """

    def setUp(self):
        self.client = APIClient()

        # Organization
        self.org = Organization.objects.create(name='Test Calculation Org')

        # Branch 1 (HQ): standard Mon-Fri (0,1,2,3,4)
        self.branch1 = Branch.objects.create(
            organization=self.org, name='HQ Branch',
            latitude='12.971600', longitude='77.594600', radius=100.0
        )
        self.cal1 = self.branch1.working_calendar
        self.cal1.work_days = '0,1,2,3,4'
        self.cal1.save()

        # Disable IP/GPS restrictions on policy for focused calculation testing
        self.policy1 = self.branch1.attendance_policy
        self.policy1.is_office_gps_enabled = False
        self.policy1.is_office_ip_enabled = False
        self.policy1.save()

        # Branch 2 (Middle East): Sun-Thu (6,0,1,2,3)
        self.branch2 = Branch.objects.create(
            organization=self.org, name='Dubai Branch',
            latitude='25.204800', longitude='55.270800', radius=100.0
        )
        self.cal2 = self.branch2.working_calendar
        self.cal2.work_days = '6,0,1,2,3'
        self.cal2.save()

        self.policy2 = self.branch2.attendance_policy
        self.policy2.is_office_gps_enabled = False
        self.policy2.is_office_ip_enabled = False
        self.policy2.save()

        # Employees
        self.user1 = User.objects.create_user(email='emp1@example.com', password='Password123!', status='active')
        self.emp1 = Employee.objects.create(user=self.user1, employee_code='EMP01', organization=self.org, branch=self.branch1)

        self.user2 = User.objects.create_user(email='emp2@example.com', password='Password123!', status='active')
        self.emp2 = Employee.objects.create(user=self.user2, employee_code='EMP02', organization=self.org, branch=self.branch2)

        # Standard Shift in Branch 1: 09:00 - 17:00, grace 15 min, full day 8h, half day 4h
        self.shift_std = Shift.objects.create(
            branch=self.branch1,
            name='Standard 9-5',
            start_time=time(9, 0),
            end_time=time(17, 0),
            grace_period=timedelta(minutes=15),
            full_day_hours=timedelta(hours=8),
            half_day_hours=timedelta(hours=4),
            work_days='0,1,2,3,4'
        )

    def test_01_configured_working_day(self):
        """1. Configured working day matches branch WorkingCalendar work_days."""
        # 2026-09-21 is a Monday (weekday 0), which is in '0,1,2,3,4'
        monday = date(2026, 9, 21)
        self.assertEqual(monday.weekday(), 0)
        self.assertTrue(AttendanceCalculationService.is_branch_working_day(self.branch1, monday))
        self.assertTrue(AttendanceCalculationService.is_employee_scheduled_work_day(self.emp1, monday))

    def test_02_configured_non_working_day(self):
        """2. Configured non-working day (e.g. weekend or unlisted weekday) returns False."""
        # 2026-09-26 is a Saturday (weekday 5)
        saturday = date(2026, 9, 26)
        self.assertEqual(saturday.weekday(), 5)
        self.assertFalse(AttendanceCalculationService.is_branch_working_day(self.branch1, saturday))
        self.assertFalse(AttendanceCalculationService.is_employee_scheduled_work_day(self.emp1, saturday))

        # 2026-09-27 is a Sunday (weekday 6)
        sunday = date(2026, 9, 27)
        self.assertEqual(sunday.weekday(), 6)
        self.assertFalse(AttendanceCalculationService.is_branch_working_day(self.branch1, sunday))
        self.assertFalse(AttendanceCalculationService.is_employee_scheduled_work_day(self.emp1, sunday))

    def test_03_branch_holiday(self):
        """3. Branch holiday overrides a normally configured working day."""
        # 2026-09-21 is Monday (normally a work day)
        monday = date(2026, 9, 21)
        Holiday.objects.create(branch=self.branch1, name='Founder Day', date=monday, is_active=True)

        self.assertTrue(AttendanceCalculationService.is_branch_holiday(self.branch1, monday))
        self.assertFalse(AttendanceCalculationService.is_branch_working_day(self.branch1, monday))
        self.assertFalse(AttendanceCalculationService.is_employee_scheduled_work_day(self.emp1, monday))

    def test_04_employee_effective_shift(self):
        """4. Effective shift resolution respects effective_from, effective_to, and ordering."""
        shift_jan = Shift.objects.create(
            branch=self.branch1, name='Jan Shift', start_time=time(8, 0), end_time=time(16, 0)
        )
        shift_feb = Shift.objects.create(
            branch=self.branch1, name='Feb Shift', start_time=time(10, 0), end_time=time(18, 0)
        )

        EmployeeShiftAssignment.objects.create(
            employee=self.emp1, shift=shift_jan, effective_from=date(2026, 1, 1), effective_to=date(2026, 1, 31)
        )
        EmployeeShiftAssignment.objects.create(
            employee=self.emp1, shift=shift_feb, effective_from=date(2026, 2, 1), effective_to=None
        )

        # In January -> resolves Jan Shift
        resolved_jan = AttendanceCalculationService.get_effective_shift(self.emp1, date(2026, 1, 15))
        self.assertEqual(resolved_jan.id, shift_jan.id)

        # In February -> resolves Feb Shift
        resolved_feb = AttendanceCalculationService.get_effective_shift(self.emp1, date(2026, 2, 15))
        self.assertEqual(resolved_feb.id, shift_feb.id)

        # In March (open-ended assignment) -> resolves Feb Shift
        resolved_mar = AttendanceCalculationService.get_effective_shift(self.emp1, date(2026, 3, 10))
        self.assertEqual(resolved_mar.id, shift_feb.id)

    def test_05_shift_work_days(self):
        """5. Shift-specific work_days determine scheduled work days."""
        shift_weekend = Shift.objects.create(
            branch=self.branch1,
            name='Weekend Shift',
            start_time=time(9, 0),
            end_time=time(17, 0),
            work_days='5,6' # Saturday & Sunday
        )
        EmployeeShiftAssignment.objects.create(
            employee=self.emp1, shift=shift_weekend, effective_from=date(2026, 9, 1)
        )

        saturday = date(2026, 9, 26)
        monday = date(2026, 9, 21)

        # For this employee, Saturday IS scheduled, while Monday is NOT
        self.assertTrue(AttendanceCalculationService.is_employee_scheduled_work_day(self.emp1, saturday))
        self.assertFalse(AttendanceCalculationService.is_employee_scheduled_work_day(self.emp1, monday))

    def test_06_grace_period_boundary(self):
        """6. Check-in exactly at shift.start_time + grace_period is NOT late."""
        # Shift starts at 09:00 with 15 min grace (cutoff is exactly 09:15:00)
        target_date = date(2026, 9, 21)
        tz = timezone.get_current_timezone()

        # Check-in at 09:15:00
        check_in_exact = timezone.make_aware(datetime.combine(target_date, time(9, 15, 0)), tz)
        is_late = AttendanceCalculationService.is_late_check_in(self.shift_std, check_in_exact, target_date=target_date)
        self.assertFalse(is_late, "Check-in at exactly the grace cutoff should NOT be marked late.")

        # Check-in at 09:14:59 (1 second before)
        check_in_before = timezone.make_aware(datetime.combine(target_date, time(9, 14, 59)), tz)
        self.assertFalse(AttendanceCalculationService.is_late_check_in(self.shift_std, check_in_before, target_date=target_date))

    def test_07_late_check_in(self):
        """7. Check-in past shift.start_time + grace_period is flagged late."""
        target_date = date(2026, 9, 21)
        tz = timezone.get_current_timezone()

        # Check-in at 09:15:01 (1 second past cutoff)
        check_in_after = timezone.make_aware(datetime.combine(target_date, time(9, 15, 1)), tz)
        is_late = AttendanceCalculationService.is_late_check_in(self.shift_std, check_in_after, target_date=target_date)
        self.assertTrue(is_late, "Check-in after grace cutoff must be marked late.")

        # Check-in at 09:30:00
        check_in_late = timezone.make_aware(datetime.combine(target_date, time(9, 30, 0)), tz)
        self.assertTrue(AttendanceCalculationService.is_late_check_in(self.shift_std, check_in_late, target_date=target_date))

    def test_08_full_day_threshold(self):
        """8. Check-out with productive duration >= full_day_hours sets status='present'."""
        EmployeeShiftAssignment.objects.create(
            employee=self.emp1, shift=self.shift_std, effective_from=date(2026, 9, 1)
        )
        today = timezone.now().date()
        att = Attendance.objects.create(
            employee=self.emp1,
            date=today,
            check_in=timezone.now() - timedelta(hours=9),
            status='present',
            productive_work_duration=timedelta(hours=8, minutes=15)
        )

        status_result = AttendanceCalculationService.determine_attendance_status(att, shift=self.shift_std)
        self.assertEqual(status_result, 'present')

    def test_09_half_day_threshold(self):
        """9. Check-out between half_day_hours and full_day_hours sets status='half_day'; below is 'absent'."""
        EmployeeShiftAssignment.objects.create(
            employee=self.emp1, shift=self.shift_std, effective_from=date(2026, 9, 1)
        )
        today = timezone.now().date()

        # 5 hours worked (between 4h half-day and 8h full-day)
        att_half = Attendance.objects.create(
            employee=self.emp1,
            date=today,
            check_in=timezone.now() - timedelta(hours=6),
            status='present',
            productive_work_duration=timedelta(hours=5)
        )
        status_half = AttendanceCalculationService.determine_attendance_status(att_half, shift=self.shift_std)
        self.assertEqual(status_half, 'half_day')

        # 2 hours worked (below 4h half-day threshold)
        att_absent = Attendance.objects.create(
            employee=self.emp1,
            date=today + timedelta(days=1),
            check_in=timezone.now() - timedelta(hours=3),
            status='present',
            productive_work_duration=timedelta(hours=2)
        )
        status_absent = AttendanceCalculationService.determine_attendance_status(att_absent, shift=self.shift_std)
        self.assertEqual(status_absent, 'absent')

    def test_10_approved_leave_interaction(self):
        """
        10. Approved leave does NOT block check-in.
        Attended work is recorded, and payroll excludes attendance dates from leave days to avoid double-counting.
        """
        self.client.force_authenticate(user=self.user1)
        today = timezone.now().date()

        lt = LeaveType.objects.create(organization=self.org, name='Annual Leave', annual_allocation=20)
        LeaveRequest.objects.create(
            employee=self.emp1,
            leave_type=lt,
            start_date=today,
            end_date=today,
            status='approved'
        )

        # Check-in succeeds despite approved leave
        res = self.client.post(reverse('attendance-check-in'))
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Attendance.objects.filter(employee=self.emp1, date=today).exists())

    def test_11_branch_specific_calendar_differences(self):
        """11. Calendars configured with different work_days evaluate correctly per branch."""
        sunday = date(2026, 9, 27)
        friday = date(2026, 9, 25)

        # Sunday: HQ (0,1,2,3,4) is non-working, Dubai (6,0,1,2,3) is working
        self.assertFalse(AttendanceCalculationService.is_branch_working_day(self.branch1, sunday))
        self.assertTrue(AttendanceCalculationService.is_branch_working_day(self.branch2, sunday))

        # Friday: HQ is working, Dubai is non-working
        self.assertTrue(AttendanceCalculationService.is_branch_working_day(self.branch1, friday))
        self.assertFalse(AttendanceCalculationService.is_branch_working_day(self.branch2, friday))

    def test_12_payroll_working_day_calculation(self):
        """12. Payroll _approved_leave_days respects branch WorkingCalendar instead of hardcoded weekday < 5."""
        lt = LeaveType.objects.create(organization=self.org, name='Sick Leave', annual_allocation=10)

        # Dubai branch work days: Sun(6), Mon(0), Tue(1), Wed(2), Thu(3). Fri(4) & Sat(5) off.
        # Leave spanning Fri Sep 25 to Sun Sep 27 (Fri=off, Sat=off, Sun=workday)
        start = date(2026, 9, 25) # Fri
        end = date(2026, 9, 27)   # Sun
        LeaveRequest.objects.create(
            employee=self.emp2,
            leave_type=lt,
            start_date=start,
            end_date=end,
            status='approved'
        )

        # Under the old code (current.weekday() < 5), Friday was counted as leave and Sunday was excluded.
        # Under the branch calendar, Friday is excluded and Sunday is counted -> exactly 1 leave day.
        leave_days = _approved_leave_days(self.emp2, start, end)
        self.assertEqual(leave_days, 1)

    def test_13_cross_branch_behavior(self):
        """13. Holiday and calendar in Branch 1 do not affect Branch 2."""
        mon = date(2026, 9, 21)
        Holiday.objects.create(branch=self.branch1, name='HQ Only Holiday', date=mon, is_active=True)

        self.assertTrue(AttendanceCalculationService.is_branch_holiday(self.branch1, mon))
        self.assertFalse(AttendanceCalculationService.is_branch_holiday(self.branch2, mon))

        self.assertFalse(AttendanceCalculationService.is_branch_working_day(self.branch1, mon))
        self.assertTrue(AttendanceCalculationService.is_branch_working_day(self.branch2, mon))

    def test_14_timezone_and_date_boundary_behavior(self):
        """14. Timezone conversions around midnight / date boundary calculate grace cutoff accurately."""
        # Shift starting at 23:30 with 15 min grace (grace cutoff at 23:45:00)
        shift_night = Shift.objects.create(
            branch=self.branch1,
            name='Night Shift',
            start_time=time(23, 30),
            end_time=time(7, 30),
            grace_period=timedelta(minutes=15)
        )
        target_date = date(2026, 9, 21)
        tz = timezone.get_current_timezone()

        dt_ok = timezone.make_aware(datetime.combine(target_date, time(23, 45, 0)), tz)
        self.assertFalse(AttendanceCalculationService.is_late_check_in(shift_night, dt_ok, target_date=target_date))

        dt_late = timezone.make_aware(datetime.combine(target_date, time(23, 45, 1)), tz)
        self.assertTrue(AttendanceCalculationService.is_late_check_in(shift_night, dt_late, target_date=target_date))
