from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.organization.models import Organization, Department, Designation
from apps.notifications.models import Notification
from unittest.mock import patch
from django.utils import timezone

User = get_user_model()

class EmployeeNotificationIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Emp Org')

        self.user = User.objects.create_user(email='emp_test@example.com', password='Password123!', status='active')
        self.employee = Employee.objects.create(user=self.user, employee_code='EMP01', organization=self.org)

        self.admin_user = User.objects.create_user(email='admin_emp@example.com', password='Password123!', status='active', is_superuser=True)

        self.department = Department.objects.create(organization=self.org, name='Engineering')
        self.designation = Designation.objects.create(organization=self.org, name='Senior Engineer')

    @patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True)
    def test_employee_transfer_notification(self, mock_perm):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(f'/api/v1/employees/management/{self.employee.pk}/transfer/', {
            'department': self.department.id,
            'effective_date': timezone.now().date().isoformat(),
            'reason': 'Team restructuring'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        notifs = Notification.objects.filter(recipient=self.user)
        self.assertEqual(notifs.count(), 1)
        notif = notifs.first()
        self.assertEqual(notif.notification_type, 'EMPLOYEE_TRANSFER')
        self.assertEqual(notif.organization, self.org)
        self.assertIn('Engineering', notif.message)

    @patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True)
    def test_employee_promotion_notification(self, mock_perm):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(f'/api/v1/employees/management/{self.employee.pk}/promote/', {
            'designation': self.designation.id,
            'effective_date': timezone.now().date().isoformat(),
            'reason': 'Good performance'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        notifs = Notification.objects.filter(recipient=self.user)
        self.assertEqual(notifs.count(), 1)
        notif = notifs.first()
        self.assertEqual(notif.notification_type, 'EMPLOYEE_PROMOTION')
        self.assertEqual(notif.organization, self.org)
        self.assertIn('Senior Engineer', notif.message)
