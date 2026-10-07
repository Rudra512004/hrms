from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from datetime import date, timedelta
from unittest.mock import patch
from apps.attendance.models import Attendance, AttendanceProductivity
from apps.organization.models import Organization, Branch, Department, Team
from apps.employees.models import Employee
from django.contrib.auth import get_user_model
from apps.authorization.models import Role, Permission, RolePermission, UserRole
from apps.attendance.analytics import ProductivityAnalyticsService

User = get_user_model()

class ProductivityAnalyticsTests(APITestCase):
    def setUp(self):
        patcher = patch('apps.authorization.network.NetworkAccessService.is_remote_access_allowed', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.org1 = Organization.objects.create(name="Org1", status="active")
        self.org2 = Organization.objects.create(name="Org2", status="active")

        self.branch1 = Branch.objects.create(organization=self.org1, name="Branch1", is_active=True)
        self.branch2 = Branch.objects.create(organization=self.org1, name="Branch2", is_active=True)
        
        self.dept1 = Department.objects.create(branch=self.branch1, name="Dept1")
        self.team1 = Team.objects.create(department=self.dept1, name="Team1")
        self.team2 = Team.objects.create(department=self.dept1, name="Team2")

        self.user1 = User.objects.create_user(email='emp1@test.com', password='password', first_name="E", last_name="1", status='active')
        self.emp1 = Employee.objects.create(user=self.user1, employee_code='E1', organization=self.org1, branch=self.branch1, department=self.dept1, team=self.team1, employment_status='active')

        self.user2 = User.objects.create_user(email='emp2@test.com', password='password', first_name="E", last_name="2", status='active')
        self.emp2 = Employee.objects.create(user=self.user2, employee_code='E2', organization=self.org1, branch=self.branch1, department=self.dept1, team=self.team2, employment_status='active')

        self.user3 = User.objects.create_user(email='emp3@test.com', password='password', first_name="E", last_name="3", status='active')
        self.emp3 = Employee.objects.create(user=self.user3, employee_code='E3', organization=self.org1, branch=self.branch2, employment_status='active')

        self.user4 = User.objects.create_user(email='emp4@test.com', password='password', status='active')
        self.emp4 = Employee.objects.create(user=self.user4, employee_code='E4', organization=self.org2, branch=Branch.objects.create(organization=self.org2, name="O2B"), employment_status='active')

        # Create Permissions
        self.perm_view_all, _ = Permission.objects.get_or_create(codename='attendance.view_all', defaults={'resource': 'attendance', 'action': 'view_all', 'name': 'View All'})
        
        self.manager_role = Role.objects.create(organization=self.org1, name="Manager")
        RolePermission.objects.create(role=self.manager_role, permission=self.perm_view_all)
        
        self.super_role = Role.objects.create(organization=self.org1, name="SuperAdmin")
        RolePermission.objects.create(role=self.super_role, permission=self.perm_view_all)

        # emp1 is Manager of team1. emp3 is SuperAdmin of Org1.
        UserRole.objects.create(user=self.user1, role=self.manager_role, team=self.team1, scope='team')
        UserRole.objects.create(user=self.user3, role=self.super_role, scope='organization')

        self._seed_attendance()

    def _seed_attendance(self):
        # 3 days of data
        dates = [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)]
        for idx, d in enumerate(dates):
            # Emp 1 (Team 1)
            a1 = Attendance.objects.create(employee=self.emp1, date=d, status='present', total_break_duration=timedelta(hours=1))
            AttendanceProductivity.objects.create(
                attendance=a1,
                online_duration=timedelta(hours=8),
                active_duration=timedelta(hours=6),
                idle_duration=timedelta(hours=2),
                productive_duration=timedelta(hours=5),
                active_percent=75.0,
                mouse_clicks=1000 + idx
            )
            # Emp 2 (Team 2)
            a2 = Attendance.objects.create(employee=self.emp2, date=d, status='present', total_break_duration=timedelta(hours=0.5))
            AttendanceProductivity.objects.create(
                attendance=a2,
                online_duration=timedelta(hours=9),
                active_duration=timedelta(hours=8),
                idle_duration=timedelta(hours=1),
                productive_duration=timedelta(hours=7),
                active_percent=88.8,
                mouse_clicks=2000
            )
            # Emp 4 (Org 2)
            a4 = Attendance.objects.create(employee=self.emp4, date=d, status='present')
            AttendanceProductivity.objects.create(
                attendance=a4,
                online_duration=timedelta(hours=8),
                active_duration=timedelta(hours=8),
            )
            
    def test_overview_aggregation_correctness(self):
        """Test overview metrics accurately aggregate data"""
        self.client.force_authenticate(user=self.user3)
        url = reverse('productivity-analytics-overview')
        res = self.client.get(url, {'start_date': '2026-10-01', 'end_date': '2026-10-03'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Org 2 employee should be excluded via RBAC automatically.
        # Emp1 and Emp2 are in Org 1. 3 days each = 6 records.
        self.assertEqual(res.data['attendance_count'], 6)
        # Total active duration: Emp1 (6h*3 = 18h) + Emp2 (8h*3 = 24h) = 42 hours = "42:00:00"
        self.assertEqual(res.data['total_active_duration'], "42:00:00")
        self.assertEqual(res.data['total_idle_duration'], "09:00:00")
        # Avg active percent: (75.0 * 3 + 88.8 * 3) / 6 = 81.9
        self.assertAlmostEqual(res.data['average_active_percent'], 81.9, places=1)
        self.assertEqual(res.data['total_mouse_clicks'], 1000 + 1001 + 1002 + 6000)

    def test_date_filtering(self):
        """Test daily, weekly, monthly date filters work"""
        self.client.force_authenticate(user=self.user3)
        url = reverse('productivity-analytics-overview')
        
        # Single day
        res = self.client.get(url, {'start_date': '2026-10-01', 'end_date': '2026-10-01'})
        self.assertEqual(res.data['attendance_count'], 2)
        
        # Date range missing
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_trends_endpoint(self):
        """Test trends group data by date"""
        self.client.force_authenticate(user=self.user3)
        url = reverse('productivity-analytics-trends')
        res = self.client.get(url, {'start_date': '2026-10-01', 'end_date': '2026-10-02'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)
        self.assertEqual(str(res.data[0]['date']), '2026-10-01')
        self.assertEqual(res.data[0]['attendance_count'], 2)
        self.assertEqual(res.data[0]['total_active_duration'], '14:00:00')

    def test_team_breakdown(self):
        self.client.force_authenticate(user=self.user3)
        url = reverse('productivity-analytics-team-breakdown')
        res = self.client.get(url, {'start_date': '2026-10-01', 'end_date': '2026-10-01'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)
        team_names = [r['team_name'] for r in res.data]
        self.assertIn('Team1', team_names)
        self.assertIn('Team2', team_names)

    def test_employee_breakdown(self):
        self.client.force_authenticate(user=self.user3)
        url = reverse('productivity-analytics-employee-breakdown')
        res = self.client.get(url, {'start_date': '2026-10-01', 'end_date': '2026-10-01'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)
        names = [r['employee_name'] for r in res.data]
        self.assertIn('E 1', names)
        self.assertIn('E 2', names)

    def test_rbac_team_scope(self):
        """Test manager restricted to team1 scope"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('productivity-analytics-overview')
        res = self.client.get(url, {'start_date': '2026-10-01', 'end_date': '2026-10-03'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Should only see Team1 (emp1)
        self.assertEqual(res.data['attendance_count'], 3)
        self.assertEqual(res.data['total_active_duration'], "18:00:00")

    def test_idor_attempt(self):
        """Test trying to force filter on team2 as team1 manager"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('productivity-analytics-overview')
        res = self.client.get(url, {'start_date': '2026-10-01', 'end_date': '2026-10-03', 'team_id': self.team2.id})
        # Backend should just silently return 0 results since the QS filter intersects with RBAC authorized_teams
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['attendance_count'], 0)
        self.assertEqual(res.data['total_active_duration'], "00:00:00")

    def test_permission_denied(self):
        self.client.force_authenticate(user=self.user4) # No permissions
        url = reverse('productivity-analytics-overview')
        res = self.client.get(url, {'start_date': '2026-10-01', 'end_date': '2026-10-03'})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_empty_dataset(self):
        self.client.force_authenticate(user=self.user3)
        url = reverse('productivity-analytics-overview')
        res = self.client.get(url, {'start_date': '2028-10-01', 'end_date': '2028-10-03'})
        self.assertEqual(res.data['attendance_count'], 0)
        self.assertEqual(res.data['total_active_duration'], "00:00:00")
        self.assertEqual(res.data['total_mouse_clicks'], 0)
        self.assertEqual(res.data['average_active_percent'], 0.0)
