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

    def test_effective_days_capped_at_working_days(self):
        # Even if present + leave exceeds working days, effective_days is capped at working_days
        working_days = _working_days_in_period(self.org.id, date(2024, 9, 1), date(2024, 9, 30))
        # Mark 25 attendance days (e.g. including weekends)
        for d in range(1, 26):
            Attendance.objects.create(employee=self.emp, date=date(2024, 9, d), status='present')
        generate_payroll_for_period(self.period)
        record = PayrollRecord.objects.get(period=self.period, employee=self.emp)
        self.assertEqual(record.effective_days, Decimal(working_days))
        self.assertEqual(record.gross_salary, Decimal('30000.00'))
        self.assertEqual(record.absent_days, 0)


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

    def test_overlapping_approved_leaves_not_double_counted(self):
        # Request 1: Mon Sep 2 to Wed Sep 4 (3 weekdays: 2, 3, 4)
        LeaveRequest.objects.create(
            employee=self.emp, leave_type=self.leave_type,
            start_date=date(2024, 9, 2), end_date=date(2024, 9, 4), status='approved',
        )
        # Request 2: Wed Sep 4 to Fri Sep 6 (3 weekdays: 4, 5, 6 — Sep 4 overlaps)
        LeaveRequest.objects.create(
            employee=self.emp, leave_type=self.leave_type,
            start_date=date(2024, 9, 4), end_date=date(2024, 9, 6), status='approved',
        )
        # Distinct days: Sep 2, 3, 4, 5, 6 -> 5 days (not 6)
        leave_days = _approved_leave_days(self.emp, date(2024, 9, 1), date(2024, 9, 30))
        self.assertEqual(leave_days, 5)


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


class PayrollWorkflowRegressionTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Regression Org')
        # Superuser WITHOUT an employee profile
        self.superadmin = User.objects.create_user(
            email='super_reg@company.com',
            password='Pass123!',
            status='active',
            is_superuser=True,
        )
        # Normal employee with user and compensation
        self.emp_user = User.objects.create_user(
            email='reg_emp@company.com',
            password='Pass123!',
            status='active',
        )
        self.emp = Employee.objects.create(
            user=self.emp_user,
            employee_code='REG01',
            organization=self.org,
            employment_status=EmploymentStatus.ACTIVE,
        )
        self.comp = CompensationHistory.objects.create(
            employee=self.emp,
            effective_from=date(2026, 9, 5),  # mid-period effective date
            basic_salary=Decimal('55000.00'),
            created_by=self.superadmin,
        )
        # Mark 10 attendance days
        for d in range(1, 15):
            if date(2026, 9, d).weekday() < 5:
                Attendance.objects.create(
                    employee=self.emp,
                    date=date(2026, 9, d),
                    status='present',
                )

    def test_superuser_without_employee_can_create_period(self):
        self.client.force_authenticate(user=self.superadmin)
        resp = self.client.post('/api/v1/payroll/periods/', {
            'organization': self.org.id,
            'year': 2026,
            'month': 9,
            'start_date': '2026-09-01',
            'end_date': '2026-09-30',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['organization'], self.org.id)

    def test_superuser_complete_payroll_flow(self):
        self.client.force_authenticate(user=self.superadmin)
        # 1. Create period
        create_resp = self.client.post('/api/v1/payroll/periods/', {
            'organization': self.org.id,
            'year': 2026,
            'month': 9,
            'start_date': '2026-09-01',
            'end_date': '2026-09-30',
        })
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        period_id = create_resp.data['id']

        # 2. View periods
        list_resp = self.client.get('/api/v1/payroll/periods/')
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(any(p['id'] == period_id for p in list_resp.data))

        # 3. Generate payroll
        gen_resp = self.client.post(f'/api/v1/payroll/periods/{period_id}/generate/')
        self.assertEqual(gen_resp.status_code, status.HTTP_200_OK)

        # 4. View records and verify calculation
        rec_resp = self.client.get(f'/api/v1/payroll/records/?period={period_id}')
        self.assertEqual(rec_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(rec_resp.data), 1)
        record = rec_resp.data[0]
        self.assertEqual(record['employee_code'], 'REG01')
        self.assertEqual(record['basic_salary'], '55000.00')
        self.assertGreater(float(record['gross_salary']), 0)
        self.assertEqual(record['gross_salary'], record['net_salary'])

        # 5. Approve payroll
        appr_resp = self.client.post(f'/api/v1/payroll/periods/{period_id}/approve/')
        self.assertEqual(appr_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(appr_resp.data['status'], 'approved')

        # 6. Verify period locked
        gen_again = self.client.post(f'/api/v1/payroll/periods/{period_id}/generate/')
        self.assertEqual(gen_again.status_code, status.HTTP_400_BAD_REQUEST)

        # 7. Verify payslip created and accessible to employee
        self.client.force_authenticate(user=self.emp_user)
        my_payslips = self.client.get('/api/v1/payroll/payslips/my/')
        self.assertEqual(my_payslips.status_code, status.HTTP_200_OK)
        self.assertEqual(len(my_payslips.data), 1)
        self.assertEqual(my_payslips.data[0]['employee_code'], 'REG01')
        self.assertEqual(my_payslips.data[0]['net_salary'], record['net_salary'])

    def test_superuser_can_set_compensation(self):
        self.client.force_authenticate(user=self.superadmin)
        resp = self.client.post('/api/v1/payroll/compensation/set/', {
            'employee': self.emp.id,
            'basic_salary': '75000.00',
            'effective_from': '2026-10-01',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['basic_salary'], '75000.00')

    def test_zero_attendance_vs_valid_attendance_payroll_workflow(self):
        """
        Verify root cause regression:
        1. When period has 0 attendance (e.g. future period October 2026),
           effective_days is 0.0, net_salary is 0.00, LOP is full basic_salary,
           and exception detection flags FULL_ABSENCE.
        2. When period has valid attendance (e.g. September 2026),
           effective_days > 0, net_salary > 0, and reports aggregate correctly.
        3. Organization isolation is strictly preserved.
        4. RBAC is strictly preserved.
        """
        self.client.force_authenticate(user=self.superadmin)

        # 1. October 2026 period: No attendance records exist in October
        oct_resp = self.client.post('/api/v1/payroll/periods/', {
            'organization': self.org.id,
            'year': 2026,
            'month': 10,
            'start_date': '2026-10-01',
            'end_date': '2026-10-31',
        })
        self.assertEqual(oct_resp.status_code, status.HTTP_201_CREATED)
        oct_period_id = oct_resp.data['id']

        # Generate October payroll
        gen_oct = self.client.post(f'/api/v1/payroll/periods/{oct_period_id}/generate/')
        self.assertEqual(gen_oct.status_code, status.HTTP_200_OK)

        # Verify October record values
        rec_oct = self.client.get(f'/api/v1/payroll/records/?period={oct_period_id}')
        self.assertEqual(rec_oct.status_code, status.HTTP_200_OK)
        record = rec_oct.data[0]
        self.assertEqual(record['present_days'], 0)
        self.assertEqual(Decimal(record['effective_days']), Decimal('0.0'))
        self.assertEqual(Decimal(record['net_salary']), Decimal('0.00'))

        # Check October reporting: 0 payout, full LOP, FULL_ABSENCE exception
        summary_resp = self.client.get(f'/api/v1/payroll/reports/period-summary/?period={oct_period_id}')
        self.assertEqual(summary_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(summary_resp.data['summary']['total_net_salary']), Decimal('0.00'))
        self.assertEqual(Decimal(summary_resp.data['summary']['total_effective_paid_days']), Decimal('0.0'))
        self.assertEqual(
            Decimal(summary_resp.data['summary']['total_loss_of_pay']),
            Decimal(record['basic_salary'])
        )

        exc_resp = self.client.get(f'/api/v1/payroll/reports/exceptions/?period={oct_period_id}')
        self.assertEqual(exc_resp.status_code, status.HTTP_200_OK)
        exc_types = [e['type'] for e in exc_resp.data['exceptions']]
        self.assertIn('FULL_ABSENCE', exc_types)

        # 2. September 2026 period: 10 valid attendance records exist (from setUp)
        sep_resp = self.client.post('/api/v1/payroll/periods/', {
            'organization': self.org.id,
            'year': 2026,
            'month': 9,
            'start_date': '2026-09-01',
            'end_date': '2026-09-30',
        })
        self.assertEqual(sep_resp.status_code, status.HTTP_201_CREATED)
        sep_period_id = sep_resp.data['id']

        gen_sep = self.client.post(f'/api/v1/payroll/periods/{sep_period_id}/generate/')
        self.assertEqual(gen_sep.status_code, status.HTTP_200_OK)

        rec_sep = self.client.get(f'/api/v1/payroll/records/?period={sep_period_id}')
        self.assertEqual(rec_sep.status_code, status.HTTP_200_OK)
        sep_record = rec_sep.data[0]
        self.assertEqual(sep_record['present_days'], 10)
        self.assertEqual(Decimal(sep_record['effective_days']), Decimal('10.0'))
        self.assertGreater(Decimal(sep_record['net_salary']), Decimal('0.00'))

        # Approve September and check payslip & locked period
        appr_sep = self.client.post(f'/api/v1/payroll/periods/{sep_period_id}/approve/')
        self.assertEqual(appr_sep.status_code, status.HTTP_200_OK)

        # Re-generate locked period rejected
        regen_resp = self.client.post(f'/api/v1/payroll/periods/{sep_period_id}/generate/')
        self.assertEqual(regen_resp.status_code, status.HTTP_400_BAD_REQUEST)

        # Employee self-service payslip matches finalized payroll
        self.client.force_authenticate(user=self.emp_user)
        my_payslips = self.client.get('/api/v1/payroll/payslips/my/')
        self.assertEqual(my_payslips.status_code, status.HTTP_200_OK)
        sep_slip = next(s for s in my_payslips.data if s['month'] == 9)
        self.assertEqual(Decimal(sep_slip['net_salary']), Decimal(sep_record['net_salary']))

        # 3. Organization isolation & RBAC
        other_org = Organization.objects.create(name='Isolated Org')
        other_user = User.objects.create_user(email='iso@other.com', password='Pass123!', status='active')
        Employee.objects.create(
            user=other_user, employee_code='ISO01', organization=other_org, employment_status=EmploymentStatus.ACTIVE
        )
        self.client.force_authenticate(user=other_user)
        # Without payroll.view -> 403 Forbidden
        other_records = self.client.get(f'/api/v1/payroll/records/?period={sep_period_id}')
        self.assertEqual(other_records.status_code, status.HTTP_403_FORBIDDEN)

        # With payroll.view in Isolated Org -> Cannot see sep_period_id records from self.org
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            other_records_auth = self.client.get(f'/api/v1/payroll/records/?period={sep_period_id}')
            self.assertEqual(other_records_auth.status_code, status.HTTP_200_OK)
            self.assertEqual(len(other_records_auth.data), 0)

        # 4. RBAC: Employee without payroll.approve cannot approve
        self.client.force_authenticate(user=self.emp_user)
        unauth_appr = self.client.post(f'/api/v1/payroll/periods/{oct_period_id}/approve/')
        self.assertEqual(unauth_appr.status_code, status.HTTP_403_FORBIDDEN)


class FuturePeriodWarningTest(TestCase):
    """
    Regression tests for the future-period warning added to the generate endpoint.

    Rule: when a payroll period's end_date is still in the future, the generate
    endpoint MUST return a 'warning' key alongside 'detail'.  For a completed
    (past) period no warning is emitted.

    Calculations are NOT altered — the warning is purely informational.
    """

    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Warn Org')
        self.user = User.objects.create_user(email='warn@org.com', password='Pass123!', status='active')
        self.emp = Employee.objects.create(
            user=self.user,
            employee_code='WO01',
            organization=self.org,
            employment_status=EmploymentStatus.ACTIVE,
        )
        CompensationHistory.objects.create(
            employee=self.emp,
            effective_from=date(2024, 1, 1),
            basic_salary=Decimal('50000.00'),
        )
        self.client.force_authenticate(user=self.user)

    def _make_period(self, year, month, start, end):
        return PayrollPeriod.objects.create(
            organization=self.org,
            year=year,
            month=month,
            start_date=start,
            end_date=end,
        )

    def test_generate_future_period_returns_warning(self):
        """
        Generating payroll for a period whose end_date > today returns HTTP 200
        plus a non-empty 'warning' key.  Payroll calculations are unchanged.
        """
        period = self._make_period(2099, 3, date(2099, 3, 1), date(2099, 3, 31))

        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            resp = self.client.post(f'/api/v1/payroll/periods/{period.id}/generate/')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('detail', resp.data)
        self.assertIn('warning', resp.data)
        self.assertIn('2099', resp.data['warning'])
        self.assertIn('incomplete', resp.data['warning'].lower())

        # Guard must NOT block generation — record must still be created.
        self.assertEqual(PayrollRecord.objects.filter(period=period).count(), 1)

    def test_generate_past_period_no_warning(self):
        """
        Generating payroll for a period that has already ended returns HTTP 200
        with 'detail' only — no 'warning' key.
        """
        period = self._make_period(2020, 1, date(2020, 1, 1), date(2020, 1, 31))

        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            resp = self.client.post(f'/api/v1/payroll/periods/{period.id}/generate/')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('detail', resp.data)
        self.assertNotIn('warning', resp.data)

        self.assertEqual(PayrollRecord.objects.filter(period=period).count(), 1)

    def test_generate_future_period_payroll_math_unchanged(self):
        """
        The future-period warning must NOT alter the payroll calculation.
        A future period with zero attendance must still produce effective_days=0
        and net_salary=0, faithfully reflecting the absence of attendance data.
        """
        period = self._make_period(2099, 4, date(2099, 4, 1), date(2099, 4, 30))

        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            resp = self.client.post(f'/api/v1/payroll/periods/{period.id}/generate/')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        record = PayrollRecord.objects.get(period=period, employee=self.emp)
        # No attendance for 2099: effective_days and net_salary must be zero.
        self.assertEqual(record.present_days, 0)
        self.assertEqual(record.effective_days, Decimal('0.00'))
        self.assertEqual(record.net_salary, Decimal('0.00'))
        # Basic salary snapshot must still be captured correctly.
        self.assertEqual(record.basic_salary, Decimal('50000.00'))


class PayrollCalculationSemanticsRegressionTests(TestCase):
    """
    Exhaustive regression test suite ensuring payroll day-count semantics and salary calculations:
    1. Zero attendance
    2. Full attendance
    3. Partial attendance
    4. Attendance + approved paid leave
    5. Half-day attendance
    6. Weekend/holiday exclusion
    7. Overlapping leave/attendance deduplication
    8. Salary/LOP consistency for ₹100,000 basic salary
    9. Partial LOP consistency
    10. Payroll approval locking and record immutability
    """

    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Regression Org')
        self.user = User.objects.create_user(
            email='superadmin@company.com',
            password='Password123!',
            first_name='Super',
            last_name='Admin',
            status='active',
        )
        self.emp = Employee.objects.create(
            user=self.user,
            employee_code='ADMIN-001',
            organization=self.org,
            employment_status=EmploymentStatus.ACTIVE,
        )
        # ₹100,000 monthly basic salary configured
        CompensationHistory.objects.create(
            employee=self.emp,
            effective_from=date(2025, 1, 1),
            basic_salary=Decimal('100000.00'),
            created_by=self.user,
        )
        # Holiday on Jan 1, 2025 (New Year) -> 23 weekdays - 1 holiday = 22 working days
        Holiday.objects.create(
            organization=self.org,
            name='New Year',
            date=date(2025, 1, 1),
            is_active=True,
        )
        self.period = PayrollPeriod.objects.create(
            organization=self.org,
            year=2025,
            month=1,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
        )
        self.leave_type = LeaveType.objects.create(
            organization=self.org,
            name='Earned Leave',
            annual_allocation=15,
        )
        # List of the 22 scheduled working dates in Jan 2025
        self.working_dates = [
            d for d in [date(2025, 1, day) for day in range(1, 32)]
            if d.weekday() < 5 and d != date(2025, 1, 1)
        ]
        self.assertEqual(len(self.working_dates), 22)

    def test_1_zero_attendance(self):
        """
        1. Zero attendance:
        working_days = 22, present_days = 0, leave_days = 0, absent_days = 22,
        effective_days = 0, lop_days = 22, lop_amount = 100,000, net_salary = 0.
        Effective days MUST NOT equal working days.
        """
        generate_payroll_for_period(self.period)
        record = PayrollRecord.objects.get(period=self.period, employee=self.emp)

        self.assertEqual(record.working_days, 22)
        self.assertEqual(record.present_days, 0)
        self.assertEqual(record.half_days, 0)
        self.assertEqual(record.leave_days, 0)
        self.assertEqual(record.absent_days, 22)
        self.assertEqual(record.effective_days, Decimal('0.0'))
        self.assertEqual(record.lop_days, Decimal('22.0'))
        self.assertEqual(record.basic_salary, Decimal('100000.00'))
        self.assertEqual(record.gross_salary, Decimal('0.00'))
        self.assertEqual(record.net_salary, Decimal('0.00'))
        self.assertEqual(record.lop_amount, Decimal('100000.00'))

        # Verify serializer representation
        from .serializers import PayrollRecordSerializer
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True):
            data = PayrollRecordSerializer(record, context={'request': None}).data
            self.assertEqual(Decimal(data['effective_days']), Decimal('0.0'))
            self.assertEqual(Decimal(data['lop_days']), Decimal('22.0'))
            self.assertEqual(Decimal(data['lop_amount']), Decimal('100000.00'))

    def test_2_full_attendance(self):
        """
        2. Full attendance:
        working_days = 22, present_days = 22, absent_days = 0, effective_days = 22,
        lop_days = 0, lop_amount = 0, net_salary = 100,000.
        """
        for d in self.working_dates:
            Attendance.objects.create(employee=self.emp, date=d, status='present')

        generate_payroll_for_period(self.period)
        record = PayrollRecord.objects.get(period=self.period, employee=self.emp)

        self.assertEqual(record.working_days, 22)
        self.assertEqual(record.present_days, 22)
        self.assertEqual(record.half_days, 0)
        self.assertEqual(record.leave_days, 0)
        self.assertEqual(record.absent_days, 0)
        self.assertEqual(record.effective_days, Decimal('22.0'))
        self.assertEqual(record.lop_days, Decimal('0.0'))
        self.assertEqual(record.basic_salary, Decimal('100000.00'))
        self.assertEqual(record.gross_salary, Decimal('100000.00'))
        self.assertEqual(record.net_salary, Decimal('100000.00'))
        self.assertEqual(record.lop_amount, Decimal('0.00'))

    def test_3_partial_attendance(self):
        """
        3. Partial attendance:
        working_days = 22, present_days = 20, absent_days = 2,
        effective_days = 20, lop_days = 2.
        """
        for d in self.working_dates[:20]:
            Attendance.objects.create(employee=self.emp, date=d, status='present')

        generate_payroll_for_period(self.period)
        record = PayrollRecord.objects.get(period=self.period, employee=self.emp)

        self.assertEqual(record.working_days, 22)
        self.assertEqual(record.present_days, 20)
        self.assertEqual(record.half_days, 0)
        self.assertEqual(record.leave_days, 0)
        self.assertEqual(record.absent_days, 2)
        self.assertEqual(record.effective_days, Decimal('20.0'))
        self.assertEqual(record.lop_days, Decimal('2.0'))
        expected_gross = (Decimal('100000.00') * Decimal(20) / Decimal(22)).quantize(Decimal('0.01'))
        self.assertEqual(record.gross_salary, expected_gross)
        self.assertEqual(record.net_salary, expected_gross)
        self.assertEqual(record.lop_amount, Decimal('100000.00') - expected_gross)

    def test_4_attendance_plus_approved_paid_leave(self):
        """
        4. Attendance + approved paid leave:
        working_days = 22, present_days = 20, leave_days = 2,
        absent_days = 0, effective_days = 22, lop_days = 0.
        """
        # 20 days present
        for d in self.working_dates[:20]:
            Attendance.objects.create(employee=self.emp, date=d, status='present')

        # Remaining 2 working days approved leave: Jan 30 & Jan 31
        LeaveRequest.objects.create(
            employee=self.emp,
            leave_type=self.leave_type,
            start_date=self.working_dates[20],
            end_date=self.working_dates[21],
            status='approved',
        )

        generate_payroll_for_period(self.period)
        record = PayrollRecord.objects.get(period=self.period, employee=self.emp)

        self.assertEqual(record.working_days, 22)
        self.assertEqual(record.present_days, 20)
        self.assertEqual(record.half_days, 0)
        self.assertEqual(record.leave_days, 2)
        self.assertEqual(record.absent_days, 0)
        self.assertEqual(record.effective_days, Decimal('22.0'))
        self.assertEqual(record.lop_days, Decimal('0.0'))
        self.assertEqual(record.gross_salary, Decimal('100000.00'))
        self.assertEqual(record.net_salary, Decimal('100000.00'))
        self.assertEqual(record.lop_amount, Decimal('0.00'))

    def test_5_half_day_attendance(self):
        """
        5. Half-day:
        20 full present + 1 half day -> effective = 20.5, lop_days = 1.5.
        """
        for d in self.working_dates[:20]:
            Attendance.objects.create(employee=self.emp, date=d, status='present')
        Attendance.objects.create(employee=self.emp, date=self.working_dates[20], status='half_day')

        generate_payroll_for_period(self.period)
        record = PayrollRecord.objects.get(period=self.period, employee=self.emp)

        self.assertEqual(record.working_days, 22)
        self.assertEqual(record.present_days, 20)
        self.assertEqual(record.half_days, 1)
        self.assertEqual(record.leave_days, 0)
        self.assertEqual(record.effective_days, Decimal('20.5'))
        self.assertEqual(record.lop_days, Decimal('1.5'))
        expected_gross = (Decimal('100000.00') * Decimal('20.5') / Decimal(22)).quantize(Decimal('0.01'))
        self.assertEqual(record.gross_salary, expected_gross)
        self.assertEqual(record.net_salary, expected_gross)
        self.assertEqual(record.lop_amount, Decimal('100000.00') - expected_gross)

    def test_6_weekend_holiday_exclusion(self):
        """
        6. Weekend/holiday exclusion:
        Ensure working_days does not count excluded days (weekends & holidays).
        """
        wd = _working_days_in_period(self.org.id, date(2025, 1, 1), date(2025, 1, 31))
        self.assertEqual(wd, 22)
        # Jan 1 is holiday (Wednesday) -> excluded
        # Jan 4, 5, 11, 12, 18, 19, 25, 26 are Saturdays/Sundays -> 8 weekend days excluded
        # 31 - 8 - 1 = 22 scheduled working days

    def test_7_overlapping_leave_and_attendance_no_double_counting(self):
        """
        7. Overlapping leave/attendance:
        If an employee has attendance on a date that is also covered by approved leave,
        the date is not double counted.
        """
        # Employee attended Jan 2 to Jan 29 (20 working days)
        for d in self.working_dates[:20]:
            Attendance.objects.create(employee=self.emp, date=d, status='present')

        # Employee ALSO had an approved leave that covered Jan 29 and Jan 30
        # self.working_dates[19] is Jan 29 (present attendance exists)
        # self.working_dates[20] is Jan 30 (no attendance)
        # self.working_dates[21] is Jan 31 (absent)
        LeaveRequest.objects.create(
            employee=self.emp,
            leave_type=self.leave_type,
            start_date=self.working_dates[19],
            end_date=self.working_dates[20],
            status='approved',
        )

        generate_payroll_for_period(self.period)
        record = PayrollRecord.objects.get(period=self.period, employee=self.emp)

        self.assertEqual(record.working_days, 22)
        self.assertEqual(record.present_days, 20)
        # Jan 29 is not double-counted; leave_days only counts Jan 30
        self.assertEqual(record.leave_days, 1)
        self.assertEqual(record.effective_days, Decimal('21.0'))
        self.assertEqual(record.absent_days, 1)
        self.assertEqual(record.lop_days, Decimal('1.0'))

    def test_8_salary_and_lop_consistency(self):
        """
        8. Salary/LOP consistency:
        For ₹100,000 salary, 22 working days, zero effective days:
        LOP amount = ₹100,000, Net salary = ₹0.
        """
        generate_payroll_for_period(self.period)
        record = PayrollRecord.objects.get(period=self.period, employee=self.emp)

        self.assertEqual(record.basic_salary, Decimal('100000.00'))
        self.assertEqual(record.gross_salary, Decimal('0.00'))
        self.assertEqual(record.net_salary, Decimal('0.00'))
        self.assertEqual(record.lop_amount, Decimal('100000.00'))
        self.assertEqual(record.net_salary + record.lop_amount, record.basic_salary)

    def test_9_partial_lop_consistency(self):
        """
        9. Partial LOP:
        Verify LOP amount matches LOP days according to the salary calculation.
        """
        for d in self.working_dates[:20]:
            Attendance.objects.create(employee=self.emp, date=d, status='present')

        generate_payroll_for_period(self.period)
        record = PayrollRecord.objects.get(period=self.period, employee=self.emp)

        self.assertEqual(record.lop_days, Decimal('2.0'))
        expected_lop = (Decimal('100000.00') * Decimal('2') / Decimal('22')).quantize(Decimal('0.01'))
        self.assertEqual(record.lop_amount, expected_lop)
        self.assertEqual(record.net_salary + record.lop_amount, record.basic_salary)

    def test_10_payroll_approval_and_locking(self):
        """
        10. Payroll approval:
        Verify the correction does not bypass payroll locking or mutate approved records unexpectedly.
        """
        generate_payroll_for_period(self.period)
        self.period.status = PayrollPeriod.STATUS_APPROVED
        self.period.save(update_fields=['status'])

        # Attempting re-generation on approved period must fail
        with self.assertRaises(ValueError):
            generate_payroll_for_period(self.period)

        # Approved records remain immutable
        record = PayrollRecord.objects.get(period=self.period, employee=self.emp)
        self.assertEqual(record.status, PayrollRecord.STATUS_DRAFT)
