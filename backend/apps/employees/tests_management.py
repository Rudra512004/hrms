from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.organization.models import Organization

User = get_user_model()

class EmployeeManagementAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Test Org')

        # Superadmin
        self.super_user = User.objects.create_user(email='super@example.com', password='Password123!', status='active', is_superuser=True)
        self.super_employee = Employee.objects.create(user=self.super_user, employee_code='EMP_SUPER', organization=self.org)

        # Normal Employee (No management permissions)
        self.normal_user = User.objects.create_user(email='normal@example.com', password='Password123!', status='active')
        self.normal_employee = Employee.objects.create(user=self.normal_user, employee_code='EMP_NORMAL', organization=self.org)

        # Another employee to manipulate
        self.target_user = User.objects.create_user(email='target@example.com', password='Password123!', status='active')
        self.target_employee = Employee.objects.create(user=self.target_user, employee_code='EMP_TARGET', organization=self.org)

    def test_employee_creation_superadmin(self):
        self.client.force_authenticate(user=self.super_user)
        response = self.client.post(reverse('employee-management-list'), {
            'email': 'new_emp@example.com',
            'first_name': 'New',
            'last_name': 'Emp',
            'employee_code': 'EMP_NEW'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='new_emp@example.com').exists())

    def test_employee_creation_unauthorized(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.post(reverse('employee-management-list'), {
            'email': 'new_emp2@example.com',
            'first_name': 'New',
            'last_name': 'Emp',
            'employee_code': 'EMP_NEW2'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_list(self):
        self.client.force_authenticate(user=self.super_user)
        response = self.client.get(reverse('employee-management-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see all 3 employees created in setUp
        self.assertEqual(len(response.data), 3)

    def test_employee_activation(self):
        self.target_user.status = 'deactivated'
        self.target_user.is_active = False
        self.target_user.save()

        self.client.force_authenticate(user=self.super_user)
        response = self.client.post(reverse('employee-management-activate', kwargs={'pk': self.target_employee.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.status, 'active')
        self.assertTrue(self.target_user.is_active)

    def test_employee_deactivation(self):
        self.client.force_authenticate(user=self.super_user)
        response = self.client.post(reverse('employee-management-deactivate', kwargs={'pk': self.target_employee.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.status, 'deactivated')
        self.assertFalse(self.target_user.is_active)

    def test_deactivate_own_account_fails(self):
        self.client.force_authenticate(user=self.super_user)
        response = self.client.post(reverse('employee-management-deactivate', kwargs={'pk': self.super_employee.pk}))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deactivated_account_access(self):
        self.target_user.status = 'deactivated'
        self.target_user.is_active = False
        self.target_user.save()

        self.client.force_authenticate(user=self.target_user)
        response = self.client.get(reverse('employee-me'))
        # Should fail authentication since user is inactive
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
