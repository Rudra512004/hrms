from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.authorization.models import Permission, Role, UserRole
from apps.organization.models import Organization, Department, Designation

User = get_user_model()

class OrganizationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email='admin@example.com', password='password123', status='active')
        
        self.org = Organization.objects.create(name='Test Org')
        self.role = Role.objects.create(organization=self.org, name='AdminRole')
        UserRole.objects.create(user=self.user, role=self.role)
        
        # Give manage permissions
        for codename in ['organization.manage', 'department.manage', 'designation.manage']:
            perm, _ = Permission.objects.get_or_create(codename=codename, defaults={'name': codename, 'resource': 'org', 'action': 'manage'})
            self.role.permissions.add(perm)

    def test_create_organization(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('organization-list'), {'name': 'New Org', 'status': 'active'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Organization.objects.count(), 2)

    def test_create_department(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('department-list'), {'organization': self.org.id, 'name': 'Engineering'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Department.objects.count(), 1)

    def test_create_designation(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('designation-list'), {'organization': self.org.id, 'name': 'Software Engineer'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Designation.objects.count(), 1)

    def test_no_permission(self):
        self.role.permissions.clear()
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('organization-list'), {'name': 'New Org'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
