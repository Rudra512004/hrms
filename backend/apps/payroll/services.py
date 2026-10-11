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
from django.db.models import Q
from django.utils import timezone

from apps.attendance.models import Attendance, Holiday
from apps.leaves.models import LeaveRequest
from .models import CompensationHistory, FinalSettlement, PayrollPeriod, PayrollRecord, Payslip, PayslipLine
from .currency_utils import amount_to_words_inr
import hashlib
import uuid
import logging
from apps.audit.services import AuditService

logger = logging.getLogger(__name__)


def _working_days_in_period(branch_id: int, start: date, end: date) -> int:
    """
    Count working days within [start, end] that are not branch holidays or recurring off-days.
    Uses WorkingCalendarService as the authoritative evaluation engine.
    """
    if not branch_id:
        return 0

    from apps.organization.models import Branch
    from apps.organization.services import WorkingCalendarService
    branch = Branch.objects.get(id=branch_id)
    return WorkingCalendarService.count_working_days(branch, start, end)



def _get_active_salary(employee, period_start: date, period_end: date = None) -> Decimal:
    """
    Return the basic_salary that was active at the start of the period,
    or during the period.
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
        # Fallback: check if any record was active as of period_start with an effective_to date
        record = (
            CompensationHistory.objects.filter(
                employee=employee,
                effective_from__lte=period_start,
                effective_to__gte=period_start,
            )
            .order_by('-effective_from')
            .first()
        )
    if record is None and period_end:
        # Fallback: check if a compensation record became effective during the period
        record = (
            CompensationHistory.objects.filter(
                employee=employee,
                effective_from__lte=period_end,
            )
            .filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=period_start)
            )
            .order_by('-effective_from')
            .first()
        )
    if record is None:
        # Fallback: most recent compensation record
        record = (
            CompensationHistory.objects.filter(
                employee=employee,
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


def _approved_leave_days(employee, start: date, end: date, exclude_dates: set = None) -> int:
    """
    Count distinct working days of approved LeaveRequests overlapping the pay period.
    Excludes weekends, recurring off-days, and holidays via WorkingCalendarService.
    Deduplicates overlapping requests and excludes dates already accounted for by attendance (exclude_dates).
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
        return 0

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
                    raise WorkingCalendarConfigurationError("Branch is required to determine leave duration.")
                if WorkingCalendarService.is_working_day(branch, current):
                    leave_dates.add(current)
            current += timedelta(days=1)
    return len(leave_dates)



