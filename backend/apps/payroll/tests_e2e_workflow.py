"""
Day 14: Complete End-to-End Workflow Acceptance Test Suite.
Traces:
Organization -> Branch -> Department -> Shift -> Employee -> Attendance ->
Leave -> Compensation -> Payroll Period -> Payroll Generation ->
Payroll Approval -> Payslip Issuance -> HR Reporting & Reconciliation.
"""
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.organization.models import Organization, Department, Branch
from apps.attendance.models import Shift, Holiday, Attendance
from apps.employees.models import Employee, EmploymentStatus
from apps.leaves.models import LeaveType, LeaveBalance, LeaveRequest
from apps.payroll.models import CompensationHistory, PayrollPeriod, PayrollRecord, Payslip
from apps.payroll.services import (
    generate_payroll_for_period,
    issue_payslips_for_period,
    _working_days_in_period,
    _approved_leave_days,
)

User = get_user_model()


class EndToEndHRMSWorkflowTests(TestCase):
    """
    Acceptance tests for the full HRMS pipeline and critical edge cases.
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Organization Setup
        self.org = Organization.objects.create(name='Acme Corp')
        self.org_other = Organization.objects.create(name='Competitor Ltd')

        # 2. Branch Setup
        self.branch = Branch.objects.create(
            organization=self.org,
            name='Bangalore HQ',
            address='123 Tech Park',
            latitude=12.9716,
            longitude=77.5946,
            radius=500.0,
            is_active=True,
        )

        # 3. Department Setup
        self.dept = Department.objects.create(
            organization=self.org,
            name='Engineering',
        )

        # 4. Shift Setup
        self.shift = Shift.objects.create(
            organization=self.org,
            name='General Shift',
            start_time='09:00:00',
            end_time='18:00:00',
            grace_period=timedelta(minutes=15),
            is_active=True,
        )

        # 5. Holiday Setup (e.g. New Year's Day)
        self.holiday = Holiday.objects.create(
            organization=self.org,
            name="New Year's Day",
            date=date(2025, 1, 1),
            is_active=True,
        )

        # 6. Leave Type Setup
        self.leave_type = LeaveType.objects.create(
            organization=self.org,
            name='Annual Leave',
            annual_allocation=12,
            is_active=True,
        )

        # 7. Employee 1: Primary active lifecycle subject
        self.user1 = User.objects.create_user(
            email='john.doe@acme.com',
            password='Password123!',
            first_name='John',
            last_name='Doe',
            status='active',
        )
        self.emp1 = Employee.objects.create(
            user=self.user1,
            employee_code='EMP001',
            organization=self.org,
            branch=self.branch,
            department=self.dept,
            employment_status=EmploymentStatus.ACTIVE,
            joining_date=date(2024, 1, 1),
        )

        # 8. HR / Admin User with RBAC capabilities
        self.hr_user = User.objects.create_user(
            email='hr.admin@acme.com',
            password='Password123!',
            first_name='Helen',
            last_name='Admin',
            status='active',
        )
        self.hr_emp = Employee.objects.create(
            user=self.hr_user,
            employee_code='HR001',
            organization=self.org,
            branch=self.branch,
            department=self.dept,
            employment_status=EmploymentStatus.ACTIVE,
        )

        # 9. Cross-organization User & Employee
        self.other_user = User.objects.create_user(
            email='foreign@other.com',
            password='Password123!',
            status='active',
        )
        self.other_emp = Employee.objects.create(
            user=self.other_user,
            employee_code='FOR001',
            organization=self.org_other,
            employment_status=EmploymentStatus.ACTIVE,
        )

    def _auth_as(self, user, permissions=None):
        self.client.force_authenticate(user=user)
        perms = set(permissions or [])
        return patch(
            'apps.authorization.services.AuthorizationService.has_permission',
            side_effect=lambda u, p: (p in perms) if u == user else False
        )

    # ─── Full Lifecycle Test ──────────────────────────────────────────────────

    def test_full_employee_to_payslip_and_report_lifecycle(self):
        """
        Traces one complete employee lifecycle:
        Attendance + Leave + Compensation -> Payroll Period -> Draft Generation ->
        Approval -> Payslip Issuance -> Self-Service Retrieve -> Executive Report.
        """
        # Step A: Compensation exists for Jan 2025
        CompensationHistory.objects.create(
            employee=self.emp1,
            effective_from=date(2025, 1, 1),
            basic_salary=Decimal('60000.00'),
        )

        # Step B: Record valid attendance (Mon Jan 6 - Fri Jan 10 = 5 present days)
        for d in range(6, 11):
            Attendance.objects.create(
                employee=self.emp1,
                date=date(2025, 1, d),
                check_in=timezone.now(),
                check_out=timezone.now() + timedelta(hours=8),
                status='present',
            )

        # Step C: Submit and approve Leave for Mon Jan 13 - Tue Jan 14 (2 days)
        leave = LeaveRequest.objects.create(
            employee=self.emp1,
            leave_type=self.leave_type,
            start_date=date(2025, 1, 13),
            end_date=date(2025, 1, 14),
            reason='Personal reasons',
            status='pending',
        )
        # HR approves leave
        with self._auth_as(self.hr_user, permissions=['leave.approve', 'leave.view']):
            resp = self.client.post(reverse('leave-requests-approve', kwargs={'pk': leave.id}), {
                'reviewer_comment': 'Approved by HR'
            })
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
        leave.refresh_from_db()
        self.assertEqual(leave.status, 'approved')

        # Balance deducted
        balance = LeaveBalance.objects.get(employee=self.emp1, leave_type=self.leave_type)
        self.assertEqual(balance.used, 2)
        self.assertEqual(balance.remaining, 10)

        # Step D: HR creates Payroll Period for Jan 2025
        with self._auth_as(self.hr_user, permissions=['payroll.view', 'payroll.generate']):
            resp = self.client.post('/api/v1/payroll/periods/', {
                'year': 2025,
                'month': 1,
                'start_date': '2025-01-01',
                'end_date': '2025-01-31',
            })
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
            period_id = resp.data['id']

        period = PayrollPeriod.objects.get(id=period_id)

        # Step E: HR Generates Draft Payroll
        with self._auth_as(self.hr_user, permissions=['payroll.view', 'payroll.generate']):
            resp = self.client.post(f'/api/v1/payroll/periods/{period_id}/generate/')
            self.assertEqual(resp.status_code, status.HTTP_200_OK)

        record = PayrollRecord.objects.get(period=period, employee=self.emp1)
        self.assertEqual(record.status, PayrollRecord.STATUS_DRAFT)
        self.assertEqual(record.present_days, 5)
        self.assertEqual(record.leave_days, 2)
        self.assertEqual(record.half_days, 0)
        self.assertEqual(record.effective_days, Decimal('7.00'))

        # Jan 2025 working days: 23 weekdays - 1 holiday (Jan 1) = 22 working days
        working_days = _working_days_in_period(self.org.id, date(2025, 1, 1), date(2025, 1, 31))
        self.assertEqual(working_days, 22)
        self.assertEqual(record.working_days, 22)
        self.assertEqual(record.absent_days, 15)  # 22 - 7 = 15

        # Expected gross = (60000 * 7 / 22) = 19090.91
        expected_gross = (Decimal('60000.00') * Decimal('7') / Decimal('22')).quantize(Decimal('0.01'))
        self.assertEqual(record.gross_salary, expected_gross)
        self.assertEqual(record.net_salary, expected_gross)

        # Step F: HR Approves Payroll Period
        with self._auth_as(self.hr_user, permissions=['payroll.view', 'payroll.approve']):
            resp = self.client.post(f'/api/v1/payroll/periods/{period_id}/approve/')
            self.assertEqual(resp.status_code, status.HTTP_200_OK)

        period.refresh_from_db()
        record.refresh_from_db()
        self.assertEqual(period.status, PayrollPeriod.STATUS_APPROVED)
        self.assertEqual(record.status, PayrollRecord.STATUS_APPROVED)

        # Step G: Exactly one Payslip auto-issued
        self.assertEqual(Payslip.objects.filter(payroll_record=record).count(), 1)
        payslip = Payslip.objects.get(payroll_record=record)
        self.assertEqual(payslip.payslip_number, 'PAY-202501-EMP001')
        self.assertEqual(payslip.status, Payslip.STATUS_ISSUED)

        # Step H: Employee views own payslip (/my/)
        with self._auth_as(self.user1):
            resp = self.client.get('/api/v1/payroll/payslips/my/')
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            self.assertEqual(len(resp.data), 1)
            self.assertEqual(resp.data[0]['payslip_number'], 'PAY-202501-EMP001')
            self.assertEqual(resp.data[0]['net_salary'], str(expected_gross))

        # Step I: HR views period summary & reconciliation reports
        with self._auth_as(self.hr_user, permissions=['payroll.view_reports', 'payroll.view_sensitive']):
            resp_summary = self.client.get(f'/api/v1/payroll/reports/period-summary/?period={period_id}')
            self.assertEqual(resp_summary.status_code, status.HTTP_200_OK)
            self.assertEqual(resp_summary.data['summary']['total_employees'], 2)  # emp1 + hr_emp

            resp_recon = self.client.get(f'/api/v1/payroll/reports/reconciliation/?period={period_id}&search=EMP001')
            self.assertEqual(resp_recon.status_code, status.HTTP_200_OK)
            self.assertEqual(resp_recon.data['count'], 1)
            self.assertEqual(resp_recon.data['records'][0]['employee_code'], 'EMP001')
            self.assertEqual(Decimal(resp_recon.data['records'][0]['effective_days']), Decimal('7.0'))

    # ─── Edge Case Tests ──────────────────────────────────────────────────────

    def test_edge_case_employee_with_no_compensation(self):
        """Active employee without compensation gets 0 basic salary and is flagged in exceptions."""
        period = PayrollPeriod.objects.create(
            organization=self.org, year=2025, month=2,
            start_date=date(2025, 2, 1), end_date=date(2025, 2, 28)
        )
        generate_payroll_for_period(period)
        record = PayrollRecord.objects.get(period=period, employee=self.emp1)
        self.assertEqual(record.basic_salary, Decimal('0.00'))
        self.assertEqual(record.gross_salary, Decimal('0.00'))

        # Exception detector identifies MISSING_COMPENSATION
        with self._auth_as(self.hr_user, permissions=['payroll.view_reports']):
            resp = self.client.get(f'/api/v1/payroll/reports/exceptions/?period={period.id}')
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            ex_types = [e['type'] for e in resp.data['exceptions'] if e['employee_id'] == self.emp1.id]
            self.assertIn('MISSING_COMPENSATION', ex_types)

    def test_edge_case_employee_with_no_attendance_is_full_absence(self):
        """Employee with 0 attendance/leave has effective_days == 0 and is flagged as FULL_ABSENCE."""
        CompensationHistory.objects.create(
            employee=self.emp1, effective_from=date(2025, 3, 1), basic_salary=Decimal('50000.00')
        )
        period = PayrollPeriod.objects.create(
            organization=self.org, year=2025, month=3,
            start_date=date(2025, 3, 1), end_date=date(2025, 3, 31)
        )
        generate_payroll_for_period(period)
        record = PayrollRecord.objects.get(period=period, employee=self.emp1)
        self.assertEqual(record.effective_days, Decimal('0.00'))
        self.assertEqual(record.gross_salary, Decimal('0.00'))

        with self._auth_as(self.hr_user, permissions=['payroll.view_reports']):
            resp = self.client.get(f'/api/v1/payroll/reports/exceptions/?period={period.id}')
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            ex_types = [e['type'] for e in resp.data['exceptions'] if e['employee_id'] == self.emp1.id]
            self.assertIn('FULL_ABSENCE', ex_types)

    def test_edge_case_pending_leave_not_counted_and_flagged_in_exceptions(self):
        """Pending leaves are NOT counted as paid days, and are detected by exceptions endpoint."""
        LeaveRequest.objects.create(
            employee=self.emp1,
            leave_type=self.leave_type,
            start_date=date(2025, 4, 7),
            end_date=date(2025, 4, 11),
            status='pending',
        )
        period = PayrollPeriod.objects.create(
            organization=self.org, year=2025, month=4,
            start_date=date(2025, 4, 1), end_date=date(2025, 4, 30)
        )
        generate_payroll_for_period(period)
        record = PayrollRecord.objects.get(period=period, employee=self.emp1)
        self.assertEqual(record.leave_days, 0)

        with self._auth_as(self.hr_user, permissions=['payroll.view_reports']):
            resp = self.client.get(f'/api/v1/payroll/reports/exceptions/?period={period.id}')
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            ex_types = [e['type'] for e in resp.data['exceptions'] if e['employee_id'] == self.emp1.id]
            self.assertIn('PENDING_LEAVE', ex_types)

    def test_edge_case_missing_clock_out_flagged_in_exceptions(self):
        """Attendance check-in without check-out is flagged as ATTENDANCE_INCOMPLETE."""
        Attendance.objects.create(
            employee=self.emp1,
            date=date(2025, 5, 5),
            check_in=timezone.now(),
            check_out=None,
            status='present',
        )
        period = PayrollPeriod.objects.create(
            organization=self.org, year=2025, month=5,
            start_date=date(2025, 5, 1), end_date=date(2025, 5, 31)
        )
        generate_payroll_for_period(period)

        with self._auth_as(self.hr_user, permissions=['payroll.view_reports']):
            resp = self.client.get(f'/api/v1/payroll/reports/exceptions/?period={period.id}')
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            ex_types = [e['type'] for e in resp.data['exceptions'] if e['employee_id'] == self.emp1.id]
            self.assertIn('ATTENDANCE_INCOMPLETE', ex_types)

    def test_edge_case_cross_org_period_access_rejected_with_404(self):
        """Cross-org period IDs are completely invisible (404), preventing IDOR."""
        period_org2 = PayrollPeriod.objects.create(
            organization=self.org_other, year=2025, month=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
        with self._auth_as(self.hr_user, permissions=['payroll.view_reports']):
            resp = self.client.get(f'/api/v1/payroll/reports/period-summary/?period={period_org2.id}')
            self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_edge_case_user_with_payroll_view_only_denied_reports_with_403(self):
        """Users with only operational payroll.view cannot access executive reporting endpoints."""
        period = PayrollPeriod.objects.create(
            organization=self.org, year=2025, month=6,
            start_date=date(2025, 6, 1), end_date=date(2025, 6, 30)
        )
        with self._auth_as(self.hr_user, permissions=['payroll.view']):
            resp = self.client.get(f'/api/v1/payroll/reports/period-summary/?period={period.id}')
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_edge_case_user_without_payroll_view_sensitive_has_masked_salaries(self):
        """Users with payroll.view_reports but without payroll.view_sensitive receive null salary metrics."""
        CompensationHistory.objects.create(
            employee=self.emp1, effective_from=date(2025, 7, 1), basic_salary=Decimal('75000.00')
        )
        period = PayrollPeriod.objects.create(
            organization=self.org, year=2025, month=7,
            start_date=date(2025, 7, 1), end_date=date(2025, 7, 31)
        )
        generate_payroll_for_period(period)

        with self._auth_as(self.hr_user, permissions=['payroll.view_reports']):
            resp = self.client.get(f'/api/v1/payroll/reports/period-summary/?period={period.id}')
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            self.assertIsNone(resp.data['summary']['total_net_salary'])
            self.assertIsNone(resp.data['summary']['total_basic_salary'])

            resp_recon = self.client.get(f'/api/v1/payroll/reports/reconciliation/?period={period.id}')
            self.assertEqual(resp_recon.status_code, status.HTTP_200_OK)
            self.assertIsNone(resp_recon.data['records'][0]['net_salary'])
            self.assertIsNone(resp_recon.data['records'][0]['basic_salary'])
