from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Employee, WFHRequest
from apps.organization.models import Organization, OfficeNetwork
from .models import Attendance
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class AttendanceAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Test Org')
        from apps.organization.models import Branch
        self.branch = Branch.objects.create(organization=self.org, name='HQ')
        policy = self.branch.attendance_policy
        policy.is_office_gps_enabled = False
        policy.is_office_ip_enabled = False
        policy.save()
        self.branch.working_calendar.work_days = '0,1,2,3,4,5,6'
        self.branch.working_calendar.save()
        self.user = User.objects.create_user(email='emp@example.com', password='Password123!', status='active')
        self.employee = Employee.objects.create(user=self.user, employee_code='EMP01', organization=self.org, branch=self.branch)
        self.network = OfficeNetwork.objects.create(branch=self.branch, name='HQ', network='203.0.113.0/24')
        self.office_ip = '203.0.113.50'
        self.external_ip = '198.51.100.5'

        from apps.attendance.models import Shift
        from datetime import time
        self.shift = Shift.objects.create(
            branch=self.branch,
            name='Standard Shift',
            start_time=time(9, 0),
            end_time=time(17, 0),
            grace_period=timedelta(minutes=15),
            full_day_hours=timedelta(hours=8),
            half_day_hours=timedelta(hours=4),
            work_days='0,1,2,3,4,5,6'
        )

        self.super_user = User.objects.create_user(email='super@example.com', password='Password123!', status='active', is_superuser=True)
        self.super_employee = Employee.objects.create(user=self.super_user, employee_code='EMP02', organization=self.org, branch=self.branch, personal_email='super@ext.com')

    def test_office_ip_check_in(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Attendance.objects.count(), 1)






    def test_superadmin_access(self):
        # Superadmins are explicitly prevented from checking in
        self.client.force_authenticate(user=self.super_user)
        response = self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.external_ip)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_duplicate_check_in(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_successful_check_out(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(reverse('attendance-check-out'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(Attendance.objects.first().check_out)

    def test_check_out_before_check_in(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('attendance-check-out'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get('detail'), 'Cannot check out without a check-in.')

    def test_duplicate_check_out(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        self.client.post(reverse('attendance-check-out'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(reverse('attendance-check-out'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get('detail'), 'Already checked out for today.')

    def test_check_out_with_existing_attendance_null_check_in_returns_400(self):
        """Regression test: attendance record exists for today with check_in=None.
        Checkout must return HTTP 400 with expected detail without producing HTTP 500
        and without modifying check_out or attendance status."""
        today = timezone.now().date()
        att = Attendance.objects.create(
            employee=self.employee,
            date=today,
            status='present',
            check_in=None
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('attendance-check-out'), REMOTE_ADDR=self.office_ip)

        self.assertNotEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get('detail'), 'Cannot check out without a check-in.')

        att.refresh_from_db()
        self.assertIsNone(att.check_in)
        self.assertIsNone(att.check_out)
        self.assertEqual(att.status, 'present')
        self.assertIsNone(att.productive_work_duration)

    def test_check_out_during_active_break_rejected(self):
        """Checkout while on an active break returns HTTP 400 and preserves open break."""
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)

        response = self.client.post(reverse('attendance-check-out'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get('detail'), 'End the active break before checking out.')

        att = Attendance.objects.get(employee=self.employee, date=timezone.now().date())
        self.assertIsNone(att.check_out)
        self.assertTrue(att.breaks.filter(ended_at__isnull=True).exists())

    def test_check_out_productive_duration_calculated_with_breaks(self):
        """Normal checkout with valid check_in and completed break calculates productive duration."""
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        att = Attendance.objects.get(employee=self.employee, date=timezone.now().date())
        now = timezone.now()
        att.check_in = now - timedelta(hours=2)
        att.save()

        # Start and end a 20-minute break
        self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)
        brk = att.breaks.first()
        brk.started_at = now - timedelta(minutes=40)
        brk.ended_at = now - timedelta(minutes=20)
        brk.save()
        att.total_break_duration = timedelta(minutes=20)
        att.save()

        response = self.client.post(reverse('attendance-check-out'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        att.refresh_from_db()
        self.assertIsNotNone(att.check_out)
        self.assertIsNotNone(att.productive_work_duration)
        self.assertGreaterEqual(att.productive_work_duration.total_seconds(), 95 * 60)
        self.assertLessEqual(att.productive_work_duration.total_seconds(), 105 * 60)

    def test_employee_id_injection(self):
        self.client.force_authenticate(user=self.user)
        # Attempt to inject another employee ID
        response = self.client.post(reverse('attendance-check-in'), data={'employee': self.super_employee.id}, REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Verify attendance was logged for self.user's employee, not the injected one
        attendance = Attendance.objects.first()
        self.assertEqual(attendance.employee.id, self.employee.id)

    def test_idor_view_attendance(self):
        Attendance.objects.create(employee=self.super_employee, date=timezone.now().date(), status='present')
        Attendance.objects.create(employee=self.employee, date=timezone.now().date(), status='present')
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('attendance-list'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['employee'], self.employee.id)


    def test_start_break(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_on_break'])
        self.assertEqual(len(response.data['breaks']), 1)
        self.assertIsNone(response.data['breaks'][0]['ended_at'])

    def test_end_break(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(reverse('attendance-end-break'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_on_break'])
        self.assertIsNotNone(response.data['breaks'][0]['ended_at'])

    def test_multiple_breaks(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)

        self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)
        self.client.post(reverse('attendance-end-break'), REMOTE_ADDR=self.office_ip)

        self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)
        self.client.post(reverse('attendance-end-break'), REMOTE_ADDR=self.office_ip)

        response = self.client.get(reverse('attendance-list'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(len(response.data[0]['breaks']), 2)

    def test_cannot_start_break_while_on_break(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_end_nonexistent_break(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(reverse('attendance-end-break'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_break_before_checkin(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_checkout_while_on_break(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(reverse('attendance-check-out'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_checkout_calculates_duration(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)

        att = Attendance.objects.get(employee=self.employee, date=timezone.now().date())
        att.check_in = timezone.now() - timedelta(hours=9)
        att.save()

        self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)
        b = att.breaks.first()
        b.started_at = timezone.now() - timedelta(hours=5)
        b.save()

        self.client.post(reverse('attendance-end-break'), REMOTE_ADDR=self.office_ip)
        b.refresh_from_db()
        b.ended_at = b.started_at + timedelta(minutes=45)
        b.save()

        response = self.client.post(reverse('attendance-check-out'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        att.refresh_from_db()
        # Roughly 9 hours elapsed, 45 minutes break => roughly 8h 15m productive.
        # Using almostEqual logic manually because of execution delay
        self.assertTrue(att.total_break_duration.total_seconds() == 45 * 60)
        self.assertTrue(att.productive_work_duration.total_seconds() > 8 * 3600)

    def test_repeated_end_break_requests(self):
        """Repeated or retried end-break requests cannot double-count or corrupt duration."""
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)

        # First request succeeds
        res1 = self.client.post(reverse('attendance-end-break'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        att = Attendance.objects.get(employee=self.employee, date=timezone.now().date())
        first_duration = att.total_break_duration

        # Second request (retry/double-click) returns 400 Bad Request safely
        res2 = self.client.post(reverse('attendance-end-break'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res2.data.get('detail'), 'No active break to end.')

        # Total break duration is verified unchanged
        att.refresh_from_db()
        self.assertEqual(att.total_break_duration, first_duration)

    def test_end_break_persists_total_break_duration_prior_to_checkout(self):
        """Verifies that ending a break persists total_break_duration before checkout occurs."""
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)

        att = Attendance.objects.get(employee=self.employee, date=timezone.now().date())
        b = att.breaks.first()
        b.started_at = timezone.now() - timedelta(minutes=25)
        b.save()

        res = self.client.post(reverse('attendance-end-break'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Verify serializer output
        self.assertFalse(res.data.get('is_on_break'))
        self.assertIsNone(res.data.get('current_break_started_at'))

        att.refresh_from_db()
        self.assertIsNotNone(att.total_break_duration)
        self.assertGreaterEqual(att.total_break_duration.total_seconds(), 24 * 60)

    def test_multiple_breaks_sum_correctly_without_double_counting(self):
        """Multiple completed breaks sum accurately and checkout preserves exact total."""
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)

        att = Attendance.objects.get(employee=self.employee, date=timezone.now().date())

        # Break 1: 15 minutes
        self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)
        b1 = att.breaks.first()
        b1.started_at = timezone.now() - timedelta(minutes=15)
        b1.save()
        self.client.post(reverse('attendance-end-break'), REMOTE_ADDR=self.office_ip)

        # Break 2: 20 minutes
        self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)
        b2 = att.breaks.order_by('-started_at').first()
        b2.started_at = timezone.now() - timedelta(minutes=20)
        b2.save()
        self.client.post(reverse('attendance-end-break'), REMOTE_ADDR=self.office_ip)

        att.refresh_from_db()
        # Sum of break 1 and 2 should be at least 35 minutes
        self.assertGreaterEqual(att.total_break_duration.total_seconds(), 34 * 60)

        # Check out should not double count
        res_out = self.client.post(reverse('attendance-check-out'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(res_out.status_code, status.HTTP_200_OK)

        att.refresh_from_db()
        self.assertGreaterEqual(att.total_break_duration.total_seconds(), 34 * 60)

    def test_admin_attendance_list_unauthenticated(self):
        response = self.client.get(reverse('attendance-management-list'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_attendance_list_unauthorized(self):
        # Authenticated, but no attendance.view_all permission
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('attendance-management-list'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_attendance_list_scoping(self):
        from apps.organization.models import Organization, Department, Designation, Branch
        from apps.employees.models import Employee
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Ensure self.employee belongs to self.org
        self.employee.organization = self.org
        self.employee.save()

        # Create second organization and employee
        org2 = Organization.objects.create(name='Org 2')
        branch2 = Branch.objects.create(organization=org2, name='Branch 2', radius=100)
        dept2 = Department.objects.create(branch=branch2, name='Dept 2')
        desig2 = Designation.objects.create(organization=org2, name='Desig 2')
        user2 = User.objects.create_user(email='user2@example.com', password='password123', first_name='User', last_name='Two')
        emp2 = Employee.objects.create(user=user2, organization=org2, department=dept2, designation=desig2, employee_code='EMP002')

        # Create attendance for both
        Attendance.objects.create(employee=self.employee, date=timezone.now().date(), status='present')
        Attendance.objects.create(employee=emp2, date=timezone.now().date(), status='present')

        # Super user should see all
        self.client.force_authenticate(user=self.super_user)
        response = self.client.get(reverse('attendance-management-list'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # Standard Admin (requires attendance.view_all)
        from apps.authorization.models import Role, Permission, RolePermission, UserRole
        role = Role.objects.create(name='Attendance Admin', organization=self.org)
        perm, _ = Permission.objects.get_or_create(codename='attendance.view_all', defaults={'name': 'View All Attendance', 'resource': 'attendance', 'action': 'view_all'})
        RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(user=self.user, role=role)

        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('attendance-management-list'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Must only see their own organization's records
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['employee'], self.employee.id)

    def test_attendance_serializer_no_leak(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.get(reverse('attendance-list'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Ensure employee_name and code are present but NO sensitive info (like salary, phone, address) is leaked
        data = response.data[0]
        self.assertIn('employee_name', data)
        self.assertIn('employee_code', data)
        self.assertNotIn('personal_email', data)
        self.assertNotIn('address', data)

    def test_concurrent_check_in_integrity_handled(self):
        self.client.force_authenticate(user=self.user)
        from unittest.mock import patch
        from django.db import IntegrityError
        # Simulate database throwing IntegrityError as in concurrent race
        with patch('apps.attendance.models.Attendance.objects.create', side_effect=IntegrityError("duplicate key")):
            response = self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data.get('detail'), 'Check-in already exists for today.')

    def test_check_out_productive_duration_non_negative(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(reverse('attendance-check-out'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        att = Attendance.objects.get(employee=self.employee, date=timezone.now().date())
        self.assertIsNotNone(att.productive_work_duration)
        self.assertGreaterEqual(att.productive_work_duration, timedelta(0))

    def test_branch_independent_holidays(self):
        from apps.attendance.models import Holiday
        from apps.organization.models import Branch
        from apps.authorization.models import Role, Permission, RolePermission, UserRole

        branch2 = Branch.objects.create(organization=self.org, name='Branch 2')
        Holiday.objects.create(branch=self.branch, name='HQ Holiday', date='2026-01-01')
        Holiday.objects.create(branch=branch2, name='Branch 2 Holiday', date='2026-01-02')

        role = Role.objects.create(name='Holiday Admin', organization=self.org)
        perm, _ = Permission.objects.get_or_create(codename='holiday.view', defaults={'name': 'View Holiday', 'resource': 'holiday', 'action': 'view'})
        RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(user=self.user, role=role, scope='branch', branch=self.branch)

        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('holiday-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should only see HQ Holiday
        names = [h['name'] for h in response.data]
        self.assertEqual(len(names), 1)
        self.assertIn('HQ Holiday', names)
        self.assertNotIn('Branch 2 Holiday', names)

    def test_start_break_with_valid_reason_lunch(self):
        """Valid reason 'lunch' persists authoritative server label and duration limit."""
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(
            reverse('attendance-start-break'),
            {'reason': 'lunch'},
            format='json',
            REMOTE_ADDR=self.office_ip
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_on_break'])
        brk = response.data['breaks'][0]
        self.assertEqual(brk['reason'], 'lunch')
        self.assertEqual(brk['reason_label'], 'Lunch')
        self.assertEqual(brk['counts_as_worked_time'], False)
        self.assertEqual(brk['duration_limit_minutes'], 40)

    def test_start_break_with_worked_time_reason(self):
        """Reason 'outside_meeting' sets counts_as_worked_time=True and duration_limit=None."""
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(
            reverse('attendance-start-break'),
            {'reason': 'outside_meeting'},
            format='json',
            REMOTE_ADDR=self.office_ip
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        brk = response.data['breaks'][0]
        self.assertEqual(brk['reason'], 'outside_meeting')
        self.assertEqual(brk['reason_label'], 'Outside meeting')
        self.assertEqual(brk['counts_as_worked_time'], True)
        self.assertIsNone(brk['duration_limit_minutes'])

    def test_start_break_forged_client_metadata_ignored(self):
        """Client-supplied label, limits, and counts_as_worked_time are ignored in favor of server definitions."""
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(
            reverse('attendance-start-break'),
            {
                'reason': 'lunch',
                'reason_label': 'Manipulated Label',
                'counts_as_worked_time': True,
                'duration_limit_minutes': 999
            },
            format='json',
            REMOTE_ADDR=self.office_ip
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        brk = response.data['breaks'][0]
        self.assertEqual(brk['reason'], 'lunch')
        self.assertEqual(brk['reason_label'], 'Lunch')
        self.assertEqual(brk['counts_as_worked_time'], False)
        self.assertEqual(brk['duration_limit_minutes'], 40)

    def test_start_break_invalid_reason_rejected(self):
        """Invalid break reason returns HTTP 400."""
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(
            reverse('attendance-start-break'),
            {'reason': 'power_nap'},
            format='json',
            REMOTE_ADDR=self.office_ip
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid break reason", response.data['detail'])

    def test_start_break_empty_reason_rejected(self):
        """Explicit empty reason returns HTTP 400."""
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(
            reverse('attendance-start-break'),
            {'reason': '   '},
            format='json',
            REMOTE_ADDR=self.office_ip
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'A break reason is required.')

    def test_start_break_other_comment_validation(self):
        """Reason 'other' strictly requires trimmed comment between 3 and 255 characters."""
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)

        # Missing comment
        r1 = self.client.post(reverse('attendance-start-break'), {'reason': 'other'}, format='json', REMOTE_ADDR=self.office_ip)
        self.assertEqual(r1.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('comment between 3 and 255', r1.data['detail'])

        # Comment too short
        r2 = self.client.post(reverse('attendance-start-break'), {'reason': 'other', 'comment': 'ab'}, format='json', REMOTE_ADDR=self.office_ip)
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)

        # Comment too long
        r3 = self.client.post(reverse('attendance-start-break'), {'reason': 'other', 'comment': 'x' * 256}, format='json', REMOTE_ADDR=self.office_ip)
        self.assertEqual(r3.status_code, status.HTTP_400_BAD_REQUEST)

        # Valid comment
        r4 = self.client.post(reverse('attendance-start-break'), {'reason': 'other', 'comment': 'Dentist appointment'}, format='json', REMOTE_ADDR=self.office_ip)
        self.assertEqual(r4.status_code, status.HTTP_200_OK)
        brk = r4.data['breaks'][0]
        self.assertEqual(brk['reason'], 'other')
        self.assertEqual(brk['comment'], 'Dentist appointment')
        self.assertEqual(brk['duration_limit_minutes'], 15)
        self.assertEqual(brk['counts_as_worked_time'], False)

    def test_start_break_legacy_unparameterized_compatibility(self):
        """Unparameterized start-break calls maintain backward compatibility with legacy endpoints."""
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(reverse('attendance-start-break'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_on_break'])
        brk = response.data['breaks'][0]
        self.assertIsNone(brk['reason'])
        self.assertIsNone(brk['reason_label'])

    def test_start_break_legacy_break_type_id_compatibility(self):
        """Legacy break_type_id payload creates break with break_type FK and metadata."""
        from apps.attendance.models import BreakType
        bt = BreakType.objects.create(organization=self.org, name='Custom Break', max_duration_minutes=25)
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(
            reverse('attendance-start-break'),
            {'break_type_id': bt.id},
            format='json',
            REMOTE_ADDR=self.office_ip
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        brk = response.data['breaks'][0]
        self.assertEqual(brk['break_type'], bt.id)
        self.assertEqual(brk['reason_label'], 'Custom Break')
        self.assertEqual(brk['duration_limit_minutes'], 25)

    def test_start_break_conflicting_other_org_break_type_rejected(self):
        """Specifying a break_type_id from a different organization is rejected."""
        from apps.organization.models import Organization
        from apps.attendance.models import BreakType
        org2 = Organization.objects.create(name='Foreign Org')
        bt_foreign = BreakType.objects.create(organization=org2, name='Foreign Break', max_duration_minutes=15)
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(
            reverse('attendance-start-break'),
            {'reason': 'lunch', 'break_type_id': bt_foreign.id},
            format='json',
            REMOTE_ADDR=self.office_ip
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Selected break type is unavailable.')
