from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date, timedelta
from decimal import Decimal
from apps.organization.models import Organization, Department, Designation, OfficeNetwork
from apps.employees.models import Employee, EmploymentStatus
from apps.authorization.models import Role, Permission, RolePermission, UserRole
from apps.payroll.models import PayrollPeriod, PayrollRecord, Payslip
from apps.payroll.services import issue_payslips_for_period

User = get_user_model()


class PayrollSecurityAndCorrectnessTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.org = Organization.objects.create(name='Payroll Org')
        OfficeNetwork.objects.create(organization=self.org, name='Office', network='127.0.0.1/32', is_active=True)

        self.dept = Department.objects.create(organization=self.org, name='Engineering')
        self.desig = Designation.objects.create(organization=self.org, name='Staff Architect')

        # Admin user with payroll permissions
        self.admin_user = User.objects.create_user(email='payroll_admin@example.com', password='Password123!', status='active')
        self.admin_emp = Employee.objects.create(
            user=self.admin_user,
            organization=self.org,
            department=self.dept,
            designation=self.desig,
            employee_code='EMP-PAY-001',
            employment_status=EmploymentStatus.ACTIVE
        )

        role = Role.objects.create(organization=self.org, name='Payroll Manager')
        perms = ['payroll.view', 'payroll.approve', 'payroll.view_sensitive', 'payslip.view']
        for codename in perms:
            res, act = codename.split('.', 1)
            p, _ = Permission.objects.get_or_create(
                codename=codename,
                defaults={'name': codename, 'resource': res, 'action': act}
            )
            RolePermission.objects.create(role=role, permission=p)
        UserRole.objects.create(user=self.admin_user, role=role)

        # Standard employee
        self.emp_user = User.objects.create_user(email='employee@example.com', password='Password123!', status='active')
        self.emp = Employee.objects.create(
            user=self.emp_user,
            organization=self.org,
            department=self.dept,
            designation=self.desig,
            employee_code='EMP-PAY-002',
            employment_status=EmploymentStatus.ACTIVE
        )

    def test_cannot_approve_future_period(self):
        """Verify that a payroll period ending in the future cannot be approved."""
        future_start = date.today() + timedelta(days=1)
        future_end = date.today() + timedelta(days=20)
        period = PayrollPeriod.objects.create(
            organization=self.org,
            year=future_start.year,
            month=future_start.month,
            start_date=future_start,
            end_date=future_end,
            status=PayrollPeriod.STATUS_DRAFT
        )
        PayrollRecord.objects.create(
            period=period,
            employee=self.emp,
            working_days=20,
            present_days=20,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal('20.0'),
            basic_salary=Decimal('50000.00'),
            gross_salary=Decimal('50000.00'),
            net_salary=Decimal('50000.00'),
            status=PayrollRecord.STATUS_DRAFT
        )

        self.client.force_authenticate(user=self.admin_user)
        resp = self.client.post(f'/api/v1/payroll/periods/{period.id}/approve/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot approve an ongoing or future payroll period', resp.data['detail'])

    def test_cannot_approve_ongoing_period(self):
        """Verify that an ongoing period ending today cannot be approved."""
        ongoing_start = date.today() - timedelta(days=14)
        ongoing_end = date.today()
        period = PayrollPeriod.objects.create(
            organization=self.org,
            year=ongoing_start.year,
            month=ongoing_start.month,
            start_date=ongoing_start,
            end_date=ongoing_end,
            status=PayrollPeriod.STATUS_DRAFT
        )
        PayrollRecord.objects.create(
            period=period,
            employee=self.emp,
            working_days=10,
            present_days=10,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal('10.0'),
            basic_salary=Decimal('50000.00'),
            gross_salary=Decimal('50000.00'),
            net_salary=Decimal('50000.00'),
            status=PayrollRecord.STATUS_DRAFT
        )

        self.client.force_authenticate(user=self.admin_user)
        resp = self.client.post(f'/api/v1/payroll/periods/{period.id}/approve/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot approve an ongoing or future payroll period', resp.data['detail'])

    def test_completed_period_approval_and_repeated_approval(self):
        """Verify that a completed period can be approved, and repeating approval is rejected."""
        completed_start = date.today() - timedelta(days=40)
        completed_end = date.today() - timedelta(days=10)
        period = PayrollPeriod.objects.create(
            organization=self.org,
            year=completed_start.year,
            month=completed_start.month,
            start_date=completed_start,
            end_date=completed_end,
            status=PayrollPeriod.STATUS_DRAFT
        )
        PayrollRecord.objects.create(
            period=period,
            employee=self.emp,
            working_days=20,
            present_days=20,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal('20.0'),
            basic_salary=Decimal('50000.00'),
            gross_salary=Decimal('50000.00'),
            net_salary=Decimal('50000.00'),
            status=PayrollRecord.STATUS_DRAFT
        )

        self.client.force_authenticate(user=self.admin_user)
        # 1. Initial approval of completed period succeeds
        resp = self.client.post(f'/api/v1/payroll/periods/{period.id}/approve/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'approved')
        period.refresh_from_db()
        self.assertEqual(period.status, PayrollPeriod.STATUS_APPROVED)

        # 2. Repeated approval is rejected
        repeat_resp = self.client.post(f'/api/v1/payroll/periods/{period.id}/approve/')
        self.assertEqual(repeat_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already approved', repeat_resp.data['detail'])

    def test_payslip_detail_with_designation_does_not_crash(self):
        """Verify that retrieving PayslipDetail for an employee with a designation returns designation.name cleanly."""
        past_start = date(2024, 1, 1)
        past_end = date(2024, 1, 31)
        period = PayrollPeriod.objects.create(
            organization=self.org,
            year=2024,
            month=1,
            start_date=past_start,
            end_date=past_end,
            status=PayrollPeriod.STATUS_APPROVED
        )
        record = PayrollRecord.objects.create(
            period=period,
            employee=self.emp,
            working_days=22,
            present_days=22,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal('22.0'),
            basic_salary=Decimal('80000.00'),
            gross_salary=Decimal('80000.00'),
            net_salary=Decimal('80000.00'),
            status=PayrollRecord.STATUS_APPROVED
        )
        payslips = issue_payslips_for_period(period)
        self.assertEqual(len(payslips), 1)
        payslip = payslips[0]

        self.client.force_authenticate(user=self.admin_user)
        resp = self.client.get(f'/api/v1/payroll/payslips/{payslip.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['employee']['designation'], 'Staff Architect')
        self.assertEqual(resp.data['employee']['department'], 'Engineering')
