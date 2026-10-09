from rest_framework import serializers
from decimal import Decimal
from apps.payroll.models import (
    FinancialYear,
    TaxDeclarationCategory,
    TaxDeclaration,
    InvestmentDeclaration,
    InvestmentProof,
    TaxRuleConfiguration,
    TaxSlab,
    TaxSurchargeSlab,
    TaxRuleDeductionApplicability,
)


class FinancialYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialYear
        fields = [
            'id', 'name', 'start_date', 'end_date', 'is_active', 'is_locked', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class TaxDeclarationCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxDeclarationCategory
        fields = [
            'id', 'code', 'name', 'description', 'max_limit',
            'regime_applicability', 'is_active'
        ]
        read_only_fields = ['id']


class InvestmentProofSerializer(serializers.ModelSerializer):
    reviewed_by_email = serializers.CharField(source='reviewed_by.email', read_only=True, default=None)

    class Meta:
        model = InvestmentProof
        fields = [
            'id', 'declaration_item', 'proof_type', 'document_name',
            'file_size', 'mime_type', 'status', 'rejection_reason',
            'reviewed_by_email', 'reviewed_at', 'submitted_at'
        ]
        read_only_fields = [
            'id', 'declaration_item', 'file_size', 'mime_type', 'status',
            'rejection_reason', 'reviewed_by_email', 'reviewed_at', 'submitted_at'
        ]


class InvestmentDeclarationSerializer(serializers.ModelSerializer):
    proofs = InvestmentProofSerializer(many=True, read_only=True)

    class Meta:
        model = InvestmentDeclaration
        fields = [
            'id', 'declaration', 'category', 'category_code', 'description',
            'declared_amount', 'verified_amount', 'status', 'rejection_reason',
            'metadata', 'proofs', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'declaration', 'category', 'verified_amount', 'status',
            'rejection_reason', 'proofs', 'created_at', 'updated_at'
        ]


class TaxDeclarationSummarySerializer(serializers.ModelSerializer):
    financial_year_name = serializers.CharField(source='financial_year.name', read_only=True)
    financial_year_start = serializers.DateField(source='financial_year.start_date', read_only=True)
    financial_year_end = serializers.DateField(source='financial_year.end_date', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    employee_name = serializers.SerializerMethodField()
    items_count = serializers.IntegerField(source='items.count', read_only=True)

    class Meta:
        model = TaxDeclaration
        fields = [
            'id', 'employee', 'employee_code', 'employee_name', 'financial_year',
            'financial_year_name', 'financial_year_start', 'financial_year_end',
            'tax_regime', 'status', 'total_declared_amount', 'total_verified_amount',
            'items_count', 'submission_date', 'verification_date', 'created_at'
        ]
        read_only_fields = fields

    def get_employee_name(self, obj):
        u = getattr(obj.employee, 'user', None)
        if u:
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return obj.employee.employee_code


class TaxDeclarationDetailSerializer(serializers.ModelSerializer):
    financial_year_name = serializers.CharField(source='financial_year.name', read_only=True)
    financial_year_start = serializers.DateField(source='financial_year.start_date', read_only=True)
    financial_year_end = serializers.DateField(source='financial_year.end_date', read_only=True)
    financial_year_locked = serializers.BooleanField(source='financial_year.is_locked', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    employee_name = serializers.SerializerMethodField()
    verified_by_email = serializers.CharField(source='verified_by.email', read_only=True, default=None)
    items = InvestmentDeclarationSerializer(many=True, read_only=True)

    class Meta:
        model = TaxDeclaration
        fields = [
            'id', 'employee', 'employee_code', 'employee_name', 'financial_year',
            'financial_year_name', 'financial_year_start', 'financial_year_end',
            'financial_year_locked', 'tax_regime', 'status', 'total_declared_amount',
            'total_verified_amount', 'submission_date', 'verification_date',
            'verified_by_email', 'rejection_reason', 'notes', 'snapshot_data',
            'items', 'created_at', 'updated_at'
        ]
        read_only_fields = fields

    def get_employee_name(self, obj):
        u = getattr(obj.employee, 'user', None)
        if u:
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return obj.employee.employee_code


class TaxDeclarationCreateSerializer(serializers.Serializer):
    financial_year_id = serializers.IntegerField(required=False)
    financial_year_name = serializers.CharField(required=False, max_length=32)
    tax_regime = serializers.ChoiceField(
        choices=[TaxDeclaration.REGIME_OLD, TaxDeclaration.REGIME_NEW],
        default=TaxDeclaration.REGIME_NEW,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        if not attrs.get('financial_year_id') and not attrs.get('financial_year_name'):
            raise serializers.ValidationError("Either financial_year_id or financial_year_name is required.")
        return attrs


class TaxDeclarationUpdateSerializer(serializers.Serializer):
    tax_regime = serializers.ChoiceField(
        choices=[TaxDeclaration.REGIME_OLD, TaxDeclaration.REGIME_NEW],
        required=False,
    )
    notes = serializers.CharField(required=False, allow_blank=True)


class InvestmentItemCreateSerializer(serializers.Serializer):
    category_code = serializers.CharField(max_length=32)
    description = serializers.CharField(max_length=255)
    declared_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    metadata = serializers.DictField(required=False, default=dict)


class InvestmentItemUpdateSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=255, required=False)
    declared_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'), required=False)
    metadata = serializers.DictField(required=False)


class TaxDeclarationRejectSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(required=True, min_length=3)


class TaxProofRejectSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(required=True, min_length=3)


class ItemVerificationEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)
    verified_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    rejected = serializers.BooleanField(required=False, default=False)
    rejection_reason = serializers.CharField(required=False, allow_blank=True, default='')


class TaxDeclarationVerificationSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    item_verifications = ItemVerificationEntrySerializer(many=True, required=False, default=list)


# =============================================================================
# TAX RULE & TDS CALCULATION SERIALIZERS (Phase 6.9C)
# =============================================================================

class TaxSlabSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxSlab
        fields = ['id', 'slab_order', 'lower_limit', 'upper_limit', 'rate']
        read_only_fields = ['id']


class TaxSurchargeSlabSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxSurchargeSlab
        fields = ['id', 'slab_order', 'threshold_amount', 'rate']
        read_only_fields = ['id']


class TaxRuleDeductionApplicabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRuleDeductionApplicability
        fields = ['id', 'category_code', 'is_allowed', 'max_deductible_limit']
        read_only_fields = ['id']


class TaxRuleConfigurationSerializer(serializers.ModelSerializer):
    financial_year_name = serializers.CharField(source='financial_year.name', read_only=True)
    slabs = TaxSlabSerializer(many=True, read_only=True)
    surcharge_slabs = TaxSurchargeSlabSerializer(many=True, read_only=True)
    deduction_rules = TaxRuleDeductionApplicabilitySerializer(many=True, read_only=True)

    class Meta:
        model = TaxRuleConfiguration
        fields = [
            'id', 'financial_year', 'financial_year_name', 'regime', 'version_identifier',
            'effective_from', 'effective_to', 'standard_deduction', 'rebate_income_threshold',
            'max_rebate_amount', 'cess_rate', 'is_active', 'description',
            'slabs', 'surcharge_slabs', 'deduction_rules', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TaxCalculationPreviewRequestSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField(required=True)
    period_id = serializers.IntegerField(required=True)
    current_gross = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)

