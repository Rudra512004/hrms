from django.contrib import admin
from .models import Employee, EmployeeLifecycleEvent, EmployeeDocument

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_code', 'user', 'employment_status', 'created_at')
    search_fields = ('employee_code', 'user__email')

@admin.register(EmployeeLifecycleEvent)
class EmployeeLifecycleEventAdmin(admin.ModelAdmin):
    list_display = ('employee', 'event_type', 'effective_date', 'created_at')
    search_fields = ('employee__employee_code', 'event_type')

@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(admin.ModelAdmin):
    list_display = ('employee', 'document_name', 'document_type', 'status', 'uploaded_at')
    search_fields = ('employee__employee_code', 'document_name')
    list_filter = ('document_type', 'status')
