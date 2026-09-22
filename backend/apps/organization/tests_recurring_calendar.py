from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.core.exceptions import ValidationError

from apps.organization.models import Organization, Branch, OfficeNetwork, WorkingCalendar, WorkingCalendarRule
from apps.organization.services import WorkingCalendarService
from apps.organization.exceptions import WorkingCalendarConfigurationError
from apps.attendance.models import Holiday, Shift, EmployeeShiftAssignment
from apps.attendance.services import AttendanceCalculationService
from apps.leaves.models import LeaveRequest, LeaveType
from apps.payroll.services import _working_days_in_period
from apps.employees.models import Employee, EmploymentStatus
from apps.authorization.models import Role, Permission, UserRole, RolePermission, ScopeChoices

User = get_user_model()


class RecurringWorkingCalendarTests(TestCase):
    """
    C5.5.4A — Comprehensive Recurring Working Calendar Rules Test Suite:
    Verifies:
    1. 1st Saturday rule
    2. 3rd Saturday rule
    3. 5th Saturday rule
    4. 2nd/4th Saturday remain governed by base calendar when no rule exists
    5. Rule on another weekday (Wednesday)
    6. Explicit Holiday overrides working status (precedence 1)
    7. No recurring rules preserves existing behavior
    8. Invalid weekday rejected (< 0 or > 6)
    9. Invalid occurrence rejected (< 1 or > 5)
    10. Duplicate rule in same calendar rejected
    11. Branch A cannot read Branch B rules (404 IDOR protection)
    12. Branch A cannot modify Branch B rules (404 IDOR protection)
    13. Organization-wide authorized user can manage authorized branches
    14. Cross-tenant isolation
    15. Unauthorized user denied (401/403)
    16. Attendance calculation uses recurring rule (resolve_scheduled_shift)
    17. Leave duration_days and Payroll working-day calculation use identical recurring rule results
    18. No Mon-Fri fallback introduced (strict configuration error when calendar missing)
    19. Concrete September 2026 scenario verified across all four consumers
    """

    def setUp(self):
        self.client = APIClient()

        # Organization Alpha
        self.org_a = Organization.objects.create(name='Org Alpha', status='active')

        # Branch A
        self.branch_a = Branch.objects.create(organization=self.org_a, name='Branch A', radius=100)
        self.cal_a = self.branch_a.working_calendar
        self.cal_a.work_days = '0,1,2,3,4,5'  # Mon-Sat working
        self.cal_a.save()

        # Branch B
        self.branch_b = Branch.objects.create(organization=self.org_a, name='Branch B', radius=100)
        self.cal_b = self.branch_b.working_calendar
        self.cal_b.work_days = '0,1,2,3,4'  # Mon-Fri working
        self.cal_b.save()

        # Office network allowing 127.0.0.1
        OfficeNetwork.objects.create(
            branch=self.branch_a,
            name='Alpha Net',
            network='127.0.0.1/32',
            is_active=True
        )
        OfficeNetwork.objects.create(
            branch=self.branch_b,
            name='Alpha Net B',
            network='127.0.0.1/32',
            is_active=True
        )

        # Tenant Beta (for cross-tenant test)
        self.org_b = Organization.objects.create(name='Tenant Beta', status='active')
        self.branch_beta = Branch.objects.create(organization=self.org_b, name='Branch Beta', radius=100)
        self.cal_beta = self.branch_beta.working_calendar
        self.cal_beta.work_days = '0,1,2,3,4'
        self.cal_beta.save()

        # Permission setup
        self.perm_update, _ = Permission.objects.get_or_create(
            codename='organization.update',
            defaults={'name': 'Update Org', 'resource': 'organization', 'action': 'update'}
        )

        # Role for Branch A manager
        self.role_branch_a = Role.objects.create(organization=self.org_a, name='Branch A Manager')
        RolePermission.objects.create(role=self.role_branch_a, permission=self.perm_update)

        # User Manager A
        self.user_mgr_a = User.objects.create_user(email='mgr_a@alpha.local', password='Password123!', status='active')
        Employee.objects.create(
            user=self.user_mgr_a, organization=self.org_a, branch=self.branch_a,
            employee_code='MGR-A', employment_status=EmploymentStatus.ACTIVE
        )
        UserRole.objects.create(user=self.user_mgr_a, role=self.role_branch_a, scope=ScopeChoices.BRANCH, branch=self.branch_a)

        # Role for Org-wide manager
        self.role_org_wide = Role.objects.create(organization=self.org_a, name='Org Manager')
        RolePermission.objects.create(role=self.role_org_wide, permission=self.perm_update)

        # User Org Admin
        self.user_org_admin = User.objects.create_user(email='org_admin@alpha.local', password='Password123!', status='active')
        Employee.objects.create(
            user=self.user_org_admin, organization=self.org_a, branch=self.branch_a,
            employee_code='ORG-ADM', employment_status=EmploymentStatus.ACTIVE
        )
        UserRole.objects.create(user=self.user_org_admin, role=self.role_org_wide, scope=ScopeChoices.ORGANIZATION)

        # Superuser
        self.superuser = User.objects.create_superuser(email='super@company.local', password='Password123!')

        # Regular employee on Branch A
        self.user_emp_a = User.objects.create_user(email='emp_a@alpha.local', password='Password123!', status='active')
        self.employee_a = Employee.objects.create(
            user=self.user_emp_a, organization=self.org_a, branch=self.branch_a,
            employee_code='EMP-A001', employment_status=EmploymentStatus.ACTIVE
        )

        # Shift on Branch A
        self.shift_a = Shift.objects.create(
            branch=self.branch_a, name='Standard Shift',
            start_time='09:00:00', end_time='18:00:00',
            work_days='0,1,2,3,4,5', is_active=True
        )
        # Shift assignment for employee_a
        EmployeeShiftAssignment.objects.create(
            employee=self.employee_a, shift=self.shift_a,
            effective_from=date(2026, 1, 1)
        )

        # Leave Type
        self.leave_type = LeaveType.objects.create(
            organization=self.org_a, name='Annual Leave', annual_allocation=20, is_active=True
        )

    # -------------------------------------------------------------------------
    # 1 - 5, 19: Concrete September 2026 Scenario & Saturday Overrides
    # -------------------------------------------------------------------------
    def test_september_2026_concrete_scenario_across_all_consumers(self):
        """
        Base Saturday = working (work_days = 0,1,2,3,4,5)
        1st Saturday = OFF
        3rd Saturday = OFF

        Dates:
        2026-09-05 (1st Sat) -> Non-working
        2026-09-12 (2nd Sat) -> Working
        2026-09-19 (3rd Sat) -> Non-working
        2026-09-26 (4th Sat) -> Working

        Verified across:
        1. WorkingCalendarService.is_working_day
        2. AttendanceCalculationService.resolve_scheduled_shift
        3. LeaveRequest.duration_days
        4. payroll._working_days_in_period
        """
        # Configure rules: 1st Sat (occ 1, weekday 5) = False, 3rd Sat (occ 3, weekday 5) = False
        WorkingCalendarRule.objects.create(working_calendar=self.cal_a, weekday=5, occurrence=1, is_working=False)
        WorkingCalendarRule.objects.create(working_calendar=self.cal_a, weekday=5, occurrence=3, is_working=False)

        sep_05 = date(2026, 9, 5)   # 1st Saturday
        sep_12 = date(2026, 9, 12)  # 2nd Saturday
        sep_19 = date(2026, 9, 19)  # 3rd Saturday
        sep_26 = date(2026, 9, 26)  # 4th Saturday

        # 1. WorkingCalendarService.is_working_day
        self.assertFalse(WorkingCalendarService.is_working_day(self.branch_a, sep_05))
        self.assertTrue(WorkingCalendarService.is_working_day(self.branch_a, sep_12))
        self.assertFalse(WorkingCalendarService.is_working_day(self.branch_a, sep_19))
        self.assertTrue(WorkingCalendarService.is_working_day(self.branch_a, sep_26))

        # 2. AttendanceCalculationService.resolve_scheduled_shift
        self.assertIsNone(AttendanceCalculationService.resolve_scheduled_shift(self.employee_a, sep_05))
        self.assertEqual(AttendanceCalculationService.resolve_scheduled_shift(self.employee_a, sep_12), self.shift_a)
        self.assertIsNone(AttendanceCalculationService.resolve_scheduled_shift(self.employee_a, sep_19))
        self.assertEqual(AttendanceCalculationService.resolve_scheduled_shift(self.employee_a, sep_26), self.shift_a)

        # 3. LeaveRequest.duration_days
        # 1-day leaves on each Saturday
        leave_sep_05 = LeaveRequest(employee=self.employee_a, leave_type=self.leave_type, start_date=sep_05, end_date=sep_05)
        leave_sep_12 = LeaveRequest(employee=self.employee_a, leave_type=self.leave_type, start_date=sep_12, end_date=sep_12)
        leave_sep_19 = LeaveRequest(employee=self.employee_a, leave_type=self.leave_type, start_date=sep_19, end_date=sep_19)
        leave_sep_26 = LeaveRequest(employee=self.employee_a, leave_type=self.leave_type, start_date=sep_26, end_date=sep_26)

        self.assertEqual(leave_sep_05.duration_days, 0)
        self.assertEqual(leave_sep_12.duration_days, 1)
        self.assertEqual(leave_sep_19.duration_days, 0)
        self.assertEqual(leave_sep_26.duration_days, 1)

        # Full month of September 2026: 30 days total (22 Mon-Fri + 2 working Saturdays (12th, 26th) = 24 days)
        full_month_leave = LeaveRequest(
            employee=self.employee_a, leave_type=self.leave_type,
            start_date=date(2026, 9, 1), end_date=date(2026, 9, 30)
        )
        self.assertEqual(full_month_leave.duration_days, 24)

        # 4. Payroll working days in period
        payroll_days = _working_days_in_period(self.branch_a.id, date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual(payroll_days, 24)

    def test_fifth_saturday_configurable_rule(self):
        """5th Saturday rule can be explicitly configured as non-working."""
        # May 2026 has 5 Saturdays: May 2, 9, 16, 23, 30.
        # Day 30 is 5th Saturday: (30-1)//7 + 1 = 5
        WorkingCalendarRule.objects.create(working_calendar=self.cal_a, weekday=5, occurrence=5, is_working=False)

        may_30 = date(2026, 5, 30)
        self.assertFalse(WorkingCalendarService.is_working_day(self.branch_a, may_30))

        # May 23 (4th Saturday) has no rule, so it uses base Saturday (working)
        may_23 = date(2026, 5, 23)
        self.assertTrue(WorkingCalendarService.is_working_day(self.branch_a, may_23))

    def test_recurring_rule_on_other_weekday(self):
        """Recurring rule on Wednesday (weekday 2) as non-working override."""
        # 1st Wednesday of Oct 2026: Oct 7 ((7-1)//7 + 1 = 1)
        WorkingCalendarRule.objects.create(working_calendar=self.cal_a, weekday=2, occurrence=1, is_working=False)

        oct_07 = date(2026, 10, 7)
        oct_14 = date(2026, 10, 14)  # 2nd Wednesday

        self.assertFalse(WorkingCalendarService.is_working_day(self.branch_a, oct_07))
        self.assertTrue(WorkingCalendarService.is_working_day(self.branch_a, oct_14))

    # -------------------------------------------------------------------------
    # 6: Precedence - Explicit Holiday Overrides Working Rule and Base Calendar
    # -------------------------------------------------------------------------
    def test_explicit_holiday_overrides_working_status(self):
        """An active explicit Holiday always overrides working rules and base calendar."""
        # Sep 12 is 2nd Saturday (normally working)
        sep_12 = date(2026, 9, 12)
        self.assertTrue(WorkingCalendarService.is_working_day(self.branch_a, sep_12))

        # Create active Holiday on Sep 12
        Holiday.objects.create(branch=self.branch_a, name='Branch Day', date=sep_12, is_active=True)

        # Now non-working due to holiday
        self.assertFalse(WorkingCalendarService.is_working_day(self.branch_a, sep_12))

        # Even if an explicit rule said is_working=True, Holiday still takes precedence
        WorkingCalendarRule.objects.create(working_calendar=self.cal_a, weekday=5, occurrence=2, is_working=True)
        self.assertFalse(WorkingCalendarService.is_working_day(self.branch_a, sep_12))

    # -------------------------------------------------------------------------
    # 7: No Recurring Rules Preserves Existing Behavior
    # -------------------------------------------------------------------------
    def test_no_recurring_rules_preserves_existing_behavior(self):
        """Branch without recurring rules behaves strictly according to base work_days."""
        # cal_b has work_days='0,1,2,3,4' and no recurring rules
        friday = date(2026, 9, 4)
        saturday = date(2026, 9, 5)
        sunday = date(2026, 9, 6)

        self.assertTrue(WorkingCalendarService.is_working_day(self.branch_b, friday))
        self.assertFalse(WorkingCalendarService.is_working_day(self.branch_b, saturday))
        self.assertFalse(WorkingCalendarService.is_working_day(self.branch_b, sunday))

    # -------------------------------------------------------------------------
    # 8 - 10: Model & Serializer Bounds Validation
    # -------------------------------------------------------------------------
    def test_invalid_weekday_rejected_by_model(self):
        rule = WorkingCalendarRule(working_calendar=self.cal_a, weekday=7, occurrence=1, is_working=False)
        with self.assertRaises(ValidationError):
            rule.full_clean()

    def test_invalid_occurrence_rejected_by_model(self):
        rule = WorkingCalendarRule(working_calendar=self.cal_a, weekday=5, occurrence=6, is_working=False)
        with self.assertRaises(ValidationError):
            rule.full_clean()

    def test_duplicate_rule_rejected_by_model(self):
        WorkingCalendarRule.objects.create(working_calendar=self.cal_a, weekday=5, occurrence=1, is_working=False)
        dup = WorkingCalendarRule(working_calendar=self.cal_a, weekday=5, occurrence=1, is_working=True)
        with self.assertRaises(Exception):
            dup.save()

    # -------------------------------------------------------------------------
    # 11 - 15: API IDOR, Authorization, and Cross-Tenant Security
    # -------------------------------------------------------------------------
    def test_branch_a_cannot_read_branch_b_rules_idor(self):
        """User authorized for Branch A cannot GET Branch B's calendar / recurring rules (returns 404)."""
        self.client.force_authenticate(user=self.user_mgr_a)
        response = self.client.get(f'/api/v1/organization/working-calendars/{self.cal_b.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_branch_a_cannot_modify_branch_b_rules_idor(self):
        """User authorized for Branch A cannot PATCH Branch B's recurring rules (returns 404)."""
        self.client.force_authenticate(user=self.user_mgr_a)
        payload = {
            'recurring_rules': [{'weekday': 5, 'occurrence': 1, 'is_working': False}]
        }
        response = self.client.patch(f'/api/v1/organization/working-calendars/{self.cal_b.id}/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.cal_b.recurring_rules.count(), 0)

    def test_branch_a_manager_can_update_branch_a_rules(self):
        """User authorized for Branch A can successfully PATCH Branch A rules."""
        self.client.force_authenticate(user=self.user_mgr_a)
        payload = {
            'work_days': '0,1,2,3,4,5',
            'recurring_rules': [
                {'weekday': 5, 'occurrence': 1, 'is_working': False},
                {'weekday': 5, 'occurrence': 3, 'is_working': False},
            ]
        }
        response = self.client.patch(f'/api/v1/organization/working-calendars/{self.cal_a.id}/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['recurring_rules']), 2)
        self.assertEqual(self.cal_a.recurring_rules.count(), 2)

    def test_api_rejects_duplicate_recurring_rules_in_payload(self):
        """PATCH with duplicate (weekday, occurrence) in the payload is rejected with 400 Bad Request."""
        self.client.force_authenticate(user=self.user_mgr_a)
        payload = {
            'recurring_rules': [
                {'weekday': 5, 'occurrence': 1, 'is_working': False},
                {'weekday': 5, 'occurrence': 1, 'is_working': True},
            ]
        }
        response = self.client.patch(f'/api/v1/organization/working-calendars/{self.cal_a.id}/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_organization_wide_user_can_manage_all_authorized_branches(self):
        """Org Admin can update calendars for both Branch A and Branch B."""
        self.client.force_authenticate(user=self.user_org_admin)
        res_a = self.client.patch(
            f'/api/v1/organization/working-calendars/{self.cal_a.id}/',
            {'recurring_rules': [{'weekday': 5, 'occurrence': 1, 'is_working': False}]},
            format='json'
        )
        self.assertEqual(res_a.status_code, status.HTTP_200_OK)

        res_b = self.client.patch(
            f'/api/v1/organization/working-calendars/{self.cal_b.id}/',
            {'recurring_rules': [{'weekday': 5, 'occurrence': 2, 'is_working': False}]},
            format='json'
        )
        self.assertEqual(res_b.status_code, status.HTTP_200_OK)

    def test_cross_tenant_isolation(self):
        """Org A user cannot read or update Org B's calendar."""
        self.client.force_authenticate(user=self.user_org_admin)
        res_get = self.client.get(f'/api/v1/organization/working-calendars/{self.cal_beta.id}/')
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)

        res_patch = self.client.patch(
            f'/api/v1/organization/working-calendars/{self.cal_beta.id}/',
            {'recurring_rules': [{'weekday': 5, 'occurrence': 1, 'is_working': False}]},
            format='json'
        )
        self.assertEqual(res_patch.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthorized_user_denied(self):
        """Unauthenticated returns 401, regular employee without organization.update returns 403."""
        response = self.client.get(f'/api/v1/organization/working-calendars/{self.cal_a.id}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=self.user_emp_a)
        response = self.client.get(f'/api/v1/organization/working-calendars/{self.cal_a.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # 18: No Mon-Fri Fallback When Calendar is Missing
    # -------------------------------------------------------------------------
    def test_no_mon_fri_fallback_when_calendar_missing(self):
        """WorkingCalendarService raises WorkingCalendarConfigurationError when branch has no WorkingCalendar."""
        branch_no_cal = Branch.objects.create(organization=self.org_a, name='No Cal Branch', radius=100)
        # Delete automatically provisioned calendar
        WorkingCalendar.objects.filter(branch=branch_no_cal).delete()
        branch_no_cal.refresh_from_db()

        with self.assertRaises(WorkingCalendarConfigurationError):
            WorkingCalendarService.is_working_day(branch_no_cal, date(2026, 9, 7))
