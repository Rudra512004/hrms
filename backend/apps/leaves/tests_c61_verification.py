import threading
from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.db import connection, transaction

from apps.employees.models import Employee, EmploymentStatus
from apps.organization.models import Organization, Branch
from apps.organization.exceptions import WorkingCalendarConfigurationError
from apps.leaves.models import LeaveType, LeaveBalance, LeaveRequest
from apps.payroll.services import _approved_leave_days

User = get_user_model()


class LeaveC61VerificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org1 = Organization.objects.create(name='Org Alpha')
        self.branch1 = Branch.objects.create(organization=self.org1, name='Branch Alpha')

        self.org2 = Organization.objects.create(name='Org Beta')
        self.branch2 = Branch.objects.create(organization=self.org2, name='Branch Beta')

        # Superadmin
        self.superadmin = User.objects.create_user(
            email='superadmin@example.com',
            password='Password123!',
            status='active',
            is_superuser=True
        )

        # Employee 1 in Org 1
        self.user1 = User.objects.create_user(email='emp1@alpha.com', password='Password123!', status='active')
        self.emp1 = Employee.objects.create(user=self.user1, employee_code='EMP01', organization=self.org1, branch=self.branch1)

        # Manager in Org 1
        self.mgr_user1 = User.objects.create_user(email='mgr1@alpha.com', password='Password123!', status='active')
        self.mgr_emp1 = Employee.objects.create(user=self.mgr_user1, employee_code='MGR01', organization=self.org1, branch=self.branch1)

        # Employee 2 in Org 2
        self.user2 = User.objects.create_user(email='emp2@beta.com', password='Password123!', status='active')
        self.emp2 = Employee.objects.create(user=self.user2, employee_code='EMP02', organization=self.org2, branch=self.branch2)

        # Leave Types
        self.leave_type1 = LeaveType.objects.create(organization=self.org1, name='Sick Leave')
        self.leave_type2 = LeaveType.objects.create(organization=self.org2, name='Sick Leave Beta')

        # Balances
        from apps.leaves.models import LeaveCycle
        from datetime import date
        self.cycle1 = LeaveCycle.objects.create(branch=self.branch1, name='C1', start_date=date(2026,1,1), end_date=date(2026,12,31))
        self.balance1 = LeaveBalance.objects.create(employee=self.emp1, leave_type=self.leave_type1, branch=self.branch1, leave_cycle=self.cycle1, allocated=10, used=0)
        self.cycle2 = LeaveCycle.objects.create(branch=self.branch2, name='C2', start_date=date(2026,1,1), end_date=date(2026,12,31))
        self.balance2 = LeaveBalance.objects.create(employee=self.emp2, leave_type=self.leave_type2, branch=self.branch2, leave_cycle=self.cycle2, allocated=10, used=0)

    # -------------------------------------------------------------------------
    # CASE A: approved 2-day leave + used=2 -> cancellation -> used=0
    # -------------------------------------------------------------------------
    def test_case_a_approved_leave_cancellation_refunds_used(self):
        # Mon-Tue 2-day leave
        base_date = date(2026, 9, 7)  # Monday
        leave = LeaveRequest.objects.create(
            employee=self.emp1,
            leave_type=self.leave_type1,
            start_date=base_date,
            end_date=base_date + timedelta(days=1),
            reason='Medical recovery',
            status='approved'
        )
        self.assertEqual(leave.duration_days, 2)
        self.balance1.used = 2
        self.balance1.save()

        self.client.force_authenticate(user=self.user1)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True), \
             patch('apps.authorization.services.AuthorizationService.get_authorized_branches', return_value=[self.branch1]):
            resp = self.client.post(reverse('leave-requests-cancel', kwargs={'pk': leave.pk}))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        leave.refresh_from_db()
        self.assertEqual(leave.status, 'cancelled')
        self.balance1.refresh_from_db()
        self.assertEqual(self.balance1.used, 0)

    # -------------------------------------------------------------------------
    # CASE B: approved 2-day leave + used=1 -> cancellation rejected; leave remains approved; used remains 1
    # -------------------------------------------------------------------------
    def test_case_b_cancellation_rejected_when_used_less_than_refund(self):
        base_date = date(2026, 9, 7)  # Monday
        leave = LeaveRequest.objects.create(
            employee=self.emp1,
            leave_type=self.leave_type1,
            start_date=base_date,
            end_date=base_date + timedelta(days=1),
            reason='Medical recovery',
            status='approved'
        )
        self.assertEqual(leave.duration_days, 2)
        self.balance1.used = 1
        self.balance1.save()

        self.client.force_authenticate(user=self.user1)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True), \
             patch('apps.authorization.services.AuthorizationService.get_authorized_branches', return_value=[self.branch1]):
            resp = self.client.post(reverse('leave-requests-cancel', kwargs={'pk': leave.pk}))

        # Must fail and rollback completely
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        leave.refresh_from_db()
        self.assertEqual(leave.status, 'approved')
        self.balance1.refresh_from_db()
        self.assertEqual(self.balance1.used, 1)

    def test_case_b_missing_leave_balance_rejected(self):
        base_date = date(2026, 9, 7)
        leave = LeaveRequest.objects.create(
            employee=self.emp1,
            leave_type=self.leave_type1,
            start_date=base_date,
            end_date=base_date + timedelta(days=1),
            reason='Medical recovery',
            status='approved'
        )
        # Delete balance
        self.balance1.delete()

        self.client.force_authenticate(user=self.user1)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True), \
             patch('apps.authorization.services.AuthorizationService.get_authorized_branches', return_value=[self.branch1]):
            resp = self.client.post(reverse('leave-requests-cancel', kwargs={'pk': leave.pk}))

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('balance', str(resp.data).lower())
        leave.refresh_from_db()
        self.assertEqual(leave.status, 'approved')

    def test_case_b_branchless_leave_duration_none_rejected(self):
        # Leave where employee has no branch -> duration_days is None
        branchless_user = User.objects.create_user(email='nobranch_cancel@alpha.com', password='Password123!', status='active')
        branchless_emp = Employee.objects.create(user=branchless_user, employee_code='NOBR99', organization=self.org1, branch=None)
        leave = LeaveRequest.objects.create(
            employee=branchless_emp,
            leave_type=self.leave_type1,
            start_date=date(2026, 9, 7),
            end_date=date(2026, 9, 8),
            reason='Branchless cancel test',
            status='approved'
        )
        self.assertIsNone(leave.duration_days)

        self.client.force_authenticate(user=branchless_user)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            resp = self.client.post(reverse('leave-requests-cancel', kwargs={'pk': leave.pk}))

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('duration', str(resp.data).lower())
        leave.refresh_from_db()
        self.assertEqual(leave.status, 'approved')

    # -------------------------------------------------------------------------
    # CASE C: cancellation twice -> only one refund
    # -------------------------------------------------------------------------
    def test_case_c_cancellation_twice_only_one_refund(self):
        base_date = date(2026, 9, 7)  # Monday
        leave = LeaveRequest.objects.create(
            employee=self.emp1,
            leave_type=self.leave_type1,
            start_date=base_date,
            end_date=base_date + timedelta(days=1),
            reason='Medical recovery',
            status='approved'
        )
        self.balance1.used = 2
        self.balance1.save()

        self.client.force_authenticate(user=self.user1)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True), \
             patch('apps.authorization.services.AuthorizationService.get_authorized_branches', return_value=[self.branch1]):
            # First cancellation
            resp1 = self.client.post(reverse('leave-requests-cancel', kwargs={'pk': leave.pk}))
            self.assertEqual(resp1.status_code, status.HTTP_200_OK)
            self.balance1.refresh_from_db()
            self.assertEqual(self.balance1.used, 0)

            # Second cancellation
            resp2 = self.client.post(reverse('leave-requests-cancel', kwargs={'pk': leave.pk}))
            self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
            self.balance1.refresh_from_db()
            self.assertEqual(self.balance1.used, 0)

    # -------------------------------------------------------------------------
    # CASE E: branchless employee create -> rejected
    # -------------------------------------------------------------------------
    def test_case_e_branchless_employee_create_rejected(self):
        branchless_user = User.objects.create_user(email='nobranch@alpha.com', password='Password123!', status='active')
        Employee.objects.create(user=branchless_user, employee_code='NOBR01', organization=self.org1, branch=None)

        self.client.force_authenticate(user=branchless_user)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            resp = self.client.post(reverse('leave-requests-list'), {
                'leave_type': self.leave_type1.id,
                'start_date': '2026-09-08',
                'end_date': '2026-09-09',
                'reason': 'Branchless attempt'
            })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('branch', str(resp.data).lower())

    # -------------------------------------------------------------------------
    # CASE F: historical branchless leave GET/list -> no 500
    # -------------------------------------------------------------------------
    def test_case_f_historical_branchless_leave_get_list_no_500(self):
        branchless_user = User.objects.create_user(email='nobranch2@alpha.com', password='Password123!', status='active')
        branchless_emp = Employee.objects.create(user=branchless_user, employee_code='NOBR02', organization=self.org1, branch=None)
        leave = LeaveRequest.objects.create(
            employee=branchless_emp,
            leave_type=self.leave_type1,
            start_date=date(2026, 9, 8),
            end_date=date(2026, 9, 9),
            reason='Historical request',
            status='pending'
        )

        self.client.force_authenticate(user=branchless_user)
        # Detail view
        resp_detail = self.client.get(reverse('leave-requests-detail', kwargs={'pk': leave.pk}))
        self.assertEqual(resp_detail.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp_detail.data['duration_days'])

        # List view
        resp_list = self.client.get(reverse('leave-requests-list'))
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        items = resp_list.data if isinstance(resp_list.data, list) else resp_list.data.get('results', [])
        self.assertEqual(len(items), 1)
        self.assertIsNone(items[0]['duration_days'])

    # -------------------------------------------------------------------------
    # CASE G: branchless payroll calculation -> controlled configuration error
    # -------------------------------------------------------------------------
    def test_case_g_branchless_payroll_calculation_raises_working_calendar_configuration_error(self):
        branchless_user = User.objects.create_user(email='nobranch3@alpha.com', password='Password123!', status='active')
        branchless_emp = Employee.objects.create(user=branchless_user, employee_code='NOBR03', organization=self.org1, branch=None)
        LeaveRequest.objects.create(
            employee=branchless_emp,
            leave_type=self.leave_type1,
            start_date=date(2026, 9, 7),
            end_date=date(2026, 9, 8),
            reason='Approved without branch',
            status='approved'
        )

        with self.assertRaises(WorkingCalendarConfigurationError):
            _approved_leave_days(branchless_emp, date(2026, 9, 1), date(2026, 9, 30))

    # -------------------------------------------------------------------------
    # CASE H: Super Admin unfiltered leave list -> no global dataset
    # -------------------------------------------------------------------------
    def test_case_h_super_admin_unfiltered_leave_list_returns_no_global_dataset(self):
        # Create leaves in Org 1 and Org 2
        LeaveRequest.objects.create(
            employee=self.emp1,
            leave_type=self.leave_type1,
            start_date=date(2026, 9, 7),
            end_date=date(2026, 9, 8),
            reason='Org 1 leave',
            status='approved'
        )
        LeaveRequest.objects.create(
            employee=self.emp2,
            leave_type=self.leave_type2,
            start_date=date(2026, 9, 7),
            end_date=date(2026, 9, 8),
            reason='Org 2 leave',
            status='approved'
        )

        self.client.force_authenticate(user=self.superadmin)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            resp = self.client.get(reverse('leave-requests-list'))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        items = resp.data if isinstance(resp.data, list) else resp.data.get('results', [])
        # Must return empty list, NOT all organizations' leaves
        self.assertEqual(len(items), 0)

    # -------------------------------------------------------------------------
    # CASE I: Super Admin authorized organization filter -> works
    # -------------------------------------------------------------------------
    def test_case_i_super_admin_authorized_org_filter_works(self):
        lr1 = LeaveRequest.objects.create(
            employee=self.emp1,
            leave_type=self.leave_type1,
            start_date=date(2026, 9, 7),
            end_date=date(2026, 9, 8),
            reason='Org 1 leave',
            status='approved'
        )
        lr2 = LeaveRequest.objects.create(
            employee=self.emp2,
            leave_type=self.leave_type2,
            start_date=date(2026, 9, 7),
            end_date=date(2026, 9, 8),
            reason='Org 2 leave',
            status='approved'
        )

        self.client.force_authenticate(user=self.superadmin)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            resp = self.client.get(f"{reverse('leave-requests-list')}?organization_id={self.org1.id}")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        items = resp.data if isinstance(resp.data, list) else resp.data.get('results', [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['id'], lr1.id)

    # -------------------------------------------------------------------------
    # CASE J: cross-tenant organization/branch filter -> denied
    # -------------------------------------------------------------------------
    def test_case_j_cross_tenant_filter_denied(self):
        # User in Org 1 tries to supply organization_id of Org 2 or branch of Org 2
        self.client.force_authenticate(user=self.user1)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True), \
             patch('apps.authorization.services.AuthorizationService.get_authorized_branches', return_value=[self.branch1]):
            # Passing foreign branch
            resp = self.client.get(f"{reverse('leave-requests-list')}?branch_id={self.branch2.id}")
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

            # Passing foreign organization
            resp_org = self.client.get(f"{reverse('leave-requests-list')}?organization_id={self.org2.id}")
            self.assertEqual(resp_org.status_code, status.HTTP_403_FORBIDDEN)

            # Passing foreign employee
            resp_emp = self.client.get(f"{reverse('leave-requests-list')}?employee_id={self.emp2.id}")
            self.assertEqual(resp_emp.status_code, status.HTTP_403_FORBIDDEN)

            # Authorized branch filter -> 200
            resp_auth = self.client.get(f"{reverse('leave-requests-list')}?branch_id={self.branch1.id}")
            self.assertEqual(resp_auth.status_code, status.HTTP_200_OK)

            # Authorized organization filter -> 200
            resp_auth_org = self.client.get(f"{reverse('leave-requests-list')}?organization_id={self.org1.id}")
            self.assertEqual(resp_auth_org.status_code, status.HTTP_200_OK)

    def test_case_j_superadmin_cross_tenant_combination_denied(self):
        self.client.force_authenticate(user=self.superadmin)
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            # Superadmin specifying Org 1 with Branch of Org 2
            resp = self.client.get(f"{reverse('leave-requests-list')}?organization_id={self.org1.id}&branch_id={self.branch2.id}")
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

            # Superadmin specifying Org 1 with Employee of Org 2
            resp2 = self.client.get(f"{reverse('leave-requests-list')}?organization_id={self.org1.id}&employee_id={self.emp2.id}")
            self.assertEqual(resp2.status_code, status.HTTP_403_FORBIDDEN)


