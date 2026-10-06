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

# Check Announcements
resp1 = client_emp.get('/api/v1/announcements/')
print(f"Emp Announcements GET: {resp1.status_code}")

# Check Dashboard Trends 400
resp2 = client_hr.get('/api/v1/dashboard/trends/')
print(f"HR Dashboard Trends GET: {resp2.status_code} - {resp2.data}")

# Check Cross Tenant
orgs = list(hr.employee.organization.__class__.objects.all())
print(f"Total Orgs: {len(orgs)}")
