"""
Employee Calendar Endpoint Tests
=================================

Tests for GET /api/v1/leaves/calendar/

Coverage:
1.  Employee retrieves own calendar
2.  Employee cannot retrieve another employee's calendar
3.  Authorized manager/admin access follows existing RBAC scope
4.  Cross-organization access denied
5.  Branch isolation
6.  Working day correctly calculated
7.  Holiday correctly overrides working day
8.  Recurring calendar rule respected
9.  Approved leave appears
10. Pending leave does not appear
11. Rejected leave does not appear
12. Half-day leave represented correctly
13. Missing start_date rejected
14. Missing end_date rejected
15. Malformed date rejected
16. end_date before start_date rejected
17. >60-day range rejected
18. Employee without profile handled correctly
"""

from django.test import TestCase
from decimal import Decimal
from datetime import date, timedelta
from rest_framework.test import APIClient
from rest_framework import status as http_status

from apps.organization.models import Organization, Branch, WorkingCalendar, WorkingCalendarRule
from apps.attendance.models import Holiday
from apps.employees.models import Employee
from apps.leaves.models import LeaveType, LeaveRequest, LeaveCycle, LeaveBalance, BranchLeavePolicy
from django.contrib.auth import get_user_model

User = get_user_model()


class EmployeeCalendarTestBase(TestCase):
    """Shared setUp for calendar tests."""

    def setUp(self):
        self.client = APIClient()

        # Organization & branches
        self.org1 = Organization.objects.create(name="Org Alpha")
        self.branch1 = Branch.objects.create(organization=self.org1, name="Branch Alpha")
        # WorkingCalendar is auto-provisioned via signal with work_days='0,1,2,3,4' (Mon-Fri)

        self.org2 = Organization.objects.create(name="Org Beta")
        self.branch2 = Branch.objects.create(organization=self.org2, name="Branch Beta")

        # Users & employees
        self.user_emp1 = User.objects.create(email="emp1@cal.test", status="active")
        self.emp1 = Employee.objects.create(
            user=self.user_emp1, employee_code="CAL-E01",
            organization=self.org1, branch=self.branch1,
            joining_date=date(2025, 1, 1), employment_status='active'
        )

        self.user_emp2 = User.objects.create(email="emp2@cal.test", status="active")
        self.emp2 = Employee.objects.create(
            user=self.user_emp2, employee_code="CAL-E02",
            organization=self.org1, branch=self.branch1,
            joining_date=date(2025, 1, 1), employment_status='active'
        )

        # Employee in a different org
        self.user_emp3 = User.objects.create(email="emp3@cal.test", status="active")
        self.emp3 = Employee.objects.create(
            user=self.user_emp3, employee_code="CAL-E03",
            organization=self.org2, branch=self.branch2,
            joining_date=date(2025, 1, 1), employment_status='active'
        )

        # Superuser (without employee profile)
        self.superuser = User.objects.create(
            email="super@cal.test", is_superuser=True, is_staff=True, status="active"
        )

        # Leave type and policy
        self.leave_type = LeaveType.objects.create(
            organization=self.org1, name="Annual Leave", is_active=True
        )
        self.policy = BranchLeavePolicy.objects.create(
            branch=self.branch1, leave_type=self.leave_type,
            monthly_allocation=Decimal('2.0'),
            half_day_allowed=True,
            negative_balance_allowed=False,
            advance_notice_days=0,
        )

        # Leave cycle
        self.cycle = LeaveCycle.objects.create(
            branch=self.branch1, name="FY 2026-27",
            start_date=date(2026, 4, 1), end_date=date(2027, 3, 31),
            is_active=True,
        )

        self.balance = LeaveBalance.objects.create(
            employee=self.emp1, leave_type=self.leave_type,
            leave_cycle=self.cycle, branch=self.branch1,
            allocated=Decimal('20.0'),
        )

        # Fixed test dates: use a known Mon-Fri working week
        # 2026-10-05 is Monday, 2026-10-09 is Friday
        self.mon = date(2026, 10, 5)
        self.tue = date(2026, 10, 6)
        self.wed = date(2026, 10, 7)
        self.thu = date(2026, 10, 8)
        self.fri = date(2026, 10, 9)
        self.sat = date(2026, 10, 10)
        self.sun = date(2026, 10, 11)

    def _url(self, **params):
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"/api/v1/leaves/calendar/?{qs}"


