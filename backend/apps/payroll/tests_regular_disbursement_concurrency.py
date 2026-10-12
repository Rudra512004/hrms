import threading
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from django.db import connection, IntegrityError
from rest_framework.test import APIClient

from apps.organization.models import Organization, Branch, Department, Designation
from apps.employees.models import Employee, EmployeeStatutoryAndBank, EmploymentStatus
from apps.authorization.models import Role, Permission, RolePermission, UserRole, ScopeChoices
from apps.payroll.models import (
    PayrollPeriod,
    PayrollRecord,
    OrganizationBankAccount,
    DisbursementBatch,
    DisbursementItem,
    FinalSettlement,
    SettlementLine,
)
from apps.payroll.disbursement_service import DisbursementService, DisbursementException

User = get_user_model()


class RegularPayrollDisbursementConcurrencyTests(TransactionTestCase):
    """
    Focused financial integrity test suite for regular payroll disbursement
    concurrency, locking, database uniqueness constraints, and error handling.
    """

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        # Tenant A
        self.org_a = Organization.objects.create(name="BeyondSure Tech Ltd", code="BST")
        self.branch_a1 = Branch.objects.create(
            organization=self.org_a,
            name="Bangalore HQ",
            city="Bangalore",
            state="Karnataka",
            postal_code="560001",
        )
        self.branch_a2 = Branch.objects.create(
            organization=self.org_a,
            name="Mumbai Regional",
            city="Mumbai",
            state="Maharashtra",
            postal_code="400001",
        )
        self.dept_a = Department.objects.create(branch=self.branch_a1, name="Engineering")
        self.desig_a = Designation.objects.create(organization=self.org_a, name="Engineer")

        # Tenant B (for cross-tenant checks)
        self.org_b = Organization.objects.create(name="Other Corp Ltd", code="OTH")
        self.branch_b = Branch.objects.create(
            organization=self.org_b,
            name="Delhi Branch",
            city="Delhi",
            state="Delhi",
            postal_code="110001",
        )

        # Users Org A
        self.maker_a = User.objects.create_user(
            email="maker_a@bst.com", password="Password123!", status="active"
        )
        self.maker_emp_a = Employee.objects.create(
            user=self.maker_a,
            organization=self.org_a,
            branch=self.branch_a1,
            employee_code="MKR-001",
            employment_status=EmploymentStatus.ACTIVE,
        )

        self.checker_a = User.objects.create_user(
            email="checker_a@bst.com", password="Password123!", status="active"
        )
        self.checker_emp_a = Employee.objects.create(
            user=self.checker_a,
            organization=self.org_a,
            branch=self.branch_a1,
            employee_code="CHK-001",
            employment_status=EmploymentStatus.ACTIVE,
        )

        # User Org B
        self.user_b = User.objects.create_user(
            email="admin@other.com", password="Password123!", status="active"
        )
        self.emp_b = Employee.objects.create(
            user=self.user_b,
            organization=self.org_b,
            branch=self.branch_b,
            employee_code="OTH-001",
            employment_status=EmploymentStatus.ACTIVE,
        )

        # Employee 1 in Branch A1
        self.user_e1 = User.objects.create_user(
            email="emp1@bst.com", password="Password123!", first_name="Emp", last_name="One", status="active"
        )
        self.emp1 = Employee.objects.create(
            user=self.user_e1,
            organization=self.org_a,
            branch=self.branch_a1,
            department=self.dept_a,
            designation=self.desig_a,
            employee_code="EMP-101",
            joining_date=date(2025, 1, 1),
            employment_status=EmploymentStatus.ACTIVE,
        )
        EmployeeStatutoryAndBank.objects.create(
            employee=self.emp1,
            bank_name="HDFC Bank",
            account_name="Emp One",
            account_number="50100112233445",
            ifsc_code="HDFC0001234",
            payment_mode="BANK_TRANSFER",
        )

        # Employee 2 in Branch A2
        self.user_e2 = User.objects.create_user(
            email="emp2@bst.com", password="Password123!", first_name="Emp", last_name="Two", status="active"
        )
        self.emp2 = Employee.objects.create(
            user=self.user_e2,
            organization=self.org_a,
            branch=self.branch_a2,
            designation=self.desig_a,
            employee_code="EMP-102",
            joining_date=date(2025, 1, 1),
            employment_status=EmploymentStatus.ACTIVE,
        )
        EmployeeStatutoryAndBank.objects.create(
            employee=self.emp2,
            bank_name="ICICI Bank",
            account_name="Emp Two",
            account_number="00020155667788",
            ifsc_code="ICIC0000002",
            payment_mode="BANK_TRANSFER",
        )

        # Corporate Debit Accounts
        self.debit_a = OrganizationBankAccount.objects.create(
            organization=self.org_a,
            bank_name="HDFC Corporate",
            account_number="999888777666",
            ifsc_code="HDFC0001234",
            account_name="BeyondSure Tech Ltd",
            is_active=True,
            is_primary=True,
        )
        self.debit_b = OrganizationBankAccount.objects.create(
            organization=self.org_b,
            bank_name="SBI Corporate",
            account_number="111222333444",
            ifsc_code="SBIN0001234",
            account_name="Other Corp Ltd",
            is_active=True,
            is_primary=True,
        )

        # Finalized Payroll Period 1 (Oct 2026)
        self.period_oct = PayrollPeriod.objects.create(
            organization=self.org_a,
            year=2026,
            month=10,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            status=PayrollPeriod.STATUS_FINALIZED,
        )
        PayrollRecord.objects.create(
            period=self.period_oct,
            employee=self.emp1,
            basic_salary=Decimal("50000.00"),
            gross_salary=Decimal("50000.00"),
            net_salary=Decimal("45000.00"),
            working_days=22,
            present_days=22,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal("22.0"),
            status=PayrollRecord.STATUS_FINALIZED,
        )
        PayrollRecord.objects.create(
            period=self.period_oct,
            employee=self.emp2,
            basic_salary=Decimal("60000.00"),
            gross_salary=Decimal("60000.00"),
            net_salary=Decimal("55000.00"),
            working_days=22,
            present_days=22,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal("22.0"),
            status=PayrollRecord.STATUS_FINALIZED,
        )

        # Finalized Payroll Period 2 (Nov 2026)
        self.period_nov = PayrollPeriod.objects.create(
            organization=self.org_a,
            year=2026,
            month=11,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
            status=PayrollPeriod.STATUS_FINALIZED,
        )
        PayrollRecord.objects.create(
            period=self.period_nov,
            employee=self.emp1,
            basic_salary=Decimal("50000.00"),
            gross_salary=Decimal("50000.00"),
            net_salary=Decimal("45000.00"),
            working_days=22,
            present_days=22,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal("22.0"),
            status=PayrollRecord.STATUS_FINALIZED,
        )

    # =========================================================================
    # TEST 1: SEQUENTIAL DUPLICATE PREPARATION
    # =========================================================================
    def test_sequential_duplicate_preparation_prevented(self):
        """Preparing the same regular payroll batch twice sequentially raises DUPLICATE_DISBURSEMENT_BATCH."""
        batch1 = DisbursementService.prepare_disbursement_batch(
            period=self.period_oct,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        self.assertIsNotNone(batch1)
        self.assertEqual(batch1.status, DisbursementBatch.STATUS_DRAFT)

        # Attempt second preparation for same period
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_disbursement_batch(
                period=self.period_oct,
                user=self.maker_a,
                value_date=date(2026, 10, 31),
            )
        self.assertEqual(ctx.exception.code, "DUPLICATE_DISBURSEMENT_BATCH")
        self.assertIn("already exists", ctx.exception.message)

        # Exactly 1 active batch exists
        active_batches = DisbursementBatch.objects.filter(
            organization=self.org_a, period=self.period_oct
        ).exclude(status="cancelled")
        self.assertEqual(active_batches.count(), 1)

    # =========================================================================
    # TEST 2: CONCURRENT PREPARATION (RACE CONDITION PREVENTION)
    # =========================================================================
    def test_concurrent_preparation_serialized_and_prevents_duplicate(self):
        """
        Two concurrent preparation attempts for the same payroll period must not
        create two active batches. Tested via deterministic threading barrier against PostgreSQL.
        """
        barrier = threading.Barrier(2)
        successes = []
        errors = []

        def worker():
            connection.close()  # Ensure separate thread connection
            try:
                barrier.wait(timeout=5)
                batch = DisbursementService.prepare_disbursement_batch(
                    period=self.period_oct,
                    user=self.maker_a,
                    value_date=date(2026, 10, 31),
                )
                successes.append(batch.id)
            except Exception as e:
                errors.append(e)
            finally:
                connection.close()

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)

        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        # Exactly 1 thread must succeed, and 1 must receive DUPLICATE_DISBURSEMENT_BATCH
        self.assertEqual(len(successes), 1, f"Expected 1 success, got {len(successes)}: {successes}")
        self.assertEqual(len(errors), 1, f"Expected 1 error, got {len(errors)}: {errors}")
        self.assertIsInstance(errors[0], DisbursementException)
        self.assertEqual(errors[0].code, "DUPLICATE_DISBURSEMENT_BATCH")

        # In DB, exactly 1 batch exists
        total_batches = DisbursementBatch.objects.filter(
            organization=self.org_a, period=self.period_oct
        ).count()
        self.assertEqual(total_batches, 1)

    # =========================================================================
    # TEST 3: CANCELLATION AND RE-PREPARATION
    # =========================================================================
    def test_cancellation_permits_re_preparation(self):
        """Cancelling an active regular batch allows preparing a new batch for the period."""
        batch1 = DisbursementService.prepare_disbursement_batch(
            period=self.period_oct,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        self.assertEqual(batch1.status, DisbursementBatch.STATUS_DRAFT)

        # Cancel the draft batch
        cancelled_batch = DisbursementService.cancel_disbursement_batch(
            batch=batch1, user=self.maker_a, reason="Incorrect value date"
        )
        self.assertEqual(cancelled_batch.status, DisbursementBatch.STATUS_CANCELLED)

        # Re-preparation must now succeed
        batch2 = DisbursementService.prepare_disbursement_batch(
            period=self.period_oct,
            user=self.maker_a,
            value_date=date(2026, 11, 2),
        )
        self.assertEqual(batch2.status, DisbursementBatch.STATUS_DRAFT)
        self.assertNotEqual(batch1.id, batch2.id)

        # Verify DB state: exactly 1 cancelled batch and 1 active batch
        all_batches = DisbursementBatch.objects.filter(
            organization=self.org_a, period=self.period_oct
        )
        self.assertEqual(all_batches.count(), 2)
        self.assertEqual(all_batches.filter(status=DisbursementBatch.STATUS_CANCELLED).count(), 1)
        self.assertEqual(all_batches.filter(status=DisbursementBatch.STATUS_DRAFT).count(), 1)

    # =========================================================================
    # TEST 4: DIFFERENT PERIODS AND BRANCHES REMAIN INDEPENDENT
    # =========================================================================
    def test_different_periods_and_branches_remain_independent(self):
        """
        Batches for different periods and separate branches can be prepared independently
        where permitted by business rules.
        """
        # Batch for Period 1 (Oct) - Branch A1
        batch_oct_b1 = DisbursementService.prepare_disbursement_batch(
            period=self.period_oct,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
            branch=self.branch_a1,
        )
        self.assertEqual(batch_oct_b1.branch, self.branch_a1)

        # Batch for Period 1 (Oct) - Branch A2 (Independent branch)
        batch_oct_b2 = DisbursementService.prepare_disbursement_batch(
            period=self.period_oct,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
            branch=self.branch_a2,
        )
        self.assertEqual(batch_oct_b2.branch, self.branch_a2)
        self.assertNotEqual(batch_oct_b1.id, batch_oct_b2.id)

        # Batch for Period 2 (Nov) - Independent period
        batch_nov = DisbursementService.prepare_disbursement_batch(
            period=self.period_nov,
            user=self.maker_a,
            value_date=date(2026, 11, 30),
        )
        self.assertEqual(batch_nov.period, self.period_nov)

        # Attempting duplicate for Branch A1 in Oct is blocked
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_disbursement_batch(
                period=self.period_oct,
                user=self.maker_a,
                value_date=date(2026, 10, 31),
                branch=self.branch_a1,
            )
        self.assertEqual(ctx.exception.code, "DUPLICATE_DISBURSEMENT_BATCH")

    # =========================================================================
    # TEST 5: FNF COMPATIBILITY
    # =========================================================================
    def test_fnf_compatibility_and_mutual_independence(self):
        """Regular payroll constraint does not break or interfere with FnF disbursement batches."""
        # Active regular batch
        reg_batch = DisbursementService.prepare_disbursement_batch(
            period=self.period_oct,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )

        # Create an exit employee and finalized FnF settlement
        exit_user = User.objects.create_user(email="exit@bst.com", password="P!", status="active")
        exit_emp = Employee.objects.create(
            user=exit_user,
            organization=self.org_a,
            branch=self.branch_a1,
            employee_code="EXIT-999",
            joining_date=date(2024, 1, 1),
            exit_date=date(2026, 10, 15),
            employment_status=EmploymentStatus.EXITED,
        )
        EmployeeStatutoryAndBank.objects.create(
            employee=exit_emp,
            bank_name="Axis Bank",
            account_number="912010044556677",
            ifsc_code="UTIB0000123",
            payment_mode="BANK_TRANSFER",
        )

        settlement = FinalSettlement.objects.create(
            organization=self.org_a,
            employee=exit_emp,
            settlement_number="FNF-202610-EXIT999",
            exit_date=date(2026, 10, 15),
            status=FinalSettlement.STATUS_FINALIZED,
            total_earnings=Decimal("25000.00"),
            total_deductions=Decimal("0.00"),
            total_recoveries=Decimal("0.00"),
            net_settlement_amount=Decimal("25000.00"),
            created_by=self.maker_a,
        )
        SettlementLine.objects.create(
            settlement=settlement,
            category=SettlementLine.CATEGORY_EARNING,
            code="GRATUITY",
            name="Gratuity",
            amount=Decimal("25000.00"),
            calculation_basis="Tenure",
            order=1,
        )

        # FnF disbursement preparation succeeds alongside regular batch
        fnf_batch = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=settlement,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        self.assertEqual(fnf_batch.batch_type, DisbursementBatch.BATCH_TYPE_FNF)
        self.assertEqual(fnf_batch.final_settlement, settlement)
        self.assertEqual(reg_batch.batch_type, DisbursementBatch.BATCH_TYPE_REGULAR)

        # FnF duplicate prevention still works
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_fnf_disbursement_batch(
                settlement=settlement,
                user=self.maker_a,
                value_date=date(2026, 10, 31),
            )
        self.assertEqual(ctx.exception.code, "DUPLICATE_DISBURSEMENT_BATCH")

    # =========================================================================
    # TEST 6: ERROR HANDLING & TRANSACTION ROLLBACK
    # =========================================================================
    def test_uniqueness_conflict_produces_clean_error_and_rolls_back_transaction(self):
        """Duplicate conflicts produce a clean application error and do not leave partial batches."""
        DisbursementService.prepare_disbursement_batch(
            period=self.period_oct,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )
        initial_items_count = DisbursementItem.objects.count()

        try:
            DisbursementService.prepare_disbursement_batch(
                period=self.period_oct,
                user=self.maker_a,
                value_date=date(2026, 10, 31),
            )
        except DisbursementException as exc:
            self.assertEqual(exc.code, "DUPLICATE_DISBURSEMENT_BATCH")

        # Verify no orphaned items were created
        self.assertEqual(DisbursementItem.objects.count(), initial_items_count)

        # Verify the database connection and transaction remain usable
        recheck_count = DisbursementBatch.objects.filter(period=self.period_oct).count()
        self.assertEqual(recheck_count, 1)

    # =========================================================================
    # TEST 7: AUTHORIZATION AND TENANT ISOLATION
    # =========================================================================
    def test_authorization_and_cross_tenant_isolation(self):
        """Cannot prepare disbursement using debit account from another tenant."""
        with self.assertRaises(DisbursementException) as ctx:
            DisbursementService.prepare_disbursement_batch(
                period=self.period_oct,
                user=self.maker_a,
                value_date=date(2026, 10, 31),
                debit_account=self.debit_b,  # Tenant B debit account
            )
        self.assertEqual(ctx.exception.code, "CROSS_TENANT_DEBIT_ACCOUNT")

    # =========================================================================
    # TEST 8: DATABASE CONSTRAINT ENFORCEMENT INDEPENDENT OF APP CHECK
    # =========================================================================
    def test_database_constraint_enforces_invariant_independently(self):
        """
        Verify that even if the application-level duplicate check is bypassed,
        the database UniqueConstraint rejects the second active batch, and
        the service catches IntegrityError and translates it to DUPLICATE_DISBURSEMENT_BATCH.
        """
        # Create first active batch
        DisbursementService.prepare_disbursement_batch(
            period=self.period_oct,
            user=self.maker_a,
            value_date=date(2026, 10, 31),
        )

        # Mock the application-level duplicate filter check to return None (simulating race window)
        with patch.object(
            DisbursementBatch.objects,
            "filter",
            side_effect=lambda *args, **kwargs: (
                DisbursementBatch.objects.none()
                if "status__in" in kwargs and kwargs.get("period") == self.period_oct
                else DisbursementBatch.objects.all().filter(*args, **kwargs)
            ),
        ):
            with self.assertRaises(DisbursementException) as ctx:
                DisbursementService.prepare_disbursement_batch(
                    period=self.period_oct,
                    user=self.maker_a,
                    value_date=date(2026, 10, 31),
                )
            self.assertEqual(ctx.exception.code, "DUPLICATE_DISBURSEMENT_BATCH")

        # Direct database insert of duplicate active regular batch raises IntegrityError
        with self.assertRaises(IntegrityError):
            DisbursementBatch.objects.create(
                organization=self.org_a,
                batch_type=DisbursementBatch.BATCH_TYPE_REGULAR,
                period=self.period_oct,
                branch=None,
                batch_number="DISB-DUP-TEST-001",
                debit_account=self.debit_a,
                debit_account_number=self.debit_a.account_number,
                value_date=date(2026, 10, 31),
                status=DisbursementBatch.STATUS_DRAFT,
            )
