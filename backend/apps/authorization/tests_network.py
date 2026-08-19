from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from apps.organization.models import Organization, OfficeNetwork
from apps.employees.models import Employee, WFHRequest
from apps.authorization.network import NetworkAccessService
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class NetworkPolicyTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(email='test@example.com', password='Password123!', status='active')
        self.employee = Employee.objects.create(user=self.user, employee_code='EMP001')
        self.org = Organization.objects.create(name='Test Org')
        self.network = OfficeNetwork.objects.create(
            organization=self.org,
            name='HQ Network',
            network='203.0.113.0/24'
        )

    def test_get_client_ip(self):
        request = self.factory.get('/', REMOTE_ADDR='192.168.1.10')
        # We test that it does not blindly trust HTTP_X_FORWARDED_FOR
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.50'
        ip = NetworkAccessService.get_client_ip(request)
        self.assertEqual(ip, '192.168.1.10')

    def test_office_network_allowed(self):
        # 203.0.113.50 is inside 203.0.113.0/24
        self.assertTrue(NetworkAccessService.is_office_network_allowed('203.0.113.50'))
        # 203.0.114.50 is outside
        self.assertFalse(NetworkAccessService.is_office_network_allowed('203.0.114.50'))

    def test_wfh_active(self):
        now = timezone.now()
        # No WFH yet
        self.assertFalse(NetworkAccessService.is_wfh_active(self.employee))

        # Pending WFH -> Not active
        WFHRequest.objects.create(
            employee=self.employee,
            start_at=now - timedelta(days=1),
            end_at=now + timedelta(days=1),
            status='pending'
        )
        self.assertFalse(NetworkAccessService.is_wfh_active(self.employee))

        # Approved WFH -> Active
        wfh = WFHRequest.objects.create(
            employee=self.employee,
            start_at=now - timedelta(days=1),
            end_at=now + timedelta(days=1),
            status='approved'
        )
        self.assertTrue(NetworkAccessService.is_wfh_active(self.employee))

        # Future WFH -> Not active
        wfh.start_at = now + timedelta(days=1)
        wfh.end_at = now + timedelta(days=2)
        wfh.save()
        self.assertFalse(NetworkAccessService.is_wfh_active(self.employee))

    def test_remote_access_allowed(self):
        # Outside network, no WFH
        request = self.factory.get('/', REMOTE_ADDR='192.168.1.10')
        self.assertFalse(NetworkAccessService.is_remote_access_allowed(request, self.user))

        # Inside network, no WFH
        request = self.factory.get('/', REMOTE_ADDR='203.0.113.50')
        self.assertTrue(NetworkAccessService.is_remote_access_allowed(request, self.user))

        # Outside network, approved WFH
        now = timezone.now()
        wfh = WFHRequest.objects.create(
            employee=self.employee,
            start_at=now - timedelta(days=1),
            end_at=now + timedelta(days=1),
            status='approved'
        )
        request = self.factory.get('/', REMOTE_ADDR='192.168.1.10')
        self.assertTrue(NetworkAccessService.is_remote_access_allowed(request, self.user))

        # Outside network, expired WFH
        wfh.start_at = now - timedelta(days=2)
        wfh.end_at = now - timedelta(days=1)
        wfh.save()
        self.assertFalse(NetworkAccessService.is_remote_access_allowed(request, self.user))

        # Outside network, rejected WFH
        wfh.start_at = now - timedelta(days=1)
        wfh.end_at = now + timedelta(days=1)
        wfh.status = 'rejected'
        wfh.save()
        self.assertFalse(NetworkAccessService.is_remote_access_allowed(request, self.user))

    def test_superadmin_access(self):
        super_user = User.objects.create_user(email='super@example.com', password='Password123!', status='active', is_superuser=True)
        # External IP, no WFH, no OfficeNetwork match -> ALLOWED for superadmin
        request = self.factory.get('/', REMOTE_ADDR='192.168.1.10')
        self.assertTrue(NetworkAccessService.is_remote_access_allowed(request, super_user))
