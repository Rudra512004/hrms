from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.employees.models import Employee
from .models import LeaveType, LeaveBalance



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
