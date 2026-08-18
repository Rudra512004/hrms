from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.organization.models import Organization
from apps.authorization.models import Permission, Role, RolePermission, UserRole, UserPermissionGrant
from apps.authorization.services import AuthorizationService
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class AuthorizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='test@example.com', password='Password123!', status='active')
        self.superuser = User.objects.create_superuser(email='admin@example.com', password='Password123!')
        self.inactive_user = User.objects.create_user(email='inactive@example.com', password='Password123!', status='inactive')
        self.org = Organization.objects.create(name='Test Org')

        self.perm_view = Permission.objects.create(name='View Employee', codename='employee.view', resource='employee', action='view')
        self.perm_create = Permission.objects.create(name='Create Employee', codename='employee.create', resource='employee', action='create')
        self.perm_inactive = Permission.objects.create(name='Delete Employee', codename='employee.delete', resource='employee', action='delete', is_active=False)

        self.role = Role.objects.create(organization=self.org, name='Manager')
        self.role2 = Role.objects.create(organization=self.org, name='HR')

        RolePermission.objects.create(role=self.role, permission=self.perm_view)

    def test_effective_permissions_role(self):
        UserRole.objects.create(user=self.user, role=self.role)
        perms = AuthorizationService.get_effective_permissions(self.user)
        self.assertIn('employee.view', perms)
        self.assertNotIn('employee.create', perms)

    def test_has_permission_regular_user(self):
        UserRole.objects.create(user=self.user, role=self.role)
        self.assertTrue(AuthorizationService.has_permission(self.user, 'employee.view'))
        self.assertFalse(AuthorizationService.has_permission(self.user, 'employee.create'))
