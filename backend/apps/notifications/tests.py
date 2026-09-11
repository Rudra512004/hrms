from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.organization.models import Organization
from .models import Notification

User = get_user_model()

class NotificationModelTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(email='test1@example.com', password='password123')
        self.user2 = User.objects.create_user(email='test2@example.com', password='password123')
        self.org = Organization.objects.create(name='Test Org')

    def test_notification_creation_and_defaults(self):
        """Test basic creation and that default values (is_read, created_at) are set correctly."""
        notification = Notification.objects.create(
            recipient=self.user1,
            organization=self.org,
            notification_type='TEST_TYPE',
            title='Test Title',
            message='Test message content'
        )
        
        self.assertEqual(notification.recipient, self.user1)
        self.assertEqual(notification.organization, self.org)
        self.assertEqual(notification.notification_type, 'TEST_TYPE')
        self.assertEqual(notification.title, 'Test Title')
        self.assertEqual(notification.message, 'Test message content')
        self.assertFalse(notification.is_read)
        self.assertIsNotNone(notification.created_at)
        self.assertEqual(notification.reference_id, '')

    def test_notification_with_reference(self):
        """Test creating a notification with an optional reference_id."""
        notification = Notification.objects.create(
            recipient=self.user1,
            organization=self.org,
            notification_type='LEAVE_APPROVED',
            title='Leave Approved',
            message='Your leave has been approved.',
            reference_id='leave_123'
        )
        
        self.assertEqual(notification.reference_id, 'leave_123')
        self.assertEqual(notification.organization, self.org)

    def test_notification_ordering(self):
        """Test that notifications are ordered by -created_at by default."""
        notif1 = Notification.objects.create(
            recipient=self.user1,
            organization=self.org,
            title='First',
            message='First msg',
            notification_type='TYPE'
        )
        notif2 = Notification.objects.create(
            recipient=self.user1,
            organization=self.org,
            title='Second',
            message='Second msg',
            notification_type='TYPE'
        )
        
        notifications = Notification.objects.all()
        self.assertEqual(list(notifications), [notif2, notif1])

    def test_recipient_relationship(self):
        """Test the related_name from User to Notifications."""
        Notification.objects.create(
            recipient=self.user1,
            organization=self.org,
            title='For User 1',
            message='Msg 1',
            notification_type='TYPE'
        )
        Notification.objects.create(
            recipient=self.user2,
            organization=self.org,
            title='For User 2',
            message='Msg 2',
            notification_type='TYPE'
        )
        
        self.assertEqual(self.user1.notifications.count(), 1)
        self.assertEqual(self.user1.notifications.first().title, 'For User 1')
        self.assertEqual(self.user2.notifications.count(), 1)

    def test_organization_relationship(self):
        """Test the related_name from Organization to Notifications."""
        Notification.objects.create(
            recipient=self.user1,
            organization=self.org,
            title='For Org',
            message='Msg',
            notification_type='TYPE'
        )
        
        self.assertEqual(self.org.notifications.count(), 1)
        self.assertEqual(self.org.notifications.first().recipient, self.user1)

    def test_str_representation(self):
        """Test the __str__ method."""
        notif = Notification.objects.create(
            recipient=self.user1,
            organization=self.org,
            title='Welcome',
            message='Hello',
            notification_type='TYPE'
        )
        
        self.assertEqual(str(notif), f"To {self.user1}: Welcome (Unread)")
        notif.is_read = True
        notif.save()
        self.assertEqual(str(notif), f"To {self.user1}: Welcome (Read)")
