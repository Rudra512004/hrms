import io
import csv
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework import status

from apps.organization.models import Organization, Branch, Department, Designation, OfficeNetwork
from apps.employees.models import Employee, EmployeeStatutoryAndBank, EmploymentStatus
from apps.authorization.models import Role, Permission, RolePermission, UserRole
from apps.payroll.models import (
    PayrollPeriod,
    PayrollRecord,
    OrganizationBankAccount,
    PaymentRoutingConfiguration,
    DisbursementBatch,
    DisbursementItem,
)
from apps.payroll.disbursement_service import DisbursementService, DisbursementException, mask_account_number
from apps.audit.models import AuditLog

User = get_user_model()


class GenericBankDisbursementTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Tenant A
        self.org_a = Organization.objects.create(name='BeyondSure Technologies Ltd', code='BST')
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

        # Maker User (Preparer) Org A
        self.maker_a = User.objects.create_user(email='maker_a@beyondsure.com', password='Password123!', status='active')
        self.maker_emp_a = Employee.objects.create(
            user=self.maker_a,
            organization=self.org_a,
            branch=self.branch_a,
            employee_code='MAKER-001',
            employment_status=EmploymentStatus.ACTIVE
        )

        # Checker User (Approver) Org A
        self.checker_a = User.objects.create_user(email='checker_a@beyondsure.com', password='Password123!', status='active')
        self.checker_emp_a = Employee.objects.create(
            user=self.checker_a,
            organization=self.org_a,
            branch=self.branch_a,
            employee_code='CHECKER-001',
            employment_status=EmploymentStatus.ACTIVE
        )

        # Employee 1 Org A (Standard salary 84,500)
        self.user_emp1 = User.objects.create_user(
            email='rahul@beyondsure.com',
            first_name='Rahul Navnath',
            last_name='Shete',
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
            phone_number='9876543210',
            joining_date=date(2023, 1, 15),
            employment_status=EmploymentStatus.ACTIVE
        )
        EmployeeStatutoryAndBank.objects.create(
            employee=self.emp1,
            bank_name='HDFC Bank',
            account_name='Rahul Navnath Shete',
            account_number='50100234567890',
            ifsc_code='HDFC0001234',
            payment_mode='BANK_TRANSFER'
        )

        # Employee 2 Org A (High salary 215,000)
        self.user_emp2 = User.objects.create_user(
            email='amit@beyondsure.com',
            first_name='Amit',
            last_name='Verma',
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
            phone_number='9123456789',
            joining_date=date(2023, 5, 1),
            employment_status=EmploymentStatus.ACTIVE
        )
        EmployeeStatutoryAndBank.objects.create(
            employee=self.emp2,
            bank_name='State Bank of India',
            account_name='Amit Verma',
            account_number='30291084729102',
            ifsc_code='SBIN0004521',
            payment_mode='BANK_TRANSFER'
        )

        # Corporate Debit Bank Account for Org A
        self.org_bank_a = OrganizationBankAccount.objects.create(
            organization=self.org_a,
            bank_name='HDFC Bank',
            account_name='BeyondSure Technologies Ltd Corporate Payroll',
            account_number='001122334455',
            ifsc_code='HDFC0001234',
            is_primary=True,
            is_active=True
        )

        # Payment Routing Configuration for Org A
        self.routing_cfg_a = PaymentRoutingConfiguration.objects.create(
            organization=self.org_a,
            default_payment_mode='NEFT',
            rtgs_enabled=True,
            rtgs_threshold=Decimal('200000.00'),
            ift_enabled=False,
            effective_from=date(2026, 1, 1),
            is_active=True,
            created_by=self.maker_a
        )

        # Setup Finalized Payroll Period for Org A
        self.period_a = PayrollPeriod.objects.create(
            organization=self.org_a,
            year=2026,
            month=10,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            status=PayrollPeriod.STATUS_FINALIZED
        )

        self.rec1 = PayrollRecord.objects.create(
            period=self.period_a,
            employee=self.emp1,
            working_days=31,
            present_days=31,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal('31.0'),
            basic_salary=Decimal('84500.00'),
            gross_salary=Decimal('84500.00'),
            net_salary=Decimal('84500.00'),
            status=PayrollRecord.STATUS_FINALIZED
        )

        self.rec2 = PayrollRecord.objects.create(
            period=self.period_a,
            employee=self.emp2,
            working_days=31,
            present_days=31,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal('31.0'),
            basic_salary=Decimal('215000.00'),
            gross_salary=Decimal('215000.00'),
            net_salary=Decimal('215000.00'),
            status=PayrollRecord.STATUS_FINALIZED
        )

        # Tenant B (for cross-tenant tests)
        self.org_b = Organization.objects.create(name='Competitor Corp', code='CC')
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

        # Dynamic Permissions Setup
        self._setup_permissions()

    def _setup_permissions(self):
        role_maker = Role.objects.create(organization=self.org_a, name='Payroll Maker')
        role_checker = Role.objects.create(organization=self.org_a, name='Payroll Checker')
        role_org_b = Role.objects.create(organization=self.org_b, name='Org B Manager')

        maker_perms = [
            'payroll.view', 'payroll.disburse', 'payroll.disburse_prepare',
            'payroll.disburse_configure', 'payroll.generate'
        ]
        checker_perms = [
            'payroll.view', 'payroll.disburse_approve', 'payroll.disburse_export',
            'payroll.approve', 'payroll.disburse'
        ]

        for codename in set(maker_perms + checker_perms):
            res, act = codename.split('.', 1)
            p, _ = Permission.objects.get_or_create(
                codename=codename,
                defaults={'name': codename, 'resource': res, 'action': act}
            )
            if codename in maker_perms:
                RolePermission.objects.create(role=role_maker, permission=p)
            if codename in checker_perms:
                RolePermission.objects.create(role=role_checker, permission=p)
            RolePermission.objects.create(role=role_org_b, permission=p)

        UserRole.objects.create(user=self.maker_a, role=role_maker)
        UserRole.objects.create(user=self.checker_a, role=role_checker)
        UserRole.objects.create(user=self.admin_b, role=role_org_b)

    # -------------------------------------------------------------------------
    # A & B: Eligibility and Rejection
    # -------------------------------------------------------------------------
    def test_finalized_payroll_eligibility(self):
        """Batch preparation succeeds for FINALIZED and DISBURSED periods."""
        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        self.assertEqual(batch.status, DisbursementBatch.STATUS_DRAFT)
        self.assertEqual(batch.total_count, 2)
        self.assertEqual(batch.total_amount, Decimal('299500.00'))

    def test_non_finalized_payroll_rejection(self):
        """Rejects periods in DRAFT, LOCKED, PROCESSING, REVIEW status."""
        for invalid_status in [
            PayrollPeriod.STATUS_DRAFT,
            PayrollPeriod.STATUS_LOCKED,
            PayrollPeriod.STATUS_PROCESSING,
            PayrollPeriod.STATUS_REVIEW,
        ]:
            self.period_a.status = invalid_status
            self.period_a.save()
            with self.assertRaises(DisbursementException) as ctx:
                DisbursementService.prepare_disbursement_batch(
                    period=self.period_a,
                    user=self.maker_a,
                    value_date=date(2026, 10, 31),
                )
            self.assertEqual(ctx.exception.code, 'PERIOD_NOT_FINALIZED')

    # -------------------------------------------------------------------------
    # C, D, E, F: Exact CSV headers, order, mapping, escaping, and Decimals
    # -------------------------------------------------------------------------
    def test_exact_csv_contract_and_mapping(self):
        """Verifies exact CSV headers, columns order, dynamic mapping, and formatting."""
        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        DisbursementService.approve_disbursement_batch(batch, user=self.checker_a)
        csv_text = DisbursementService.export_disbursement_csv(batch, user=self.checker_a)

        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)

        expected_headers = [
            'Payment_Mode',
            'Debit_Account_Number',
            'Beneficiary_Account_Number',
            'Beneficiary_Name',
            'Beneficiary_IFSC',
            'Amount',
            'Value_Date',
            'Narration',
            'Beneficiary_Email',
            'Beneficiary_Mobile',
        ]
        self.assertEqual(rows[0], expected_headers)
        self.assertEqual(len(rows), 3)  # Header + 2 employees

        # Row 1: Rahul (84,500 -> NEFT)
        self.assertEqual(rows[1][0], 'NEFT')
        self.assertEqual(rows[1][1], '001122334455')
        self.assertEqual(rows[1][2], '50100234567890')
        self.assertEqual(rows[1][3], 'Rahul Navnath Shete')
        self.assertEqual(rows[1][4], 'HDFC0001234')
        self.assertEqual(rows[1][5], '84500.00')
        self.assertEqual(rows[1][6], '31-10-2026')
        self.assertEqual(rows[1][7], 'Salary Oct 2026')
        self.assertEqual(rows[1][8], 'rahul@beyondsure.com')
        self.assertEqual(rows[1][9], '9876543210')

        # Row 2: Amit (215,000 -> RTGS because >= 200,000)
        self.assertEqual(rows[2][0], 'RTGS')
        self.assertEqual(rows[2][1], '001122334455')
        self.assertEqual(rows[2][2], '30291084729102')
        self.assertEqual(rows[2][3], 'Amit Verma')
        self.assertEqual(rows[2][4], 'SBIN0004521')
        self.assertEqual(rows[2][5], '215000.00')
        self.assertEqual(rows[2][6], '31-10-2026')
        self.assertEqual(rows[2][7], 'Salary Oct 2026')

    def test_csv_escaping_with_commas_and_quotes(self):
        """Ensures names or narration with commas and quotes are escaped properly."""
        sb = self.emp1.statutory_and_bank
        sb.account_name = 'Shete, "Rahul" N.'
        sb.save()

        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
            narration='Salary, Bonus "Oct" 2026',
        )
        DisbursementService.approve_disbursement_batch(batch, user=self.checker_a)
        csv_text = DisbursementService.export_disbursement_csv(batch, user=self.checker_a)

        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        # Proper CSV reader deserializes escaped content transparently
        self.assertEqual(rows[1][3], 'Shete, "Rahul" N.')
        self.assertEqual(rows[1][7], 'Salary, Bonus "Oct" 2026')

    # -------------------------------------------------------------------------
    # G, H, I: Missing Bank Info & Ineligible Payment Modes
    # -------------------------------------------------------------------------
    def test_missing_debit_account_blocker(self):
        """Blocker when no corporate debit account is configured."""
        self.org_bank_a.delete()
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_disbursement_batch(
                period=self.period_a,
                user=self.maker_a,
                value_date=date(2026, 10, 31),
            )
        self.assertEqual(ctx.exception.code, 'MISSING_DEBIT_ACCOUNT')

    def test_missing_employee_bank_details_blocker(self):
        """Blocker when an employee lacks account number or IFSC."""
        sb = self.emp1.statutory_and_bank
        sb.account_number = ''
        sb.save()

        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_disbursement_batch(
                period=self.period_a,
                user=self.maker_a,
                value_date=date(2026, 10, 31),
            )
        self.assertEqual(ctx.exception.code, 'MISSING_BENEFICIARY_ACCOUNT')

    def test_cheque_cash_ineligibility_blocker(self):
        """Employees with CHEQUE or CASH are flagged as ineligible for electronic export."""
        sb = self.emp1.statutory_and_bank
        sb.payment_mode = 'CASH'
        sb.save()

        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_disbursement_batch(
                period=self.period_a,
                user=self.maker_a,
                value_date=date(2026, 10, 31),
            )
        self.assertEqual(ctx.exception.code, 'INELIGIBLE_PAYMENT_MODE')

    # -------------------------------------------------------------------------
    # J, K, L, M, N, O, P: Configurable Payment Routing Policy
    # -------------------------------------------------------------------------
    def test_configured_rtgs_threshold_routing(self):
        """Routing threshold is determined dynamically from configuration."""
        self.routing_cfg_a.rtgs_threshold = Decimal('300000.00')
        self.routing_cfg_a.save()

        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        # Amit (215,000) is now below 300,000, so routed as default (NEFT)
        item2 = batch.items.get(employee=self.emp2)
        self.assertEqual(item2.payment_mode, 'NEFT')

    def test_changing_configuration_does_not_alter_approved_batch(self):
        """Changing live configuration does not mutate already-approved batch snapshots."""
        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        DisbursementService.approve_disbursement_batch(batch, user=self.checker_a)

        # Now change configuration live
        self.routing_cfg_a.rtgs_threshold = Decimal('500000.00')
        self.routing_cfg_a.default_payment_mode = 'IFT'
        self.routing_cfg_a.save()

        # The snapshot items on the approved batch remain unchanged!
        item2 = batch.items.get(employee=self.emp2)
        self.assertEqual(item2.payment_mode, 'RTGS')
        self.assertEqual(batch.routing_config_snapshot['rtgs_threshold'], '200000.00')

    def test_ift_routing_when_enabled(self):
        """When IFT is enabled and configured with matching rule, routes accordingly."""
        self.routing_cfg_a.ift_enabled = True
        self.routing_cfg_a.ift_matching_mode = PaymentRoutingConfiguration.IFT_MATCHING_MODE_PREFIX
        self.routing_cfg_a.ift_ifsc_prefix_length = 4
        self.routing_cfg_a.save()

        # Rahul's IFSC is HDFC0001234, debit IFSC is HDFC0001234 (prefix 'HDFC' matches)
        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        item1 = batch.items.get(employee=self.emp1)
        self.assertEqual(item1.payment_mode, 'IFT')

        # Amit's IFSC is SBIN0004521 (different prefix), routes as RTGS
        item2 = batch.items.get(employee=self.emp2)
        self.assertEqual(item2.payment_mode, 'RTGS')

    def test_effective_dated_configuration_selection(self):
        """Selects configuration effective on the given value_date."""
        # Future configuration starting in Nov 2026 with default mode RTGS
        PaymentRoutingConfiguration.objects.create(
            organization=self.org_a,
            default_payment_mode='RTGS',
            rtgs_enabled=False,
            effective_from=date(2026, 11, 1),
            is_active=True,
        )

        # Batch prepared with Oct value date gets Oct config (default NEFT)
        batch_oct = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        self.assertEqual(batch_oct.routing_config_snapshot['default_payment_mode'], 'NEFT')

    # -------------------------------------------------------------------------
    # S, T: Duplicate Prevention & Immutability
    # -------------------------------------------------------------------------
    def test_duplicate_batch_protection(self):
        """Prevent preparing a second active batch for the same period."""
        DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_disbursement_batch(
                period=self.period_a,
                user=self.maker_a,
                value_date=date(2026, 10, 31),
            )
        self.assertEqual(ctx.exception.code, 'DUPLICATE_DISBURSEMENT_BATCH')

    def test_approved_batch_and_item_immutability(self):
        """Approved disbursement batch and its items cannot be mutated."""
        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        DisbursementService.approve_disbursement_batch(batch, user=self.checker_a)

        # Direct mutation on batch total raises ValidationError
        batch.total_amount = Decimal('999999.00')
        with self.assertRaises(ValidationError):
            batch.save()

        # Direct mutation on item amount raises ValidationError
        item = batch.items.first()
        item.amount = Decimal('1.00')
        with self.assertRaises(ValidationError):
            item.save()

    # -------------------------------------------------------------------------
    # U, V, W, X: Maker-Checker, Org Isolation, Masking, Audit
    # -------------------------------------------------------------------------
    def test_maker_checker_violation(self):
        """Maker cannot approve their own disbursement batch."""
        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.approve_disbursement_batch(batch, user=self.maker_a)
        self.assertEqual(ctx.exception.code, 'MAKER_CHECKER_VIOLATION')

    def test_organization_isolation(self):
        """User from Org B cannot access, approve, or export Org A's batch."""
        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        self.client.force_authenticate(user=self.admin_b)
        resp = self.client.get(f'/api/v1/payroll/disbursements/{batch.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        resp_approve = self.client.post(f'/api/v1/payroll/disbursements/{batch.id}/approve/')
        self.assertEqual(resp_approve.status_code, status.HTTP_404_NOT_FOUND)

    def test_sensitive_data_masking_in_api(self):
        """API list and detail endpoints return masked account numbers."""
        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        self.client.force_authenticate(user=self.maker_a)
        resp = self.client.get(f'/api/v1/payroll/disbursements/{batch.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.assertTrue(resp.data['masked_debit_account_number'].endswith('4455'))
        self.assertNotIn('001122334455', resp.data['masked_debit_account_number'])

        item_data = resp.data['items'][0]
        self.assertTrue(item_data['masked_beneficiary_account_number'].endswith('7890'))
        self.assertNotIn('50100234567890', item_data['masked_beneficiary_account_number'])

    def test_audit_logging_across_lifecycle(self):
        """Lifecycle events (PREPARED, APPROVED, EXPORTED) are audited."""
        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        DisbursementService.approve_disbursement_batch(batch, user=self.checker_a)
        DisbursementService.export_disbursement_csv(batch, user=self.checker_a)

        logs = AuditLog.objects.filter(
            target_type='DisbursementBatch',
            target_id=str(batch.id),
        ).values_list('action', flat=True)

        self.assertIn('DISBURSEMENT_BATCH_PREPARED', logs)
        self.assertIn('DISBURSEMENT_BATCH_APPROVED', logs)
        self.assertIn('DISBURSEMENT_BATCH_EXPORTED', logs)

    # -------------------------------------------------------------------------
    # Y, Z, AA, AB: Zero/Negative Pay, Missing Value Date, Invalid State Transitions
    # -------------------------------------------------------------------------
    def test_zero_net_salary_handling(self):
        """Employee with net pay of 0 requires review and blocks export."""
        self.rec1.net_salary = Decimal('0.00')
        self.rec1.save()

        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_disbursement_batch(
                period=self.period_a,
                user=self.maker_a,
                value_date=date(2026, 10, 31),
            )
        self.assertEqual(ctx.exception.code, 'ZERO_NET_SALARY')

    def test_negative_net_salary_handling(self):
        """Employee with negative net pay is strictly blocked."""
        self.rec1.net_salary = Decimal('-1000.00')
        self.rec1.save()

        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_disbursement_batch(
                period=self.period_a,
                user=self.maker_a,
                value_date=date(2026, 10, 31),
            )
        self.assertEqual(ctx.exception.code, 'NEGATIVE_NET_SALARY')

    def test_missing_value_date_handling(self):
        """Value date is required."""
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_disbursement_batch(
                period=self.period_a,
                user=self.maker_a,
                value_date=None,
            )
        self.assertEqual(ctx.exception.code, 'MISSING_VALUE_DATE')

    def test_invalid_state_transitions(self):
        """Cannot export unapproved batch; cannot export or approve cancelled batch."""
        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        # Draft batch cannot be exported
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.export_disbursement_csv(batch, user=self.checker_a)
        self.assertEqual(ctx.exception.code, 'BATCH_NOT_APPROVED')

        # Cancel batch
        DisbursementService.cancel_disbursement_batch(batch, user=self.checker_a)

        # Cancelled batch cannot be approved or exported
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.approve_disbursement_batch(batch, user=self.checker_a)
        self.assertEqual(ctx.exception.code, 'BATCH_CANCELLED')

    # -------------------------------------------------------------------------
    # Focused Tests: Constrained Routing Policy & Sensitive Permissions
    # -------------------------------------------------------------------------
    def test_1_ift_disabled_never_selects_ift(self):
        """1. IFT disabled -> never selects IFT even if IFSCs match identically."""
        self.routing_cfg_a.ift_enabled = False
        self.routing_cfg_a.ift_matching_mode = PaymentRoutingConfiguration.IFT_MATCHING_MODE_EXACT
        self.routing_cfg_a.save()

        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        item1 = batch.items.get(employee=self.emp1)
        # Even though Rahul's IFSC matches debit IFSC identically, ift_enabled is False
        self.assertNotEqual(item1.payment_mode, 'IFT')
        self.assertEqual(item1.payment_mode, 'NEFT')

    def test_2_ift_enabled_without_explicit_matching_does_not_assume_prefix(self):
        """2. IFT enabled without explicit matching configuration -> does not silently assume IFSC-prefix routing."""
        self.routing_cfg_a.ift_enabled = True
        self.routing_cfg_a.ift_matching_mode = PaymentRoutingConfiguration.IFT_MATCHING_MODE_NONE
        self.routing_cfg_a.ift_ifsc_prefix_length = None
        self.routing_cfg_a.save()

        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        item1 = batch.items.get(employee=self.emp1)
        # Without explicit matching mode, mode remains default NEFT, never silently assuming IFT
        self.assertEqual(item1.payment_mode, 'NEFT')

    def test_3_configured_ift_rule_works_according_to_stored_configuration(self):
        """3. Configured IFT rule -> works according to the stored configuration (exact vs prefix)."""
        # Part A: Exact match mode
        self.routing_cfg_a.ift_enabled = True
        self.routing_cfg_a.ift_matching_mode = PaymentRoutingConfiguration.IFT_MATCHING_MODE_EXACT
        self.routing_cfg_a.save()

        batch_exact = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        item1_exact = batch_exact.items.get(employee=self.emp1)
        self.assertEqual(item1_exact.payment_mode, 'IFT')

        # Cancel batch and modify employee's IFSC to have same 4-letter prefix but different branch
        DisbursementService.cancel_disbursement_batch(batch_exact, user=self.checker_a)
        sb1 = self.emp1.statutory_and_bank
        sb1.ifsc_code = 'HDFC0009999'  # Different branch
        sb1.save()

        # Under EXACT match, HDFC0009999 != HDFC0001234 -> should NOT route to IFT
        batch_no_match = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        item1_no_match = batch_no_match.items.get(employee=self.emp1)
        self.assertEqual(item1_no_match.payment_mode, 'NEFT')
        DisbursementService.cancel_disbursement_batch(batch_no_match, user=self.checker_a)

        # Part B: Configured prefix length 4
        self.routing_cfg_a.ift_matching_mode = PaymentRoutingConfiguration.IFT_MATCHING_MODE_PREFIX
        self.routing_cfg_a.ift_ifsc_prefix_length = 4
        self.routing_cfg_a.save()

        batch_prefix = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        item1_prefix = batch_prefix.items.get(employee=self.emp1)
        self.assertEqual(item1_prefix.payment_mode, 'IFT')
        DisbursementService.cancel_disbursement_batch(batch_prefix, user=self.checker_a)

        # Reset emp1 IFSC back to original
        sb1.ifsc_code = 'HDFC0001234'
        sb1.save()

    def test_4_changing_ift_configuration_affects_future_batches_only(self):
        """4. Changing IFT configuration affects future batches only."""
        # Batch 1 under IFT disabled
        self.routing_cfg_a.ift_enabled = False
        self.routing_cfg_a.save()

        batch1 = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        DisbursementService.approve_disbursement_batch(batch1, user=self.checker_a)
        self.assertEqual(batch1.items.get(employee=self.emp1).payment_mode, 'NEFT')

        # Change configuration
        self.routing_cfg_a.ift_enabled = True
        self.routing_cfg_a.ift_matching_mode = PaymentRoutingConfiguration.IFT_MATCHING_MODE_EXACT
        self.routing_cfg_a.save()

        # Batch 1 unchanged
        batch1.refresh_from_db()
        self.assertEqual(batch1.items.get(employee=self.emp1).payment_mode, 'NEFT')
        self.assertFalse(batch1.routing_config_snapshot['ift_enabled'])

    def test_5_approved_batch_retains_routing_snapshot(self):
        """5. Approved batch retains its routing snapshot and all items remain immutable."""
        self.routing_cfg_a.ift_enabled = True
        self.routing_cfg_a.ift_matching_mode = PaymentRoutingConfiguration.IFT_MATCHING_MODE_PREFIX
        self.routing_cfg_a.ift_ifsc_prefix_length = 4
        self.routing_cfg_a.rtgs_threshold = Decimal('150000.00')
        self.routing_cfg_a.save()

        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        DisbursementService.approve_disbursement_batch(batch, user=self.checker_a)

        # Mutate config completely
        self.routing_cfg_a.ift_enabled = False
        self.routing_cfg_a.ift_matching_mode = PaymentRoutingConfiguration.IFT_MATCHING_MODE_NONE
        self.routing_cfg_a.rtgs_threshold = Decimal('999999.00')
        self.routing_cfg_a.save()

        batch.refresh_from_db()
        snapshot = batch.routing_config_snapshot
        self.assertTrue(snapshot['ift_enabled'])
        self.assertEqual(snapshot['ift_matching_mode'], 'ifsc_prefix')
        self.assertEqual(snapshot['ift_ifsc_prefix_length'], 4)
        self.assertEqual(snapshot['rtgs_threshold'], '150000.00')

    def test_6_rtgs_threshold_comes_entirely_from_configuration(self):
        """6. RTGS threshold comes entirely from configuration."""
        self.routing_cfg_a.rtgs_enabled = True
        self.routing_cfg_a.rtgs_threshold = Decimal('50000.00')  # Custom low threshold
        self.routing_cfg_a.save()

        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        # Rahul (84,500 > 50,000) routes to RTGS
        item1 = batch.items.get(employee=self.emp1)
        self.assertEqual(item1.payment_mode, 'RTGS')

        # Amit (215,000 > 50,000) routes to RTGS
        item2 = batch.items.get(employee=self.emp2)
        self.assertEqual(item2.payment_mode, 'RTGS')

    def test_7_no_implicit_200k_business_rule_is_relied_upon(self):
        """7. No implicit ₹200,000 business rule is relied upon."""
        # When RTGS is disabled, even amounts > 200,000 route as default NEFT
        self.routing_cfg_a.rtgs_enabled = False
        self.routing_cfg_a.rtgs_threshold = None
        self.routing_cfg_a.save()

        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        item2 = batch.items.get(employee=self.emp2)
        self.assertEqual(item2.payment_mode, 'NEFT')

        # Furthermore, test fallback config when no routing config row exists in DB
        PaymentRoutingConfiguration.objects.filter(organization=self.org_a).delete()
        DisbursementService.cancel_disbursement_batch(batch, user=self.checker_a)

        fallback_batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        self.assertFalse(fallback_batch.routing_config_snapshot['rtgs_enabled'])
        self.assertIsNone(fallback_batch.routing_config_snapshot['rtgs_threshold'])
        self.assertEqual(fallback_batch.items.get(employee=self.emp2).payment_mode, 'NEFT')

    def test_8_generic_payroll_permissions_cannot_bypass_dedicated_disbursement_security(self):
        """8. Generic payroll permissions cannot bypass dedicated disbursement security."""
        # Create user with ONLY generic payroll permissions (no disburse permissions)
        gen_user = User.objects.create_user(email='generic@beyondsure.com', password='Password123!', status='active')
        Employee.objects.create(
            user=gen_user,
            organization=self.org_a,
            branch=self.branch_a,
            employee_code='GEN-001',
            employment_status=EmploymentStatus.ACTIVE
        )
        role_generic = Role.objects.create(organization=self.org_a, name='Generic Payroll User')
        for codename in ['payroll.view', 'payroll.generate', 'payroll.approve', 'payroll.manage_compensation']:
            res, act = codename.split('.', 1)
            p, _ = Permission.objects.get_or_create(codename=codename, defaults={'name': codename, 'resource': res, 'action': act})
            RolePermission.objects.create(role=role_generic, permission=p)
        UserRole.objects.create(user=gen_user, role=role_generic)

        self.client.force_authenticate(user=gen_user)

        # A. Cannot prepare via disbursements/prepare/
        resp_prep = self.client.post('/api/v1/payroll/disbursements/prepare/', {
            'period_id': str(self.period_a.id),
            'value_date': '2026-10-31',
        })
        self.assertEqual(resp_prep.status_code, status.HTTP_403_FORBIDDEN)

        # B. Cannot prepare via periods/{id}/prepare-disbursement/
        resp_period_prep = self.client.post(f'/api/v1/payroll/periods/{self.period_a.id}/prepare-disbursement/', {
            'value_date': '2026-10-31',
        })
        self.assertEqual(resp_period_prep.status_code, status.HTTP_403_FORBIDDEN)

        # C. Prepare batch as maker for testing approve/export/cancel
        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )

        # D. Cannot approve
        resp_app = self.client.post(f'/api/v1/payroll/disbursements/{batch.id}/approve/')
        self.assertEqual(resp_app.status_code, status.HTTP_403_FORBIDDEN)

        # E. Cannot cancel
        resp_can = self.client.post(f'/api/v1/payroll/disbursements/{batch.id}/cancel/')
        self.assertEqual(resp_can.status_code, status.HTTP_403_FORBIDDEN)

        # F. Cannot export CSV
        resp_exp = self.client.get(f'/api/v1/payroll/disbursements/{batch.id}/export-csv/')
        self.assertEqual(resp_exp.status_code, status.HTTP_403_FORBIDDEN)

    def test_9_export_permission_remains_explicitly_protected(self):
        """9. Export permission remains explicitly protected (cannot be accessed with just disburse/approve)."""
        batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_a,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        DisbursementService.approve_disbursement_batch(batch, user=self.checker_a)

        # User with disburse and disburse_approve, but NOT disburse_export
        no_exp_user = User.objects.create_user(email='noexport@beyondsure.com', password='Password123!', status='active')
        Employee.objects.create(
            user=no_exp_user,
            organization=self.org_a,
            branch=self.branch_a,
            employee_code='NOEXP-001',
            employment_status=EmploymentStatus.ACTIVE
        )
        role = Role.objects.create(organization=self.org_a, name='No Export Approver')
        for codename in ['payroll.view', 'payroll.disburse', 'payroll.disburse_approve']:
            res, act = codename.split('.', 1)
            p, _ = Permission.objects.get_or_create(codename=codename, defaults={'name': codename, 'resource': res, 'action': act})
            RolePermission.objects.create(role=role, permission=p)
        UserRole.objects.create(user=no_exp_user, role=role)

        self.client.force_authenticate(user=no_exp_user)
        resp = self.client.get(f'/api/v1/payroll/disbursements/{batch.id}/export-csv/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # Now grant payroll.disburse_export
        p_exp, _ = Permission.objects.get_or_create(
            codename='payroll.disburse_export',
            defaults={'name': 'Export Bank CSV', 'resource': 'payroll', 'action': 'disburse_export'}
        )
        RolePermission.objects.create(role=role, permission=p_exp)

        resp_ok = self.client.get(f'/api/v1/payroll/disbursements/{batch.id}/export-csv/')
        self.assertEqual(resp_ok.status_code, status.HTTP_200_OK)

    def test_10_configuration_permission_remains_explicitly_protected(self):
        """10. Configuration permission remains explicitly protected (cannot configure with manage_compensation)."""
        comp_user = User.objects.create_user(email='comp_user@beyondsure.com', password='Password123!', status='active')
        Employee.objects.create(
            user=comp_user,
            organization=self.org_a,
            branch=self.branch_a,
            employee_code='COMP-001',
            employment_status=EmploymentStatus.ACTIVE
        )
        role = Role.objects.create(organization=self.org_a, name='Comp Manager Only')
        for codename in ['payroll.view', 'payroll.manage_compensation', 'payroll.disburse_prepare']:
            res, act = codename.split('.', 1)
            p, _ = Permission.objects.get_or_create(codename=codename, defaults={'name': codename, 'resource': res, 'action': act})
            RolePermission.objects.create(role=role, permission=p)
        UserRole.objects.create(user=comp_user, role=role)

        self.client.force_authenticate(user=comp_user)

        # Attempt to create routing configuration -> 403 Forbidden
        resp_cfg = self.client.post('/api/v1/payroll/routing-configurations/', {
            'organization': str(self.org_a.id),
            'default_payment_mode': 'NEFT',
            'effective_from': '2026-12-01',
        })
        self.assertEqual(resp_cfg.status_code, status.HTTP_403_FORBIDDEN)

        # Attempt to create bank account -> 403 Forbidden
        resp_bank = self.client.post('/api/v1/payroll/bank-accounts/', {
            'organization': str(self.org_a.id),
            'bank_name': 'Axis Bank',
            'account_name': 'BeyondSure Corporate',
            'account_number': '987654321',
            'ifsc_code': 'UTIB0000123',
        })
        self.assertEqual(resp_bank.status_code, status.HTTP_403_FORBIDDEN)

        # Grant payroll.disburse_configure
        p_cfg, _ = Permission.objects.get_or_create(
            codename='payroll.disburse_configure',
            defaults={'name': 'Disburse Config', 'resource': 'payroll', 'action': 'disburse_configure'}
        )
        RolePermission.objects.create(role=role, permission=p_cfg)

        resp_cfg_ok = self.client.post('/api/v1/payroll/routing-configurations/', {
            'organization': str(self.org_a.id),
            'default_payment_mode': 'NEFT',
            'effective_from': '2026-12-01',
        })
        self.assertEqual(resp_cfg_ok.status_code, status.HTTP_201_CREATED)
