import hashlib
import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any, Optional

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.employees.models import Employee, EmploymentStatus
from apps.payroll.models import (
    CompensationHistory,
    PayrollPeriod,
    PayrollRecord,
    DisbursementBatch,
    FnFPolicyConfiguration,
    FinalSettlement,
    SettlementLine,
)
from apps.payroll.services import (
    _get_active_salary,
    _working_days_in_period,
    _attendance_summary,
    _approved_leave_days,
)
from apps.audit.services import AuditService

logger = logging.getLogger(__name__)


class FnFException(Exception):
    def __init__(self, message: str, code: str = 'FNF_ERROR'):
        super().__init__(message)
        self.message = message
        self.code = code


def mask_sensitive_value(val: str, visible_suffix_len: int = 4) -> str:
    if not val:
        return ""
    val = str(val).strip()
    if len(val) <= visible_suffix_len:
        return val
    return f"{'•' * (len(val) - visible_suffix_len)}{val[-visible_suffix_len:]}"


def get_effective_fnf_policy(
    organization, branch=None, as_of_date: Optional[date] = None
) -> Optional[FnFPolicyConfiguration]:
    """
    Finds the active, effective FnFPolicyConfiguration for an organization and optional branch.
    Follows established effective-dated configuration pattern.
    """
    if as_of_date is None:
        as_of_date = timezone.now().date()

    qs = FnFPolicyConfiguration.objects.filter(
        organization=organization,
        is_active=True,
        effective_from__lte=as_of_date,
    )
    if branch:
        branch_cfg = qs.filter(branch=branch).order_by('-effective_from', '-created_at').first()
        if branch_cfg:
            return branch_cfg

    return qs.filter(branch__isnull=True).order_by('-effective_from', '-created_at').first()


def validate_fnf_eligibility(employee: Employee, exit_date: Optional[date] = None) -> date:
    """
    Validates that the employee is eligible for Full & Final settlement:
    1. Must have an approved exit state (status ON_NOTICE/EXITED or lifecycle event).
    2. Must have an authoritative last working day (exit_date).
    3. Exit dates must be logically valid.
    4. Must not have an active non-cancelled settlement already in progress.
    """
    # 1. Approved exit state
    is_notice_or_exited = employee.employment_status in [
        EmploymentStatus.ON_NOTICE,
        EmploymentStatus.EXITED,
    ]
    has_lifecycle_exit = employee.lifecycle_events.filter(
        event_type__in=['resignation', 'exit']
    ).exists()

    if not (is_notice_or_exited or has_lifecycle_exit):
        raise FnFException(
            f"Employee {employee.employee_code} has no approved exit or resignation record.",
            code="NO_APPROVED_EXIT",
        )

    # 2. Authoritative Last Working Day
    lwd = exit_date or employee.exit_date
    if not lwd:
        raise FnFException(
            f"Employee {employee.employee_code} has no recorded last working day / exit date.",
            code="MISSING_LAST_WORKING_DAY",
        )

    # 3. Date sanity check
    if employee.joining_date and lwd < employee.joining_date:
        raise FnFException(
            f"Exit date ({lwd}) cannot be before employee joining date ({employee.joining_date}).",
            code="INVALID_EXIT_DATE",
        )

    if employee.resignation_date and lwd < employee.resignation_date:
        raise FnFException(
            f"Exit date ({lwd}) cannot be before resignation date ({employee.resignation_date}).",
            code="INVALID_EXIT_DATE",
        )

    # 4. Duplicate active settlement prevention
    active_settlement = (
        FinalSettlement.objects.filter(
            employee=employee,
            organization=employee.organization,
        )
        .exclude(status=FinalSettlement.STATUS_CANCELLED)
        .first()
    )
    if active_settlement:
        raise FnFException(
            f"An active FnF settlement ({active_settlement.settlement_number}) already exists for employee {employee.employee_code}.",
            code="DUPLICATE_ACTIVE_SETTLEMENT",
        )

    return lwd


