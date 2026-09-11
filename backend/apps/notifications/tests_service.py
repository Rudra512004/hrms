from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.organization.models import Organization
from .models import Notification
from .services import NotificationService

User = get_user_model()

class NotificationServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Test Org')
        self.user = User.objects.create_user(email='test@example.com', password='password123')

    def test_create_in_app_notification_success(self):
        notification = NotificationService.create_in_app_notification(
            recipient=self.user,
            organization=self.org,
            notification_type='TEST_EVENT',
            title='Test Title',
            message='Test Message',
            reference_id='ref123'
        )
        
        self.assertIsNotNone(notification)
        self.assertEqual(notification.recipient, self.user)
        self.assertEqual(notification.organization, self.org)
        self.assertEqual(notification.notification_type, 'TEST_EVENT')
        self.assertEqual(notification.title, 'Test Title')
        self.assertEqual(notification.message, 'Test Message')
        self.assertEqual(notification.reference_id, 'ref123')
        
        self.assertEqual(Notification.objects.count(), 1)

    def test_create_in_app_notification_missing_recipient(self):
        notification = NotificationService.create_in_app_notification(
            recipient=None,
            organization=self.org,
            notification_type='TEST_EVENT',
            title='Test Title',
            message='Test Message'
        )
        self.assertIsNone(notification)
        self.assertEqual(Notification.objects.count(), 0)

    def test_create_in_app_notification_missing_org(self):
        notification = NotificationService.create_in_app_notification(
            recipient=self.user,
            organization=None,
            notification_type='TEST_EVENT',
            title='Test Title',
            message='Test Message'
        )
        self.assertIsNone(notification)
        self.assertEqual(Notification.objects.count(), 0)

    def test_create_in_app_notification_handles_exceptions_safely(self):
        # Passing an invalid type to organization will raise ValueError in Django,
        # but the service should catch it and return None without breaking the flow.
        notification = NotificationService.create_in_app_notification(
            recipient=self.user,
            organization="INVALID_ORG",
            notification_type='TEST_EVENT',
            title='Test Title',
            message='Test Message'
        )
        self.assertIsNone(notification)
