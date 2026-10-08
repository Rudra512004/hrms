from rest_framework import serializers
from .models import AlertRule, EmployeeAlertPreference, AlertInstance
from apps.organization.models import Branch, Department, Team

class AlertRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertRule
        fields = [
            'id', 'organization', 'alert_type', 'name', 'description', 'is_enabled',
            'default_value', 'minimum_value', 'maximum_value', 'value_unit',
            'employee_customization_allowed', 'severity', 'notification_enabled',
            'applicable_branches', 'applicable_departments', 'applicable_teams',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['organization', 'created_at', 'updated_at']

class EmployeeAlertPreferenceSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    rule_alert_type = serializers.CharField(source='rule.alert_type', read_only=True)
    rule_minimum_value = serializers.IntegerField(source='rule.minimum_value', read_only=True)
    rule_maximum_value = serializers.IntegerField(source='rule.maximum_value', read_only=True)
    rule_default_value = serializers.IntegerField(source='rule.default_value', read_only=True)
    rule_unit = serializers.CharField(source='rule.value_unit', read_only=True)
    employee_customization_allowed = serializers.BooleanField(source='rule.employee_customization_allowed', read_only=True)

    class Meta:
        model = EmployeeAlertPreference
        fields = [
            'id', 'employee', 'rule', 'rule_name', 'rule_alert_type', 
            'rule_minimum_value', 'rule_maximum_value', 'rule_default_value', 'rule_unit',
            'employee_customization_allowed', 'is_enabled', 'custom_value',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['employee', 'created_at', 'updated_at']

class AlertInstanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.user.get_full_name', read_only=True)
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    severity = serializers.CharField(source='rule.severity', read_only=True)
    
    class Meta:
        model = AlertInstance
        fields = [
            'id', 'employee', 'employee_name', 'rule', 'rule_name', 'severity',
            'status', 'occurrence_key', 'evaluated_at', 'acknowledged_at',
            'reference_date', 'metric_value_at_trigger', 'notification_reference'
        ]
        read_only_fields = ['id', 'employee', 'employee_name', 'rule', 'rule_name', 'severity',
                            'occurrence_key', 'evaluated_at', 'reference_date', 
                            'metric_value_at_trigger', 'notification_reference']
