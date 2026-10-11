from rest_framework import serializers
from django.utils import timezone
from .models import (
    CompensationHistory,
    PayrollPeriod,
    PayrollRecord,
    Payslip,
    PayslipLine,
    SalaryComponent,
    SalaryStructure,
    SalaryStructureComponent,
    OrganizationBankAccount,
    PaymentRoutingConfiguration,
    DisbursementBatch,
    DisbursementItem,
    FnFPolicyConfiguration,
    FinalSettlement,
    SettlementLine,
)
from .disbursement_service import mask_account_number


class CompensationHistorySerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)

    class Meta:
        model = CompensationHistory
        fields = [
            'id', 'employee', 'employee_code',
            'effective_from', 'effective_to',
            'basic_salary',
            'created_by', 'created_by_email', 'created_at',
        ]
        read_only_fields = ['id', 'employee', 'created_by', 'created_at']

    def validate(self, data):
        effective_from = data.get('effective_from')
        effective_to = data.get('effective_to')
        if effective_from and effective_to and effective_to < effective_from:
            raise serializers.ValidationError(
                {'effective_to': 'effective_to must be on or after effective_from.'}
            )
        return data


class PayrollPeriodSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    approved_by_email = serializers.CharField(source='approved_by.email', read_only=True)
    record_count = serializers.SerializerMethodField()

    class Meta:
        model = PayrollPeriod
        fields = [
            'id', 'organization', 'organization_name',
            'year', 'month', 'start_date', 'end_date',
            'status', 'generated_at',
            'approved_by', 'approved_by_email', 'approved_at',
            'record_count', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'organization', 'status', 'generated_at',
            'approved_by', 'approved_at', 'created_at', 'updated_at',
        ]

    def get_record_count(self, obj):
        return obj.records.count()

    def validate(self, data):
        start = data.get('start_date')
        end = data.get('end_date')
        if start and end and end < start:
            raise serializers.ValidationError(
                {'end_date': 'end_date must be after start_date.'}
            )
        # Enforce year/month match start_date
        year = data.get('year')
        month = data.get('month')
        if start and year and month:
            if start.year != year or start.month != month:
                raise serializers.ValidationError(
                    'year/month must match start_date.'
                )
        return data


class PayrollRecordSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    employee_name = serializers.SerializerMethodField()
    period_label = serializers.SerializerMethodField()
    lop_days = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)
    lop_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = PayrollRecord
        fields = [
            'id', 'period', 'period_label',
            'employee', 'employee_code', 'employee_name',
            'working_days', 'present_days', 'half_days', 'absent_days',
            'leave_days', 'effective_days', 'lop_days',
            'basic_salary', 'gross_salary', 'net_salary', 'lop_amount',
            'status', 'generated_at',
        ]
        read_only_fields = fields  # records are fully computed; never user-editable

    def get_employee_name(self, obj):
        u = obj.employee.user
        return f"{u.first_name} {u.last_name}".strip() or u.email

    def get_period_label(self, obj):
        return f"{obj.period.year}/{obj.period.month:02d}"

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get('request')
        from apps.authorization.services import AuthorizationService
        if request and not AuthorizationService.has_permission(request.user, 'payroll.view_sensitive'):
            ret.pop('basic_salary', None)
            ret.pop('gross_salary', None)
            ret.pop('net_salary', None)
            ret.pop('lop_amount', None)
        return ret


class PayslipLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayslipLine
        fields = [
            'id', 'category', 'component_code', 'name', 'amount', 'order', 'metadata'
        ]
        read_only_fields = fields


