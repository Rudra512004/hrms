"""
Payroll calculation engine — Phase 4.

Design principles:
- All monetary arithmetic uses Python Decimal. No floats.
- FIXED_AMOUNT and PERCENTAGE_OF_BASIC are the only supported calculation types.
- Unsupported types raise PayrollCalculationError explicitly (never silently zero).
- Finalized payroll is immutable — re-calculation is rejected.
- Approved adjustments survive draft recalculation deterministically.
- The same inputs always produce the same result (idempotent).
- Tenant isolation: every operation is scoped to period.organization.
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from typing import Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.attendance.models import Attendance, Holiday
from apps.leaves.models import LeaveRequest
from .models import (
    CompensationHistory,
    PayrollRun,
    PayrollRecord,
    PayrollLineItem,
    PayrollAdjustment,
    Payslip,
    SalaryStructure,
    SalaryStructureComponent,
    SalaryComponent,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PayrollCalculationError(Exception):
    """Raised when payroll cannot be safely calculated."""


class PayrollImmutableError(PayrollCalculationError):
    """Raised when attempting to mutate finalized or approved payroll."""


# ---------------------------------------------------------------------------
# Working-day helpers
# ---------------------------------------------------------------------------

def _working_days_in_period(branch_id: int, start: date, end: date) -> int:
    """
    Count working days within [start, end] excluding branch holidays/off-days.
    """
    if not branch_id:
        return 0
    from apps.organization.models import Branch
    from apps.organization.services import WorkingCalendarService
    branch = Branch.objects.get(id=branch_id)
    return WorkingCalendarService.count_working_days(branch, start, end)


# ---------------------------------------------------------------------------
# Salary / Compensation helpers
# ---------------------------------------------------------------------------

def _get_active_compensation(employee, period_start: date, period_end: Optional[date] = None) -> CompensationHistory:
    """
    Return the CompensationHistory record that was active at period_start.
    Priority: open-ended record (effective_to=None) effective at period_start.
    Falls back to the most recent record effective during the period.
    Returns None if no record found.
    """
    # Best: record effective at period_start with no end date
    record = (
        CompensationHistory.objects.filter(
            employee=employee,
            effective_from__lte=period_start,
            effective_to__isnull=True,
        )
        .prefetch_related('salary_structure__components__component')
        .order_by('-effective_from')
        .first()
    )
    if record:
        return record

    # Fallback: bounded record still active at period_start
    record = (
        CompensationHistory.objects.filter(
            employee=employee,
            effective_from__lte=period_start,
            effective_to__gte=period_start,
        )
        .prefetch_related('salary_structure__components__component')
        .order_by('-effective_from')
        .first()
    )
    if record:
        return record

    # Fallback: any record active during the period
    if period_end:
        record = (
            CompensationHistory.objects.filter(
                employee=employee,
                effective_from__lte=period_end,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=period_start))
            .prefetch_related('salary_structure__components__component')
            .order_by('-effective_from')
            .first()
        )
        if record:
            return record

    # Last resort: most recent record
    return (
        CompensationHistory.objects.filter(employee=employee)
        .prefetch_related('salary_structure__components__component')
        .order_by('-effective_from')
        .first()
    )


def _get_active_salary(employee, period_start: date, period_end: Optional[date] = None) -> Decimal:
    """Return basic_salary from active CompensationHistory; Decimal('0.00') if none."""
    record = _get_active_compensation(employee, period_start, period_end)
    return record.basic_salary if record else Decimal('0.00')


# ---------------------------------------------------------------------------
# Attendance helpers
# ---------------------------------------------------------------------------

def _attendance_summary(employee, start: date, end: date) -> dict:
    """Return present/half_day counts from Attendance within the period."""
    records = Attendance.objects.filter(employee=employee, date__range=[start, end])
    present = records.filter(status='present').count()
    half = records.filter(status='half_day').count()
    return {'present': present, 'half': half}


def _approved_leave_dates(employee, start: date, end: date, exclude_dates: set = None) -> set:
    """
    Return a set of distinct working dates of approved LeaveRequests overlapping the pay period.
    Excludes weekends, holidays, and dates already counted in attendance.
    """
    if exclude_dates is None:
        exclude_dates = set()

    requests = LeaveRequest.objects.filter(
        employee=employee,
        status='approved',
        start_date__lte=end,
        end_date__gte=start,
    )
    if not requests.exists():
        return set()

    from apps.organization.services import WorkingCalendarService
    branch = getattr(employee, 'branch', None)
    leave_dates = set()

    for lr in requests:
        clipped_start = max(lr.start_date, start)
        clipped_end = min(lr.end_date, end)
        current = clipped_start
        while current <= clipped_end:
            if current not in exclude_dates:
                if not branch:
                    from apps.organization.exceptions import WorkingCalendarConfigurationError
                    raise WorkingCalendarConfigurationError(
                        "Branch is required to determine leave duration."
                    )
                if WorkingCalendarService.is_working_day(branch, current):
                    leave_dates.add(current)
            current += timedelta(days=1)
    return leave_dates

def _approved_leave_days(employee, start: date, end: date, exclude_dates: set = None) -> int:
    """Wrapper that returns the count of approved leave dates."""
    return len(_approved_leave_dates(employee, start, end, exclude_dates))


# ---------------------------------------------------------------------------
# Salary structure calculation
# ---------------------------------------------------------------------------

def _calculate_component_amount(
    component: SalaryStructureComponent,
    basic_salary: Decimal,
) -> Decimal:
    """
    Calculate the monetary amount for a single SalaryStructureComponent.

    Supported:
    - FIXED_AMOUNT: returns component.amount
    - PERCENTAGE_OF_BASIC: returns (component.amount / 100) * basic_salary

    Unsupported types raise PayrollCalculationError explicitly.
    Never silently returns zero for unknown types.
    """
    calc_type = component.calculation_type

    if calc_type == 'FIXED_AMOUNT':
        amount = component.amount
    elif calc_type == 'PERCENTAGE_OF_BASIC':
        if basic_salary <= Decimal('0'):
            raise PayrollCalculationError(
                f"Cannot calculate PERCENTAGE_OF_BASIC for component "
                f"'{component.component.code}': basic_salary is zero or negative."
            )
        amount = (component.amount / Decimal('100')) * basic_salary
    else:
        raise PayrollCalculationError(
            f"Unsupported calculation_type '{calc_type}' on component "
            f"'{component.component.code}'. Only FIXED_AMOUNT and "
            f"PERCENTAGE_OF_BASIC are supported in Phase 4."
        )

    return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _map_kind_to_category(kind: str) -> str:
    """Map SalaryComponent.kind to PayrollLineItem.category."""
    mapping = {
        'earning': 'EARNING',
        'deduction': 'DEDUCTION',
        'employer_contribution': 'EMPLOYER_CONTRIBUTION',
        'tax': 'TAX',
    }
    if kind not in mapping:
        raise PayrollCalculationError(
            f"Unknown component kind '{kind}'. Cannot map to PayrollLineItem category."
        )
    return mapping[kind]


def _build_structure_line_items(
    payroll_record: PayrollRecord,
    structure: SalaryStructure,
    basic_salary: Decimal,
    lop_ratio: Decimal,
) -> list:
    """
    Build PayrollLineItem objects (unsaved) from a SalaryStructure.

    lop_ratio: effective_days / working_days (0.0–1.0), used to prorate earnings.
    Deductions are NOT prorated (e.g., a deduction is taken regardless of LOP).
    """
    components = structure.components.select_related('component').order_by('id')
    if not components.exists():
        raise PayrollCalculationError(
            f"SalaryStructure '{structure.name}' has no components. "
            "Cannot generate payroll line items."
        )

    line_items = []
    for ssc in components:
        sc = ssc.component
        if not sc.is_active:
            continue

        raw_amount = _calculate_component_amount(ssc, basic_salary)

        # Prorate earnings by LOP ratio; deductions/employer contributions are fixed
        if sc.kind == 'earning':
            amount = (raw_amount * lop_ratio).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            amount = raw_amount

        category = _map_kind_to_category(sc.kind)

        line_items.append(PayrollLineItem(
            payroll_record=payroll_record,
            component=sc,
            category=category,
            amount=amount,
            is_backfilled=False,
            calculation_type=ssc.calculation_type,
            calculation_base=basic_salary if ssc.calculation_type == 'PERCENTAGE_OF_BASIC' else ssc.amount,
            rate=ssc.amount if ssc.calculation_type == 'PERCENTAGE_OF_BASIC' else None,
            calculation_metadata={
                'raw_amount': str(raw_amount),
                'lop_ratio': str(lop_ratio) if sc.kind == 'earning' else '1.0',
            },
            source_structure_component=ssc,
        ))

    return line_items


def _build_legacy_line_item(
    payroll_record: PayrollRecord,
    gross_salary: Decimal,
) -> PayrollLineItem:
    """
    Build a single backfilled 'Legacy Gross' line item for employees
    without a SalaryStructure assignment.
    """
    return PayrollLineItem(
        payroll_record=payroll_record,
        component=None,
        category='EARNING',
        amount=gross_salary,
        is_backfilled=True,
        calculation_type='LEGACY_RECONSTRUCTED',
        calculation_base=gross_salary,
        rate=None,
        calculation_metadata={
            'source': 'legacy_basic_salary',
            'note': 'Calculated from CompensationHistory.basic_salary (no SalaryStructure assigned)',
        },
    )


def _build_adjustment_line_items(
    payroll_record: PayrollRecord,
    adjustments: list,
) -> list:
    """
    Build PayrollLineItem objects (unsaved) from approved PayrollAdjustments.
    Each adjustment maps to one line item.
    """
    line_items = []
    for adj in adjustments:
        sc = adj.component
        category = _map_kind_to_category(sc.kind)
        line_items.append(PayrollLineItem(
            payroll_record=payroll_record,
            component=sc,
            category=category,
            amount=adj.amount,
            is_backfilled=False,
            calculation_type='ADJUSTMENT',
            calculation_base=adj.amount,
            rate=None,
            calculation_metadata={
                'source': 'payroll_adjustment',
                'adjustment_id': adj.id,
                'reason': adj.reason,
            },
            source_adjustment=adj,
        ))
    return line_items


def _aggregate_line_items(line_items: list) -> dict:
    """
    Sum line items by category and compute gross/net salary.
    Returns dict with: total_earnings, total_deductions,
                       employer_contributions, total_tax,
                       gross_salary, net_salary.
    """
    totals = {
        'total_earnings': Decimal('0.00'),
        'total_deductions': Decimal('0.00'),
        'employer_contributions': Decimal('0.00'),
        'total_tax': Decimal('0.00'),
    }
    for li in line_items:
        cat = li.category
        if cat == 'EARNING':
            totals['total_earnings'] += li.amount
        elif cat == 'DEDUCTION':
            totals['total_deductions'] += li.amount
        elif cat == 'EMPLOYER_CONTRIBUTION':
            totals['employer_contributions'] += li.amount
        elif cat == 'TAX':
            totals['total_tax'] += li.amount

    gross = totals['total_earnings']
    net = (
        gross
        - totals['total_deductions']
        - totals['total_tax']
    )
    # net cannot be negative
    net = max(Decimal('0.00'), net)
    return {**totals, 'gross_salary': gross, 'net_salary': net}


# ---------------------------------------------------------------------------
# Immutability guards
# ---------------------------------------------------------------------------

def _assert_run_mutable(run: PayrollRun):
    """Raise PayrollImmutableError if run is approved or finalized."""
    if run.status in (PayrollRun.STATUS_APPROVED, PayrollRun.STATUS_FINALIZED):
        raise PayrollImmutableError(
            f"PayrollRun #{run.id} ({run.year}/{run.month:02d} {run.run_type}) "
            f"is {run.status} and cannot be recalculated or modified."
        )


# ---------------------------------------------------------------------------
# Core payroll generation
# ---------------------------------------------------------------------------

@transaction.atomic
def generate_payroll_for_period(run: PayrollRun, requesting_user=None) -> list:
    """
    Generate PayrollRecord + PayrollLineItems for every eligible employee.

    Invariants:
    - FINALIZED runs are rejected.
    - APPROVED runs are rejected.
    - For DRAFT runs: existing calculated line items are deleted and rebuilt.
    - Approved adjustments survive recalculation.
    - Idempotent: same inputs → same outputs.

    Returns list of PayrollRecord instances.
    """
    _assert_run_mutable(run)

    from apps.employees.models import Employee, EmploymentStatus

    # -------------------------------------------------------------------
    # 1. Delete previous DRAFT PayrollRecords (and their line items via CASCADE)
    # -------------------------------------------------------------------
    draft_records = PayrollRecord.objects.filter(period=run, status=PayrollRecord.STATUS_DRAFT)
    
    # Reset any processed adjustments back to approved so they aren't lost on recalculation
    draft_adj_ids = PayrollLineItem.objects.filter(
        payroll_record__in=draft_records,
        source_adjustment__isnull=False
    ).values_list('source_adjustment_id', flat=True)
    
    if draft_adj_ids:
        PayrollAdjustment.objects.filter(id__in=draft_adj_ids).update(
            status=PayrollAdjustment.STATUS_APPROVED
        )

    draft_records.delete()

    # -------------------------------------------------------------------
    # 2. Collect eligible employees (scoped to run.organization)
    # -------------------------------------------------------------------
    employees = (
        Employee.objects.filter(
            organization=run.organization,
            employment_status__in=[EmploymentStatus.ACTIVE, EmploymentStatus.ON_NOTICE],
        )
        .filter(Q(exit_date__isnull=True) | Q(exit_date__gte=run.start_date))
        .select_related('organization', 'user', 'branch')
    )

    records_to_create = []

    for emp in employees:
        # ---------------------------------------------------------------
        # 3. Attendance snapshot
        # ---------------------------------------------------------------
        working_days = _working_days_in_period(emp.branch_id, run.start_date, run.end_date)
        att = _attendance_summary(emp, run.start_date, run.end_date)

        present_dates = set(
            Attendance.objects.filter(
                employee=emp,
                date__range=[run.start_date, run.end_date],
                status='present',
            ).values_list('date', flat=True)
        )
        half_dates = set(
            Attendance.objects.filter(
                employee=emp,
                date__range=[run.start_date, run.end_date],
                status='half_day',
            ).values_list('date', flat=True)
        )
        leave_dates = _approved_leave_dates(
            emp, run.start_date, run.end_date, exclude_dates=present_dates
        )
        leave_days = len(leave_dates)

        present = att['present']
        half = att['half']
        calculated_effective = (
            Decimal(present)
            + Decimal(half) * Decimal('0.5')
            + Decimal(leave_days)
        )
        effective_days = (
            min(Decimal(working_days), calculated_effective)
            if working_days > 0
            else Decimal('0.00')
        )
        absent_days = max(0, working_days - int(effective_days))

        # Calculate exact LOP dates
        from apps.organization.services import WorkingCalendarService
        all_working_dates = set()
        if emp.branch:
            current_date = run.start_date
            while current_date <= run.end_date:
                if WorkingCalendarService.is_working_day(emp.branch, current_date):
                    all_working_dates.add(current_date)
                current_date += timedelta(days=1)
        
        # LOP dates are working dates that are NOT fully present, half present, or on approved leave
        lop_dates_set = all_working_dates - present_dates - half_dates - leave_dates
        lop_dates = sorted([d.isoformat() for d in lop_dates_set])

        # ---------------------------------------------------------------
        # 4. Compensation / salary
        # ---------------------------------------------------------------
        compensation = _get_active_compensation(emp, run.start_date, run.end_date)
        basic_salary = compensation.basic_salary if compensation else Decimal('0.00')

        # ---------------------------------------------------------------
        # 5. Calculate legacy gross (basic × proration) — used as fallback
        # ---------------------------------------------------------------
        if working_days > 0:
            lop_ratio = effective_days / Decimal(working_days)
            legacy_gross = (basic_salary * lop_ratio).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        else:
            lop_ratio = Decimal('0')
            legacy_gross = Decimal('0.00')

        # ---------------------------------------------------------------
        # 6. Determine whether a SalaryStructure is assigned
        # ---------------------------------------------------------------
        salary_structure = (
            compensation.salary_structure
            if compensation and compensation.salary_structure_id
            else None
        )

        # ---------------------------------------------------------------
        # 7. Collect approved adjustments for this employee + period
        # ---------------------------------------------------------------
        approved_adjustments = list(
            PayrollAdjustment.objects.filter(
                employee=emp,
                period_year=run.year,
                period_month=run.month,
                status=PayrollAdjustment.STATUS_APPROVED,
            ).select_related('component').order_by('id')
        )

        records_to_create.append({
            'employee': emp,
            'working_days': working_days,
            'present_days': present,
            'half_days': half,
            'absent_days': absent_days,
            'leave_days': leave_days,
            'effective_days': effective_days,
            'basic_salary': basic_salary,
            'lop_ratio': lop_ratio,
            'legacy_gross': legacy_gross,
            'salary_structure': salary_structure,
            'approved_adjustments': approved_adjustments,
            'lop_dates': lop_dates,
        })

    # -------------------------------------------------------------------
    # 8. Bulk-create PayrollRecords with placeholder amounts, then update
    # -------------------------------------------------------------------
    records = []
    for ctx in records_to_create:
        record = PayrollRecord(
            period=run,
            employee=ctx['employee'],
            working_days=ctx['working_days'],
            present_days=ctx['present_days'],
            half_days=ctx['half_days'],
            absent_days=ctx['absent_days'],
            leave_days=ctx['leave_days'],
            effective_days=ctx['effective_days'],
            basic_salary=ctx['basic_salary'],
            total_earnings=Decimal('0.00'),
            total_deductions=Decimal('0.00'),
            employer_contributions=Decimal('0.00'),
            total_tax=Decimal('0.00'),
            gross_salary=Decimal('0.00'),
            net_salary=Decimal('0.00'),
            status=PayrollRecord.STATUS_DRAFT,
            lop_dates=ctx['lop_dates'],
        )
        records.append(record)

    PayrollRecord.objects.bulk_create(records)

    # -------------------------------------------------------------------
    # 9. Build and persist PayrollLineItems for each record
    # -------------------------------------------------------------------
    all_line_items = []
    records_to_update = []

    # Re-fetch to get PKs after bulk_create
    created_records = {
        r.employee_id: r
        for r in PayrollRecord.objects.filter(period=run, status=PayrollRecord.STATUS_DRAFT)
    }

    for ctx in records_to_create:
        record = created_records.get(ctx['employee'].id)
        if not record:
            continue

        line_items = []

        if ctx['salary_structure']:
            # Structure-based calculation
            structure_items = _build_structure_line_items(
                record,
                ctx['salary_structure'],
                ctx['basic_salary'],
                ctx['lop_ratio'],
            )
            line_items.extend(structure_items)
        else:
            # Legacy fallback: single "Legacy Gross" EARNING
            line_items.append(_build_legacy_line_item(record, ctx['legacy_gross']))

        # Approved adjustments
        adj_items = _build_adjustment_line_items(record, ctx['approved_adjustments'])
        line_items.extend(adj_items)

        all_line_items.extend(line_items)

        # Compute aggregates
        agg = _aggregate_line_items(line_items)
        record.total_earnings = agg['total_earnings']
        record.total_deductions = agg['total_deductions']
        record.employer_contributions = agg['employer_contributions']
        record.total_tax = agg['total_tax']
        record.gross_salary = agg['gross_salary']
        record.net_salary = agg['net_salary']
        records_to_update.append(record)

    PayrollLineItem.objects.bulk_create(all_line_items)
    PayrollRecord.objects.bulk_update(
        records_to_update,
        [
            'total_earnings', 'total_deductions', 'employer_contributions',
            'total_tax', 'gross_salary', 'net_salary',
        ],
    )

    # -------------------------------------------------------------------
    # 10. Mark approved adjustments as processed
    # -------------------------------------------------------------------
    adj_ids = []
    for ctx in records_to_create:
        for adj in ctx['approved_adjustments']:
            adj_ids.append(adj.id)
    if adj_ids:
        PayrollAdjustment.objects.filter(id__in=adj_ids).update(
            status=PayrollAdjustment.STATUS_PROCESSED
        )

    run.generated_at = timezone.now()
    run.save(update_fields=['generated_at'])

    return list(created_records.values())


# ---------------------------------------------------------------------------
# Payslip issuance
# ---------------------------------------------------------------------------

def issue_payslips_for_period(run: PayrollRun) -> list:
    """
    Atomically issue exactly one Payslip for each approved PayrollRecord.
    Must be called within an atomic transaction.
    Raises ValueError if period is not approved.
    """
    if run.status != PayrollRun.STATUS_APPROVED:
        raise ValueError("Cannot issue payslips for an unapproved payroll run.")

    records = run.records.filter(status=PayrollRecord.STATUS_APPROVED).select_related(
        'employee', 'period'
    )
    payslips = []
    from apps.notifications.services import NotificationService
    from django.db import transaction

    for record in records:
        emp_code = record.employee.employee_code.strip()
        num = f"PAY-{run.year}{run.month:02d}-{emp_code}"
        payslip, created = Payslip.objects.get_or_create(
            payroll_record=record,
            defaults={
                'payslip_number': num,
                'status': Payslip.STATUS_ISSUED,
            },
        )
        payslips.append(payslip)

        if created:
            transaction.on_commit(
                lambda p=payslip, r=record, num=num: NotificationService.create_in_app_notification(
                    recipient=r.employee.user,
                    organization=r.employee.organization,
                    notification_type='PAYSLIP_ISSUED',
                    title='Payslip Issued',
                    message=(
                        f'Your payslip {num} for '
                        f'{r.period.year}-{r.period.month:02d} has been issued.'
                    ),
                    reference_id=str(p.id),
                )
            )

    return payslips


# ---------------------------------------------------------------------------
# Finalization
# ---------------------------------------------------------------------------

@transaction.atomic
def finalize_payroll_run(run: PayrollRun, requested_by=None) -> PayrollRun:
    """
    Transition a PayrollRun from APPROVED → FINALIZED.
    FINALIZED runs are permanently immutable.
    """
    run = PayrollRun.objects.select_for_update().get(id=run.id)

    if run.status == PayrollRun.STATUS_FINALIZED:
        raise PayrollImmutableError(
            f"PayrollRun #{run.id} is already finalized."
        )
    if run.status != PayrollRun.STATUS_APPROVED:
        raise ValueError(
            f"PayrollRun #{run.id} must be APPROVED before it can be finalized. "
            f"Current status: {run.status}"
        )

    run.status = PayrollRun.STATUS_FINALIZED
    run.save(update_fields=['status', 'updated_at'])

    # Finalize all approved records
    run.records.filter(status=PayrollRecord.STATUS_APPROVED).update(
        status=PayrollRecord.STATUS_FINALIZED
    )

    return run
