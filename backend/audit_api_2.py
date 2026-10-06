import os
import django
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
    # Auth
    '/api/v1/auth/me/',
    
    # Org
    '/api/v1/organization/organizations/',
    '/api/v1/organization/branches/',
    '/api/v1/organization/departments/',
    '/api/v1/organization/designations/',
    '/api/v1/organization/office-networks/',
    '/api/v1/organization/working-calendars/',
    '/api/v1/organization/setup/',
    
    # Employees
    '/api/v1/employees/management/',
    '/api/v1/employees/documents/',
    '/api/v1/employees/reviews/',
    '/api/v1/employees/review-cycles/',
    
    # Employee self service
    '/api/v1/employees/me/',
    '/api/v1/employees/me/letters/',
    '/api/v1/employees/me/holidays/',
    '/api/v1/employees/me/announcements/',
    
    # Attendance
    '/api/v1/attendance/records/',
    '/api/v1/attendance/my-records/',
    '/api/v1/attendance/corrections/',
    
    # Leaves
    '/api/v1/leaves/requests/',
    '/api/v1/leaves/requests/my/',
    '/api/v1/leaves/balances/',
    
    # Payroll
    '/api/v1/payroll/periods/',
    '/api/v1/payroll/salary-components/',
    '/api/v1/payroll/salary-structures/',
    '/api/v1/payroll/records/',
    '/api/v1/payroll/payslips/',
    
    # Assets
    '/api/v1/assets/',
    '/api/v1/assets/my-assets/',
    '/api/v1/assets/categories/',
    
    # Notifications / Announcements
    '/api/v1/notifications/',
    '/api/v1/announcements/',
    
    # Candidates
    '/api/v1/candidates/',
    
    # Audit Logs
    '/api/v1/audit-logs/',
    
    # Dashboard
    '/api/v1/dashboard/overview/',
    '/api/v1/dashboard/trends/',
]

print(f"{'Endpoint':<45} | {'HR':<5} | {'Mgr':<5} | {'Emp':<5} | {'None':<5}")
print("-" * 75)

for ep in endpoints:
    row = [ep]
    for role, u in users.items():
        client = APIClient()
        client.force_authenticate(user=u)
        resp = client.get(ep)
        row.append(resp.status_code)
    print(f"{row[0]:<45} | {row[1]:<5} | {row[2]:<5} | {row[3]:<5} | {row[4]:<5}")