class PayslipSummarySerializer(serializers.ModelSerializer):
    period_label = serializers.SerializerMethodField()
    year = serializers.IntegerField(source='payroll_record.period.year', read_only=True)
    month = serializers.IntegerField(source='payroll_record.period.month', read_only=True)
    start_date = serializers.DateField(source='payroll_record.period.start_date', read_only=True)
    end_date = serializers.DateField(source='payroll_record.period.end_date', read_only=True)
    net_salary = serializers.DecimalField(
        source='payroll_record.net_salary',
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    employee_code = serializers.CharField(
        source='payroll_record.employee.employee_code',
        read_only=True,
    )
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = Payslip
        fields = [
            'id', 'payslip_number', 'status', 'issued_at',
            'period_label', 'year', 'month', 'start_date', 'end_date',
            'net_salary', 'employee_code', 'employee_name',
            'verification_token', 'gross_earnings', 'total_deductions', 'net_pay',
        ]
        read_only_fields = fields

    def get_period_label(self, obj):
        p = obj.payroll_record.period
        return f"{p.year}/{p.month:02d}"

    def get_employee_name(self, obj):
        if obj.employee_name:
            return obj.employee_name
        u = obj.payroll_record.employee.user
        return f"{u.first_name} {u.last_name}".strip() or u.email


class PayslipDetailSerializer(serializers.ModelSerializer):
    period_label = serializers.SerializerMethodField()
    employee = serializers.SerializerMethodField()
    period = serializers.SerializerMethodField()
    attendance = serializers.SerializerMethodField()
    financials = serializers.SerializerMethodField()
    lines = PayslipLineSerializer(many=True, read_only=True)
    organization = serializers.SerializerMethodField()

    class Meta:
        model = Payslip
        fields = [
            'id', 'payslip_number', 'status', 'issued_at',
            'period_label', 'employee', 'period', 'attendance', 'financials',
            'lines', 'organization', 'verification_token', 'integrity_hash', 'net_pay_in_words',
        ]
        read_only_fields = fields

    def get_period_label(self, obj):
        p = obj.payroll_record.period
        return f"{p.year}/{p.month:02d}"

    def get_organization(self, obj):
        org = obj.payroll_record.period.organization
        return {
            'name': obj.organization_name or org.name,
            'legal_name': obj.legal_name or obj.organization_name or org.name,
            'address': obj.organization_address,
            'cin': obj.cin,
            'branch': obj.branch_name,
        }

    def get_employee(self, obj):
        emp = obj.payroll_record.employee
        u = emp.user
        return {
            'id': emp.id,
            'code': obj.employee_code or emp.employee_code,
            'name': obj.employee_name or (f"{u.first_name} {u.last_name}".strip() or u.email),
            'email': u.email,
            'department': obj.department_name or (emp.department.name if emp.department else None),
            'designation': obj.designation_name or (emp.designation.name if emp.designation else None),
            'joining_date': str(obj.joining_date) if obj.joining_date else (str(emp.joining_date) if emp.joining_date else None),
            'bank_name': obj.bank_name,
            'masked_bank_account': obj.masked_bank_account,
            'bank_ifsc': obj.bank_ifsc,
            'payment_mode': obj.payment_mode,
            'masked_pan': obj.masked_pan,
            'uan': obj.uan,
            'esic_number': obj.esic_number,
        }

    def get_period(self, obj):
        p = obj.payroll_record.period
        return {
            'id': p.id,
            'year': p.year,
            'month': p.month,
            'label': f"{p.year}/{p.month:02d}",
            'start_date': str(p.start_date),
            'end_date': str(p.end_date),
        }

    def get_attendance(self, obj):
        r = obj.payroll_record
        return {
            'calendar_days': obj.calendar_days or (r.period.end_date - r.period.start_date).days + 1,
            'working_days': obj.working_days or r.working_days,
            'present_days': str(obj.present_days) if obj.present_days > 0 else str(r.present_days),
            'half_days': obj.half_days or r.half_days,
            'leave_days': str(obj.leave_days) if obj.leave_days > 0 else str(r.leave_days),
            'absent_days': obj.absent_days or r.absent_days,
            'effective_days': str(obj.effective_days) if obj.effective_days > 0 else str(r.effective_days),
            'lop_days': str(obj.lop_days) if obj.lop_days > 0 else str(r.lop_days),
        }

    def get_financials(self, obj):
        r = obj.payroll_record
        request = self.context.get('request')
        is_owner = False
        if request and hasattr(request.user, 'employee'):
            is_owner = (request.user.employee.id == r.employee_id)

        has_sensitive_perm = False
        if request:
            from apps.authorization.services import AuthorizationService
            has_sensitive_perm = (
                AuthorizationService.has_permission(request.user, 'payroll.view_sensitive')
                or AuthorizationService.has_permission(request.user, 'payslip.view')
                or AuthorizationService.has_permission(request.user, 'payroll.view')
            )

        if not (is_owner or has_sensitive_perm):
            return {
                'basic_salary': None,
                'gross_salary': None,
                'deductions': None,
                'net_salary': None,
            }

        basic = obj.basic_salary if obj.basic_salary > 0 else r.basic_salary
        gross = obj.gross_earnings if obj.gross_earnings > 0 else r.gross_salary
        net = obj.net_pay if obj.net_pay > 0 else r.net_salary
        deductions = obj.total_deductions

        return {
            'basic_salary': str(basic),
            'gross_salary': str(gross),
            'deductions': str(deductions),
            'net_salary': str(net),
            'net_pay_in_words': obj.net_pay_in_words,
        }


class SalaryComponentSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)

    class Meta:
        model = SalaryComponent
        fields = [
            'id', 'organization', 'organization_name', 'name', 'code', 'kind',
            'is_taxable', 'is_active',
        ]
        read_only_fields = ['id', 'organization_name']
        extra_kwargs = {'organization': {'required': False}}

    def validate_code(self, value):
        return value.strip().upper()


