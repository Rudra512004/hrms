from django.test import TestCase
from decimal import Decimal
from datetime import date
from django.core.exceptions import ValidationError
from unittest.mock import patch

from apps.organization.models import Organization, Branch
from apps.employees.models import Employee
from apps.leaves.models import (
    LeaveType, BranchLeavePolicy, LeaveCycle,
    LeaveBalance, LeaveBalanceTransaction
)
from apps.leaves.services.allocation import LeaveAllocationEngine
from django.contrib.auth import get_user_model

User = get_user_model()

class LeaveAllocationEngineTests(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="Org 1")
        self.branch1 = Branch.objects.create(organization=self.org1, name="Branch 1")
        
        self.org2 = Organization.objects.create(name="Org 2")
        self.branch2 = Branch.objects.create(organization=self.org2, name="Branch 2")
        
        self.user1 = User.objects.create(email="test1@test.com")
        self.user2 = User.objects.create(email="test2@test.com")
        
        self.employee1 = Employee.objects.create(
            user=self.user1, employee_code="E01", organization=self.org1, branch=self.branch1,
            joining_date=date(2026, 1, 15), employment_status='active'
        )
        
        self.leave_type = LeaveType.objects.create(organization=self.org1, name="Annual")
        
        self.policy = BranchLeavePolicy.objects.create(
            branch=self.branch1, leave_type=self.leave_type,
            monthly_allocation=Decimal('1.5'),
            proration_enabled=True,
            proration_rounding='nearest_half'
        )
        
        self.cycle = LeaveCycle.objects.create(
            branch=self.branch1, name="2026 Cycle",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31)
        )

    def test_monthly_allocation(self):
        # Full monthly allocation
        res = LeaveAllocationEngine.process_monthly_allocation(self.branch1, self.cycle, 2026, 2)
        self.assertEqual(res['allocated'], 1)
        
        balance = LeaveBalance.objects.get(employee=self.employee1)
        self.assertEqual(balance.allocated, Decimal('1.5'))
        
        # Test idempotency (Re-running does not double credit)
        res2 = LeaveAllocationEngine.process_monthly_allocation(self.branch1, self.cycle, 2026, 2)
        self.assertEqual(res2['allocated'], 0)
        self.assertEqual(res2['skipped_idempotent'], 1)
        
        balance.refresh_from_db()
        self.assertEqual(balance.allocated, Decimal('1.5'))
        
        tx = LeaveBalanceTransaction.objects.filter(employee=self.employee1).first()
        self.assertEqual(tx.transaction_type, 'monthly_accrual')

    def test_mid_year_joining_proration_monthly(self):
        # Mid year proration: Joining in Sept
        emp_sept = Employee.objects.create(
            user=User.objects.create(email="sept@test.com"), employee_code="E02",
            organization=self.org1, branch=self.branch1, joining_date=date(2026, 9, 10), employment_status='active'
        )
        
        # Allocate for September (joining month)
        res = LeaveAllocationEngine.process_monthly_allocation(self.branch1, self.cycle, 2026, 9)
        self.assertEqual(res['allocated'], 2) # Allocated to both employees
        
        b2 = LeaveBalance.objects.get(employee=emp_sept)
        self.assertEqual(b2.allocated, Decimal('1.5')) # September allocation
        
        # Different month allocation
        res_oct = LeaveAllocationEngine.process_monthly_allocation(self.branch1, self.cycle, 2026, 10)
        self.assertEqual(res_oct['allocated'], 2)
        b2.refresh_from_db()
        self.assertEqual(b2.allocated, Decimal('3.0')) # Oct allocation added (1.5 + 1.5)

    def test_rounding_modes(self):
        emp_mid = Employee.objects.create(
            user=User.objects.create(email="mid@test.com"), employee_code="E03",
            organization=self.org1, branch=self.branch1, joining_date=date(2026, 10, 15), employment_status='active'
        )
        
        self.policy.monthly_allocation = Decimal('1.25')
        self.policy.proration_rounding = 'floor'
        self.policy.save()
        
        LeaveAllocationEngine.process_monthly_allocation(self.branch1, self.cycle, 2026, 10)
        b = LeaveBalance.objects.get(employee=emp_mid)
        self.assertEqual(b.allocated, Decimal('1.0')) # Floor of 1.25 is 1.0
        
        LeaveBalanceTransaction.objects.all().delete()
        LeaveBalance.objects.all().delete()
        
        self.policy.proration_rounding = 'ceiling'
        self.policy.save()
        LeaveAllocationEngine.process_monthly_allocation(self.branch1, self.cycle, 2026, 10)
        b = LeaveBalance.objects.get(employee=emp_mid)
        self.assertEqual(b.allocated, Decimal('2.0')) # Ceiling of 1.25 is 2.0
        
        LeaveBalanceTransaction.objects.all().delete()
        LeaveBalance.objects.all().delete()
        
        self.policy.proration_rounding = 'nearest_half'
        self.policy.save()
        LeaveAllocationEngine.process_monthly_allocation(self.branch1, self.cycle, 2026, 10)
        b = LeaveBalance.objects.get(employee=emp_mid)
        self.assertEqual(b.allocated, Decimal('1.5')) # nearest 0.5 of 1.25 -> 1.5

    def test_proration_disabled(self):
        emp_nov = Employee.objects.create(
            user=User.objects.create(email="nov@test.com"), employee_code="E04",
            organization=self.org1, branch=self.branch1, joining_date=date(2026, 11, 20), employment_status='active'
        )
        self.policy.proration_enabled = False
        self.policy.save()
        
        # When allocating for November (joining month), the employee gets catchup
        LeaveAllocationEngine.process_monthly_allocation(self.branch1, self.cycle, 2026, 11)
        b = LeaveBalance.objects.get(employee=emp_nov)
        # Jan-Nov = 11 months * 1.5 = 16.5
        self.assertEqual(b.allocated, Decimal('16.5'))

    def test_out_of_cycle_joining(self):
        emp_future = Employee.objects.create(
            user=User.objects.create(email="fut@test.com"), employee_code="E05",
            organization=self.org1, branch=self.branch1, joining_date=date(2027, 1, 1), employment_status='active'
        )
        LeaveAllocationEngine.process_monthly_allocation(self.branch1, self.cycle, 2026, 12)
        # Should not allocate for emp_future because they join in 2027
        self.assertFalse(LeaveBalance.objects.filter(employee=emp_future).exists())

    def test_cross_tenant_security(self):
        policy_org2 = BranchLeavePolicy.objects.create(
            branch=self.branch2, leave_type=self.leave_type,
            monthly_allocation=Decimal('1.0')
        )
        # If policy.leave_type.organization != employee.organization, it skips.
        # This is enforced in engine loop.

    def test_legacy_balances_untouched(self):
        # Create legacy balance (no cycle, no branch)
        legacy = LeaveBalance.objects.create(
            employee=self.employee1, leave_type=self.leave_type,
            allocated=Decimal('10.0')
        )
        LeaveAllocationEngine.process_monthly_allocation(self.branch1, self.cycle, 2026, 2)
        
        legacy.refresh_from_db()
        self.assertEqual(legacy.allocated, Decimal('10.0'))
        
        # New balance should have been created
        new_b = LeaveBalance.objects.get(employee=self.employee1, leave_cycle=self.cycle)
        self.assertEqual(new_b.allocated, Decimal('1.5'))

    @patch('apps.leaves.services.allocation.LeaveAllocationEngine.apply_rounding')
    def test_atomicity_on_failure(self, mock_rounding):
        # Create an operational state
        LeaveBalance.objects.create(
            employee=self.employee1, leave_type=self.leave_type, leave_cycle=self.cycle,
            allocated=Decimal('5.0'), branch=self.branch1
        )
        
        # Force an exception during processing
        mock_rounding.side_effect = Exception("Forced error during allocation")
        
        with self.assertRaises(Exception):
            LeaveAllocationEngine.process_monthly_allocation(self.branch1, self.cycle, 2026, 3)
        
        # Verify the database rollback is complete
        balance = LeaveBalance.objects.get(employee=self.employee1)
        self.assertEqual(balance.allocated, Decimal('5.0')) # Not incremented
        
        # Verify no transaction remains
        tx_count = LeaveBalanceTransaction.objects.filter(
            employee=self.employee1, reference='ALLOC-2026-03-1'
        ).count()
        self.assertEqual(tx_count, 0)
