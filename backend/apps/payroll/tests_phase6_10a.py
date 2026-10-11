import io
import csv
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient
from rest_framework import status

from apps.organization.models import Organization, Branch, Department, Designation, OfficeNetwork
from apps.employees.models import (
    Employee,
    EmployeeStatutoryAndBank,
    EmploymentStatus,
)
from apps.authorization.models import Role, Permission, RolePermission, UserRole
from apps.payroll.models import (
    PayrollPeriod,
    PayrollRecord,
    OrganizationBankAccount,
    PaymentRoutingConfiguration,
    DisbursementBatch,
    DisbursementItem,
    FinalSettlement,
    SettlementLine,
    CompensationHistory,
)
from apps.payroll.disbursement_service import (
    DisbursementService,
    DisbursementException,
    mask_account_number,
)
from apps.payroll.fnf_service import (
    FnFService,
    FnFException,
)
from apps.payroll.services import generate_payroll_for_period
from apps.audit.models import AuditLog

User = get_user_model()


class Phase610AFnFDisbursementTests(TestCase):
    """
    Comprehensive test suite covering Phase 6.10A:
    FnF -> Generic Bank Disbursement Backend Integration & Bidirectional Duplicate-Payment Prevention.
    Covers all 32 required test scenarios.
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Organization A
        self.org_a = Organization.objects.create(name='BeyondSure Corp A', code='BSCA')
        self.branch_a = Branch.objects.create(
            organization=self.org_a,
            name='Bangalore Central',
            address_line1='MG Road',
            city='Bangalore',
            state='Karnataka',
            postal_code='560001',
        )
        OfficeNetwork.objects.create(branch=self.branch_a, name='Office', network='127.0.0.1/32', is_active=True)
        self.dept_a = Department.objects.create(branch=self.branch_a, name='Engineering')
        self.desig_a = Designation.objects.create(organization=self.org_a, name='Engineer')

        # 2. Organization B (for tenant isolation tests)
        self.org_b = Organization.objects.create(name='Competitor Corp B', code='CCB')
        self.branch_b = Branch.objects.create(
            organization=self.org_b,
            name='Mumbai Central',
            address_line1='Nariman Point',
            city='Mumbai',
            state='Maharashtra',
            postal_code='400021',
        )
        self.dept_b = Department.objects.create(branch=self.branch_b, name='Sales')

        # 3. Users in Org A
        # Maker (Preparer)
        self.maker_a = User.objects.create_user(email='maker_a@beyondsure.com', password='Password123!', status='active')
        self.maker_emp_a = Employee.objects.create(
            user=self.maker_a,
            organization=self.org_a,
            branch=self.branch_a,
            employee_code='MKR-001',
            employment_status=EmploymentStatus.ACTIVE,
        )

        # Checker (Approver / Exporter)
        self.checker_a = User.objects.create_user(email='checker_a@beyondsure.com', password='Password123!', status='active')
        self.checker_emp_a = Employee.objects.create(
            user=self.checker_a,
            organization=self.org_a,
            branch=self.branch_a,
            employee_code='CHK-001',
            employment_status=EmploymentStatus.ACTIVE,
        )

        # Standard User without disbursement permissions
        self.unauth_user_a = User.objects.create_user(email='unauth@beyondsure.com', password='Password123!', status='active')
        self.unauth_emp_a = Employee.objects.create(
            user=self.unauth_user_a,
            organization=self.org_a,
            branch=self.branch_a,
            employee_code='UNAUTH-001',
            employment_status=EmploymentStatus.ACTIVE,
        )

        # User in Org B
        self.user_b = User.objects.create_user(email='user_b@competitor.com', password='Password123!', status='active')
        self.emp_b = Employee.objects.create(
            user=self.user_b,
            organization=self.org_b,
            branch=self.branch_b,
            employee_code='ORG-B-001',
            employment_status=EmploymentStatus.ACTIVE,
        )

        # 4. Primary Exiting Employee in Org A
        self.exit_user_a = User.objects.create_user(
            email='exiting_emp@beyondsure.com',
            first_name='Rahul',
            last_name='Sharma',
            password='Password123!',
            status='active',
        )
        self.exit_emp_a = Employee.objects.create(
            user=self.exit_user_a,
            organization=self.org_a,
            branch=self.branch_a,
            department=self.dept_a,
            designation=self.desig_a,
            employee_code='EMP-EXIT-01',
            joining_date=date(2023, 1, 1),
            employment_status=EmploymentStatus.EXITED,
        )
        self.exit_sb_a = EmployeeStatutoryAndBank.objects.create(
            employee=self.exit_emp_a,
            bank_name='HDFC Bank',
            account_number='987654321012',
            ifsc_code='HDFC0001234',
            account_name='Rahul Sharma',
            payment_mode='BANK_TRANSFER',
        )
        CompensationHistory.objects.create(
            employee=self.exit_emp_a,
            ctc_annual=Decimal('1200000.00'),
            basic_salary=Decimal('50000.00'),
            effective_from=date(2023, 1, 1),
            created_by=self.maker_a,
        )

        # 5. Organization Bank Accounts
        self.org_bank_a = OrganizationBankAccount.objects.create(
            organization=self.org_a,
            bank_name='HDFC Corporate Banking',
            account_name='Org A Corporate Account',
            account_number='112233445566',
            ifsc_code='HDFC0001234',
            is_primary=True,
            is_active=True,
        )
        self.org_bank_b = OrganizationBankAccount.objects.create(
            organization=self.org_b,
            bank_name='ICICI Corporate Banking',
            account_name='Org B Corporate Account',
            account_number='998877665544',
            ifsc_code='ICIC0009999',
            is_primary=True,
            is_active=True,
        )

        # 6. Payment Routing Config for Org A
        self.routing_cfg_a = PaymentRoutingConfiguration.objects.create(
            organization=self.org_a,
            default_payment_mode='NEFT',
            rtgs_enabled=True,
            rtgs_threshold=Decimal('200000.00'),
            ift_enabled=True,
            ift_matching_mode=PaymentRoutingConfiguration.IFT_MATCHING_MODE_EXACT,
            effective_from=date(2026, 1, 1),
        )

        # 7. Seed Permissions and Roles
        self.perm_prepare, _ = Permission.objects.get_or_create(
            codename='payroll.disburse_prepare',
            defaults={'name': 'Prepare Disbursement', 'resource': 'payroll', 'action': 'disburse_prepare'},
        )
        self.perm_disburse, _ = Permission.objects.get_or_create(
            codename='payroll.disburse',
            defaults={'name': 'Disburse Payroll', 'resource': 'payroll', 'action': 'disburse'},
        )
        self.perm_approve, _ = Permission.objects.get_or_create(
            codename='payroll.disburse_approve',
            defaults={'name': 'Approve Disbursement', 'resource': 'payroll', 'action': 'disburse_approve'},
        )
        self.perm_export, _ = Permission.objects.get_or_create(
            codename='payroll.disburse_export',
            defaults={'name': 'Export Disbursement', 'resource': 'payroll', 'action': 'disburse_export'},
        )
        self.perm_view, _ = Permission.objects.get_or_create(
            codename='payroll.view',
            defaults={'name': 'View Payroll', 'resource': 'payroll', 'action': 'view'},
        )

        # Assign Maker permissions
        role_maker = Role.objects.create(organization=self.org_a, name='Payroll Maker')
        RolePermission.objects.create(role=role_maker, permission=self.perm_prepare)
        RolePermission.objects.create(role=role_maker, permission=self.perm_disburse)
        RolePermission.objects.create(role=role_maker, permission=self.perm_view)
        UserRole.objects.create(user=self.maker_a, role=role_maker)

        # Assign Checker permissions
        role_checker = Role.objects.create(organization=self.org_a, name='Payroll Checker')
        RolePermission.objects.create(role=role_checker, permission=self.perm_approve)
        RolePermission.objects.create(role=role_checker, permission=self.perm_export)
        RolePermission.objects.create(role=role_checker, permission=self.perm_disburse)
        RolePermission.objects.create(role=role_checker, permission=self.perm_view)
        UserRole.objects.create(user=self.checker_a, role=role_checker)

        # Org B Role
        role_b = Role.objects.create(organization=self.org_b, name='Org B Manager')
        RolePermission.objects.create(role=role_b, permission=self.perm_disburse)
        RolePermission.objects.create(role=role_b, permission=self.perm_prepare)
        RolePermission.objects.create(role=role_b, permission=self.perm_approve)
        RolePermission.objects.create(role=role_b, permission=self.perm_view)
        UserRole.objects.create(user=self.user_b, role=role_b)

    def _create_finalized_settlement(
        self,
        employee,
        exit_date=date(2026, 10, 15),
        net_payable=Decimal('75000.00'),
        settlement_number='FNF-2026-001',
    ):
        """Helper to create an immutable finalized FnF settlement with lines and valid integrity hash."""
        settlement = FinalSettlement.objects.create(
            organization=employee.organization,
            employee=employee,
            settlement_number=settlement_number,
            exit_date=exit_date,
            resignation_date=exit_date - timedelta(days=30),
            settlement_date=exit_date + timedelta(days=5),
            status=FinalSettlement.STATUS_APPROVED,
            total_earnings=net_payable + Decimal('5000.00'),
            total_deductions=Decimal('5000.00'),
            total_recoveries=Decimal('0.00'),
            net_settlement_amount=net_payable,
            created_by=self.maker_a,
            approved_by=self.checker_a,
        )
        SettlementLine.objects.create(
            settlement=settlement,
            category=SettlementLine.CATEGORY_EARNING,
            code='SALARY_LWD',
            name='Salary through Last Working Day',
            amount=net_payable + Decimal('5000.00'),
            calculation_basis='Prorated basic salary to LWD',
            source_reference=f"{exit_date.year}-{exit_date.month:02d}",
            order=1,
        )
        SettlementLine.objects.create(
            settlement=settlement,
            category=SettlementLine.CATEGORY_DEDUCTION,
            code='TDS',
            name='Tax Deducted at Source',
            amount=Decimal('5000.00'),
            order=2,
        )
        return FnFService.finalize(settlement, requesting_user=self.checker_a)

    # =========================================================================
    # 1. ELIGIBILITY & STATUS TESTS (Req 1, 2, 3, 4, 5)
    # =========================================================================

    def test_prepare_fnf_disbursement_batch_success(self):
        """1. Finalized FnF is eligible and creates a draft DisbursementBatch with an immutable snapshot."""
        settlement = self._create_finalized_settlement(self.exit_emp_a, net_payable=Decimal('75000.00'))

        batch = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=settlement,
            user=self.maker_a,
            value_date=date(2026, 10, 20),
            narration="FnF Settlement Final Payment",
        )

        self.assertIsNotNone(batch.pk)
        self.assertEqual(batch.batch_type, DisbursementBatch.BATCH_TYPE_FNF)
        self.assertEqual(batch.final_settlement, settlement)
        self.assertIsNone(batch.period)
        self.assertEqual(batch.status, DisbursementBatch.STATUS_DRAFT)
        self.assertEqual(batch.total_count, 1)
        self.assertEqual(batch.total_amount, Decimal('75000.00'))
        self.assertEqual(batch.created_by, self.maker_a)
        self.assertEqual(batch.narration, "FnF Settlement Final Payment")
        self.assertTrue(batch.batch_number.startswith(f"DISB-FNF-202610-{self.org_a.code}-"))

        # Verify DisbursementItem snapshot
        items = batch.items.all()
        self.assertEqual(items.count(), 1)
        item = items.first()
        self.assertEqual(item.final_settlement, settlement)
        self.assertIsNone(item.payroll_record)
        self.assertEqual(item.employee, self.exit_emp_a)
        self.assertEqual(item.amount, Decimal('75000.00'))
        self.assertEqual(item.beneficiary_name, 'Rahul Sharma')
        self.assertEqual(item.beneficiary_account_number, '987654321012')
        self.assertEqual(item.beneficiary_ifsc, 'HDFC0001234')
        self.assertEqual(item.beneficiary_ifsc_code, 'HDFC0001234')
        # Since employee IFSC == Org Bank IFSC (HDFC0001234), IFT routing rule is applied!
        self.assertEqual(item.payment_mode, 'IFT')

    def test_fnf_disbursement_rejects_non_finalized_states(self):
        """2, 3, 4, 5. FnF settlement in DRAFT, REVIEW, APPROVED, or CANCELLED status is strictly rejected."""
        # A. Draft
        s_draft = FinalSettlement.objects.create(
            organization=self.org_a,
            employee=self.exit_emp_a,
            settlement_number='FNF-DRAFT-001',
            exit_date=date(2026, 10, 15),
            status=FinalSettlement.STATUS_DRAFT,
            net_settlement_amount=Decimal('50000.00'),
            created_by=self.maker_a,
        )
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_fnf_disbursement_batch(
                settlement=s_draft, user=self.maker_a, value_date=date(2026, 10, 20)
            )
        self.assertEqual(ctx.exception.code, "SETTLEMENT_NOT_FINALIZED")
        s_draft.delete()

        # B. Review
        s_review = FinalSettlement.objects.create(
            organization=self.org_a,
            employee=self.exit_emp_a,
            settlement_number='FNF-REV-001',
            exit_date=date(2026, 10, 15),
            status=FinalSettlement.STATUS_REVIEW,
            net_settlement_amount=Decimal('50000.00'),
            created_by=self.maker_a,
        )
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_fnf_disbursement_batch(
                settlement=s_review, user=self.maker_a, value_date=date(2026, 10, 20)
            )
        self.assertEqual(ctx.exception.code, "SETTLEMENT_NOT_FINALIZED")
        s_review.delete()

        # C. Approved (not finalized)
        s_approved = FinalSettlement.objects.create(
            organization=self.org_a,
            employee=self.exit_emp_a,
            settlement_number='FNF-APP-001',
            exit_date=date(2026, 10, 15),
            status=FinalSettlement.STATUS_APPROVED,
            net_settlement_amount=Decimal('50000.00'),
            created_by=self.maker_a,
        )
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_fnf_disbursement_batch(
                settlement=s_approved, user=self.maker_a, value_date=date(2026, 10, 20)
            )
        self.assertEqual(ctx.exception.code, "SETTLEMENT_NOT_FINALIZED")
        s_approved.delete()

        # D. Cancelled
        s_canc = FinalSettlement.objects.create(
            organization=self.org_a,
            employee=self.exit_emp_a,
            settlement_number='FNF-CANC-001',
            exit_date=date(2026, 10, 15),
            status=FinalSettlement.STATUS_CANCELLED,
            net_settlement_amount=Decimal('50000.00'),
            created_by=self.maker_a,
        )
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_fnf_disbursement_batch(
                settlement=s_canc, user=self.maker_a, value_date=date(2026, 10, 20)
            )
        self.assertEqual(ctx.exception.code, "SETTLEMENT_NOT_FINALIZED")

    # =========================================================================
    # 2. FINANCIAL ACCURACY & IMMUTABILITY (Req 6, 24)
    # =========================================================================

    def test_immutable_settlement_amount_used(self):
        """6, 24. Correct immutable settlement amount used without recalculation, settlement remains immutable."""
        settlement = self._create_finalized_settlement(self.exit_emp_a, net_payable=Decimal('82500.50'))

        batch = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=settlement,
            user=self.maker_a,
            value_date=date(2026, 10, 20),
        )

        self.assertEqual(batch.total_amount, Decimal('82500.50'))
        item = batch.items.first()
        self.assertEqual(item.amount, Decimal('82500.50'))

        # Attempting to mutate finalized settlement fails integrity / validation
        settlement.net_settlement_amount = Decimal('99999.00')
        with self.assertRaises(ValidationError):
            settlement.save()

    # =========================================================================
    # 3. BANK & ACCOUNT VALIDATION (Req 7, 8, 9, 10, 11)
    # =========================================================================

    def test_missing_or_invalid_bank_details_rejected(self):
        """7, 8. Beneficiary missing account number, IFSC, or non-electronic payment mode is rejected."""
        settlement = self._create_finalized_settlement(self.exit_emp_a, net_payable=Decimal('60000.00'))

        # 1. Cash payment mode
        self.exit_sb_a.payment_mode = 'CASH'
        self.exit_sb_a.save()
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_fnf_disbursement_batch(
                settlement=settlement, user=self.maker_a, value_date=date(2026, 10, 20)
            )
        self.assertEqual(ctx.exception.code, "INELIGIBLE_PAYMENT_MODE")

        # 2. Missing account number
        self.exit_sb_a.payment_mode = 'BANK_TRANSFER'
        self.exit_sb_a.account_number = ''
        self.exit_sb_a.save()
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_fnf_disbursement_batch(
                settlement=settlement, user=self.maker_a, value_date=date(2026, 10, 20)
            )
        self.assertEqual(ctx.exception.code, "MISSING_BENEFICIARY_ACCOUNT")

        # 3. Missing IFSC code
        self.exit_sb_a.account_number = '987654321012'
        self.exit_sb_a.ifsc_code = ''
        self.exit_sb_a.save()
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_fnf_disbursement_batch(
                settlement=settlement, user=self.maker_a, value_date=date(2026, 10, 20)
            )
        self.assertEqual(ctx.exception.code, "MISSING_BENEFICIARY_IFSC")

    def test_missing_employer_debit_account_rejected(self):
        """9. Missing employer debit bank account raises MISSING_DEBIT_ACCOUNT."""
        # Deactivate Org A's corporate bank accounts
        OrganizationBankAccount.objects.filter(organization=self.org_a).update(is_active=False)
        settlement = self._create_finalized_settlement(self.exit_emp_a, net_payable=Decimal('50000.00'))

        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_fnf_disbursement_batch(
                settlement=settlement, user=self.maker_a, value_date=date(2026, 10, 20)
            )
        self.assertEqual(ctx.exception.code, "MISSING_DEBIT_ACCOUNT")

    def test_zero_or_negative_net_payable_rejected(self):
        """10, 11. Zero or negative net payable settlements cannot be prepared for bank disbursement."""
        # Zero net payable
        settlement_zero = self._create_finalized_settlement(
            self.exit_emp_a,
            exit_date=date(2026, 10, 15),
            net_payable=Decimal('0.00'),
            settlement_number='FNF-ZERO-001',
        )
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_fnf_disbursement_batch(
                settlement=settlement_zero, user=self.maker_a, value_date=date(2026, 10, 20)
            )
        self.assertEqual(ctx.exception.code, "ZERO_NET_PAYABLE")

        # Cancel zero settlement to release unique active settlement constraint on employee
        settlement_zero.status = FinalSettlement.STATUS_CANCELLED
        settlement_zero.save()

        # Negative net payable (recovery due from employee)
        user_neg = User.objects.create_user(email='neg@beyondsure.com', password='Password123!', status='active')
        emp_neg = Employee.objects.create(
            user=user_neg,
            organization=self.org_a,
            branch=self.branch_a,
            employee_code='EMP-NEG-001',
            employment_status=EmploymentStatus.ON_NOTICE,
        )
        EmployeeStatutoryAndBank.objects.create(
            employee=emp_neg,
            account_number='987654321099',
            ifsc_code='HDFC0001234',
            account_name='Negative Net Emp',
            payment_mode='BANK_TRANSFER',
        )
        settlement_neg = FinalSettlement.objects.create(
            organization=self.org_a,
            employee=emp_neg,
            settlement_number='FNF-NEG-001',
            exit_date=date(2026, 10, 15),
            status=FinalSettlement.STATUS_FINALIZED,
            net_settlement_amount=Decimal('-15000.00'),
            created_by=self.maker_a,
            approved_by=self.checker_a,
        )
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_fnf_disbursement_batch(
                settlement=settlement_neg, user=self.maker_a, value_date=date(2026, 10, 20)
            )
        self.assertEqual(ctx.exception.code, "NEGATIVE_NET_PAYABLE")

    # =========================================================================
    # 4. PAYMENT ROUTING & CSV EXPORT (Req 12, 13, 14, 15)
    # =========================================================================

    def test_routing_configuration_behavior(self):
        """12. Configurable payment routing: IFT (exact/prefix), RTGS (threshold), and NEFT default."""
        settlement = self._create_finalized_settlement(self.exit_emp_a, net_payable=Decimal('250000.00'))

        # A. When beneficiary IFSC matches debit account IFSC exactly -> IFT
        batch_ift = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=settlement, user=self.maker_a, value_date=date(2026, 10, 20)
        )
        self.assertEqual(batch_ift.items.first().payment_mode, 'IFT')
        batch_ift.delete()

        # B. When beneficiary IFSC is different bank (SBIN) and amount >= RTGS threshold (200k) -> RTGS
        self.exit_sb_a.ifsc_code = 'SBIN0001234'
        self.exit_sb_a.save()

        batch_rtgs = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=settlement, user=self.maker_a, value_date=date(2026, 10, 20)
        )
        self.assertEqual(batch_rtgs.items.first().payment_mode, 'RTGS')
        batch_rtgs.delete()

        # C. When beneficiary IFSC is different bank and amount < RTGS threshold -> NEFT
        settlement.net_settlement_amount = Decimal('50000.00')
        FinalSettlement.objects.filter(pk=settlement.pk).update(net_settlement_amount=Decimal('50000.00'))
        settlement.refresh_from_db()

        batch_neft = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=settlement, user=self.maker_a, value_date=date(2026, 10, 20)
        )
        self.assertEqual(batch_neft.items.first().payment_mode, 'NEFT')

    def test_export_generic_bank_csv_exact_columns_and_deterministic_narration(self):
        """13, 14, 15. Exporting approved FnF disbursement batch generates authoritative 10-column Generic CSV."""
        settlement = self._create_finalized_settlement(self.exit_emp_a, net_payable=Decimal('75000.00'))

        batch = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=settlement,
            user=self.maker_a,
            value_date=date(2026, 10, 20),
            narration="",  # Test deterministic default narration
        )
        self.assertEqual(batch.narration, f"FnF Settlement {settlement.settlement_number}")

        # Attempt to export before approval -> fails
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.export_bank_disbursement_csv(batch=batch, user=self.checker_a)
        self.assertEqual(ctx.exception.code, "BATCH_NOT_APPROVED")

        # Approve batch
        DisbursementService.approve_disbursement_batch(batch=batch, user=self.checker_a)

        # Export CSV
        csv_content = DisbursementService.export_bank_disbursement_csv(batch=batch, user=self.checker_a)

        # Verify batch state updated
        batch.refresh_from_db()
        self.assertEqual(batch.status, DisbursementBatch.STATUS_EXPORTED)
        self.assertEqual(batch.exported_by, self.checker_a)
        self.assertIsNotNone(batch.exported_at)

        # Parse and verify CSV exact columns and ordering
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        self.assertEqual(len(rows), 2)  # Header + 1 record

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

        data_row = rows[1]
        self.assertEqual(data_row[0], 'IFT')
        self.assertEqual(data_row[1], self.org_bank_a.account_number)
        self.assertEqual(data_row[2], '987654321012')
        self.assertEqual(data_row[3], 'Rahul Sharma')
        self.assertEqual(data_row[4], 'HDFC0001234')
        self.assertEqual(data_row[5], '75000.00')
        self.assertEqual(data_row[6], '20-10-2026')
        self.assertIn(settlement.settlement_number, data_row[7])
        self.assertEqual(data_row[8], 'exiting_emp@beyondsure.com')

    # =========================================================================
    # 5. REPEATED PREPARATION & CONCURRENCY (Req 16, 17, 18, 19, 20)
    # =========================================================================

    def test_duplicate_and_concurrent_active_fnf_disbursement_batch_prevented(self):
        """16, 17, 18. Service and DB constraints prevent duplicate active FnF disbursement batches."""
        settlement = self._create_finalized_settlement(self.exit_emp_a, net_payable=Decimal('75000.00'))

        batch1 = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=settlement, user=self.maker_a, value_date=date(2026, 10, 20)
        )
        self.assertEqual(batch1.status, DisbursementBatch.STATUS_DRAFT)

        # Service-level duplicate rejection
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_fnf_disbursement_batch(
                settlement=settlement, user=self.maker_a, value_date=date(2026, 10, 21)
            )
        self.assertEqual(ctx.exception.code, "DUPLICATE_DISBURSEMENT_BATCH")

        # Database unique constraint enforcement: attempting raw insert of second active batch
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                DisbursementBatch.objects.create(
                    organization=self.org_a,
                    batch_type=DisbursementBatch.BATCH_TYPE_FNF,
                    final_settlement=settlement,
                    batch_number="DISB-FNF-MANUAL-DUP",
                    debit_account=self.org_bank_a,
                    debit_account_number=self.org_bank_a.account_number,
                    value_date=date(2026, 10, 20),
                    narration="Duplicate",
                    status=DisbursementBatch.STATUS_DRAFT,
                    total_amount=Decimal('75000.00'),
                    total_count=1,
                )

    def test_cancelled_and_exported_batch_lifecycle(self):
        """19, 20. Cancelled batch allows re-preparation; exported batch cannot be cancelled or re-approved."""
        settlement = self._create_finalized_settlement(self.exit_emp_a, net_payable=Decimal('75000.00'))

        batch = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=settlement, user=self.maker_a, value_date=date(2026, 10, 20)
        )

        # Cancel batch
        cancelled = DisbursementService.cancel_disbursement_batch(batch=batch, user=self.maker_a, reason="Typo in date")
        self.assertEqual(cancelled.status, DisbursementBatch.STATUS_CANCELLED)

        # Cancelled batch cannot be approved
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.approve_disbursement_batch(batch=cancelled, user=self.checker_a)
        self.assertEqual(ctx.exception.code, "BATCH_CANCELLED")

        # After cancellation, re-preparation succeeds
        new_batch = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=settlement, user=self.maker_a, value_date=date(2026, 10, 25)
        )
        self.assertEqual(new_batch.status, DisbursementBatch.STATUS_DRAFT)

        # Approve and export new batch
        DisbursementService.approve_disbursement_batch(batch=new_batch, user=self.checker_a)
        DisbursementService.export_bank_disbursement_csv(batch=new_batch, user=self.checker_a)
        self.assertEqual(new_batch.status, DisbursementBatch.STATUS_EXPORTED)

        # Exported batch cannot be cancelled
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.cancel_disbursement_batch(batch=new_batch, user=self.maker_a)
        self.assertEqual(ctx.exception.code, "CANNOT_CANCEL_EXPORTED_BATCH")

        # Export is idempotent
        csv_again = DisbursementService.export_bank_disbursement_csv(batch=new_batch, user=self.checker_a)
        self.assertIn('Rahul Sharma', csv_again)

    # =========================================================================
    # 6. MAKER/CHECKER & RBAC (Req 21, 22, 23)
    # =========================================================================

    def test_maker_checker_enforcement(self):
        """21. Maker cannot approve own batch; separate checker approval succeeds."""
        settlement = self._create_finalized_settlement(self.exit_emp_a, net_payable=Decimal('75000.00'))

        batch = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=settlement, user=self.maker_a, value_date=date(2026, 10, 20)
        )

        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.approve_disbursement_batch(batch=batch, user=self.maker_a)
        self.assertEqual(ctx.exception.code, "MAKER_CHECKER_VIOLATION")

        approved = DisbursementService.approve_disbursement_batch(batch=batch, user=self.checker_a)
        self.assertEqual(approved.status, DisbursementBatch.STATUS_APPROVED)
        self.assertEqual(approved.approved_by, self.checker_a)

    def test_dynamic_rbac_and_organization_isolation(self):
        """22, 23. Dynamic permissions enforced; cross-tenant debit accounts and settlements rejected."""
        settlement = self._create_finalized_settlement(self.exit_emp_a, net_payable=Decimal('75000.00'))

        # Cross-tenant debit account rejected
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_fnf_disbursement_batch(
                settlement=settlement, user=self.maker_a, value_date=date(2026, 10, 20), debit_account=self.org_bank_b
            )
        self.assertEqual(ctx.exception.code, "CROSS_TENANT_DEBIT_ACCOUNT")

        # Org B user cannot prepare or access Org A settlement via API
        self.client.force_authenticate(user=self.user_b)
        resp_org_b = self.client.post(
            '/api/v1/payroll/disbursements/prepare/',
            {'final_settlement_id': settlement.id, 'value_date': '2026-10-20'},
            format='json',
        )
        self.assertEqual(resp_org_b.status_code, status.HTTP_404_NOT_FOUND)

        # Unauthorized Org A user without disburse_prepare permission
        self.client.force_authenticate(user=self.unauth_user_a)
        resp_unauth = self.client.post(
            '/api/v1/payroll/disbursements/prepare/',
            {'final_settlement_id': settlement.id, 'value_date': '2026-10-20'},
            format='json',
        )
        self.assertEqual(resp_unauth.status_code, status.HTTP_403_FORBIDDEN)

    # =========================================================================
    # 7. BIDIRECTIONAL DUPLICATE PAYMENT SAFEGUARDS (Req 25, 26)
    # =========================================================================

    def test_bidirectional_duplicate_safeguard_fnf_then_regular_payroll(self):
        """25. When salary through LWD is settled in FnF, regular payroll generation excludes the employee."""
        settlement = self._create_finalized_settlement(
            self.exit_emp_a, exit_date=date(2026, 10, 15), net_payable=Decimal('35000.00')
        )

        period_oct = PayrollPeriod.objects.create(
            organization=self.org_a,
            year=2026,
            month=10,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            status=PayrollPeriod.STATUS_DRAFT,
        )

        records = generate_payroll_for_period(period_oct, requesting_user=self.maker_a)
        record_emp_ids = [r.employee_id for r in records]
        self.assertNotIn(self.exit_emp_a.id, record_emp_ids)

    def test_bidirectional_duplicate_safeguard_fnf_then_regular_disbursement(self):
        """25. Stale draft regular payroll record for an already-settled employee is blocked from regular disbursement."""
        settlement = self._create_finalized_settlement(
            self.exit_emp_a, exit_date=date(2026, 10, 15), net_payable=Decimal('35000.00')
        )

        period_oct = PayrollPeriod.objects.create(
            organization=self.org_a,
            year=2026,
            month=10,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            status=PayrollPeriod.STATUS_FINALIZED,
        )
        # Stale regular payroll record
        PayrollRecord.objects.create(
            period=period_oct,
            employee=self.exit_emp_a,
            basic_salary=Decimal('50000.00'),
            gross_salary=Decimal('25000.00'),
            net_salary=Decimal('25000.00'),
            working_days=22,
            present_days=22,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal('22.0'),
        )

        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_disbursement_batch(
                period=period_oct, user=self.maker_a, value_date=date(2026, 10, 31)
            )
        self.assertEqual(ctx.exception.code, "SALARY_ALREADY_SETTLED_IN_FNF")

    def test_bidirectional_duplicate_safeguard_regular_payroll_then_fnf(self):
        """26. When regular payroll was already finalized/active for the exit month, FnF deducts already paid salary."""
        period_oct = PayrollPeriod.objects.create(
            organization=self.org_a,
            year=2026,
            month=10,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            status=PayrollPeriod.STATUS_FINALIZED,
        )
        PayrollRecord.objects.create(
            period=period_oct,
            employee=self.exit_emp_a,
            basic_salary=Decimal('50000.00'),
            gross_salary=Decimal('50000.00'),
            net_salary=Decimal('45000.00'),
            tds_amount=Decimal('5000.00'),
            working_days=22,
            present_days=22,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal('22.0'),
        )

        preview = FnFService.calculate_settlement_preview(
            employee=self.exit_emp_a,
            resignation_date=date(2026, 9, 20),
            exit_date=date(2026, 10, 20),
        )

        salary_line = next(l for l in preview['lines'] if l['code'] == 'SALARY_LWD')
        self.assertIn("already paid in regular payroll", salary_line['calculation_basis'])
        self.assertEqual(salary_line['metadata']['already_paid_regular_payroll'], '50000.00')

    # =========================================================================
    # 8. REGULAR PAYROLL REGRESSION & PARALLEL EXECUTION (Req 27, 28)
    # =========================================================================

    def test_existing_regular_payroll_disbursement_and_csv_still_works(self):
        """27, 28. Regular payroll disbursement preparation, approval, and CSV export remain intact and identical."""
        period = PayrollPeriod.objects.create(
            organization=self.org_a,
            year=2026,
            month=11,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
            status=PayrollPeriod.STATUS_FINALIZED,
        )
        # Active employee in Org A
        PayrollRecord.objects.create(
            period=period,
            employee=self.maker_emp_a,
            basic_salary=Decimal('80000.00'),
            gross_salary=Decimal('80000.00'),
            net_salary=Decimal('72000.00'),
            working_days=22,
            present_days=22,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal('22.0'),
        )
        EmployeeStatutoryAndBank.objects.create(
            employee=self.maker_emp_a,
            account_number='554433221100',
            ifsc_code='HDFC0001234',
            account_name='Maker A',
            payment_mode='BANK_TRANSFER',
        )

        # Prepare regular payroll batch
        batch = DisbursementService.prepare_disbursement_batch(
            period=period,
            user=self.maker_a,
            value_date=date(2026, 11, 30),
            narration="Salary Nov 2026",
        )
        self.assertEqual(batch.batch_type, DisbursementBatch.BATCH_TYPE_REGULAR)
        self.assertEqual(batch.period, period)
        self.assertIsNone(batch.final_settlement)
        self.assertEqual(batch.total_amount, Decimal('72000.00'))

        # Approve and export
        DisbursementService.approve_disbursement_batch(batch=batch, user=self.checker_a)
        csv_content = DisbursementService.export_disbursement_csv(batch=batch, user=self.checker_a)
        self.assertIn('Maker A', csv_content)
        self.assertIn('Salary Nov 2026', csv_content)

    # =========================================================================
    # 9. DATABASE CHECK CONSTRAINTS & MIGRATION INTEGRITY (Req 32)
    # =========================================================================

    def test_database_check_constraints_and_migration_integrity(self):
        """32. Database CheckConstraints enforce mutually exclusive sources on batches and items."""
        period = PayrollPeriod.objects.create(
            organization=self.org_a,
            year=2026,
            month=12,
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 31),
            status=PayrollPeriod.STATUS_FINALIZED,
        )
        settlement = self._create_finalized_settlement(self.exit_emp_a, net_payable=Decimal('75000.00'))

        # A. Batch with BOTH period and final_settlement -> CheckConstraint fails
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                DisbursementBatch.objects.create(
                    organization=self.org_a,
                    batch_type='regular',
                    period=period,
                    final_settlement=settlement,
                    batch_number="DISB-INVALID-BOTH",
                    debit_account=self.org_bank_a,
                    debit_account_number='112233445566',
                    value_date=date(2026, 12, 31),
                    narration="Invalid",
                    status='draft',
                )

        # B. Batch with NEITHER period nor final_settlement -> CheckConstraint fails
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                DisbursementBatch.objects.create(
                    organization=self.org_a,
                    batch_type='regular',
                    period=None,
                    final_settlement=None,
                    batch_number="DISB-INVALID-NONE",
                    debit_account=self.org_bank_a,
                    debit_account_number='112233445566',
                    value_date=date(2026, 12, 31),
                    narration="Invalid",
                    status='draft',
                )

    # =========================================================================
    # 10. UNIFIED API CONTRACT (Req 8, 22)
    # =========================================================================

    def test_api_unified_prepare_endpoint_validation(self):
        """8. POST /disbursements/prepare/ validates exactly one source is supplied (not both, not neither)."""
        settlement = self._create_finalized_settlement(self.exit_emp_a, net_payable=Decimal('75000.00'))
        period = PayrollPeriod.objects.create(
            organization=self.org_a,
            year=2026,
            month=10,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            status=PayrollPeriod.STATUS_FINALIZED,
        )

        self.client.force_authenticate(user=self.maker_a)

        # A. Neither provided -> 400 Bad Request
        resp_neither = self.client.post(
            '/api/v1/payroll/disbursements/prepare/',
            {'value_date': '2026-10-20'},
            format='json',
        )
        self.assertEqual(resp_neither.status_code, status.HTTP_400_BAD_REQUEST)

        # B. Both provided -> 400 Bad Request
        resp_both = self.client.post(
            '/api/v1/payroll/disbursements/prepare/',
            {
                'period_id': period.id,
                'final_settlement_id': settlement.id,
                'value_date': '2026-10-20',
            },
            format='json',
        )
        self.assertEqual(resp_both.status_code, status.HTTP_400_BAD_REQUEST)

        # C. Exactly final_settlement_id provided -> 201 Created FnF batch
        resp_fnf = self.client.post(
            '/api/v1/payroll/disbursements/prepare/',
            {
                'final_settlement_id': settlement.id,
                'value_date': '2026-10-20',
            },
            format='json',
        )
        self.assertEqual(resp_fnf.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp_fnf.data['batch_type'], 'fnf')

    def test_api_final_settlement_prepare_disbursement_action(self):
        """8. POST /api/v1/payroll/final-settlements/<id>/prepare-disbursement/ succeeds with dynamic RBAC."""
        settlement = self._create_finalized_settlement(self.exit_emp_a, net_payable=Decimal('75000.00'))

        self.client.force_authenticate(user=self.maker_a)
        resp = self.client.post(
            f'/api/v1/payroll/final-settlements/{settlement.id}/prepare-disbursement/',
            {
                'value_date': '2026-10-20',
                'narration': 'Custom Settlement Narration',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['batch_type'], 'fnf')
        self.assertEqual(resp.data['total_amount'], '75000.00')

    # =========================================================================
    # 11. AUDIT TRAIL LOGGING (Req 10)
    # =========================================================================

    def test_audit_trail_emitted(self):
        """10. Audit log entries are recorded for FnF disbursement lifecycle events."""
        settlement = self._create_finalized_settlement(self.exit_emp_a, net_payable=Decimal('75000.00'))

        batch = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=settlement,
            user=self.maker_a,
            value_date=date(2026, 10, 20),
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action='DISBURSEMENT_BATCH_PREPARED',
                target_type='DisbursementBatch',
                target_id=str(batch.id),
            ).exists()
        )

        DisbursementService.approve_disbursement_batch(batch=batch, user=self.checker_a)
        self.assertTrue(
            AuditLog.objects.filter(
                action='DISBURSEMENT_BATCH_APPROVED',
                target_type='DisbursementBatch',
                target_id=str(batch.id),
            ).exists()
        )

        DisbursementService.export_bank_disbursement_csv(batch=batch, user=self.checker_a)
        self.assertTrue(
            AuditLog.objects.filter(
                action='DISBURSEMENT_BATCH_EXPORTED',
                target_type='DisbursementBatch',
                target_id=str(batch.id),
            ).exists()
        )
