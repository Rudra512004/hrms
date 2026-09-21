from datetime import datetime, date, time, timedelta
from typing import Optional, List
from django.utils import timezone
from django.db.models import Q
from .models import Attendance, Holiday, Shift, EmployeeShiftAssignment
from apps.employees.models import Employee
from apps.organization.models import Branch, WorkingCalendar


class AttendanceCalculationService:
    """
    Central calculation engine for employee attendance, shifts, working calendars,
    holidays, leave interaction, and status determination.
    """

    @staticmethod
    def get_branch_working_calendar(branch: Optional[Branch]) -> Optional[WorkingCalendar]:
        """Resolve the working calendar for a branch."""
        if not branch:
            return None
        return getattr(branch, 'working_calendar', None)

    @staticmethod
    def get_branch_work_days(branch: Optional[Branch]) -> List[int]:
        """
        Return the list of configured working day integers (0=Monday, 6=Sunday).
        Defaults to [0, 1, 2, 3, 4] if calendar is missing or unconfigured.
        """
        if not branch:
            return [0, 1, 2, 3, 4]
        wc = getattr(branch, 'working_calendar', None)
        if wc and hasattr(wc, 'get_work_days_list'):
            return wc.get_work_days_list()
        return [0, 1, 2, 3, 4]

    @staticmethod
    def is_branch_holiday(branch: Optional[Branch], target_date: date) -> bool:
        """Check if an active holiday exists for the branch on target_date."""
        if not branch:
            return False
        return Holiday.objects.filter(branch=branch, date=target_date, is_active=True).exists()

    @staticmethod
    def is_branch_working_day(branch: Optional[Branch], target_date: date) -> bool:
        """
        Determine if target_date is normally a working day for the branch,
        taking both the branch WorkingCalendar and active branch Holidays into account.
        """
        if not branch:
            return target_date.weekday() < 5
        if AttendanceCalculationService.is_branch_holiday(branch, target_date):
            return False
        work_days = AttendanceCalculationService.get_branch_work_days(branch)
        return target_date.weekday() in work_days

    @staticmethod
    def get_effective_shift(employee: Employee, target_date: date) -> Optional[Shift]:
        """
        Resolve the employee's effective shift for the target_date from EmployeeShiftAssignment.
        Falls back to the branch's primary active shift if no explicit assignment exists.
        """
        if not employee:
            return None

        assignment = (
            EmployeeShiftAssignment.objects.filter(
                employee=employee,
                effective_from__lte=target_date,
            )
            .filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=target_date)
            )
            .select_related('shift')
            .order_by('-effective_from')
            .first()
        )
        if assignment:
            return assignment.shift

        # Fallback to active shift in employee's branch if available
        if employee.branch_id:
            return Shift.objects.filter(branch=employee.branch, is_active=True).order_by('id').first()

        return None

    @staticmethod
    def get_shift_work_days(shift: Optional[Shift]) -> List[int]:
        """Return the scheduled work days for a shift."""
        if not shift:
            return [0, 1, 2, 3, 4]
        if hasattr(shift, 'get_work_days_list'):
            return shift.get_work_days_list()
        return [0, 1, 2, 3, 4]

    @staticmethod
    def is_shift_working_day(shift: Optional[Shift], target_date: date) -> bool:
        """Check if target_date is a scheduled working day for the shift."""
        if not shift:
            return target_date.weekday() < 5
        return target_date.weekday() in AttendanceCalculationService.get_shift_work_days(shift)

    @staticmethod
    def is_employee_scheduled_work_day(employee: Employee, target_date: date) -> bool:
        """
        Determine if target_date is a scheduled working day for the employee,
        respecting active branch holidays and the effective shift (or branch calendar).
        """
        # Active branch holidays always override scheduled work days
        if AttendanceCalculationService.is_branch_holiday(employee.branch, target_date):
            return False

        shift = AttendanceCalculationService.get_effective_shift(employee, target_date)
        if shift:
            return AttendanceCalculationService.is_shift_working_day(shift, target_date)

        return AttendanceCalculationService.is_branch_working_day(employee.branch, target_date)

    @staticmethod
    def is_late_check_in(shift: Optional[Shift], check_in_dt: datetime, target_date: Optional[date] = None) -> bool:
        """
        Calculate whether check_in_dt constitutes a late arrival for the given shift.
        Threshold: shift.start_time + shift.grace_period.
        Check-in precisely at the cutoff is NOT late (grace-period boundary).
        Strictly greater than the cutoff is late.
        Carefully handles timezones.
        """
        if not shift or not shift.start_time:
            return False

        tz = timezone.get_current_timezone()
        if timezone.is_aware(check_in_dt):
            local_dt = timezone.localtime(check_in_dt, tz)
        else:
            local_dt = check_in_dt

        effective_date = target_date or local_dt.date()

        # Construct timezone-aware shift start datetime
        shift_start_dt = datetime.combine(effective_date, shift.start_time)
        if timezone.is_aware(check_in_dt):
            shift_start_dt = timezone.make_aware(shift_start_dt, tz)

        grace = shift.grace_period or timedelta(0)
        grace_cutoff = shift_start_dt + grace

        return check_in_dt > grace_cutoff

    @staticmethod
    def determine_attendance_status(attendance: Attendance, shift: Optional[Shift] = None) -> str:
        """
        Determine attendance status ('present', 'half_day', 'absent') based on
        productive_work_duration and the shift's full_day_hours and half_day_hours thresholds.
        If no shift or thresholds are configured, preserves existing attendance status.
        """
        if attendance.productive_work_duration is None:
            return attendance.status or 'present'

        if not shift:
            shift = AttendanceCalculationService.get_effective_shift(attendance.employee, attendance.date)

        if not shift:
            return attendance.status or 'present'

        productive = attendance.productive_work_duration

        # Determine full_day_hours threshold
        full_day = shift.full_day_hours
        if not full_day:
            if shift.start_time and shift.end_time:
                s_dt = datetime.combine(attendance.date, shift.start_time)
                e_dt = datetime.combine(attendance.date, shift.end_time)
                duration = e_dt - s_dt
                full_day = duration if duration.total_seconds() > 0 else timedelta(hours=8)
            else:
                full_day = timedelta(hours=8)

        # Determine half_day_hours threshold
        half_day = shift.half_day_hours
        if not half_day:
            half_day = full_day / 2

        if productive >= full_day:
            return 'present'
        elif productive >= half_day:
            return 'half_day'
        else:
            return 'absent'

    @staticmethod
    def check_approved_leave(employee: Employee, target_date: date):
        """
        Check if employee has an approved LeaveRequest covering target_date.
        """
        from apps.leaves.models import LeaveRequest
        return LeaveRequest.objects.filter(
            employee=employee,
            status='approved',
            start_date__lte=target_date,
            end_date__gte=target_date,
        ).first()