class EmployeeCalendarSelfAccessTests(EmployeeCalendarTestBase):
    """1. Employee retrieves own calendar."""

    def test_employee_retrieves_own_calendar(self):
        self.client.force_authenticate(user=self.user_emp1)
        resp = self.client.get(self._url(
            start_date=self.mon.isoformat(),
            end_date=self.fri.isoformat()
        ))
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["employee_id"], self.emp1.id)
        self.assertEqual(data["start_date"], self.mon.isoformat())
        self.assertEqual(data["end_date"], self.fri.isoformat())
        self.assertEqual(len(data["days"]), 5)

    def test_all_five_weekdays_are_working(self):
        self.client.force_authenticate(user=self.user_emp1)
        resp = self.client.get(self._url(
            start_date=self.mon.isoformat(),
            end_date=self.fri.isoformat()
        ))
        days = resp.json()["days"]
        for day in days:
            self.assertTrue(day["is_working_day"], f"{day['date']} should be working")

    def test_weekend_is_non_working(self):
        """6. Working day correctly calculated — weekends are non-working."""
        self.client.force_authenticate(user=self.user_emp1)
        resp = self.client.get(self._url(
            start_date=self.sat.isoformat(),
            end_date=self.sun.isoformat()
        ))
        days = resp.json()["days"]
        for day in days:
            self.assertFalse(day["is_working_day"], f"{day['date']} should be non-working")


class EmployeeCalendarCrossAccessTests(EmployeeCalendarTestBase):
    """2. Employee cannot retrieve another employee's calendar (no leave.view perm)."""

    def test_employee_cannot_access_other_employee_calendar(self):
        self.client.force_authenticate(user=self.user_emp1)
        resp = self.client.get(self._url(
            start_date=self.mon.isoformat(),
            end_date=self.fri.isoformat(),
            employee_id=self.emp2.id
        ))
        self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)


class EmployeeCalendarAuthorizedAccessTests(EmployeeCalendarTestBase):
    """3. Authorized manager/admin access follows existing RBAC scope."""

    def setUp(self):
        super().setUp()
        # Create a manager user with leave.view on branch1
        self.user_mgr = User.objects.create(email="mgr@cal.test", status="active")
        self.emp_mgr = Employee.objects.create(
            user=self.user_mgr, employee_code="CAL-MGR",
            organization=self.org1, branch=self.branch1,
            joining_date=date(2025, 1, 1), employment_status='active'
        )

    def test_authorized_manager_can_view_employee_calendar(self):
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True), \
             patch('apps.authorization.services.AuthorizationService.get_authorized_branches') as mock_branches:
            mock_branches.return_value = Branch.objects.filter(id=self.branch1.id)
            self.client.force_authenticate(user=self.user_mgr)
            resp = self.client.get(self._url(
                start_date=self.mon.isoformat(),
                end_date=self.fri.isoformat(),
                employee_id=self.emp1.id
            ))
            self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
            self.assertEqual(resp.json()["employee_id"], self.emp1.id)

    def test_manager_without_branch_scope_denied(self):
        """Manager with leave.view but NOT authorized for the target branch."""
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True), \
             patch('apps.authorization.services.AuthorizationService.get_authorized_branches') as mock_branches:
            # Return empty branch set — not authorized for branch1
            mock_branches.return_value = Branch.objects.none()
            self.client.force_authenticate(user=self.user_mgr)
            resp = self.client.get(self._url(
                start_date=self.mon.isoformat(),
                end_date=self.fri.isoformat(),
                employee_id=self.emp1.id
            ))
            self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)


class EmployeeCalendarCrossOrgTests(EmployeeCalendarTestBase):
    """4. Cross-organization access denied."""

    def test_cross_org_access_denied(self):
        """User in org1 cannot view employee in org2."""
        from unittest.mock import patch
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True), \
             patch('apps.authorization.services.AuthorizationService.get_authorized_branches') as mock_branches:
            mock_branches.return_value = Branch.objects.filter(id=self.branch1.id)
            self.client.force_authenticate(user=self.user_emp1)
            resp = self.client.get(self._url(
                start_date=self.mon.isoformat(),
                end_date=self.fri.isoformat(),
                employee_id=self.emp3.id  # emp3 is in org2
            ))
            self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)


