from rest_framework import serializers
from .models import CompensationHistory, PayrollPeriod, PayrollRecord


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

    class Meta:
        model = PayrollRecord
        fields = [
            'id', 'period', 'period_label',
            'employee', 'employee_code', 'employee_name',
            'working_days', 'present_days', 'half_days', 'absent_days',
            'leave_days', 'effective_days',
            'basic_salary', 'gross_salary', 'net_salary',
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
        return ret
