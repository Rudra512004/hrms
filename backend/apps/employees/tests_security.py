from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from unittest.mock import patch
from apps.organization.models import Organization, Department, Designation
from apps.employees.models import Employee

User = get_user_model()

class EmployeeSelfServiceSecurityTests(APITestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name='Org 1')
        self.org2 = Organization.objects.create(name='Org 2')
        
        self.dept1 = Department.objects.create(name='Dept 1', organization=self.org1)
        self.desig1 = Designation.objects.create(name='Worker', organization=self.org1)
        self.desig_ceo = Designation.objects.create(name='CEO', organization=self.org1)
        
        self.user1 = User.objects.create_user(email='emp1@example.com', password='password123')
        self.employee = Employee.objects.create(
            user=self.user1,
            organization=self.org1,
            department=self.dept1,
            designation=self.desig1,
            employee_code='E001'
        )

        self.user2 = User.objects.create_user(email='manager@example.com', password='password123')
        self.manager = Employee.objects.create(
            user=self.user2,
            organization=self.org1,
            employee_code='M001'
        )

    def patch_json(self, url, data):
        with patch('apps.authorization.network.NetworkAccessService.is_remote_access_allowed', return_value=True):
            return self.client.patch(url, data, format='json')

    def test_legitimate_self_service_fields_work(self):
        self.client.force_authenticate(user=self.user1)
        response = self.patch_json('/api/v1/employees/me/', {
            'phone_number': '1234567890',
            'address': 'New Address'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone_number, '1234567890')
        self.assertEqual(self.employee.address, 'New Address')

    def test_employee_cannot_change_organization(self):
        self.client.force_authenticate(user=self.user1)
        response = self.patch_json('/api/v1/employees/me/', {
            'organization': self.org2.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee.refresh_from_db()
        # Organization MUST remain unchanged
        self.assertEqual(self.employee.organization_id, self.org1.id)

    def test_employee_cannot_change_designation_or_department(self):
        self.client.force_authenticate(user=self.user1)
        response = self.patch_json('/api/v1/employees/me/', {
            'designation': self.desig_ceo.id,
            'department': None
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.designation_id, self.desig1.id)
        self.assertEqual(self.employee.department_id, self.dept1.id)

    def test_employee_cannot_change_reporting_manager(self):
        self.client.force_authenticate(user=self.user1)
        response = self.patch_json('/api/v1/employees/me/', {
            'reporting_manager': self.manager.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.reporting_manager)

    def test_employee_cannot_change_notice_period(self):
        self.client.force_authenticate(user=self.user1)
        response = self.patch_json('/api/v1/employees/me/', {
            'notice_period_start': '2026-09-01',
            'notice_period_end': '2026-09-30'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.notice_period_start)
        self.assertIsNone(self.employee.notice_period_end)
