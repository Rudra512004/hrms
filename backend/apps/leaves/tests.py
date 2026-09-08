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
        self.employee = Employee.objects.create(user=self.user, employee_code='EMP01', organization=self.org)

        self.manager_user = User.objects.create_user(email='manager@example.com', password='Password123!', status='active')
        self.manager_employee = Employee.objects.create(user=self.manager_user, employee_code='MGR01', organization=self.org)

        self.leave_type = LeaveType.objects.create(organization=self.org, name='Sick Leave', annual_allocation=10)
        self.balance = LeaveBalance.objects.get(employee=self.employee, leave_type=self.leave_type)

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
            end_date=timezone.now().date() + timedelta(days=20),  # 20 days ensures it exceeds 10 even with weekends
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

class AdminLeaveTypeAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Test Org 2')
        
        self.superadmin = User.objects.create_user(email='super@example.com', password='Password123!', status='active', is_superuser=True)
        self.admin = User.objects.create_user(email='admin@example.com', password='Password123!', status='active')
        self.admin_employee = Employee.objects.create(user=self.admin, employee_code='ADM01', organization=self.org)
        
        self.employee = User.objects.create_user(email='emp2@example.com', password='Password123!', status='active')
        self.emp_profile = Employee.objects.create(user=self.employee, employee_code='EMP02', organization=self.org)
        
        self.leave_type = LeaveType.objects.create(organization=self.org, name='Initial Leave', annual_allocation=5)

    def test_superadmin_can_create(self):
        self.client.force_authenticate(user=self.superadmin)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            response = self.client.post(reverse('admin-leave-types-list'), {
                'name': 'New Leave',
                'description': 'Description',
                'annual_allocation': 15,
                'is_active': True
            })
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(LeaveType.objects.count(), 2)

    def test_authorized_admin_can_create(self):
        self.client.force_authenticate(user=self.admin)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            response = self.client.post(reverse('admin-leave-types-list'), {
                'name': 'Admin Leave',
                'annual_allocation': 10
            })
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_unauthorized_employee_cannot_create(self):
        self.client.force_authenticate(user=self.employee)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=False):
            response = self.client.post(reverse('admin-leave-types-list'), {
                'name': 'Emp Leave',
                'annual_allocation': 10
            })
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_request_returns_401(self):
        response = self.client.post(reverse('admin-leave-types-list'), {
            'name': 'Anon Leave',
            'annual_allocation': 10
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_duplicate_name_rejected(self):
        self.client.force_authenticate(user=self.superadmin)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            response = self.client.post(reverse('admin-leave-types-list'), {
                'name': 'Initial Leave',
                'annual_allocation': 10
            })
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_allocation_rejected(self):
        self.client.force_authenticate(user=self.superadmin)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            response = self.client.post(reverse('admin-leave-types-list'), {
                'name': 'Invalid Leave',
                'annual_allocation': -5
            })
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_works(self):
        self.client.force_authenticate(user=self.superadmin)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            response = self.client.patch(reverse('admin-leave-types-detail', kwargs={'pk': self.leave_type.id}), {
                'name': 'Updated Leave'
            })
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.leave_type.refresh_from_db()
            self.assertEqual(self.leave_type.name, 'Updated Leave')

    def test_referenced_leave_type_cannot_be_deleted(self):
        self.client.force_authenticate(user=self.superadmin)
        # Create a request to make it undeletable
        LeaveRequest.objects.create(
            employee=self.emp_profile, leave_type=self.leave_type,
            start_date=timezone.now().date() + timedelta(days=1),
            end_date=timezone.now().date() + timedelta(days=2),
            reason='Testing'
        )
        
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            response = self.client.delete(reverse('admin-leave-types-detail', kwargs={'pk': self.leave_type.id}))
            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
            self.assertEqual(LeaveType.objects.count(), 1)

    def test_unreferenced_leave_type_can_be_deleted(self):
        self.client.force_authenticate(user=self.superadmin)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            response = self.client.delete(reverse('admin-leave-types-detail', kwargs={'pk': self.leave_type.id}))
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            self.assertEqual(LeaveType.objects.count(), 0)

    def test_employee_facing_get_returns_configured(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.get(reverse('leave-types-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Initial Leave')

    def test_duration_days_excludes_weekends(self):
        # Monday to following Monday = 8 calendar days, 6 working days
        start = timezone.now().date()
        while start.weekday() != 0: # find a Monday
            start += timedelta(days=1)
        end = start + timedelta(days=7) # next Monday
        
        request = LeaveRequest(
            employee=self.emp_profile, leave_type=self.leave_type,
            start_date=start, end_date=end, reason='Weekend test'
        )
        self.assertEqual(request.duration_days, 6)

    def test_cannot_edit_approved_request(self):
        self.client.force_authenticate(user=self.employee)
        request = LeaveRequest.objects.create(
            employee=self.emp_profile, leave_type=self.leave_type,
            start_date=timezone.now().date() + timedelta(days=1),
            end_date=timezone.now().date() + timedelta(days=2),
            reason='Testing edit',
            status='approved'
        )
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            response = self.client.patch(reverse('leave-requests-detail', kwargs={'pk': request.id}), {
                'reason': 'Changed my mind'
            })
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deleting_approved_request_restores_balance(self):
        # First ensure there's a balance record
        balance = LeaveBalance.objects.get(employee=self.emp_profile, leave_type=self.leave_type)
        balance.used = 5
        balance.save()
        
        request = LeaveRequest.objects.create(
            employee=self.emp_profile, leave_type=self.leave_type,
            start_date=timezone.now().date() + timedelta(days=1),
            end_date=timezone.now().date() + timedelta(days=2),
            reason='Testing delete',
            status='approved'
        )
        
        # duration is roughly 2 days (assuming not weekend)
        duration = request.duration_days
        
        # delete request
        request.delete()
        
        balance.refresh_from_db()
        self.assertEqual(balance.used, 5 - duration)

    def test_cannot_delete_approved_request_via_api(self):
        self.client.force_authenticate(user=self.employee)
        req = LeaveRequest.objects.create(
            employee=self.emp_profile, leave_type=self.leave_type,
            start_date=timezone.now().date() + timedelta(days=5),
            end_date=timezone.now().date() + timedelta(days=6),
            reason='Testing API delete',
            status='approved'
        )
        response = self.client.delete(reverse('leave-requests-detail', kwargs={'pk': req.id}))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(LeaveRequest.objects.filter(id=req.id).exists())

    def test_can_delete_pending_request_via_api(self):
        self.client.force_authenticate(user=self.employee)
        req = LeaveRequest.objects.create(
            employee=self.emp_profile, leave_type=self.leave_type,
            start_date=timezone.now().date() + timedelta(days=5),
            end_date=timezone.now().date() + timedelta(days=6),
            reason='Testing pending delete',
            status='pending'
        )
        response = self.client.delete(reverse('leave-requests-detail', kwargs={'pk': req.id}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(LeaveRequest.objects.filter(id=req.id).exists())
