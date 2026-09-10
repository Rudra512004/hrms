from django.contrib import admin
from .models import CompensationHistory, PayrollPeriod, PayrollRecord


@admin.register(CompensationHistory)
class CompensationHistoryAdmin(admin.ModelAdmin):
    list_display = ('employee', 'basic_salary', 'effective_from', 'effective_to', 'created_by', 'created_at')
    list_filter = ('employee__organization',)
    search_fields = ('employee__employee_code', 'employee__user__email')
    readonly_fields = ('created_by', 'created_at')
    ordering = ('-effective_from',)


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ('organization', 'year', 'month', 'status', 'generated_at', 'approved_by', 'approved_at')
    list_filter = ('organization', 'status', 'year')
    search_fields = ('organization__name',)
    readonly_fields = ('generated_at', 'approved_by', 'approved_at', 'created_at', 'updated_at')
    ordering = ('-year', '-month')


@admin.register(PayrollRecord)
class PayrollRecordAdmin(admin.ModelAdmin):
    list_display = (
        'employee', 'period', 'working_days', 'present_days', 'leave_days',
        'effective_days', 'basic_salary', 'net_salary', 'status',
    )
    list_filter = ('period__organization', 'status', 'period__year', 'period__month')
    search_fields = ('employee__employee_code', 'employee__user__email')
    readonly_fields = [f.name for f in PayrollRecord._meta.get_fields() if hasattr(f, 'name')]
    ordering = ('-period__year', '-period__month', 'employee__employee_code')
