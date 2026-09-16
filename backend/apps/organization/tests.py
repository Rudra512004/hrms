
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from apps.organization.models import Organization, Branch, OfficeNetwork, AttendancePolicy, WorkingCalendar

User = get_user_model()

class OrganizationSetupTests(APITestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(email='super@admin.com', password='password', is_superuser=True)
        self.normal_user = User.objects.create_user(email='normal@user.com', password='password')
        self.url = '/api/v1/organization/setup/'

    def test_setup_success(self):
        self.client.force_authenticate(user=self.superadmin)
        data = {
            'name': 'New Org Ltd',
            'status': 'active',
            'working_calendar': {'work_days': '0,1,2,3,4'},
            'attendance_policy': {
                'is_office_gps_enabled': True,
                'is_office_ip_enabled': True,
                'is_wfh_enabled': False,
                'wfh_bypasses_office_restrictions': False
            },
            'primary_office': {
                'name': 'HQ',
                'latitude': '40.7128',
                'longitude': '-74.0060',
                'radius': 150.0
            },
            'primary_network': {
                'name': 'HQ WiFi',
                'network': '192.168.1.0/24',
                'is_active': True
            }
        }
        res = self.client.post(self.url, data, format='json')
        self.assertEqual(res.status_code, 201)

        org = Organization.objects.get(name='New Org Ltd')
        self.assertEqual(org.working_calendar.work_days, '0,1,2,3,4')
        self.assertTrue(org.attendance_policy.is_office_gps_enabled)
        self.assertTrue(Branch.objects.filter(organization=org, name='HQ').exists())
        self.assertTrue(OfficeNetwork.objects.filter(organization=org, name='HQ WiFi').exists())

    def test_setup_rollback_on_failure(self):
        self.client.force_authenticate(user=self.superadmin)
        data = {
            'name': 'Failing Org',
            'status': 'active',
            'primary_office': {
                'name': 'HQ',
                'latitude': '40.7128',
                'longitude': '-74.0060',
                'radius': 50.0 # Will fail because MinValueValidator(100.0) is strictly enforced in models clean(), but wait, DRF serializers don't call clean() unless configured.
                # Actually, our Branch model has a validator. Let's provide invalid IP instead to trigger failure at serializer/model level.
            },
            'primary_network': {
                'name': 'HQ WiFi',
                'network': 'invalid-ip',
                'is_active': True
            }
        }
        res = self.client.post(self.url, data, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Organization.objects.filter(name='Failing Org').exists())

    def test_setup_requires_superadmin(self):
        self.client.force_authenticate(user=self.normal_user)
        res = self.client.post(self.url, {'name': 'Unauthorized Org'})
        self.assertEqual(res.status_code, 403)
