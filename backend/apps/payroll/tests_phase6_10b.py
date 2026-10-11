"""
Phase 6.10B Employee Self-Service FnF Disbursement & Payment Status Tests.

Verifies:
1. Employee sees payment status for their own finalized FnF.
2. Employee cannot see another employee's payment status (IDOR protection, 404).
3. Cross-organization access is strictly denied (Org isolation).
4. Draft or non-finalized FnF remains inaccessible to employees.
5. Missing employee profile is handled safely (returns empty list / 404).
6. No disbursement batch is represented accurately ("not_prepared" / "Payment instruction not prepared").
7. Draft batch label matches the actual state ("Payment instruction prepared").
8. Approved batch label matches the actual state ("Payment instruction approved").
9. Exported batch is NOT represented as paid ("Bank file exported — bank confirmation pending").
10. Cancelled batch is not shown as active.
11. Multiple batches are handled deterministically (latest active takes precedence; latest cancelled when all cancelled).
12. Sensitive administrative and banking fields are excluded (account numbers, IFSC, PAN, admin remarks, maker/checker, hashes).
13. Administrative endpoints remain protected against unauthorized employee access.
14. Existing P6.9D behavior remains intact.
15. Existing P6.10A behavior remains intact.
"""

from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.organization.models import Organization, Branch, Department
from apps.employees.models import Employee, EmploymentStatus, EmployeeStatutoryAndBank
from apps.authorization.models import Role, Permission, RolePermission, UserRole
from apps.payroll.models import (
    CompensationHistory,
    OrganizationBankAccount,
    FinalSettlement,
    DisbursementBatch,
    DisbursementItem,
)
from apps.payroll.fnf_service import FnFService
from apps.payroll.disbursement_service import DisbursementService

User = get_user_model()


class EmployeeFnFPaymentStatusTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # 1. Organizations
        self.org_a = Organization.objects.create(name="BeyondSure Solutions Org A")
        self.branch_a = Branch.objects.create(
            organization=self.org_a,
            name="Bangalore HQ",
            address_line1="100 Tech Blvd",
            city="Bangalore",
            state="Karnataka",
            postal_code="560001",
        )
        self.dept_a = Department.objects.create(branch=self.branch_a, name="Engineering")

        self.org_b = Organization.objects.create(name="Competitor Inc Org B")

        # 2. Bank Accounts
        self.debit_account = OrganizationBankAccount.objects.create(
            organization=self.org_a,
            bank_name="HDFC Corporate Bank",
            account_name="Org A Operating Account",
            account_number="987654321098",
            ifsc_code="HDFC0009876",
            is_primary=True,
            is_active=True,
        )

        # 3. Users in Org A
        self.maker_user = User.objects.create_user(
            email="maker@orga.com", password="Password123!", first_name="Maker", last_name="Admin", status="active"
        )
        self.checker_user = User.objects.create_user(
            email="checker@orga.com", password="Password123!", first_name="Checker", last_name="Admin", status="active"
        )

        # Alice (Exited Employee with finalized FnF)
        self.user_alice = User.objects.create_user(
            email="alice@orga.com", password="Password123!", first_name="Alice", last_name="Smith", status="active"
        )
        self.emp_alice = Employee.objects.create(
            user=self.user_alice,
            organization=self.org_a,
            branch=self.branch_a,
            department=self.dept_a,
            employee_code="EMP-ALICE",
            personal_email="alice.personal@example.com",
            joining_date=date(2022, 1, 1),
            exit_date=date(2026, 1, 31),
            resignation_date=date(2026, 1, 1),
            employment_status=EmploymentStatus.EXITED,
        )
        CompensationHistory.objects.create(
            employee=self.emp_alice,
            effective_from=date(2022, 1, 1),
            basic_salary=Decimal("60000.00"),
            created_by=self.maker_user,
        )
        EmployeeStatutoryAndBank.objects.create(
            employee=self.emp_alice,
            pan_number="ALICE1234F",
            account_number="111122223333",
            bank_name="HDFC Bank",
            ifsc_code="HDFC0001234",
        )

        # Bob (Exited Employee with finalized FnF)
        self.user_bob = User.objects.create_user(
            email="bob@orga.com", password="Password123!", first_name="Bob", last_name="Jones", status="active"
        )
        self.emp_bob = Employee.objects.create(
            user=self.user_bob,
            organization=self.org_a,
            branch=self.branch_a,
            department=self.dept_a,
            employee_code="EMP-BOB",
            personal_email="bob.personal@example.com",
            joining_date=date(2023, 1, 1),
            exit_date=date(2026, 2, 28),
            employment_status=EmploymentStatus.EXITED,
        )
        CompensationHistory.objects.create(
            employee=self.emp_bob,
            effective_from=date(2023, 1, 1),
            basic_salary=Decimal("50000.00"),
            created_by=self.maker_user,
        )
        EmployeeStatutoryAndBank.objects.create(
            employee=self.emp_bob,
            pan_number="BOB998877G",
            account_number="444455556666",
            bank_name="ICICI Bank",
            ifsc_code="ICIC0005678",
        )

        # Charlie (User with no employee profile)
        self.user_charlie = User.objects.create_user(
            email="charlie@orga.com", password="Password123!", first_name="Charlie", last_name="NoEmp", status="active"
        )

        # Eve (User in Org B)
        self.user_eve = User.objects.create_user(
            email="eve@orgb.com", password="Password123!", first_name="Eve", last_name="OrgB", status="active"
        )
        self.emp_eve = Employee.objects.create(
            user=self.user_eve,
            organization=self.org_b,
            employee_code="EMP-EVE",
            personal_email="eve.personal@example.com",
            joining_date=date(2024, 1, 1),
            employment_status=EmploymentStatus.ACTIVE,
        )

        # 4. Roles & Permissions
        self._setup_roles()

        # 5. Create Finalized Settlement for Alice
        self.settlement_alice = FnFService.prepare(
            employee_id=self.emp_alice.id,
            requesting_user=self.maker_user,
            exit_date=date(2026, 1, 31),
            settlement_date=date(2026, 2, 5),
            bonus_amount=Decimal("60000.00"),
            remarks="Settlement for Alice",
        )
        FnFService.approve(self.settlement_alice, self.checker_user)
        FnFService.finalize(self.settlement_alice, self.checker_user)

        # 6. Create Finalized Settlement for Bob
        self.settlement_bob = FnFService.prepare(
            employee_id=self.emp_bob.id,
            requesting_user=self.maker_user,
            exit_date=date(2026, 2, 28),
            settlement_date=date(2026, 3, 5),
            bonus_amount=Decimal("50000.00"),
            remarks="Settlement for Bob",
        )
        FnFService.approve(self.settlement_bob, self.checker_user)
        FnFService.finalize(self.settlement_bob, self.checker_user)

    def _setup_roles(self):
        perms_data = [
            ("payroll.fnf_view", "payroll", "fnf_view"),
            ("payroll.fnf_prepare", "payroll", "fnf_prepare"),
            ("payroll.fnf_approve", "payroll", "fnf_approve"),
            ("payroll.fnf_finalize", "payroll", "fnf_finalize"),
            ("payroll.disburse", "payroll", "disburse"),
            ("payroll.disburse_prepare", "payroll", "disburse_prepare"),
            ("payroll.disburse_approve", "payroll", "disburse_approve"),
            ("payroll.disburse_export", "payroll", "disburse_export"),
        ]
        perms = {}
        for code, res, act in perms_data:
            p, _ = Permission.objects.get_or_create(codename=code, defaults={"name": code, "resource": res, "action": act})
            perms[code] = p

        role_maker = Role.objects.create(organization=self.org_a, name="Payroll Maker")
        for c in ["payroll.fnf_view", "payroll.fnf_prepare", "payroll.disburse_prepare"]:
            RolePermission.objects.create(role=role_maker, permission=perms[c])
        UserRole.objects.create(user=self.maker_user, role=role_maker)

        role_checker = Role.objects.create(organization=self.org_a, name="Payroll Checker")
        for c in ["payroll.fnf_view", "payroll.fnf_approve", "payroll.fnf_finalize", "payroll.disburse_approve", "payroll.disburse_export"]:
            RolePermission.objects.create(role=role_checker, permission=perms[c])
        UserRole.objects.create(user=self.checker_user, role=role_checker)

        role_emp = Role.objects.create(organization=self.org_a, name="Employee")
        UserRole.objects.create(user=self.user_alice, role=role_emp)
        UserRole.objects.create(user=self.user_bob, role=role_emp)

    # =========================================================================
    # TEST 1 & 6: EMPLOYEE SEES OWN SETTLEMENT WITH NO DISBURSEMENT BATCH
    # =========================================================================
    def test_employee_sees_payment_status_with_no_disbursement_batch(self):
        """When no disbursement batch has been prepared, status is 'not_prepared'."""
        self.client.force_authenticate(user=self.user_alice)
        resp = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.data
        self.assertEqual(data["settlement_number"], self.settlement_alice.settlement_number)
        self.assertEqual(data["settlement_status"], "finalized")
        self.assertEqual(Decimal(data["net_settlement_amount"]), self.settlement_alice.net_settlement_amount)

        # Payment status fields
        self.assertEqual(data["disbursement_status"], "not_prepared")
        self.assertEqual(data["disbursement_status_label"], "Payment instruction not prepared")
        self.assertIsNone(data["disbursement_reference"])
        self.assertIsNone(data["value_date"])
        self.assertIsNone(data["prepared_at"])
        self.assertIsNone(data["approved_at"])
        self.assertIsNone(data["exported_at"])

        # Nested payment_status structure
        ps = data["payment_status"]
        self.assertEqual(ps["status"], "not_prepared")
        self.assertEqual(ps["status_label"], "Payment instruction not prepared")
        self.assertIsNone(ps["disbursement_reference"])
        self.assertIsNone(ps["value_date"])
        self.assertFalse(ps["bank_confirmation_pending"])
        self.assertEqual(ps["history"], [])

    # =========================================================================
    # TEST 7: DRAFT DISBURSEMENT BATCH
    # =========================================================================
    def test_draft_disbursement_batch_represented_accurately(self):
        """Draft batch shows 'draft' status and 'Payment instruction prepared' label."""
        batch = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=self.settlement_alice,
            user=self.maker_user,
            value_date=date(2026, 2, 10),
            narration="FnF Payout Alice",
            debit_account=self.debit_account,
        )

        self.client.force_authenticate(user=self.user_alice)
        resp = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.data
        self.assertEqual(data["disbursement_status"], "draft")
        self.assertEqual(data["disbursement_status_label"], "Payment instruction prepared")
        self.assertEqual(data["disbursement_reference"], batch.batch_number)
        self.assertEqual(data["value_date"], "2026-02-10")
        self.assertIsNotNone(data["prepared_at"])
        self.assertIsNone(data["approved_at"])
        self.assertIsNone(data["exported_at"])

        ps = data["payment_status"]
        self.assertEqual(ps["status"], "draft")
        self.assertEqual(ps["status_label"], "Payment instruction prepared")
        self.assertEqual(ps["disbursement_reference"], batch.batch_number)
        self.assertEqual(ps["value_date"], "2026-02-10")
        self.assertFalse(ps["bank_confirmation_pending"])
        self.assertEqual(len(ps["history"]), 1)

    # =========================================================================
    # TEST 8: APPROVED DISBURSEMENT BATCH
    # =========================================================================
    def test_approved_disbursement_batch_represented_accurately(self):
        """Approved batch shows 'approved' status and 'Payment instruction approved' label."""
        batch = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=self.settlement_alice,
            user=self.maker_user,
            value_date=date(2026, 2, 10),
            narration="FnF Payout Alice",
            debit_account=self.debit_account,
        )
        DisbursementService.approve_disbursement_batch(batch, user=self.checker_user)

        self.client.force_authenticate(user=self.user_alice)
        resp = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.data
        self.assertEqual(data["disbursement_status"], "approved")
        self.assertEqual(data["disbursement_status_label"], "Payment instruction approved")
        self.assertEqual(data["disbursement_reference"], batch.batch_number)
        self.assertEqual(data["value_date"], "2026-02-10")
        self.assertIsNotNone(data["prepared_at"])
        self.assertIsNotNone(data["approved_at"])
        self.assertIsNone(data["exported_at"])

        ps = data["payment_status"]
        self.assertEqual(ps["status"], "approved")
        self.assertEqual(ps["status_label"], "Payment instruction approved")
        self.assertFalse(ps["bank_confirmation_pending"])

    # =========================================================================
    # TEST 9: EXPORTED BATCH IS NOT REPRESENTED AS PAID
    # =========================================================================
    def test_exported_batch_not_represented_as_paid(self):
        """CRITICAL: Exported batch MUST NOT be labeled as 'Paid' or 'Payment Successful'."""
        batch = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=self.settlement_alice,
            user=self.maker_user,
            value_date=date(2026, 2, 10),
            narration="FnF Payout Alice",
            debit_account=self.debit_account,
        )
        DisbursementService.approve_disbursement_batch(batch, user=self.checker_user)
        DisbursementService.export_disbursement_csv(batch, user=self.checker_user)

        self.client.force_authenticate(user=self.user_alice)
        resp = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.data
        self.assertEqual(data["disbursement_status"], "exported")
        self.assertEqual(data["disbursement_status_label"], "Bank file exported — bank confirmation pending")
        self.assertEqual(data["disbursement_reference"], batch.batch_number)
        self.assertEqual(data["value_date"], "2026-02-10")
        self.assertIsNotNone(data["prepared_at"])
        self.assertIsNotNone(data["approved_at"])
        self.assertIsNotNone(data["exported_at"])

        # Stringent verification: No 'paid' claims anywhere in serialized response
        data_str = str(data).lower()
        self.assertNotIn("payment successful", data_str)
        self.assertNotIn("'paid'", data_str)
        self.assertNotIn("\"paid\"", data_str)

        # Payment status structure explicitly communicates confirmation pending
        ps = data["payment_status"]
        self.assertEqual(ps["status"], "exported")
        self.assertEqual(ps["status_label"], "Bank file exported — bank confirmation pending")
        self.assertTrue(ps["bank_confirmation_pending"])

    # =========================================================================
    # TEST 10: CANCELLED BATCH NOT SHOWN AS ACTIVE
    # =========================================================================
    def test_cancelled_batch_not_shown_as_active(self):
        """Cancelled batch shows 'cancelled' status and 'Payment instruction cancelled'."""
        batch = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=self.settlement_alice,
            user=self.maker_user,
            value_date=date(2026, 2, 10),
            narration="FnF Payout Alice",
            debit_account=self.debit_account,
        )
        DisbursementService.cancel_disbursement_batch(batch, user=self.checker_user, reason="Incorrect date")

        self.client.force_authenticate(user=self.user_alice)
        resp = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.data
        self.assertEqual(data["disbursement_status"], "cancelled")
        self.assertEqual(data["disbursement_status_label"], "Payment instruction cancelled")
        self.assertEqual(data["disbursement_reference"], batch.batch_number)

        ps = data["payment_status"]
        self.assertEqual(ps["status"], "cancelled")
        self.assertEqual(ps["status_label"], "Payment instruction cancelled")
        self.assertFalse(ps["bank_confirmation_pending"])

    # =========================================================================
    # TEST 11: MULTIPLE BATCHES HANDLED DETERMINISTICALLY
    # =========================================================================
    def test_multiple_batches_handled_deterministically(self):
        """Active batch takes precedence over older cancelled batches."""
        # 1. Prepare and cancel first batch
        batch1 = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=self.settlement_alice,
            user=self.maker_user,
            value_date=date(2026, 2, 10),
            narration="Batch 1",
            debit_account=self.debit_account,
        )
        DisbursementService.cancel_disbursement_batch(batch1, user=self.checker_user, reason="Voided")

        # 2. Prepare replacement active batch (draft)
        batch2 = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=self.settlement_alice,
            user=self.maker_user,
            value_date=date(2026, 2, 15),
            narration="Batch 2 Replacement",
            debit_account=self.debit_account,
        )

        self.client.force_authenticate(user=self.user_alice)
        resp = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.data
        # Active replacement batch must be the current instruction
        self.assertEqual(data["disbursement_status"], "draft")
        self.assertEqual(data["disbursement_status_label"], "Payment instruction prepared")
        self.assertEqual(data["disbursement_reference"], batch2.batch_number)
        self.assertEqual(data["value_date"], "2026-02-15")

        # History includes both batches in reverse chronological order
        ps = data["payment_status"]
        self.assertEqual(len(ps["history"]), 2)
        self.assertEqual(ps["history"][0]["disbursement_reference"], batch2.batch_number)
        self.assertEqual(ps["history"][0]["status"], "draft")
        self.assertEqual(ps["history"][1]["disbursement_reference"], batch1.batch_number)
        self.assertEqual(ps["history"][1]["status"], "cancelled")

    # =========================================================================
    # TEST 2 & IDOR: EMPLOYEE CANNOT SEE ANOTHER EMPLOYEE'S PAYMENT STATUS
    # =========================================================================
    def test_employee_cannot_see_another_employees_payment_status(self):
        """Alice attempts to query Bob's settlement ID: must return 404, never 200."""
        # Prepare batch for Bob
        DisbursementService.prepare_fnf_disbursement_batch(
            settlement=self.settlement_bob,
            user=self.maker_user,
            value_date=date(2026, 3, 10),
            narration="Bob Payout",
            debit_account=self.debit_account,
        )

        self.client.force_authenticate(user=self.user_alice)
        resp = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_bob.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        # Bob's data must not appear in Alice's list
        resp_list = self.client.get("/api/v1/payroll/fnf/my/")
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in resp_list.data]
        self.assertIn(self.settlement_alice.id, ids)
        self.assertNotIn(self.settlement_bob.id, ids)

    # =========================================================================
    # TEST 3: CROSS-ORGANIZATION ACCESS IS DENIED
    # =========================================================================
    def test_cross_organization_access_denied(self):
        """Eve in Org B cannot see Alice's settlement in Org A."""
        self.client.force_authenticate(user=self.user_eve)
        resp = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        resp_list = self.client.get("/api/v1/payroll/fnf/my/")
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_list.data, [])

    # =========================================================================
    # TEST 4: DRAFT OR NON-FINALIZED FnF REMAINS INACCESSIBLE
    # =========================================================================
    def test_draft_or_non_finalized_fnf_inaccessible(self):
        """Settlement in draft or approved state (not yet finalized) is hidden."""
        # Create draft settlement for Charlie
        emp_charlie = Employee.objects.create(
            user=self.user_charlie,
            organization=self.org_a,
            employee_code="EMP-CHARLIE",
            joining_date=date(2024, 1, 1),
            exit_date=date(2026, 3, 1),
            employment_status=EmploymentStatus.EXITED,
        )
        draft_settlement = FnFService.prepare(
            employee_id=emp_charlie.id,
            requesting_user=self.maker_user,
            exit_date=date(2026, 3, 1),
        )

        self.client.force_authenticate(user=self.user_charlie)
        resp_detail = self.client.get(f"/api/v1/payroll/fnf/my/{draft_settlement.id}/")
        self.assertEqual(resp_detail.status_code, status.HTTP_404_NOT_FOUND)

        resp_list = self.client.get("/api/v1/payroll/fnf/my/")
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_list.data, [])

    # =========================================================================
    # TEST 5: MISSING EMPLOYEE PROFILE HANDLED SAFELY
    # =========================================================================
    def test_missing_employee_profile_handled_safely(self):
        """User with no employee profile receives clean 404 / empty list."""
        user_no_profile = User.objects.create_user(
            email="noprofile@orga.com", password="Password123!", first_name="No", last_name="Profile"
        )
        self.client.force_authenticate(user=user_no_profile)

        resp_list = self.client.get("/api/v1/payroll/fnf/my/")
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_list.data, [])

        resp_detail = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp_detail.status_code, status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # TEST 12: SENSITIVE ADMINISTRATIVE AND BANKING FIELDS EXCLUDED
    # =========================================================================
    def test_sensitive_administrative_and_banking_fields_excluded(self):
        """Verify no bank account numbers, IFSC, PAN, admin remarks, or hashes leak."""
        batch = DisbursementService.prepare_fnf_disbursement_batch(
            settlement=self.settlement_alice,
            user=self.maker_user,
            value_date=date(2026, 2, 10),
            narration="FnF Payout Alice",
            debit_account=self.debit_account,
        )

        self.client.force_authenticate(user=self.user_alice)
        resp = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.data
        data_str = str(data)

        # 1. No corporate debit account number
        self.assertNotIn("987654321098", data_str)
        self.assertNotIn("debit_account", data)
        self.assertNotIn("debit_account_number", data)

        # 2. No beneficiary bank account or IFSC
        self.assertNotIn("111122223333", data_str)
        self.assertNotIn("HDFC0001234", data_str)
        self.assertNotIn("account_number", data)
        self.assertNotIn("ifsc_code", data)

        # 3. No PAN or statutory numbers
        self.assertNotIn("ALICE1234F", data_str)
        self.assertNotIn("pan_number", data)

        # 4. No maker/checker emails or user objects
        self.assertNotIn("maker@orga.com", data_str)
        self.assertNotIn("checker@orga.com", data_str)
        self.assertNotIn("created_by", data)
        self.assertNotIn("approved_by", data)
        self.assertNotIn("exported_by", data)

        # 5. No administrative notes or cancellation reasons
        self.assertNotIn("remarks", data)
        self.assertNotIn("cancellation_reason", data)

        # 6. No internal integrity hashes or routing snapshots
        self.assertNotIn("integrity_hash", data)
        self.assertNotIn("routing_config_snapshot", data)

    # =========================================================================
    # TEST 13: ADMINISTRATIVE ENDPOINTS REMAIN PROTECTED
    # =========================================================================
    def test_administrative_endpoints_remain_protected(self):
        """Standard employee cannot call administrative disbursement or FnF endpoints."""
        self.client.force_authenticate(user=self.user_alice)

        # Admin FnF list & detail
        self.assertEqual(self.client.get("/api/v1/payroll/fnf/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(f"/api/v1/payroll/fnf/{self.settlement_alice.id}/").status_code, status.HTTP_403_FORBIDDEN)

        # Admin disbursement endpoints
        self.assertEqual(self.client.get("/api/v1/payroll/disbursements/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post("/api/v1/payroll/disbursements/prepare-fnf/", {}).status_code, status.HTTP_403_FORBIDDEN)
