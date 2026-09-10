"""
Payroll Reporting & Reconciliation Service.

Performs database-level aggregation, cross-sectional department/branch
summaries, and exception auditing without duplicating payroll arithmetic.
"""
from decimal import Decimal
from django.db.models import Sum, Avg, Count, Q

from apps.employees.models import Employee, EmploymentStatus
from apps.leaves.models import LeaveRequest
from apps.attendance.models import Attendance
from .models import PayrollPeriod, PayrollRecord, CompensationHistory


def get_period_summary(period: PayrollPeriod, has_sensitive_perm: bool = False) -> dict:
    """
    High-level financial and attendance rollup for a payroll period.
    Uses database-level aggregation to compute totals.
    """
    records = period.records.all()
    agg = records.aggregate(
        total_employees=Count('id'),
        total_basic=Sum('basic_salary'),
        total_gross=Sum('gross_salary'),
        total_net=Sum('net_salary'),
        avg_net=Avg('net_salary'),
        total_working_days=Sum('working_days'),
        total_present_days=Sum('present_days'),
        total_half_days=Sum('half_days'),
        total_leave_days=Sum('leave_days'),
        total_absent_days=Sum('absent_days'),
        total_effective_days=Sum('effective_days'),
    )

    total_employees = agg['total_employees'] or 0
    total_basic = agg['total_basic'] or Decimal('0.00')
    total_gross = agg['total_gross'] or Decimal('0.00')
    total_net = agg['total_net'] or Decimal('0.00')
    avg_net = agg['avg_net'] or Decimal('0.00')
    total_loss_of_pay = max(Decimal('0.00'), total_basic - total_net)

    return {
        'period': {
            'id': period.id,
            'year': period.year,
            'month': period.month,
            'label': f"{period.year}/{period.month:02d}",
            'status': period.status,
            'start_date': str(period.start_date),
            'end_date': str(period.end_date),
        },
        'summary': {
            'total_employees': total_employees,
            'total_basic_salary': str(total_basic) if has_sensitive_perm else None,
            'total_gross_salary': str(total_gross) if has_sensitive_perm else None,
            'total_net_salary': str(total_net) if has_sensitive_perm else None,
            'total_loss_of_pay': str(total_loss_of_pay) if has_sensitive_perm else None,
            'average_net_salary': str(avg_net.quantize(Decimal('0.01'))) if has_sensitive_perm else None,
            'scheduled_working_days': period.records.first().working_days if period.records.exists() else 0,
            'total_present_days': agg['total_present_days'] or 0,
            'total_half_days': agg['total_half_days'] or 0,
            'total_leave_days': agg['total_leave_days'] or 0,
            'total_absent_days': agg['total_absent_days'] or 0,
            'total_effective_paid_days': str(agg['total_effective_days'] or Decimal('0.0')),
        }
    }


def get_reconciliation_records(
    period: PayrollPeriod,
    branch_id: int = None,
    department_id: int = None,
    search: str = None,
    has_sensitive_perm: bool = False,
) -> list:
    """
    Per-employee reconciliation ledger for the period.
    """
    qs = period.records.select_related(
        'employee',
        'employee__user',
        'employee__branch',
        'employee__department',
    )

    if branch_id:
        qs = qs.filter(employee__branch_id=branch_id)
    if department_id:
        qs = qs.filter(employee__department_id=department_id)
    if search:
        search = search.strip()
        qs = qs.filter(
            Q(employee__employee_code__icontains=search)
            | Q(employee__user__first_name__icontains=search)
            | Q(employee__user__last_name__icontains=search)
            | Q(employee__user__email__icontains=search)
        )

    results = []
    for r in qs:
        u = r.employee.user
        emp_name = f"{u.first_name} {u.last_name}".strip() or u.email
        lop = max(Decimal('0.00'), r.basic_salary - r.net_salary)

        results.append({
            'id': r.id,
            'employee_id': r.employee.id,
            'employee_code': r.employee.employee_code,
            'employee_name': emp_name,
            'branch_name': r.employee.branch.name if r.employee.branch else 'Unassigned',
            'department_name': r.employee.department.name if r.employee.department else 'Unassigned',
            'working_days': r.working_days,
            'present_days': r.present_days,
            'half_days': r.half_days,
            'leave_days': r.leave_days,
            'absent_days': r.absent_days,
            'effective_days': str(r.effective_days),
            'basic_salary': str(r.basic_salary) if has_sensitive_perm else None,
            'gross_salary': str(r.gross_salary) if has_sensitive_perm else None,
            'net_salary': str(r.net_salary) if has_sensitive_perm else None,
            'loss_of_pay_amount': str(lop) if has_sensitive_perm else None,
            'status': r.status,
        })

    return results


