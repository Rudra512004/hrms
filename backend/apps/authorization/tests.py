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