class EmployeeCalendarBranchIsolationTests(EmployeeCalendarTestBase):
    """5. Branch isolation — holidays are branch-specific."""

    def test_holiday_from_other_branch_not_visible(self):
        # Holiday in branch2, NOT in branch1
        Holiday.objects.create(branch=self.branch2, name="Branch2 Holiday", date=self.wed)
        self.client.force_authenticate(user=self.user_emp1)
        resp = self.client.get(self._url(
            start_date=self.mon.isoformat(),
            end_date=self.fri.isoformat()
        ))
        days = resp.json()["days"]
        wed_day = next(d for d in days if d["date"] == self.wed.isoformat())
        self.assertTrue(wed_day["is_working_day"])
        self.assertIsNone(wed_day["holiday"])


class EmployeeCalendarHolidayTests(EmployeeCalendarTestBase):
    """7. Holiday correctly overrides working day."""

    def test_holiday_overrides_working_day(self):
        Holiday.objects.create(branch=self.branch1, name="National Day", date=self.wed)
        self.client.force_authenticate(user=self.user_emp1)
        resp = self.client.get(self._url(
            start_date=self.mon.isoformat(),
            end_date=self.fri.isoformat()
        ))
        days = resp.json()["days"]
        wed_day = next(d for d in days if d["date"] == self.wed.isoformat())
        self.assertFalse(wed_day["is_working_day"])
        self.assertIsNotNone(wed_day["holiday"])
        self.assertEqual(wed_day["holiday"]["name"], "National Day")
        self.assertIsNone(wed_day["leave"])  # Leave not shown on holidays


class EmployeeCalendarRecurringRuleTests(EmployeeCalendarTestBase):
    """8. Recurring calendar rule respected."""

    def test_recurring_rule_makes_saturday_working(self):
        """A WorkingCalendarRule making the 2nd Saturday of the month a working day."""
        wc = WorkingCalendar.objects.get(branch=self.branch1)
        # 2026-10-10 is the 2nd Saturday (occurrence=2, weekday=5)
        WorkingCalendarRule.objects.create(
            working_calendar=wc, weekday=5, occurrence=2, is_working=True
        )
        self.client.force_authenticate(user=self.user_emp1)
        resp = self.client.get(self._url(
            start_date=self.sat.isoformat(),
            end_date=self.sat.isoformat()
        ))
        day = resp.json()["days"][0]
        self.assertTrue(day["is_working_day"])

    def test_recurring_rule_makes_weekday_non_working(self):
        """A WorkingCalendarRule overriding a normal weekday to non-working."""
        wc = WorkingCalendar.objects.get(branch=self.branch1)
        # 2026-10-05 is Mon, occurrence=1 (1st Monday of month)
        WorkingCalendarRule.objects.create(
            working_calendar=wc, weekday=0, occurrence=1, is_working=False
        )
        self.client.force_authenticate(user=self.user_emp1)
        resp = self.client.get(self._url(
            start_date=self.mon.isoformat(),
            end_date=self.mon.isoformat()
        ))
        day = resp.json()["days"][0]
        self.assertFalse(day["is_working_day"])


