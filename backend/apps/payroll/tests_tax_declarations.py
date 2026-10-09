from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status

from apps.organization.models import Organization, Branch, Department
from apps.employees.models import Employee, EmploymentStatus
from apps.payroll.models import (
    FinancialYear,
    TaxDeclarationCategory,
    TaxDeclaration,
    InvestmentDeclaration,
    InvestmentProof,
    PayrollPeriod,
    PayrollRecord,
)
from apps.payroll.services_tax import TaxDeclarationService, TaxDeclarationException
from apps.authorization.models import Permission, Role, RolePermission, UserRole, ScopeChoices
from apps.audit.models import AuditLog

User = get_user_model()


class Phase69ATaxDeclarationTests(TestCase):
    """
    Focused acceptance test suite covering requirements 1 through 28 of Phase 6.9A:
    Employee Tax Declaration, Regime Election, Investment Proofs, and RBAC.
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Organizations
        self.org1 = Organization.objects.create(name="BeyondSure Tech Corp")
        self.org2 = Organization.objects.create(name="Competitor Global")

        self.branch1 = Branch.objects.create(
            organization=self.org1,
            name="Bangalore HQ",
            is_active=True,
        )

        # 2. Financial Years
        self.fy24 = FinancialYear.objects.create(
            organization=self.org1,
            name="FY 2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_active=True,
        )
        self.fy25 = FinancialYear.objects.create(
            organization=self.org1,
            name="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            is_active=True,
        )

        # 3. Tax Categories
        self.cat_80c = TaxDeclarationCategory.objects.create(
            organization=self.org1,
            code="80C",
            name="Section 80C Deductions",
            max_limit=Decimal("150000.00"),
            regime_applicability="OLD",
        )
        self.cat_80d = TaxDeclarationCategory.objects.create(
            organization=self.org1,
            code="80D",
            name="Medical Insurance Premium",
            max_limit=Decimal("50000.00"),
            regime_applicability="OLD",
        )
        self.cat_hra = TaxDeclarationCategory.objects.create(
            organization=self.org1,
            code="HRA",
            name="House Rent Allowance Exemption",
            regime_applicability="OLD",
        )

        # 4. Employees & Users
        self.user1 = User.objects.create_user(
            email="emp1@beyondsure.com", password="Password123!", status="active"
        )
        self.emp1 = Employee.objects.create(
            user=self.user1,
            organization=self.org1,
            branch=self.branch1,
            employee_code="EMP-101",
            employment_status=EmploymentStatus.ACTIVE,
        )

        self.user2 = User.objects.create_user(
            email="emp2@beyondsure.com", password="Password123!", status="active"
        )
        self.emp2 = Employee.objects.create(
            user=self.user2,
            organization=self.org1,
            branch=self.branch1,
            employee_code="EMP-102",
            employment_status=EmploymentStatus.ACTIVE,
        )

        # Org 2 Employee (Cross-tenant testing)
        self.user_org2 = User.objects.create_user(
            email="emp_org2@competitor.com", password="Password123!", status="active"
        )
        self.emp_org2 = Employee.objects.create(
            user=self.user_org2,
            organization=self.org2,
            employee_code="COMP-201",
            employment_status=EmploymentStatus.ACTIVE,
        )

        # 5. Reviewer User & RBAC Setup
        self.reviewer_user = User.objects.create_user(
            email="tax_reviewer@beyondsure.com", password="Password123!", status="active"
        )
        self.unauth_user = User.objects.create_user(
            email="unauth@beyondsure.com", password="Password123!", status="active"
        )

        self.reviewer_role = Role.objects.create(
            organization=self.org1,
            name="Tax Compliance Reviewer",
        )
        perm_review, _ = Permission.objects.get_or_create(
            codename="payroll.tax_review",
            defaults={"name": "Review Tax Declarations", "resource": "payroll", "action": "tax_review"},
        )
        perm_view, _ = Permission.objects.get_or_create(
            codename="payroll.tax_view",
            defaults={"name": "View Tax Declarations", "resource": "payroll", "action": "tax_view"},
        )
        RolePermission.objects.create(role=self.reviewer_role, permission=perm_review)
        RolePermission.objects.create(role=self.reviewer_role, permission=perm_view)

        UserRole.objects.create(
            user=self.reviewer_user,
            role=self.reviewer_role,
            scope=ScopeChoices.ORGANIZATION,
        )

    # =========================================================================
    # PART 1: DECLARATION TESTS (1 - 11)
    # =========================================================================

    def test_01_employee_creates_declaration(self):
        """1. Employee successfully creates a draft tax declaration."""
        self.client.force_authenticate(user=self.user1)
        resp = self.client.post("/api/v1/payroll/tax/declarations/", {
            "financial_year_id": self.fy24.id,
            "tax_regime": "NEW",
            "notes": "Initial election",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "draft")
        self.assertEqual(resp.data["tax_regime"], "NEW")
        self.assertEqual(resp.data["employee_code"], "EMP-101")

    def test_02_employee_retrieves_own_declaration(self):
        """2. Employee retrieves their own declarations via /my/ endpoint."""
        TaxDeclaration.objects.create(
            organization=self.org1,
            employee=self.emp1,
            financial_year=self.fy24,
            tax_regime="NEW",
            status="draft",
        )
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get("/api/v1/payroll/tax/declarations/my/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["employee_code"], "EMP-101")

    def test_03_employee_cannot_retrieve_another_employee_declaration_idor(self):
        """3. Employee A cannot access Employee B's declaration by ID (IDOR prevention)."""
        dec2 = TaxDeclaration.objects.create(
            organization=self.org1,
            employee=self.emp2,
            financial_year=self.fy24,
            tax_regime="OLD",
            status="draft",
        )
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get(f"/api/v1/payroll/tax/declarations/{dec2.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_04_employee_cannot_modify_another_employee_declaration(self):
        """4. Employee A cannot patch/modify Employee B's declaration."""
        dec2 = TaxDeclaration.objects.create(
            organization=self.org1,
            employee=self.emp2,
            financial_year=self.fy24,
            tax_regime="NEW",
            status="draft",
        )
        self.client.force_authenticate(user=self.user1)
        resp = self.client.patch(f"/api/v1/payroll/tax/declarations/{dec2.id}/", {
            "tax_regime": "OLD",
        })
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_05_employee_can_select_old_regime(self):
        """5. Employee can explicitly elect the Old Tax Regime."""
        self.client.force_authenticate(user=self.user1)
        resp = self.client.post("/api/v1/payroll/tax/declarations/", {
            "financial_year_id": self.fy24.id,
            "tax_regime": "OLD",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["tax_regime"], "OLD")

    def test_06_employee_can_select_new_regime(self):
        """6. Employee can elect the New Tax Regime."""
        self.client.force_authenticate(user=self.user1)
        resp = self.client.post("/api/v1/payroll/tax/declarations/", {
            "financial_year_id": self.fy24.id,
            "tax_regime": "NEW",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["tax_regime"], "NEW")

    def test_07_financial_year_isolation(self):
        """7. Employee can have separate declarations for FY 24-25 and FY 25-26."""
        dec_fy24 = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="OLD"
        )
        dec_fy25 = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy25, tax_regime="NEW"
        )
        self.assertEqual(dec_fy24.tax_regime, "OLD")
        self.assertEqual(dec_fy25.tax_regime, "NEW")
        self.assertEqual(self.emp1.tax_declarations.count(), 2)

    def test_08_duplicate_declaration_prevented(self):
        """8. Creating a duplicate declaration for same employee + financial year is blocked."""
        self.client.force_authenticate(user=self.user1)
        resp1 = self.client.post("/api/v1/payroll/tax/declarations/", {
            "financial_year_id": self.fy24.id,
            "tax_regime": "NEW",
        })
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        resp2 = self.client.post("/api/v1/payroll/tax/declarations/", {
            "financial_year_id": self.fy24.id,
            "tax_regime": "OLD",
        })
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp2.data["code"], "DUPLICATE_DECLARATION")

    def test_09_draft_can_be_edited(self):
        """9. Draft declaration allows regime switching and note updates."""
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="NEW"
        )
        self.client.force_authenticate(user=self.user1)
        resp = self.client.patch(f"/api/v1/payroll/tax/declarations/{dec.id}/", {
            "tax_regime": "OLD",
            "notes": "Switched to Old regime for 80C deductions",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["tax_regime"], "OLD")
        self.assertEqual(resp.data["notes"], "Switched to Old regime for 80C deductions")

    def test_10_submitted_declaration_lifecycle_rules(self):
        """10. Submitted declaration cannot be mutated by employee without rejection/resubmission."""
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="OLD"
        )
        TaxDeclarationService.submit_declaration(dec, requesting_user=self.user1)

        self.client.force_authenticate(user=self.user1)
        resp = self.client.patch(f"/api/v1/payroll/tax/declarations/{dec.id}/", {
            "tax_regime": "NEW",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "IMMUTABLE_DECLARATION_STATE")

    def test_11_invalid_status_transitions_fail(self):
        """11. Invalid status transitions (e.g. verifying a draft directly) fail."""
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="NEW"
        )
        # Verify directly from draft should fail
        with self.assertRaises(TaxDeclarationException) as ctx:
            TaxDeclarationService.verify_declaration(dec, reviewer_user=self.reviewer_user)
        self.assertEqual(ctx.exception.code, "INVALID_STATUS_TRANSITION")

    # =========================================================================
    # PART 2: INVESTMENTS TESTS (12 - 15)
    # =========================================================================

    def test_12_employee_creates_investment_item(self):
        """12. Employee adds an itemized investment entry to draft declaration."""
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="OLD"
        )
        self.client.force_authenticate(user=self.user1)
        resp = self.client.post(f"/api/v1/payroll/tax/declarations/{dec.id}/items/", {
            "category_code": "80C",
            "description": "Public Provident Fund (PPF)",
            "declared_amount": "75000.00",
            "metadata": {"account_number": "PPF123456"},
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["category_code"], "80C")
        self.assertEqual(resp.data["declared_amount"], "75000.00")

        dec.refresh_from_db()
        self.assertEqual(dec.total_declared_amount, Decimal("75000.00"))

    def test_13_investment_amount_validation(self):
        """13. Investment amount must be greater than zero."""
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="OLD"
        )
        self.client.force_authenticate(user=self.user1)
        resp = self.client.post(f"/api/v1/payroll/tax/declarations/{dec.id}/items/", {
            "category_code": "80C",
            "description": "Invalid Zero Amount",
            "declared_amount": "0.00",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_14_employee_cannot_access_another_employee_investment(self):
        """14. Employee A cannot add or edit items on Employee B's declaration."""
        dec2 = TaxDeclarationService.create_declaration(
            employee=self.emp2, financial_year=self.fy24, tax_regime="OLD"
        )
        self.client.force_authenticate(user=self.user1)
        resp = self.client.post(f"/api/v1/payroll/tax/declarations/{dec2.id}/items/", {
            "category_code": "80C",
            "description": "Hacked item",
            "declared_amount": "10000.00",
        })
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_15_multiple_investment_categories(self):
        """15. Declaration supports multiple investment categories (80C, 80D, HRA)."""
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="OLD"
        )
        TaxDeclarationService.add_item(dec, "80C", "PPF Deposit", Decimal("50000.00"))
        TaxDeclarationService.add_item(dec, "80D", "Health Insurance", Decimal("25000.00"))
        TaxDeclarationService.add_item(
            dec, "HRA", "House Rent", Decimal("120000.00"),
            metadata={"landlord_pan": "ABCDE1234F", "monthly_rent": "10000"}
        )

        dec.refresh_from_db()
        self.assertEqual(dec.items.count(), 3)
        self.assertEqual(dec.total_declared_amount, Decimal("195000.00"))

    # =========================================================================
    # PART 3: PROOFS TESTS (16 - 21)
    # =========================================================================

    def test_16_proof_attaches_to_correct_item(self):
        """16. Proof file attaches to the specific declaration item."""
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="OLD"
        )
        item = TaxDeclarationService.add_item(dec, "80C", "ELSS Mutual Fund", Decimal("30000.00"))

        dummy_file = SimpleUploadedFile("elss_statement.pdf", b"%PDF-1.4 dummy content", content_type="application/pdf")

        self.client.force_authenticate(user=self.user1)
        resp = self.client.post(
            f"/api/v1/payroll/tax/declarations/{dec.id}/items/{item.id}/proofs/",
            {"file": dummy_file, "document_name": "ELSS Tax Receipt 2024", "proof_type": "STATEMENT"},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["document_name"], "ELSS Tax Receipt 2024")
        self.assertEqual(resp.data["status"], "submitted")

    def test_17_employee_can_retrieve_and_download_own_proof(self):
        """17. Employee can stream-download their own uploaded tax proof."""
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="OLD"
        )
        item = TaxDeclarationService.add_item(dec, "80C", "PPF Receipt", Decimal("10000.00"))
        dummy_file = SimpleUploadedFile("ppf.pdf", b"binary content of ppf", content_type="application/pdf")
        proof = TaxDeclarationService.upload_proof(item, dummy_file, document_name="ppf.pdf")

        self.client.force_authenticate(user=self.user1)
        resp = self.client.get(
            f"/api/v1/payroll/tax/declarations/{dec.id}/items/{item.id}/proofs/{proof.id}/download/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.content, b"binary content of ppf")

    def test_18_employee_cannot_download_another_employee_proof(self):
        """18. Employee A cannot download Employee B's proof (IDOR prevention)."""
        dec2 = TaxDeclarationService.create_declaration(
            employee=self.emp2, financial_year=self.fy24, tax_regime="OLD"
        )
        item2 = TaxDeclarationService.add_item(dec2, "80C", "Secret Item", Decimal("10000.00"))
        dummy_file = SimpleUploadedFile("secret.pdf", b"secret proof", content_type="application/pdf")
        proof2 = TaxDeclarationService.upload_proof(item2, dummy_file, document_name="secret.pdf")

        self.client.force_authenticate(user=self.user1)
        resp = self.client.get(
            f"/api/v1/payroll/tax/declarations/{dec2.id}/items/{item2.id}/proofs/{proof2.id}/download/"
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_19_reviewer_can_review_authorized_proof(self):
        """19. Reviewer with payroll.tax_review can download and verify proof."""
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="OLD"
        )
        item = TaxDeclarationService.add_item(dec, "80D", "Health Insurance", Decimal("20000.00"))
        dummy_file = SimpleUploadedFile("health.pdf", b"health policy bytes", content_type="application/pdf")
        proof = TaxDeclarationService.upload_proof(item, dummy_file, document_name="health.pdf")
        TaxDeclarationService.submit_declaration(dec, requesting_user=self.user1)

        self.client.force_authenticate(user=self.reviewer_user)
        # Download proof as reviewer
        dl_resp = self.client.get(
            f"/api/v1/payroll/tax/declarations/{dec.id}/items/{item.id}/proofs/{proof.id}/download/"
        )
        self.assertEqual(dl_resp.status_code, status.HTTP_200_OK)

        # Verify proof
        ver_resp = self.client.post(
            f"/api/v1/payroll/tax/declarations/{dec.id}/items/{item.id}/proofs/{proof.id}/verify/"
        )
        self.assertEqual(ver_resp.status_code, status.HTTP_200_OK)
        proof.refresh_from_db()
        self.assertEqual(proof.status, "verified")
        self.assertEqual(proof.reviewed_by, self.reviewer_user)

    def test_20_rejection_requires_appropriate_reason(self):
        """20. Rejecting a proof or declaration requires a non-empty reason."""
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="OLD"
        )
        TaxDeclarationService.submit_declaration(dec, requesting_user=self.user1)

        self.client.force_authenticate(user=self.reviewer_user)
        resp = self.client.post(f"/api/v1/payroll/tax/declarations/{dec.id}/reject/", {
            "rejection_reason": "",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_21_verification_changes_declaration_state_and_snapshots(self):
        """21. Verification creates immutable snapshot and marks declaration VERIFIED."""
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="OLD"
        )
        it1 = TaxDeclarationService.add_item(dec, "80C", "PPF", Decimal("50000.00"))
        TaxDeclarationService.submit_declaration(dec, requesting_user=self.user1)

        self.client.force_authenticate(user=self.reviewer_user)
        resp = self.client.post(f"/api/v1/payroll/tax/declarations/{dec.id}/verify/", {
            "notes": "Verified against bank statement",
            "item_verifications": [
                {"id": it1.id, "verified_amount": "50000.00"}
            ]
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        dec.refresh_from_db()
        self.assertEqual(dec.status, "verified")
        self.assertEqual(dec.verified_by, self.reviewer_user)
        self.assertTrue(bool(dec.snapshot_data))
        self.assertEqual(dec.snapshot_data["tax_regime"], "OLD")
        self.assertEqual(dec.total_verified_amount, Decimal("50000.00"))

    # =========================================================================
    # PART 4: RBAC & MULTI-TENANT TESTS (22 - 25)
    # =========================================================================

    def test_22_unauthorized_user_cannot_review(self):
        """22. User without payroll.tax_review cannot verify or reject declarations."""
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="OLD"
        )
        TaxDeclarationService.submit_declaration(dec, requesting_user=self.user1)

        self.client.force_authenticate(user=self.unauth_user)
        resp = self.client.post(f"/api/v1/payroll/tax/declarations/{dec.id}/verify/", {})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_23_authorized_reviewer_can_review(self):
        """23. Authorized reviewer with payroll.tax_review can review and verify."""
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="OLD"
        )
        TaxDeclarationService.submit_declaration(dec, requesting_user=self.user1)

        self.client.force_authenticate(user=self.reviewer_user)
        resp = self.client.post(f"/api/v1/payroll/tax/declarations/{dec.id}/start-review/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "under_review")

    def test_24_scope_restrictions_enforced(self):
        """24. Reviewer in Org 1 cannot view declarations in Org 2."""
        fy_org2 = FinancialYear.objects.create(
            organization=self.org2,
            name="FY 2024-25 Org 2",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
        )
        dec_org2 = TaxDeclarationService.create_declaration(
            employee=self.emp_org2, financial_year=fy_org2, tax_regime="OLD"
        )

        self.client.force_authenticate(user=self.reviewer_user)
        resp = self.client.get(f"/api/v1/payroll/tax/declarations/{dec_org2.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_25_organization_isolation(self):
        """25. Employee in Org 2 querying /my/ sees only Org 2 declarations."""
        fy_org2 = FinancialYear.objects.create(
            organization=self.org2,
            name="FY 2024-25 Org 2",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
        )
        TaxDeclarationService.create_declaration(
            employee=self.emp_org2, financial_year=fy_org2, tax_regime="NEW"
        )

        self.client.force_authenticate(user=self.user_org2)
        resp = self.client.get("/api/v1/payroll/tax/declarations/my/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["employee_code"], "COMP-201")

    # =========================================================================
    # PART 5: AUDIT LOGGING (26)
    # =========================================================================

    def test_26_declaration_lifecycle_generates_audit_records(self):
        """26. Creating, changing regime, submitting, and verifying logs audit events."""
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="NEW", requesting_user=self.user1
        )
        TaxDeclarationService.update_declaration(
            dec, tax_regime="OLD", requesting_user=self.user1
        )
        TaxDeclarationService.submit_declaration(
            dec, requesting_user=self.user1
        )
        TaxDeclarationService.verify_declaration(
            dec, reviewer_user=self.reviewer_user
        )

        actions = list(
            AuditLog.objects.filter(target_type="TaxDeclaration", target_id=dec.id)
            .values_list("action", flat=True)
        )
        self.assertIn("TAX_DECLARATION_CREATED", actions)
        self.assertIn("TAX_REGIME_CHANGED", actions)
        self.assertIn("TAX_DECLARATION_SUBMITTED", actions)
        self.assertIn("TAX_DECLARATION_VERIFIED", actions)

    # =========================================================================
    # PART 6: DOWNSTREAM INTEGRATION & PAYROLL IMMUTABILITY (27 - 28)
    # =========================================================================

    def test_27_verified_declaration_exposes_inputs_to_tax_boundary(self):
        """27. get_verified_declaration_inputs returns verified deductions and regime."""
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="OLD"
        )
        TaxDeclarationService.add_item(dec, "80C", "PPF", Decimal("100000.00"))
        TaxDeclarationService.add_item(dec, "80D", "Health Insurance", Decimal("25000.00"))
        TaxDeclarationService.submit_declaration(dec, requesting_user=self.user1)
        TaxDeclarationService.verify_declaration(dec, reviewer_user=self.reviewer_user)

        tax_inputs = TaxDeclarationService.get_verified_declaration_inputs(self.emp1, self.fy24)
        self.assertTrue(tax_inputs["has_verified_declaration"])
        self.assertEqual(tax_inputs["tax_regime"], "OLD")
        self.assertEqual(tax_inputs["total_verified_deductions"], Decimal("125000.00"))
        self.assertEqual(tax_inputs["categories"]["80C"], Decimal("100000.00"))
        self.assertEqual(tax_inputs["categories"]["80D"], Decimal("25000.00"))

    def test_28_finalized_payroll_immutable_after_declaration_changes(self):
        """28. Existing finalized payroll records remain unchanged when a declaration is later added/verified."""
        # Create finalized period and payroll record
        period = PayrollPeriod.objects.create(
            organization=self.org1,
            year=2024,
            month=6,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 30),
            status=PayrollPeriod.STATUS_FINALIZED,
        )
        record = PayrollRecord.objects.create(
            period=period,
            employee=self.emp1,
            working_days=20,
            present_days=20,
            half_days=0,
            absent_days=0,
            leave_days=0,
            effective_days=Decimal("20.00"),
            basic_salary=Decimal("50000.00"),
            gross_salary=Decimal("50000.00"),
            net_salary=Decimal("50000.00"),
            status=PayrollRecord.STATUS_FINALIZED,
        )

        # Employee creates and gets verified declaration for FY 24-25 later
        dec = TaxDeclarationService.create_declaration(
            employee=self.emp1, financial_year=self.fy24, tax_regime="OLD"
        )
        TaxDeclarationService.add_item(dec, "80C", "PPF", Decimal("150000.00"))
        TaxDeclarationService.submit_declaration(dec, requesting_user=self.user1)
        TaxDeclarationService.verify_declaration(dec, reviewer_user=self.reviewer_user)

        # Assert historical record is 100% untouched
        record.refresh_from_db()
        self.assertEqual(record.status, PayrollRecord.STATUS_FINALIZED)
        self.assertEqual(record.net_salary, Decimal("50000.00"))
        self.assertEqual(record.gross_salary, Decimal("50000.00"))
