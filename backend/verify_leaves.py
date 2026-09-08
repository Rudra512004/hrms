import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.organization.models import Organization
from apps.leaves.models import LeaveType, LeaveBalance, LeaveRequest
from rest_framework.test import APIClient
from django.urls import reverse
from rest_framework import status
from datetime import timedelta
from django.utils import timezone

User = get_user_model()

def run_verification():
    print("Starting verification...")
    # Setup
    orgA = Organization.objects.create(name='Org A')
    orgB = Organization.objects.create(name='Org B')

    userA = User.objects.create_user(email='empA@example.com', password='Password123!', status='active')
    empA = Employee.objects.create(user=userA, employee_code='EMPA', organization=orgA)

    userB = User.objects.create_user(email='empB@example.com', password='Password123!', status='active')
    empB = Employee.objects.create(user=userB, employee_code='EMPB', organization=orgB)

    # Org A LeaveType
    ltA = LeaveType.objects.create(organization=orgA, name='Annual A', annual_allocation=20)
    
    # Check provisioning
    balA = LeaveBalance.objects.get(employee=empA, leave_type=ltA)
    print(f"Provisioned A: {balA.allocated} allocated, {balA.used} used")

    # Check Org B doesn't get Org A balances
    if LeaveBalance.objects.filter(employee=empB, leave_type=ltA).exists():
        print("FAIL: Org B got Org A balance!")
    else:
        print("PASS: Org B isolated from Org A provisioning")

    # Test API
    client = APIClient()
    client.force_authenticate(user=userB)
    
    # Org B trying to access Org A leave types
    response = client.get(reverse('leave-types-list'))
    if len(response.data) == 0:
        print("PASS: Org B cannot see Org A leave types")
    else:
        print("FAIL: Org B saw Org A leave types!")

    # Super Admin
    super_user = User.objects.create_user(email='super2@example.com', password='Password123!', status='active', is_superuser=True)
    client.force_authenticate(user=super_user)
    response = client.get(reverse('admin-leave-types-list'))
    if len(response.data) > 0:
        print("PASS: Super admin can see all leave types")
    else:
        print("FAIL: Super admin cannot see leave types!")

    print("Verification complete.")

if __name__ == '__main__':
    run_verification()
