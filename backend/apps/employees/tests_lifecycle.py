from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.authorization.models import Permission, Role, UserRole, RolePermission
from apps.employees.models import Employee
from apps.organization.models import Organization
from unittest.mock import patch

User = get_user_model()

@patch('apps.authorization.permissions.IsNetworkAllowed.has_permission', return_value=True)
class EmployeeLifecycleAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(email='admin@example.com', password='password123', status='active')
        self.employee_user = User.objects.create_user(email='emp@example.com', password='password123', status='active')
        
        self.employee = Employee.objects.create(
            user=self.employee_user, 
            employee_code='E001',
            personal_email='personal@example.com',
            phone_number='1234567890'
        )
        
        self.admin_emp = Employee.objects.create(user=self.admin_user, employee_code='E002')

        self.org = Organization.objects.create(name='Test Org')
        self.role = Role.objects.create(name='HRRole', organization=self.org)
        UserRole.objects.create(user=self.admin_user, role=self.role)
        
        for codename in ['employee.view', 'employee.update', 'employee.manage_status', 'employee.view_sensitive']:
            perm, _ = Permission.objects.get_or_create(codename=codename, defaults={'name': codename, 'resource': 'employee', 'action': codename.split('.')[1]})
            RolePermission.objects.create(role=self.role, permission=perm)

    def test_retrieve_sensitive_info(self, mock_network):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('employee-management-detail', args=[self.employee.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('personal_email', response.data)
        
        # Without permission
        RolePermission.objects.filter(role=self.role).delete()
        perm = Permission.objects.get(codename='employee.view')
        RolePermission.objects.create(role=self.role, permission=perm)
        response = self.client.get(reverse('employee-management-detail', args=[self.employee.id]))
        self.assertNotIn('personal_email', response.data)

    def test_update_lifecycle_dates(self, mock_network):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(reverse('employee-management-detail', args=[self.employee.id]), {
            'joining_date': '2026-01-01',
            'exit_date': '2026-12-31'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['joining_date'], '2026-01-01')

    def test_invalid_lifecycle_dates(self, mock_network):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(reverse('employee-management-detail', args=[self.employee.id]), {
            'joining_date': '2026-12-31',
            'exit_date': '2026-01-01'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('exit_date', response.data)

    def test_change_employment_status(self, mock_network):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(reverse('employee-management-change-employment-status', args=[self.employee.id]), {
            'employment_status': 'active'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['employment_status'], 'active')

        response = self.client.post(reverse('employee-management-change-employment-status', args=[self.employee.id]), {
            'employment_status': 'invalid_status'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_permission_status_change(self, mock_network):
        RolePermission.objects.filter(role=self.role).delete()
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(reverse('employee-management-change-employment-status', args=[self.employee.id]), {
            'employment_status': 'exited'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
