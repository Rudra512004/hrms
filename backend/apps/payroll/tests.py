from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from unittest.mock import patch

from apps.employees.models import Employee, EmploymentStatus
from apps.organization.models import Organization
from apps.attendance.models import Attendance, Holiday
from apps.leaves.models import LeaveType, LeaveBalance, LeaveRequest

from .models import CompensationHistory, PayrollPeriod, PayrollRecord
from .services import (
    generate_payroll_for_period,
    _working_days_in_period,
    _approved_leave_days,
)

User = get_user_model()


class WorkingDaysTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='WD Org')

    def test_excludes_weekends(self):
        # 2024-09-02 (Mon) to 2024-09-08 (Sun) → 5 working days
        days = _working_days_in_period(self.org.id, date(2024, 9, 2), date(2024, 9, 8))
        self.assertEqual(days, 5)

    def test_excludes_holidays(self):
        Holiday.objects.create(organization=self.org, name='Test Holiday', date=date(2024, 9, 2), is_active=True)
        days = _working_days_in_period(self.org.id, date(2024, 9, 2), date(2024, 9, 6))
        self.assertEqual(days, 4)  # 5 weekdays − 1 holiday

    def test_inactive_holiday_not_excluded(self):
        Holiday.objects.create(organization=self.org, name='Inactive', date=date(2024, 9, 2), is_active=False)
        days = _working_days_in_period(self.org.id, date(2024, 9, 2), date(2024, 9, 6))
        self.assertEqual(days, 5)


class CompensationHistoryTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Comp Org')
        self.user = User.objects.create_user(email='emp@comp.com', password='Pass123!', status='active')
        self.emp = Employee.objects.create(user=self.user, employee_code='CE01', organization=self.org)

    def test_basic_salary_is_decimal(self):
        record = CompensationHistory.objects.create(
            employee=self.emp,
            effective_from=date(2024, 1, 1),
            basic_salary=Decimal('50000.00'),
        )
        self.assertIsInstance(record.basic_salary, Decimal)

    def test_negative_salary_rejected(self):
        record = CompensationHistory(
            employee=self.emp,
            effective_from=date(2024, 1, 1),
            basic_salary=Decimal('-1.00'),
        )
        from django.core.exceptions import ValidationError
        with self.assertRaises(Exception):
            record.full_clean()


class PayrollGenerationTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Gen Org')
        self.user = User.objects.create_user(email='emp@gen.com', password='Pass123!', status='active')
        self.emp = Employee.objects.create(
            user=self.user, employee_code='GE01',
            organization=self.org,
            employment_status=EmploymentStatus.ACTIVE,
        )
        CompensationHistory.objects.create(
            employee=self.emp,
            effective_from=date(2024, 9, 1),
            basic_salary=Decimal('30000.00'),
        )
        self.period = PayrollPeriod.objects.create(
            organization=self.org,
            year=2024, month=9,
            start_date=date(2024, 9, 1),
            end_date=date(2024, 9, 30),
        )

    def test_generates_one_record_per_active_employee(self):
        generate_payroll_for_period(self.period)
        self.assertEqual(PayrollRecord.objects.filter(period=self.period).count(), 1)

    def test_salary_snapshot_is_correct(self):
        generate_payroll_for_period(self.period)
        record = PayrollRecord.objects.get(period=self.period, employee=self.emp)
        self.assertEqual(record.basic_salary, Decimal('30000.00'))

    def test_gross_uses_decimal_arithmetic(self):
        # Mark 10 present days
        for d in range(2, 12):
            Attendance.objects.create(employee=self.emp, date=date(2024, 9, d), status='present')
        generate_payroll_for_period(self.period)
        record = PayrollRecord.objects.get(period=self.period, employee=self.emp)
        working_days = _working_days_in_period(self.org.id, date(2024, 9, 1), date(2024, 9, 30))
        expected = (Decimal('30000.00') * Decimal(10) / Decimal(working_days)).quantize(Decimal('0.01'))
        self.assertEqual(record.gross_salary, expected)

    def test_approved_period_cannot_be_regenerated(self):
        generate_payroll_for_period(self.period)
        self.period.status = PayrollPeriod.STATUS_APPROVED
        self.period.save()
        with self.assertRaises(ValueError):
            generate_payroll_for_period(self.period)

    def test_inactive_employee_excluded(self):
        user2 = User.objects.create_user(email='emp2@gen.com', password='Pass123!', status='active')
        emp2 = Employee.objects.create(
            user=user2, employee_code='GE02',
            organization=self.org,
            employment_status=EmploymentStatus.INACTIVE,
        )
        CompensationHistory.objects.create(
            employee=emp2, effective_from=date(2024, 9, 1), basic_salary=Decimal('20000.00')
        )
        generate_payroll_for_period(self.period)
        self.assertFalse(PayrollRecord.objects.filter(period=self.period, employee=emp2).exists())


class ApprovedLeaveInPayrollTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Leave Org')
        self.user = User.objects.create_user(email='lemp@lo.com', password='Pass123!', status='active')
        self.emp = Employee.objects.create(
            user=self.user, employee_code='LE01',
            organization=self.org,
            employment_status=EmploymentStatus.ACTIVE,
        )
        self.leave_type = LeaveType.objects.create(
            organization=self.org, name='Annual', annual_allocation=20
        )

    def test_approved_leave_counted_in_period(self):
        # Monday to Friday (5 days)
        LeaveRequest.objects.create(
            employee=self.emp,
            leave_type=self.leave_type,
            start_date=date(2024, 9, 2),
            end_date=date(2024, 9, 6),
            status='approved',
        )
        leave_days = _approved_leave_days(self.emp, date(2024, 9, 1), date(2024, 9, 30))
        self.assertEqual(leave_days, 5)

    def test_rejected_leave_not_counted(self):
        LeaveRequest.objects.create(
            employee=self.emp,
            leave_type=self.leave_type,
            start_date=date(2024, 9, 2),
            end_date=date(2024, 9, 6),
            status='rejected',
        )
        leave_days = _approved_leave_days(self.emp, date(2024, 9, 1), date(2024, 9, 30))
        self.assertEqual(leave_days, 0)


class PayrollAPIPermissionTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='API Org')
        self.user = User.objects.create_user(email='api@org.com', password='Pass123!', status='active')
        self.emp = Employee.objects.create(
            user=self.user,
            employee_code='AP01',
            organization=self.org,
            employment_status=EmploymentStatus.ACTIVE,
        )

    def test_unauthenticated_returns_401(self):
        resp = self.client.get('/api/v1/payroll/periods/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_permission_returns_403(self):
        self.client.force_authenticate(user=self.user)
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=False):
            resp = self.client.get('/api/v1/payroll/periods/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_org_period_not_visible(self):
        org2 = Organization.objects.create(name='Other Org')
        period = PayrollPeriod.objects.create(
            organization=org2, year=2024, month=9,
            start_date=date(2024, 9, 1), end_date=date(2024, 9, 30),
        )
        self.client.force_authenticate(user=self.user)
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            resp = self.client.get('/api/v1/payroll/periods/')
        ids = [p['id'] for p in resp.data]
        self.assertNotIn(period.id, ids)

    def test_duplicate_period_rejected(self):
        PayrollPeriod.objects.create(
            organization=self.org, year=2024, month=9,
            start_date=date(2024, 9, 1), end_date=date(2024, 9, 30),
        )
        self.client.force_authenticate(user=self.user)
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            resp = self.client.post('/api/v1/payroll/periods/', {
                'year': 2024, 'month': 9,
                'start_date': '2024-09-01', 'end_date': '2024-09-30',
            })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sensitive_fields_hidden_without_permission(self):
        period = PayrollPeriod.objects.create(
            organization=self.org, year=2024, month=8,
            start_date=date(2024, 8, 1), end_date=date(2024, 8, 31),
        )
        CompensationHistory.objects.create(
            employee=self.emp, effective_from=date(2024, 8, 1), basic_salary=Decimal('40000.00')
        )
        generate_payroll_for_period(period)
        record = PayrollRecord.objects.get(period=period, employee=self.emp)
        self.client.force_authenticate(user=self.user)
        with patch('apps.authorization.services.AuthorizationService.has_permission', side_effect=lambda u, p: p == 'payroll.view'):
            resp = self.client.get(f'/api/v1/payroll/records/{record.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn('basic_salary', resp.data)
        self.assertNotIn('gross_salary', resp.data)
        self.assertNotIn('net_salary', resp.data)