class EmployeeCalendarLeaveTests(EmployeeCalendarTestBase):
    """9-12. Leave visibility tests."""

    def test_approved_leave_appears(self):
        """9. Approved leave appears on calendar."""
        LeaveRequest.objects.create(
            employee=self.emp1, leave_type=self.leave_type,
            start_date=self.tue, end_date=self.tue,
            reason="Vacation", status='approved',
        )
        self.client.force_authenticate(user=self.user_emp1)
        resp = self.client.get(self._url(
            start_date=self.mon.isoformat(),
            end_date=self.fri.isoformat()
        ))
        days = resp.json()["days"]
        tue_day = next(d for d in days if d["date"] == self.tue.isoformat())
        self.assertIsNotNone(tue_day["leave"])
        self.assertEqual(tue_day["leave"]["leave_type_name"], "Annual Leave")
        self.assertFalse(tue_day["leave"]["is_half_day"])

    def test_pending_leave_does_not_appear(self):
        """10. Pending leave does not appear."""
        LeaveRequest.objects.create(
            employee=self.emp1, leave_type=self.leave_type,
            start_date=self.tue, end_date=self.tue,
            reason="Pending", status='pending',
        )
        self.client.force_authenticate(user=self.user_emp1)
        resp = self.client.get(self._url(
            start_date=self.mon.isoformat(),
            end_date=self.fri.isoformat()
        ))
        days = resp.json()["days"]
        tue_day = next(d for d in days if d["date"] == self.tue.isoformat())
        self.assertIsNone(tue_day["leave"])

    def test_rejected_leave_does_not_appear(self):
        """11. Rejected leave does not appear."""
        LeaveRequest.objects.create(
            employee=self.emp1, leave_type=self.leave_type,
            start_date=self.wed, end_date=self.wed,
            reason="Rejected", status='rejected',
        )
        self.client.force_authenticate(user=self.user_emp1)
        resp = self.client.get(self._url(
            start_date=self.mon.isoformat(),
            end_date=self.fri.isoformat()
        ))
        days = resp.json()["days"]
        wed_day = next(d for d in days if d["date"] == self.wed.isoformat())
        self.assertIsNone(wed_day["leave"])

    def test_half_day_leave_represented_correctly(self):
        """12. Half-day leave represented correctly."""
        LeaveRequest.objects.create(
            employee=self.emp1, leave_type=self.leave_type,
            start_date=self.thu, end_date=self.thu,
            reason="Half day", status='approved',
            is_half_day=True, half_day_period='first_half',
        )
        self.client.force_authenticate(user=self.user_emp1)
        resp = self.client.get(self._url(
            start_date=self.thu.isoformat(),
            end_date=self.thu.isoformat()
        ))
        day = resp.json()["days"][0]
        self.assertTrue(day["is_working_day"])
        self.assertIsNotNone(day["leave"])
        self.assertTrue(day["leave"]["is_half_day"])

    def test_leave_not_shown_on_holiday(self):
        """Leave overlapping a holiday should not show leave on the holiday date."""
        Holiday.objects.create(branch=self.branch1, name="Hol", date=self.wed)
        LeaveRequest.objects.create(
            employee=self.emp1, leave_type=self.leave_type,
            start_date=self.tue, end_date=self.thu,
            reason="Spanning holiday", status='approved',
        )
        self.client.force_authenticate(user=self.user_emp1)
        resp = self.client.get(self._url(
            start_date=self.tue.isoformat(),
            end_date=self.thu.isoformat()
        ))
        days = resp.json()["days"]
        wed_day = next(d for d in days if d["date"] == self.wed.isoformat())
        self.assertFalse(wed_day["is_working_day"])
        self.assertIsNone(wed_day["leave"])
        # But Tue and Thu should show the leave
        tue_day = next(d for d in days if d["date"] == self.tue.isoformat())
        thu_day = next(d for d in days if d["date"] == self.thu.isoformat())
        self.assertIsNotNone(tue_day["leave"])
        self.assertIsNotNone(thu_day["leave"])


class EmployeeCalendarDateValidationTests(EmployeeCalendarTestBase):
    """13-17. Date validation tests."""

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.user_emp1)

    def test_missing_start_date(self):
        resp = self.client.get(self._url(end_date=self.fri.isoformat()))
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_date", resp.json()["detail"])

    def test_missing_end_date(self):
        resp = self.client.get(self._url(start_date=self.mon.isoformat()))
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_date", resp.json()["detail"])

    def test_malformed_start_date(self):
        resp = self.client.get(self._url(start_date="not-a-date", end_date=self.fri.isoformat()))
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_malformed_end_date(self):
        resp = self.client.get(self._url(start_date=self.mon.isoformat(), end_date="2026/10/09"))
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_end_before_start(self):
        resp = self.client.get(self._url(
            start_date=self.fri.isoformat(),
            end_date=self.mon.isoformat()
        ))
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn("before", resp.json()["detail"])

    def test_range_exceeds_60_days(self):
        far_end = (self.mon + timedelta(days=61)).isoformat()
        resp = self.client.get(self._url(start_date=self.mon.isoformat(), end_date=far_end))
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn("60", resp.json()["detail"])

    def test_range_exactly_60_days_allowed(self):
        end_60 = (self.mon + timedelta(days=60)).isoformat()
        resp = self.client.get(self._url(start_date=self.mon.isoformat(), end_date=end_60))
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(resp.json()["days"]), 61)  # inclusive


class EmployeeCalendarNoProfileTests(TestCase):
    """18. Employee without profile handled correctly."""

    def test_user_without_employee_profile(self):
        user = User.objects.create(email="noprofile@cal.test", status="active")
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/leaves/calendar/?start_date=2026-10-05&end_date=2026-10-09")
        self.assertEqual(resp.status_code, http_status.HTTP_404_NOT_FOUND)
        self.assertIn("Employee profile", resp.json()["detail"])

    def test_unauthenticated_request_rejected(self):
        client = APIClient()
        resp = client.get("/api/v1/leaves/calendar/?start_date=2026-10-05&end_date=2026-10-09")
        self.assertEqual(resp.status_code, http_status.HTTP_401_UNAUTHORIZED)


