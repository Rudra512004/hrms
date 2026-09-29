from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.organization.models import Organization, Branch
from apps.attendance.models import Shift
from apps.attendance.exceptions import AttendanceConfigurationError
from apps.attendance.services import AttendanceCalculationService
from datetime import time

User = get_user_model()


class ShiftAndAssignmentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Org 1
        self.org1 = Organization.objects.create(name='Org 1')
        self.branch1 = Branch.objects.create(organization=self.org1, name='HQ 1')
        self.branch3 = Branch.objects.create(organization=self.org1, name='Branch 3')
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
            end_time=time(17, 0),
            work_days='0,1,2,3,4',
            is_active=True
        )

        # Base shift in Org 2
        self.shift2 = Shift.objects.create(
            branch=self.branch2,
            name='Night Shift Org 2',
            start_time=time(22, 0),
            end_time=time(6, 0),
            work_days='0,1,2,3,4',
            is_active=True
        )

    # -------------------------------------------------------------------------
    # P0 FIX 1: Enforce One Active Shift Per Branch
    # -------------------------------------------------------------------------
    def test_create_second_active_shift_rejected(self):
        """Creating a second active shift for the same branch must be rejected with HTTP 400."""
        self.client.force_authenticate(user=self.super_user)
        url = reverse('shift-list')
        data = {
            'branch': self.branch1.id,
            'name': 'Second Active Shift',
            'start_time': '10:00:00',
            'end_time': '19:00:00',
            'work_days': '0,1,2,3,4',
            'is_active': True
        }
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        error_msg = str(res.data)
        self.assertIn("An active shift is already configured for this branch. Deactivate the existing shift before activating a new one.", error_msg)

    def test_activate_inactive_second_shift_rejected(self):
        """Activating an existing inactive shift when another active shift exists must be rejected with HTTP 400."""
        self.client.force_authenticate(user=self.super_user)
        inactive_shift = Shift.objects.create(
            branch=self.branch1,
            name='Inactive Shift',
            start_time=time(14, 0),
            end_time=time(22, 0),
            work_days='0,1,2,3,4',
            is_active=False
        )
        url = reverse('shift-detail', args=[inactive_shift.id])
        res = self.client.patch(url, {'is_active': True})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("An active shift is already configured for this branch. Deactivate the existing shift before activating a new one.", str(res.data))

    def test_update_existing_active_shift_allowed(self):
        """Updating non-status fields on an already active shift must be allowed."""
        self.client.force_authenticate(user=self.super_user)
        url = reverse('shift-detail', args=[self.shift1.id])
        res = self.client.patch(url, {'name': 'Updated Shift Name', 'start_time': '08:30:00'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.shift1.refresh_from_db()
        self.assertEqual(self.shift1.name, 'Updated Shift Name')
        self.assertEqual(self.shift1.start_time, time(8, 30))

    def test_deactivate_active_shift_allowed(self):
        """Deactivating an active shift (setting is_active=False) must be allowed."""
        self.client.force_authenticate(user=self.super_user)
        url = reverse('shift-detail', args=[self.shift1.id])
        res = self.client.patch(url, {'is_active': False})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.shift1.refresh_from_db()
        self.assertFalse(self.shift1.is_active)

    def test_create_active_shift_after_previous_one_inactive_allowed(self):
        """Creating an active shift when the previous shift was deactivated must succeed."""
        self.client.force_authenticate(user=self.super_user)
        # Deactivate shift1 first
        self.shift1.is_active = False
        self.shift1.save()

        url = reverse('shift-list')
        data = {
            'branch': self.branch1.id,
            'name': 'New Active Shift',
            'start_time': '09:00:00',
            'end_time': '18:00:00',
            'work_days': '0,1,2,3,4',
            'is_active': True
        }
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['name'], 'New Active Shift')
        self.assertTrue(res.data['is_active'])

    def test_cross_branch_active_shifts_allowed(self):
        """Different branches having their own active shift is completely valid."""
        self.client.force_authenticate(user=self.super_user)
        url = reverse('shift-list')
        data = {
            'branch': self.branch3.id,
            'name': 'Branch 3 Shift',
            'start_time': '08:00:00',
            'end_time': '16:00:00',
            'work_days': '0,1,2,3,4',
            'is_active': True
        }
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['name'], 'Branch 3 Shift')

    def test_change_branch_to_branch_with_existing_active_shift_rejected(self):
        """Moving an active shift to another branch that already has an active shift must be rejected."""
        self.client.force_authenticate(user=self.super_user)
        shift_b3 = Shift.objects.create(
            branch=self.branch3,
            name='B3 Shift',
            start_time=time(8, 0),
            end_time=time(16, 0),
            is_active=True
        )
        url = reverse('shift-detail', args=[shift_b3.id])
        # Attempt to move shift_b3 to branch1 (which already has shift1 active)
        res = self.client.patch(url, {'branch': self.branch1.id})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("An active shift is already configured for this branch", str(res.data))

    # -------------------------------------------------------------------------
    # P1 FIX 3: Remove Shift Work-Day Fallback Tests
    # -------------------------------------------------------------------------
    def test_shift_work_days_list_valid_configurations(self):
        """Verify 5-day, 6-day, and Sunday-inclusive work_days configurations."""
        # 5-day
        s5 = Shift(name='5-day', work_days='0,1,2,3,4')
        self.assertEqual(s5.get_work_days_list(), [0, 1, 2, 3, 4])
        self.assertEqual(AttendanceCalculationService.get_shift_work_days(s5), [0, 1, 2, 3, 4])

        # 6-day
        s6 = Shift(name='6-day', work_days='0,1,2,3,4,5')
        self.assertEqual(s6.get_work_days_list(), [0, 1, 2, 3, 4, 5])
        self.assertEqual(AttendanceCalculationService.get_shift_work_days(s6), [0, 1, 2, 3, 4, 5])

        # Sunday-inclusive (all 7 days)
        s7 = Shift(name='7-day', work_days='0,1,2,3,4,5,6')
        self.assertEqual(s7.get_work_days_list(), [0, 1, 2, 3, 4, 5, 6])
        self.assertEqual(AttendanceCalculationService.get_shift_work_days(s7), [0, 1, 2, 3, 4, 5, 6])

    def test_shift_work_days_empty_raises_error_no_fallback(self):
        """Empty or blank work_days must raise AttendanceConfigurationError, not default to Mon-Fri."""
        s_empty = Shift(name='Empty Shift', work_days='')
        with self.assertRaises(AttendanceConfigurationError) as cm:
            s_empty.get_work_days_list()
        self.assertIn("has unconfigured work days", str(cm.exception))

        with self.assertRaises(AttendanceConfigurationError):
            AttendanceCalculationService.get_shift_work_days(s_empty)

    def test_shift_work_days_invalid_raises_error_no_fallback(self):
        """Invalid characters or out-of-range days in shift work_days must raise AttendanceConfigurationError."""
        s_invalid = Shift(name='Invalid Shift', work_days='0,foo,2')
        with self.assertRaises(AttendanceConfigurationError) as cm:
            s_invalid.get_work_days_list()
        self.assertIn("Invalid work day", str(cm.exception))

        s_out_of_bounds = Shift(name='OOB Shift', work_days='0,1,7')
        with self.assertRaises(AttendanceConfigurationError):
            s_out_of_bounds.get_work_days_list()

    def test_get_shift_work_days_none_shift_raises_error(self):
        """Passing None to AttendanceCalculationService.get_shift_work_days raises AttendanceConfigurationError."""
        with self.assertRaises(AttendanceConfigurationError):
            AttendanceCalculationService.get_shift_work_days(None)

    # -------------------------------------------------------------------------
    # General CRUD, Branch Filtering & Authorization Tests
    # -------------------------------------------------------------------------
    def test_shift_list_branch_filtering(self):
        self.client.force_authenticate(user=self.super_user)
        url = reverse('shift-list')

        res = self.client.get(url, {'branch_id': self.branch1.id})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_ids = [s['id'] for s in res.data]
        self.assertIn(self.shift1.id, returned_ids)
        self.assertNotIn(self.shift2.id, returned_ids)

    def test_shift_delete_and_branch_scope(self):
        self.client.force_authenticate(user=self.super_user)
        shift_to_delete = Shift.objects.create(
            branch=self.branch3,
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

