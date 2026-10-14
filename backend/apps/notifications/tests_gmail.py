"""
Comprehensive tests for Gmail API OAuth integration.

All Google API calls are mocked — no real network requests or emails
are sent during the test suite.

Test coverage:
  - PlatformEmailCredential model: encryption/decryption, active credential
  - GmailAuthorizeView: superuser restriction, state generation, config check
  - GmailCallbackView: state validation, code exchange, email verification,
    credential storage, error handling
  - GmailAPIEmailBackend: token refresh, MIME construction, API send,
    fail_silently behavior, missing credentials
"""

import base64
import json
from unittest.mock import MagicMock, patch, PropertyMock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.notifications.gmail_models import PlatformEmailCredential, _get_fernet
from apps.notifications.gmail_views import GmailAuthorizeView, GmailCallbackView
from apps.notifications.gmail_backend import GmailAPIEmailBackend

User = get_user_model()


# ---------------------------------------------------------------------------
# Test settings overlay for Gmail OAuth
# ---------------------------------------------------------------------------
GMAIL_TEST_SETTINGS = {
    'GOOGLE_OAUTH_CLIENT_ID': 'test-client-id.apps.googleusercontent.com',
    'GOOGLE_OAUTH_CLIENT_SECRET': 'test-client-secret',
    'GOOGLE_OAUTH_REDIRECT_URI': 'https://backend.example.com/api/v1/auth/google/callback/',
    'PLATFORM_EMAIL_ADDRESS': 'noreply@example.com',
    'GMAIL_ENCRYPTION_KEY': 'test-encryption-key-for-unit-tests',
}


# ===========================================================================
#  Model tests
# ===========================================================================

class PlatformEmailCredentialModelTest(TestCase):
    """Tests for PlatformEmailCredential encryption and retrieval."""

    @override_settings(**GMAIL_TEST_SETTINGS)
    def test_set_and_get_refresh_token(self):
        """Refresh token round-trips through Fernet encryption."""
        cred = PlatformEmailCredential(email='test@example.com')
        cred.set_refresh_token('1//refresh-token-value')
        cred.save()

        loaded = PlatformEmailCredential.objects.get(pk=cred.pk)
        self.assertEqual(loaded.get_refresh_token(), '1//refresh-token-value')

    @override_settings(**GMAIL_TEST_SETTINGS)
    def test_encrypted_token_is_not_plaintext(self):
        """The stored value must not be the plaintext token."""
        cred = PlatformEmailCredential(email='test@example.com')
        cred.set_refresh_token('1//my-secret-token')
        self.assertNotEqual(cred.encrypted_refresh_token, '1//my-secret-token')
        self.assertTrue(len(cred.encrypted_refresh_token) > 0)

    @override_settings(**GMAIL_TEST_SETTINGS)
    def test_get_active_credential(self):
        """get_active_credential returns the most recently authorized active credential."""
        from django.utils import timezone
        from datetime import timedelta

        old_cred = PlatformEmailCredential(
            email='old@example.com', is_active=True,
            authorized_at=timezone.now() - timedelta(days=1),
        )
        old_cred.set_refresh_token('old-token')
        old_cred.save()

        new_cred = PlatformEmailCredential(
            email='new@example.com', is_active=True,
            authorized_at=timezone.now(),
        )
        new_cred.set_refresh_token('new-token')
        new_cred.save()

        active = PlatformEmailCredential.get_active_credential()
        self.assertEqual(active.pk, new_cred.pk)

    @override_settings(**GMAIL_TEST_SETTINGS)
    def test_get_active_credential_none_when_all_inactive(self):
        """Returns None when no active credentials exist."""
        cred = PlatformEmailCredential(email='test@example.com', is_active=False)
        cred.set_refresh_token('token')
        cred.save()

        self.assertIsNone(PlatformEmailCredential.get_active_credential())

    @override_settings(GMAIL_ENCRYPTION_KEY='wrong-key')
    def test_decryption_with_wrong_key_returns_none(self):
        """Decryption failure (key change) returns None, not an exception."""
        # Create with correct key
        with self.settings(**GMAIL_TEST_SETTINGS):
            cred = PlatformEmailCredential(email='test@example.com')
            cred.set_refresh_token('secret-token')
            cred.save()

        # Try to decrypt with different key
        loaded = PlatformEmailCredential.objects.get(pk=cred.pk)
        result = loaded.get_refresh_token()
        self.assertIsNone(result)

    @override_settings(**GMAIL_TEST_SETTINGS)
    def test_mark_used_updates_timestamp(self):
        """mark_used() sets last_used_at."""
        cred = PlatformEmailCredential(email='test@example.com')
        cred.set_refresh_token('token')
        cred.save()

        self.assertIsNone(cred.last_used_at)
        cred.mark_used()
        cred.refresh_from_db()
        self.assertIsNotNone(cred.last_used_at)

    @override_settings(**GMAIL_TEST_SETTINGS)
    def test_str_representation(self):
        """String representation shows email and status."""
        cred = PlatformEmailCredential(email='test@example.com', is_active=True)
        self.assertEqual(str(cred), 'test@example.com (active)')

        cred.is_active = False
        self.assertEqual(str(cred), 'test@example.com (inactive)')


