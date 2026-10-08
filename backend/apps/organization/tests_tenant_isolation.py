from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.organization.models import Organization, Branch, Department, Team
from apps.employees.models import Employee
from apps.authorization.models import Role, Permission, UserRole, ScopeChoices
from apps.leaves.models import LeaveType

User = get_user_model()

class TenantIsolationTests(TestCase):
    def setUp(self):
        # Create Tenant A
        self.org_a = Organization.objects.create(name='Tenant A')
        self.branch_a = Branch.objects.create(organization=self.org_a, name='Branch A')
        self.dept_a = Department.objects.create(branch=self.branch_a, name='Dept A')
        self.team_a = Team.objects.create(department=self.dept_a, name='Team A')
        self.leave_type_a = LeaveType.objects.create(organization=self.org_a, name='Leave A')

        self.user_a = User.objects.create_user(email='user_a@tenant_a.com', password='password', status='active')
        from apps.organization.models import OrganizationMembership
        OrganizationMembership.objects.create(user=self.user_a, organization=self.org_a, status='active')
        self.emp_a = Employee.objects.create(
            user=self.user_a, organization=self.org_a, branch=self.branch_a, 
            department=self.dept_a, team=self.team_a, employee_code='EMP-A'
        )

        # Create Tenant B
        self.org_b = Organization.objects.create(name='Tenant B')
        self.branch_b = Branch.objects.create(organization=self.org_b, name='Branch B')
        self.dept_b = Department.objects.create(branch=self.branch_b, name='Dept B')
        self.team_b = Team.objects.create(department=self.dept_b, name='Team B')
        self.leave_type_b = LeaveType.objects.create(organization=self.org_b, name='Leave B')

        self.user_b = User.objects.create_user(email='user_b@tenant_b.com', password='password', status='active')
        OrganizationMembership.objects.create(user=self.user_b, organization=self.org_b, status='active')
        self.emp_b = Employee.objects.create(
            user=self.user_b, organization=self.org_b, branch=self.branch_b, 
            department=self.dept_b, team=self.team_b, employee_code='EMP-B'
        )

        # Set up permissions for User A (Tenant Owner / Admin)
        self.role_a = Role.objects.create(organization=self.org_a, name='Admin A', is_active=True)
        # Create required permissions for tests
        for codename in ['department.view', 'department.manage', 'employee.view', 'employee.manage', 'employee.update', 'leave.view', 'leave.manage', 'leave_type.manage', 'attendance.view', 'attendance.manage']:
            Permission.objects.get_or_create(codename=codename, is_active=True, defaults={'name': codename, 'resource': codename.split('.')[0], 'action': codename.split('.')[1]})

        all_perms = Permission.objects.filter(is_active=True)
        from apps.authorization.models import RolePermission
        for p in all_perms:
            RolePermission.objects.create(role=self.role_a, permission=p)
        UserRole.objects.create(user=self.user_a, role=self.role_a, scope=ScopeChoices.ORGANIZATION)
        
        self.client_a = APIClient()
        self.client_a.force_authenticate(user=self.user_a)

        # Patch NetworkAccessService
        from unittest.mock import patch
        self.patcher = patch('apps.authorization.network.NetworkAccessService.is_remote_access_allowed', return_value=True)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_tenant_a_cannot_get_tenant_b_departments(self):
        url = reverse('department-detail', kwargs={'pk': self.dept_b.id})
        response = self.client_a.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tenant_a_cannot_update_tenant_b_departments(self):
        url = reverse('department-detail', kwargs={'pk': self.dept_b.id})
        response = self.client_a.patch(url, {'name': 'Hacked Dept B'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tenant_a_cannot_delete_tenant_b_departments(self):
        url = reverse('department-detail', kwargs={'pk': self.dept_b.id})
        response = self.client_a.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Department.objects.filter(id=self.dept_b.id).exists())

    def test_tenant_a_cannot_assign_tenant_b_branch_to_department(self):
        url = reverse('department-list')
        response = self.client_a.post(url, {
            'name': 'New Dept in B',
            'branch': self.branch_b.id
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('branch', response.data)

    def test_tenant_a_cannot_get_tenant_b_employees(self):
        url = reverse('employee-management-detail', kwargs={'pk': self.emp_b.id})
        response = self.client_a.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tenant_a_cannot_update_tenant_b_employees(self):
        url = reverse('employee-management-detail', kwargs={'pk': self.emp_b.id})
        response = self.client_a.patch(url, {'first_name': 'Hacked'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tenant_a_cannot_get_tenant_b_leave_types(self):
        url = reverse('admin-leave-types-detail', kwargs={'pk': self.leave_type_b.id})
        response = self.client_a.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_missing_organization_context_fails_closed(self):
        # User A becomes a multi-org user by joining Org B
        from apps.organization.models import OrganizationMembership
        OrganizationMembership.objects.create(user=self.user_a, organization=self.org_b, status='active')
        
        # Now User A makes a request WITHOUT the X-Organization-Id header
        url = reverse('department-list')
        response = self.client_a.get(url)
        
        # It must fail closed (403 Forbidden) instead of guessing
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Directly test the AuthorizationService._resolve_organization
        from apps.authorization.services import AuthorizationService
        
        class DummyRequest:
            def __init__(self, user):
                self.user = user
                self.headers = {}
                self.organization_context = None
                
        dummy_req = DummyRequest(self.user_a)
        resolved_org = AuthorizationService._resolve_organization(dummy_req)
        
        # It must be None because we should NEVER guess based on employees.first().organization
        self.assertIsNone(resolved_org, "Must NOT guess the organization based on fallback")
