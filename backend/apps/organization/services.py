from datetime import date, timedelta
from typing import Optional, Set
from django.apps import apps
from apps.organization.models import Branch, WorkingCalendar
from apps.organization.exceptions import WorkingCalendarConfigurationError


def _get_holiday_model():
    """Dynamically resolves the Holiday model without creating a static module-level dependency on apps.attendance."""
    return apps.get_model('attendance', 'Holiday')


class WorkingCalendarService:
    """
    Authoritative domain service for branch working calendar evaluations.
    Cross-domain consumers (Attendance, Leave, Payroll) rely on this service
    as the single source of truth for working-day calculations.

    Precedence Hierarchy:
    1. Explicit active Holiday (date is non-working)
    2. Recurring WorkingCalendarRule for matching (weekday, occurrence)
    3. Base WorkingCalendar configured weekdays (work_days)
    """

    @staticmethod
    def is_holiday(branch: Optional[Branch], target_date: date) -> bool:
        """Checks whether target_date is an active holiday for the specified branch."""
        if not branch:
            return False
        Holiday = _get_holiday_model()
        return Holiday.objects.filter(branch=branch, date=target_date, is_active=True).exists()

    @staticmethod
    def is_working_day(branch: Optional[Branch], target_date: date) -> bool:
        """
        Determines whether target_date is a working day for the given branch following strict precedence:
        1. Explicit active Holiday -> Non-working (False)
        2. Recurring WorkingCalendarRule for (weekday, occurrence) -> rule.is_working
        3. Base WorkingCalendar work_days -> weekday in work_days

        Raises WorkingCalendarConfigurationError if branch is None, WorkingCalendar is missing,
        or work_days is unconfigured/invalid. Does NOT fall back to Mon-Fri.
        """
        if not branch:
            raise WorkingCalendarConfigurationError("Branch is required to determine working day.")

        # Precedence 1: Explicit active branch holiday
        if WorkingCalendarService.is_holiday(branch, target_date):
            return False

        # Resolve branch WorkingCalendar
        try:
            wc = getattr(branch, 'working_calendar', None)
        except Exception:
            wc = None
        if not wc:
            raise WorkingCalendarConfigurationError(
                f"Working calendar is not configured for branch {branch.id}."
            )

        # Precedence 2 & 3: Calendar recurring rules and base weekdays
        return wc.is_working_day(target_date)

    @staticmethod
    def count_working_days(
        branch: Optional[Branch],
        start_date: date,
        end_date: date,
        exclude_dates: Optional[Set[date]] = None
    ) -> int:
        """
        Counts working days in the closed interval [start_date, end_date] for the given branch.
        Accounts for active holidays, recurring monthly rules, base work days, and optional excluded dates.
        Evaluates batch date ranges in O(days) time without N+1 queries.

        Raises WorkingCalendarConfigurationError if branch is None or has no WorkingCalendar.
        """
        if not branch:
            raise WorkingCalendarConfigurationError("Branch is required to count working days.")

        if start_date > end_date:
            return 0

        try:
            wc = getattr(branch, 'working_calendar', None)
        except Exception:
            wc = None
        if not wc:
            raise WorkingCalendarConfigurationError(
                f"Working calendar is not configured for branch {branch.id}."
            )

        base_work_days = set(wc.get_work_days_list())
        recurring_rules = wc.get_recurring_rules_dict()

        # Pre-fetch all active holiday dates within the interval
        Holiday = _get_holiday_model()
        holiday_dates = set(
            Holiday.objects.filter(
                branch=branch,
                date__range=[start_date, end_date],
                is_active=True
            ).values_list('date', flat=True)
        )

        working_day_count = 0
        current = start_date
        while current <= end_date:
            # Check exclusions & holidays
            if current in holiday_dates or (exclude_dates and current in exclude_dates):
                current += timedelta(days=1)
                continue

            weekday = current.weekday()
            occurrence = (current.day - 1) // 7 + 1

            # Precedence 2: Recurring rule override
            if (weekday, occurrence) in recurring_rules:
                is_working = recurring_rules[(weekday, occurrence)]
            else:
                # Precedence 3: Base weekday configuration
                is_working = weekday in base_work_days

            if is_working:
                working_day_count += 1

            current += timedelta(days=1)

        return working_day_count