class SalaryStructureComponentSerializer(serializers.ModelSerializer):
    component_name = serializers.CharField(source='component.name', read_only=True)
    component_code = serializers.CharField(source='component.code', read_only=True)
    component_kind = serializers.CharField(source='component.kind', read_only=True)

    class Meta:
        model = SalaryStructureComponent
        fields = [
            'id', 'component', 'component_name', 'component_code',
            'component_kind', 'amount',
        ]
        read_only_fields = ['id']


class SalaryStructureSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    components = SalaryStructureComponentSerializer(many=True, read_only=True)
    monthly_earnings = serializers.SerializerMethodField()
    monthly_deductions = serializers.SerializerMethodField()

    class Meta:
        model = SalaryStructure
        fields = [
            'id', 'organization', 'organization_name', 'name', 'is_active',
            'components', 'monthly_earnings', 'monthly_deductions',
        ]
        read_only_fields = [
            'id', 'organization_name', 'components', 'monthly_earnings',
            'monthly_deductions',
        ]
        extra_kwargs = {'organization': {'required': False}}

    def get_monthly_earnings(self, obj):
        return sum(
            (item.amount for item in obj.components.all() if item.component.kind == 'earning'),
            start=0,
        )

    def get_monthly_deductions(self, obj):
        return sum(
            (item.amount for item in obj.components.all() if item.component.kind == 'deduction'),
            start=0,
        )


class OrganizationBankAccountSerializer(serializers.ModelSerializer):
    masked_account_number = serializers.SerializerMethodField()
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = OrganizationBankAccount
        fields = [
            'id', 'organization', 'branch', 'branch_name',
            'bank_name', 'account_name', 'account_number', 'masked_account_number',
            'ifsc_code', 'is_primary', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'masked_account_number', 'created_at', 'updated_at']
        extra_kwargs = {
            'account_number': {'write_only': True},
        }

    def get_masked_account_number(self, obj):
        return mask_account_number(obj.account_number)


class PaymentRoutingConfigurationSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    updated_by_email = serializers.CharField(source='updated_by.email', read_only=True)

    class Meta:
        model = PaymentRoutingConfiguration
        fields = [
            'id', 'organization', 'branch',
            'default_payment_mode', 'rtgs_enabled', 'rtgs_threshold',
            'ift_enabled', 'ift_matching_mode', 'ift_ifsc_prefix_length',
            'effective_from', 'is_active',
            'created_by', 'created_by_email', 'updated_by', 'updated_by_email',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'created_by', 'created_by_email', 'updated_by', 'updated_by_email',
            'created_at', 'updated_at',
        ]


class DisbursementItemSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    masked_debit_account_number = serializers.SerializerMethodField()
    masked_beneficiary_account_number = serializers.SerializerMethodField()

    class Meta:
        model = DisbursementItem
        fields = [
            'id', 'payroll_record', 'final_settlement', 'employee', 'employee_code',
            'payment_mode', 'masked_debit_account_number',
            'masked_beneficiary_account_number', 'beneficiary_name',
            'beneficiary_ifsc', 'amount', 'value_date', 'narration',
            'beneficiary_email', 'beneficiary_mobile',
        ]
        read_only_fields = fields

    def get_masked_debit_account_number(self, obj):
        return mask_account_number(obj.debit_account_number)

    def get_masked_beneficiary_account_number(self, obj):
        return mask_account_number(obj.beneficiary_account_number)


