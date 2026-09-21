from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, time, datetime, timedelta

from apps.organization.models import Organization, Branch, WorkingCalendar, AttendancePolicy
from apps.employees.models import Employee
from apps.attendance.models import Attendance, Holiday, Shift, EmployeeShiftAssignment
from apps.attendance.services import AttendanceCalculationService
from apps.attendance.exceptions import AttendanceConfigurationError
from apps.leaves.models import LeaveType, LeaveRequest
from apps.payroll.services import _approved_leave_days

User = get_user_model()


class AttendanceCalculationEngineHardeningTests(TestCase):
    """
    Focused backend test suite covering C5.5.2.1 hardening requirements:
    1. Missing WorkingCalendar does NOT default to Mon–Fri.
    2. Missing WorkingCalendar produces deterministic configuration error.
    3. Valid WorkingCalendar still works.
    4. Empty/invalid WorkingCalendar configuration does not silently become Mon–Fri.
    5. Employee with effective shift assignment uses that exact shift.
    6. Employee without effective shift assignment does NOT fall back to an arbitrary active branch shift.
    7. Missing shift assignment produces deterministic configuration error on a scheduled working day.
    8. Multiple active branch shifts do not cause arbitrary shift selection.
    9. Non-working branch-calendar date does not require a shift merely to determine non-working.
    10. Branch WorkingCalendar + Shift.work_days are both respected (Cases A, B, C, D).
    11. Active Holiday prevents scheduled attendance calculation regardless of shift.
    12. Existing late/full-day/half-day behavior remains unchanged.
    13. Cross-branch isolation remains intact.
    14. Existing timezone/date-boundary behavior remains intact.
    """

    def setUp(self):
        self.client = APIClient()

        # Organization
        self.org = Organization.objects.create(name='Test Hardening Org')

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

        # Branch 2 (Dubai): Sun-Thu (6,0,1,2,3)
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

        # Standard Shift in Branch 1: 09:00 - 17:00, grace 15 min, full day 8h, half day 4h, Mon-Fri (0,1,2,3,4)
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

    def test_01_missing_working_calendar_does_not_default_to_mon_fri(self):
        """1. Missing WorkingCalendar does NOT default to Mon–Fri [0,1,2,3,4]."""
        branch_no_cal = Branch.objects.create(
            organization=self.org, name='No Cal Branch',
            latitude='10.000000', longitude='20.000000', radius=100.0
        )
        # Delete auto-provisioned calendar to simulate missing configuration
        WorkingCalendar.objects.filter(branch=branch_no_cal).delete()
        branch_no_cal.refresh_from_db()

        monday = date(2026, 9, 21)
        # Must not return True or default to [0,1,2,3,4]
        with self.assertRaises(AttendanceConfigurationError):
            AttendanceCalculationService.is_branch_working_day(branch_no_cal, monday)

    def test_02_missing_working_calendar_produces_deterministic_configuration_error(self):
        """2. Missing WorkingCalendar produces deterministic configuration error message."""
        branch_no_cal = Branch.objects.create(
            organization=self.org, name='No Cal Branch 2',
            latitude='10.000000', longitude='20.000000', radius=100.0
        )
        WorkingCalendar.objects.filter(branch=branch_no_cal).delete()
        branch_no_cal.refresh_from_db()

        monday = date(2026, 9, 21)
        with self.assertRaises(AttendanceConfigurationError) as cm:
            AttendanceCalculationService.get_branch_work_days(branch_no_cal)

        self.assertIn(f"Working calendar is not configured for branch {branch_no_cal.id}", str(cm.exception))

    def test_03_valid_working_calendar_still_works(self):
        """3. Valid WorkingCalendar evaluates working days correctly."""
        monday = date(2026, 9, 21) # Mon
        saturday = date(2026, 9, 26) # Sat

        self.assertTrue(AttendanceCalculationService.is_branch_working_day(self.branch1, monday))
        self.assertFalse(AttendanceCalculationService.is_branch_working_day(self.branch1, saturday))

    def test_04_empty_invalid_working_calendar_does_not_silently_become_mon_fri(self):
        """4. Empty or invalid WorkingCalendar configuration does not silently become Mon–Fri."""
        # Empty work_days
        self.cal1.work_days = '   '
        self.cal1.save()

        monday = date(2026, 9, 21)
        with self.assertRaises(AttendanceConfigurationError) as cm:
            AttendanceCalculationService.is_branch_working_day(self.branch1, monday)
        self.assertIn("unconfigured work days", str(cm.exception))

        # Malformed work_days
        self.cal1.work_days = '0,M,2'
        self.cal1.save()
        with self.assertRaises(AttendanceConfigurationError) as cm:
            AttendanceCalculationService.is_branch_working_day(self.branch1, monday)
        self.assertIn("Invalid work day 'M'", str(cm.exception))

    def test_05_employee_with_effective_shift_assignment_uses_that_exact_shift(self):
        """5. Employee with effective shift assignment uses that exact shift."""
        shift_a = Shift.objects.create(
            branch=self.branch1, name='Shift A', start_time=time(7, 0), end_time=time(15, 0)
        )
        EmployeeShiftAssignment.objects.create(
            employee=self.emp1, shift=shift_a, effective_from=date(2026, 9, 1)
        )

        resolved = AttendanceCalculationService.get_effective_shift(self.emp1, date(2026, 9, 21))
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.id, shift_a.id)

    def test_06_employee_without_effective_shift_assignment_does_not_fall_back(self):
        """6. Employee without effective shift assignment does NOT fall back to an arbitrary active branch shift."""
        # Active shifts exist in branch1 (self.shift_std), but emp1 has NO EmployeeShiftAssignment
        resolved = AttendanceCalculationService.get_effective_shift(self.emp1, date(2026, 9, 21))
        self.assertIsNone(resolved, "Must NOT fall back to branch's active shift when no assignment exists.")

    def test_07_missing_shift_assignment_produces_deterministic_error_on_scheduled_working_day(self):
        """7. Missing shift assignment produces deterministic configuration error on a scheduled working day."""
        monday = date(2026, 9, 21) # Monday is a branch working day
        self.assertTrue(AttendanceCalculationService.is_branch_working_day(self.branch1, monday))

        # emp1 has NO shift assignment
        with self.assertRaises(AttendanceConfigurationError) as cm:
            AttendanceCalculationService.resolve_scheduled_shift(self.emp1, monday)

        expected_msg = f"No effective shift assignment for employee {self.emp1.id} on {monday}."
        self.assertEqual(str(cm.exception), expected_msg)

    def test_08_multiple_active_branch_shifts_do_not_cause_arbitrary_selection(self):
        """8. Multiple active branch shifts do not cause arbitrary shift selection when assignment is missing."""
        Shift.objects.create(branch=self.branch1, name='Active 1', start_time=time(8, 0), end_time=time(16, 0), is_active=True)
        Shift.objects.create(branch=self.branch1, name='Active 2', start_time=time(16, 0), end_time=time(0, 0), is_active=True)

        resolved = AttendanceCalculationService.get_effective_shift(self.emp1, date(2026, 9, 21))
        self.assertIsNone(resolved)

    def test_09_non_working_branch_calendar_date_does_not_require_shift(self):
        """9. Non-working branch-calendar date does not require a shift merely to determine non-working."""
        saturday = date(2026, 9, 26) # Saturday is non-working on branch1 calendar
        self.assertFalse(AttendanceCalculationService.is_branch_working_day(self.branch1, saturday))

        # emp1 has NO shift assignment, but calling is_employee_scheduled_work_day on a non-working day
        # must return False without raising a missing-shift configuration error
        is_scheduled = AttendanceCalculationService.is_employee_scheduled_work_day(self.emp1, saturday)
        self.assertFalse(is_scheduled)

    def test_10_branch_working_calendar_and_shift_work_days_both_respected(self):
        """
        10. Branch WorkingCalendar and Shift.work_days are both respected (Cases A, B, C, D):
        A. Branch Mon-Fri + Shift Mon-Fri + normal weekday -> scheduled working day
        B. Branch Mon-Fri + Shift Sat-Sun + Saturday -> non-working because branch calendar excludes Saturday
        C. Branch Mon-Sun + Shift Sat-Sun + Saturday -> scheduled working day
        D. Branch Mon-Sun + Shift Mon-Sun + active Holiday -> holiday/non-working
        """
        monday = date(2026, 9, 21)
        saturday = date(2026, 9, 26)

        # Case A: Branch Mon-Fri (self.cal1) + Shift Mon-Fri + Monday
        EmployeeShiftAssignment.objects.create(
            employee=self.emp1, shift=self.shift_std, effective_from=date(2026, 9, 1)
        )
        self.assertTrue(AttendanceCalculationService.is_employee_scheduled_work_day(self.emp1, monday))

        # Case B: Branch Mon-Fri + Shift Sat-Sun (weekend shift) + Saturday
        shift_weekend = Shift.objects.create(
            branch=self.branch1, name='Weekend Shift', start_time=time(9, 0), end_time=time(17, 0), work_days='5,6'
        )
        EmployeeShiftAssignment.objects.filter(employee=self.emp1).delete()
        EmployeeShiftAssignment.objects.create(
            employee=self.emp1, shift=shift_weekend, effective_from=date(2026, 9, 1)
        )
        # Saturday is in shift_weekend, BUT excluded by branch1 calendar (Mon-Fri) -> non-working!
        self.assertFalse(AttendanceCalculationService.is_employee_scheduled_work_day(self.emp1, saturday))

        # Case C: Branch Mon-Sun (all 7 days) + Shift Sat-Sun + Saturday
        branch_7day = Branch.objects.create(
            organization=self.org, name='24-7 Branch',
            latitude='12.000000', longitude='77.000000', radius=100.0
        )
        branch_7day.working_calendar.work_days = '0,1,2,3,4,5,6'
        branch_7day.working_calendar.save()

        emp_7day = Employee.objects.create(user=User.objects.create_user(email='e7@ex.com', password='P!'), employee_code='E7', organization=self.org, branch=branch_7day)
        shift_we_7day = Shift.objects.create(
            branch=branch_7day, name='Weekend Shift 7D', start_time=time(9, 0), end_time=time(17, 0), work_days='5,6'
        )
        EmployeeShiftAssignment.objects.create(
            employee=emp_7day, shift=shift_we_7day, effective_from=date(2026, 9, 1)
        )
        # Both branch calendar and shift allow Saturday -> scheduled working day!
        self.assertTrue(AttendanceCalculationService.is_employee_scheduled_work_day(emp_7day, saturday))

        # Case D: Branch Mon-Sun + Shift Mon-Sun + active Holiday
        shift_all = Shift.objects.create(
            branch=branch_7day, name='All Days', start_time=time(9, 0), end_time=time(17, 0), work_days='0,1,2,3,4,5,6'
        )
        EmployeeShiftAssignment.objects.filter(employee=emp_7day).delete()
        EmployeeShiftAssignment.objects.create(
            employee=emp_7day, shift=shift_all, effective_from=date(2026, 9, 1)
        )
        holiday_date = date(2026, 9, 23)
        Holiday.objects.create(branch=branch_7day, name='Special Holiday', date=holiday_date, is_active=True)
        # Active holiday takes precedence -> holiday/non-working!
        self.assertFalse(AttendanceCalculationService.is_employee_scheduled_work_day(emp_7day, holiday_date))

    def test_11_active_holiday_prevents_scheduled_calculation_regardless_of_shift(self):
        """11. Active Holiday prevents scheduled attendance calculation regardless of shift."""
        monday = date(2026, 9, 21)
        EmployeeShiftAssignment.objects.create(
            employee=self.emp1, shift=self.shift_std, effective_from=date(2026, 9, 1)
        )
        Holiday.objects.create(branch=self.branch1, name='National Day', date=monday, is_active=True)

        self.assertFalse(AttendanceCalculationService.is_employee_scheduled_work_day(self.emp1, monday))

    def test_12_existing_late_full_day_half_day_behavior_remains_unchanged(self):
        """12. Existing late, full-day, and half-day calculations remain unchanged."""
        EmployeeShiftAssignment.objects.create(
            employee=self.emp1, shift=self.shift_std, effective_from=date(2026, 9, 1)
        )
        today = timezone.now().date()
        tz = timezone.get_current_timezone()

        # Grace cutoff is 09:15:00
        t_ok = timezone.make_aware(datetime.combine(today, time(9, 15, 0)), tz)
        self.assertFalse(AttendanceCalculationService.is_late_check_in(self.shift_std, t_ok, target_date=today))

        t_late = timezone.make_aware(datetime.combine(today, time(9, 15, 1)), tz)
        self.assertTrue(AttendanceCalculationService.is_late_check_in(self.shift_std, t_late, target_date=today))

        # Full-day vs half-day vs absent
        att_full = Attendance.objects.create(
            employee=self.emp1, date=today, check_in=timezone.now() - timedelta(hours=9),
            status='present', productive_work_duration=timedelta(hours=8, minutes=1)
        )
        self.assertEqual(AttendanceCalculationService.determine_attendance_status(att_full, shift=self.shift_std), 'present')

        att_half = Attendance.objects.create(
            employee=self.emp1, date=today + timedelta(days=1), check_in=timezone.now() - timedelta(hours=5),
            status='present', productive_work_duration=timedelta(hours=4, minutes=30)
        )
        self.assertEqual(AttendanceCalculationService.determine_attendance_status(att_half, shift=self.shift_std), 'half_day')

        att_absent = Attendance.objects.create(
            employee=self.emp1, date=today + timedelta(days=2), check_in=timezone.now() - timedelta(hours=2),
            status='present', productive_work_duration=timedelta(hours=2)
        )
        self.assertEqual(AttendanceCalculationService.determine_attendance_status(att_absent, shift=self.shift_std), 'absent')

    def test_13_cross_branch_isolation_remains_intact(self):
        """13. Cross-branch isolation remains intact."""
        monday = date(2026, 9, 21)
        Holiday.objects.create(branch=self.branch1, name='HQ Holiday Only', date=monday, is_active=True)

        self.assertFalse(AttendanceCalculationService.is_branch_working_day(self.branch1, monday))
        self.assertTrue(AttendanceCalculationService.is_branch_working_day(self.branch2, monday))

    def test_14_existing_timezone_date_boundary_behavior_remains_intact(self):
        """14. Timezone and date-boundary behavior remains intact."""
        shift_night = Shift.objects.create(
            branch=self.branch1, name='Overnight', start_time=time(23, 30), end_time=time(7, 30), grace_period=timedelta(minutes=15)
        )
        today = date(2026, 9, 21)
        tz = timezone.get_current_timezone()

        t_ok = timezone.make_aware(datetime.combine(today, time(23, 45, 0)), tz)
        self.assertFalse(AttendanceCalculationService.is_late_check_in(shift_night, t_ok, target_date=today))

        t_late = timezone.make_aware(datetime.combine(today, time(23, 45, 1)), tz)
        self.assertTrue(AttendanceCalculationService.is_late_check_in(shift_night, t_late, target_date=today))
