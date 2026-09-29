from django.test import TestCase
from django.core.management import call_command
from apps.organization.models import Organization, Branch
from apps.leaves.models import LeaveType, BranchLeavePolicy, LeaveCycle
from apps.employees.models import Employee

class SeedTest(TestCase):
    def test_seed_idempotency(self):
        # Run seed first time
        call_command('seed')

        # Verify counts
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(Branch.objects.count(), 1)
        self.assertEqual(LeaveType.objects.count(), 3)
        self.assertEqual(BranchLeavePolicy.objects.count(), 3)
        self.assertEqual(LeaveCycle.objects.count(), 1)

        # Run seed second time
        call_command('seed')

        # Verify counts remain exactly the same
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(Branch.objects.count(), 1)
        self.assertEqual(LeaveType.objects.count(), 3)
        self.assertEqual(BranchLeavePolicy.objects.count(), 3)
        self.assertEqual(LeaveCycle.objects.count(), 1)

    def test_seed_branch_policy_calculation(self):
        call_command('seed')
        # Check annual allocation / 12 calculation for 'Annual Leave'
        annual_leave_type = LeaveType.objects.get(name='Annual Leave')
        policy = BranchLeavePolicy.objects.get(leave_type=annual_leave_type)
        # 20 / 12 = 1.67
        self.assertEqual(float(policy.monthly_allocation), 1.67)
