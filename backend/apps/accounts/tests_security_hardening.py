import io
import sys
from django.core.cache import cache
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


class AuthenticationSecurityHardeningTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='secure_user@example.com',
            password='SuperSecretPassword123!',
            status='active'
        )

    def test_login_does_not_log_plaintext_password(self):
        """Verify that LoginView does NOT print plaintext password to stdout."""
        captured_stdout = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_stdout
        try:
            resp = self.client.post('/api/v1/auth/login/', {
                'email': 'secure_user@example.com',
                'password': 'SuperSecretPassword123!'
            })
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
        finally:
            sys.stdout = old_stdout

        output = captured_stdout.getvalue()
        self.assertNotIn('SuperSecretPassword123!', output)
        self.assertNotIn('DEBUG LOGIN REQUEST', output)

    def test_login_rate_limiting(self):
        """Verify that LoginView throttles excessive anonymous login attempts."""
        for _ in range(10):
            resp = self.client.post('/api/v1/auth/login/', {
                'email': 'wrong@example.com',
                'password': 'WrongPassword123!'
            })
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        # The 11th request within the minute must be throttled
        throttled_resp = self.client.post('/api/v1/auth/login/', {
            'email': 'wrong@example.com',
            'password': 'WrongPassword123!'
        })
        self.assertEqual(throttled_resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_login_rate_limiting_cache_behavior(self):
        """Verify that clearing throttle cache unblocks the throttled client."""
        for _ in range(10):
            self.client.post('/api/v1/auth/login/', {
                'email': 'wrong@example.com',
                'password': 'WrongPassword123!'
            })

        throttled_resp = self.client.post('/api/v1/auth/login/', {
            'email': 'wrong@example.com',
            'password': 'WrongPassword123!'
        })
        self.assertEqual(throttled_resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # Clear throttle cache -> immediately unblocked
        cache.clear()
        unblocked_resp = self.client.post('/api/v1/auth/login/', {
            'email': 'secure_user@example.com',
            'password': 'SuperSecretPassword123!'
        })
        self.assertEqual(unblocked_resp.status_code, status.HTTP_200_OK)

