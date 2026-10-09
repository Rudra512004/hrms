"""
Phase 6.5 Payslip Engine Verification Tests.
Tests:
- Deterministic INR monetary amount-to-words conversion
- Immutable snapshotting of Organization, Employee, Attendance, and Financials
- Normalized PayslipLine items
- Issuance rules, draft rejection, and idempotency
- Immutability of issued payslips and lines
- Server-side PDF generation
- Cryptographic verification tokens and public verification endpoint
- Employee self-service access and IDOR protection
- Cross-tenant isolation
- Dynamic permission enforcement
- Audit logging
"""
from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework import status

from apps.organization.models import Organization, Branch, Department, Designation, OfficeNetwork
from apps.employees.models import Employee, EmploymentStatus, EmployeeStatutoryAndBank
from apps.authorization.models import Role, Permission, RolePermission, UserRole
from apps.payroll.models import PayrollPeriod, PayrollRecord, Payslip, PayslipLine
from apps.payroll.services import issue_payslips_for_period
from apps.payroll.currency_utils import amount_to_words_inr
from apps.payroll.pdf_service import generate_payslip_pdf
from apps.audit.models import AuditLog

User = get_user_model()


class CurrencyUtilsTests(TestCase):
    def test_amount_to_words_inr_exact_values(self):
        self.assertEqual(amount_to_words_inr(Decimal('0.00')), "Zero Rupees Only")
        self.assertEqual(amount_to_words_inr(Decimal('1.00')), "One Rupee Only")
        self.assertEqual(amount_to_words_inr(Decimal('55000.00')), "Fifty-Five Thousand Rupees Only")
        self.assertEqual(amount_to_words_inr(Decimal('55000.50')), "Fifty-Five Thousand Rupees and Fifty Paise Only")
        self.assertEqual(amount_to_words_inr(Decimal('0.50')), "Fifty Paise Only")
        self.assertEqual(amount_to_words_inr(Decimal('0.01')), "One Paisa Only")
        self.assertEqual(amount_to_words_inr(Decimal('100000.00')), "One Lakh Rupees Only")
        self.assertEqual(
            amount_to_words_inr(Decimal('123456.78')),
            "One Lakh Twenty-Three Thousand Four Hundred and Fifty-Six Rupees and Seventy-Eight Paise Only"
        )
        self.assertEqual(amount_to_words_inr(Decimal('105000000.00')), "Ten Crore Fifty Lakh Rupees Only")

    def test_amount_to_words_negative_raises_error(self):
        with self.assertRaises(ValueError):
            amount_to_words_inr(Decimal('-10.00'))


class PayslipEngineTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Tenant A
        self.org_a = Organization.objects.create(name='BeyondSure Technologies Ltd')
        self.branch_a = Branch.objects.create(
            organization=self.org_a,
            name='Bangalore Central',
            address_line1='MG Road',
            city='Bangalore',
            state='Karnataka',
            postal_code='560001'
        )
        OfficeNetwork.objects.create(branch=self.branch_a, name='Office', network='127.0.0.1/32', is_active=True)
        self.dept_a = Department.objects.create(branch=self.branch_a, name='Engineering')
        self.desig_a = Designation.objects.create(organization=self.org_a, name='Senior Engineer')

        # Admin User Org A
        self.admin_a = User.objects.create_user(email='admin_a@beyondsure.com', password='Password123!', status='active')
        self.admin_emp_a = Employee.objects.create(
            user=self.admin_a,
            organization=self.org_a,
            branch=self.branch_a,
            employee_code='ADMIN-001',
            employment_status=EmploymentStatus.ACTIVE
        )

        # Employee 1 Org A
        self.user_emp1 = User.objects.create_user(
            email='alice@beyondsure.com',
            first_name='Alice',
            last_name='Smith',
            password='Password123!',
            status='active'
        )
        self.emp1 = Employee.objects.create(
            user=self.user_emp1,
            organization=self.org_a,
            branch=self.branch_a,
            department=self.dept_a,
            designation=self.desig_a,
            employee_code='EMP-001',
            joining_date=date(2023, 1, 15),
            employment_status=EmploymentStatus.ACTIVE
        )
        EmployeeStatutoryAndBank.objects.create(
            employee=self.emp1,
            bank_name='HDFC Bank',
            account_number='98765432101234',
            ifsc_code='HDFC0001234',
            pan_number='ABCDE1234F',
            uan_number='100987654321',
            esic_number='31001234560001',
            payment_mode='BANK_TRANSFER'
        )

        # Employee 2 Org A
        self.user_emp2 = User.objects.create_user(
            email='bob@beyondsure.com',
            first_name='Bob',
            last_name='Jones',
            password='Password123!',
            status='active'
        )
        self.emp2 = Employee.objects.create(
            user=self.user_emp2,
            organization=self.org_a,
            branch=self.branch_a,
            department=self.dept_a,
            designation=self.desig_a,
            employee_code='EMP-002',
            joining_date=date(2023, 5, 1),
            employment_status=EmploymentStatus.ACTIVE
        )

        # Tenant B
        self.org_b = Organization.objects.create(name='Competitor Corp')
        self.branch_b = Branch.objects.create(organization=self.org_b, name='Mumbai Branch')
        OfficeNetwork.objects.create(branch=self.branch_b, name='Office', network='127.0.0.1/32', is_active=True)
        self.admin_b = User.objects.create_user(email='admin_b@competitor.com', password='Password123!', status='active')
        self.admin_emp_b = Employee.objects.create(
            user=self.admin_b,
            organization=self.org_b,
            branch=self.branch_b,
            employee_code='B-ADMIN-001',
            employment_status=EmploymentStatus.ACTIVE
        )

        # Set permissions for Admin A
        role_a = Role.objects.create(organization=self.org_a, name='HR Manager')
        perms = ['payroll.view', 'payroll.approve', 'payroll.generate', 'payslip.view', 'payslip.download']
        for codename in perms:
            res, act = codename.split('.', 1)
            p, _ = Permission.objects.get_or_create(
                codename=codename,
                defaults={'name': codename, 'resource': res, 'action': act}
            )
            RolePermission.objects.create(role=role_a, permission=p)
        UserRole.objects.create(user=self.admin_a, role=role_a)

        # Set permissions for Admin B
        role_b = Role.objects.create(organization=self.org_b, name='Org B Manager')
        for codename in perms:
            res, act = codename.split('.', 1)
            p, _ = Permission.objects.get_or_create(
                codename=codename,
                defaults={'name': codename, 'resource': res, 'action': act}
            )
            RolePermission.objects.create(role=role_b, permission=p)
        UserRole.objects.create(user=self.admin_b, role=role_b)

        # Setup Finalized Payroll Period for Org A
        self.period_a = PayrollPeriod.objects.create(
            organization=self.org_a,
            year=2026,
            month=9,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            status=PayrollPeriod.STATUS_FINALIZED
        )

        self.rec1 = PayrollRecord.objects.create(
            period=self.period_a,
            employee=self.emp1,
            working_days=22,
            present_days=20,
            half_days=0,
            absent_days=0,
            leave_days=2,
            effective_days=Decimal('22.0'),
            basic_salary=Decimal('60000.00'),
            gross_salary=Decimal('60000.00'),
            net_salary=Decimal('60000.00'),
            status=PayrollRecord.STATUS_FINALIZED
        )

        self.rec2 = PayrollRecord.objects.create(
            period=self.period_a,
            employee=self.emp2,
            working_days=22,
            present_days=18,
            half_days=0,
            absent_days=4,
            leave_days=0,
            effective_days=Decimal('18.0'),
            basic_salary=Decimal('44000.00'),
            gross_salary=Decimal('36000.00'),
            net_salary=Decimal('36000.00'),
            status=PayrollRecord.STATUS_FINALIZED
        )

    def test_payslip_issuance_snapshots_and_lines(self):
        payslips = issue_payslips_for_period(self.period_a, requesting_user=self.admin_a)
        self.assertEqual(len(payslips), 2)

        ps1 = Payslip.objects.get(payroll_record=self.rec1)
        self.assertEqual(ps1.status, Payslip.STATUS_ISSUED)
        self.assertEqual(ps1.organization_name, "BeyondSure Technologies Ltd")
        self.assertEqual(ps1.employee_code, "EMP-001")
        self.assertEqual(ps1.employee_name, "Alice Smith")
        self.assertEqual(ps1.department_name, "Engineering")
        self.assertTrue(ps1.masked_bank_account.endswith("1234"))
        self.assertNotIn("9876543210", ps1.masked_bank_account)
        self.assertTrue(ps1.masked_pan.endswith("234F"))
        self.assertNotIn("ABCDE", ps1.masked_pan)
        self.assertEqual(ps1.esic_number, "31001234560001")
        self.assertEqual(ps1.gross_earnings, Decimal('60000.00'))
        self.assertEqual(ps1.net_pay, Decimal('60000.00'))
        self.assertEqual(ps1.net_pay_in_words, "Sixty Thousand Rupees Only")
        self.assertTrue(ps1.verification_token)
        self.assertTrue(ps1.integrity_hash)

        # Lines
        lines = ps1.lines.all()
        self.assertEqual(lines.count(), 1)
        line = lines.first()
        self.assertEqual(line.category, PayslipLine.CATEGORY_EARNING)
        self.assertEqual(line.component_code, "BASIC")
        self.assertEqual(line.amount, Decimal('60000.00'))

    def test_rejection_from_unfinalized_periods(self):
        draft_period = PayrollPeriod.objects.create(
            organization=self.org_a,
            year=2026,
            month=10,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            status=PayrollPeriod.STATUS_DRAFT
        )
        with self.assertRaises(ValueError):
            issue_payslips_for_period(draft_period)

        draft_period.status = PayrollPeriod.STATUS_LOCKED
        draft_period.save()
        with self.assertRaises(ValueError):
            issue_payslips_for_period(draft_period)

        draft_period.status = PayrollPeriod.STATUS_PROCESSING
        draft_period.save()
        with self.assertRaises(ValueError):
            issue_payslips_for_period(draft_period)

        draft_period.status = PayrollPeriod.STATUS_REVIEW
        draft_period.save()
        with self.assertRaises(ValueError):
            issue_payslips_for_period(draft_period)

    def test_issuance_idempotency(self):
        first_run = issue_payslips_for_period(self.period_a, requesting_user=self.admin_a)
        initial_count = Payslip.objects.count()
        initial_lines_count = PayslipLine.objects.count()

        second_run = issue_payslips_for_period(self.period_a, requesting_user=self.admin_a)
        self.assertEqual(len(second_run), initial_count)
        self.assertEqual(Payslip.objects.count(), initial_count)
        self.assertEqual(PayslipLine.objects.count(), initial_lines_count)

    def test_issued_payslip_immutability(self):
        issue_payslips_for_period(self.period_a, requesting_user=self.admin_a)
        ps1 = Payslip.objects.get(payroll_record=self.rec1)

        # Direct mutation of net_pay should fail validation
        ps1.net_pay = Decimal('99999.00')
        with self.assertRaises(ValidationError):
            ps1.save()

        # Direct mutation of lines should fail validation
        line = ps1.lines.first()
        line.amount = Decimal('99999.00')
        with self.assertRaises(ValidationError):
            line.save()

    def test_pdf_generation(self):
        issue_payslips_for_period(self.period_a, requesting_user=self.admin_a)
        ps1 = Payslip.objects.get(payroll_record=self.rec1)
        pdf_bytes = generate_payslip_pdf(ps1)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        self.assertGreater(len(pdf_bytes), 2000)

    def test_public_verification_endpoint(self):
        issue_payslips_for_period(self.period_a, requesting_user=self.admin_a)
        ps1 = Payslip.objects.get(payroll_record=self.rec1)

        # Unauthenticated request
        self.client.logout()
        resp = self.client.get(f'/api/v1/payroll/payslips/verify/{ps1.verification_token}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['valid'])
        self.assertEqual(resp.data['payslip_number'], ps1.payslip_number)
        self.assertEqual(resp.data['employee_name'], "Alice Smith")
        self.assertEqual(resp.data['employee_code'], "EMP-001")
        self.assertEqual(resp.data['period'], "2026/09")

        # Crucial security assertion: NEVER expose sensitive financials on public verification
        self.assertNotIn('gross_earnings', resp.data)
        self.assertNotIn('net_pay', resp.data)
        self.assertNotIn('basic_salary', resp.data)
        self.assertNotIn('pan', resp.data)
        self.assertNotIn('bank_account', resp.data)

        # Invalid token
        bad_resp = self.client.get('/api/v1/payroll/payslips/verify/00000000-0000-0000-0000-000000000000/')
        self.assertEqual(bad_resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(bad_resp.data['valid'])

    def test_employee_self_service_and_idor_protection(self):
        issue_payslips_for_period(self.period_a, requesting_user=self.admin_a)
        ps1 = Payslip.objects.get(payroll_record=self.rec1)
        ps2 = Payslip.objects.get(payroll_record=self.rec2)

        # Authenticate as Alice (emp1)
        self.client.force_authenticate(user=self.user_emp1)

        # Alice retrieves own list (/my/)
        my_resp = self.client.get('/api/v1/payroll/payslips/my/')
        self.assertEqual(my_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(my_resp.data), 1)
        self.assertEqual(my_resp.data[0]['payslip_number'], ps1.payslip_number)

        # Alice retrieves own payslip detail
        det_resp = self.client.get(f'/api/v1/payroll/payslips/{ps1.id}/')
        self.assertEqual(det_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(det_resp.data['financials']['net_salary'], '60000.00')

        # Alice downloads own PDF
        pdf_resp = self.client.get(f'/api/v1/payroll/payslips/{ps1.id}/pdf/')
        self.assertEqual(pdf_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(pdf_resp['Content-Type'], 'application/pdf')

        # IDOR Attempt: Alice tries to access Bob's payslip
        idor_resp = self.client.get(f'/api/v1/payroll/payslips/{ps2.id}/')
        self.assertEqual(idor_resp.status_code, status.HTTP_404_NOT_FOUND)

        # IDOR Attempt: Alice tries to download Bob's PDF
        idor_pdf_resp = self.client.get(f'/api/v1/payroll/payslips/{ps2.id}/pdf/')
        self.assertEqual(idor_pdf_resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_tenant_isolation(self):
        issue_payslips_for_period(self.period_a, requesting_user=self.admin_a)
        ps1 = Payslip.objects.get(payroll_record=self.rec1)

        # Admin of Org B attempts to access Org A's payslip
        self.client.force_authenticate(user=self.admin_b)
        resp = self.client.get(f'/api/v1/payroll/payslips/{ps1.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        pdf_resp = self.client.get(f'/api/v1/payroll/payslips/{ps1.id}/pdf/')
        self.assertEqual(pdf_resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_api_issue_endpoints_and_audit(self):
        self.client.force_authenticate(user=self.admin_a)

        # Issue via period action: POST /api/v1/payroll/periods/<id>/issue-payslips/
        resp = self.client.post(f'/api/v1/payroll/periods/{self.period_a.id}/issue-payslips/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 2)

        # Verify audit logs created
        issued_logs = AuditLog.objects.filter(action='PAYSLIP_ISSUED', organization=self.org_a)
        self.assertEqual(issued_logs.count(), 2)

        # Download PDF and verify audit log
        ps1 = Payslip.objects.get(payroll_record=self.rec1)
        pdf_resp = self.client.get(f'/api/v1/payroll/payslips/{ps1.id}/pdf/')
        self.assertEqual(pdf_resp.status_code, status.HTTP_200_OK)

        download_logs = AuditLog.objects.filter(action='PAYSLIP_PDF_DOWNLOADED', target_id=ps1.id)
        self.assertEqual(download_logs.count(), 1)
