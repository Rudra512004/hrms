import re
from django.test import TestCase
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from rest_framework.authtoken.models import Token
from apps.audit.models import AuditLog
from apps.employees.models import Employee
from apps.organization.models import Organization, OfficeNetwork
from apps.authorization.models import Role, UserRole

User = get_user_model()

class PasswordResetTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

        self.client = APIClient()
        self.org, _ = Organization.objects.get_or_create(name='TestOrg')
        OfficeNetwork.objects.get_or_create(
            organization=self.org, name='Localhost',
            defaults={'network': '127.0.0.0/8', 'is_active': True}
        )

        self.user = User.objects.create_user(email='active@co.com', password='OldPassword123!')
        self.user.status = 'active'
        self.user.save()
        Employee.objects.create(user=self.user, employee_code='ACT001', personal_email='active@ext.com')

        self.superadmin = User.objects.create_superuser(email='super@co.com', password='SuperOld123!')
        Employee.objects.create(user=self.superadmin, employee_code='SUP001', personal_email='super@ext.com')
        self.role, _ = Role.objects.get_or_create(organization=self.org, name='AdminRole')
        UserRole.objects.create(user=self.superadmin, role=self.role)

        self.inactive_user = User.objects.create_user(email='inactive@co.com', password='Inactive123!')
        self.inactive_user.status = 'inactive'
        self.inactive_user.save()
        Employee.objects.create(user=self.inactive_user, employee_code='INA001', personal_email='in@ext.com')

        AuditLog.objects.all().delete()
        mail.outbox.clear()

    def test_reset_request_existing_active_account(self):
        resp = self.client.post('/api/v1/auth/password-reset/request/', {'email': 'active@co.com'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('If an account is associated', str(resp.data))

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('uid=', mail.outbox[0].body)
        self.assertIn('token=', mail.outbox[0].body)

        log = AuditLog.objects.filter(action='password_reset_requested').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.actor, self.user)
        meta_str = str(log.metadata).lower()
        self.assertNotIn('token', meta_str)
        self.assertNotIn('password', meta_str)

    def test_reset_request_nonexistent_account(self):
        resp = self.client.post('/api/v1/auth/password-reset/request/', {'email': 'nobody@co.com'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('If an account is associated', str(resp.data))

        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(AuditLog.objects.filter(action='password_reset_requested').exists())

    def test_reset_request_enumeration_protection(self):
        resp1 = self.client.post('/api/v1/auth/password-reset/request/', {'email': 'active@co.com'})
        resp2 = self.client.post('/api/v1/auth/password-reset/request/', {'email': 'nobody@co.com'})
        self.assertEqual(resp1.data, resp2.data)

    def test_successful_reset(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        # Test old password still works
        resp = self.client.post('/api/v1/auth/login/', {'email': 'active@co.com', 'password': 'OldPassword123!'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp = self.client.post('/api/v1/auth/password-reset/confirm/', {
            'uid': uid, 'token': token,
            'new_password': 'NewPassword123!', 'confirm_password': 'NewPassword123!'
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Test old password no longer works
        resp = self.client.post('/api/v1/auth/login/', {'email': 'active@co.com', 'password': 'OldPassword123!'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        # Test new password works
        resp = self.client.post('/api/v1/auth/login/', {'email': 'active@co.com', 'password': 'NewPassword123!'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        log = AuditLog.objects.filter(action='password_reset_completed').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.actor, self.user)
        meta_str = str(log.metadata).lower()
        self.assertNotIn('token', meta_str)
        self.assertNotIn('password', meta_str)

    def test_token_cannot_be_reused(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        resp = self.client.post('/api/v1/auth/password-reset/confirm/', {
            'uid': uid, 'token': token,
            'new_password': 'NewPassword123!', 'confirm_password': 'NewPassword123!'
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp2 = self.client.post('/api/v1/auth/password-reset/confirm/', {
            'uid': uid, 'token': token,
            'new_password': 'AnotherPassword123!', 'confirm_password': 'AnotherPassword123!'
        })
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid or expired reset token', str(resp2.data))

    def test_invalid_token_rejected(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        resp = self.client.post('/api/v1/auth/password-reset/confirm/', {
            'uid': uid, 'token': 'fake-token-123',
            'new_password': 'NewPassword123!', 'confirm_password': 'NewPassword123!'
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_confirmation_mismatch(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        resp = self.client.post('/api/v1/auth/password-reset/confirm/', {
            'uid': uid, 'token': token,
            'new_password': 'NewPassword123!', 'confirm_password': 'Mismatch123!'
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Passwords do not match', str(resp.data))

    def test_weak_password_rejected(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        resp = self.client.post('/api/v1/auth/password-reset/confirm/', {
            'uid': uid, 'token': token,
            'new_password': 'weak', 'confirm_password': 'weak'
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_superadmin_reset(self):
        uid = urlsafe_base64_encode(force_bytes(self.superadmin.pk))
        token = default_token_generator.make_token(self.superadmin)

        resp = self.client.post('/api/v1/auth/password-reset/confirm/', {
            'uid': uid, 'token': token,
            'new_password': 'NewSuperPass123!', 'confirm_password': 'NewSuperPass123!'
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.superadmin.refresh_from_db()
        self.assertTrue(self.superadmin.is_superuser)
        self.assertTrue(UserRole.objects.filter(user=self.superadmin, role=self.role).exists())
        self.assertEqual(self.superadmin.status, 'active')

    def test_deactivated_account_reset(self):
        resp = self.client.post('/api/v1/auth/password-reset/request/', {'email': 'inactive@co.com'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

        uid = urlsafe_base64_encode(force_bytes(self.inactive_user.pk))
        token = default_token_generator.make_token(self.inactive_user)

        resp = self.client.post('/api/v1/auth/password-reset/confirm/', {
            'uid': uid, 'token': token,
            'new_password': 'NewInactive123!', 'confirm_password': 'NewInactive123!'
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Account is not active', str(resp.data))

        self.inactive_user.refresh_from_db()
        self.assertEqual(self.inactive_user.status, 'inactive')

    def test_existing_token_invalidated(self):
        auth_token, _ = Token.objects.get_or_create(user=self.user)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {auth_token.key}')
        resp = self.client.get('/api/v1/auth/me/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.client.credentials()

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        resp = self.client.post('/api/v1/auth/password-reset/confirm/', {
            'uid': uid, 'token': token,
            'new_password': 'NewPassword123!', 'confirm_password': 'NewPassword123!'
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {auth_token.key}')
        resp = self.client.get('/api/v1/auth/me/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.credentials()

    def test_rate_limiting(self):
        from django.core.cache import cache
        cache.clear()

        for i in range(5):
            resp = self.client.post('/api/v1/auth/password-reset/request/', {'email': 'active@co.com'})
            self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp = self.client.post('/api/v1/auth/password-reset/request/', {'email': 'active@co.com'})
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