class DisbursementBatchListSerializer(serializers.ModelSerializer):
    period_year = serializers.IntegerField(source='period.year', read_only=True)
    period_month = serializers.IntegerField(source='period.month', read_only=True)
    final_settlement_number = serializers.CharField(source='final_settlement.settlement_number', read_only=True)
    masked_debit_account_number = serializers.SerializerMethodField()
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    approved_by_email = serializers.CharField(source='approved_by.email', read_only=True)
    exported_by_email = serializers.CharField(source='exported_by.email', read_only=True)

    class Meta:
        model = DisbursementBatch
        fields = [
            'id', 'batch_type', 'batch_number', 'period', 'period_year', 'period_month',
            'final_settlement', 'final_settlement_number',
            'branch', 'masked_debit_account_number', 'value_date', 'narration',
            'status', 'total_amount', 'total_count',
            'created_by_email', 'created_at',
            'approved_by_email', 'approved_at',
            'exported_by_email', 'exported_at',
        ]
        read_only_fields = fields

    def get_masked_debit_account_number(self, obj):
        return mask_account_number(obj.debit_account_number)


class DisbursementBatchDetailSerializer(serializers.ModelSerializer):
    period_year = serializers.IntegerField(source='period.year', read_only=True)
    period_month = serializers.IntegerField(source='period.month', read_only=True)
    final_settlement_number = serializers.CharField(source='final_settlement.settlement_number', read_only=True)
    masked_debit_account_number = serializers.SerializerMethodField()
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    approved_by_email = serializers.CharField(source='approved_by.email', read_only=True)
    exported_by_email = serializers.CharField(source='exported_by.email', read_only=True)
    items = DisbursementItemSerializer(many=True, read_only=True)

    class Meta:
        model = DisbursementBatch
        fields = [
            'id', 'batch_type', 'batch_number', 'period', 'period_year', 'period_month',
            'final_settlement', 'final_settlement_number',
            'branch', 'masked_debit_account_number', 'value_date', 'narration',
            'status', 'total_amount', 'total_count',
            'routing_config_snapshot',
            'created_by_email', 'created_at',
            'approved_by_email', 'approved_at',
            'exported_by_email', 'exported_at',
            'items',
        ]
        read_only_fields = fields

    def get_masked_debit_account_number(self, obj):
        return mask_account_number(obj.debit_account_number)


class PrepareDisbursementBatchSerializer(serializers.Serializer):
    period_id = serializers.IntegerField(required=False, allow_null=True)
    final_settlement_id = serializers.IntegerField(required=False, allow_null=True)
    value_date = serializers.DateField(required=True)
    narration = serializers.CharField(required=False, allow_blank=True, max_length=255)
    debit_account_id = serializers.IntegerField(required=False, allow_null=True)
    branch_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        period_id = attrs.get('period_id')
        final_settlement_id = attrs.get('final_settlement_id')
        if not period_id and not final_settlement_id:
            raise serializers.ValidationError("Either period_id or final_settlement_id must be provided.")
        if period_id and final_settlement_id:
            raise serializers.ValidationError("Cannot provide both period_id and final_settlement_id.")
        return attrs


class PrepareFnFDisbursementBatchSerializer(serializers.Serializer):
    final_settlement_id = serializers.IntegerField(required=True)
    value_date = serializers.DateField(required=True)
    narration = serializers.CharField(required=False, allow_blank=True, max_length=255)
    debit_account_id = serializers.IntegerField(required=False, allow_null=True)


class FnFPolicyConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FnFPolicyConfiguration
        fields = [
            'id', 'organization', 'branch', 'effective_from', 'is_active',
            'leave_encashment_enabled', 'leave_encashment_daily_divisor',
            'leave_encashment_salary_basis', 'encashable_leave_types',
            'gratuity_enabled', 'gratuity_min_service_years',
            'gratuity_wage_days_per_year', 'gratuity_divisor', 'gratuity_max_ceiling',
            'notice_recovery_enabled', 'notice_recovery_daily_divisor',
            'notice_recovery_salary_basis',
            'bonus_enabled', 'joining_bonus_clawback_enabled', 'clawback_threshold_months',
            'created_by', 'updated_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'updated_by', 'created_at', 'updated_at']


class SettlementLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = SettlementLine
        fields = [
            'id', 'category', 'code', 'name', 'amount',
            'calculation_basis', 'source_reference', 'order', 'metadata',
        ]
        read_only_fields = fields


class FinalSettlementListSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    employee_name = serializers.SerializerMethodField()
    branch_name = serializers.CharField(source='employee.branch.name', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    approved_by_email = serializers.CharField(source='approved_by.email', read_only=True)
    finalized_by_email = serializers.CharField(source='finalized_by.email', read_only=True)

    class Meta:
        model = FinalSettlement
        fields = [
            'id', 'settlement_number', 'employee', 'employee_code', 'employee_name',
            'branch_name', 'department_name', 'exit_date', 'settlement_date', 'status',
            'total_earnings', 'total_deductions', 'total_recoveries', 'net_settlement_amount',
            'currency', 'created_by_email', 'created_at', 'approved_by_email', 'approved_at',
            'finalized_by_email', 'finalized_at',
        ]
        read_only_fields = fields

    def get_employee_name(self, obj):
        u = obj.employee.user
        return f"{u.first_name} {u.last_name}".strip() or u.email


class FinalSettlementDetailSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    employee_name = serializers.SerializerMethodField()
    branch_name = serializers.CharField(source='employee.branch.name', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    approved_by_email = serializers.CharField(source='approved_by.email', read_only=True)
    finalized_by_email = serializers.CharField(source='finalized_by.email', read_only=True)
    lines = SettlementLineSerializer(many=True, read_only=True)
    disbursement_batches = serializers.SerializerMethodField()

    class Meta:
        model = FinalSettlement
        fields = [
            'id', 'settlement_number', 'employee', 'employee_code', 'employee_name',
            'branch_name', 'department_name', 'exit_date', 'resignation_date',
            'settlement_date', 'status', 'total_earnings', 'total_deductions',
            'total_recoveries', 'net_settlement_amount', 'currency', 'remarks',
            'cancellation_reason', 'created_by_email', 'created_at',
            'approved_by_email', 'approved_at', 'finalized_by_email', 'finalized_at',
            'snapshot_data', 'integrity_hash', 'lines', 'disbursement_batches',
        ]
        read_only_fields = fields

    def get_employee_name(self, obj):
        u = obj.employee.user
        return f"{u.first_name} {u.last_name}".strip() or u.email

    def get_disbursement_batches(self, obj):
        batches = obj.disbursement_batches.all()
        return [
            {
                'id': b.id,
                'batch_number': b.batch_number,
                'status': b.status,
                'total_amount': b.total_amount,
                'value_date': b.value_date,
                'created_at': b.created_at,
            }
            for b in batches
        ]


class EmployeeSettlementLineSerializer(serializers.ModelSerializer):
    """
    Employee-safe representation of a settlement line item.
    Excludes internal metadata, debug fields, and sensitive source references.
    """
    class Meta:
        model = SettlementLine
        fields = [
            'id', 'category', 'code', 'name', 'amount',
            'calculation_basis', 'order',
        ]
        read_only_fields = fields


DISBURSEMENT_STATUS_LABELS = {
    'not_prepared': 'Payment instruction not prepared',
    'draft': 'Payment instruction prepared',
    'approved': 'Payment instruction approved',
    'exported': 'Bank file exported — bank confirmation pending',
    'cancelled': 'Payment instruction cancelled',
}


class EmployeeFinalSettlementSerializer(serializers.ModelSerializer):
    """
    Dedicated employee self-service serializer for Full & Final Settlement (FnF).
    Exposes only employee-safe financial outcomes, dates, normalized line items,
    and payment instruction status.
    Strictly excludes maker-checker workflow internals, audit metadata, administrative remarks,
    rejection/cancellation reasons, and sensitive banking/statutory details.
    """
    settlement_status = serializers.CharField(source='status', read_only=True)
    lines = EmployeeSettlementLineSerializer(many=True, read_only=True)
    disbursement_status = serializers.SerializerMethodField()
    disbursement_status_label = serializers.SerializerMethodField()
    disbursement_reference = serializers.SerializerMethodField()
    value_date = serializers.SerializerMethodField()
    prepared_at = serializers.SerializerMethodField()
    approved_at = serializers.SerializerMethodField()
    exported_at = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()

    class Meta:
        model = FinalSettlement
        fields = [
            'id', 'settlement_number', 'status', 'settlement_status', 'exit_date',
            'resignation_date', 'settlement_date', 'currency',
            'total_earnings', 'total_deductions', 'total_recoveries',
            'net_settlement_amount', 'finalized_at',
            'lines',
            'disbursement_status', 'disbursement_status_label',
            'disbursement_reference', 'value_date',
            'prepared_at', 'approved_at', 'exported_at',
            'payment_status',
        ]
        read_only_fields = fields

    def _get_sorted_batches(self, obj):
        if not hasattr(obj, '_cached_sorted_batches'):
            batches = list(obj.disbursement_batches.all())
            batches.sort(key=lambda b: (b.created_at or timezone.now(), b.id or 0), reverse=True)
            obj._cached_sorted_batches = batches
        return obj._cached_sorted_batches

    def _get_effective_batch(self, obj):
        batches = self._get_sorted_batches(obj)
        # Unique active constraint ensures at most one active batch exists (draft, approved, exported)
        for b in batches:
            if b.status in [DisbursementBatch.STATUS_DRAFT, DisbursementBatch.STATUS_APPROVED, DisbursementBatch.STATUS_EXPORTED]:
                return b
        # If no active batch, return the latest cancelled batch if one exists
        if batches:
            return batches[0]
        return None

    def get_disbursement_status(self, obj):
        b = self._get_effective_batch(obj)
        return b.status if b else 'not_prepared'

    def get_disbursement_status_label(self, obj):
        st = self.get_disbursement_status(obj)
        return DISBURSEMENT_STATUS_LABELS.get(st, st.replace('_', ' ').title())

    def get_disbursement_reference(self, obj):
        b = self._get_effective_batch(obj)
        return b.batch_number if b else None

    def get_value_date(self, obj):
        b = self._get_effective_batch(obj)
        return b.value_date.isoformat() if (b and b.value_date) else None

    def get_prepared_at(self, obj):
        b = self._get_effective_batch(obj)
        return b.created_at.isoformat() if (b and b.created_at) else None

    def get_approved_at(self, obj):
        b = self._get_effective_batch(obj)
        return b.approved_at.isoformat() if (b and b.approved_at) else None

    def get_exported_at(self, obj):
        b = self._get_effective_batch(obj)
        return b.exported_at.isoformat() if (b and b.exported_at) else None

    def get_payment_status(self, obj):
        b = self._get_effective_batch(obj)
        st = b.status if b else 'not_prepared'
        label = DISBURSEMENT_STATUS_LABELS.get(st, st.replace('_', ' ').title())
        batches = self._get_sorted_batches(obj)

        history = [
            {
                'disbursement_reference': h.batch_number,
                'status': h.status,
                'status_label': DISBURSEMENT_STATUS_LABELS.get(h.status, h.status.replace('_', ' ').title()),
                'value_date': h.value_date.isoformat() if h.value_date else None,
                'created_at': h.created_at.isoformat() if h.created_at else None,
            }
            for h in batches
        ]

        return {
            'status': st,
            'status_label': label,
            'disbursement_reference': b.batch_number if b else None,
            'value_date': b.value_date.isoformat() if (b and b.value_date) else None,
            'prepared_at': b.created_at.isoformat() if (b and b.created_at) else None,
            'approved_at': b.approved_at.isoformat() if (b and b.approved_at) else None,
            'exported_at': b.exported_at.isoformat() if (b and b.exported_at) else None,
            'bank_confirmation_pending': bool(b and b.status == DisbursementBatch.STATUS_EXPORTED),
            'history': history,
        }


class FnFPreviewRequestSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField(required=True)
    exit_date = serializers.DateField(required=False, allow_null=True)
    settlement_date = serializers.DateField(required=False, allow_null=True)
    asset_recoveries = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )
    loan_recoveries = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )
    bonus_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    bonus_remarks = serializers.CharField(required=False, allow_blank=True, default='')
    joining_bonus_clawback = serializers.DictField(
        required=False, allow_null=True, default=None
    )
    tds_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    remarks = serializers.CharField(required=False, allow_blank=True, default='')


class FnFPrepareRequestSerializer(FnFPreviewRequestSerializer):
    pass


class FnFCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default='')

