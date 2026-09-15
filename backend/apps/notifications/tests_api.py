from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.organization.models import Organization
from apps.employees.models import Employee
from .models import Notification
from .services import NotificationService

User = get_user_model()

class NotificationAPITests(APITestCase):
    def setUp(self):
        # Org A
        self.org_a = Organization.objects.create(name='Org A')
        self.user_a1 = User.objects.create_user(email='a1@example.com', password='password123')
        self.emp_a1 = Employee.objects.create(user=self.user_a1, organization=self.org_a, employee_code='A1')
        
        self.user_a2 = User.objects.create_user(email='a2@example.com', password='password123')
        self.emp_a2 = Employee.objects.create(user=self.user_a2, organization=self.org_a, employee_code='A2')

        # Org B
        self.org_b = Organization.objects.create(name='Org B')
        self.user_b1 = User.objects.create_user(email='b1@example.com', password='password123')
        self.emp_b1 = Employee.objects.create(user=self.user_b1, organization=self.org_b, employee_code='B1')

        # User with no org
        self.user_no_org = User.objects.create_user(email='noorg@example.com', password='password123')

        # Create notifications
        self.notif_a1_1 = NotificationService.create_in_app_notification(
            recipient=self.user_a1, organization=self.org_a, notification_type='TEST_1', title='T1', message='M1'
        )
        self.notif_a1_2 = NotificationService.create_in_app_notification(
            recipient=self.user_a1, organization=self.org_a, notification_type='TEST_2', title='T2', message='M2'
        )
        self.notif_a2 = NotificationService.create_in_app_notification(
            recipient=self.user_a2, organization=self.org_a, notification_type='TEST_A2', title='TA2', message='MA2'
        )
        self.notif_b1 = NotificationService.create_in_app_notification(
            recipient=self.user_b1, organization=self.org_b, notification_type='TEST_B1', title='TB1', message='MB1'
        )

    # 1. Authentication Tests
    def test_unauthenticated_access_rejected(self):
        response = self.client.get('/api/v1/notifications/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        response = self.client.post(f'/api/v1/notifications/{self.notif_a1_1.id}/read/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.client.post('/api/v1/notifications/read-all/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.client.get('/api/v1/notifications/unread-count/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # 2. List API & Organization Tests
    def test_list_notifications(self):
        self.client.force_authenticate(user=self.user_a1)
        response = self.client.get('/api/v1/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Assuming pagination returns 'results' or direct array depending on settings
        data = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(data), 2)
        
        # Test ordering (-created_at) -> notif_a1_2 should be first
        self.assertEqual(data[0]['id'], self.notif_a1_2.id)
        self.assertEqual(data[1]['id'], self.notif_a1_1.id)

        # Ensure no cross-user or cross-org visibility
        ids = [n['id'] for n in data]
        self.assertNotIn(self.notif_a2.id, ids)
        self.assertNotIn(self.notif_b1.id, ids)

    def test_no_org_returns_empty(self):
        self.client.force_authenticate(user=self.user_no_org)
        response = self.client.get('/api/v1/notifications/')
        data = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(data), 0)

    # 3. Read API Tests
    def test_mark_read_own(self):
        self.client.force_authenticate(user=self.user_a1)
        response = self.client.post(f'/api/v1/notifications/{self.notif_a1_1.id}/read/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.notif_a1_1.refresh_from_db()
        self.assertTrue(self.notif_a1_1.is_read)

        # Repeated call should be safe
        response = self.client.post(f'/api/v1/notifications/{self.notif_a1_1.id}/read/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_mark_read_other_user_idor(self):
        self.client.force_authenticate(user=self.user_a1)
        response = self.client.post(f'/api/v1/notifications/{self.notif_a2.id}/read/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        response = self.client.post(f'/api/v1/notifications/{self.notif_b1.id}/read/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_read_endpoint_cannot_update_other_fields(self):
        self.client.force_authenticate(user=self.user_a1)
        response = self.client.post(f'/api/v1/notifications/{self.notif_a1_1.id}/read/', {'title': 'Hacked', 'notification_type': 'HACK'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.notif_a1_1.refresh_from_db()
        self.assertNotEqual(self.notif_a1_1.title, 'Hacked')

    def test_retrieve_other_user_idor(self):
        self.client.force_authenticate(user=self.user_a1)
        response = self.client.get(f'/api/v1/notifications/{self.notif_a2.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # 4. Mark All Read
    def test_mark_all_read(self):
        self.client.force_authenticate(user=self.user_a1)
        response = self.client.post('/api/v1/notifications/read-all/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated_count'], 2)
        
        self.notif_a1_1.refresh_from_db()
        self.notif_a1_2.refresh_from_db()
        self.assertTrue(self.notif_a1_1.is_read)
        self.assertTrue(self.notif_a1_2.is_read)

        # Other users remain unread
        self.notif_a2.refresh_from_db()
        self.assertFalse(self.notif_a2.is_read)

    # 5. Unread Count
    def test_unread_count(self):
        self.client.force_authenticate(user=self.user_a1)
        response = self.client.get('/api/v1/notifications/unread-count/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['unread_count'], 2)

        # Mark one as read
        self.notif_a1_1.is_read = True
        self.notif_a1_1.save()

        response = self.client.get('/api/v1/notifications/unread-count/')
        self.assertEqual(response.data['unread_count'], 1)
