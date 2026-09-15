from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.organization.models import Organization
from .models import Shift, EmployeeShiftAssignment
from datetime import date, time, timedelta

User = get_user_model()

class ShiftAndAssignmentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Org 1
        self.org1 = Organization.objects.create(name='Org 1')
        self.user1 = User.objects.create_user(email='emp1@example.com', password='Password123!', status='active')
        self.emp1 = Employee.objects.create(user=self.user1, employee_code='E1', organization=self.org1)
        
        # Superuser with permission seed
        self.super_user = User.objects.create_user(email='super@example.com', password='Password123!', status='active', is_superuser=True)
        self.super_emp = Employee.objects.create(user=self.super_user, employee_code='SUPER', organization=self.org1)
        
        # Org 2
        self.org2 = Organization.objects.create(name='Org 2')
        self.user2 = User.objects.create_user(email='emp2@example.com', password='Password123!', status='active')
        self.emp2 = Employee.objects.create(user=self.user2, employee_code='E2', organization=self.org2)

        # Base shift in Org 1
        self.shift1 = Shift.objects.create(
            organization=self.org1,
            name='Day Shift',
            start_time=time(9, 0),
            end_time=time(17, 0)
        )
        
        # Base shift in Org 2
        self.shift2 = Shift.objects.create(
            organization=self.org2,
            name='Night Shift Org 2',
            start_time=time(22, 0),
            end_time=time(6, 0)
        )

    def test_shift_create_and_tenant_isolation(self):
        self.client.force_authenticate(user=self.super_user)
        url = reverse('shift-list')
        
        # Create
        data = {
            'organization': self.org1.id,
            'name': 'Overnight',
            'start_time': '22:00:00',
            'end_time': '06:00:00',
            'work_days': '0,1,2,3,4'
        }
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['name'], 'Overnight')
        
        # List Isolation
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data['results'] if 'results' in res.data else res.data), 3)

    def test_shift_work_days_validation(self):
        self.client.force_authenticate(user=self.super_user)
        url = reverse('shift-list')
        
        # Duplicate days
        data = {
            'organization': self.org1.id,
            'name': 'Duplicate',
            'start_time': '10:00:00',
            'end_time': '18:00:00',
            'work_days': '0,0,1'
        }
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('work_days', res.data)

        # Out of bounds
        data['work_days'] = '0,1,7'
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Malformed / letters
        data['work_days'] = '0,M,1'
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Valid days
        data['work_days'] = '0,1,2,3,4,5,6'
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_shift_assignment_overlap_rejection(self):
        self.client.force_authenticate(user=self.super_user)
        url = reverse('shift-assignment-list')
        
        # Valid assignment 1
        res1 = self.client.post(url, {
            'employee': self.emp1.id,
            'shift': self.shift1.id,
            'effective_from': '2023-01-01',
            'effective_to': '2023-01-31'
        })
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Overlapping assignment 2
        res2 = self.client.post(url, {
            'employee': self.emp1.id,
            'shift': self.shift1.id,
            'effective_from': '2023-01-15',
            'effective_to': '2023-02-15'
        })
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('effective_from', res2.data)

        # Sequential assignment (allowed)
        res3 = self.client.post(url, {
            'employee': self.emp1.id,
            'shift': self.shift1.id,
            'effective_from': '2023-02-01',
            'effective_to': '2023-02-28'
        })
        self.assertEqual(res3.status_code, status.HTTP_201_CREATED)

        # Open-ended assignment (allowed)
        res4 = self.client.post(url, {
            'employee': self.emp1.id,
            'shift': self.shift1.id,
            'effective_from': '2023-03-01',
            'effective_to': ''
        })
        self.assertEqual(res4.status_code, status.HTTP_201_CREATED)

        # Another open-ended assignment (rejected overlap)
        res5 = self.client.post(url, {
            'employee': self.emp1.id,
            'shift': self.shift1.id,
            'effective_from': '2023-04-01',
            'effective_to': ''
        })
        self.assertEqual(res5.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_assignment_cross_tenant_rejection(self):
        self.client.force_authenticate(user=self.super_user)
        url = reverse('shift-assignment-list')
        
        # Shift in Org 2, Employee in Org 1
        res = self.client.post(url, {
            'employee': self.emp1.id,
            'shift': self.shift2.id,
            'effective_from': '2023-01-01'
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_invalid_effective_dates(self):
        self.client.force_authenticate(user=self.super_user)
        url = reverse('shift-assignment-list')
        
        # End before start
        res = self.client.post(url, {
            'employee': self.emp1.id,
            'shift': self.shift1.id,
            'effective_from': '2023-01-31',
            'effective_to': '2023-01-01'
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