def get_organization_breakdown(period: PayrollPeriod, has_sensitive_perm: bool = False) -> dict:
    """
    Branch and department rollups aggregated at the database level.
    """
    # By Branch
    branch_agg = (
        period.records.values(
            'employee__branch__id',
            'employee__branch__name',
        )
        .annotate(
            headcount=Count('id'),
            total_net=Sum('net_salary'),
            avg_net=Avg('net_salary'),
        )
        .order_by('employee__branch__name')
    )

    by_branch = []
    for b in branch_agg:
        avg_val = b['avg_net'] or Decimal('0.00')
        by_branch.append({
            'branch_id': b['employee__branch__id'],
            'branch_name': b['employee__branch__name'] or 'Unassigned',
            'headcount': b['headcount'],
            'total_net_salary': str(b['total_net']) if has_sensitive_perm and b['total_net'] is not None else None,
            'average_net_salary': str(avg_val.quantize(Decimal('0.01'))) if has_sensitive_perm else None,
        })

    # By Department
    dept_agg = (
        period.records.values(
            'employee__department__id',
            'employee__department__name',
        )
        .annotate(
            headcount=Count('id'),
            total_net=Sum('net_salary'),
            avg_net=Avg('net_salary'),
        )
        .order_by('employee__department__name')
    )

    by_department = []
    for d in dept_agg:
        avg_val = d['avg_net'] or Decimal('0.00')
        by_department.append({
            'department_id': d['employee__department__id'],
            'department_name': d['employee__department__name'] or 'Unassigned',
            'headcount': d['headcount'],
            'total_net_salary': str(d['total_net']) if has_sensitive_perm and d['total_net'] is not None else None,
            'average_net_salary': str(avg_val.quantize(Decimal('0.01'))) if has_sensitive_perm else None,
        })

    return {
        'by_branch': by_branch,
        'by_department': by_department,
    }