class EmployeeCalendarSuperuserTests(EmployeeCalendarTestBase):
    """Superuser access tests."""

    def test_superuser_can_view_any_employee_in_same_org(self):
        # First ensure the superuser HAS an employee profile in org1 to establish a tenant boundary
        Employee.objects.create(
            user=self.superuser, employee_code="SUPER",
            organization=self.org1, branch=self.branch1,
            joining_date=date(2025, 1, 1), employment_status='active'
        )
        self.client.force_authenticate(user=self.superuser)
        resp = self.client.get(self._url(
            start_date=self.mon.isoformat(),
            end_date=self.fri.isoformat(),
            employee_id=self.emp1.id
        ))
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(resp.json()["employee_id"], self.emp1.id)

    def test_superuser_cross_org_access_rejected(self):
        # Even superusers MUST NOT bypass tenant isolation
        Employee.objects.create(
            user=self.superuser, employee_code="SUPER",
            organization=self.org1, branch=self.branch1,
            joining_date=date(2025, 1, 1), employment_status='active'
        )
        self.client.force_authenticate(user=self.superuser)
        resp = self.client.get(self._url(
            start_date=self.mon.isoformat(),
            end_date=self.fri.isoformat(),
            employee_id=self.emp3.id  # emp3 is in org2
        ))
        self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertIn("Cross-organization access is denied", resp.json()["detail"])

    def test_superuser_without_profile_cannot_use_default(self):
        """Superuser with no employee profile, no employee_id => 404."""
        self.client.force_authenticate(user=self.superuser)
        resp = self.client.get(self._url(
            start_date=self.mon.isoformat(),
            end_date=self.fri.isoformat()
        ))
        self.assertEqual(resp.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_superuser_without_profile_cannot_access_others(self):
        """Pure superusers with no employee profile cannot access other employees."""
        self.client.force_authenticate(user=self.superuser)
        resp = self.client.get(self._url(
            start_date=self.mon.isoformat(),
            end_date=self.fri.isoformat(),
            employee_id=self.emp1.id
        ))
        self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertIn("establish an organization context", resp.json()["detail"])

    def test_nonexistent_employee_id_returns_404(self):
        self.client.force_authenticate(user=self.superuser)
        resp = self.client.get(self._url(
            start_date=self.mon.isoformat(),
            end_date=self.fri.isoformat(),
            employee_id=99999
        ))
        self.assertEqual(resp.status_code, http_status.HTTP_404_NOT_FOUND)

class EmployeeCalendarPerformanceTests(EmployeeCalendarTestBase):
    """Performance and N+1 Query Regression Tests."""

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.user_emp1)
        # Create some background data that would trigger N+1 if not batched
        Holiday.objects.create(branch=self.branch1, name="Hol1", date=self.wed)
        Holiday.objects.create(branch=self.branch1, name="Hol2", date=self.thu)
        LeaveRequest.objects.create(
            employee=self.emp1, leave_type=self.leave_type,
            start_date=self.tue, end_date=self.wed,
            reason="Test", status='approved',
        )
        wc = WorkingCalendar.objects.get(branch=self.branch1)
        WorkingCalendarRule.objects.create(
            working_calendar=wc, weekday=5, occurrence=2, is_working=True
        )

    def test_short_range_query_count(self):
        """Short date range should trigger a fixed number of queries."""
        # Warmup cache if any
        self.client.get(self._url(start_date=self.mon.isoformat(), end_date=self.fri.isoformat()))
        
        # 1. WorkingCalendar
        # 2. WorkingCalendarRule (prefetch)
        # 3. Holidays
        # 4. Approved leaves
        with self.assertNumQueries(4):
            resp = self.client.get(self._url(
                start_date=self.mon.isoformat(),
                end_date=self.fri.isoformat()
            ))
            self.assertEqual(resp.status_code, http_status.HTTP_200_OK)

    def test_60_day_range_query_count(self):
        """A 60-day range MUST NOT increase the query count (O(1) queries)."""
        end_60 = (self.mon + timedelta(days=60)).isoformat()
        
        # Warmup cache if any
        self.client.get(self._url(start_date=self.mon.isoformat(), end_date=end_60))
        
        with self.assertNumQueries(4):
            resp = self.client.get(self._url(
                start_date=self.mon.isoformat(),
                end_date=end_60
            ))
            self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