def generate_payroll_for_period(period: PayrollPeriod, requesting_user=None) -> list:
    """
    Generate PayrollRecord for every active employee in the organization.
    Must be called inside a transaction (callers wrap it).
    Returns the list of created/updated PayrollRecord instances.

    Raises ValueError if the period is already approved.
    """
    if period.status == PayrollPeriod.STATUS_FINALIZED:
        raise ValueError("Cannot re-generate a finalized payroll period.")

    from apps.employees.models import Employee, EmploymentStatus

    # Delete any previous draft records for this period (re-generation allowed)
    PayrollRecord.objects.filter(period=period, status=PayrollRecord.STATUS_DRAFT).delete()

    employees = Employee.objects.filter(
        organization=period.organization,
        employment_status__in=[EmploymentStatus.ACTIVE, EmploymentStatus.ON_NOTICE],
    ).filter(
        Q(exit_date__isnull=True) | Q(exit_date__gte=period.start_date)
    ).select_related('organization', 'user')

    records = []

    for emp in employees:
        # Safeguard: Check if employee's salary for this period or prior period was already settled in an approved/finalized FnF
        has_prior_finalized_fnf = FinalSettlement.objects.filter(
            organization=period.organization,
            employee=emp,
            status__in=[FinalSettlement.STATUS_APPROVED, FinalSettlement.STATUS_FINALIZED],
            exit_date__lt=period.start_date,
        ).exists()
        if has_prior_finalized_fnf:
            logger.info(
                f"Skipping payroll generation for employee {emp.employee_code}: "
                f"Employee has an approved/finalized FnF settlement with exit date prior to period start date."
            )
            continue

        has_period_finalized_salary_lwd = FinalSettlement.objects.filter(
            organization=period.organization,
            employee=emp,
            status__in=[FinalSettlement.STATUS_APPROVED, FinalSettlement.STATUS_FINALIZED],
            lines__code='SALARY_LWD',
            lines__source_reference=f"{period.year}-{period.month:02d}",
        ).exists()
        if has_period_finalized_salary_lwd:
            logger.info(
                f"Skipping payroll generation for employee {emp.employee_code}: "
                f"Salary for {period.year}-{period.month:02d} was already settled in finalized FnF."
            )
            continue

        working_days = _working_days_in_period(
            emp.branch_id, period.start_date, period.end_date
        )
        basic_salary = _get_active_salary(emp, period.start_date, period.end_date)
        att = _attendance_summary(emp, period.start_date, period.end_date)

        # Dates already accounted for by present attendance to prevent double-counting with approved leave
        present_dates = set(
            Attendance.objects.filter(
                employee=emp,
                date__range=[period.start_date, period.end_date],
                status='present',
            ).values_list('date', flat=True)
        )
        leave_days = _approved_leave_days(
            emp, period.start_date, period.end_date, exclude_dates=present_dates
        )

        present = att['present']
        half = att['half']
        # Effective paid days: full present + half_days * 0.5 + approved leave
        calculated_effective = Decimal(present) + Decimal(half) * Decimal('0.5') + Decimal(leave_days)
        # Cap effective days at working days to avoid unbudgeted overpayment
        effective_days = min(Decimal(working_days), calculated_effective) if working_days > 0 else Decimal('0.00')

        if working_days > 0:
            gross = (basic_salary * effective_days / Decimal(working_days)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        else:
            gross = Decimal('0.00')

        absent_days = max(0, working_days - int(effective_days))

        # P6.9C Authoritative Progressive TDS Calculation
        tds_amount = Decimal('0.00')
        tax_snapshot = {}
        try:
            from apps.payroll.tax_calculator import TaxCalculationService
            tax_res = TaxCalculationService.calculate_monthly_tds(
                employee=emp,
                period=period,
                current_gross=gross,
            )
            tds_amount = tax_res['monthly_tds']
            tax_snapshot = tax_res['snapshot']
        except Exception as e:
            # If no financial year or tax rule configuration is configured, default safely to 0 TDS
            logger.info(f"Tax calculation bypassed for employee {emp.employee_code}: {str(e)}")
            tds_amount = Decimal('0.00')
            tax_snapshot = {'status': 'bypassed', 'reason': str(e)}

        net = max(Decimal('0.00'), gross - tds_amount)

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
            tds_amount=tds_amount,
            net_salary=net,
            tax_calculation_snapshot=tax_snapshot,
            status=PayrollRecord.STATUS_DRAFT,
        )
        records.append(record)

    PayrollRecord.objects.bulk_create(records)

    period.generated_at = timezone.now()
    period.save(update_fields=['generated_at'])

    return records


