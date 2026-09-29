from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.organization.models import Organization, Branch, Department, Team
from apps.employees.models import Employee, EmploymentStatus
from apps.authorization.models import Role, Permission, UserRole, RolePermission, ScopeChoices

User = get_user_model()

class BranchIsolationSecurityTests(TestCase):
    """
    Security regression test suite verifying branch-level isolation and IDOR prevention
    for Branch-scoped roles in Organization modules (Department, Team).
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Create Organization
        self.org = Organization.objects.create(name='Tenant Alpha', status='active')

        # 2. Create Branches
        self.branch_1 = Branch.objects.create(organization=self.org, name='Branch 1', radius=100)
        self.branch_2 = Branch.objects.create(organization=self.org, name='Branch 2', radius=100)

        # 3. Permissions required
        self.perm_codenames = [
            'department.view', 'department.manage',
            'team.view', 'team.manage',
        ]
        self.permissions = {}
        for code in self.perm_codenames:
            res, act = code.split('.')
            perm, _ = Permission.objects.get_or_create(
                codename=code,
                defaults={'name': code, 'resource': res, 'action': act}
            )
            self.permissions[code] = perm

        # 4. Create User scoped to Branch 1 ONLY
        self.user_branch1 = User.objects.create_user(email='b1_admin@alpha.local', password='Password123!', status='active')
        self.emp_branch1 = Employee.objects.create(
            user=self.user_branch1,
            organization=self.org,
            branch=self.branch_1,
            employee_code='EMP-B1',
            employment_status=EmploymentStatus.ACTIVE
        )
        self.role_branch1 = Role.objects.create(organization=self.org, name='Branch 1 Admin Role')
        for perm in self.permissions.values():
            RolePermission.objects.create(role=self.role_branch1, permission=perm)
        
        # Assign role with BRANCH scope to Branch 1
        UserRole.objects.create(
            user=self.user_branch1, 
            role=self.role_branch1,
            scope=ScopeChoices.BRANCH,
            branch=self.branch_1
        )

        # 5. Create resources in Branch 1 and Branch 2
        self.dept_b1 = Department.objects.create(branch=self.branch_1, name='Dept B1')
        self.dept_b2 = Department.objects.create(branch=self.branch_2, name='Dept B2')

        self.team_b1 = Team.objects.create(department=self.dept_b1, name='Team B1')
        self.team_b2 = Team.objects.create(department=self.dept_b2, name='Team B2')

    def test_branch_isolation_department_list(self):
        """User scoped to Branch 1 should only see Branch 1 departments."""
        self.client.force_authenticate(user=self.user_branch1)
        response = self.client.get('/api/v1/organization/departments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dept_ids = [d['id'] for d in response.data]
        
        self.assertIn(self.dept_b1.id, dept_ids)
        self.assertNotIn(self.dept_b2.id, dept_ids)

    def test_branch_isolation_department_retrieve_idor(self):
        """User scoped to Branch 1 cannot retrieve Branch 2 department."""
        self.client.force_authenticate(user=self.user_branch1)
        response = self.client.get(f'/api/v1/organization/departments/{self.dept_b2.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_branch_isolation_department_create_payload_injection(self):
        """User scoped to Branch 1 cannot create a department in Branch 2."""
        self.client.force_authenticate(user=self.user_branch1)
        payload = {'name': 'Hacked Dept', 'branch': self.branch_2.id}
        response = self.client.post('/api/v1/organization/departments/', data=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('branch', response.data)

    def test_branch_isolation_team_list(self):
        """User scoped to Branch 1 should only see Branch 1 teams."""
        self.client.force_authenticate(user=self.user_branch1)
        response = self.client.get('/api/v1/organization/teams/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        team_ids = [t['id'] for t in response.data]
        
        self.assertIn(self.team_b1.id, team_ids)
        self.assertNotIn(self.team_b2.id, team_ids)

    def test_branch_isolation_team_retrieve_idor(self):
        """User scoped to Branch 1 cannot retrieve Branch 2 team."""
        self.client.force_authenticate(user=self.user_branch1)
        response = self.client.get(f'/api/v1/organization/teams/{self.team_b2.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_branch_isolation_team_create_payload_injection(self):
        """User scoped to Branch 1 cannot create a team in Branch 2 department."""
        self.client.force_authenticate(user=self.user_branch1)
        payload = {'name': 'Hacked Team', 'department': self.dept_b2.id}
        response = self.client.post('/api/v1/organization/teams/', data=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('department', response.data)
