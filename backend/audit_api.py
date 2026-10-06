import os
import django
from collections import defaultdict
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

User = get_user_model()
users = {
    'HR': User.objects.get(email='hr@demo.local'),
    'Manager': User.objects.get(email='manager@demo.local'),
    'Employee': User.objects.get(email='employee@demo.local'),
    'NoPerm': User.objects.get(email='noperm@demo.local'),
}

endpoints = [
    '/api/v1/auth/me/',
    '/api/v1/organization/organizations/',
    '/api/v1/organization/branches/',
    '/api/v1/organization/departments/',
    '/api/v1/organization/designations/',
    '/api/v1/employees/management/',
    '/api/v1/employees/me/',
    '/api/v1/attendance/',
    '/api/v1/attendance/me/',
    '/api/v1/leaves/requests/',
    '/api/v1/leaves/requests/me/',
    '/api/v1/leaves/balances/',
    '/api/v1/payroll/payroll-periods/',
    '/api/v1/payroll/salary-components/',
    '/api/v1/employees/reviews/',
    '/api/v1/employees/documents/',
    '/api/v1/assets/assets/',
    '/api/v1/assets/assignments/',
    '/api/v1/notifications/',
    '/api/v1/announcements/',
    '/api/v1/candidates/',
    '/api/v1/audit/logs/',
]

print(f"{'Endpoint':<40} | {'HR':<5} | {'Mgr':<5} | {'Emp':<5} | {'None':<5}")
print("-" * 75)

for ep in endpoints:
    row = [ep]
    for role, u in users.items():
        client = APIClient()
        client.force_authenticate(user=u)
        resp = client.get(ep)
        row.append(resp.status_code)
    print(f"{row[0]:<40} | {row[1]:<5} | {row[2]:<5} | {row[3]:<5} | {row[4]:<5}")
