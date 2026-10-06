import os
import django
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

User = get_user_model()
hr = User.objects.get(email='hr@demo.local')
emp = User.objects.get(email='employee@demo.local')

client_emp = APIClient()
client_emp.force_authenticate(user=emp)

client_hr = APIClient()
client_hr.force_authenticate(user=hr)

# Check Branches
resp1 = client_hr.get('/api/v1/organization/branches/')
print(f"HR Branches GET: {resp1.status_code}")

resp2 = client_emp.get('/api/v1/organization/branches/')
print(f"Emp Branches GET: {resp2.status_code}")

# Check Office Networks
resp3 = client_hr.get('/api/v1/organization/office-networks/')
print(f"HR Office Networks GET: {resp3.status_code}")

resp4 = client_emp.get('/api/v1/organization/office-networks/')
print(f"Emp Office Networks GET: {resp4.status_code}")

# Check Audit
resp5 = client_hr.get('/api/v1/audit-logs/')
print(f"HR Audit GET: {resp5.status_code}")

resp6 = client_emp.get('/api/v1/audit-logs/')
print(f"Emp Audit GET: {resp6.status_code}")
