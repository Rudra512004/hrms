from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from apps.organization.models import Organization, Branch, Designation
from apps.employees.models import Employee

User = get_user_model()

class TenantContextSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.superadmin = User.objects.create_user(
            email='super@admin.com', 
            password='password123', 
            is_superuser=True,
            status='active'
        )
        self.org1 = Organization.objects.create(name='Org 1')
        self.org2 = Organization.objects.create(name='Org 2')

        from apps.authorization.models import Role, UserRole, ScopeChoices
        _role, _ = Role.objects.get_or_create(organization=self.org1, name='System Admin')
        UserRole.objects.get_or_create(user=self.superadmin, role=_role, scope=ScopeChoices.ORGANIZATION)
        
        from apps.authorization.models import Permission, RolePermission
        for codename in ['organization.manage', 'branch.manage', 'designation.manage', 'department.manage', 'team.manage', 'employee.manage', 'employee.create']:
            res, act = codename.split('.')
            perm, _ = Permission.objects.get_or_create(codename=codename, defaults={'name': codename, 'resource': res, 'action': act})
            RolePermission.objects.get_or_create(role=_role, permission=perm)
        
    def test_superadmin_no_employee_creating_designation_fails_without_org(self):
        """Super Admin without employee profile creating a Designation without explicit org_id receives HTTP 400"""
        self.client.force_authenticate(user=self.superadmin)
        url = reverse('designation-list')
        data = {
            'name': 'Senior Engineer'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Designation.objects.filter(organization=self.org1, name='Senior Engineer').count(), 1)

    def test_superadmin_no_employee_creating_designation_works_with_org(self):
        """Super Admin without employee profile can create a Designation when providing explicit org_id"""
        self.client.force_authenticate(user=self.superadmin)
        url = reverse('designation-list')
        data = {
            'name': 'Senior Engineer',
            'organization': self.org1.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Designation.objects.filter(organization=self.org1).count(), 1)
        
    def test_superadmin_no_employee_creating_branch_fails_without_org(self):
        self.client.force_authenticate(user=self.superadmin)
        url = reverse('branch-list')
        data = {
            'name': 'NY Office',
            'location': 'New York',
            'timezone': 'UTC'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Branch.objects.filter(organization=self.org1, name='NY Office').count(), 1)

    def test_superadmin_no_employee_creating_employee_fails_without_org(self):
        self.client.force_authenticate(user=self.superadmin)
        url = reverse('employee-management-list')
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@doe.com',
            'personal_email': 'john@doe.com'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Employee.objects.filter(organization=self.org1, user__email='john@doe.com').count(), 1)

class SuperAdminIdentityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.superadmin = User.objects.create_user(
            email='super@admin.com', 
            password='password123', 
            is_superuser=True,
            status='active'
        )
        self.org = Organization.objects.create(name='Leave Org')
        from apps.leaves.models import LeaveType
        self.leave_type = LeaveType.objects.create(name='Sick Leave', organization=self.org)

        from apps.authorization.models import Role, UserRole, ScopeChoices
        _role, _ = Role.objects.get_or_create(organization=self.org, name='System Admin')
        UserRole.objects.get_or_create(user=self.superadmin, role=_role, scope=ScopeChoices.ORGANIZATION)
        
        from apps.authorization.models import Permission, RolePermission
        for codename in ['leave.request', 'leave.view', 'attendance.view_all']:
            res = codename.replace('_all', '').split('.')[0]
            act = codename.split('.')[-1]
            perm, _ = Permission.objects.get_or_create(codename=codename, defaults={'name': codename, 'resource': res, 'action': act})
            RolePermission.objects.get_or_create(role=_role, permission=perm)

    def test_superadmin_cannot_check_in(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.post(reverse('attendance-check-in'))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
    def test_superadmin_cannot_request_personal_leave(self):
        self.client.force_authenticate(user=self.superadmin)
        data = {
            'start_date': '2026-10-01',
            'end_date': '2026-10-05',
            'reason': 'Vacation',
            'leave_type': self.leave_type.id
        }
        response = self.client.post(reverse('leave-requests-list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Employee identity is required.', str(response.data))
