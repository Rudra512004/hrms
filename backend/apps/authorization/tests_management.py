from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.organization.models import Organization
from .models import Role, Permission, UserRole, UserPermissionGrant
from .services import AuthorizationService

User = get_user_model()

class AuthorizationManagementAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Test Org')

        # Superadmin
        self.super_user = User.objects.create_user(email='super@example.com', password='Password123!', status='active', is_superuser=True)
        self.super_employee = Employee.objects.create(user=self.super_user, employee_code='EMP_SUPER')

        # Normal User
        self.normal_user = User.objects.create_user(email='normal@example.com', password='Password123!', status='active')
        self.normal_employee = Employee.objects.create(user=self.normal_user, employee_code='EMP_NORMAL')

        # Permissions and Roles
        self.perm_view_emp = Permission.objects.create(name='View Employee', codename='employee.view', resource='employee', action='view')
        self.perm_create_emp = Permission.objects.create(name='Create Employee', codename='employee.create', resource='employee', action='create')

        self.hr_role = Role.objects.create(organization=self.org, name='HR Manager')
        self.hr_role.role_permissions.create(permission=self.perm_view_emp)
        self.hr_role.role_permissions.create(permission=self.perm_create_emp)

    def test_assign_role(self):
        self.client.force_authenticate(user=self.super_user)
        response = self.client.post(reverse('user-roles-list'), {
            'user': self.normal_user.id,
            'role': self.hr_role.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(UserRole.objects.filter(user=self.normal_user, role=self.hr_role, is_revoked=False).exists())

        # Check effective permissions
        perms = AuthorizationService.get_effective_permissions(self.normal_user)
        self.assertIn('employee.view', perms)

    def test_revoke_role(self):
        user_role = UserRole.objects.create(user=self.normal_user, role=self.hr_role, assigned_by=self.super_user)
        self.client.force_authenticate(user=self.super_user)
        response = self.client.post(reverse('user-roles-revoke', kwargs={'pk': user_role.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user_role.refresh_from_db()
        self.assertTrue(user_role.is_revoked)

        perms = AuthorizationService.get_effective_permissions(self.normal_user)
        self.assertNotIn('employee.view', perms)

    def test_grant_direct_permission(self):
        self.client.force_authenticate(user=self.super_user)
        response = self.client.post(reverse('user-permissions-list'), {
            'user': self.normal_user.id,
            'permission': self.perm_view_emp.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(UserPermissionGrant.objects.filter(user=self.normal_user, permission=self.perm_view_emp, is_revoked=False).exists())

    def test_revoke_direct_permission(self):
        grant = UserPermissionGrant.objects.create(user=self.normal_user, permission=self.perm_view_emp, granted_by=self.super_user)
        self.client.force_authenticate(user=self.super_user)
        response = self.client.post(reverse('user-permissions-revoke', kwargs={'pk': grant.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        grant.refresh_from_db()
        self.assertTrue(grant.is_revoked)

    def test_unauthorized_role_assignment(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.post(reverse('user-roles-list'), {
            'user': self.normal_user.id,
            'role': self.hr_role.id
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_effective_permissions_api(self):
        UserRole.objects.create(user=self.normal_user, role=self.hr_role, assigned_by=self.super_user)
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(reverse('permissions-my-permissions'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('employee.view', response.data)

    def test_superadmin_protection(self):
        # Normal user with role assignment permission shouldn't revoke superadmin role
        # Actually in views.py, any modification of superadmin roles requires the acting user to be superadmin
        super_role = UserRole.objects.create(user=self.super_user, role=self.hr_role, assigned_by=self.super_user)

        # Give normal user role.revoke permission
        UserPermissionGrant.objects.create(user=self.normal_user, permission=Permission.objects.create(codename='role.revoke', name='Revoke Role'))

        self.client.force_authenticate(user=self.normal_user)
        response = self.client.post(reverse('user-roles-revoke', kwargs={'pk': super_role.pk}))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
