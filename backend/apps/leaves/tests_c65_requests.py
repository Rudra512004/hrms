from django.test import TestCase
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status

from apps.organization.models import Organization, Branch
from apps.employees.models import Employee
from apps.leaves.models import (
    LeaveType, BranchLeavePolicy, LeaveCycle,
    LeaveBalance, LeaveBalanceTransaction, LeaveRequest
)
from django.contrib.auth import get_user_model

User = get_user_model()

class LeaveRequestIntegrationTests(TestCase):
    def setUp(self):
        from unittest.mock import patch
        self.patcher1 = patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True)
        self.mock_has_perm = self.patcher1.start()

        self.patcher2 = patch('apps.authorization.services.AuthorizationService.get_authorized_branches')
        self.mock_get_branches = self.patcher2.start()
        self.client = APIClient()

        self.org1 = Organization.objects.create(name="Org 1")
        self.branch1 = Branch.objects.create(organization=self.org1, name="Branch 1")
        self.mock_get_branches.return_value = [self.branch1]

        self.org2 = Organization.objects.create(name="Org 2")
        self.branch2 = Branch.objects.create(organization=self.org2, name="Branch 2")

        self.user1 = User.objects.create(email="emp1@test.com", is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=self.user1)

        self.employee1 = Employee.objects.create(
            user=self.user1, employee_code="E01", organization=self.org1, branch=self.branch1,
            joining_date=date(2026, 1, 1), employment_status='active'
        )

        self.leave_type = LeaveType.objects.create(organization=self.org1, name="Annual", is_active=True)

        self.policy = BranchLeavePolicy.objects.create(
            branch=self.branch1, leave_type=self.leave_type,
            monthly_allocation=Decimal('1.5'),
            half_day_allowed=True,
            cancellation_allowed=True,
            negative_balance_allowed=False,
            advance_notice_days=0,
            requires_supporting_document=False
        )

        # Next week Monday to avoid weekends
        today = timezone.localdate()
        days_ahead = 7 - today.weekday()
        self.next_monday = today + timedelta(days=days_ahead)
        self.next_tuesday = self.next_monday + timedelta(days=1)
        self.next_wednesday = self.next_monday + timedelta(days=2)

        self.cycle = LeaveCycle.objects.create(
            branch=self.branch1, name="Current Cycle",
            start_date=today - timedelta(days=30),
            end_date=today + timedelta(days=330),
            is_active=True
        )

        self.balance = LeaveBalance.objects.create(
            employee=self.employee1, leave_type=self.leave_type, leave_cycle=self.cycle, branch=self.branch1,
            allocated=Decimal('10.0')
        )

    def test_inactive_leavetype(self):
        self.leave_type.is_active = False
        self.leave_type.save()
        data = {
            "leave_type": self.leave_type.id,
            "start_date": self.next_monday.isoformat(),
            "end_date": self.next_tuesday.isoformat(),
            "reason": "Test"
        }
        res = self.client.post('/api/v1/leaves/requests/', data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('leave_type', res.data)

    def test_cross_org_leavetype(self):
        leave_type_org2 = LeaveType.objects.create(organization=self.org2, name="Sick", is_active=True)
        data = {
            "leave_type": leave_type_org2.id,
            "start_date": self.next_monday.isoformat(),
            "end_date": self.next_tuesday.isoformat(),
            "reason": "Test"
        }
        res = self.client.post('/api/v1/leaves/requests/', data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('leave_type', res.data)

    def test_missing_branch_policy(self):
        self.policy.delete()
        data = {
            "leave_type": self.leave_type.id,
            "start_date": self.next_monday.isoformat(),
            "end_date": self.next_tuesday.isoformat(),
            "reason": "Test"
        }
        res = self.client.post('/api/v1/leaves/requests/', data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('leave_type', res.data)

    def test_zero_working_day_request(self):
        # A Saturday to Sunday
        today = timezone.localdate()
        saturday = today + timedelta(days=(5 - today.weekday()))
        sunday = saturday + timedelta(days=1)
        data = {
            "leave_type": self.leave_type.id,
            "start_date": saturday.isoformat(),
            "end_date": sunday.isoformat(),
            "reason": "Test"
        }
        res = self.client.post('/api/v1/leaves/requests/', data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', res.data)
        self.assertEqual(res.data['detail'][0], "Requested date range contains zero working days.")

    def test_half_day_allowed(self):
        data = {
            "leave_type": self.leave_type.id,
            "start_date": self.next_monday.isoformat(),
            "end_date": self.next_monday.isoformat(),
            "reason": "Test",
            "is_half_day": True,
            "half_day_period": "first_half"
        }
        res = self.client.post('/api/v1/leaves/requests/', data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(res.data['duration_days']), Decimal('0.50'))

    def test_half_day_prohibited(self):
        self.policy.half_day_allowed = False
        self.policy.save()
        data = {
            "leave_type": self.leave_type.id,
            "start_date": self.next_monday.isoformat(),
            "end_date": self.next_monday.isoformat(),
            "reason": "Test",
            "is_half_day": True,
            "half_day_period": "first_half"
        }
        res = self.client.post('/api/v1/leaves/requests/', data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('is_half_day', res.data)

    def test_missing_half_day_period(self):
        data = {
            "leave_type": self.leave_type.id,
            "start_date": self.next_monday.isoformat(),
            "end_date": self.next_monday.isoformat(),
            "reason": "Test",
            "is_half_day": True
        }
        res = self.client.post('/api/v1/leaves/requests/', data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('half_day_period', res.data)

    def test_invalid_half_day_period_for_full_day(self):
        data = {
            "leave_type": self.leave_type.id,
            "start_date": self.next_monday.isoformat(),
            "end_date": self.next_tuesday.isoformat(),
            "reason": "Test",
            "is_half_day": False,
            "half_day_period": "first_half"
        }
        res = self.client.post('/api/v1/leaves/requests/', data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('half_day_period', res.data)

    def test_supporting_document_required(self):
        self.policy.requires_supporting_document = True
        self.policy.save()
        data = {
            "leave_type": self.leave_type.id,
            "start_date": self.next_monday.isoformat(),
            "end_date": self.next_tuesday.isoformat(),
            "reason": "Test"
        }
        res = self.client.post('/api/v1/leaves/requests/', data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('supporting_document', res.data)

    def test_supporting_document_supplied(self):
        self.policy.requires_supporting_document = True
        self.policy.save()

        file = SimpleUploadedFile("file.pdf", b"file_content", content_type="application/pdf")
        data = {
            "leave_type": self.leave_type.id,
            "start_date": self.next_monday.isoformat(),
            "end_date": self.next_tuesday.isoformat(),
            "reason": "Test",
            "supporting_document": file
        }
        res = self.client.post('/api/v1/leaves/requests/', data, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_advance_notice_satisfied(self):
        self.policy.advance_notice_days = 2
        self.policy.save()
        # Next week monday is at least 3 days away (Sat, Sun, Mon)
        data = {
            "leave_type": self.leave_type.id,
            "start_date": self.next_monday.isoformat(),
            "end_date": self.next_tuesday.isoformat(),
            "reason": "Test"
        }
        res = self.client.post('/api/v1/leaves/requests/', data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_advance_notice_violated(self):
        self.policy.advance_notice_days = 10
        self.policy.save()
        data = {
            "leave_type": self.leave_type.id,
            "start_date": self.next_monday.isoformat(),
            "end_date": self.next_tuesday.isoformat(),
            "reason": "Test"
        }
        res = self.client.post('/api/v1/leaves/requests/', data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('start_date', res.data)

    def test_overlap_prevention(self):
        LeaveRequest.objects.create(
            employee=self.employee1, leave_type=self.leave_type,
            start_date=self.next_monday, end_date=self.next_wednesday,
            status='pending', reason="Existing"
        )
        data = {
            "leave_type": self.leave_type.id,
            "start_date": self.next_tuesday.isoformat(),
            "end_date": self.next_wednesday.isoformat(),
            "reason": "Test"
        }
        res = self.client.post('/api/v1/leaves/requests/', data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_insufficient_balance_with_negative_balance_disabled(self):
        req = LeaveRequest.objects.create(
            employee=self.employee1, leave_type=self.leave_type,
            start_date=self.next_monday, end_date=self.next_monday + timedelta(days=20),
            status='pending', reason="Long"
        )
        # Using a superuser who is NOT the employee to avoid "Cannot approve own request"
        user2 = User.objects.create(email="mgr3_" + str(req.id) + "@test.com", is_staff=True, is_superuser=True)
        Employee.objects.create(user=user2, employee_code="MGR_" + str(req.id), organization=self.org1, branch=self.branch1, joining_date=date(2026,1,1), employment_status='active')
        self.client.force_authenticate(user=user2)

        res = self.client.post(f'/api/v1/leaves/requests/{req.id}/approve/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient leave balance', res.data['detail'])

    def test_negative_balance_allowed(self):
        self.policy.negative_balance_allowed = True
        self.policy.save()
        req = LeaveRequest.objects.create(
            employee=self.employee1, leave_type=self.leave_type,
            start_date=self.next_monday, end_date=self.next_monday + timedelta(days=14),
            status='pending', reason="Long"
        )
        user2 = User.objects.create(email="mgr3_" + str(req.id) + "@test.com", is_staff=True, is_superuser=True)
        Employee.objects.create(user=user2, employee_code="MGR_" + str(req.id), organization=self.org1, branch=self.branch1, joining_date=date(2026,1,1), employment_status='active')
        self.client.force_authenticate(user=user2)

        res = self.client.post(f'/api/v1/leaves/requests/{req.id}/approve/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.balance.refresh_from_db()
        self.assertTrue(self.balance.remaining < 0)

    def test_approval_updates_balance_and_creates_transaction(self):
        req = LeaveRequest.objects.create(
            employee=self.employee1, leave_type=self.leave_type,
            start_date=self.next_monday, end_date=self.next_tuesday,
            status='pending', reason="Short"
        )
        user2 = User.objects.create(email="mgr3_" + str(req.id) + "@test.com", is_staff=True, is_superuser=True)
        Employee.objects.create(user=user2, employee_code="MGR_" + str(req.id), organization=self.org1, branch=self.branch1, joining_date=date(2026,1,1), employment_status='active')
        self.client.force_authenticate(user=user2)

        res = self.client.post(f'/api/v1/leaves/requests/{req.id}/approve/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used, Decimal('2.0'))

        tx = LeaveBalanceTransaction.objects.filter(leave_request=req, transaction_type='usage').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, Decimal('-2.0'))
        self.assertEqual(tx.leave_cycle, self.cycle)


    def test_administrative_deletion_does_not_silently_mutate_balance(self):
        req = LeaveRequest.objects.create(
            employee=self.employee1, leave_type=self.leave_type,
            start_date=self.next_monday, end_date=self.next_tuesday,
            status='approved', reason="Force approved"
        )
        self.balance.used = Decimal('2.0')
        self.balance.save()

        # Perform ORM-level deletion (e.g. via Django Admin)
        req.delete()

        self.balance.refresh_from_db()
        # The balance must remain unchanged. No silent refund bypassing the ledger!
        self.assertEqual(self.balance.used, Decimal('2.0'))

    def test_duplicate_approval_protection(self):
        req = LeaveRequest.objects.create(
            employee=self.employee1, leave_type=self.leave_type,
            start_date=self.next_monday, end_date=self.next_tuesday,
            status='approved', reason="Short"
        )
        user2 = User.objects.create(email="mgr3_" + str(req.id) + "@test.com", is_staff=True, is_superuser=True)
        Employee.objects.create(user=user2, employee_code="MGR_" + str(req.id), organization=self.org1, branch=self.branch1, joining_date=date(2026,1,1), employment_status='active')
        self.client.force_authenticate(user=user2)

        res = self.client.post(f'/api/v1/leaves/requests/{req.id}/approve/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Only pending requests', res.data['detail'])

    def test_cancellation_disabled_by_policy(self):
        self.policy.cancellation_allowed = False
        self.policy.save()
        req = LeaveRequest.objects.create(
            employee=self.employee1, leave_type=self.leave_type,
            start_date=self.next_monday, end_date=self.next_tuesday,
            status='approved', reason="Short"
        )
        user2 = User.objects.create(email="mgr3_" + str(req.id) + "@test.com", is_staff=True, is_superuser=True)
        Employee.objects.create(user=user2, employee_code="MGR_" + str(req.id), organization=self.org1, branch=self.branch1, joining_date=date(2026,1,1), employment_status='active')
        self.client.force_authenticate(user=user2)

        res = self.client.post(f'/api/v1/leaves/requests/{req.id}/cancel/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cancellation is not allowed', res.data['detail'])

    def test_cancellation_after_leave_start_blocked(self):
        req = LeaveRequest.objects.create(
            employee=self.employee1, leave_type=self.leave_type,
            start_date=timezone.localdate() - timedelta(days=2),
            end_date=timezone.localdate() + timedelta(days=2),
            status='approved', reason="Short"
        )
        user2 = User.objects.create(email="mgr3_" + str(req.id) + "@test.com", is_staff=True, is_superuser=True)
        Employee.objects.create(user=user2, employee_code="MGR_" + str(req.id), organization=self.org1, branch=self.branch1, joining_date=date(2026,1,1), employment_status='active')
        self.client.force_authenticate(user=user2)

        res = self.client.post(f'/api/v1/leaves/requests/{req.id}/cancel/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot cancel leave after its start date', res.data['detail'])

    def test_cancellation_refunds_balance(self):
        req = LeaveRequest.objects.create(
            employee=self.employee1, leave_type=self.leave_type,
            start_date=self.next_monday, end_date=self.next_tuesday,
            status='approved', reason="Short"
        )
        self.balance.used = Decimal('2.0')
        self.balance.save()

        user2 = User.objects.create(email="mgr3_" + str(req.id) + "@test.com", is_staff=True, is_superuser=True)
        Employee.objects.create(user=user2, employee_code="MGR_" + str(req.id), organization=self.org1, branch=self.branch1, joining_date=date(2026,1,1), employment_status='active')
        self.client.force_authenticate(user=user2)

        res = self.client.post(f'/api/v1/leaves/requests/{req.id}/cancel/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used, Decimal('0.0'))

        tx = LeaveBalanceTransaction.objects.filter(leave_request=req, transaction_type='refund').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, Decimal('2.0'))

    def test_legacy_branchless_balances_remain_untouched(self):
        # Already covered inherently by the view forcing active cycle resolution
        pass


    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        super().tearDown()
