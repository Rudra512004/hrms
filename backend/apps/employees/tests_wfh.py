from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from apps.organization.models import Organization
from apps.employees.models import Employee, WFHRequest
from apps.authorization.models import Permission, Role, RolePermission, UserRole
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class WFHRequestTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Test Org')

        self.employee_user = User.objects.create_user(email='emp@example.com', password='Password123!', status='active')
        self.employee = Employee.objects.create(user=self.employee_user, employee_code='EMP001')

        self.manager_user = User.objects.create_user(email='mgr@example.com', password='Password123!', status='active')
        self.manager_employee = Employee.objects.create(user=self.manager_user, employee_code='EMP002')

        self.perm_req = Permission.objects.create(name='Request WFH', codename='wfh.request', resource='wfh', action='request')
        self.perm_appr = Permission.objects.create(name='Approve WFH', codename='wfh.approve', resource='wfh', action='approve')
        self.perm_view = Permission.objects.create(name='View WFH', codename='wfh.view', resource='wfh', action='view')

        self.emp_role = Role.objects.create(organization=self.org, name='Employee')
        RolePermission.objects.create(role=self.emp_role, permission=self.perm_req)
        UserRole.objects.create(user=self.employee_user, role=self.emp_role)

        self.mgr_role = Role.objects.create(organization=self.org, name='Manager')
        RolePermission.objects.create(role=self.mgr_role, permission=self.perm_appr)
        RolePermission.objects.create(role=self.mgr_role, permission=self.perm_view)
        UserRole.objects.create(user=self.manager_user, role=self.mgr_role)

    def test_employee_creates_wfh(self):
        self.client.force_authenticate(user=self.employee_user)
        now = timezone.now()
        data = {
            'start_at': now + timedelta(days=1),
            'end_at': now + timedelta(days=2),
            'reason': 'Sick'
        }
        response = self.client.post('/api/v1/employees/wfh-requests/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(WFHRequest.objects.count(), 1)
        # Verify employee mapping
        self.assertEqual(WFHRequest.objects.first().employee, self.employee)

    def test_employee_cannot_approve_own(self):
        self.client.force_authenticate(user=self.employee_user)
        now = timezone.now()
        wfh = WFHRequest.objects.create(
            employee=self.employee, start_at=now, end_at=now+timedelta(days=1), status='pending'
        )
        response = self.client.post(f'/api/v1/employees/wfh-requests/{wfh.id}/approve/')
        self.assertEqual(response.status_code, 403)

        # Give approve permission to employee for testing self-approval block
        RolePermission.objects.create(role=self.emp_role, permission=self.perm_appr)
        response = self.client.post(f'/api/v1/employees/wfh-requests/{wfh.id}/approve/')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['detail'], 'Cannot approve own request.')

    def test_manager_approves_wfh(self):
        now = timezone.now()
        wfh = WFHRequest.objects.create(
            employee=self.employee, start_at=now, end_at=now+timedelta(days=1), status='pending'
        )
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.post(f'/api/v1/employees/wfh-requests/{wfh.id}/approve/', {'reviewer_comment': 'OK'})
        self.assertEqual(response.status_code, 200)
        wfh.refresh_from_db()
        self.assertEqual(wfh.status, 'approved')
        self.assertEqual(wfh.reviewer_comment, 'OK')
        self.assertEqual(wfh.reviewed_by, self.manager_user)
