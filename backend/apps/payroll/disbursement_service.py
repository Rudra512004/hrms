import csv
import io
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.payroll.models import (
    PayrollPeriod,
    PayrollRecord,
    FinalSettlement,
    OrganizationBankAccount,
    PaymentRoutingConfiguration,
    DisbursementBatch,
    DisbursementItem,
)
from apps.payroll.workflow_service import PayrollWorkflowException
from apps.audit.services import AuditService

logger = logging.getLogger(__name__)


class DisbursementException(PayrollWorkflowException):
    def __init__(self, message: str, code: str = 'DISBURSEMENT_ERROR'):
        super().__init__(message)
        self.message = message
        self.code = code


def mask_account_number(acc: str) -> str:
    if not acc:
        return ""
    acc = acc.strip()
    if len(acc) <= 4:
        return acc
    return f"{'•' * (len(acc) - 4)}{acc[-4:]}"


class DisbursementService:
    """
    Service managing the offline generic bank salary disbursement lifecycle:
    1. Effective routing configuration evaluation.
    2. Finalized payroll eligibility validation & snapshot preparation (Draft).
    3. Maker-checker approval.
    4. Exact CSV generation & export.
    5. Cancellation.
    """

    CSV_HEADERS = [
        'Payment_Mode',
        'Debit_Account_Number',
        'Beneficiary_Account_Number',
        'Beneficiary_Name',
        'Beneficiary_IFSC',
        'Amount',
        'Value_Date',
        'Narration',
        'Beneficiary_Email',
        'Beneficiary_Mobile',
    ]

    @staticmethod
    def get_effective_routing_configuration(
        organization, branch=None, target_date: Optional[date] = None
    ) -> PaymentRoutingConfiguration:
        """
        Retrieve active PaymentRoutingConfiguration effective on target_date.
        Prefers branch-specific override if available, otherwise organization-wide.
        Falls back to a default configuration instance if none exists.
        """
        if target_date is None:
            target_date = timezone.now().date()

        qs = PaymentRoutingConfiguration.objects.filter(
            organization=organization,
            is_active=True,
            effective_from__lte=target_date,
        )

        if branch:
            branch_cfg = qs.filter(branch=branch).order_by('-effective_from', '-created_at').first()
            if branch_cfg:
                return branch_cfg

        org_cfg = qs.filter(branch__isnull=True).order_by('-effective_from', '-created_at').first()
        if org_cfg:
            return org_cfg

        # Fallback default: safe electronic default without hardcoded thresholds
        return PaymentRoutingConfiguration(
            organization=organization,
            default_payment_mode='NEFT',
            rtgs_enabled=False,
            rtgs_threshold=None,
            ift_enabled=False,
            ift_matching_mode=PaymentRoutingConfiguration.IFT_MATCHING_MODE_NONE,
            ift_ifsc_prefix_length=None,
            effective_from=target_date,
            is_active=True,
        )

    @classmethod
    @transaction.atomic
    def prepare_disbursement_batch(
        cls,
        period: PayrollPeriod,
        user,
        value_date: date,
        narration: Optional[str] = None,
        debit_account: Optional[OrganizationBankAccount] = None,
        branch=None,
    ) -> DisbursementBatch:
        """
        Validate finalized payroll eligibility, evaluate routing configuration,
        and create an immutable DisbursementBatch with snapshot items in DRAFT status.
        """
        # 1. State check: PayrollPeriod must be FINALIZED or DISBURSED
        if period.status not in [PayrollPeriod.STATUS_FINALIZED, PayrollPeriod.STATUS_DISBURSED]:
            raise DisbursementException(
                f"Cannot prepare bank disbursement for period in state '{period.status}'. "
                "Only finalized payroll periods are eligible.",
                code="PERIOD_NOT_FINALIZED",
            )

        # 2. Value Date validation
        if not value_date:
            raise DisbursementException(
                "Value date is mandatory for bank disbursement preparation.",
                code="MISSING_VALUE_DATE",
            )
        if isinstance(value_date, str):
            try:
                value_date = datetime.strptime(value_date, "%Y-%m-%d").date()
            except ValueError:
                raise DisbursementException(
                    "Value date must be in YYYY-MM-DD format.",
                    code="INVALID_VALUE_DATE_FORMAT",
                )

        # 3. Duplicate protection
        existing_batch = DisbursementBatch.objects.filter(
            organization=period.organization,
            period=period,
            branch=branch,
            status__in=[
                DisbursementBatch.STATUS_DRAFT,
                DisbursementBatch.STATUS_APPROVED,
                DisbursementBatch.STATUS_EXPORTED,
            ],
        ).first()
        if existing_batch:
            raise DisbursementException(
                f"An active disbursement batch ({existing_batch.batch_number}) already exists for this period. "
                "Duplicate payment runs are prevented.",
                code="DUPLICATE_DISBURSEMENT_BATCH",
            )

        # 4. Authoritative Debit Account check
        if debit_account is None:
            # Query primary active account for organization and optional branch
            debit_qs = OrganizationBankAccount.objects.filter(
                organization=period.organization,
                is_active=True,
                is_primary=True,
            )
            if branch:
                debit_account = debit_qs.filter(branch=branch).first()
            if not debit_account:
                debit_account = debit_qs.filter(branch__isnull=True).first()

            if not debit_account:
                # If no primary active account, check if any active account exists
                fallback_qs = OrganizationBankAccount.objects.filter(
                    organization=period.organization,
                    is_active=True,
                )
                if branch:
                    debit_account = fallback_qs.filter(branch=branch).first()
                if not debit_account:
                    debit_account = fallback_qs.filter(branch__isnull=True).first()

        if not debit_account or not debit_account.account_number.strip():
            raise DisbursementException(
                f"No corporate debit bank account configured for organization '{period.organization.name}'.",
                code="MISSING_DEBIT_ACCOUNT",
            )

        # Ensure debit account belongs to the same organization
        if debit_account.organization_id != period.organization_id:
            raise DisbursementException(
                "Debit bank account belongs to a different organization.",
                code="CROSS_TENANT_DEBIT_ACCOUNT",
            )

        # 5. Authoritative Narration
        if narration and narration.strip():
            clean_narration = narration.strip()
        else:
            # Deterministic: "Salary Oct 2026"
            month_abbr = period.start_date.strftime("%b")
            clean_narration = f"Salary {month_abbr} {period.year}"

        # 6. Retrieve Effective Routing Configuration
        routing_cfg = cls.get_effective_routing_configuration(
            organization=period.organization,
            branch=branch,
            target_date=value_date,
        )

        routing_snapshot = {
            'config_id': routing_cfg.id,
            'effective_from': routing_cfg.effective_from.isoformat() if routing_cfg.effective_from else None,
            'default_payment_mode': routing_cfg.default_payment_mode,
            'rtgs_enabled': routing_cfg.rtgs_enabled,
            'rtgs_threshold': str(routing_cfg.rtgs_threshold) if routing_cfg.rtgs_threshold is not None else None,
            'ift_enabled': routing_cfg.ift_enabled,
            'ift_matching_mode': routing_cfg.ift_matching_mode,
            'ift_ifsc_prefix_length': routing_cfg.ift_ifsc_prefix_length,
        }

        # 7. Check Eligible Payroll Records
        records_qs = period.records.all().select_related(
            'employee',
            'employee__statutory_and_bank',
            'employee__user',
        )
        if branch:
            records_qs = records_qs.filter(employee__branch=branch)

        records = list(records_qs)
        if not records:
            raise DisbursementException(
                "No eligible payroll records found in this period.",
                code="EMPTY_PAYROLL",
            )

        # 8. Validate Each Record and Build Snapshot Items
        total_amount = Decimal('0.00')
        items_to_create = []

        debit_ifsc_clean = debit_account.ifsc_code.strip().upper() if debit_account.ifsc_code else ""

        for rec in records:
            emp = rec.employee

            # Guard: check if employee's salary for this period was settled in an approved/finalized FnF
            already_settled_fnf = FinalSettlement.objects.filter(
                organization=period.organization,
                employee=emp,
                status__in=[FinalSettlement.STATUS_APPROVED, FinalSettlement.STATUS_FINALIZED],
                lines__code='SALARY_LWD',
                lines__source_reference=f"{period.year}-{period.month:02d}",
            ).first()
            if already_settled_fnf:
                raise DisbursementException(
                    f"Employee {emp.employee_code} already had salary for {period.year}-{period.month:02d} "
                    f"settled in FnF settlement ({already_settled_fnf.settlement_number}). "
                    "Cannot disburse regular payroll containing settled employee.",
                    code="SALARY_ALREADY_SETTLED_IN_FNF",
                )

            prior_exit_fnf = FinalSettlement.objects.filter(
                organization=period.organization,
                employee=emp,
                status__in=[FinalSettlement.STATUS_APPROVED, FinalSettlement.STATUS_FINALIZED],
                exit_date__lt=period.start_date,
            ).first()
            if prior_exit_fnf:
                raise DisbursementException(
                    f"Employee {emp.employee_code} exited on {prior_exit_fnf.exit_date} "
                    f"prior to period start and was settled in FnF ({prior_exit_fnf.settlement_number}). "
                    "Cannot disburse regular payroll for settled employee.",
                    code="EMPLOYEE_ALREADY_SETTLED_PRIOR_EXIT",
                )

            # A. Check Net Salary Amount
            if rec.net_salary < Decimal('0.00'):
                raise DisbursementException(
                    f"Employee {emp.employee_code} has negative net pay (₹{rec.net_salary}). "
                    "Cannot disburse negative amounts.",
                    code="NEGATIVE_NET_SALARY",
                )
            if rec.net_salary == Decimal('0.00'):
                raise DisbursementException(
                    f"Employee {emp.employee_code} has zero net pay (₹0.00). "
                    "Manual review required before disbursement.",
                    code="ZERO_NET_SALARY",
                )

            # B. Check Employee Statutory and Bank Details
            if not hasattr(emp, 'statutory_and_bank') or not emp.statutory_and_bank:
                raise DisbursementException(
                    f"Employee {emp.employee_code} is missing statutory & bank information.",
                    code="MISSING_BANK_DETAILS",
                )

            sb = emp.statutory_and_bank

            # C. Check Payment Mode Eligibility
            if sb.payment_mode in ['CHEQUE', 'CASH']:
                raise DisbursementException(
                    f"Employee {emp.employee_code} has payment mode '{sb.payment_mode}'. "
                    "Only electronic bank transfer employees are eligible for bank upload CSV export.",
                    code="INELIGIBLE_PAYMENT_MODE",
                )

            # D. Check Bank Account & IFSC
            ben_acc = sb.account_number.strip() if sb.account_number else ""
            if not ben_acc:
                raise DisbursementException(
                    f"Employee {emp.employee_code} is missing bank account number.",
                    code="MISSING_BENEFICIARY_ACCOUNT",
                )

            ben_ifsc = sb.ifsc_code.strip().upper() if sb.ifsc_code else ""
            if not ben_ifsc:
                raise DisbursementException(
                    f"Employee {emp.employee_code} is missing IFSC code.",
                    code="MISSING_BENEFICIARY_IFSC",
                )

            # E. Determine Beneficiary Name & Contacts
            ben_name = (sb.account_name.strip() if sb.account_name else "") or (
                f"{emp.user.first_name} {emp.user.last_name}".strip()
            ) or emp.employee_code

            ben_email = emp.user.email or emp.personal_email or ""
            ben_mobile = emp.phone_number or ""

            # F. Evaluate Configurable Routing (strictly configuration-driven)
            routed_mode = None
            if routing_cfg.ift_enabled:
                if routing_cfg.ift_matching_mode == PaymentRoutingConfiguration.IFT_MATCHING_MODE_EXACT:
                    if ben_ifsc and debit_ifsc_clean and ben_ifsc == debit_ifsc_clean:
                        routed_mode = 'IFT'
                elif routing_cfg.ift_matching_mode == PaymentRoutingConfiguration.IFT_MATCHING_MODE_PREFIX:
                    plen = routing_cfg.ift_ifsc_prefix_length
                    if plen and len(ben_ifsc) >= plen and len(debit_ifsc_clean) >= plen:
                        if ben_ifsc[:plen] == debit_ifsc_clean[:plen]:
                            routed_mode = 'IFT'

            if not routed_mode:
                if (
                    routing_cfg.rtgs_enabled
                    and routing_cfg.rtgs_threshold is not None
                    and rec.net_salary >= routing_cfg.rtgs_threshold
                ):
                    routed_mode = 'RTGS'
                else:
                    routed_mode = routing_cfg.default_payment_mode

            total_amount += rec.net_salary

            items_to_create.append(
                DisbursementItem(
                    payroll_record=rec,
                    employee=emp,
                    payment_mode=routed_mode,
                    debit_account_number=debit_account.account_number.strip(),
                    beneficiary_account_number=ben_acc,
                    beneficiary_name=ben_name,
                    beneficiary_ifsc=ben_ifsc,
                    amount=rec.net_salary,
                    value_date=value_date,
                    narration=clean_narration,
                    beneficiary_email=ben_email,
                    beneficiary_mobile=ben_mobile,
                )
            )

        # 9. Generate Deterministic Batch Number
        seq = DisbursementBatch.objects.filter(
            organization=period.organization,
            period=period,
        ).count() + 1
        org_code = period.organization.code or 'ORG'
        batch_number = f"DISB-{period.year}{period.month:02d}-{org_code}-{seq:03d}"

        # 10. Persist Batch
        batch = DisbursementBatch.objects.create(
            organization=period.organization,
            period=period,
            branch=branch,
            batch_number=batch_number,
            debit_account=debit_account,
            debit_account_number=debit_account.account_number.strip(),
            value_date=value_date,
            narration=clean_narration,
            status=DisbursementBatch.STATUS_DRAFT,
            total_amount=total_amount,
            total_count=len(items_to_create),
            routing_config_snapshot=routing_snapshot,
            created_by=user,
        )

        for itm in items_to_create:
            itm.batch = batch
        DisbursementItem.objects.bulk_create(items_to_create)

        # 11. Audit Logging
        AuditService.log(
            action="DISBURSEMENT_BATCH_PREPARED",
            actor=user,
            target_type="DisbursementBatch",
            target_id=str(batch.id),
            organization=period.organization,
            metadata={
                'batch_number': batch.batch_number,
                'period_id': period.id,
                'total_count': batch.total_count,
                'total_amount': str(batch.total_amount),
                'masked_debit_account': mask_account_number(debit_account.account_number),
                'value_date': value_date.isoformat(),
            },
        )

        return batch

    @classmethod
    @transaction.atomic
    def prepare_fnf_disbursement_batch(
        cls,
        settlement: FinalSettlement,
        user,
        value_date: date,
        narration: Optional[str] = None,
        debit_account: Optional[OrganizationBankAccount] = None,
    ) -> DisbursementBatch:
        """
        Validate finalized Full & Final Settlement (FnF) eligibility, evaluate routing configuration,
        and create an immutable DisbursementBatch with a single FnF snapshot item in DRAFT status.
        """
        # 1. State check: FinalSettlement must be FINALIZED
        settlement = FinalSettlement.objects.select_for_update().get(pk=settlement.pk)
        if settlement.status != FinalSettlement.STATUS_FINALIZED:
            raise DisbursementException(
                f"Cannot prepare bank disbursement for FnF settlement in state '{settlement.status}'. "
                "Only finalized FnF settlements are eligible.",
                code="SETTLEMENT_NOT_FINALIZED",
            )

        # 2. Value Date validation
        if not value_date:
            raise DisbursementException(
                "Value date is mandatory for bank disbursement preparation.",
                code="MISSING_VALUE_DATE",
            )
        if isinstance(value_date, str):
            try:
                value_date = datetime.strptime(value_date, "%Y-%m-%d").date()
            except ValueError:
                raise DisbursementException(
                    "Value date must be in YYYY-MM-DD format.",
                    code="INVALID_VALUE_DATE_FORMAT",
                )

        # 3. Duplicate protection
        existing_batch = DisbursementBatch.objects.filter(
            organization=settlement.organization,
            final_settlement=settlement,
            status__in=[
                DisbursementBatch.STATUS_DRAFT,
                DisbursementBatch.STATUS_APPROVED,
                DisbursementBatch.STATUS_EXPORTED,
            ],
        ).first()
        if existing_batch:
            raise DisbursementException(
                f"An active disbursement batch ({existing_batch.batch_number}) already exists for this FnF settlement. "
                "Duplicate payment runs are prevented.",
                code="DUPLICATE_DISBURSEMENT_BATCH",
            )

        # 4. Net Payable validation
        if settlement.net_payable < Decimal('0.00'):
            raise DisbursementException(
                f"FnF settlement has negative net payable (₹{settlement.net_payable}). "
                "Employee owes recovery to company. Cannot disburse negative amounts.",
                code="NEGATIVE_NET_PAYABLE",
            )
        if settlement.net_payable == Decimal('0.00'):
            raise DisbursementException(
                "FnF settlement has zero net payable (₹0.00). "
                "Manual review required before disbursement.",
                code="ZERO_NET_PAYABLE",
            )

        emp = settlement.employee
        branch = emp.branch

        # 5. Authoritative Debit Account check
        if debit_account is None:
            debit_qs = OrganizationBankAccount.objects.filter(
                organization=settlement.organization,
                is_active=True,
                is_primary=True,
            )
            if branch:
                debit_account = debit_qs.filter(branch=branch).first()
            if not debit_account:
                debit_account = debit_qs.filter(branch__isnull=True).first()

            if not debit_account:
                fallback_qs = OrganizationBankAccount.objects.filter(
                    organization=settlement.organization,
                    is_active=True,
                )
                if branch:
                    debit_account = fallback_qs.filter(branch=branch).first()
                if not debit_account:
                    debit_account = fallback_qs.filter(branch__isnull=True).first()

        if not debit_account or not debit_account.account_number.strip():
            raise DisbursementException(
                f"No corporate debit bank account configured for organization '{settlement.organization.name}'.",
                code="MISSING_DEBIT_ACCOUNT",
            )

        if debit_account.organization_id != settlement.organization_id:
            raise DisbursementException(
                "Debit bank account belongs to a different organization.",
                code="CROSS_TENANT_DEBIT_ACCOUNT",
            )

        # 6. Authoritative Narration
        if narration and narration.strip():
            clean_narration = narration.strip()[:255]
        else:
            clean_narration = f"FnF Settlement {settlement.settlement_number}"

        # 7. Retrieve Effective Routing Configuration
        routing_cfg = cls.get_effective_routing_configuration(
            organization=settlement.organization,
            branch=branch,
            target_date=value_date,
        )

        routing_snapshot = {
            'config_id': routing_cfg.id,
            'effective_from': routing_cfg.effective_from.isoformat() if routing_cfg.effective_from else None,
            'default_payment_mode': routing_cfg.default_payment_mode,
            'rtgs_enabled': routing_cfg.rtgs_enabled,
            'rtgs_threshold': str(routing_cfg.rtgs_threshold) if routing_cfg.rtgs_threshold is not None else None,
            'ift_enabled': routing_cfg.ift_enabled,
            'ift_matching_mode': routing_cfg.ift_matching_mode,
            'ift_ifsc_prefix_length': routing_cfg.ift_ifsc_prefix_length,
        }

        # 8. Check Employee Statutory and Bank Details
        if not hasattr(emp, 'statutory_and_bank') or not emp.statutory_and_bank:
            raise DisbursementException(
                f"Employee {emp.employee_code} is missing statutory & bank information.",
                code="MISSING_BANK_DETAILS",
            )

        sb = emp.statutory_and_bank

        if sb.payment_mode in ['CHEQUE', 'CASH']:
            raise DisbursementException(
                f"Employee {emp.employee_code} has payment mode '{sb.payment_mode}'. "
                "Only electronic bank transfer employees are eligible for bank upload CSV export.",
                code="INELIGIBLE_PAYMENT_MODE",
            )

        ben_acc = sb.account_number.strip() if sb.account_number else ""
        if not ben_acc:
            raise DisbursementException(
                f"Employee {emp.employee_code} is missing bank account number.",
                code="MISSING_BENEFICIARY_ACCOUNT",
            )

        ben_ifsc = sb.ifsc_code.strip().upper() if sb.ifsc_code else ""
        if not ben_ifsc:
            raise DisbursementException(
                f"Employee {emp.employee_code} is missing IFSC code.",
                code="MISSING_BENEFICIARY_IFSC",
            )

        ben_name = (sb.account_name.strip() if sb.account_name else "") or (
            f"{emp.user.first_name} {emp.user.last_name}".strip()
        ) or emp.employee_code

        ben_email = emp.user.email or emp.personal_email or ""
        ben_mobile = emp.phone_number or ""
        debit_ifsc_clean = debit_account.ifsc_code.strip().upper() if debit_account.ifsc_code else ""

        # 9. Evaluate Configurable Routing
        routed_mode = None
        if routing_cfg.ift_enabled:
            if routing_cfg.ift_matching_mode == PaymentRoutingConfiguration.IFT_MATCHING_MODE_EXACT:
                if ben_ifsc and debit_ifsc_clean and ben_ifsc == debit_ifsc_clean:
                    routed_mode = 'IFT'
            elif routing_cfg.ift_matching_mode == PaymentRoutingConfiguration.IFT_MATCHING_MODE_PREFIX:
                plen = routing_cfg.ift_ifsc_prefix_length
                if plen and len(ben_ifsc) >= plen and len(debit_ifsc_clean) >= plen:
                    if ben_ifsc[:plen] == debit_ifsc_clean[:plen]:
                        routed_mode = 'IFT'

        if not routed_mode:
            if (
                routing_cfg.rtgs_enabled
                and routing_cfg.rtgs_threshold is not None
                and settlement.net_payable >= routing_cfg.rtgs_threshold
            ):
                routed_mode = 'RTGS'
            else:
                routed_mode = routing_cfg.default_payment_mode

        # 10. Generate Deterministic Batch Number
        seq = DisbursementBatch.objects.filter(
            organization=settlement.organization,
            batch_type=DisbursementBatch.BATCH_TYPE_FNF,
        ).count() + 1
        org_code = settlement.organization.code or 'ORG'
        exit_d = settlement.exit_date or timezone.now().date()
        batch_number = f"DISB-FNF-{exit_d.year}{exit_d.month:02d}-{org_code}-{seq:03d}"

        # 11. Persist Batch
        batch = DisbursementBatch.objects.create(
            organization=settlement.organization,
            batch_type=DisbursementBatch.BATCH_TYPE_FNF,
            final_settlement=settlement,
            branch=branch,
            batch_number=batch_number,
            debit_account=debit_account,
            debit_account_number=debit_account.account_number.strip(),
            value_date=value_date,
            narration=clean_narration,
            status=DisbursementBatch.STATUS_DRAFT,
            total_amount=settlement.net_payable,
            total_count=1,
            routing_config_snapshot=routing_snapshot,
            created_by=user,
        )

        # 12. Persist Disbursement Item
        DisbursementItem.objects.create(
            batch=batch,
            final_settlement=settlement,
            employee=emp,
            payment_mode=routed_mode,
            debit_account_number=debit_account.account_number.strip(),
            beneficiary_account_number=ben_acc,
            beneficiary_name=ben_name,
            beneficiary_ifsc=ben_ifsc,
            amount=settlement.net_payable,
            value_date=value_date,
            narration=clean_narration,
            beneficiary_email=ben_email,
            beneficiary_mobile=ben_mobile,
        )

        # 13. Audit Logging
        AuditService.log(
            action="DISBURSEMENT_BATCH_PREPARED",
            actor=user,
            target_type="DisbursementBatch",
            target_id=str(batch.id),
            organization=settlement.organization,
            metadata={
                'batch_type': 'fnf',
                'batch_number': batch.batch_number,
                'settlement_id': settlement.id,
                'settlement_number': settlement.settlement_number,
                'employee_code': emp.employee_code,
                'total_count': 1,
                'total_amount': str(batch.total_amount),
                'masked_debit_account': mask_account_number(debit_account.account_number),
                'value_date': value_date.isoformat(),
            },
        )

        return batch

    @classmethod
    @transaction.atomic
    def approve_disbursement_batch(cls, batch: DisbursementBatch, user) -> DisbursementBatch:
        """
        Approve a prepared disbursement batch.
        Enforces maker-checker separation: creator cannot approve their own batch.
        """
        if batch.status == DisbursementBatch.STATUS_APPROVED:
            return batch  # Idempotent

        if batch.status == DisbursementBatch.STATUS_EXPORTED:
            raise DisbursementException(
                "Disbursement batch has already been exported.",
                code="BATCH_ALREADY_EXPORTED",
            )

        if batch.status == DisbursementBatch.STATUS_CANCELLED:
            raise DisbursementException(
                "Cannot approve a cancelled disbursement batch.",
                code="BATCH_CANCELLED",
            )

        if batch.status != DisbursementBatch.STATUS_DRAFT:
            raise DisbursementException(
                f"Cannot approve batch in status '{batch.status}'.",
                code="INVALID_BATCH_STATUS",
            )

        # Maker-Checker enforcement
        if batch.created_by_id == user.id:
            raise DisbursementException(
                "Maker-checker violation: Batch cannot be approved by the same user who prepared it.",
                code="MAKER_CHECKER_VIOLATION",
            )

        batch.status = DisbursementBatch.STATUS_APPROVED
        batch.approved_by = user
        batch.approved_at = timezone.now()
        batch.save(update_fields=['status', 'approved_by', 'approved_at'])

        AuditService.log(
            action="DISBURSEMENT_BATCH_APPROVED",
            actor=user,
            target_type="DisbursementBatch",
            target_id=str(batch.id),
            organization=batch.organization,
            metadata={
                'batch_number': batch.batch_number,
                'approved_by': user.email or str(user.id),
                'total_amount': str(batch.total_amount),
                'total_count': batch.total_count,
            },
        )

        return batch

    @classmethod
    @transaction.atomic
    def export_disbursement_csv(cls, batch: DisbursementBatch, user) -> str:
        """
        Generate exact generic CSV string strictly from the approved immutable DisbursementItem snapshots.
        Transitions status from APPROVED to EXPORTED (or remains EXPORTED if already downloaded).
        """
        if batch.status == DisbursementBatch.STATUS_DRAFT:
            raise DisbursementException(
                "Disbursement batch must be approved before generating the bank export file.",
                code="BATCH_NOT_APPROVED",
            )

        if batch.status == DisbursementBatch.STATUS_CANCELLED:
            raise DisbursementException(
                "Cannot export a cancelled disbursement batch.",
                code="BATCH_CANCELLED",
            )

        # Generate CSV from immutable items
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator='\r\n')

        # Write exact headers
        writer.writerow(cls.CSV_HEADERS)

        items = batch.items.all().order_by('id')
        for item in items:
            writer.writerow([
                item.payment_mode,
                item.debit_account_number,
                item.beneficiary_account_number,
                item.beneficiary_name,
                item.beneficiary_ifsc,
                f"{item.amount:.2f}",
                item.value_date.strftime("%d-%m-%Y"),
                item.narration,
                item.beneficiary_email,
                item.beneficiary_mobile,
            ])

        csv_content = output.getvalue()

        # Update export metadata
        if batch.status == DisbursementBatch.STATUS_APPROVED:
            batch.status = DisbursementBatch.STATUS_EXPORTED
            batch.exported_by = user
            batch.exported_at = timezone.now()
            batch.save(update_fields=['status', 'exported_by', 'exported_at'])

        AuditService.log(
            action="DISBURSEMENT_BATCH_EXPORTED",
            actor=user,
            target_type="DisbursementBatch",
            target_id=str(batch.id),
            organization=batch.organization,
            metadata={
                'batch_number': batch.batch_number,
                'exported_by': user.email or str(user.id),
                'total_count': batch.total_count,
                'total_amount': str(batch.total_amount),
            },
        )

        return csv_content

    @classmethod
    @transaction.atomic
    def cancel_disbursement_batch(cls, batch: DisbursementBatch, user, reason: str = "") -> DisbursementBatch:
        """
        Cancel a prepared or approved disbursement batch before it has been exported.
        """
        if batch.status == DisbursementBatch.STATUS_EXPORTED:
            raise DisbursementException(
                "Cannot cancel a batch that has already been exported to bank.",
                code="CANNOT_CANCEL_EXPORTED_BATCH",
            )
        if batch.status == DisbursementBatch.STATUS_CANCELLED:
            return batch

        batch.status = DisbursementBatch.STATUS_CANCELLED
        batch.save(update_fields=['status'])

        AuditService.log(
            action="DISBURSEMENT_BATCH_CANCELLED",
            actor=user,
            target_type="DisbursementBatch",
            target_id=str(batch.id),
            organization=batch.organization,
            metadata={
                'batch_number': batch.batch_number,
                'reason': reason,
            },
        )

        return batch

    @classmethod
    def export_bank_disbursement_csv(cls, batch: DisbursementBatch, user) -> str:
        """Alias for export_disbursement_csv."""
        return cls.export_disbursement_csv(batch=batch, user=user)
