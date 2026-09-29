from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.employees.models import Employee
from .models import LeaveType, LeaveBalance



from django.db.models.signals import post_delete
from .models import LeaveRequest
from django.db import transaction
