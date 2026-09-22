from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.organization.models import Organization
from .models import Shift
from datetime import date, time, timedelta

User = get_user_model()

class ShiftAndAssignmentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        from apps.organization.models import Branch

        # Org 1
        self.org1 = Organization.objects.create(name='Org 1')
        self.branch1 = Branch.objects.create(organization=self.org1, name='HQ 1')
        self.user1 = User.objects.create_user(email='emp1@example.com', password='Password123!', status='active')
        self.emp1 = Employee.objects.create(user=self.user1, employee_code='E1', organization=self.org1, branch=self.branch1)

        # Superuser with permission seed
        self.super_user = User.objects.create_user(email='super@example.com', password='Password123!', status='active', is_superuser=True)
        self.super_emp = Employee.objects.create(user=self.super_user, employee_code='SUPER', organization=self.org1, branch=self.branch1)

        # Org 2
        self.org2 = Organization.objects.create(name='Org 2')
        self.branch2 = Branch.objects.create(organization=self.org2, name='HQ 2')
        self.user2 = User.objects.create_user(email='emp2@example.com', password='Password123!', status='active')
        self.emp2 = Employee.objects.create(user=self.user2, employee_code='E2', organization=self.org2, branch=self.branch2)

        # Base shift in Org 1
        self.shift1 = Shift.objects.create(
            branch=self.branch1,
            name='Day Shift',
            start_time=time(9, 0),
            end_time=time(17, 0)
        )

        # Base shift in Org 2
        self.shift2 = Shift.objects.create(
            branch=self.branch2,
            name='Night Shift Org 2',
            start_time=time(22, 0),
            end_time=time(6, 0)
        )

    def test_shift_create_and_tenant_isolation(self):
        self.client.force_authenticate(user=self.super_user)
        url = reverse('shift-list')

        # Create
        data = {
            'branch': self.branch1.id,
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
            'branch': self.branch1.id,
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

    def test_shift_list_branch_filtering(self):
        self.client.force_authenticate(user=self.super_user)
        url = reverse('shift-list')

        res = self.client.get(url, {'branch_id': self.branch1.id})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_ids = [s['id'] for s in res.data]
        self.assertIn(self.shift1.id, returned_ids)
        self.assertNotIn(self.shift2.id, returned_ids)

    def test_shift_update_and_branch_scope(self):
        self.client.force_authenticate(user=self.super_user)
        url = reverse('shift-detail', args=[self.shift1.id])

        res = self.client.patch(url, {'name': 'Updated Shift Name'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.shift1.refresh_from_db()
        self.assertEqual(self.shift1.name, 'Updated Shift Name')

    def test_shift_delete_and_branch_scope(self):
        self.client.force_authenticate(user=self.super_user)
        shift_to_delete = Shift.objects.create(
            branch=self.branch1,
            name='Temporary Shift',
            start_time=time(10, 0),
            end_time=time(18, 0)
        )
        url = reverse('shift-detail', args=[shift_to_delete.id])

        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Shift.objects.filter(id=shift_to_delete.id).exists())

    def test_shift_cross_organization_forbidden(self):
        from apps.authorization.models import Role, RolePermission, Permission, UserRole, ScopeChoices
        p_manage = Permission.objects.get(codename='shift.manage')
        p_view = Permission.objects.get(codename='shift.view')
        role = Role.objects.create(organization=self.org1, name='Org 1 Shift Admin')
        RolePermission.objects.create(role=role, permission=p_manage)
        RolePermission.objects.create(role=role, permission=p_view)
        UserRole.objects.create(user=self.user1, role=role, scope=ScopeChoices.BRANCH, branch=self.branch1)

        # Attempt to modify shift in Org 2
        self.client.force_authenticate(user=self.user1)
        url = reverse('shift-detail', args=[self.shift2.id])
        res = self.client.patch(url, {'name': 'Hacked Shift'})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_shift_inactive_toggle(self):
        self.client.force_authenticate(user=self.super_user)
        url = reverse('shift-detail', args=[self.shift1.id])

        res = self.client.patch(url, {'is_active': False})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.shift1.refresh_from_db()
        self.assertFalse(self.shift1.is_active)
