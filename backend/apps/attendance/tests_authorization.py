from datetime import date, time, timedelta
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.organization.models import (
    Organization, Branch, Department, Team, OfficeNetwork, AttendancePolicy, WorkingCalendar
)
from apps.employees.models import Employee
from apps.authorization.models import (
    Role, Permission, RolePermission, UserRole, ScopeChoices
)
from apps.attendance.models import (
    Attendance, Holiday, Shift, EmployeeShiftAssignment
)

User = get_user_model()

class AttendanceAuthorizationTestSuite(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Organization 1
        self.org1 = Organization.objects.create(name='Org Alpha')
        self.branch1 = Branch.objects.create(
            organization=self.org1, name='Alpha HQ',
            latitude='12.971600', longitude='77.594600', radius=150.0
        )
        self.branch2 = Branch.objects.create(
            organization=self.org1, name='Alpha North',
            latitude='13.000000', longitude='77.600000', radius=150.0
        )
        self.dept1 = Department.objects.create(branch=self.branch1, name='Engineering')
        self.team1_a = Team.objects.create(department=self.dept1, name='Backend Team')
        self.team1_b = Team.objects.create(department=self.dept1, name='Frontend Team')

        # Organization 2
        self.org2 = Organization.objects.create(name='Org Beta')
        self.branch3 = Branch.objects.create(
            organization=self.org2, name='Beta HQ',
            latitude='19.076000', longitude='72.877700', radius=150.0
        )
        self.dept2 = Department.objects.create(branch=self.branch3, name='Operations')
        self.team2 = Team.objects.create(department=self.dept2, name='Beta Ops')

        # Network for remote access allowance
        self.net1 = OfficeNetwork.objects.create(branch=self.branch1, name='Net1', network='192.168.1.0/24')
        self.net2 = OfficeNetwork.objects.create(branch=self.branch2, name='Net2', network='192.168.2.0/24')
        self.net3 = OfficeNetwork.objects.create(branch=self.branch3, name='Net3', network='192.168.3.0/24')
        self.net_local1 = OfficeNetwork.objects.create(branch=self.branch1, name='Local1', network='127.0.0.1/32')
        self.net_local3 = OfficeNetwork.objects.create(branch=self.branch3, name='Local3', network='127.0.0.1/32')
        self.client_ip = '127.0.0.1'

        # Superuser
        self.super_user = User.objects.create_user(email='super@alpha.com', password='Password123!', is_superuser=True)
        self.super_emp = Employee.objects.create(
            user=self.super_user, employee_code='SUP-01', organization=self.org1, branch=self.branch1
        )

        # Employees in Org 1
        # Emp 1A: Branch 1, Dept 1, Team A
        self.user_1a = User.objects.create_user(email='emp1a@alpha.com', password='Password123!', status='active')
        self.emp_1a = Employee.objects.create(
            user=self.user_1a, employee_code='EMP-1A', organization=self.org1,
            branch=self.branch1, department=self.dept1, team=self.team1_a
        )

        # Emp 1B: Branch 1, Dept 1, Team B (sibling team)
        self.user_1b = User.objects.create_user(email='emp1b@alpha.com', password='Password123!', status='active')
        self.emp_1b = Employee.objects.create(
            user=self.user_1b, employee_code='EMP-1B', organization=self.org1,
            branch=self.branch1, department=self.dept1, team=self.team1_b
        )

        # Emp 1C: Branch 1, Dept 1, no team (department-level / parent)
        self.user_1c = User.objects.create_user(email='emp1c@alpha.com', password='Password123!', status='active')
        self.emp_1c = Employee.objects.create(
            user=self.user_1c, employee_code='EMP-1C', organization=self.org1,
            branch=self.branch1, department=self.dept1, team=None
        )

        # Emp 2: Branch 2 (different branch in Org 1)
        self.user_2 = User.objects.create_user(email='emp2@alpha.com', password='Password123!', status='active')
        self.emp_2 = Employee.objects.create(
            user=self.user_2, employee_code='EMP-2', organization=self.org1,
            branch=self.branch2
        )

        # Emp 3: Org 2, Branch 3 (cross-tenant)
        self.user_3 = User.objects.create_user(email='emp3@beta.com', password='Password123!', status='active')
        self.emp_3 = Employee.objects.create(
            user=self.user_3, employee_code='EMP-3', organization=self.org2,
            branch=self.branch3, department=self.dept2, team=self.team2
        )

        # Today's attendance records
        self.today = timezone.now().date()
        self.att_1a = Attendance.objects.create(employee=self.emp_1a, date=self.today, status='present')
        self.att_1b = Attendance.objects.create(employee=self.emp_1b, date=self.today, status='present')
        self.att_1c = Attendance.objects.create(employee=self.emp_1c, date=self.today, status='half_day')
        self.att_2 = Attendance.objects.create(employee=self.emp_2, date=self.today, status='present')
        self.att_3 = Attendance.objects.create(employee=self.emp_3, date=self.today, status='present')

    def test_attendance_permission_availability(self):
        """1. Ensure all attendance permissions are registered and available in the DB."""
        expected_codenames = [
            'attendance.view_all',
            'holiday.view',
            'holiday.manage',
            'shift.view',
            'shift.manage',
            'shift_assignment.view',
            'shift_assignment.manage',
        ]
        for codename in expected_codenames:
            perm = Permission.objects.filter(codename=codename).first()
            self.assertIsNotNone(perm, f"Permission {codename} is missing from database.")
            self.assertTrue(perm.is_active)
            self.assertTrue(bool(perm.name))

    def test_organization_scoped_attendance_access(self):
        """2. Organization-scoped role sees all branches in own org, but zero in other orgs."""
        role = Role.objects.create(organization=self.org1, name='Org Attendance Admin')
        perm = Permission.objects.get(codename='attendance.view_all')
        RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(user=self.user_1a, role=role, scope=ScopeChoices.ORGANIZATION)

        self.client.force_authenticate(user=self.user_1a)
        res = self.client.get(reverse('attendance-management-list'), REMOTE_ADDR=self.client_ip)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        emp_ids = [r['employee'] for r in res.data]
        self.assertIn(self.emp_1a.id, emp_ids)
        self.assertIn(self.emp_1b.id, emp_ids)
        self.assertIn(self.emp_1c.id, emp_ids)
        self.assertIn(self.emp_2.id, emp_ids)
        self.assertNotIn(self.emp_3.id, emp_ids, "Cross-org attendance must not be visible.")

    def test_branch_scoped_attendance_access(self):
        """3. Branch-scoped role sees all employees in assigned branch only."""
        role = Role.objects.create(organization=self.org1, name='Branch 1 Admin')
        perm = Permission.objects.get(codename='attendance.view_all')
        RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(
            user=self.user_1a, role=role, scope=ScopeChoices.BRANCH, branch=self.branch1
        )

        self.client.force_authenticate(user=self.user_1a)
        res = self.client.get(reverse('attendance-management-list'), REMOTE_ADDR=self.client_ip)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        emp_ids = [r['employee'] for r in res.data]
        # In Branch 1:
        self.assertIn(self.emp_1a.id, emp_ids)
        self.assertIn(self.emp_1b.id, emp_ids)
        self.assertIn(self.emp_1c.id, emp_ids)
        # Not in Branch 1:
        self.assertNotIn(self.emp_2.id, emp_ids, "Branch 2 records must not be visible.")
        self.assertNotIn(self.emp_3.id, emp_ids, "Org 2 records must not be visible.")

    def test_team_scoped_attendance_access(self):
        """4. Team-scoped role sees strictly authorized team employees."""
        role = Role.objects.create(organization=self.org1, name='Team A Lead')
        perm = Permission.objects.get(codename='attendance.view_all')
        RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(
            user=self.user_1a, role=role, scope=ScopeChoices.TEAM, team=self.team1_a
        )

        self.client.force_authenticate(user=self.user_1a)
        res = self.client.get(reverse('attendance-management-list'), REMOTE_ADDR=self.client_ip)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        emp_ids = [r['employee'] for r in res.data]
        self.assertEqual(emp_ids, [self.emp_1a.id], "Team scope must only include Team A employees.")

    def test_team_scope_cannot_access_sibling_or_parent_employees(self):
        """5. Team scope must not expand to sibling teams, parent dept, or via query manipulation."""
        role = Role.objects.create(organization=self.org1, name='Team A Lead')
        perm = Permission.objects.get(codename='attendance.view_all')
        RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(
            user=self.user_1a, role=role, scope=ScopeChoices.TEAM, team=self.team1_a
        )

        self.client.force_authenticate(user=self.user_1a)

        # Attempt to filter by sibling team
        res_sibling = self.client.get(
            f"{reverse('attendance-management-list')}?team_id={self.team1_b.id}",
            REMOTE_ADDR=self.client_ip
        )
        self.assertEqual(res_sibling.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_sibling.data), 0, "Querying sibling team must return empty.")

        # Attempt to filter by parent branch
        res_branch = self.client.get(
            f"{reverse('attendance-management-list')}?branch_id={self.branch1.id}",
            REMOTE_ADDR=self.client_ip
        )
        self.assertEqual(res_branch.status_code, status.HTTP_200_OK)
        emp_ids = [r['employee'] for r in res_branch.data]
        self.assertNotIn(self.emp_1b.id, emp_ids, "Sibling team must not appear.")
        self.assertNotIn(self.emp_1c.id, emp_ids, "Parent department employee without team must not appear.")
        self.assertEqual(emp_ids, [self.emp_1a.id])

    def test_unauthorized_branch_access(self):
        """6. Unauthorized branch query yields empty list; missing permission yields 403."""
        # Unprivileged user
        self.client.force_authenticate(user=self.user_2)
        res_forbidden = self.client.get(reverse('attendance-management-list'), REMOTE_ADDR=self.client_ip)
        self.assertEqual(res_forbidden.status_code, status.HTTP_403_FORBIDDEN)

        # User with Branch 1 permission querying Branch 2
        role = Role.objects.create(organization=self.org1, name='Branch 1 Only')
        perm = Permission.objects.get(codename='attendance.view_all')
        RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(user=self.user_1a, role=role, scope=ScopeChoices.BRANCH, branch=self.branch1)

        self.client.force_authenticate(user=self.user_1a)
        res_other = self.client.get(
            f"{reverse('attendance-management-list')}?branch_id={self.branch2.id}",
            REMOTE_ADDR=self.client_ip
        )
        self.assertEqual(res_other.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_other.data), 0, "Cannot query another branch without authorization.")

    def test_unauthorized_holiday_modification(self):
        """7. User cannot create, update, or delete holidays for unauthorized branches."""
        role = Role.objects.create(organization=self.org1, name='Branch 1 Holiday Admin')
        p_view = Permission.objects.get(codename='holiday.view')
        p_manage = Permission.objects.get(codename='holiday.manage')
        RolePermission.objects.create(role=role, permission=p_view)
        RolePermission.objects.create(role=role, permission=p_manage)
        UserRole.objects.create(user=self.user_1a, role=role, scope=ScopeChoices.BRANCH, branch=self.branch1)

        holiday_b1 = Holiday.objects.create(branch=self.branch1, name='HQ Day', date='2026-10-01')
        holiday_b2 = Holiday.objects.create(branch=self.branch2, name='North Day', date='2026-10-02')

        self.client.force_authenticate(user=self.user_1a)

        # 1. Cannot create in Branch 2
        res_create = self.client.post(reverse('holiday-list'), {
            'branch': self.branch2.id,
            'name': 'Malicious Holiday',
            'date': '2026-11-01'
        })
        self.assertEqual(res_create.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('branch', res_create.data)

        # 2. Cannot create in Org 2
        res_cross_org = self.client.post(reverse('holiday-list'), {
            'branch': self.branch3.id,
            'name': 'Cross Org Holiday',
            'date': '2026-11-01'
        })
        self.assertEqual(res_cross_org.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. Cannot move existing Branch 1 holiday to Branch 2
        res_patch_move = self.client.patch(reverse('holiday-detail', args=[holiday_b1.id]), {
            'branch': self.branch2.id
        })
        self.assertEqual(res_patch_move.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('branch', res_patch_move.data)

        # 4. Cannot modify Branch 2 holiday (404 from scoped queryset)
        res_patch_b2 = self.client.patch(reverse('holiday-detail', args=[holiday_b2.id]), {
            'name': 'Hacked Name'
        })
        self.assertEqual(res_patch_b2.status_code, status.HTTP_404_NOT_FOUND)

        # 5. Cannot delete Branch 2 holiday
        res_del_b2 = self.client.delete(reverse('holiday-detail', args=[holiday_b2.id]))
        self.assertEqual(res_del_b2.status_code, status.HTTP_404_NOT_FOUND)

        # 6. CAN successfully update Branch 1 holiday
        res_ok = self.client.patch(reverse('holiday-detail', args=[holiday_b1.id]), {
            'name': 'Renamed HQ Day'
        })
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        holiday_b1.refresh_from_db()
        self.assertEqual(holiday_b1.name, 'Renamed HQ Day')

    def test_unauthorized_shift_modification(self):
        """8. User cannot create, update, or delete shifts for unauthorized branches."""
        role = Role.objects.create(organization=self.org1, name='Branch 1 Shift Admin')
        p_view = Permission.objects.get(codename='shift.view')
        p_manage = Permission.objects.get(codename='shift.manage')
        RolePermission.objects.create(role=role, permission=p_view)
        RolePermission.objects.create(role=role, permission=p_manage)
        UserRole.objects.create(user=self.user_1a, role=role, scope=ScopeChoices.BRANCH, branch=self.branch1)

        shift_b1 = Shift.objects.create(
            branch=self.branch1, name='Day Shift HQ', start_time=time(9, 0), end_time=time(17, 0)
        )
        shift_b2 = Shift.objects.create(
            branch=self.branch2, name='Night Shift North', start_time=time(22, 0), end_time=time(6, 0)
        )

        self.client.force_authenticate(user=self.user_1a)

        # 1. Cannot create shift in Branch 2
        res_create = self.client.post(reverse('shift-list'), {
            'branch': self.branch2.id,
            'name': 'Rogue Shift',
            'start_time': '10:00:00',
            'end_time': '18:00:00'
        })
        self.assertEqual(res_create.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('branch', res_create.data)

        # 2. Cannot create shift in Org 2
        res_cross = self.client.post(reverse('shift-list'), {
            'branch': self.branch3.id,
            'name': 'Cross Shift',
            'start_time': '10:00:00',
            'end_time': '18:00:00'
        })
        self.assertEqual(res_cross.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. Cannot move Branch 1 shift to Branch 2
        res_move = self.client.patch(reverse('shift-detail', args=[shift_b1.id]), {
            'branch': self.branch2.id
        })
        self.assertEqual(res_move.status_code, status.HTTP_400_BAD_REQUEST)

        # 4. Cannot modify Branch 2 shift
        res_patch_b2 = self.client.patch(reverse('shift-detail', args=[shift_b2.id]), {
            'name': 'Tampered'
        })
        self.assertEqual(res_patch_b2.status_code, status.HTTP_404_NOT_FOUND)

        # 5. Cannot delete Branch 2 shift
        res_del_b2 = self.client.delete(reverse('shift-detail', args=[shift_b2.id]))
        self.assertEqual(res_del_b2.status_code, status.HTTP_404_NOT_FOUND)

        # 6. CAN modify Branch 1 shift
        res_ok = self.client.patch(reverse('shift-detail', args=[shift_b1.id]), {
            'name': 'Updated Day Shift HQ'
        })
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        shift_b1.refresh_from_db()
        self.assertEqual(shift_b1.name, 'Updated Day Shift HQ')

    def test_cross_organization_isolation(self):
        """9. Cross-organization isolation for attendance, shifts, and shift assignments."""
        role1 = Role.objects.create(organization=self.org1, name='Org 1 Admin')
        p_sa_manage = Permission.objects.get(codename='shift_assignment.manage')
        p_sa_view = Permission.objects.get(codename='shift_assignment.view')
        RolePermission.objects.create(role=role1, permission=p_sa_manage)
        RolePermission.objects.create(role=role1, permission=p_sa_view)
        UserRole.objects.create(user=self.user_1a, role=role1, scope=ScopeChoices.ORGANIZATION)

        shift_b1 = Shift.objects.create(
            branch=self.branch1, name='S1', start_time=time(9, 0), end_time=time(17, 0)
        )
        shift_b3 = Shift.objects.create(
            branch=self.branch3, name='S3', start_time=time(9, 0), end_time=time(17, 0)
        )

        self.client.force_authenticate(user=self.user_1a)

        # Cannot assign employee from Org 2 to shift in Org 1
        res_x1 = self.client.post(reverse('shift-assignment-list'), {
            'employee': self.emp_3.id,
            'shift': shift_b1.id,
            'effective_from': '2026-10-01'
        })
        self.assertEqual(res_x1.status_code, status.HTTP_400_BAD_REQUEST)

        # Cannot assign employee from Org 1 to shift in Org 2
        res_x2 = self.client.post(reverse('shift-assignment-list'), {
            'employee': self.emp_1a.id,
            'shift': shift_b3.id,
            'effective_from': '2026-10-01'
        })
        self.assertEqual(res_x2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_attendance_policy_authorization(self):
        """10. AttendancePolicy API authorization via Branch configuration endpoint."""
        url_policy = reverse('branch-attendance-policy', args=[self.branch1.id])
        url_branch = reverse('branch-detail', args=[self.branch1.id])

        # 1. User without branch.view gets 403
        self.client.force_authenticate(user=self.user_1a)
        res_unauth = self.client.get(url_policy)
        self.assertEqual(res_unauth.status_code, status.HTTP_403_FORBIDDEN)

        # Grant branch.view
        role = Role.objects.create(organization=self.org1, name='Branch Viewer')
        p_branch_view = Permission.objects.get_or_create(
            codename='branch.view', defaults={'name': 'View Branch', 'resource': 'branch', 'action': 'view'}
        )[0]
        p_branch_manage = Permission.objects.get_or_create(
            codename='branch.manage', defaults={'name': 'Manage Branch', 'resource': 'branch', 'action': 'manage'}
        )[0]
        RolePermission.objects.create(role=role, permission=p_branch_view)
        UserRole.objects.create(user=self.user_1a, role=role, scope=ScopeChoices.BRANCH, branch=self.branch1)

        # 2. Can GET attendance-policy
        res_get = self.client.get(url_policy)
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertIn('is_office_gps_enabled', res_get.data)
        self.assertTrue(res_get.data['is_office_gps_enabled'])

        # 3. Cannot PATCH without branch.manage (403)
        res_patch_unauth = self.client.patch(url_policy, {'is_office_ip_enabled': True})
        self.assertEqual(res_patch_unauth.status_code, status.HTTP_403_FORBIDDEN)

        # Grant branch.manage
        RolePermission.objects.create(role=role, permission=p_branch_manage)

        # 4. Successfully PATCH via dedicated action endpoint
        res_patch_ok = self.client.patch(url_policy, {
            'is_office_ip_enabled': True,
            'is_wfh_enabled': True
        })
        self.assertEqual(res_patch_ok.status_code, status.HTTP_200_OK)
        self.assertTrue(res_patch_ok.data['is_office_ip_enabled'])
        self.assertTrue(res_patch_ok.data['is_wfh_enabled'])

        self.branch1.refresh_from_db()
        policy = self.branch1.attendance_policy
        self.assertTrue(policy.is_office_ip_enabled)
        self.assertTrue(policy.is_wfh_enabled)

        # 5. Successfully update via nested BranchSerializer on PATCH /branches/{id}/
        res_branch_patch = self.client.patch(url_branch, {
            'attendance_policy': {
                'is_office_gps_enabled': False
            }
        }, format='json')
        self.assertEqual(res_branch_patch.status_code, status.HTTP_200_OK)
        policy.refresh_from_db()
        self.assertFalse(policy.is_office_gps_enabled)
        self.assertFalse(res_branch_patch.data['attendance_policy']['is_office_gps_enabled'])

        # 6. Cannot access policy for a branch in another organization
        url_other_policy = reverse('branch-attendance-policy', args=[self.branch3.id])
        res_other = self.client.get(url_other_policy)
        self.assertEqual(res_other.status_code, status.HTTP_404_NOT_FOUND)
