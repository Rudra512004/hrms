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

from .models import CompensationHistory, PayrollPeriod, PayrollRecord, Payslip

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


class PayslipSecurityAndSelfServiceTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org1 = Organization.objects.create(name='Org 1')
        self.org2 = Organization.objects.create(name='Org 2')

        # Employee 1 in Org 1
        self.user1 = User.objects.create_user(
            email='emp1@org1.com', password='Pass123!', first_name='Alice', last_name='Smith', status='active'
        )
        self.emp1 = Employee.objects.create(
            user=self.user1, employee_code='E001', organization=self.org1, employment_status=EmploymentStatus.ACTIVE
        )
        CompensationHistory.objects.create(
            employee=self.emp1, effective_from=date(2024, 7, 1), basic_salary=Decimal('60000.00')
        )

        # Employee 2 in Org 1
        self.user2 = User.objects.create_user(
            email='emp2@org1.com', password='Pass123!', first_name='Bob', last_name='Jones', status='active'
        )
        self.emp2 = Employee.objects.create(
            user=self.user2, employee_code='E002', organization=self.org1, employment_status=EmploymentStatus.ACTIVE
        )
        CompensationHistory.objects.create(
            employee=self.emp2, effective_from=date(2024, 7, 1), basic_salary=Decimal('45000.00')
        )

        # Employee 3 in Org 2
        self.user3 = User.objects.create_user(
            email='emp3@org2.com', password='Pass123!', first_name='Charlie', last_name='Brown', status='active'
        )
        self.emp3 = Employee.objects.create(
            user=self.user3, employee_code='E003', organization=self.org2, employment_status=EmploymentStatus.ACTIVE
        )
        CompensationHistory.objects.create(
            employee=self.emp3, effective_from=date(2024, 7, 1), basic_salary=Decimal('50000.00')
        )

        # Period in Org 1
        self.period1 = PayrollPeriod.objects.create(
            organization=self.org1,
            year=2024,
            month=7,
            start_date=date(2024, 7, 1),
            end_date=date(2024, 7, 31),
        )
        generate_payroll_for_period(self.period1)

    def _approve_period(self, period, user):
        self.client.force_authenticate(user=user)
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            resp = self.client.post(f'/api/v1/payroll/periods/{period.id}/approve/')
        return resp

    def test_payslip_automatically_created_after_approval(self):
        resp = self._approve_period(self.period1, self.user1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Period has 2 active employees, so 2 payslips should exist
        payslips = Payslip.objects.filter(payroll_record__period=self.period1)
        self.assertEqual(payslips.count(), 2)
        for ps in payslips:
            self.assertEqual(ps.status, Payslip.STATUS_ISSUED)
            self.assertTrue(ps.payslip_number.startswith('PAY-202407-'))

    def test_exactly_one_payslip_per_payroll_record(self):
        self._approve_period(self.period1, self.user1)
        for record in self.period1.records.all():
            self.assertTrue(hasattr(record, 'payslip'))
            self.assertIsNotNone(record.payslip.payslip_number)

    def test_duplicate_approval_cannot_create_duplicates(self):
        self._approve_period(self.period1, self.user1)
        initial_count = Payslip.objects.count()

        # Second approval attempt should fail with 400
        resp2 = self._approve_period(self.period1, self.user1)
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payslip.objects.count(), initial_count)

    def test_draft_payroll_has_no_employee_visible_payslip(self):
        # Period 1 is in draft. Payslip count is 0.
        self.assertEqual(Payslip.objects.filter(payroll_record__period=self.period1).count(), 0)
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get('/api/v1/payroll/payslips/my/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_employee_can_list_only_their_own_payslips(self):
        self._approve_period(self.period1, self.user1)
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get('/api/v1/payroll/payslips/my/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['employee_code'], 'E001')

    def test_employee_can_retrieve_their_own_finalized_payslip(self):
        self._approve_period(self.period1, self.user1)
        ps1 = Payslip.objects.get(payroll_record__employee=self.emp1)
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get(f'/api/v1/payroll/payslips/{ps1.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['payslip_number'], ps1.payslip_number)
        self.assertEqual(resp.data['employee']['code'], 'E001')
        self.assertEqual(resp.data['employee']['name'], 'Alice Smith')
        # Owner receives their own salary breakdown
        self.assertIsNotNone(resp.data['financials']['net_salary'])
        self.assertEqual(resp.data['financials']['basic_salary'], '60000.00')

    def test_employee_a_cannot_retrieve_employee_b_payslip(self):
        self._approve_period(self.period1, self.user1)
        ps2 = Payslip.objects.get(payroll_record__employee=self.emp2)
        # Employee 1 tries to access Employee 2's payslip -> 404 (IDOR blocked)
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get(f'/api/v1/payroll/payslips/{ps2.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_organization_access_is_blocked(self):
        self._approve_period(self.period1, self.user1)
        ps1 = Payslip.objects.get(payroll_record__employee=self.emp1)
        # Employee 3 in Org 2 tries to access ps1 in Org 1 -> 404
        self.client.force_authenticate(user=self.user3)
        resp = self.client.get(f'/api/v1/payroll/payslips/{ps1.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_salary_values_match_approved_payroll_record_exactly(self):
        self._approve_period(self.period1, self.user1)
        ps1 = Payslip.objects.get(payroll_record__employee=self.emp1)
        rec = ps1.payroll_record
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get(f'/api/v1/payroll/payslips/{ps1.id}/')
        self.assertEqual(Decimal(resp.data['financials']['basic_salary']), rec.basic_salary)
        self.assertEqual(Decimal(resp.data['financials']['gross_salary']), rec.gross_salary)
        self.assertEqual(Decimal(resp.data['financials']['net_salary']), rec.net_salary)

    def test_payslip_cannot_be_modified_through_api(self):
        self._approve_period(self.period1, self.user1)
        ps1 = Payslip.objects.get(payroll_record__employee=self.emp1)
        self.client.force_authenticate(user=self.user1)
        # POST to /payslips/ -> 405
        post_resp = self.client.post('/api/v1/payroll/payslips/', {'status': 'revoked'})
        self.assertEqual(post_resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        # PUT to /payslips/{id}/ -> 405
        put_resp = self.client.put(f'/api/v1/payroll/payslips/{ps1.id}/', {'status': 'revoked'})
        self.assertEqual(put_resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        # PATCH -> 405
        patch_resp = self.client.patch(f'/api/v1/payroll/payslips/{ps1.id}/', {'status': 'revoked'})
        self.assertEqual(patch_resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        # DELETE -> 405
        del_resp = self.client.delete(f'/api/v1/payroll/payslips/{ps1.id}/')
        self.assertEqual(del_resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_unauthorized_administrative_access_returns_401_or_403(self):
        # Unauthenticated -> 401
        resp_unauth = self.client.get('/api/v1/payroll/payslips/')
        self.assertEqual(resp_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticated without payslip.view -> 403
        self.client.force_authenticate(user=self.user1)
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=False):
            resp_no_perm = self.client.get('/api/v1/payroll/payslips/')
        self.assertEqual(resp_no_perm.status_code, status.HTTP_403_FORBIDDEN)

    def test_organization_isolation_remains_enforced(self):
        # Approve period in Org 1
        self._approve_period(self.period1, self.user1)

        # Create and approve period in Org 2
        period2 = PayrollPeriod.objects.create(
            organization=self.org2,
            year=2024,
            month=7,
            start_date=date(2024, 7, 1),
            end_date=date(2024, 7, 31),
        )
        generate_payroll_for_period(period2)
        self._approve_period(period2, self.user3)

        # User 1 with admin perm in Org 1 queries /payslips/
        self.client.force_authenticate(user=self.user1)
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            resp = self.client.get('/api/v1/payroll/payslips/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Should only contain Org 1 payslips (2 items), NOT Org 2 (1 item)
        returned_codes = [p['employee_code'] for p in resp.data]
        self.assertIn('E001', returned_codes)
        self.assertIn('E002', returned_codes)
        self.assertNotIn('E003', returned_codes)
