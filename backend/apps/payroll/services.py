"""
Payroll generation engine.

All monetary arithmetic uses Python's Decimal type.
This service is the single source of truth for payroll calculation.
It reads from Attendance, LeaveRequest, Holiday, and CompensationHistory
but never duplicates their data — results are snapshotted into PayrollRecord.
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from apps.attendance.models import Attendance, Holiday
from apps.leaves.models import LeaveRequest
from .models import CompensationHistory, PayrollPeriod, PayrollRecord, Payslip


def _working_days_in_period(organization_id: int, start: date, end: date) -> int:
    """
    Count weekdays (Mon–Fri) within [start, end] that are NOT org holidays.
    Mirrors the logic in LeaveRequest.duration_days for consistency.
    """
    holiday_dates = set(
        Holiday.objects.filter(
            organization_id=organization_id,
            date__range=[start, end],
            is_active=True,
        ).values_list('date', flat=True)
    )

    days = 0
    current = start
    while current <= end:
        if current.weekday() < 5 and current not in holiday_dates:
            days += 1
        current += timedelta(days=1)
    return days


def _get_active_salary(employee, period_start: date) -> Decimal:
    """
    Return the basic_salary that was active at the start of the period.
    Uses the CompensationHistory record whose effective_from <= period_start
    and (effective_to is null OR effective_to >= period_start).
    """
    record = (
        CompensationHistory.objects.filter(
            employee=employee,
            effective_from__lte=period_start,
        )
        .filter(
            effective_to__isnull=True,
        )
        .order_by('-effective_from')
        .first()
    )
    if record is None:
        # Fallback: find any record that was active during the period
        record = (
            CompensationHistory.objects.filter(
                employee=employee,
                effective_from__lte=period_start,
                effective_to__gte=period_start,
            )
            .order_by('-effective_from')
            .first()
        )
    return record.basic_salary if record else Decimal('0.00')


def _attendance_summary(employee, start: date, end: date) -> dict:
    """Return present/half_day counts from Attendance within the period."""
    records = Attendance.objects.filter(
        employee=employee,
        date__range=[start, end],
    )
    present = records.filter(status='present').count()
    half = records.filter(status='half_day').count()
    return {'present': present, 'half': half}


def _approved_leave_days(employee, start: date, end: date) -> int:
    """
    Sum duration_days of approved LeaveRequests overlapping the pay period.
    duration_days already excludes weekends and holidays.
    """
    requests = LeaveRequest.objects.filter(
        employee=employee,
        status='approved',
        start_date__lte=end,
        end_date__gte=start,
    )
    total = 0
    for lr in requests:
        # Clip the leave to the period boundary before counting
        clipped_start = max(lr.start_date, start)
        clipped_end = min(lr.end_date, end)

        # Count working days in the clipped range (excludes weekends/holidays)
        holiday_dates = set(
            Holiday.objects.filter(
                organization=employee.organization,
                date__range=[clipped_start, clipped_end],
                is_active=True,
            ).values_list('date', flat=True)
        )
        current = clipped_start
        while current <= clipped_end:
            if current.weekday() < 5 and current not in holiday_dates:
                total += 1
            current += timedelta(days=1)
    return total


def generate_payroll_for_period(period: PayrollPeriod, requesting_user=None) -> list:
    """
    Generate PayrollRecord for every active employee in the organization.
    Must be called inside a transaction (callers wrap it).
    Returns the list of created/updated PayrollRecord instances.

    Raises ValueError if the period is already approved.
    """
    if period.status == PayrollPeriod.STATUS_APPROVED:
        raise ValueError("Cannot re-generate an approved payroll period.")

    from apps.employees.models import Employee, EmploymentStatus

    # Delete any previous draft records for this period (re-generation allowed)
    PayrollRecord.objects.filter(period=period, status=PayrollRecord.STATUS_DRAFT).delete()

    employees = Employee.objects.filter(
        organization=period.organization,
        employment_status=EmploymentStatus.ACTIVE,
    ).select_related('organization', 'user')

    working_days = _working_days_in_period(
        period.organization_id, period.start_date, period.end_date
    )

    records = []

    for emp in employees:
        basic_salary = _get_active_salary(emp, period.start_date)
        att = _attendance_summary(emp, period.start_date, period.end_date)
        leave_days = _approved_leave_days(emp, period.start_date, period.end_date)

        present = att['present']
        half = att['half']
        # Effective paid days: full present + half_days * 0.5 + approved leave
        effective_days = Decimal(present) + Decimal(half) * Decimal('0.5') + Decimal(leave_days)

        if working_days > 0:
            gross = (basic_salary * effective_days / Decimal(working_days)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        else:
            gross = Decimal('0.00')

        absent_days = max(0, working_days - present - half - leave_days)

        record = PayrollRecord(
            period=period,
            employee=emp,
            working_days=working_days,
            present_days=present,
            half_days=half,
            absent_days=absent_days,
            leave_days=leave_days,
            effective_days=effective_days,
            basic_salary=basic_salary,
            gross_salary=gross,
            net_salary=gross,
            status=PayrollRecord.STATUS_DRAFT,
        )
        records.append(record)

    PayrollRecord.objects.bulk_create(records)

    period.generated_at = timezone.now()
    period.save(update_fields=['generated_at'])

    return records


def issue_payslips_for_period(period: PayrollPeriod) -> list:
    """
    Atomically issue exactly one Payslip for each approved PayrollRecord in the period.
    Must be called within an atomic transaction.
    Raises ValueError if period is not approved.
    """
    if period.status != PayrollPeriod.STATUS_APPROVED:
        raise ValueError("Cannot issue payslips for an unapproved period.")

    records = period.records.filter(status=PayrollRecord.STATUS_APPROVED).select_related(
        'employee', 'period'
    )
    payslips = []
    for record in records:
        emp_code = record.employee.employee_code.strip()
        num = f"PAY-{period.year}{period.month:02d}-{emp_code}"
        payslip, _ = Payslip.objects.get_or_create(
            payroll_record=record,
            defaults={
                'payslip_number': num,
                'status': Payslip.STATUS_ISSUED,
            },
        )
        payslips.append(payslip)

    return payslips
