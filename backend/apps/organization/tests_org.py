from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.authorization.models import Permission, Role, UserRole, RolePermission
from apps.organization.models import Organization, Department, Designation

User = get_user_model()

class OrganizationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email='admin@example.com', password='password123', status='active')

        self.org = Organization.objects.create(name='Test Org')
        self.role = Role.objects.create(organization=self.org, name='AdminRole')
        UserRole.objects.create(user=self.user, role=self.role)

        for codename in ['organization.manage', 'department.manage', 'designation.manage', 'team.manage']:
            resource = codename.split('.')[0]
            perm, _ = Permission.objects.get_or_create(codename=codename, defaults={'name': codename, 'resource': resource, 'action': 'manage'})
            RolePermission.objects.create(role=self.role, permission=perm)

    def test_create_organization(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('organization-list'), {'name': 'New Org', 'status': 'active'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Organization.objects.count(), 2)

    def test_create_department(self):
        from apps.organization.models import Branch
        branch = Branch.objects.create(organization=self.org, name='Test Branch', radius=100)
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('department-list'), {'branch': branch.id, 'name': 'Engineering'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Department.objects.count(), 1)

    def test_create_designation(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('designation-list'), {'organization': self.org.id, 'name': 'Software Engineer'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Designation.objects.count(), 1)

    def test_no_permission(self):
        RolePermission.objects.filter(role=self.role).delete()
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('organization-list'), {'name': 'New Org'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_department_creation_under_branch(self):
        from apps.organization.models import Branch
        branch = Branch.objects.create(organization=self.org, name='Main Branch', radius=100)
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('department-list'), {'branch': branch.id, 'name': 'HR'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Department.objects.filter(branch=branch).count(), 1)

    def test_team_creation_under_department(self):
        from apps.organization.models import Branch, Team
        branch = Branch.objects.create(organization=self.org, name='Main Branch', radius=100)
        department = Department.objects.create(branch=branch, name='Engineering')
        self.client.force_authenticate(user=self.user)

        # Test creating team via API
        response = self.client.post(reverse('team-list'), {'department': department.id, 'name': 'Backend'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Team.objects.filter(department=department).count(), 1)

    def test_team_manager_validation(self):
        from apps.organization.models import Branch, Team
        from apps.employees.models import Employee, EmploymentStatus
        from django.core.exceptions import ValidationError

        branch1 = Branch.objects.create(organization=self.org, name='Branch 1', radius=100)
        branch2 = Branch.objects.create(organization=self.org, name='Branch 2', radius=100)
        department = Department.objects.create(branch=branch1, name='Engineering')

        user_emp = User.objects.create_user(email='emp@example.com', password='password123')
        # Manager is in a DIFFERENT branch
        manager = Employee.objects.create(
            user=user_emp, employee_code='E01', organization=self.org,
            branch=branch2, employment_status=EmploymentStatus.ACTIVE
        )

        team = Team(department=department, name='Frontend', manager=manager)
        with self.assertRaises(ValidationError):
            team.clean()

    def test_team_uniqueness_per_department(self):
        from apps.organization.models import Branch, Team
        from django.db import IntegrityError
        branch = Branch.objects.create(organization=self.org, name='Main Branch', radius=100)
        department = Department.objects.create(branch=branch, name='Engineering')
        Team.objects.create(department=department, name='DevOps')

        with self.assertRaises(IntegrityError):
            Team.objects.create(department=department, name='DevOps')