def calculate_fnf_settlement(
    employee: Employee,
    exit_date: Optional[date] = None,
    settlement_date: Optional[date] = None,
    asset_recoveries: Optional[List[Dict[str, Any]]] = None,
    loan_recoveries: Optional[List[Dict[str, Any]]] = None,
    bonus_amount: Optional[Decimal] = None,
    bonus_remarks: str = "",
    joining_bonus_clawback: Optional[Dict[str, Any]] = None,
    tds_amount: Optional[Decimal] = None,
    remarks: str = "",
) -> Dict[str, Any]:
    """
    Computes all settlement lines for Full & Final Settlement without persisting:
    - Prorated salary through LWD (reusing authoritative payroll logic and checking regular payroll)
    - Leave encashment based on policy and real balance
    - Gratuity based on tenure and policy
    - Approved bonus
    - Notice period shortfall recovery
    - Asset recovery (checked against assigned assets)
    - Loan/advance recovery (approved items)
    - Joining bonus clawback (approved items/policy)
    - Statutory (EPF, ESIC, PT) & Tax deductions
    """
    lwd = validate_fnf_eligibility(employee, exit_date=exit_date)
    settlement_date = settlement_date or timezone.now().date()
    policy = get_effective_fnf_policy(employee.organization, employee.branch, as_of_date=lwd)

    lines: List[Dict[str, Any]] = []
    order = 1

    # =========================================================================
    # 1. SALARY THROUGH LAST WORKING DAY
    # =========================================================================
    exit_month_start = date(lwd.year, lwd.month, 1)
    if lwd.month == 12:
        next_month_start = date(lwd.year + 1, 1, 1)
    else:
        next_month_start = date(lwd.year, lwd.month + 1, 1)
    exit_month_end = next_month_start - timedelta(days=1)

    total_month_working_days = _working_days_in_period(
        employee.branch_id, exit_month_start, exit_month_end
    )
    lwd_working_days = _working_days_in_period(
        employee.branch_id, exit_month_start, lwd
    )

    basic_salary = _get_active_salary(employee, lwd, lwd)
    if basic_salary == Decimal('0.00'):
        basic_salary = _get_active_salary(employee, exit_month_start, lwd)
    att = _attendance_summary(employee, exit_month_start, lwd)

    from apps.attendance.models import Attendance
    present_dates = set(
        Attendance.objects.filter(
            employee=employee,
            date__range=[exit_month_start, lwd],
            status='present',
        ).values_list('date', flat=True)
    )
    leave_days = _approved_leave_days(
        employee, exit_month_start, lwd, exclude_dates=present_dates
    )

    present = att['present']
    half = att['half']
    calculated_effective = Decimal(present) + Decimal(half) * Decimal('0.5') + Decimal(leave_days)
    effective_days = (
        min(Decimal(lwd_working_days), calculated_effective)
        if lwd_working_days > 0
        else Decimal('0.00')
    )
    lop_days = max(Decimal('0.0'), Decimal(lwd_working_days) - effective_days)

    if total_month_working_days > 0:
        gross_salary_lwd = (
            basic_salary * effective_days / Decimal(total_month_working_days)
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        gross_salary_lwd = Decimal('0.00')

    # Guard against double payment: check if a regular payroll record was already approved/finalized,
    # or actively queued/exported in a disbursement batch for this month
    already_accounted_record = (
        PayrollRecord.objects.filter(
            employee=employee,
            period__organization=employee.organization,
            period__year=lwd.year,
            period__month=lwd.month,
        )
        .filter(
            Q(period__status__in=[PayrollPeriod.STATUS_FINALIZED, PayrollPeriod.STATUS_LOCKED, PayrollPeriod.STATUS_DISBURSED])
            | Q(
                disbursement_items__batch__status__in=[
                    DisbursementBatch.STATUS_DRAFT,
                    DisbursementBatch.STATUS_APPROVED,
                    DisbursementBatch.STATUS_EXPORTED,
                ]
            )
        )
        .select_related('period')
        .distinct()
        .first()
    )

    already_paid_salary = Decimal('0.00')
    if already_accounted_record:
        already_paid_salary = already_accounted_record.gross_salary
        net_salary_lwd = max(Decimal('0.00'), gross_salary_lwd - already_paid_salary)
        basis_explanation = (
            f"Basic: ₹{basic_salary}. Effective: {effective_days}/{total_month_working_days} days "
            f"(Prorated: ₹{gross_salary_lwd}). Less already paid in regular payroll period "
            f"{already_accounted_record.period.year}/{already_accounted_record.period.month:02d}: ₹{already_paid_salary}."
        )
    else:
        net_salary_lwd = gross_salary_lwd
        basis_explanation = (
            f"Basic: ₹{basic_salary}. Effective: {effective_days}/{total_month_working_days} working days "
            f"in month ({lwd_working_days} scheduled days to LWD, LOP: {lop_days} days)."
        )

    lines.append({
        'category': SettlementLine.CATEGORY_EARNING,
        'code': 'SALARY_LWD',
        'name': 'Salary through Last Working Day',
        'amount': net_salary_lwd,
        'calculation_basis': basis_explanation,
        'source_reference': f"{lwd.year}-{lwd.month:02d}",
        'order': order,
        'metadata': {
            'basic_salary': str(basic_salary),
            'total_month_working_days': total_month_working_days,
            'lwd_working_days': lwd_working_days,
            'present_days': present,
            'half_days': half,
            'leave_days': leave_days,
            'effective_days': str(effective_days),
            'lop_days': str(lop_days),
            'gross_earned': str(gross_salary_lwd),
            'already_paid_regular_payroll': str(already_paid_salary),
        },
    })
    order += 1

    # =========================================================================
    # 2. LEAVE ENCASHMENT
    # =========================================================================
    if policy and policy.leave_encashment_enabled:
        divisor = policy.leave_encashment_daily_divisor or 30
        eligible_leave_codes = policy.encashable_leave_types or []

        from apps.leaves.models import LeaveBalance
        balances = LeaveBalance.objects.filter(employee=employee).select_related('leave_type')

        for b in balances:
            lt_code = b.leave_type.code or b.leave_type.name
            is_eligible = (not eligible_leave_codes) or (
                lt_code in eligible_leave_codes or b.leave_type.name in eligible_leave_codes
            )
            if is_eligible and b.remaining > 0:
                daily_rate = (basic_salary / Decimal(divisor)).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                encash_amount = (b.remaining * daily_rate).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                lines.append({
                    'category': SettlementLine.CATEGORY_EARNING,
                    'code': f'LEAVE_ENCASHMENT_{b.leave_type.code or b.leave_type.id}',
                    'name': f'Leave Encashment ({b.leave_type.name})',
                    'amount': encash_amount,
                    'calculation_basis': (
                        f"{b.remaining} remaining balance days @ ₹{daily_rate}/day (Divisor: {divisor})"
                    ),
                    'source_reference': b.leave_type.code or str(b.leave_type.id),
                    'order': order,
                    'metadata': {
                        'leave_type_id': b.leave_type.id,
                        'leave_type_name': b.leave_type.name,
                        'remaining_days': str(b.remaining),
                        'daily_rate': str(daily_rate),
                        'divisor': divisor,
                    },
                })
                order += 1

    # =========================================================================
    # 3. GRATUITY
    # =========================================================================
    if policy and policy.gratuity_enabled:
        if employee.joining_date:
            tenure_days = (lwd - employee.joining_date).days
            service_years = Decimal(str(round(tenure_days / 365.25, 2)))
            if service_years >= policy.gratuity_min_service_years:
                completed_years = int(service_years)
                gratuity_amount = (
                    (basic_salary * Decimal(policy.gratuity_wage_days_per_year) * Decimal(completed_years))
                    / Decimal(policy.gratuity_divisor)
                ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                if policy.gratuity_max_ceiling and gratuity_amount > policy.gratuity_max_ceiling:
                    gratuity_amount = policy.gratuity_max_ceiling

                lines.append({
                    'category': SettlementLine.CATEGORY_EARNING,
                    'code': 'GRATUITY',
                    'name': 'Gratuity',
                    'amount': gratuity_amount,
                    'calculation_basis': (
                        f"Tenure: {service_years} yrs ({completed_years} completed yrs). Formula: "
                        f"(₹{basic_salary} * {policy.gratuity_wage_days_per_year} * {completed_years}) "
                        f"/ {policy.gratuity_divisor}"
                    ),
                    'source_reference': 'GRATUITY_POLICY',
                    'order': order,
                    'metadata': {
                        'tenure_years': str(service_years),
                        'completed_years': completed_years,
                        'min_service_years': str(policy.gratuity_min_service_years),
                        'wage_days_per_year': policy.gratuity_wage_days_per_year,
                        'divisor': policy.gratuity_divisor,
                        'ceiling': str(policy.gratuity_max_ceiling) if policy.gratuity_max_ceiling else None,
                    },
                })
                order += 1

    # =========================================================================
    # 4. BONUS
    # =========================================================================
    if bonus_amount and Decimal(str(bonus_amount)) > Decimal('0.00'):
        bonus_val = Decimal(str(bonus_amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        lines.append({
            'category': SettlementLine.CATEGORY_EARNING,
            'code': 'BONUS',
            'name': 'Approved Settlement Bonus',
            'amount': bonus_val,
            'calculation_basis': bonus_remarks or 'Approved discretionary / performance bonus',
            'source_reference': 'BONUS_APPROVAL',
            'order': order,
            'metadata': {'remarks': bonus_remarks},
        })
        order += 1

    # =========================================================================
    # 5. NOTICE PERIOD RECOVERY
    # =========================================================================
    required_notice = employee.notice_period_days
    if not required_notice and employee.notice_period_start and employee.notice_period_end:
        required_notice = (employee.notice_period_end - employee.notice_period_start).days

    if required_notice and required_notice > 0 and (not policy or policy.notice_recovery_enabled):
        notice_start = employee.notice_period_start or employee.resignation_date or lwd
        served_notice = max(0, (lwd - notice_start).days) if lwd >= notice_start else 0
        shortfall_days = max(0, required_notice - served_notice)

        if shortfall_days > 0:
            divisor = (policy.notice_recovery_daily_divisor if policy else 30) or 30
            daily_rate = (basic_salary / Decimal(divisor)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            recovery_amount = (Decimal(shortfall_days) * daily_rate).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

            lines.append({
                'category': SettlementLine.CATEGORY_RECOVERY,
                'code': 'NOTICE_RECOVERY',
                'name': 'Notice Period Shortfall Recovery',
                'amount': recovery_amount,
                'calculation_basis': (
                    f"Required: {required_notice} days, Served: {served_notice} days. "
                    f"Shortfall: {shortfall_days} days @ ₹{daily_rate}/day (Divisor: {divisor})"
                ),
                'source_reference': 'NOTICE_SHORTFALL',
                'order': order,
                'metadata': {
                    'required_notice_days': required_notice,
                    'served_notice_days': served_notice,
                    'shortfall_days': shortfall_days,
                    'daily_rate': str(daily_rate),
                    'divisor': divisor,
                },
            })
            order += 1

    # =========================================================================
    # 6. ASSET RECOVERY
    # =========================================================================
    if asset_recoveries:
        from apps.assets.models import AssetAssignment
        for item in asset_recoveries:
            asset_id = item.get('asset_id')
            amt = Decimal(str(item.get('amount', '0.00'))).quantize(Decimal('0.01'))
            reason = item.get('reason', 'Approved asset damage / unreturned recovery')

            assignment = (
                AssetAssignment.objects.filter(
                    employee=employee,
                    asset_id=asset_id,
                    is_active=True,
                )
                .select_related('asset')
                .first()
            )
            if not assignment:
                raise FnFException(
                    f"Asset ID {asset_id} is not actively assigned to employee {employee.employee_code}.",
                    code="INVALID_ASSET_RECOVERY",
                )

            asset = assignment.asset
            lines.append({
                'category': SettlementLine.CATEGORY_RECOVERY,
                'code': f'ASSET_RECOVERY_{asset.asset_tag}',
                'name': f'Asset Recovery ({asset.name})',
                'amount': amt,
                'calculation_basis': reason,
                'source_reference': asset.asset_tag,
                'order': order,
                'metadata': {
                    'asset_id': asset.id,
                    'asset_tag': asset.asset_tag,
                    'reason': reason,
                },
            })
            order += 1

    # =========================================================================
    # 7. LOAN / ADVANCE RECOVERY
    # =========================================================================
    if loan_recoveries:
        for item in loan_recoveries:
            amt = Decimal(str(item.get('amount', '0.00'))).quantize(Decimal('0.01'))
            rec_type = item.get('type', 'loan').lower()
            code = 'ADVANCE_RECOVERY' if 'advance' in rec_type else 'LOAN_RECOVERY'
            name = item.get('name', 'Outstanding Loan Recovery' if code == 'LOAN_RECOVERY' else 'Salary Advance Recovery')
            ref = item.get('reference', '')
            reason = item.get('reason', 'Approved outstanding loan/advance recovery')

            lines.append({
                'category': SettlementLine.CATEGORY_RECOVERY,
                'code': code,
                'name': name,
                'amount': amt,
                'calculation_basis': reason,
                'source_reference': ref,
                'order': order,
                'metadata': {'reference': ref, 'reason': reason},
            })
            order += 1

    # =========================================================================
    # 8. JOINING BONUS CLAWBACK
    # =========================================================================
    if joining_bonus_clawback:
        amt = Decimal(str(joining_bonus_clawback.get('amount', '0.00'))).quantize(Decimal('0.01'))
        reason = joining_bonus_clawback.get('reason', 'Joining bonus retention clawback')
        if amt > Decimal('0.00'):
            lines.append({
                'category': SettlementLine.CATEGORY_RECOVERY,
                'code': 'JOINING_BONUS_CLAWBACK',
                'name': 'Joining Bonus Clawback',
                'amount': amt,
                'calculation_basis': reason,
                'source_reference': 'CLAWBACK_OBLIGATION',
                'order': order,
                'metadata': {'reason': reason},
            })
            order += 1

    # =========================================================================
    # 9. STATUTORY & TAX DEDUCTIONS
    # =========================================================================
    if hasattr(employee, 'statutory_and_bank') and employee.statutory_and_bank:
        sb = employee.statutory_and_bank

        # EPF
        if sb.is_epf_applicable and net_salary_lwd > Decimal('0.00'):
            epf_wage = net_salary_lwd
            if sb.restrict_epf_to_ceiling and basic_salary > Decimal('15000.00'):
                prorated_ceiling = (
                    (Decimal('15000.00') * effective_days / Decimal(total_month_working_days)).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    )
                    if total_month_working_days > 0
                    else Decimal('15000.00')
                )
                epf_wage = min(net_salary_lwd, prorated_ceiling)

            epf_deduction = (epf_wage * Decimal('0.12')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            lines.append({
                'category': SettlementLine.CATEGORY_DEDUCTION,
                'code': 'STAT_EPF',
                'name': 'Provident Fund (EPF)',
                'amount': epf_deduction,
                'calculation_basis': f"12% of eligible wage ₹{epf_wage}",
                'source_reference': 'STAT_EPF',
                'order': order,
                'metadata': {'wage': str(epf_wage)},
            })
            order += 1

        # ESIC
        if sb.is_esic_applicable and net_salary_lwd > Decimal('0.00'):
            esic_deduction = (net_salary_lwd * Decimal('0.0075')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            lines.append({
                'category': SettlementLine.CATEGORY_DEDUCTION,
                'code': 'STAT_ESIC',
                'name': 'Employee State Insurance (ESIC)',
                'amount': esic_deduction,
                'calculation_basis': f"0.75% of gross salary ₹{net_salary_lwd}",
                'source_reference': 'STAT_ESIC',
                'order': order,
                'metadata': {'wage': str(net_salary_lwd)},
            })
            order += 1

        # PT
        if sb.is_pt_applicable and net_salary_lwd > Decimal('0.00'):
            pt_deduction = Decimal('200.00')
            lines.append({
                'category': SettlementLine.CATEGORY_DEDUCTION,
                'code': 'STAT_PT',
                'name': 'Professional Tax (PT)',
                'amount': pt_deduction,
                'calculation_basis': 'Standard professional tax slab deduction',
                'source_reference': 'STAT_PT',
                'order': order,
                'metadata': {'amount': '200.00'},
            })
            order += 1

    # TDS
    if tds_amount and Decimal(str(tds_amount)) > Decimal('0.00'):
        tds_val = Decimal(str(tds_amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        lines.append({
            'category': SettlementLine.CATEGORY_DEDUCTION,
            'code': 'TAX_TDS',
            'name': 'Tax Deducted at Source (TDS)',
            'amount': tds_val,
            'calculation_basis': 'Approved tax deduction at source',
            'source_reference': 'TAX_TDS',
            'order': order,
            'metadata': {'amount': str(tds_val)},
        })
        order += 1

    # =========================================================================
    # 10. TOTALS & NET CALCULATION
    # =========================================================================
    total_earnings = sum(
        (l['amount'] for l in lines if l['category'] == SettlementLine.CATEGORY_EARNING),
        Decimal('0.00'),
    )
    total_deductions = sum(
        (l['amount'] for l in lines if l['category'] == SettlementLine.CATEGORY_DEDUCTION),
        Decimal('0.00'),
    )
    total_recoveries = sum(
        (l['amount'] for l in lines if l['category'] == SettlementLine.CATEGORY_RECOVERY),
        Decimal('0.00'),
    )
    net_settlement_amount = total_earnings - total_deductions - total_recoveries

    # Immutable Snapshot dict
    user = employee.user
    sb = getattr(employee, 'statutory_and_bank', None)
    branch = employee.branch

    snapshot_data = {
        'employee': {
            'id': employee.id,
            'employee_code': employee.employee_code,
            'name': f"{user.first_name} {user.last_name}".strip() or user.email,
            'email': user.email,
            'joining_date': str(employee.joining_date) if employee.joining_date else None,
            'exit_date': str(lwd),
            'resignation_date': str(employee.resignation_date) if employee.resignation_date else None,
            'department': employee.department.name if employee.department else None,
            'designation': employee.designation.name if employee.designation else None,
            'masked_pan': mask_sensitive_value(sb.pan_number, 4) if (sb and sb.pan_number) else None,
            'masked_account': mask_sensitive_value(sb.account_number, 4) if (sb and sb.account_number) else None,
            'bank_name': sb.bank_name if sb else None,
            'ifsc': sb.ifsc_code if sb else None,
        },
        'organization': {
            'id': employee.organization_id,
            'name': employee.organization.name,
            'branch': branch.name if branch else None,
        },
        'policy': {
            'id': policy.id if policy else None,
            'effective_from': str(policy.effective_from) if policy else None,
            'leave_encashment_enabled': policy.leave_encashment_enabled if policy else False,
            'gratuity_enabled': policy.gratuity_enabled if policy else False,
            'notice_recovery_enabled': policy.notice_recovery_enabled if policy else False,
        },
        'attendance_and_proration': {
            'basic_salary': str(basic_salary),
            'total_month_working_days': total_month_working_days,
            'lwd_working_days': lwd_working_days,
            'present_days': present,
            'half_days': half,
            'leave_days': leave_days,
            'effective_days': str(effective_days),
            'lop_days': str(lop_days),
        },
        'lines': [
            {
                'category': l['category'],
                'code': l['code'],
                'name': l['name'],
                'amount': str(l['amount']),
                'calculation_basis': l['calculation_basis'],
                'source_reference': l['source_reference'],
            }
            for l in lines
        ],
        'totals': {
            'total_earnings': str(total_earnings),
            'total_deductions': str(total_deductions),
            'total_recoveries': str(total_recoveries),
            'net_settlement_amount': str(net_settlement_amount),
        },
        'settlement_date': str(settlement_date),
    }

    return {
        'lines': lines,
        'total_earnings': total_earnings,
        'total_deductions': total_deductions,
        'total_recoveries': total_recoveries,
        'net_settlement_amount': net_settlement_amount,
        'exit_date': lwd,
        'resignation_date': employee.resignation_date,
        'settlement_date': settlement_date,
        'snapshot_data': snapshot_data,
        'remarks': remarks,
    }


def compute_settlement_integrity_hash(
    settlement_number: str,
    employee_code: str,
    net_amount: Decimal,
    total_earnings: Decimal,
    total_deductions: Decimal,
    total_recoveries: Decimal,
    lines_summary: str,
) -> str:
    """Computes a deterministic SHA-256 integrity hash across canonical settlement fields."""
    payload = (
        f"{settlement_number}|{employee_code}|{net_amount:.2f}|{total_earnings:.2f}|"
        f"{total_deductions:.2f}|{total_recoveries:.2f}|{lines_summary}"
    )
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


class FnFService:
    """
    Orchestration service for Full & Final Settlement (FnF).
    """

    @staticmethod
    def calculate_settlement_preview(employee, exit_date=None, **kwargs) -> Dict[str, Any]:
        """Calculates settlement preview for an employee instance."""
        resignation_date = kwargs.pop('resignation_date', None)
        if resignation_date:
            employee.resignation_date = resignation_date
        return calculate_fnf_settlement(employee, exit_date=exit_date, **kwargs)

    @staticmethod
    def preview(employee_id: int, requesting_user, **kwargs) -> Dict[str, Any]:
        """Calculates settlement preview without modifying database state."""
        org = requesting_user.employee.organization if hasattr(requesting_user, 'employee') and requesting_user.employee else None
        if not org:
            from apps.authorization.services import AuthorizationService
            org = AuthorizationService.get_primary_organization(requesting_user)

        try:
            employee = Employee.objects.get(id=employee_id, organization=org)
        except Employee.DoesNotExist:
            raise FnFException(f"Employee with ID {employee_id} not found.", code="EMPLOYEE_NOT_FOUND")

        data = calculate_fnf_settlement(employee, **kwargs)
        return data

    @staticmethod
    @transaction.atomic
    def prepare(employee_id: int, requesting_user, **kwargs) -> FinalSettlement:
        """
        Creates a DRAFT FinalSettlement and normalized SettlementLine entries.
        Must be idempotent and reject duplicates.
        """
        org = requesting_user.employee.organization if hasattr(requesting_user, 'employee') and requesting_user.employee else None
        if not org:
            from apps.authorization.services import AuthorizationService
            org = AuthorizationService.get_primary_organization(requesting_user)

        try:
            employee = Employee.objects.get(id=employee_id, organization=org)
        except Employee.DoesNotExist:
            raise FnFException(f"Employee with ID {employee_id} not found.", code="EMPLOYEE_NOT_FOUND")

        calc_result = calculate_fnf_settlement(employee, **kwargs)

        lwd = calc_result['exit_date']
        settlement_num = f"FNF-{lwd.year}{lwd.month:02d}-{employee.employee_code.strip()}"

        # Resignation event reference if available
        resignation_event = employee.lifecycle_events.filter(
            event_type__in=['resignation', 'exit']
        ).first()

        settlement = FinalSettlement.objects.create(
            organization=employee.organization,
            employee=employee,
            resignation_event=resignation_event,
            settlement_number=settlement_num,
            exit_date=lwd,
            resignation_date=calc_result['resignation_date'],
            settlement_date=calc_result['settlement_date'],
            status=FinalSettlement.STATUS_DRAFT,
            total_earnings=calc_result['total_earnings'],
            total_deductions=calc_result['total_deductions'],
            total_recoveries=calc_result['total_recoveries'],
            net_settlement_amount=calc_result['net_settlement_amount'],
            remarks=calc_result['remarks'],
            created_by=requesting_user,
            snapshot_data=calc_result['snapshot_data'],
        )

        lines_to_create = [
            SettlementLine(
                settlement=settlement,
                category=l['category'],
                code=l['code'],
                name=l['name'],
                amount=l['amount'],
                calculation_basis=l['calculation_basis'],
                source_reference=l['source_reference'],
                order=l['order'],
                metadata=l['metadata'],
            )
            for l in calc_result['lines']
        ]
        SettlementLine.objects.bulk_create(lines_to_create)

        AuditService.log(
            action="FNF_PREPARED",
            actor=requesting_user,
            target_type="FinalSettlement",
            target_id=settlement.id,
            organization=employee.organization,
            metadata={
                'settlement_number': settlement.settlement_number,
                'employee_code': employee.employee_code,
                'net_amount': str(settlement.net_settlement_amount),
            },
        )

        return settlement

    @staticmethod
    @transaction.atomic
    def approve(settlement: FinalSettlement, requesting_user) -> FinalSettlement:
        """
        Approves a draft settlement. Enforces maker-checker separation.
        """
        if settlement.status not in [FinalSettlement.STATUS_DRAFT, FinalSettlement.STATUS_REVIEW]:
            raise FnFException(
                f"Settlement in state '{settlement.status}' cannot be approved.",
                code="INVALID_STATE_TRANSITION",
            )

        # Maker-checker validation
        if settlement.created_by_id == requesting_user.id:
            raise FnFException(
                "Maker-checker violation: Settlement creator cannot approve the settlement.",
                code="MAKER_CHECKER_VIOLATION",
            )

        settlement.status = FinalSettlement.STATUS_APPROVED
        settlement.approved_by = requesting_user
        settlement.approved_at = timezone.now()
        settlement.save(update_fields=['status', 'approved_by', 'approved_at'])

        AuditService.log(
            action="FNF_APPROVED",
            actor=requesting_user,
            target_type="FinalSettlement",
            target_id=settlement.id,
            organization=settlement.organization,
            metadata={'settlement_number': settlement.settlement_number},
        )

        return settlement

    @staticmethod
    @transaction.atomic
    def finalize(settlement: FinalSettlement, requesting_user) -> FinalSettlement:
        """
        Finalizes an approved settlement. Locks immutable financial state and computes hash.
        """
        if settlement.status != FinalSettlement.STATUS_APPROVED:
            raise FnFException(
                f"Only approved settlements can be finalized. Current status: '{settlement.status}'.",
                code="INVALID_STATE_TRANSITION",
            )

        lines_summary = ";".join(
            f"{l.code}:{l.amount:.2f}" for l in settlement.lines.order_by('order', 'id')
        )
        integrity_hash = compute_settlement_integrity_hash(
            settlement_number=settlement.settlement_number,
            employee_code=settlement.employee.employee_code,
            net_amount=settlement.net_settlement_amount,
            total_earnings=settlement.total_earnings,
            total_deductions=settlement.total_deductions,
            total_recoveries=settlement.total_recoveries,
            lines_summary=lines_summary,
        )

        settlement.status = FinalSettlement.STATUS_FINALIZED
        settlement.finalized_by = requesting_user
        settlement.finalized_at = timezone.now()
        settlement.integrity_hash = integrity_hash

        # Update snapshot with finalizer information
        snapshot = settlement.snapshot_data or {}
        snapshot['finalized_by'] = requesting_user.email
        snapshot['finalized_at'] = str(settlement.finalized_at)
        snapshot['integrity_hash'] = integrity_hash
        settlement.snapshot_data = snapshot

        settlement.save(update_fields=['status', 'finalized_by', 'finalized_at', 'integrity_hash', 'snapshot_data'])

        AuditService.log(
            action="FNF_FINALIZED",
            actor=requesting_user,
            target_type="FinalSettlement",
            target_id=settlement.id,
            organization=settlement.organization,
            metadata={
                'settlement_number': settlement.settlement_number,
                'integrity_hash': integrity_hash,
            },
        )

        return settlement

    @staticmethod
    @transaction.atomic
    def cancel(settlement: FinalSettlement, requesting_user, reason: str = "") -> FinalSettlement:
        """Cancels a settlement in DRAFT or REVIEW status."""
        if settlement.status == FinalSettlement.STATUS_FINALIZED:
            raise FnFException(
                "Finalized settlements cannot be cancelled or voided.",
                code="CANNOT_CANCEL_FINALIZED",
            )

        settlement.status = FinalSettlement.STATUS_CANCELLED
        settlement.cancellation_reason = reason or "Cancelled by administrative action."
        settlement.save(update_fields=['status', 'cancellation_reason'])

        AuditService.log(
            action="FNF_CANCELLED",
            actor=requesting_user,
            target_type="FinalSettlement",
            target_id=settlement.id,
            organization=settlement.organization,
            metadata={
                'settlement_number': settlement.settlement_number,
                'cancellation_reason': settlement.cancellation_reason,
            },
        )

        return settlement
