from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.organization.models import Organization
from .models import LeaveType, LeaveRequest, LeaveBalance
from apps.notifications.models import Notification
from datetime import timedelta
from django.utils import timezone
from unittest.mock import patch

User = get_user_model()

class LeaveNotificationIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Test Org')

        self.user = User.objects.create_user(email='emp@example.com', password='Password123!', status='active')
        self.employee = Employee.objects.create(user=self.user, employee_code='EMP01', organization=self.org)

        self.manager_user = User.objects.create_user(email='manager@example.com', password='Password123!', status='active', is_superuser=True)

        self.leave_type = LeaveType.objects.create(organization=self.org, name='Sick Leave', annual_allocation=10)

    @patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True)
    def test_leave_approved_notification(self, mock_perm):
        base_date = timezone.now().date()
        leave = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=base_date, end_date=base_date + timedelta(days=1),
            reason='Testing approval'
        )

        self.client.force_authenticate(user=self.manager_user)
        response = self.client.post(reverse('leave-requests-approve', kwargs={'pk': leave.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify notification
        notifs = Notification.objects.filter(recipient=self.user)
        self.assertEqual(notifs.count(), 1)
        notif = notifs.first()
        self.assertEqual(notif.notification_type, 'LEAVE_APPROVED')
        self.assertEqual(notif.organization, self.org)
        self.assertEqual(notif.reference_id, str(leave.id))
        self.assertIn('approved', notif.message.lower())

    @patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True)
    def test_leave_rejected_notification(self, mock_perm):
        base_date = timezone.now().date()
        leave = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=base_date, end_date=base_date + timedelta(days=1),
            reason='Testing rejection'
        )

        self.client.force_authenticate(user=self.manager_user)
        response = self.client.post(reverse('leave-requests-reject', kwargs={'pk': leave.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        notifs = Notification.objects.filter(recipient=self.user)
        self.assertEqual(notifs.count(), 1)
        self.assertEqual(notifs.first().notification_type, 'LEAVE_REJECTED')

    @patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True)
    def test_leave_cancelled_by_admin_notification(self, mock_perm):
        base_date = timezone.now().date()
        leave = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=base_date, end_date=base_date + timedelta(days=1),
            reason='Testing cancellation'
        )

        self.client.force_authenticate(user=self.manager_user)
        response = self.client.post(reverse('leave-requests-cancel', kwargs={'pk': leave.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        notifs = Notification.objects.filter(recipient=self.user)
        self.assertEqual(notifs.count(), 1)
        self.assertEqual(notifs.first().notification_type, 'LEAVE_CANCELLED')
        
    @patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True)
    def test_leave_cancelled_by_self_no_notification(self, mock_perm):
        base_date = timezone.now().date()
        leave = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=base_date, end_date=base_date + timedelta(days=1),
            reason='Testing cancellation'
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('leave-requests-cancel', kwargs={'pk': leave.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        notifs = Notification.objects.filter(recipient=self.user)
        self.assertEqual(notifs.count(), 0)
