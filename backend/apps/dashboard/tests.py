"""
Unit and integration tests for Dashboard V2 backend foundation (apps.dashboard).
"""
from datetime import timedelta, date
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.organization.models import Organization, Department, Branch, OfficeNetwork
from apps.employees.models import Employee, EmploymentStatus, WFHRequest
from apps.attendance.models import Attendance, AttendanceBreak, Holiday
from apps.leaves.models import LeaveType, LeaveBalance, LeaveRequest
from apps.authorization.models import Permission, Role, RolePermission, UserRole

User = get_user_model()


class DashboardOverviewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.today = timezone.localdate()

        # Organization 1 (Primary)
        self.org1 = Organization.objects.create(name="Primary Corp")
        from apps.organization.models import Branch
        self.branch1 = Branch.objects.create(organization=self.org1, name="Headquarters", radius=100.0)
        OfficeNetwork.objects.create(branch=self.branch1, name="Primary Net", network="127.0.0.0/8", is_active=True)
        self.dept1 = Department.objects.create(branch=self.branch1, name="Engineering")

        # Organization 2 (Isolated)
        self.org2 = Organization.objects.create(name="Secondary Corp")
        self.branch2 = Branch.objects.create(organization=self.org2, name="Secondary HQ", radius=100.0)
        OfficeNetwork.objects.create(branch=self.branch2, name="Secondary Net", network="10.0.0.0/8", is_active=True)
        self.dept2 = Department.objects.create(branch=self.branch2, name="Marketing")

        # Standard Permissions
        self.perm_emp_view, _ = Permission.objects.get_or_create(
            codename='employee.view',
            defaults={'name': 'View Employee', 'resource': 'employee', 'action': 'view'}
        )
        self.perm_att_view, _ = Permission.objects.get_or_create(
            codename='attendance.view_all',
            defaults={'name': 'View Attendance All', 'resource': 'attendance', 'action': 'view_all'}
        )
        self.perm_leave_view, _ = Permission.objects.get_or_create(
            codename='leave.view',
            defaults={'name': 'View Leave', 'resource': 'leave', 'action': 'view'}
        )
        self.perm_wfh_view, _ = Permission.objects.get_or_create(
            codename='wfh.view',
            defaults={'name': 'View WFH', 'resource': 'wfh', 'action': 'view'}
        )

        # 1. Regular Employee (Org 1, No direct reports, No admin permissions)
        self.emp_user = User.objects.create_user(
            email="employee@primary.com", password="Password123!", status="active",
            first_name="Jane", last_name="Doe"
        )
        self.emp_profile = Employee.objects.create(
            user=self.emp_user, organization=self.org1, employee_code="EMP001",
            department=self.dept1, branch=self.branch1, employment_status=EmploymentStatus.ACTIVE
        )

        # 2. Manager (Org 1, will have direct reports)
        self.mgr_user = User.objects.create_user(
            email="manager@primary.com", password="Password123!", status="active",
            first_name="John", last_name="Manager"
        )
        self.mgr_profile = Employee.objects.create(
            user=self.mgr_user, organization=self.org1, employee_code="MGR001",
            department=self.dept1, branch=self.branch1, employment_status=EmploymentStatus.ACTIVE
        )

        # 3. Direct Report for Manager (Org 1)
        self.report_user = User.objects.create_user(
            email="report@primary.com", password="Password123!", status="active",
            first_name="Bob", last_name="Reporter"
        )
        self.report_profile = Employee.objects.create(
            user=self.report_user, organization=self.org1, employee_code="REP001",
            department=self.dept1, branch=self.branch1, reporting_manager=self.mgr_profile,
            employment_status=EmploymentStatus.ACTIVE
        )

        # 4. HR Admin (Org 1, Has permissions)
        self.hr_user = User.objects.create_user(
            email="hr@primary.com", password="Password123!", status="active",
            first_name="Alice", last_name="HR"
        )
        self.hr_profile = Employee.objects.create(
            user=self.hr_user, organization=self.org1, employee_code="HR001",
            department=self.dept1, branch=self.branch1, employment_status=EmploymentStatus.ACTIVE
        )
        self.hr_role = Role.objects.create(organization=self.org1, name="HR Manager")
        RolePermission.objects.create(role=self.hr_role, permission=self.perm_emp_view)
        RolePermission.objects.create(role=self.hr_role, permission=self.perm_att_view)
        RolePermission.objects.create(role=self.hr_role, permission=self.perm_leave_view)
        RolePermission.objects.create(role=self.hr_role, permission=self.perm_wfh_view)
        UserRole.objects.create(user=self.hr_user, role=self.hr_role)

        # 5. Org 2 Employee (for isolation verification)
        self.org2_user = User.objects.create_user(
            email="user@secondary.com", password="Password123!", status="active"
        )
        self.org2_profile = Employee.objects.create(
            user=self.org2_user, organization=self.org2, branch=self.branch2, employee_code="SEC001",
            department=self.dept2, employment_status=EmploymentStatus.ACTIVE
        )

        # 6. Standalone Superuser (No employee profile, No org)
        self.superadmin = User.objects.create_superuser(
            email="superadmin@system.com", password="SuperPassword123!"
        )

        self.overview_url = "/api/v1/dashboard/overview/"

    def test_unauthenticated_request_rejected(self):
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_regular_employee_view(self):
        """Regular employee sees personal section; team and organization are None."""
        # Setup personal data: Attendance, Leave balance, Holiday
        Attendance.objects.create(
            employee=self.emp_profile,
            date=self.today,
            status='present',
            check_in=timezone.now()
        )
        leave_type = LeaveType.objects.create(
            organization=self.org1, name="Casual Leave"
        )
        from apps.leaves.models import LeaveCycle
        from datetime import date
        cycle = LeaveCycle.objects.create(branch=self.branch1, name='C1', start_date=date(2026,1,1), end_date=date(2026,12,31), is_active=True)
        balance = LeaveBalance.objects.create(employee=self.emp_profile, leave_type=leave_type, branch=self.branch1, leave_cycle=cycle, allocated=10, used=0)
        balance.used = 2
        balance.save()
        Holiday.objects.create(
            branch=self.branch1, name="Independence Day", date=self.today
        )

        self.client.force_authenticate(user=self.emp_user)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertIn('personal', data)
        self.assertIn('team', data)
        self.assertIn('organization', data)

        # Personal section populated
        personal = data['personal']
        self.assertIsNotNone(personal)
        self.assertEqual(personal['attendance_today']['status'], 'present')
        self.assertEqual(len(personal['leave_balances']), 1)
        self.assertEqual(personal['leave_balances'][0]['remaining'], 8)
        self.assertEqual(len(personal['upcoming_holidays']), 1)
        self.assertEqual(personal['upcoming_holidays'][0]['name'], 'Independence Day')

        # Team and Org sections are None for regular employee
        self.assertIsNone(data['team'])
        self.assertIsNone(data['organization'])

    def test_manager_with_direct_reports_sees_team_section(self):
        """Manager sees personal and team sections with direct report aggregates."""
        # Setup direct report attendance and pending leave
        Attendance.objects.create(
            employee=self.report_profile,
            date=self.today,
            status='present',
            check_in=timezone.now()
        )
        leave_type = LeaveType.objects.create(
            organization=self.org1, name="Sick Leave"
        )
        LeaveRequest.objects.create(
            employee=self.report_profile,
            leave_type=leave_type,
            start_date=self.today,
            end_date=self.today,
            reason="Flu",
            status="pending"
        )
        WFHRequest.objects.create(
            employee=self.report_profile,
            start_at=timezone.now(),
            end_at=timezone.now() + timezone.timedelta(days=1),
            reason="Home repair",
            status="pending"
        )

        self.client.force_authenticate(user=self.mgr_user)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertIsNotNone(data['personal'])
        self.assertIsNotNone(data['team'])
        self.assertIsNone(data['organization'])  # Manager does not have org-wide permissions

        team = data['team']
        self.assertEqual(team['direct_reports_count'], 1)
        self.assertEqual(team['attendance_today']['present'], 1)
        self.assertEqual(team['attendance_today']['absent'], 0)
        self.assertEqual(team['pending_approvals']['leaves_count'], 1)
        self.assertEqual(team['pending_approvals']['wfh_count'], 1)
        self.assertEqual(len(team['pending_approvals']['leaves']), 1)
        self.assertEqual(team['pending_approvals']['leaves'][0]['employee_name'], "Bob Reporter")

    def test_organization_permission_gating_and_isolation(self):
        """HR Admin with permissions sees organization metrics strictly scoped to Org 1."""
        # Create some extra data in Org 2 that must NOT be counted
        Attendance.objects.create(
            employee=self.org2_profile,
            date=self.today,
            status='present',
            check_in=timezone.now()
        )

        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertIsNotNone(data['organization'])
        org_data = data['organization']

        # Org 1 has 4 active employees: emp_profile, mgr_profile, report_profile, hr_profile
        # Org 2's user must NOT leak into total_active
        self.assertEqual(org_data['workforce']['total_active'], 4)

        # Department breakdown must only show Org 1 departments
        dept_names = [d['name'] for d in org_data['workforce']['by_department']]
        self.assertIn("Engineering", dept_names)
        self.assertNotIn("Marketing", dept_names)

        # Org attendance expected total should be 4
        self.assertEqual(org_data['attendance_today']['expected_total'], 4)

    def test_granular_organization_permissions(self):
        """User with only employee.view sees workforce but not attendance_today or pending_approvals."""
        partial_user = User.objects.create_user(
            email="partial@primary.com", password="Password123!", status="active"
        )
        Employee.objects.create(
            user=partial_user, organization=self.org1, employee_code="PAR001",
            employment_status=EmploymentStatus.ACTIVE
        )
        role = Role.objects.create(organization=self.org1, name="Recruiter")
        RolePermission.objects.create(role=role, permission=self.perm_emp_view)
        UserRole.objects.create(user=partial_user, role=role)

        self.client.force_authenticate(user=partial_user)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        org_data = response.data['organization']
        self.assertIsNotNone(org_data)
        self.assertIn('workforce', org_data)
        self.assertNotIn('attendance_today', org_data)
        self.assertNotIn('pending_approvals', org_data)

    def test_superuser_without_employee_profile_safe_behavior(self):
        """Superuser without an employee profile safely gets None for all sections (no arbitrary fallback)."""
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertIsNone(data['personal'])
        self.assertIsNone(data['team'])
        self.assertIsNone(data['organization'])

    def test_multiscope_user_manager_and_hr(self):
        """User who is both a Team Lead and an HR Admin receives all 3 sections."""
        # Grant manager HR permissions
        UserRole.objects.create(user=self.mgr_user, role=self.hr_role)

        self.client.force_authenticate(user=self.mgr_user)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertIsNotNone(data['personal'])
        self.assertIsNotNone(data['team'])
        self.assertIsNotNone(data['organization'])

    def test_empty_no_data_organization_state(self):
        """An organization with 1 employee and 0 attendance records evaluates without divide-by-zero errors."""
        empty_org = Organization.objects.create(name="Empty Corp")
        empty_branch = Branch.objects.create(organization=empty_org, name="Empty Branch", radius=100.0)
        empty_user = User.objects.create_user(
            email="empty@corp.com", password="Password123!", status="active"
        )
        Employee.objects.create(
            user=empty_user, organization=empty_org, branch=empty_branch, employee_code="EMPEMPTY",
            employment_status=EmploymentStatus.ONBOARDING
        )
        empty_role = Role.objects.create(organization=empty_org, name="Admin")
        RolePermission.objects.create(role=empty_role, permission=self.perm_emp_view)
        RolePermission.objects.create(role=empty_role, permission=self.perm_att_view)
        UserRole.objects.create(user=empty_user, role=empty_role)

        self.client.force_authenticate(user=empty_user)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        org_data = response.data['organization']
        self.assertEqual(org_data['workforce']['total_active'], 0)
        self.assertEqual(org_data['attendance_today']['expected_total'], 0)
        self.assertEqual(org_data['attendance_today']['expected_working'], 0)
        self.assertEqual(org_data['attendance_today']['attendance_percentage'], 0.0)

    def test_attendance_rate_all_expected_employees_present(self):
        """All 4 active employees punch in as present -> 100% attendance rate."""
        for emp in [self.emp_profile, self.mgr_profile, self.report_profile, self.hr_profile]:
            Attendance.objects.create(employee=emp, date=self.today, status='present', check_in=timezone.now())

        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        att = response.data['organization']['attendance_today']
        self.assertEqual(att['expected_total'], 4)
        self.assertEqual(att['expected_working'], 4)
        self.assertEqual(att['present'], 4)
        self.assertEqual(att['half_day'], 0)
        self.assertEqual(att['absent'], 0)
        self.assertEqual(att['on_leave'], 0)
        self.assertEqual(att['attendance_percentage'], 100.0)

    def test_attendance_rate_employees_on_approved_leave(self):
        """1 employee on approved leave and 3 present -> net expected_working is 3, 100% rate."""
        leave_type = LeaveType.objects.create(organization=self.org1, name="Annual Leave")
        LeaveRequest.objects.create(
            employee=self.emp_profile,
            leave_type=leave_type,
            start_date=self.today,
            end_date=self.today,
            status='approved'
        )
        # The other 3 employees check in
        for emp in [self.mgr_profile, self.report_profile, self.hr_profile]:
            Attendance.objects.create(employee=emp, date=self.today, status='present', check_in=timezone.now())

        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        att = response.data['organization']['attendance_today']
        self.assertEqual(att['expected_total'], 4)
        self.assertEqual(att['on_leave'], 1)
        self.assertEqual(att['expected_working'], 3)
        self.assertEqual(att['present'], 3)
        self.assertEqual(att['absent'], 0)
        # Net scheduled attendance: 3 / 3 = 100.0%
        self.assertEqual(att['attendance_percentage'], 100.0)

    def test_attendance_rate_half_day_treatment(self):
        """3 present and 1 half-day -> effective_present = 3.5 / 4 = 87.5%."""
        Attendance.objects.create(employee=self.emp_profile, date=self.today, status='half_day', check_in=timezone.now())
        for emp in [self.mgr_profile, self.report_profile, self.hr_profile]:
            Attendance.objects.create(employee=emp, date=self.today, status='present', check_in=timezone.now())

        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        att = response.data['organization']['attendance_today']
        self.assertEqual(att['expected_total'], 4)
        self.assertEqual(att['expected_working'], 4)
        self.assertEqual(att['present'], 3)
        self.assertEqual(att['half_day'], 1)
        self.assertEqual(att['absent'], 0)
        self.assertEqual(att['attendance_percentage'], 87.5)

    def test_attendance_rate_approved_wfh_plus_present(self):
        """Approved WFH employee remains in expected workforce; when punched in, counts as present."""
        now = timezone.now()
        WFHRequest.objects.create(
            employee=self.emp_profile,
            status='approved',
            start_at=now - timezone.timedelta(hours=1),
            end_at=now + timezone.timedelta(hours=8)
        )
        # All 4 employees check in
        for emp in [self.emp_profile, self.mgr_profile, self.report_profile, self.hr_profile]:
            Attendance.objects.create(employee=emp, date=self.today, status='present', check_in=timezone.now())

        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        att = response.data['organization']['attendance_today']
        self.assertEqual(att['expected_total'], 4)
        self.assertEqual(att['expected_working'], 4)
        self.assertEqual(att['on_wfh'], 1)
        self.assertEqual(att['present'], 4)
        self.assertEqual(att['absent'], 0)
        self.assertEqual(att['attendance_percentage'], 100.0)

    def test_attendance_rate_approved_leave_plus_attendance_edge_case(self):
        """Employee has approved leave but punches in anyway: counted once as present, not on leave."""
        leave_type = LeaveType.objects.create(organization=self.org1, name="Sick Leave")
        LeaveRequest.objects.create(
            employee=self.emp_profile,
            leave_type=leave_type,
            start_date=self.today,
            end_date=self.today,
            status='approved'
        )
        # Employee punches in anyway!
        for emp in [self.emp_profile, self.mgr_profile, self.report_profile, self.hr_profile]:
            Attendance.objects.create(employee=emp, date=self.today, status='present', check_in=timezone.now())

        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        att = response.data['organization']['attendance_today']
        self.assertEqual(att['expected_total'], 4)
        # on_leave is 0 because the employee attended (actual presence takes precedence)
        self.assertEqual(att['on_leave'], 0)
        self.assertEqual(att['expected_working'], 4)
        self.assertEqual(att['present'], 4)
        self.assertEqual(att['absent'], 0)
        self.assertEqual(att['attendance_percentage'], 100.0)

    def test_attendance_rate_zero_expected_workforce(self):
        """All active employees are on approved leave -> expected_working is 0, percentage is 0.0%."""
        leave_type = LeaveType.objects.create(organization=self.org1, name="Company Vacation")
        for emp in [self.emp_profile, self.mgr_profile, self.report_profile, self.hr_profile]:
            LeaveRequest.objects.create(
                employee=emp,
                leave_type=leave_type,
                start_date=self.today,
                end_date=self.today,
                status='approved'
            )

        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        att = response.data['organization']['attendance_today']
        self.assertEqual(att['expected_total'], 4)
        self.assertEqual(att['on_leave'], 4)
        self.assertEqual(att['expected_working'], 0)
        self.assertEqual(att['present'], 0)
        self.assertEqual(att['absent'], 0)
        self.assertEqual(att['attendance_percentage'], 0.0)

    def test_dashboard_unauthorized_branch_access(self):
        """Requesting overview with branch_id for a cross-organization branch must return HTTP 403 Forbidden."""
        self.client.force_authenticate(user=self.hr_user)
        # Scope HR role to branch1
        UserRole.objects.filter(user=self.hr_user).update(scope='branch', branch=self.branch1)

        # Try accessing branch2 (secondary organization branch)
        response = self.client.get(f"{self.overview_url}?branch_id={self.branch2.id}")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_same_org_unauthorized_branch_access(self):
        """Requesting overview with branch_id for another branch in same org without permissions returns HTTP 403 Forbidden."""
        branch3 = Branch.objects.create(organization=self.org1, name="Branch 3", radius=100.0)
        self.client.force_authenticate(user=self.hr_user)
        UserRole.objects.filter(user=self.hr_user).update(scope='branch', branch=self.branch1)

        response = self.client.get(f"{self.overview_url}?branch_id={branch3.id}")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_authorized_branch_access(self):
        """Requesting overview with branch_id for an authorized branch returns HTTP 200 with isolated data."""
        self.client.force_authenticate(user=self.hr_user)
        UserRole.objects.filter(user=self.hr_user).update(scope='branch', branch=self.branch1)

        response = self.client.get(f"{self.overview_url}?branch_id={self.branch1.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        org_data = response.data['organization']
        self.assertIsNotNone(org_data)
        self.assertEqual(org_data['workforce']['total_active'], 4)

    def test_dashboard_authorized_branch_zero_data(self):
        """Authorized branch with zero active employees returns HTTP 200 with 0 metrics, distinct from 403."""
        empty_branch = Branch.objects.create(organization=self.org1, name="Zero Data Branch", radius=100.0)
        empty_role = Role.objects.create(organization=self.org1, name="Empty Branch Admin")
        RolePermission.objects.create(role=empty_role, permission=self.perm_emp_view)
        RolePermission.objects.create(role=empty_role, permission=self.perm_att_view)
        UserRole.objects.create(user=self.hr_user, role=empty_role, scope='branch', branch=empty_branch)

        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(f"{self.overview_url}?branch_id={empty_branch.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        org_data = response.data['organization']
        self.assertIsNotNone(org_data)
        self.assertEqual(org_data['workforce']['total_active'], 0)
        self.assertEqual(org_data['attendance_today']['expected_total'], 0)

    def test_dashboard_no_branch_id_branch_scoped_user_isolation(self):
        """No branch_id for branch-scoped user aggregates ONLY across their authorized branches, not all org branches."""
        branch3 = Branch.objects.create(organization=self.org1, name="Unassigned Branch", radius=100.0)
        u_extra = User.objects.create_user(email="extra@primary.com", password="Password123!", status="active")
        Employee.objects.create(
            user=u_extra, organization=self.org1, employee_code="EXT001",
            branch=branch3, employment_status=EmploymentStatus.ACTIVE
        )

        self.client.force_authenticate(user=self.hr_user)
        # Scope HR user strictly to branch1
        UserRole.objects.filter(user=self.hr_user).update(scope='branch', branch=self.branch1)

        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        org_data = response.data['organization']
        self.assertIsNotNone(org_data)
        # Should be 4 (branch1 employees), NOT 5 (which would include branch3)
        self.assertEqual(org_data['workforce']['total_active'], 4)


class DashboardTrendsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.today = timezone.localdate()
        self.trends_url = '/api/v1/dashboard/trends/'

        # Organization 1 (Primary)
        self.org1 = Organization.objects.create(name="Trends Primary Corp")
        from apps.organization.models import Branch
        self.branch1 = Branch.objects.create(organization=self.org1, name="Trends HQ", radius=100.0)
        OfficeNetwork.objects.create(branch=self.branch1, name="Primary Net", network="127.0.0.0/8", is_active=True)
        self.dept1 = Department.objects.create(branch=self.branch1, name="Engineering")

        # Organization 2 (Isolated)
        self.org2 = Organization.objects.create(name="Trends Secondary Corp")
        self.branch2 = Branch.objects.create(organization=self.org2, name="Secondary HQ", radius=100.0)
        OfficeNetwork.objects.create(branch=self.branch2, name="Secondary Net", network="10.0.0.0/8", is_active=True)

        # Standard Permissions
        self.perm_emp_view, _ = Permission.objects.get_or_create(
            codename='employee.view',
            defaults={'name': 'View Employee', 'resource': 'employee', 'action': 'view'}
        )
        self.perm_att_view, _ = Permission.objects.get_or_create(
            codename='attendance.view_all',
            defaults={'name': 'View Attendance All', 'resource': 'attendance', 'action': 'view_all'}
        )

        # 1. Regular employee (No admin permissions)
        self.emp_user = User.objects.create_user(
            email="emp@trendscorp.com", password="Password123!", status="active",
            first_name="Jane", last_name="Doe"
        )
        self.emp_profile = Employee.objects.create(
            user=self.emp_user, organization=self.org1, employee_code="TRD_EMP01",
            department=self.dept1, branch=self.branch1, employment_status=EmploymentStatus.ACTIVE,
            joining_date=self.today - timedelta(days=120)
        )

        # 2. HR user (Both attendance.view_all and employee.view)
        self.hr_user = User.objects.create_user(
            email="hr@trendscorp.com", password="Password123!", status="active",
            first_name="Helen", last_name="HR"
        )
        self.hr_profile = Employee.objects.create(
            user=self.hr_user, organization=self.org1, employee_code="TRD_HR01",
            department=self.dept1, branch=self.branch1, employment_status=EmploymentStatus.ACTIVE,
            joining_date=self.today - timedelta(days=120)
        )
        hr_role = Role.objects.create(organization=self.org1, name="HR Trends Admin")
        RolePermission.objects.create(role=hr_role, permission=self.perm_att_view)
        RolePermission.objects.create(role=hr_role, permission=self.perm_emp_view)
        UserRole.objects.create(user=self.hr_user, role=hr_role)

        # 3. Attendance View Only User
        self.att_user = User.objects.create_user(
            email="att@trendscorp.com", password="Password123!", status="active",
            first_name="Adam", last_name="Attendance"
        )
        self.att_profile = Employee.objects.create(
            user=self.att_user, organization=self.org1, employee_code="TRD_ATT01",
            department=self.dept1, branch=self.branch1, employment_status=EmploymentStatus.ACTIVE,
            joining_date=self.today - timedelta(days=120)
        )
        att_role = Role.objects.create(organization=self.org1, name="Attendance Only")
        RolePermission.objects.create(role=att_role, permission=self.perm_att_view)
        UserRole.objects.create(user=self.att_user, role=att_role)

        # 4. Employee View Only User
        self.staff_user = User.objects.create_user(
            email="staff@trendscorp.com", password="Password123!", status="active",
            first_name="Sam", last_name="Staff"
        )
        self.staff_profile = Employee.objects.create(
            user=self.staff_user, organization=self.org1, employee_code="TRD_STF01",
            department=self.dept1, branch=self.branch1, employment_status=EmploymentStatus.ACTIVE,
            joining_date=self.today - timedelta(days=120)
        )
        staff_role = Role.objects.create(organization=self.org1, name="Staff Only")
        RolePermission.objects.create(role=staff_role, permission=self.perm_emp_view)
        UserRole.objects.create(user=self.staff_user, role=staff_role)

        # 5. Isolated Org 2 User & Employee
        self.org2_user = User.objects.create_user(
            email="isolated@trendscorp2.com", password="Password123!", status="active"
        )
        self.org2_profile = Employee.objects.create(
            user=self.org2_user, organization=self.org2, employee_code="TRD_ORG2_01",
            employment_status=EmploymentStatus.ACTIVE,
            joining_date=self.today - timedelta(days=120)
        )

    def test_invalid_window_returns_400(self):
        """Endpoint rejects unsupported or missing window parameter with HTTP 400."""
        self.client.force_authenticate(user=self.hr_user)
        # Missing window
        r1 = self.client.get(self.trends_url)
        self.assertEqual(r1.status_code, status.HTTP_400_BAD_REQUEST)

        # Invalid window
        r2 = self.client.get(f"{self.trends_url}?window=invalid")
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)

        # Unsupported window like 30d
        r3 = self.client.get(f"{self.trends_url}?window=30d")
        self.assertEqual(r3.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_access_returns_401(self):
        """Unauthenticated requests to trends endpoint are strictly rejected with 401."""
        self.client.force_authenticate(user=None)
        r = self.client.get(f"{self.trends_url}?window=7d")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_without_organization_or_employee_returns_none_trends(self):
        """User without employee or organization context safely returns null trends without 500 error."""
        orphan_user = User.objects.create_user(email="orphan_trends@corp.com", password="Password123!", status="active")
        self.client.force_authenticate(user=orphan_user)
        r = self.client.get(f"{self.trends_url}?window=7d")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNone(r.data['attendance_trend'])
        self.assertIsNone(r.data['workforce_trend'])

    def test_permission_gating_personal_only_user(self):

        """User without attendance.view_all or employee.view receives null for both trends."""
        self.client.force_authenticate(user=self.emp_user)

        r_7d = self.client.get(f"{self.trends_url}?window=7d")
        self.assertEqual(r_7d.status_code, status.HTTP_200_OK)
        self.assertIsNone(r_7d.data['attendance_trend'])
        self.assertIsNone(r_7d.data['workforce_trend'])

        r_6m = self.client.get(f"{self.trends_url}?window=6m")
        self.assertEqual(r_6m.status_code, status.HTTP_200_OK)
        self.assertIsNone(r_7d.data['attendance_trend'])
        self.assertIsNone(r_7d.data['workforce_trend'])

    def test_permission_gating_attendance_view_all_only(self):
        """User with attendance.view_all receives 7d attendance trend but not workforce trend."""
        self.client.force_authenticate(user=self.att_user)

        r_7d = self.client.get(f"{self.trends_url}?window=7d")
        self.assertEqual(r_7d.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(r_7d.data['attendance_trend'])
        self.assertEqual(len(r_7d.data['attendance_trend']), 7)
        self.assertIsNone(r_7d.data['workforce_trend'])

        r_6m = self.client.get(f"{self.trends_url}?window=6m")
        self.assertEqual(r_6m.status_code, status.HTTP_200_OK)
        self.assertIsNone(r_6m.data['workforce_trend'])

    def test_permission_gating_employee_view_only(self):
        """User with employee.view receives 6m workforce trend but not attendance trend."""
        self.client.force_authenticate(user=self.staff_user)

        r_6m = self.client.get(f"{self.trends_url}?window=6m")
        self.assertEqual(r_6m.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(r_6m.data['workforce_trend'])
        self.assertEqual(len(r_6m.data['workforce_trend']), 6)
        self.assertIsNone(r_6m.data['attendance_trend'])

        r_7d = self.client.get(f"{self.trends_url}?window=7d")
        self.assertEqual(r_7d.status_code, status.HTTP_200_OK)
        self.assertIsNone(r_7d.data['attendance_trend'])

    def test_organization_isolation(self):
        """Org 2 employee records never bleed into Org 1 trend analytics."""
        # Create an attendance record for Org 2 employee on a past day
        past_date = self.today - timedelta(days=1)
        Attendance.objects.create(
            employee=self.org2_profile, date=past_date, status='present', check_in=timezone.now()
        )

        self.client.force_authenticate(user=self.hr_user)
        r = self.client.get(f"{self.trends_url}?window=7d")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        day_item = next(item for item in r.data['attendance_trend'] if item['date'] == str(past_date))
        # Total active workforce in Org 1 is 4 (emp, hr, att, staff). Org 2's employee must NOT be counted.
        self.assertEqual(day_item['expected_total'], 4)
        # Org 2's attendance must not be in present count
        self.assertEqual(day_item['present'], 0)

    def test_7d_attendance_trend_weekends(self):
        """Weekend days are flagged as non-working days with attendance_percentage null."""
        self.client.force_authenticate(user=self.hr_user)
        r = self.client.get(f"{self.trends_url}?window=7d")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        for item in r.data['attendance_trend']:
            d = date.fromisoformat(item['date'])
            if d.weekday() >= 5:  # Saturday or Sunday
                self.assertFalse(item['is_working_day'])
                self.assertIsNone(item['attendance_percentage'])
                self.assertEqual(item['expected_working'], 0)
                self.assertEqual(item['absent'], 0)

    def test_7d_attendance_trend_holidays(self):
        """Active organization holidays are marked as non-working days with percentage null."""
        # Pick a date within the 7-day window that is a weekday
        target_date = None
        for i in range(1, 7):
            candidate = self.today - timedelta(days=i)
            if candidate.weekday() < 5:
                target_date = candidate
                break

        if target_date:
            Holiday.objects.create(branch=self.branch1, name="Founder's Holiday", date=target_date, is_active=True)

            self.client.force_authenticate(user=self.hr_user)
            r = self.client.get(f"{self.trends_url}?window=7d")
            self.assertEqual(r.status_code, status.HTTP_200_OK)

            holiday_item = next(item for item in r.data['attendance_trend'] if item['date'] == str(target_date))
            self.assertFalse(holiday_item['is_working_day'])
            self.assertIsNone(holiday_item['attendance_percentage'])
            self.assertEqual(holiday_item['expected_working'], 0)

    def test_7d_attendance_trend_joining_date_boundary(self):
        """Employee joined mid-week is not counted in workforce before their joining date."""
        join_date = self.today - timedelta(days=2)
        u = User.objects.create_user(email="new_joiner@trendscorp.com", password="Password123!", status="active")
        Employee.objects.create(
            user=u, organization=self.org1, employee_code="TRD_NEW01",
            department=self.dept1, branch=self.branch1, employment_status=EmploymentStatus.ACTIVE,
            joining_date=join_date
        )

        self.client.force_authenticate(user=self.hr_user)
        r = self.client.get(f"{self.trends_url}?window=7d")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        day_before = str(join_date - timedelta(days=1))
        day_on = str(join_date)

        item_before = next(item for item in r.data['attendance_trend'] if item['date'] == day_before)
        item_on = next(item for item in r.data['attendance_trend'] if item['date'] == day_on)

        # 4 original employees before join date, 5 on join date
        self.assertEqual(item_before['expected_total'], 4)
        self.assertEqual(item_on['expected_total'], 5)

    def test_7d_attendance_trend_exit_date_boundary(self):
        """Employee with exit date is counted before exit date, but excluded on and after exit date."""
        exit_date = self.today - timedelta(days=2)
        u = User.objects.create_user(email="exited_emp@trendscorp.com", password="Password123!", status="active")
        Employee.objects.create(
            user=u, organization=self.org1, employee_code="TRD_EXIT01",
            department=self.dept1, branch=self.branch1, employment_status=EmploymentStatus.EXITED,
            joining_date=self.today - timedelta(days=100),
            exit_date=exit_date
        )

        self.client.force_authenticate(user=self.hr_user)
        r = self.client.get(f"{self.trends_url}?window=7d")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        day_before = str(exit_date - timedelta(days=1))
        day_on = str(exit_date)

        item_before = next(item for item in r.data['attendance_trend'] if item['date'] == day_before)
        item_on = next(item for item in r.data['attendance_trend'] if item['date'] == day_on)

        # 4 baseline + 1 = 5 before exit date; 4 on and after exit date
        self.assertEqual(item_before['expected_total'], 5)
        self.assertEqual(item_on['expected_total'], 4)

    def test_7d_attendance_trend_approved_leave(self):
        """Approved leave reduces expected_working and is not counted as absent."""
        # Find a past weekday
        target_date = None
        for i in range(1, 7):
            candidate = self.today - timedelta(days=i)
            if candidate.weekday() < 5:
                target_date = candidate
                break

        if target_date:
            leave_type = LeaveType.objects.create(organization=self.org1, name="Paid Vacation")
            LeaveRequest.objects.create(
                employee=self.emp_profile, leave_type=leave_type,
                start_date=target_date, end_date=target_date, status='approved'
            )

            self.client.force_authenticate(user=self.hr_user)
            r = self.client.get(f"{self.trends_url}?window=7d")
            self.assertEqual(r.status_code, status.HTTP_200_OK)

            item = next(it for it in r.data['attendance_trend'] if it['date'] == str(target_date))
            self.assertTrue(item['is_working_day'])
            self.assertEqual(item['expected_total'], 4)
            self.assertEqual(item['on_leave'], 1)
            self.assertEqual(item['expected_working'], 3)
            # 0 present, 3 absent (the other 3 employees did not punch)
            self.assertEqual(item['absent'], 3)

    def test_7d_attendance_trend_leave_plus_attendance_precedence(self):
        """If employee has approved leave but punches in, attendance presence takes precedence."""
        target_date = None
        for i in range(1, 7):
            candidate = self.today - timedelta(days=i)
            if candidate.weekday() < 5:
                target_date = candidate
                break

        if target_date:
            leave_type = LeaveType.objects.create(organization=self.org1, name="Casual Leave")
            LeaveRequest.objects.create(
                employee=self.emp_profile, leave_type=leave_type,
                start_date=target_date, end_date=target_date, status='approved'
            )
            # Employee actually attends!
            Attendance.objects.create(employee=self.emp_profile, date=target_date, status='present', check_in=timezone.now())

            self.client.force_authenticate(user=self.hr_user)
            r = self.client.get(f"{self.trends_url}?window=7d")
            self.assertEqual(r.status_code, status.HTTP_200_OK)

            item = next(it for it in r.data['attendance_trend'] if it['date'] == str(target_date))
            self.assertEqual(item['present'], 1)
            self.assertEqual(item['on_leave'], 0)  # precedence: not counted on leave
            self.assertEqual(item['expected_working'], 4)

    def test_7d_attendance_trend_half_day(self):
        """Half-day status is credited with 0.5 effective presence."""
        target_date = None
        for i in range(1, 7):
            candidate = self.today - timedelta(days=i)
            if candidate.weekday() < 5:
                target_date = candidate
                break

        if target_date:
            Attendance.objects.create(employee=self.emp_profile, date=target_date, status='half_day', check_in=timezone.now())

            self.client.force_authenticate(user=self.hr_user)
            r = self.client.get(f"{self.trends_url}?window=7d")
            self.assertEqual(r.status_code, status.HTTP_200_OK)

            item = next(it for it in r.data['attendance_trend'] if it['date'] == str(target_date))
            self.assertEqual(item['half_day'], 1)
            self.assertEqual(item['present'], 0)
            # 4 total active, 0 leave -> expected_working = 4
            # effective_present = 0 + (1 * 0.5) = 0.5
            # percentage = (0.5 / 4) * 100 = 12.5%
            self.assertEqual(item['attendance_percentage'], 12.5)

    def test_7d_attendance_trend_wfh_plus_attendance(self):
        """Approved WFH is an overlay; employee is present and not double-counted."""
        target_date = None
        for i in range(1, 7):
            candidate = self.today - timedelta(days=i)
            if candidate.weekday() < 5:
                target_date = candidate
                break

        if target_date:
            dt = timezone.now().replace(year=target_date.year, month=target_date.month, day=target_date.day)
            WFHRequest.objects.create(
                employee=self.emp_profile, status='approved',
                start_at=dt, end_at=dt + timedelta(hours=8), reason="Remote coding"
            )
            Attendance.objects.create(employee=self.emp_profile, date=target_date, status='present', check_in=dt)

            self.client.force_authenticate(user=self.hr_user)
            r = self.client.get(f"{self.trends_url}?window=7d")
            self.assertEqual(r.status_code, status.HTTP_200_OK)

            item = next(it for it in r.data['attendance_trend'] if it['date'] == str(target_date))
            self.assertEqual(item['on_wfh'], 1)
            self.assertEqual(item['present'], 1)
            self.assertEqual(item['expected_working'], 4)

    def test_7d_attendance_trend_zero_workforce(self):
        """Organization with zero workforce safely returns 7 items without ZeroDivisionError."""
        empty_org = Organization.objects.create(name="Empty Trends Corp")
        empty_user = User.objects.create_user(email="empty@trendscorp.com", password="Password123!", status="active")
        empty_profile = Employee.objects.create(
            user=empty_user, organization=empty_org, employee_code="EMPTY01",
            employment_status=EmploymentStatus.EXITED,
            joining_date=self.today - timedelta(days=365),
            exit_date=self.today - timedelta(days=30)  # already exited
        )
        empty_role = Role.objects.create(organization=empty_org, name="Empty Admin")
        RolePermission.objects.create(role=empty_role, permission=self.perm_att_view)
        UserRole.objects.create(user=empty_user, role=empty_role)

        self.client.force_authenticate(user=empty_user)
        r = self.client.get(f"{self.trends_url}?window=7d")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data['attendance_trend']), 7)
        for item in r.data['attendance_trend']:
            self.assertEqual(item['expected_total'], 0)
            if item['is_working_day']:
                self.assertEqual(item['attendance_percentage'], 0.0)
            else:
                self.assertIsNone(item['attendance_percentage'])

    def test_6m_workforce_trend_calculation_and_turnover(self):
        """Calculates 6-month workforce trend with start/end headcount, new hires, exits, and turnover rate."""
        # Create an employee who joined last month and exited last month
        last_month = (self.today.replace(day=1) - timedelta(days=1))
        u = User.objects.create_user(email="turnover_emp@trendscorp.com", password="Password123!", status="active")
        Employee.objects.create(
            user=u, organization=self.org1, employee_code="TRD_TURN01",
            department=self.dept1, branch=self.branch1, employment_status=EmploymentStatus.EXITED,
            joining_date=last_month.replace(day=5),
            exit_date=last_month.replace(day=20)
        )

        # Explicitly cover joining_date=None fallback to created_at invariant
        u_fallback = User.objects.create_user(email="fallback_join@trendscorp.com", password="Password123!", status="active")
        Employee.objects.create(
            user=u_fallback, organization=self.org1, employee_code="TRD_FALLBACK01",
            department=self.dept1, branch=self.branch1, employment_status=EmploymentStatus.ACTIVE,
            joining_date=None  # Explicitly None to test created_at fallback invariant
        )

        self.client.force_authenticate(user=self.hr_user)
        r = self.client.get(f"{self.trends_url}?window=6m")

        self.assertEqual(r.status_code, status.HTTP_200_OK)

        trend = r.data['workforce_trend']
        self.assertEqual(len(trend), 6)

        # Check chronology
        current_period = f"{self.today.year}-{self.today.month:02d}"
        self.assertEqual(trend[-1]['period'], current_period)

        # Check keys on each item
        for item in trend:
            self.assertIn('period', item)
            self.assertIn('year', item)
            self.assertIn('month', item)
            self.assertIn('month_name', item)
            self.assertIn('start_headcount', item)
            self.assertIn('end_headcount', item)
            self.assertIn('new_hires', item)
            self.assertIn('exits', item)
            self.assertIn('net_growth', item)
            self.assertIn('turnover_rate', item)
            self.assertEqual(item['net_growth'], item['new_hires'] - item['exits'])
            self.assertEqual(item['start_headcount'] + item['new_hires'] - item['exits'], item['end_headcount'])

    def test_6m_workforce_trend_zero_average_headcount(self):

        """Period with zero average headcount calculates turnover rate as 0.0 without ZeroDivisionError."""
        empty_org = Organization.objects.create(name="Empty Workforce Corp")
        empty_user = User.objects.create_user(email="empty_wf@trendscorp.com", password="Password123!", status="active")
        Employee.objects.create(
            user=empty_user, organization=empty_org, employee_code="EMPTY_WF01",
            employment_status=EmploymentStatus.EXITED,
            joining_date=self.today - timedelta(days=800),
            exit_date=self.today - timedelta(days=600)  # exited long ago
        )
        empty_role = Role.objects.create(organization=empty_org, name="Empty WF Admin")
        RolePermission.objects.create(role=empty_role, permission=self.perm_emp_view)
        UserRole.objects.create(user=empty_user, role=empty_role)

        self.client.force_authenticate(user=empty_user)
        r = self.client.get(f"{self.trends_url}?window=6m")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data['workforce_trend']), 6)
        for item in r.data['workforce_trend']:
            self.assertEqual(item['start_headcount'], 0)
            self.assertEqual(item['end_headcount'], 0)
            self.assertEqual(item['turnover_rate'], 0.0)

    def test_trends_unauthorized_branch_access_returns_403(self):
        """Trends endpoint with branch_id for unauthorized branch or cross-org branch returns HTTP 403 Forbidden."""
        # Scope HR user to branch1
        UserRole.objects.filter(user=self.hr_user).update(scope='branch', branch=self.branch1)
        self.client.force_authenticate(user=self.hr_user)

        # Cross-organization branch (branch2)
        r1 = self.client.get(f"{self.trends_url}?window=7d&branch_id={self.branch2.id}")
        self.assertEqual(r1.status_code, status.HTTP_403_FORBIDDEN)

        r2 = self.client.get(f"{self.trends_url}?window=6m&branch_id={self.branch2.id}")
        self.assertEqual(r2.status_code, status.HTTP_403_FORBIDDEN)

        # Same organization unauthorized branch (branch3)
        branch3 = Branch.objects.create(organization=self.org1, name="Trends Branch 3", radius=100.0)
        r3 = self.client.get(f"{self.trends_url}?window=7d&branch_id={branch3.id}")
        self.assertEqual(r3.status_code, status.HTTP_403_FORBIDDEN)

        r4 = self.client.get(f"{self.trends_url}?window=6m&branch_id={branch3.id}")
        self.assertEqual(r4.status_code, status.HTTP_403_FORBIDDEN)

    def test_trends_authorized_branch_access_returns_200(self):
        """Trends endpoint with branch_id for an authorized branch returns HTTP 200 with isolated data."""
        # Scope HR user to branch1
        UserRole.objects.filter(user=self.hr_user).update(scope='branch', branch=self.branch1)
        self.client.force_authenticate(user=self.hr_user)

        # Authorized branch (branch1)
        r1 = self.client.get(f"{self.trends_url}?window=7d&branch_id={self.branch1.id}")
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(r1.data['attendance_trend'])

        r2 = self.client.get(f"{self.trends_url}?window=6m&branch_id={self.branch1.id}")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(r2.data['workforce_trend'])