def compute_payslip_integrity_hash(
    payslip_number: str,
    employee_code: str,
    period_str: str,
    gross: Decimal,
    net: Decimal,
    token: str,
) -> str:
    """
    Computes a deterministic SHA-256 integrity hash over canonical financial fields.
    """
    payload = f"{payslip_number}|{employee_code}|{period_str}|{gross:.2f}|{net:.2f}|{token}"
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def issue_payslips_for_period(period: PayrollPeriod, requesting_user=None) -> list:
    """
    Atomically and idempotently issues Payslips for each finalized PayrollRecord in the period.
    Snapshots all organization, employee, attendance, and financial data into the Payslip
    and creates normalized PayslipLine records.
    Raises ValueError if period is not finalized.
    """
    if period.status != PayrollPeriod.STATUS_FINALIZED:
        raise ValueError("Cannot issue payslips for an unfinalized period.")

    records = period.records.filter(status=PayrollRecord.STATUS_FINALIZED).select_related(
        'employee', 'employee__user', 'employee__department', 'employee__designation',
        'employee__branch', 'period', 'period__organization'
    )
    payslips = []
    from apps.notifications.services import NotificationService

    with transaction.atomic():
        for record in records:
            emp = record.employee
            u = emp.user
            emp_code = emp.employee_code.strip()
            num = f"PAY-{period.year}{period.month:02d}-{emp_code}"

            existing = Payslip.objects.filter(payroll_record=record).first()
            if existing:
                payslips.append(existing)
                continue

            # Organization snapshot
            org = period.organization
            branch = emp.branch
            org_name = org.name
            legal_name = org_name
            cin = ""
            branch_name = branch.name if branch else ""
            branch_address = (
                f"{branch.address_line1}, {branch.city}, {branch.state} {branch.postal_code}".strip(", ")
                if branch and branch.address_line1 else ""
            )
            org_address = branch_address

            # Employee snapshot
            emp_name = f"{u.first_name} {u.last_name}".strip() or u.email
            dept_name = emp.department.name if emp.department else ""
            desig_name = emp.designation.name if emp.designation else ""
            joining_date = emp.joining_date

            bank_name = ""
            masked_bank_acc = ""
            bank_ifsc = ""
            payment_mode = "BANK_TRANSFER"
            masked_pan = ""
            uan_num = ""
            esic_num = ""

            if hasattr(emp, 'statutory_and_bank') and emp.statutory_and_bank:
                sb = emp.statutory_and_bank
                bank_name = sb.bank_name or ""
                if sb.account_number:
                    raw_acc = sb.account_number.strip()
                    masked_bank_acc = f"{'•' * max(0, len(raw_acc) - 4)}{raw_acc[-4:]}" if len(raw_acc) >= 4 else raw_acc
                bank_ifsc = sb.ifsc_code or ""
                payment_mode = sb.payment_mode or "BANK_TRANSFER"
                if sb.pan_number:
                    raw_pan = sb.pan_number.strip()
                    masked_pan = f"{'•' * max(0, len(raw_pan) - 4)}{raw_pan[-4:]}" if len(raw_pan) >= 4 else raw_pan
                uan_num = sb.uan_number or ""
                esic_num = sb.esic_number or ""

            # Attendance snapshot
            cal_days = (period.end_date - period.start_date).days + 1
            work_days = record.working_days
            pres_days = Decimal(record.present_days)
            half_days = record.half_days
            absent_days = record.absent_days
            leave_days = Decimal(record.leave_days)
            eff_days = record.effective_days
            lop_days = record.lop_days

            # Financial snapshot
            basic = record.basic_salary
            gross = record.gross_salary
            deductions = record.tds_amount or Decimal('0.00')
            net = record.net_salary
            words = amount_to_words_inr(net)

            # Security & verification
            token = uuid.uuid4()
            period_label = f"{period.year}/{period.month:02d}"
            hash_val = compute_payslip_integrity_hash(num, emp_code, period_label, gross, net, str(token))

            payslip = Payslip.objects.create(
                payroll_record=record,
                payslip_number=num,
                status=Payslip.STATUS_ISSUED,
                issued_by=requesting_user,
                verification_token=token,
                integrity_hash=hash_val,
                organization_name=org_name,
                legal_name=legal_name,
                organization_address=org_address,
                cin=cin,
                branch_name=branch_name,
                branch_address=branch_address,
                employee_code=emp_code,
                employee_name=emp_name,
                department_name=dept_name,
                designation_name=desig_name,
                joining_date=joining_date,
                bank_name=bank_name,
                masked_bank_account=masked_bank_acc,
                bank_ifsc=bank_ifsc,
                payment_mode=payment_mode,
                masked_pan=masked_pan,
                uan=uan_num,
                esic_number=esic_num,
                period_year=period.year,
                period_month=period.month,
                period_start_date=period.start_date,
                period_end_date=period.end_date,
                calendar_days=cal_days,
                working_days=work_days,
                present_days=pres_days,
                half_days=half_days,
                absent_days=absent_days,
                leave_days=leave_days,
                effective_days=eff_days,
                lop_days=lop_days,
                basic_salary=basic,
                gross_earnings=gross,
                total_deductions=deductions,
                net_pay=net,
                net_pay_in_words=words,
            )

            # Normalized earning line item
            PayslipLine.objects.create(
                payslip=payslip,
                category=PayslipLine.CATEGORY_EARNING,
                component_code='BASIC',
                name='Basic Salary',
                amount=gross,
                order=1,
                metadata={'basic_rate': str(basic), 'effective_days': str(eff_days)}
            )

            # Normalized deduction line item for TDS
            if record.tds_amount and record.tds_amount > Decimal('0.00'):
                PayslipLine.objects.create(
                    payslip=payslip,
                    category=PayslipLine.CATEGORY_DEDUCTION,
                    component_code='TDS',
                    name='Income Tax (TDS)',
                    amount=record.tds_amount,
                    order=10,
                    metadata=record.tax_calculation_snapshot or {}
                )

            payslips.append(payslip)

            AuditService.log(
                action='PAYSLIP_ISSUED',
                actor=requesting_user,
                target_type='Payslip',
                target_id=payslip.id,
                organization=period.organization,
            )

            transaction.on_commit(lambda p=payslip, r=record, num=num: NotificationService.create_in_app_notification(
                recipient=r.employee.user,
                organization=r.employee.organization,
                notification_type='PAYSLIP_ISSUED',
                title='Payslip Issued',
                message=f'Your payslip {num} for {r.period.year}-{r.period.month:02d} has been issued.',
                reference_id=str(p.id)
            ))

    return payslips