# ===========================================================================
#  OAuth View tests
# ===========================================================================

@override_settings(**GMAIL_TEST_SETTINGS)
class GmailAuthorizeViewTest(TestCase):
    """Tests for GET /api/v1/auth/google/authorize/"""

    def setUp(self):
        self.client = APIClient()
        self.superuser = User.objects.create_superuser(
            email='admin@example.com', password='SecurePass123!'
        )
        self.regular_user = User.objects.create_user(
            email='user@example.com', password='SecurePass123!', status='active'
        )
        self.url = '/api/v1/auth/google/authorize/'

    def test_unauthenticated_user_denied(self):
        """Anonymous users get 401."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_non_superuser_denied(self):
        """Regular users get 403."""
        token, _ = Token.objects.get_or_create(user=self.regular_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_superuser_gets_authorization_url(self):
        """Superuser receives a valid Google authorization URL."""
        token, _ = Token.objects.get_or_create(user=self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Use session-capable client
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('authorization_url', data)
        auth_url = data['authorization_url']
        self.assertIn('accounts.google.com', auth_url)
        self.assertIn('client_id=test-client-id', auth_url)
        self.assertIn('gmail.send', auth_url)
        self.assertIn('state=', auth_url)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='', GOOGLE_OAUTH_CLIENT_SECRET='')
    def test_missing_oauth_config_returns_500(self):
        """Missing OAuth configuration returns a 500 error."""
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 500)
        self.assertIn('not configured', response.json()['detail'])


@override_settings(**GMAIL_TEST_SETTINGS)
class GmailCallbackViewTest(TestCase):
    """Tests for GET /api/v1/auth/google/callback/"""

    def setUp(self):
        self.client = APIClient()
        self.superuser = User.objects.create_superuser(
            email='admin@example.com', password='SecurePass123!'
        )
        self.url = '/api/v1/auth/google/callback/'

    def test_missing_code_returns_400(self):
        """Missing authorization code returns 400."""
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(self.url, {'state': 'some-state'})
        self.assertEqual(response.status_code, 400)

    def test_missing_state_returns_400(self):
        """Missing state parameter returns 400."""
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(self.url, {'code': 'some-code'})
        self.assertEqual(response.status_code, 400)

    def test_error_parameter_returns_400(self):
        """Google error in callback returns 400."""
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(self.url, {'error': 'access_denied'})
        self.assertEqual(response.status_code, 400)

    def test_invalid_state_returns_403(self):
        """State mismatch returns 403."""
        self.client.force_authenticate(user=self.superuser)
        # Set a session state
        session = self.client.session
        session['gmail_oauth_state'] = 'correct-state'
        session['gmail_oauth_user_id'] = self.superuser.pk
        session.save()

        response = self.client.get(self.url, {
            'code': 'auth-code',
            'state': 'wrong-state',
        })
        self.assertEqual(response.status_code, 403)

    @patch('apps.notifications.gmail_views.urllib.request.urlopen')
    def test_successful_callback_stores_credential(self, mock_urlopen):
        """Successful OAuth callback stores encrypted credentials."""
        self.client.force_authenticate(user=self.superuser)

        # Set session state
        session = self.client.session
        session['gmail_oauth_state'] = 'valid-state-123'
        session['gmail_oauth_user_id'] = self.superuser.pk
        session.save()

        # Mock the token exchange response
        token_response = MagicMock()
        token_response.read.return_value = json.dumps({
            'access_token': 'ya29.mock-access-token',
            'refresh_token': '1//mock-refresh-token',
            'token_type': 'Bearer',
            'expires_in': 3600,
        }).encode('utf-8')
        token_response.__enter__ = MagicMock(return_value=token_response)
        token_response.__exit__ = MagicMock(return_value=False)

        # Mock the userinfo response
        userinfo_response = MagicMock()
        userinfo_response.read.return_value = json.dumps({
            'email': 'noreply@example.com',
            'email_verified': True,
        }).encode('utf-8')
        userinfo_response.__enter__ = MagicMock(return_value=userinfo_response)
        userinfo_response.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [token_response, userinfo_response]

        response = self.client.get(self.url, {
            'code': 'mock-auth-code',
            'state': 'valid-state-123',
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['email'], 'noreply@example.com')
        self.assertIn('successful', data['detail'])

        # Verify credential was stored
        cred = PlatformEmailCredential.get_active_credential()
        self.assertIsNotNone(cred)
        self.assertEqual(cred.email, 'noreply@example.com')
        self.assertTrue(cred.is_active)
        self.assertEqual(cred.authorized_by, self.superuser)

        # Verify refresh token is encrypted and decryptable
        decrypted = cred.get_refresh_token()
        self.assertEqual(decrypted, '1//mock-refresh-token')

    @patch('apps.notifications.gmail_views.urllib.request.urlopen')
    def test_callback_email_mismatch_returns_403(self, mock_urlopen):
        """Callback rejects if authorized email doesn't match PLATFORM_EMAIL_ADDRESS."""
        self.client.force_authenticate(user=self.superuser)

        session = self.client.session
        session['gmail_oauth_state'] = 'valid-state'
        session['gmail_oauth_user_id'] = self.superuser.pk
        session.save()

        token_response = MagicMock()
        token_response.read.return_value = json.dumps({
            'access_token': 'ya29.token', 'refresh_token': '1//token',
        }).encode('utf-8')
        token_response.__enter__ = MagicMock(return_value=token_response)
        token_response.__exit__ = MagicMock(return_value=False)

        userinfo_response = MagicMock()
        userinfo_response.read.return_value = json.dumps({
            'email': 'wrong@example.com',
        }).encode('utf-8')
        userinfo_response.__enter__ = MagicMock(return_value=userinfo_response)
        userinfo_response.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [token_response, userinfo_response]

        response = self.client.get(self.url, {
            'code': 'auth-code', 'state': 'valid-state',
        })

        self.assertEqual(response.status_code, 403)
        self.assertIn('does not match', response.json()['detail'])

    @patch('apps.notifications.gmail_views.urllib.request.urlopen')
    def test_callback_no_refresh_token_returns_400(self, mock_urlopen):
        """Returns 400 if Google doesn't provide a refresh token."""
        self.client.force_authenticate(user=self.superuser)

        session = self.client.session
        session['gmail_oauth_state'] = 'state'
        session['gmail_oauth_user_id'] = self.superuser.pk
        session.save()

        token_response = MagicMock()
        token_response.read.return_value = json.dumps({
            'access_token': 'ya29.token',
            # No refresh_token
        }).encode('utf-8')
        token_response.__enter__ = MagicMock(return_value=token_response)
        token_response.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [token_response]

        response = self.client.get(self.url, {
            'code': 'auth-code', 'state': 'state',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('refresh token', response.json()['detail'].lower())


# ===========================================================================
#  Email Backend tests
# ===========================================================================

@override_settings(**GMAIL_TEST_SETTINGS)
class GmailAPIEmailBackendTest(TestCase):
    """Tests for the custom Gmail API email backend."""

    def setUp(self):
        # Create an active credential
        self.cred = PlatformEmailCredential(
            email='noreply@example.com',
            is_active=True,
        )
        self.cred.set_refresh_token('1//test-refresh-token')
        self.cred.save()

    @patch('apps.notifications.gmail_backend.urllib.request.urlopen')
    def test_send_single_email(self, mock_urlopen):
        """Successfully sends a single email via Gmail API."""
        # Mock token refresh response
        token_response = MagicMock()
        token_response.read.return_value = json.dumps({
            'access_token': 'ya29.fresh-token',
        }).encode('utf-8')
        token_response.__enter__ = MagicMock(return_value=token_response)
        token_response.__exit__ = MagicMock(return_value=False)

        # Mock Gmail API send response
        send_response = MagicMock()
        send_response.read.return_value = json.dumps({
            'id': 'gmail-message-id-123',
            'threadId': 'thread-id',
        }).encode('utf-8')
        send_response.__enter__ = MagicMock(return_value=send_response)
        send_response.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [token_response, send_response]

        from django.core.mail import EmailMessage
        email = EmailMessage(
            subject='Test Subject',
            body='Test body content.',
            from_email='noreply@example.com',
            to=['recipient@example.com'],
        )

        backend = GmailAPIEmailBackend()
        sent = backend.send_messages([email])

        self.assertEqual(sent, 1)
        self.assertEqual(mock_urlopen.call_count, 2)

        # Verify the send request contained the right payload
        send_call = mock_urlopen.call_args_list[1]
        send_req = send_call[0][0]
        self.assertIn('gmail.googleapis.com', send_req.full_url)
        self.assertEqual(send_req.get_header('Authorization'), 'Bearer ya29.fresh-token')

    @patch('apps.notifications.gmail_backend.urllib.request.urlopen')
    def test_send_multiple_emails(self, mock_urlopen):
        """Backend can send multiple emails in one batch."""
        # Token refresh (once) + 2 sends
        token_resp = MagicMock()
        token_resp.read.return_value = json.dumps({'access_token': 'ya29.token'}).encode('utf-8')
        token_resp.__enter__ = MagicMock(return_value=token_resp)
        token_resp.__exit__ = MagicMock(return_value=False)

        send_resp_1 = MagicMock()
        send_resp_1.read.return_value = json.dumps({'id': 'msg-1'}).encode('utf-8')
        send_resp_1.__enter__ = MagicMock(return_value=send_resp_1)
        send_resp_1.__exit__ = MagicMock(return_value=False)

        send_resp_2 = MagicMock()
        send_resp_2.read.return_value = json.dumps({'id': 'msg-2'}).encode('utf-8')
        send_resp_2.__enter__ = MagicMock(return_value=send_resp_2)
        send_resp_2.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [token_resp, send_resp_1, send_resp_2]

        from django.core.mail import EmailMessage
        emails = [
            EmailMessage(subject='Email 1', body='Body 1', to=['a@example.com']),
            EmailMessage(subject='Email 2', body='Body 2', to=['b@example.com']),
        ]

        backend = GmailAPIEmailBackend()
        sent = backend.send_messages(emails)
        self.assertEqual(sent, 2)

    def test_no_credential_raises_error(self):
        """Missing credentials raise RuntimeError when fail_silently=False."""
        PlatformEmailCredential.objects.all().delete()

        from django.core.mail import EmailMessage
        email = EmailMessage(subject='Test', body='Body', to=['a@example.com'])

        backend = GmailAPIEmailBackend(fail_silently=False)
        with self.assertRaises(RuntimeError):
            backend.send_messages([email])

    def test_no_credential_returns_zero_silently(self):
        """Missing credentials return 0 when fail_silently=True."""
        PlatformEmailCredential.objects.all().delete()

        from django.core.mail import EmailMessage
        email = EmailMessage(subject='Test', body='Body', to=['a@example.com'])

        backend = GmailAPIEmailBackend(fail_silently=True)
        sent = backend.send_messages([email])
        self.assertEqual(sent, 0)

    @patch('apps.notifications.gmail_backend.urllib.request.urlopen')
    def test_token_refresh_failure_raises_error(self, mock_urlopen):
        """Token refresh failure raises RuntimeError when fail_silently=False."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url='https://oauth2.googleapis.com/token',
            code=401,
            msg='Unauthorized',
            hdrs=None,
            fp=MagicMock(read=MagicMock(return_value=b'{"error":"invalid_grant"}')),
        )

        from django.core.mail import EmailMessage
        email = EmailMessage(subject='Test', body='Body', to=['a@example.com'])

        backend = GmailAPIEmailBackend(fail_silently=False)
        with self.assertRaises(RuntimeError):
            backend.send_messages([email])

    @patch('apps.notifications.gmail_backend.urllib.request.urlopen')
    def test_send_failure_fail_silently(self, mock_urlopen):
        """Send failure returns 0 when fail_silently=True."""
        import urllib.error

        # Token refresh succeeds
        token_resp = MagicMock()
        token_resp.read.return_value = json.dumps({'access_token': 'ya29.token'}).encode('utf-8')
        token_resp.__enter__ = MagicMock(return_value=token_resp)
        token_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [
            token_resp,
            urllib.error.HTTPError(
                url=None, code=403, msg='Forbidden', hdrs=None,
                fp=MagicMock(read=MagicMock(return_value=b'{}')),
            ),
        ]

        from django.core.mail import EmailMessage
        email = EmailMessage(subject='Test', body='Body', to=['a@example.com'])

        backend = GmailAPIEmailBackend(fail_silently=True)
        sent = backend.send_messages([email])
        self.assertEqual(sent, 0)

    def test_empty_messages_returns_zero(self):
        """Sending empty list returns 0 without errors."""
        backend = GmailAPIEmailBackend()
        self.assertEqual(backend.send_messages([]), 0)

    @patch('apps.notifications.gmail_backend.urllib.request.urlopen')
    def test_mime_message_structure(self, mock_urlopen):
        """MIME message includes correct headers."""
        token_resp = MagicMock()
        token_resp.read.return_value = json.dumps({'access_token': 'ya29.token'}).encode('utf-8')
        token_resp.__enter__ = MagicMock(return_value=token_resp)
        token_resp.__exit__ = MagicMock(return_value=False)

        send_resp = MagicMock()
        send_resp.read.return_value = json.dumps({'id': 'msg-id'}).encode('utf-8')
        send_resp.__enter__ = MagicMock(return_value=send_resp)
        send_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [token_resp, send_resp]

        from django.core.mail import EmailMessage
        email = EmailMessage(
            subject='Important Notice',
            body='Hello World',
            from_email='sender@example.com',
            to=['recipient@example.com'],
            cc=['cc@example.com'],
            reply_to=['replyto@example.com'],
        )

        backend = GmailAPIEmailBackend()
        backend.send_messages([email])

        # Check the sent payload
        send_call = mock_urlopen.call_args_list[1]
        send_req = send_call[0][0]
        payload = json.loads(send_req.data.decode('utf-8'))
        raw_bytes = base64.urlsafe_b64decode(payload['raw'])
        raw_str = raw_bytes.decode('utf-8')

        self.assertIn('Subject: Important Notice', raw_str)
        self.assertIn('From: sender@example.com', raw_str)
        self.assertIn('To: recipient@example.com', raw_str)
        self.assertIn('Cc: cc@example.com', raw_str)
        self.assertIn('Reply-To: replyto@example.com', raw_str)
        import email as email_pkg
        msg = email_pkg.message_from_string(raw_str)
        self.assertEqual(msg.get_payload(decode=True).decode('utf-8'), 'Hello World')


# ===========================================================================
#  Integration test: NotificationService → GmailAPIEmailBackend
# ===========================================================================

@override_settings(
    EMAIL_BACKEND='apps.notifications.gmail_backend.GmailAPIEmailBackend',
    **GMAIL_TEST_SETTINGS,
)
class NotificationServiceGmailIntegrationTest(TestCase):
    """
    Verifies that NotificationService.send_*() methods work correctly
    when EMAIL_BACKEND is set to GmailAPIEmailBackend.
    """

    def setUp(self):
        self.cred = PlatformEmailCredential(
            email='noreply@example.com', is_active=True,
        )
        self.cred.set_refresh_token('1//integration-test-token')
        self.cred.save()

    @patch('apps.notifications.gmail_backend.urllib.request.urlopen')
    def test_send_verification_email_via_gmail(self, mock_urlopen):
        """send_tenant_owner_verification_email sends through Gmail API."""
        token_resp = MagicMock()
        token_resp.read.return_value = json.dumps({'access_token': 'ya29.token'}).encode('utf-8')
        token_resp.__enter__ = MagicMock(return_value=token_resp)
        token_resp.__exit__ = MagicMock(return_value=False)

        send_resp = MagicMock()
        send_resp.read.return_value = json.dumps({'id': 'msg-1'}).encode('utf-8')
        send_resp.__enter__ = MagicMock(return_value=send_resp)
        send_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [token_resp, send_resp]

        from apps.notifications.services import NotificationService
        result = NotificationService.send_tenant_owner_verification_email(
            recipient_email='owner@example.com',
            first_name='Jane',
            uid='abc123',
            token='token-xyz',
        )

        self.assertTrue(result)
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch('apps.notifications.gmail_backend.urllib.request.urlopen')
    def test_send_password_reset_via_gmail(self, mock_urlopen):
        """send_password_reset_email sends through Gmail API."""
        token_resp = MagicMock()
        token_resp.read.return_value = json.dumps({'access_token': 'ya29.token'}).encode('utf-8')
        token_resp.__enter__ = MagicMock(return_value=token_resp)
        token_resp.__exit__ = MagicMock(return_value=False)

        send_resp = MagicMock()
        send_resp.read.return_value = json.dumps({'id': 'msg-2'}).encode('utf-8')
        send_resp.__enter__ = MagicMock(return_value=send_resp)
        send_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [token_resp, send_resp]

        from apps.notifications.services import NotificationService
        result = NotificationService.send_password_reset_email(
            email='user@example.com',
            first_name='John',
            uid='def456',
            token='reset-token',
        )

        self.assertTrue(result)

    @patch('apps.notifications.gmail_backend.urllib.request.urlopen')
    def test_send_invitation_via_gmail(self, mock_urlopen):
        """send_organization_admin_invitation_email sends through Gmail API."""
        token_resp = MagicMock()
        token_resp.read.return_value = json.dumps({'access_token': 'ya29.token'}).encode('utf-8')
        token_resp.__enter__ = MagicMock(return_value=token_resp)
        token_resp.__exit__ = MagicMock(return_value=False)

        send_resp = MagicMock()
        send_resp.read.return_value = json.dumps({'id': 'msg-3'}).encode('utf-8')
        send_resp.__enter__ = MagicMock(return_value=send_resp)
        send_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [token_resp, send_resp]

        from apps.notifications.services import NotificationService
        result = NotificationService.send_organization_admin_invitation_email(
            recipient_email='admin@example.com',
            recipient_name='Admin',
            organization_name='TestCorp',
            raw_token='invite-token-123',
            inviter_name='Super Admin',
        )

        self.assertTrue(result)
