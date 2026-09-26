from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from apps.accounts.models import User
from apps.organization.models import Organization, Branch, Department, Team, Designation
from apps.employees.models import Employee
from apps.authorization.models import Role, Permission, RolePermission, UserRole, UserPermissionGrant
import uuid
from unittest.mock import patch

class PaginationAndFilteringTests(TestCase):
    def setUp(self):
        self.patcher = patch('apps.authorization.permissions.IsNetworkAllowed.has_permission', return_value=True)
        self.patcher.start()
        self.client = APIClient()
        self.org1 = Organization.objects.create(name='Org 1')
        self.org2 = Organization.objects.create(name='Org 2')
        
        self.branch1 = Branch.objects.create(name='Branch 1', organization=self.org1)
        self.branch2 = Branch.objects.create(name='Branch 2', organization=self.org1) # same org
        self.branch3 = Branch.objects.create(name='Branch 3', organization=self.org2) # diff org

        self.dept1 = Department.objects.create(name='Dept 1', branch=self.branch1)
        self.team1 = Team.objects.create(name='Team 1', department=self.dept1)
        self.desig1 = Designation.objects.create(name='Desig 1', organization=self.org1)
        
        self.dept2 = Department.objects.create(name='Dept 2', branch=self.branch2)
        self.team2 = Team.objects.create(name='Team 2', department=self.dept2)

        # Superuser
        self.superuser = User.objects.create_superuser(email='admin@org1.com', password='password')
        
        # User 1 (Authorized for Branch 1)
        self.user1 = User.objects.create_user(email='user1@org1.com', password='password', status='active')
        self.emp1 = Employee.objects.create(
            user=self.user1, organization=self.org1, branch=self.branch1,
            department=self.dept1, team=self.team1, designation=self.desig1,
            employee_code='E001'
        )

        # User 2 (In Branch 2)
        self.user2 = User.objects.create_user(email='user2@org1.com', password='password', status='active')
        self.emp2 = Employee.objects.create(
            user=self.user2, organization=self.org1, branch=self.branch2,
            department=self.dept2, team=self.team2, designation=self.desig1,
            employee_code='E002'
        )
        
        # User 3 (In Branch 3 - Org 2)
        self.user3 = User.objects.create_user(email='user3@org2.com', password='password', status='active')
        self.emp3 = Employee.objects.create(
            user=self.user3, organization=self.org2, branch=self.branch3,
            employee_code='E003'
        )

        # Add more employees to branch 1 to test pagination
        for i in range(25):
            u = User.objects.create_user(email=f'dummy{i}@org1.com', password='password', first_name=f'Dummy {i}', status='active')
            Employee.objects.create(
                user=u, organization=self.org1, branch=self.branch1,
                department=self.dept1, team=self.team1, designation=self.desig1,
                employee_code=f'D{i:03d}'
            )

        # Assign permissions
        perm = Permission.objects.create(name='employee.view', codename='employee.view', resource='employee', action='view')
        role1 = Role.objects.create(name='Manager B1', organization=self.org1)
        RolePermission.objects.create(role=role1, permission=perm)
        
        # Grant role1 to user1 for branch1
        UserRole.objects.create(user=self.user1, role=role1, scope='branch', branch=self.branch1)

        self.url = '/api/v1/employees/management/'

    def test_existing_non_paginated_requests_return_array(self):
        self.client.force_authenticate(user=self.superuser)
        res = self.client.get(self.url)
        if res.status_code != 200:
            print("ERROR", res.data)
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.data, list)
        self.assertEqual(len(res.data), 28) # All employees

    def test_paginate_true_returns_paginated_results(self):
        self.client.force_authenticate(user=self.superuser)
        res = self.client.get(self.url + '?paginate=true')
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.data, dict)
        self.assertIn('count', res.data)
        self.assertIn('next', res.data)
        self.assertIn('previous', res.data)
        self.assertIn('results', res.data)
        self.assertEqual(res.data['count'], 28)
        self.assertEqual(len(res.data['results']), 20) # Default page size

    def test_page_and_page_size_work_correctly(self):
        self.client.force_authenticate(user=self.superuser)
        res = self.client.get(self.url + '?paginate=true&page=2&page_size=10')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['results']), 10)
        
        res3 = self.client.get(self.url + '?paginate=true&page=3&page_size=10')
        self.assertEqual(len(res3.data['results']), 8)

    def test_maximum_page_size_is_enforced(self):
        self.client.force_authenticate(user=self.superuser)
        res = self.client.get(self.url + '?paginate=true&page_size=1000')
        self.assertEqual(res.status_code, 200)
        self.assertLessEqual(len(res.data['results']), 100) # Enforced by max_page_size=100

    def test_filtering_works_correctly(self):
        self.client.force_authenticate(user=self.superuser)
        res = self.client.get(self.url + f'?branch_id={self.branch2.id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1) # User 2

    def test_combined_filtering_and_pagination(self):
        self.client.force_authenticate(user=self.superuser)
        res = self.client.get(self.url + f'?paginate=true&branch_id={self.branch1.id}&page_size=15')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['count'], 26) # 25 dummies + User 1
        self.assertEqual(len(res.data['results']), 15)

    def test_unauthorized_branch_filtering_cannot_escape_rbac_scope(self):
        # User 1 is only authorized for Branch 1.
        self.client.force_authenticate(user=self.user1)
        
        # User 1 queries all (should only see Branch 1)
        res1 = self.client.get(self.url)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(len(res1.data), 26) # 25 dummies + User 1

        # User 1 tries to query Branch 2 using the filter
        res2 = self.client.get(self.url + f'?branch_id={self.branch2.id}')
        if res2.status_code != 200:
            print("RES2:", res2.content)
        self.assertEqual(res2.status_code, 200)
        # Should return empty, not branch 2 data, because get_queryset restricts to branch 1
        self.assertEqual(len(res2.data), 0)

    def test_unauthorized_organization_filtering_is_rejected_or_ignored(self):
        self.client.force_authenticate(user=self.user1)
        # User 1 tries to see Branch 3 (Org 2)
        res = self.client.get(self.url + f'?branch_id={self.branch3.id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 0)

    def tearDown(self):
        self.patcher.stop()
