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
