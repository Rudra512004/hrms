from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from .models import Permission, Role, RolePermission, UserRole, UserPermissionGrant
from apps.organization.models import Organization

User = get_user_model()

class AuthorizationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email='test@example.com', password='password123', status='active')
        self.org = Organization.objects.create(name='Test Org')
        from apps.organization.models import OrganizationMembership
        OrganizationMembership.objects.create(user=self.user, organization=self.org, status='active')
        self.role = Role.objects.create(organization=self.org, name='TestRole')
        self.permission = Permission.objects.create(codename='test.perm', name='Test Perm', resource='test', action='perm')

    def test_unauthenticated_me_request(self):
        response = self.client.get(reverse('auth-me'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_me_request(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('auth-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['email'], self.user.email)
        self.assertEqual(response.data['permissions'], [])

    def test_rbac_role_assignment(self):
        RolePermission.objects.create(role=self.role, permission=self.permission)
        UserRole.objects.create(user=self.user, role=self.role)

        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('auth-me'))
        self.assertIn('test.perm', response.data['permissions'])
        self.assertIn('TestRole', response.data['roles'])

    def test_rbac_direct_permission(self):
        UserPermissionGrant.objects.create(user=self.user, permission=self.permission)

        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('auth-me'))
        self.assertIn('test.perm', response.data['permissions'])

    def test_me_endpoint_with_employee_profile(self):
        """Verifies designation, department, and organization_name are returned for employees."""
        from apps.organization.models import Branch, Department, Designation
        from apps.employees.models import Employee

        branch = Branch.objects.create(organization=self.org, name='Main Branch', radius=100)
        dept = Department.objects.create(branch=branch, name='Engineering')
        desig = Designation.objects.create(organization=self.org, name='Staff Engineer')
        Employee.objects.create(
            user=self.user,
            organization=self.org,
            branch=branch,
            department=dept,
            designation=desig,
            employee_code='EMP-777',
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('auth-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_data = response.data['user']
        self.assertTrue(user_data['has_employee_profile'])
        self.assertEqual(user_data['employee_code'], 'EMP-777')
        self.assertEqual(user_data['designation'], 'Staff Engineer')
        self.assertEqual(user_data['department'], 'Engineering')
        self.assertEqual(user_data['organization_name'], 'Test Org')

    def test_me_endpoint_without_employee_profile_safe(self):
        """Verifies headless user returns None for employee fields safely."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('auth-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_data = response.data['user']
        self.assertFalse(user_data['has_employee_profile'])
        self.assertIsNone(user_data['employee_code'])
        self.assertIsNone(user_data['designation'])
        self.assertIsNone(user_data['department'])
        self.assertEqual(user_data['organization_name'], 'Test Org')
