from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import date
from apps.organization.models import Organization, Branch
from apps.leaves.models import LeaveType, BranchLeavePolicy, LeaveCycle

class C63ModelValidationTests(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="Org 1")
        self.branch1 = Branch.objects.create(organization=self.org1, name="Branch 1")
        
        self.org2 = Organization.objects.create(name="Org 2")
        self.branch2 = Branch.objects.create(organization=self.org2, name="Branch 2")
        
        self.leave_type1 = LeaveType.objects.create(organization=self.org1, name="Annual Leave")

    def test_branch_policy_cross_org_rejection(self):
        policy = BranchLeavePolicy(
            branch=self.branch2,  # Org 2
            leave_type=self.leave_type1, # Org 1
            monthly_allocation=10
        )
        with self.assertRaises(ValidationError) as ctx:
            policy.clean()
        self.assertIn("Branch and LeaveType must belong to the same organization.", str(ctx.exception))

    def test_branch_policy_uniqueness(self):
        BranchLeavePolicy.objects.create(
            branch=self.branch1,
            leave_type=self.leave_type1,
            monthly_allocation=10
        )
        policy2 = BranchLeavePolicy(
            branch=self.branch1,
            leave_type=self.leave_type1,
            monthly_allocation=5
        )
        # Should raise integrity error on save or validation error on clean
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            policy2.save()

    def test_leave_cycle_end_before_start_rejection(self):
        cycle = LeaveCycle(
            branch=self.branch1,
            name="Invalid Cycle",
            start_date=date(2026, 12, 31),
            end_date=date(2026, 1, 1)
        )
        with self.assertRaises(ValidationError) as ctx:
            cycle.clean()
        self.assertIn("End date cannot be before start date", str(ctx.exception))

    def test_leave_cycle_overlap_validation(self):
        LeaveCycle.objects.create(
            branch=self.branch1,
            name="Cycle 1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            is_active=True
        )
        cycle2 = LeaveCycle(
            branch=self.branch1,
            name="Cycle 2 Overlapping",
            start_date=date(2026, 6, 1), # overlaps June
            end_date=date(2026, 12, 31),
            is_active=True
        )
        with self.assertRaises(ValidationError) as ctx:
            cycle2.clean()
        self.assertIn("Overlapping active cycle exists", str(ctx.exception))

    def test_leave_cycle_overlap_allowed_if_inactive(self):
        LeaveCycle.objects.create(
            branch=self.branch1,
            name="Cycle 1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            is_active=False
        )
        cycle2 = LeaveCycle(
            branch=self.branch1,
            name="Cycle 2",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 12, 31),
            is_active=True
        )
        # Should not raise validation error
        cycle2.clean()
        cycle2.save()
        self.assertEqual(LeaveCycle.objects.count(), 2)

    def test_leave_balance_operational_invariant(self):
        from apps.employees.models import Employee
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create(email='test@example.com')
        emp = Employee.objects.create(user=user, employee_code='E01', organization=self.org1, branch=self.branch1)
        
        from apps.leaves.models import LeaveBalance
        
        # New balance without branch/cycle
        balance = LeaveBalance(
            employee=emp,
            leave_type=self.leave_type1,
            allocated=10
        )
        with self.assertRaises(ValidationError) as ctx:
            balance.clean()
        self.assertIn("Operational LeaveBalance must have branch and leave_cycle assigned", str(ctx.exception))

