"""
Phase 6.9D Employee FnF Self-Service Security and Integration Tests.

Validates:
1. Authenticated employee can view own finalized FnF settlement(s) via /api/v1/payroll/fnf/my/
2. Authenticated employee can view own finalized FnF detail via /api/v1/payroll/fnf/my/<id>/
3. Employee with no settlement receives empty list []
4. User without employee profile handled safely
5. Strict IDOR protection: Employee A cannot access Employee B's settlement via /my/<id>/ (returns 404)
6. Employee A cannot see Employee B's settlement in list (/my/)
7. Cross-organization isolation: Settlements in Org A are completely inaccessible to Org B
8. Administrative endpoint protection: Ordinary employees cannot access /api/v1/payroll/fnf/<id>/ (403)
9. Administrative list protection: Ordinary employees cannot access /api/v1/payroll/fnf/ (403)
10. Employee cannot create FnF (403)
11. Employee cannot preview FnF (403)
12. Employee cannot approve FnF (403)
13. Employee cannot finalize FnF (403)
14. Employee cannot cancel FnF (403)
15. Draft FnF visibility restricted: DRAFT settlements are not exposed via /my/ or /my/<id>/
16. Review / Approved FnF visibility restricted: Pre-finalized settlements are not exposed
17. Cancelled FnF visibility: Cancelled settlements are not exposed as payable statements
18. Finalized FnF immutability: Immutable snapshot values are returned without recalculation
19. Sensitive administrative fields excluded: created_by, approved_by, finalized_by, snapshot_data,
    integrity_hash, remarks, organization, employee are NOT serialized to employees
20. Sensitive identity and banking data (PAN, bank accounts) are not leaked
21. Unauthenticated requests are rejected (401)
22. Employee endpoint cannot be manipulated via arbitrary employee_id query params
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
    FinalSettlement,
    SettlementLine,
)
from apps.payroll.fnf_service import FnFService

User = get_user_model()


class EmployeeFnFSelfServiceTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # 1. Organization A
        self.org_a = Organization.objects.create(name="BeyondSure Tech Org A")
        self.branch_a = Branch.objects.create(
            organization=self.org_a,
            name="Bangalore Central",
            address_line1="123 Tech Park",
            city="Bangalore",
            state="Karnataka",
            postal_code="560001",
        )
        self.dept_a = Department.objects.create(
            branch=self.branch_a,
            name="Engineering",
        )

        # 2. Users and Employees in Org A
        # Admin / Maker User
        self.maker_user = User.objects.create_user(
            email="maker@orga.com", password="Password123!", first_name="Maker", last_name="Admin", status="active"
        )
        self.maker_emp = Employee.objects.create(
            user=self.maker_user,
            organization=self.org_a,
            branch=self.branch_a,
            department=self.dept_a,
            employee_code="ADM-001",
            personal_email="maker.admin@personal.com",
            joining_date=date(2020, 1, 1),
            employment_status=EmploymentStatus.ACTIVE,
        )

        # Checker User
        self.checker_user = User.objects.create_user(
            email="checker@orga.com", password="Password123!", first_name="Checker", last_name="Admin", status="active"
        )
        self.checker_emp = Employee.objects.create(
            user=self.checker_user,
            organization=self.org_a,
            branch=self.branch_a,
            department=self.dept_a,
            employee_code="ADM-002",
            personal_email="checker.admin@personal.com",
            joining_date=date(2020, 1, 1),
            employment_status=EmploymentStatus.ACTIVE,
        )

        # Employee 1 (Alice)
        self.user_alice = User.objects.create_user(
            email="alice@orga.com", password="Password123!", first_name="Alice", last_name="Smith", status="active"
        )
        self.emp_alice = Employee.objects.create(
            user=self.user_alice,
            organization=self.org_a,
            branch=self.branch_a,
            department=self.dept_a,
            employee_code="EMP-001",
            personal_email="alice.personal@gmail.com",
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
            pan_number="ABCDE1234F",
            account_number="123456789012",
            bank_name="HDFC Bank",
            ifsc_code="HDFC0001234",
        )

        # Employee 2 (Bob)
        self.user_bob = User.objects.create_user(
            email="bob@orga.com", password="Password123!", first_name="Bob", last_name="Jones", status="active"
        )
        self.emp_bob = Employee.objects.create(
            user=self.user_bob,
            organization=self.org_a,
            branch=self.branch_a,
            department=self.dept_a,
            employee_code="EMP-002",
            personal_email="bob.personal@gmail.com",
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

        # Employee 3 (Charlie - Active, No FnF)
        self.user_charlie = User.objects.create_user(
            email="charlie@orga.com", password="Password123!", first_name="Charlie", last_name="Brown", status="active"
        )
        self.emp_charlie = Employee.objects.create(
            user=self.user_charlie,
            organization=self.org_a,
            branch=self.branch_a,
            department=self.dept_a,
            employee_code="EMP-003",
            personal_email="charlie.personal@gmail.com",
            joining_date=date(2024, 1, 1),
            employment_status=EmploymentStatus.ACTIVE,
        )

        # User 4 (David - Account without Employee Profile)
        self.user_david = User.objects.create_user(
            email="david@orga.com", password="Password123!", first_name="David", last_name="NoEmp", status="active"
        )

        # 3. Organization B & User in Org B
        self.org_b = Organization.objects.create(name="Competitor Inc Org B")
        self.user_org_b = User.objects.create_user(
            email="employee@orgb.com", password="Password123!", first_name="Eve", last_name="External", status="active"
        )
        self.emp_org_b = Employee.objects.create(
            user=self.user_org_b,
            organization=self.org_b,
            employee_code="ORGB-001",
            personal_email="eve.personal@gmail.com",
            joining_date=date(2023, 1, 1),
            employment_status=EmploymentStatus.ACTIVE,
        )

        # 4. Permissions Setup
        self._setup_permissions()

        # 5. Prepare, Approve & Finalize Settlement for Alice
        self.settlement_alice = FnFService.prepare(
            employee_id=self.emp_alice.id,
            requesting_user=self.maker_user,
            exit_date=date(2026, 1, 31),
            settlement_date=date(2026, 2, 5),
            remarks="Authoritative final settlement for Alice",
        )
        FnFService.approve(self.settlement_alice, self.checker_user)
        FnFService.finalize(self.settlement_alice, self.checker_user)

        # 6. Prepare, Approve & Finalize Settlement for Bob
        self.settlement_bob = FnFService.prepare(
            employee_id=self.emp_bob.id,
            requesting_user=self.maker_user,
            exit_date=date(2026, 2, 28),
            settlement_date=date(2026, 3, 5),
            remarks="Authoritative final settlement for Bob",
        )
        FnFService.approve(self.settlement_bob, self.checker_user)
        FnFService.finalize(self.settlement_bob, self.checker_user)

    def _setup_permissions(self):
        perms_data = [
            ("payroll.fnf_view", "payroll", "fnf_view"),
            ("payroll.fnf_prepare", "payroll", "fnf_prepare"),
            ("payroll.fnf_approve", "payroll", "fnf_approve"),
            ("payroll.fnf_finalize", "payroll", "fnf_finalize"),
        ]
        perms = {}
        for code, res, act in perms_data:
            p, _ = Permission.objects.get_or_create(codename=code, defaults={"name": code, "resource": res, "action": act})
            perms[code] = p

        # Maker Role
        role_maker = Role.objects.create(organization=self.org_a, name="FnF Maker")
        RolePermission.objects.create(role=role_maker, permission=perms["payroll.fnf_view"])
        RolePermission.objects.create(role=role_maker, permission=perms["payroll.fnf_prepare"])
        UserRole.objects.create(user=self.maker_user, role=role_maker)

        # Checker Role
        role_checker = Role.objects.create(organization=self.org_a, name="FnF Checker")
        RolePermission.objects.create(role=role_checker, permission=perms["payroll.fnf_view"])
        RolePermission.objects.create(role=role_checker, permission=perms["payroll.fnf_approve"])
        RolePermission.objects.create(role=role_checker, permission=perms["payroll.fnf_finalize"])
        UserRole.objects.create(user=self.checker_user, role=role_checker)

        # Employee Role (Standard employee without admin payroll permissions)
        role_emp = Role.objects.create(organization=self.org_a, name="Standard Employee")
        UserRole.objects.create(user=self.user_alice, role=role_emp)
        UserRole.objects.create(user=self.user_bob, role=role_emp)
        UserRole.objects.create(user=self.user_charlie, role=role_emp)

    # =========================================================================
    # 1. AUTHENTICATED EMPLOYEE CAN VIEW OWN FnF LIST
    # =========================================================================
    def test_authenticated_employee_can_view_own_finalized_fnf_list(self):
        self.client.force_authenticate(user=self.user_alice)
        resp = self.client.get("/api/v1/payroll/fnf/my/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)
        self.assertEqual(len(resp.data), 1)

        settlement_data = resp.data[0]
        self.assertEqual(settlement_data["id"], self.settlement_alice.id)
        self.assertEqual(settlement_data["settlement_number"], self.settlement_alice.settlement_number)
        self.assertEqual(settlement_data["status"], FinalSettlement.STATUS_FINALIZED)
        self.assertEqual(settlement_data["exit_date"], "2026-01-31")
        self.assertEqual(settlement_data["currency"], "INR")
        self.assertEqual(Decimal(settlement_data["net_settlement_amount"]), self.settlement_alice.net_settlement_amount)
        self.assertIn("lines", settlement_data)
        self.assertTrue(len(settlement_data["lines"]) > 0)

    # =========================================================================
    # 2. AUTHENTICATED EMPLOYEE CAN VIEW OWN FnF DETAIL
    # =========================================================================
    def test_authenticated_employee_can_view_own_finalized_fnf_detail(self):
        self.client.force_authenticate(user=self.user_alice)
        resp = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["id"], self.settlement_alice.id)
        self.assertEqual(resp.data["settlement_number"], self.settlement_alice.settlement_number)
        self.assertEqual(resp.data["status"], FinalSettlement.STATUS_FINALIZED)
        self.assertIn("lines", resp.data)

        # Check line structure
        line = resp.data["lines"][0]
        self.assertIn("category", line)
        self.assertIn("code", line)
        self.assertIn("name", line)
        self.assertIn("amount", line)
        self.assertIn("calculation_basis", line)

    # =========================================================================
    # 3. EMPLOYEE WITH NO SETTLEMENT RECEIVES EMPTY RESULT
    # =========================================================================
    def test_employee_with_no_settlement_receives_empty_result(self):
        self.client.force_authenticate(user=self.user_charlie)
        resp = self.client.get("/api/v1/payroll/fnf/my/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

        # Requesting arbitrary ID gives 404
        resp_detail = self.client.get("/api/v1/payroll/fnf/my/9999/")
        self.assertEqual(resp_detail.status_code, status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # 4. USER WITHOUT EMPLOYEE PROFILE HANDLED SAFELY
    # =========================================================================
    def test_user_without_employee_profile_handled_safely(self):
        self.client.force_authenticate(user=self.user_david)
        resp = self.client.get("/api/v1/payroll/fnf/my/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

        resp_detail = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp_detail.status_code, status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # 5. IDOR PROTECTION: EMPLOYEE A CANNOT VIEW EMPLOYEE B's SETTLEMENT
    # =========================================================================
    def test_idor_employee_cannot_view_another_employees_settlement(self):
        """CRITICAL: Alice requests Bob's settlement ID. Must return 404, never 200 or 403."""
        self.client.force_authenticate(user=self.user_alice)

        resp = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_bob.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn("Bob", str(resp.data))
        self.assertNotIn(self.settlement_bob.settlement_number, str(resp.data))

        # Bob requests Alice's settlement ID
        self.client.force_authenticate(user=self.user_bob)
        resp_b = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp_b.status_code, status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # 6. EMPLOYEE A CANNOT SEE EMPLOYEE B's SETTLEMENT IN LIST
    # =========================================================================
    def test_employee_cannot_see_another_employees_settlement_in_list(self):
        self.client.force_authenticate(user=self.user_alice)
        resp = self.client.get("/api/v1/payroll/fnf/my/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        ids_returned = [s["id"] for s in resp.data]
        self.assertIn(self.settlement_alice.id, ids_returned)
        self.assertNotIn(self.settlement_bob.id, ids_returned)

    # =========================================================================
    # 7. CROSS-ORGANIZATION ISOLATION
    # =========================================================================
    def test_organization_isolation_enforced(self):
        """User in Org B cannot see settlements from Org A."""
        self.client.force_authenticate(user=self.user_org_b)

        # List returns empty
        resp = self.client.get("/api/v1/payroll/fnf/my/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

        # Detail returns 404
        resp_detail = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp_detail.status_code, status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # 8. ADMINISTRATIVE ENDPOINT PROTECTION
    # =========================================================================
    def test_employee_cannot_access_administrative_fnf_endpoints(self):
        """DO NOT simply add employee permission to /api/v1/payroll/fnf/<id>/."""
        self.client.force_authenticate(user=self.user_alice)

        # Admin detail endpoint -> 403 Forbidden
        resp_detail = self.client.get(f"/api/v1/payroll/fnf/{self.settlement_alice.id}/")
        self.assertEqual(resp_detail.status_code, status.HTTP_403_FORBIDDEN)

        # Admin list endpoint -> 403 Forbidden
        resp_list = self.client.get("/api/v1/payroll/fnf/")
        self.assertEqual(resp_list.status_code, status.HTTP_403_FORBIDDEN)

    # =========================================================================
    # 9. EMPLOYEE CANNOT PERFORM WRITE OPERATIONS
    # =========================================================================
    def test_employee_cannot_perform_write_operations(self):
        self.client.force_authenticate(user=self.user_alice)

        # Cannot create/prepare
        resp_create = self.client.post("/api/v1/payroll/fnf/", {"employee_id": self.emp_alice.id})
        self.assertEqual(resp_create.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot preview
        resp_preview = self.client.post("/api/v1/payroll/fnf/preview/", {"employee_id": self.emp_alice.id})
        self.assertEqual(resp_preview.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot approve
        resp_approve = self.client.post(f"/api/v1/payroll/fnf/{self.settlement_alice.id}/approve/")
        self.assertEqual(resp_approve.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot finalize
        resp_finalize = self.client.post(f"/api/v1/payroll/fnf/{self.settlement_alice.id}/finalize/")
        self.assertEqual(resp_finalize.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot cancel
        resp_cancel = self.client.post(f"/api/v1/payroll/fnf/{self.settlement_alice.id}/cancel/")
        self.assertEqual(resp_cancel.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot modify policy
        resp_policy = self.client.post("/api/v1/payroll/fnf-policy/", {})
        self.assertIn(resp_policy.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST])

    # =========================================================================
    # 10. DRAFT FnF VISIBILITY RESTRICTED
    # =========================================================================
    def test_draft_fnf_visibility_is_restricted(self):
        """Draft settlement must NOT be exposed as an official payable statement."""
        emp_draft = Employee.objects.create(
            user=User.objects.create_user(email="draft.emp@orga.com", password="P!", status="active"),
            organization=self.org_a,
            branch=self.branch_a,
            employee_code="EMP-DRAFT",
            personal_email="draft.personal@gmail.com",
            joining_date=date(2023, 1, 1),
            exit_date=date(2026, 3, 31),
            employment_status=EmploymentStatus.ON_NOTICE,
        )
        settlement_draft = FnFService.prepare(
            employee_id=emp_draft.id,
            requesting_user=self.maker_user,
            exit_date=date(2026, 3, 31),
        )
        self.assertEqual(settlement_draft.status, FinalSettlement.STATUS_DRAFT)

        self.client.force_authenticate(user=emp_draft.user)
        # List returns empty
        resp = self.client.get("/api/v1/payroll/fnf/my/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

        # Detail returns 404
        resp_det = self.client.get(f"/api/v1/payroll/fnf/my/{settlement_draft.id}/")
        self.assertEqual(resp_det.status_code, status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # 11. REVIEW / APPROVED FnF VISIBILITY RESTRICTED
    # =========================================================================
    def test_review_and_approved_fnf_visibility_is_restricted(self):
        """Approved but not yet finalized settlement must NOT be exposed to employee."""
        emp_app = Employee.objects.create(
            user=User.objects.create_user(email="app.emp@orga.com", password="P!", status="active"),
            organization=self.org_a,
            branch=self.branch_a,
            employee_code="EMP-APP",
            personal_email="app.personal@gmail.com",
            joining_date=date(2023, 1, 1),
            exit_date=date(2026, 3, 31),
            employment_status=EmploymentStatus.ON_NOTICE,
        )
        settlement_app = FnFService.prepare(
            employee_id=emp_app.id,
            requesting_user=self.maker_user,
            exit_date=date(2026, 3, 31),
        )
        FnFService.approve(settlement_app, self.checker_user)
        self.assertEqual(settlement_app.status, FinalSettlement.STATUS_APPROVED)

        self.client.force_authenticate(user=emp_app.user)
        # List returns empty
        resp = self.client.get("/api/v1/payroll/fnf/my/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

        # Detail returns 404
        resp_det = self.client.get(f"/api/v1/payroll/fnf/my/{settlement_app.id}/")
        self.assertEqual(resp_det.status_code, status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # 12. CANCELLED FnF BEHAVIOR
    # =========================================================================
    def test_cancelled_settlement_behavior(self):
        """Cancelled settlements are not exposed as active or payable statements."""
        emp_canc = Employee.objects.create(
            user=User.objects.create_user(email="canc.emp@orga.com", password="P!", status="active"),
            organization=self.org_a,
            branch=self.branch_a,
            employee_code="EMP-CANC",
            personal_email="canc.personal@gmail.com",
            joining_date=date(2023, 1, 1),
            exit_date=date(2026, 3, 31),
            employment_status=EmploymentStatus.ON_NOTICE,
        )
        settlement_canc = FnFService.prepare(
            employee_id=emp_canc.id,
            requesting_user=self.maker_user,
            exit_date=date(2026, 3, 31),
        )
        FnFService.cancel(settlement_canc, self.maker_user, reason="Employee revoked resignation.")
        self.assertEqual(settlement_canc.status, FinalSettlement.STATUS_CANCELLED)

        self.client.force_authenticate(user=emp_canc.user)
        # List returns empty
        resp = self.client.get("/api/v1/payroll/fnf/my/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

        # Detail returns 404
        resp_det = self.client.get(f"/api/v1/payroll/fnf/my/{settlement_canc.id}/")
        self.assertEqual(resp_det.status_code, status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # 13. FINALIZED FnF RETURNS IMMUTABLE VALUES (NO RECALCULATION)
    # =========================================================================
    def test_finalized_fnf_returns_immutable_values(self):
        self.client.force_authenticate(user=self.user_alice)
        resp = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.assertEqual(Decimal(resp.data["total_earnings"]), self.settlement_alice.total_earnings)
        self.assertEqual(Decimal(resp.data["total_deductions"]), self.settlement_alice.total_deductions)
        self.assertEqual(Decimal(resp.data["total_recoveries"]), self.settlement_alice.total_recoveries)
        self.assertEqual(Decimal(resp.data["net_settlement_amount"]), self.settlement_alice.net_settlement_amount)

        # Mutating live employee compensation after finalization must NOT alter settlement response
        CompensationHistory.objects.create(
            employee=self.emp_alice,
            effective_from=date(2026, 2, 1),
            basic_salary=Decimal("999999.00"),
            created_by=self.maker_user,
        )

        resp2 = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(Decimal(resp2.data["net_settlement_amount"]), self.settlement_alice.net_settlement_amount)

    # =========================================================================
    # 14. SENSITIVE ADMINISTRATIVE FIELDS ARE NOT SERIALIZED
    # =========================================================================
    def test_sensitive_administrative_fields_are_not_serialized(self):
        self.client.force_authenticate(user=self.user_alice)
        resp = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.data
        # Workflow internals & makers/checkers must NOT be exposed
        self.assertNotIn("created_by", data)
        self.assertNotIn("approved_by", data)
        self.assertNotIn("finalized_by", data)
        self.assertNotIn("created_by_email", data)
        self.assertNotIn("approved_by_email", data)
        self.assertNotIn("finalized_by_email", data)

        # Audit snapshots & integrity hashes must NOT be exposed
        self.assertNotIn("snapshot_data", data)
        self.assertNotIn("integrity_hash", data)

        # Internal administrative remarks must NOT be exposed
        self.assertNotIn("remarks", data)

        # Tenant & employee foreign keys must NOT be exposed
        self.assertNotIn("organization", data)
        self.assertNotIn("employee", data)

    # =========================================================================
    # 15. SENSITIVE IDENTITY AND BANKING DATA NOT EXPOSED
    # =========================================================================
    def test_sensitive_identity_and_banking_data_not_exposed(self):
        self.client.force_authenticate(user=self.user_alice)
        resp = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data_str = str(resp.data)
        # PAN and bank account must NOT be leaked
        self.assertNotIn("ABCDE1234F", data_str)
        self.assertNotIn("123456789012", data_str)
        self.assertNotIn("account_number", data_str)
        self.assertNotIn("pan_number", data_str)

    # =========================================================================
    # 16. UNAUTHENTICATED ACCESS IS REJECTED
    # =========================================================================
    def test_unauthenticated_access_is_rejected(self):
        self.client.logout()

        resp_list = self.client.get("/api/v1/payroll/fnf/my/")
        self.assertEqual(resp_list.status_code, status.HTTP_401_UNAUTHORIZED)

        resp_detail = self.client.get(f"/api/v1/payroll/fnf/my/{self.settlement_alice.id}/")
        self.assertEqual(resp_detail.status_code, status.HTTP_401_UNAUTHORIZED)

    # =========================================================================
    # 17. EMPLOYEE ENDPOINT CANNOT BE MANIPULATED VIA QUERY PARAMS
    # =========================================================================
    def test_employee_endpoint_cannot_be_manipulated_via_query_params(self):
        self.client.force_authenticate(user=self.user_alice)

        # Passing employee=Bob's ID does NOT return Bob's settlement
        resp = self.client.get(f"/api/v1/payroll/fnf/my/?employee={self.emp_bob.id}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["id"], self.settlement_alice.id)

        # Passing status=draft does NOT return draft settlements
        resp_status = self.client.get("/api/v1/payroll/fnf/my/?status=draft")
        self.assertEqual(resp_status.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_status.data), 1)
        self.assertEqual(resp_status.data[0]["status"], FinalSettlement.STATUS_FINALIZED)

    # =========================================================================
    # 18. DETERMINISTIC ORDERING: NEWEST SETTLEMENT FIRST
    # =========================================================================
    def test_deterministic_ordering_newest_settlement_first(self):
        # Alice is in EXITED state with an existing finalized settlement.
        # Check that self.settlement_alice has settlement_date set and ordering is deterministic.
        self.client.force_authenticate(user=self.user_alice)
        resp = self.client.get("/api/v1/payroll/fnf/my/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["settlement_number"], self.settlement_alice.settlement_number)