class OrganizationReadinessService:
    """Read-only operational readiness assessment for an organization.

    This is intentionally advisory: it never blocks existing workflows or
    silently creates configuration. It gives administrators a concise view of
    the prerequisites that make attendance, leave, and access reliable.
    """

    @staticmethod
    def assess(organization):
        LeaveType = apps.get_model('leaves', 'LeaveType')
        Role = apps.get_model('authorization', 'Role')
        Shift = apps.get_model('attendance', 'Shift')

        active_branches = Branch.objects.filter(organization=organization, is_active=True)
        branch_ids = list(active_branches.values_list('id', flat=True))
        calendar_branch_ids = set(WorkingCalendar.objects.filter(branch_id__in=branch_ids).exclude(work_days='').values_list('branch_id', flat=True))
        policy_branch_ids = set(
            apps.get_model('organization', 'AttendancePolicy').objects.filter(branch_id__in=branch_ids).values_list('branch_id', flat=True)
        )
        shift_branch_ids = set(Shift.objects.filter(branch_id__in=branch_ids, is_active=True).values_list('branch_id', flat=True))

        def check(key, label, state, detail, path, required=True):
            return {
                'key': key,
                'label': label,
                'state': state,
                'detail': detail,
                'path': path,
                'required': required,
            }

        missing_calendars = len(set(branch_ids) - calendar_branch_ids)
        missing_policies = len(set(branch_ids) - policy_branch_ids)
        missing_shifts = len(set(branch_ids) - shift_branch_ids)
        department_count = sum(branch.departments.filter(is_active=True).count() for branch in active_branches)
        team_count = sum(department.teams.filter(is_active=True).count() for branch in active_branches for department in branch.departments.all())
        designation_count = organization.designations.filter(is_active=True).count()
        leave_type_count = LeaveType.objects.filter(organization=organization, is_active=True).count()
        role_count = Role.objects.filter(organization=organization, is_active=True).count()

        checks = [
            check('branches', 'Active locations', 'ready' if branch_ids else 'action_required', f'{len(branch_ids)} active location(s) configured.', '/admin/branches'),
            check('calendars', 'Working calendars', 'ready' if branch_ids and not missing_calendars else 'action_required', 'Every active location has working days.' if not missing_calendars and branch_ids else f'{missing_calendars} active location(s) need working days.', '/admin/working-calendar'),
            check('attendance_policies', 'Attendance policies', 'ready' if branch_ids and not missing_policies else 'action_required', 'Every active location has an attendance policy.' if not missing_policies and branch_ids else f'{missing_policies} active location(s) need a policy.', '/admin/attendance-policy'),
            check('structure', 'Organization structure', 'ready' if department_count and designation_count else 'action_required', f'{department_count} department(s), {team_count} team(s), and {designation_count} designation(s).', '/admin/departments'),
            check('leave_types', 'Leave configuration', 'ready' if leave_type_count else 'action_required', f'{leave_type_count} active leave type(s).', '/admin/leave-types'),
            check('roles', 'Roles and access', 'ready' if role_count else 'action_required', f'{role_count} active role(s).', '/admin/roles'),
            check('shifts', 'Shift schedules', 'ready' if branch_ids and not missing_shifts else 'recommended', 'Every active location has an active shift.' if not missing_shifts and branch_ids else f'{missing_shifts} active location(s) do not yet have a shift.', '/admin/shifts', required=False),
        ]
        required_checks = [item for item in checks if item['required']]
        ready_required = sum(item['state'] == 'ready' for item in required_checks)
        return {
            'organization_id': organization.id,
            'organization_name': organization.name,
            'score': round((ready_required / len(required_checks)) * 100) if required_checks else 0,
            'checks': checks,
        }
