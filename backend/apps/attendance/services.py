from datetime import datetime, date, time, timedelta
from typing import Optional, List
from django.utils import timezone
from django.db.models import Q
from .models import Attendance, Holiday, Shift
from .exceptions import AttendanceConfigurationError
from apps.employees.models import Employee
from apps.organization.models import Branch, WorkingCalendar


class AttendanceCalculationService:
    """
    Authoritative calculation engine for employee attendance, shifts, working calendars,
    holidays, leave interaction, and status determination.
    """

    @staticmethod
    def get_branch_working_calendar(branch: Optional[Branch]) -> WorkingCalendar:
        """
        Resolve the working calendar for a branch.
        Raises AttendanceConfigurationError if branch is missing or has no WorkingCalendar.
        """
        if not branch:
            raise AttendanceConfigurationError("Branch is required to determine working calendar.")
        wc = getattr(branch, 'working_calendar', None)
        if not wc:
            raise AttendanceConfigurationError(f"Working calendar is not configured for branch {branch.id}.")
        return wc

    @staticmethod
    def get_branch_work_days(branch: Optional[Branch]) -> List[int]:
        """
        Return the list of configured working day integers (0=Monday, 6=Sunday).
        Does NOT silently fall back to Mon-Fri; raises AttendanceConfigurationError
        if WorkingCalendar is missing or invalid.
        """
        wc = AttendanceCalculationService.get_branch_working_calendar(branch)
        return wc.get_work_days_list()

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
        taking both the branch WorkingCalendar, recurring rules, and active branch Holidays into account.
        Raises AttendanceConfigurationError if working calendar is missing or invalid.
        """
        from apps.organization.services import WorkingCalendarService
        from apps.organization.exceptions import WorkingCalendarConfigurationError
        try:
            return WorkingCalendarService.is_working_day(branch, target_date)
        except WorkingCalendarConfigurationError as exc:
            raise AttendanceConfigurationError(str(exc)) from exc

    @staticmethod
    def get_branch_shift(branch: Optional[Branch]) -> Shift:
        """
        Resolve the single active shift configured for the branch.
        Raises AttendanceConfigurationError if branch is missing, or if 0 or >1 active shifts exist.
        """
        if not branch:
            raise AttendanceConfigurationError("Branch is required to determine shift configuration.")
        active_shifts = Shift.objects.filter(branch=branch, is_active=True)
        count = active_shifts.count()
        if count == 0:
            raise AttendanceConfigurationError(
                f"No active shift configured for branch {branch.id} ({branch.name})."
            )
        if count > 1:
            raise AttendanceConfigurationError(
                f"Multiple active shifts configured for branch {branch.id} ({branch.name}). Branch must have a single active shift configuration."
            )
        return active_shifts.first()

    @staticmethod
    def get_effective_shift(employee: Employee, target_date: Optional[date] = None) -> Optional[Shift]:
        """
        Resolve the employee's authoritative shift for the target_date from their branch's shift configuration.
        Does not require or query EmployeeShiftAssignment.
        Returns None if target_date is provided and falls outside the shift's work_days.
        """
        if not employee:
            return None
        if not employee.branch_id:
            raise AttendanceConfigurationError(
                f"Branch is not configured for employee {employee.id}."
            )

        shift = AttendanceCalculationService.get_branch_shift(employee.branch)
        if target_date is not None:
            shift_work_days = AttendanceCalculationService.get_shift_work_days(shift)
            if target_date.weekday() not in shift_work_days:
                return None

        return shift

    @staticmethod
    def resolve_scheduled_shift(employee: Employee, target_date: date) -> Optional[Shift]:
        """
        Resolves the employee's authoritative shift for a scheduled working day
        following the strict evaluation order:
        1. Resolve employee and branch.
        2. Resolve branch WorkingCalendar / Holiday precedence via is_branch_working_day.
        3. If non-working or holiday, returns None without requiring a shift.
        4. If scheduled working day, resolves the branch's authoritative Shift configuration.
        5. If no active shift exists for the branch, raises AttendanceConfigurationError.
        6. If multiple active shifts exist for the branch, raises AttendanceConfigurationError.
        7. If single active shift exists, evaluates Shift.work_days.
           If target_date is in Shift.work_days, returns Shift; else returns None.
        """
        if not employee or not employee.branch:
            raise AttendanceConfigurationError(
                f"Branch is not configured for employee {employee.id if employee else 'None'}."
            )

        # Steps 2-3: Check authoritative branch working day (accounts for holiday, recurring rules, and base calendar)
        if not AttendanceCalculationService.is_branch_working_day(employee.branch, target_date):
            return None

        # Step 4-6: Resolve the branch's active shift configuration
        shift = AttendanceCalculationService.get_branch_shift(employee.branch)

        # Step 7: Evaluate shift work_days
        shift_work_days = AttendanceCalculationService.get_shift_work_days(shift)
        if target_date.weekday() in shift_work_days:
            return shift

        return None

    @staticmethod
    def get_shift_work_days(shift: Optional[Shift]) -> List[int]:
        """
        Return the scheduled work days for a shift.
        Delegates directly to shift.get_work_days_list() as the authoritative single source of truth.
        Raises AttendanceConfigurationError if shift is None.
        Does not fall back to Mon-Fri.
        """
        if not shift:
            raise AttendanceConfigurationError("Shift is required to determine shift work days.")
        return shift.get_work_days_list()

    @staticmethod
    def is_shift_working_day(shift: Optional[Shift], target_date: date) -> bool:
        """Check if target_date is a scheduled working day for the shift."""
        if not shift:
            return False
        return target_date.weekday() in AttendanceCalculationService.get_shift_work_days(shift)

    @staticmethod
    def is_employee_scheduled_work_day(employee: Employee, target_date: date) -> bool:
        """
        Determine if target_date is a scheduled working day for the employee,
        respecting both the branch WorkingCalendar and assigned Shift.work_days.
        Raises AttendanceConfigurationError if WorkingCalendar is missing/invalid,
        or if active branch shift is missing on a branch working day.
        """
        shift = AttendanceCalculationService.resolve_scheduled_shift(employee, target_date)
        return shift is not None

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
            if attendance.employee and attendance.employee.branch_id:
                try:
                    shift = AttendanceCalculationService.get_branch_shift(attendance.employee.branch)
                except AttendanceConfigurationError:
                    shift = None

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
