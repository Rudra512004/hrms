from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from apps.organization.models import Organization, OfficeNetwork
from apps.authorization.models import Permission, Role, RolePermission, UserRole

User = get_user_model()

class OfficeNetworkTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='admin@example.com', password='Password123!', status='active')
        self.org = Organization.objects.create(name='Test Org')

        self.perm_view = Permission.objects.create(name='View Net', codename='office_network.view', resource='office_network', action='view')
        self.perm_create = Permission.objects.create(name='Create Net', codename='office_network.create', resource='office_network', action='create')

        self.role = Role.objects.create(organization=self.org, name='Superadmin')
        RolePermission.objects.create(role=self.role, permission=self.perm_view)
        RolePermission.objects.create(role=self.role, permission=self.perm_create)
        UserRole.objects.create(user=self.user, role=self.role)

        self.client.force_authenticate(user=self.user)

    def test_create_office_network(self):
        data = {
            'organization': self.org.id,
            'name': 'HQ',
            'network': '203.0.113.0/24'
        }
        response = self.client.post('/api/v1/organization/office-networks/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(OfficeNetwork.objects.count(), 1)

    def test_invalid_cidr(self):
        data = {
            'organization': self.org.id,
            'name': 'HQ',
            'network': 'invalid'
        }
        response = self.client.post('/api/v1/organization/office-networks/', data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('network', response.data)

    def test_unauthorized_creation(self):
        other_user = User.objects.create_user(email='other@example.com', password='Password123!', status='active')
        self.client.force_authenticate(user=other_user)
        data = {
            'organization': self.org.id,
            'name': 'HQ2',
            'network': '203.0.114.0/24'
        }
        response = self.client.post('/api/v1/organization/office-networks/', data)
        self.assertEqual(response.status_code, 403)
