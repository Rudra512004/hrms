from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.organization.models import Organization
from .models import LeaveType, LeaveRequest, LeaveBalance
from apps.notifications.models import Notification
from datetime import timedelta, date
from django.utils import timezone
from unittest.mock import patch

User = get_user_model()

class LeaveNotificationIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Test Org')
        from apps.organization.models import Branch
        self.branch = self.org.branches.first() or Branch.objects.create(organization=self.org, name='Main')


        self.user = User.objects.create_user(email='emp@example.com', password='Password123!', status='active')
        self.employee = Employee.objects.create(user=self.user, employee_code='EMP01', organization=self.org, branch=self.branch)

        self.manager_user = User.objects.create_user(email='manager@example.com', password='Password123!', status='active', is_superuser=True)
        from apps.authorization.models import Role, UserRole, ScopeChoices, RolePermission, Permission
        from apps.organization.models import Organization as _PatchOrg
        _test_org = getattr(self, 'org', getattr(self, 'organization', getattr(self, 'org1', _PatchOrg.objects.first())))
        if _test_org:
            _role, _ = Role.objects.get_or_create(organization=_test_org, name='System Admin')
            for perm_code in ['attendance.view', 'attendance.manage', 'attendance.view_all', 'leave.view', 'leave.manage', 'leave.view_all', 'leave.verify', 'leave.manage_types', 'payroll.generate', 'payroll.approve', 'payroll.view', 'payroll.manage_compensation', 'payslip.view', 'payroll.view_sensitive']:
                action = perm_code.split('.')[1]
                resource = perm_code.split('.')[0]
                perm, _ = Permission.objects.get_or_create(codename=perm_code, defaults={'name': perm_code, 'resource': resource, 'action': action})
                RolePermission.objects.get_or_create(role=_role, permission=perm)
            UserRole.objects.get_or_create(user=self.manager_user, role=_role, scope=ScopeChoices.ORGANIZATION)

        self.leave_type = LeaveType.objects.create(organization=self.org, name='Sick Leave')
        from apps.leaves.models import LeaveCycle, LeaveBalance
        from datetime import date
        self.cycle = LeaveCycle.objects.create(branch=self.branch, name='C', start_date=date(2026,1,1), end_date=date(2026,12,31), is_active=True)

        from apps.leaves.models import BranchLeavePolicy
        if not BranchLeavePolicy.objects.filter(branch=self.branch, leave_type=self.leave_type).exists():
            BranchLeavePolicy.objects.create(
                branch=self.branch, leave_type=self.leave_type,
                monthly_allocation=1,
                half_day_allowed=True,
                cancellation_allowed=True,
                negative_balance_allowed=False,
                advance_notice_days=0,
                requires_supporting_document=False
            )
        self.balance = LeaveBalance.objects.create(employee=self.employee, leave_type=self.leave_type, branch=self.branch, leave_cycle=self.cycle, allocated=10, used=0)

    @patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True)
    @patch('apps.authorization.services.AuthorizationService.get_authorized_branches')
    def test_leave_approved_notification(self, mock_auth_branches, mock_perm):
        mock_auth_branches.return_value = [self.branch]
        base_date = date(2026, 10, 5)
        leave = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=base_date, end_date=base_date + timedelta(days=1),
            reason='Testing approval'
        )

        self.client.force_authenticate(user=self.manager_user)
        url = reverse('leave-requests-approve', kwargs={'pk': leave.pk}) + f"?organization_id={self.org.id}"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        # Verify notification
        notifs = Notification.objects.filter(recipient=self.user)
        self.assertEqual(notifs.count(), 1)
        notif = notifs.first()
        self.assertEqual(notif.notification_type, 'LEAVE_APPROVED')
        self.assertEqual(notif.organization, self.org)
        self.assertEqual(notif.reference_id, str(leave.id))
        self.assertIn('approved', notif.message.lower())

    @patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True)
    @patch('apps.authorization.services.AuthorizationService.get_authorized_branches')
    def test_leave_rejected_notification(self, mock_auth_branches, mock_perm):
        mock_auth_branches.return_value = [self.branch]
        base_date = date(2026, 10, 5)
        leave = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=base_date, end_date=base_date + timedelta(days=1),
            reason='Testing rejection'
        )

        self.client.force_authenticate(user=self.manager_user)
        url = reverse('leave-requests-reject', kwargs={'pk': leave.pk}) + f"?organization_id={self.org.id}"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        notifs = Notification.objects.filter(recipient=self.user)
        self.assertEqual(notifs.count(), 1)
        self.assertEqual(notifs.first().notification_type, 'LEAVE_REJECTED')

    @patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True)
    @patch('apps.authorization.services.AuthorizationService.get_authorized_branches')
    def test_leave_cancelled_by_admin_notification(self, mock_auth_branches, mock_perm):
        mock_auth_branches.return_value = [self.branch]
        base_date = timezone.now().date() + timedelta(days=5)
        leave = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=base_date, end_date=base_date + timedelta(days=1),
            reason='Testing cancellation'
        )

        self.client.force_authenticate(user=self.manager_user)
        url = reverse('leave-requests-cancel', kwargs={'pk': leave.pk}) + f"?organization_id={self.org.id}"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        notifs = Notification.objects.filter(recipient=self.user)
        self.assertEqual(notifs.count(), 1)
        self.assertEqual(notifs.first().notification_type, 'LEAVE_CANCELLED')

    @patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True)
    @patch('apps.authorization.services.AuthorizationService.get_authorized_branches')
    def test_leave_cancelled_by_self_no_notification(self, mock_auth_branches, mock_perm):
        mock_auth_branches.return_value = [self.branch]
        base_date = timezone.now().date() + timedelta(days=5)
        leave = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=base_date, end_date=base_date + timedelta(days=1),
            reason='Testing cancellation'
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('leave-requests-cancel', kwargs={'pk': leave.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        notifs = Notification.objects.filter(recipient=self.user)
        self.assertEqual(notifs.count(), 0)

