from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.organization.models import Organization
from .models import LeaveType, LeaveBalance, LeaveRequest
from datetime import timedelta
from django.utils import timezone

User = get_user_model()

class LeaveAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Test Org')

        self.user = User.objects.create_user(email='emp@example.com', password='Password123!', status='active')
        self.employee = Employee.objects.create(user=self.user, employee_code='EMP01')

        self.manager_user = User.objects.create_user(email='manager@example.com', password='Password123!', status='active')
        self.manager_employee = Employee.objects.create(user=self.manager_user, employee_code='MGR01')

        self.leave_type = LeaveType.objects.create(organization=self.org, name='Sick Leave', annual_allocation=10)
        self.balance = LeaveBalance.objects.create(employee=self.employee, leave_type=self.leave_type, allocated=10, used=0)

        self.external_ip = '198.51.100.5'

    def test_leave_request_creation_not_blocked_by_network(self):
        # Even from an external IP without WFH, leave request should be allowed
        self.client.force_authenticate(user=self.user)
        # Assuming user has permission 'leave.request' (In reality, dynamic RBAC mock or implicit test)
        # Mocking dynamic RBAC requires setting up Role/Permissions which might be complex,
        # so let's bypass permission checks just for the sake of the test if needed, or rely on setup.
        # Actually, in this test environment, we might need to assign the permission or mock the service.
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            response = self.client.post(reverse('leave-requests-list'), {
                'leave_type': self.leave_type.id,
                'start_date': (timezone.now().date() + timedelta(days=1)).isoformat(),
                'end_date': (timezone.now().date() + timedelta(days=2)).isoformat(),
                'reason': 'Not feeling well'
            }, REMOTE_ADDR=self.external_ip)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_invalid_date_range(self):
        self.client.force_authenticate(user=self.user)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            response = self.client.post(reverse('leave-requests-list'), {
                'leave_type': self.leave_type.id,
                'start_date': (timezone.now().date() + timedelta(days=2)).isoformat(),
                'end_date': (timezone.now().date() + timedelta(days=1)).isoformat(),
                'reason': 'Invalid dates'
            })
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_approve_leave_request(self):
        request = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=timezone.now().date() + timedelta(days=1),
            end_date=timezone.now().date() + timedelta(days=2),
            reason='Testing approval'
        )
        self.client.force_authenticate(user=self.manager_user)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            response = self.client.post(reverse('leave-requests-approve', kwargs={'pk': request.pk}))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.balance.refresh_from_db()
            self.assertEqual(self.balance.used, 2)
            self.assertEqual(self.balance.remaining, 8)

    def test_cannot_approve_own_request(self):
        request = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=timezone.now().date() + timedelta(days=1),
            end_date=timezone.now().date() + timedelta(days=2),
            reason='Testing approval'
        )
        self.client.force_authenticate(user=self.user)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            response = self.client.post(reverse('leave-requests-approve', kwargs={'pk': request.pk}))
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_insufficient_balance(self):
        request = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=timezone.now().date() + timedelta(days=1),
            end_date=timezone.now().date() + timedelta(days=12),  # 12 days > 10
            reason='Long vacation'
        )
        self.client.force_authenticate(user=self.manager_user)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            response = self.client.post(reverse('leave-requests-approve', kwargs={'pk': request.pk}))
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.balance.refresh_from_db()
            self.assertEqual(self.balance.used, 0)

    def test_rejected_does_not_consume_balance(self):
        request = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=timezone.now().date() + timedelta(days=1),
            end_date=timezone.now().date() + timedelta(days=2),
            reason='Testing rejection'
        )
        self.client.force_authenticate(user=self.manager_user)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            response = self.client.post(reverse('leave-requests-reject', kwargs={'pk': request.pk}))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.balance.refresh_from_db()
            self.assertEqual(self.balance.used, 0)
