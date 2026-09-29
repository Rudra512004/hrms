from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from apps.organization.models import Organization, Branch, Department, Team
from apps.authorization.models import Role, UserRole, Permission, RolePermission
from django.contrib.auth import get_user_model

User = get_user_model()

class OrganizationSelectorTests(APITestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name='Org 1', status='active')
        self.branch1 = Branch.objects.create(organization=self.org1, name='B1', radius=100)
        self.branch2 = Branch.objects.create(organization=self.org1, name='B2', radius=100)
        self.dept1 = Department.objects.create(branch=self.branch1, name='D1')
        self.dept2 = Department.objects.create(branch=self.branch2, name='D2')
        self.team1 = Team.objects.create(department=self.dept1, name='T1')
        self.team2 = Team.objects.create(department=self.dept2, name='T2')

        self.user = User.objects.create_user(email='sel@test.com', status='active')

        # Give user branch.view and department.view at branch1 scope
        self.role = Role.objects.create(name='B1 Admin', organization=self.org1)
        p1 = Permission.objects.get_or_create(codename='branch.view', resource='branch', action='view')[0]
        p2 = Permission.objects.get_or_create(codename='department.view', resource='department', action='view')[0]
        p3 = Permission.objects.get_or_create(codename='team.view', resource='team', action='view')[0]
        RolePermission.objects.create(role=self.role, permission=p1)
        RolePermission.objects.create(role=self.role, permission=p2)
        RolePermission.objects.create(role=self.role, permission=p3)
        UserRole.objects.create(user=self.user, role=self.role, scope='branch', branch=self.branch1)

    def test_branch_selector_isolation(self):
        from unittest.mock import patch
        with patch('apps.authorization.permissions.IsNetworkAllowed.has_permission', return_value=True):
            self.client.force_authenticate(user=self.user)
            res = self.client.get(reverse('branch-list'))
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(len(res.data), 1)
            self.assertEqual(res.data[0]['id'], self.branch1.id)

    def test_department_selector_isolation(self):
        from unittest.mock import patch
        with patch('apps.authorization.permissions.IsNetworkAllowed.has_permission', return_value=True):
            self.client.force_authenticate(user=self.user)
            res = self.client.get(reverse('department-list') + '?branch=' + str(self.branch2.id))
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(len(res.data), 0) # Should be empty because branch2 is unauthorized

            res2 = self.client.get(reverse('department-list'))
            self.assertEqual(len(res2.data), 1)
            self.assertEqual(res2.data[0]['id'], self.dept1.id)
