from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.employees.models import Employee
from .models import LeaveType, LeaveBalance

@receiver(post_save, sender=Employee)
def auto_provision_leave_balances_for_employee(sender, instance, created, **kwargs):
    if created and instance.organization_id:
        active_leave_types = LeaveType.objects.filter(organization_id=instance.organization_id, is_active=True)
        balances = [
            LeaveBalance(
                employee=instance,
                leave_type=leave_type,
                allocated=leave_type.annual_allocation,
                used=0
            )
            for leave_type in active_leave_types
        ]
        LeaveBalance.objects.bulk_create(balances, ignore_conflicts=True)

@receiver(post_save, sender=LeaveType)
def auto_provision_leave_balances_for_leave_type(sender, instance, created, **kwargs):
    if created:
        employees = Employee.objects.filter(organization_id=instance.organization_id)
        balances = [
            LeaveBalance(
                employee=employee,
                leave_type=instance,
                allocated=instance.annual_allocation,
                used=0
            )
            for employee in employees
        ]
        LeaveBalance.objects.bulk_create(balances, ignore_conflicts=True)

from django.db.models.signals import post_delete
from .models import LeaveRequest
from django.db import transaction

@receiver(post_delete, sender=LeaveRequest)
def restore_leave_balance_on_delete(sender, instance, **kwargs):
    if instance.status == 'approved':
        with transaction.atomic():
            try:
                balance = LeaveBalance.objects.select_for_update().get(
                    employee=instance.employee, 
                    leave_type=instance.leave_type
                )
                balance.used -= instance.duration_days
                if balance.used < 0:
                    balance.used = 0
                balance.save()
            except LeaveBalance.DoesNotExist:
                pass