class LeaveConcurrencyTests(TransactionTestCase):
    """
    CASE D: Concurrency test using TransactionTestCase.
    Two cancellation attempts for the same approved leave cannot both refund the balance.
    Exactly one cancellation/refund succeeds.
    No negative or double-refunded balance is possible.
    """
    def setUp(self):
        self.org = Organization.objects.create(name='Org Concurrency')
        self.branch = Branch.objects.create(organization=self.org, name='Main')
        self.user = User.objects.create_user(email='conc@example.com', password='Password123!', status='active')
        self.employee = Employee.objects.create(user=self.user, employee_code='CONC01', organization=self.org, branch=self.branch)
        self.leave_type = LeaveType.objects.create(organization=self.org, name='Casual Leave')
        from apps.leaves.models import LeaveCycle
        from datetime import date
        self.cycle = LeaveCycle.objects.create(branch=self.branch, name='C', start_date=date(2026,1,1), end_date=date(2026,12,31))
        self.balance = LeaveBalance.objects.create(employee=self.employee, leave_type=self.leave_type, branch=self.branch, leave_cycle=self.cycle, allocated=10, used=0)
        self.balance.used = 2
        self.balance.save()

        base_date = date(2026, 9, 7)  # Monday
        self.leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=base_date,
            end_date=base_date + timedelta(days=1),
            reason='Concurrency test',
            status='approved'
        )

    def test_case_d_concurrent_cancellation_only_one_refund(self):
        results = []

        def cancel_attempt():
            # Use separate database connection for thread
            from rest_framework.test import APIClient
            from unittest.mock import patch
            client = APIClient()
            client.force_authenticate(user=self.user)
            with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True), \
                 patch('apps.authorization.services.AuthorizationService.get_authorized_branches', return_value=[self.branch]):
                res = client.post(reverse('leave-requests-cancel', kwargs={'pk': self.leave.pk}))
                results.append(res.status_code)
            connection.close()

        t1 = threading.Thread(target=cancel_attempt)
        t2 = threading.Thread(target=cancel_attempt)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly one cancellation/refund succeeds
        self.assertEqual(results.count(status.HTTP_200_OK), 1)
        self.assertEqual(results.count(status.HTTP_400_BAD_REQUEST), 1)

        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used, 0)
        self.leave.refresh_from_db()
        self.assertEqual(self.leave.status, 'cancelled')