def get_payroll_exceptions(period: PayrollPeriod) -> list:
    """
    Automated pre/post-approval exception and discrepancy detection:
    1. MISSING_RECORD: Active employee expected in this period has no PayrollRecord.
    2. MISSING_COMPENSATION: Active employee has no active CompensationHistory or basic_salary == 0.
    3. FULL_ABSENCE: Employee has 0 effective paid days in the period.
    4. PENDING_LEAVE: Pending leave request overlaps the period.
    5. ATTENDANCE_INCOMPLETE: Attendance record during the period has check_in without check_out.
    """
    exceptions = []
    active_employees = Employee.objects.filter(
        organization=period.organization,
        employment_status=EmploymentStatus.ACTIVE,
    ).select_related('user', 'branch', 'department')

    active_emp_ids = set(active_employees.values_list('id', flat=True))
    period_emp_ids = set(period.records.values_list('employee_id', flat=True))

    # 1. MISSING_RECORD
    missing_record_ids = active_emp_ids - period_emp_ids
    for emp in active_employees.filter(id__in=missing_record_ids):
        u = emp.user
        emp_name = f"{u.first_name} {u.last_name}".strip() or u.email
        exceptions.append({
            'type': 'MISSING_RECORD',
            'severity': 'high',
            'employee_id': emp.id,
            'employee_code': emp.employee_code,
            'employee_name': emp_name,
            'message': f"Active employee {emp.employee_code} ({emp_name}) has no payroll record for this period.",
        })

    # 2. MISSING_COMPENSATION / ZERO_SALARY
    for emp in active_employees:
        has_comp = CompensationHistory.objects.filter(
            employee=emp,
            effective_from__lte=period.start_date,
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=period.start_date)
        ).exists()

        if not has_comp:
            u = emp.user
            emp_name = f"{u.first_name} {u.last_name}".strip() or u.email
            exceptions.append({
                'type': 'MISSING_COMPENSATION',
                'severity': 'high',
                'employee_id': emp.id,
                'employee_code': emp.employee_code,
                'employee_name': emp_name,
                'message': f"Employee {emp.employee_code} ({emp_name}) has no active salary record configured as of {period.start_date}.",
            })

    # Payroll records with basic_salary == 0 where not already reported
    zero_records = period.records.filter(basic_salary=Decimal('0.00')).select_related('employee', 'employee__user')
    for r in zero_records:
        u = r.employee.user
        emp_name = f"{u.first_name} {u.last_name}".strip() or u.email
        # Avoid duplicate report if already reported as missing comp
        if not any(e['type'] == 'MISSING_COMPENSATION' and e['employee_id'] == r.employee.id for e in exceptions):
            exceptions.append({
                'type': 'MISSING_COMPENSATION',
                'severity': 'high',
                'employee_id': r.employee.id,
                'employee_code': r.employee.employee_code,
                'employee_name': emp_name,
                'message': f"Payroll record for {r.employee.employee_code} ({emp_name}) has zero basic salary.",
            })

    # 3. FULL_ABSENCE
    zero_effective = period.records.filter(effective_days=Decimal('0.0')).select_related('employee', 'employee__user')
    for r in zero_effective:
        u = r.employee.user
        emp_name = f"{u.first_name} {u.last_name}".strip() or u.email
        exceptions.append({
            'type': 'FULL_ABSENCE',
            'severity': 'medium',
            'employee_id': r.employee.id,
            'employee_code': r.employee.employee_code,
            'employee_name': emp_name,
            'message': f"Employee {r.employee.employee_code} ({emp_name}) has 0 paid days in this period (100% absence).",
        })

    # 4. PENDING_LEAVE
    pending_leaves = LeaveRequest.objects.filter(
        employee__organization=period.organization,
        status='pending',
        start_date__lte=period.end_date,
        end_date__gte=period.start_date,
    ).select_related('employee', 'employee__user')

    for lr in pending_leaves:
        u = lr.employee.user
        emp_name = f"{u.first_name} {u.last_name}".strip() or u.email
        exceptions.append({
            'type': 'PENDING_LEAVE',
            'severity': 'medium',
            'employee_id': lr.employee.id,
            'employee_code': lr.employee.employee_code,
            'employee_name': emp_name,
            'message': f"Pending leave request from {lr.start_date} to {lr.end_date} for {lr.employee.employee_code} ({emp_name}) overlaps this pay period.",
        })

    # 5. ATTENDANCE_INCOMPLETE (check_in without check_out)
    incomplete_att = Attendance.objects.filter(
        employee__organization=period.organization,
        date__range=[period.start_date, period.end_date],
        check_in__isnull=False,
        check_out__isnull=True,
    ).select_related('employee', 'employee__user')

    for att in incomplete_att:
        u = att.employee.user
        emp_name = f"{u.first_name} {u.last_name}".strip() or u.email
        exceptions.append({
            'type': 'ATTENDANCE_INCOMPLETE',
            'severity': 'low',
            'employee_id': att.employee.id,
            'employee_code': att.employee.employee_code,
            'employee_name': emp_name,
            'message': f"Missing clock-out on {att.date} for {att.employee.employee_code} ({emp_name}).",
        })

    return exceptions
