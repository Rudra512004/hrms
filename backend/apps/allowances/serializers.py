from rest_framework import serializers
from .models import AllowanceType, AllowanceEligibility, EmployeeAllowance, ReimbursementClaim

class AllowanceEligibilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = AllowanceEligibility
        fields = ['id', 'branches', 'departments', 'designations', 'employment_statuses']

class AllowanceTypeSerializer(serializers.ModelSerializer):
    eligibility_rule = AllowanceEligibilitySerializer(read_only=True)

    class Meta:
        model = AllowanceType
        fields = [
            'id', 'organization', 'name', 'code', 'description', 'category', 'calculation_type',
            'default_amount', 'default_percentage', 'frequency', 'maximum_amount', 'minimum_amount',
            'taxable', 'requires_approval', 'is_active', 'effective_from', 'effective_until',
            'eligibility_rule', 'created_at', 'updated_at'
        ]
        read_only_fields = ['organization', 'created_at', 'updated_at']

    def validate(self, data):
        if data.get('effective_until') and data.get('effective_from') and data.get('effective_from') > data.get('effective_until'):
            raise serializers.ValidationError({"effective_until": "Effective until date cannot precede effective from date."})
        return data

class EmployeeAllowanceSerializer(serializers.ModelSerializer):
    allowance_type_name = serializers.CharField(source='allowance_type.name', read_only=True)
    allowance_type_category = serializers.CharField(source='allowance_type.category', read_only=True)

    class Meta:
        model = EmployeeAllowance
        fields = [
            'id', 'organization', 'employee', 'allowance_type', 'allowance_type_name', 'allowance_type_category',
            'amount', 'percentage', 'frequency', 'effective_from', 'effective_until',
            'maximum_amount', 'is_active', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['organization', 'created_at', 'updated_at']

    def validate(self, data):
        if data.get('effective_until') and data.get('effective_from') and data.get('effective_from') > data.get('effective_until'):
            raise serializers.ValidationError({"effective_until": "Effective until date cannot precede effective from date."})
        return data

class ReimbursementClaimSerializer(serializers.ModelSerializer):
    allowance_type_name = serializers.CharField(source='allowance_type.name', read_only=True)
    allowance_type_category = serializers.CharField(source='allowance_type.category', read_only=True)
    employee_name = serializers.CharField(source='employee.user.get_full_name', read_only=True)
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)

    class Meta:
        model = ReimbursementClaim
        fields = [
            'id', 'organization', 'employee', 'employee_name', 'allowance_type', 'allowance_type_name', 'allowance_type_category',
            'amount_claimed', 'amount_approved', 'expense_date', 'description', 'receipt', 'notes',
            'status', 'submitted_at', 'reviewer', 'reviewer_name', 'reviewed_at', 'reviewer_comment',
            'payment_status', 'paid_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'organization', 'employee', 'amount_approved', 'status', 'submitted_at',
            'reviewer', 'reviewed_at', 'payment_status', 'paid_at', 'created_at', 'updated_at'
        ]

    def validate(self, data):
        if data.get('amount_claimed') and data.get('amount_claimed') < 0:
            raise serializers.ValidationError({"amount_claimed": "Amount cannot be negative."})
        return data

class ReimbursementReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReimbursementClaim
        fields = ['status', 'amount_approved', 'reviewer_comment']

    def validate(self, data):
        status_value = data.get('status')
        if status_value not in ['approved', 'rejected', 'returned']:
            raise serializers.ValidationError({"status": "Invalid review status."})
        if status_value == 'approved' and data.get('amount_approved') is None:
            raise serializers.ValidationError({"amount_approved": "Approved amount is required when approving."})
        if status_value in ['rejected', 'returned'] and not data.get('reviewer_comment'):
            raise serializers.ValidationError({"reviewer_comment": "Comment is required when rejecting or returning."})
        return data
