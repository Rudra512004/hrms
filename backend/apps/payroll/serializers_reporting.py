"""
Serializers for Payroll Reporting & Reconciliation.
"""
from rest_framework import serializers


class PeriodMetadataSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    label = serializers.CharField()
    status = serializers.CharField()
    start_date = serializers.CharField()
    end_date = serializers.CharField()


class PeriodSummaryMetricsSerializer(serializers.Serializer):
    total_employees = serializers.IntegerField()
    total_basic_salary = serializers.CharField(allow_null=True)
    total_gross_salary = serializers.CharField(allow_null=True)
    total_net_salary = serializers.CharField(allow_null=True)
    total_loss_of_pay = serializers.CharField(allow_null=True)
    average_net_salary = serializers.CharField(allow_null=True)
    scheduled_working_days = serializers.IntegerField()
    total_present_days = serializers.IntegerField()
    total_half_days = serializers.IntegerField()
    total_leave_days = serializers.IntegerField()
    total_absent_days = serializers.IntegerField()
    total_effective_paid_days = serializers.CharField()


class PeriodSummaryResponseSerializer(serializers.Serializer):
    period = PeriodMetadataSerializer()
    summary = PeriodSummaryMetricsSerializer()


class ReconciliationRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    employee_id = serializers.IntegerField()
    employee_code = serializers.CharField()
    employee_name = serializers.CharField()
    branch_name = serializers.CharField()
    department_name = serializers.CharField()
    working_days = serializers.IntegerField()
    present_days = serializers.IntegerField()
    half_days = serializers.IntegerField()
    leave_days = serializers.IntegerField()
    absent_days = serializers.IntegerField()
    effective_days = serializers.CharField()
    basic_salary = serializers.CharField(allow_null=True)
    gross_salary = serializers.CharField(allow_null=True)
    net_salary = serializers.CharField(allow_null=True)
    loss_of_pay_amount = serializers.CharField(allow_null=True)
    status = serializers.CharField()


class BranchBreakdownSerializer(serializers.Serializer):
    branch_id = serializers.IntegerField(allow_null=True)
    branch_name = serializers.CharField()
    headcount = serializers.IntegerField()
    total_net_salary = serializers.CharField(allow_null=True)
    average_net_salary = serializers.CharField(allow_null=True)


class DepartmentBreakdownSerializer(serializers.Serializer):
    department_id = serializers.IntegerField(allow_null=True)
    department_name = serializers.CharField()
    headcount = serializers.IntegerField()
    total_net_salary = serializers.CharField(allow_null=True)
    average_net_salary = serializers.CharField(allow_null=True)


class OrganizationBreakdownResponseSerializer(serializers.Serializer):
    by_branch = BranchBreakdownSerializer(many=True)
    by_department = DepartmentBreakdownSerializer(many=True)


class PayrollExceptionItemSerializer(serializers.Serializer):
    type = serializers.CharField()
    severity = serializers.CharField()
    employee_id = serializers.IntegerField()
    employee_code = serializers.CharField()
    employee_name = serializers.CharField()
    message = serializers.CharField()
