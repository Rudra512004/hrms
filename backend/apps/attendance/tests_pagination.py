from datetime import date, timedelta
from unittest.mock import patch
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.organization.models import Organization, Branch, Department, Team
from apps.employees.models import Employee
from apps.authorization.models import Role, Permission, RolePermission, UserRole
from apps.attendance.models import Attendance

User = get_user_model()

class AttendancePaginationTests(TestCase):
    def setUp(self):
        self.patcher = patch('apps.authorization.permissions.IsNetworkAllowed.has_permission', return_value=True)
        self.patcher.start()
        self.client = APIClient()

        # Organization & Hierarchy
        self.org1 = Organization.objects.create(name='Attendance Org 1')
        self.org2 = Organization.objects.create(name='Attendance Org 2')

        self.branch1 = Branch.objects.create(organization=self.org1, name='Branch A')
        self.branch2 = Branch.objects.create(organization=self.org1, name='Branch B')
        self.branch3 = Branch.objects.create(organization=self.org2, name='Branch C')

        self.dept1 = Department.objects.create(branch=self.branch1, name='Engineering')
        self.team1 = Team.objects.create(department=self.dept1, name='Backend')

        self.dept2 = Department.objects.create(branch=self.branch2, name='Design')
        self.team2 = Team.objects.create(department=self.dept2, name='UI')

        # Superuser
        self.superuser = User.objects.create_superuser(email='super@att.com', password='password123')

        # Authorized Manager for Branch 1
        self.manager_user = User.objects.create_user(email='manager@att.com', password='password123', status='active')
        self.manager_emp = Employee.objects.create(
            user=self.manager_user, organization=self.org1, branch=self.branch1,
            department=self.dept1, team=self.team1, employee_code='M001'
        )

        perm, _ = Permission.objects.get_or_create(
            codename='attendance.view_all',
            resource='attendance',
            action='view_all',
            defaults={'name': 'View All Attendance'}
        )
        role = Role.objects.create(name='Attendance Manager', organization=self.org1)
        RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(user=self.manager_user, role=role, scope='branch', branch=self.branch1)

        # Unauthorized User
        self.unauth_user = User.objects.create_user(email='unauth@att.com', password='password123', status='active')
        Employee.objects.create(
            user=self.unauth_user, organization=self.org1, branch=self.branch1,
            employee_code='U001'
        )

        # Create employees and attendance records
        # 25 records in Branch 1
        today = timezone.now().date()
        for i in range(25):
            u = User.objects.create_user(email=f'emp{i}@att.com', password='password123', status='active')
            emp = Employee.objects.create(
                user=u, organization=self.org1, branch=self.branch1,
                department=self.dept1, team=self.team1, employee_code=f'E{i:03d}'
            )
            Attendance.objects.create(
                employee=emp,
                date=today - timedelta(days=i % 5),
                status='present'
            )

        # 5 records in Branch 2
        for j in range(5):
            u2 = User.objects.create_user(email=f'emp_b2_{j}@att.com', password='password123', status='active')
            emp2 = Employee.objects.create(
                user=u2, organization=self.org1, branch=self.branch2,
                department=self.dept2, team=self.team2, employee_code=f'EB2_{j:03d}'
            )
            Attendance.objects.create(
                employee=emp2,
                date=today,
                status='present'
            )

        self.url = '/api/v1/attendance/management/'

    def tearDown(self):
        self.patcher.stop()

    def test_unpaginated_request_returns_array(self):
        self.client.force_authenticate(user=self.superuser)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsInstance(res.data, list)
        self.assertEqual(len(res.data), 30)

    def test_paginate_true_returns_standard_drf_envelope(self):
        self.client.force_authenticate(user=self.superuser)
        res = self.client.get(f'{self.url}?paginate=true')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsInstance(res.data, dict)
        self.assertIn('count', res.data)
        self.assertIn('next', res.data)
        self.assertIn('previous', res.data)
        self.assertIn('results', res.data)
        self.assertEqual(res.data['count'], 30)
        self.assertEqual(len(res.data['results']), 20)

    def test_page_and_page_size_query_params(self):
        self.client.force_authenticate(user=self.superuser)
        res = self.client.get(f'{self.url}?paginate=true&page=2&page_size=10')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 30)
        self.assertEqual(len(res.data['results']), 10)

        res3 = self.client.get(f'{self.url}?paginate=true&page=3&page_size=10')
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res3.data['results']), 10)

    def test_filters_with_and_without_pagination(self):
        self.client.force_authenticate(user=self.superuser)
        # Unpaginated with branch_id
        res_unpaginated = self.client.get(f'{self.url}?branch_id={self.branch2.id}')
        self.assertEqual(res_unpaginated.status_code, status.HTTP_200_OK)
        self.assertIsInstance(res_unpaginated.data, list)
        self.assertEqual(len(res_unpaginated.data), 5)

        # Paginated with branch_id
        res_paginated = self.client.get(f'{self.url}?paginate=true&branch_id={self.branch2.id}')
        self.assertEqual(res_paginated.status_code, status.HTTP_200_OK)
        self.assertIsInstance(res_paginated.data, dict)
        self.assertEqual(res_paginated.data['count'], 5)
        self.assertEqual(len(res_paginated.data['results']), 5)

    def test_authorization_scope_preserved(self):
        # Unauthorized user rejected
        self.client.force_authenticate(user=self.unauth_user)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Branch manager only sees Branch 1
        self.client.force_authenticate(user=self.manager_user)
        res_mgr = self.client.get(f'{self.url}?paginate=true')
        self.assertEqual(res_mgr.status_code, status.HTTP_200_OK)
        self.assertEqual(res_mgr.data['count'], 25)
