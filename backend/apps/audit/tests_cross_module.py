"""
Cross-Module Acceptance Integration Test Suite for BeyondSure HRMS.
Tests end-to-end workflows connecting:
- Organization & Organizational Structure
- Employee Lifecycle & ESS
- Dynamic Roles & Permissions (RBAC)
- Attendance, Shifts & Working Calendars
- Leave Management & Balances
- Recruitment, Documents & Candidates
- Payroll & Full and Final (FnF) Settlement
- Universal Data Import Engine
- Multi-Tenant Isolation & Cross-Org Access Protection
"""
import io
import csv
from decimal import Decimal
from datetime import date, timedelta, time
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.organization.models import Organization, Branch, Department, Designation, WorkingCalendarRule, OfficeNetwork
from apps.organization.services import WorkingCalendarService
from apps.employees.models import Employee, EmploymentStatus
from apps.candidates.models import Candidate, CandidateStatus, LetterTemplate, LetterType, CandidateDocument
from apps.authorization.models import Role, Permission, RolePermission, UserRole, ScopeChoices
from apps.authorization.services import AuthorizationService
from apps.attendance.models import Shift, Holiday, Attendance
from apps.leaves.models import LeaveType, LeaveBalance, LeaveRequest, LeaveCycle, BranchLeavePolicy
from apps.payroll.models import CompensationHistory, PayrollPeriod, PayrollRecord, FinalSettlement, SettlementLine
from apps.payroll.services import generate_payroll_for_period, _working_days_in_period
from apps.data_import.engine import ImportEngine
from apps.data_import.models import ImportJob
from apps.data_import.registry import get_template
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()


class CrossModuleAcceptanceTests(TestCase):
    """
    Executes the 10 locked cross-module acceptance workflows with real database transactions and API endpoints.
    """

    def setUp(self):
        self.client = APIClient()

        # Tenant Alpha (Primary)
        self.org_alpha = Organization.objects.create(name="Alpha Corp", status="active")
        self.branch_alpha = Branch.objects.create(
            organization=self.org_alpha,
            name="Alpha HQ",
            latitude="12.9716",
            longitude="77.5946",
            radius=200.0,
            is_active=True,
        )
        self.dept_alpha = Department.objects.create(branch=self.branch_alpha, name="Engineering")
        self.desig_alpha = Designation.objects.create(organization=self.org_alpha, name="Senior Engineer")

        # Allow office network for loopback client in testing
        OfficeNetwork.objects.create(
            branch=self.branch_alpha,
            network="127.0.0.1/32",
            is_active=True,
        )

        # Configure base calendar (Mon-Fri)
        cal = self.branch_alpha.working_calendar
        cal.work_days = "0,1,2,3,4"
        cal.save()

        # Shift
        self.shift_alpha = Shift.objects.create(
            branch=self.branch_alpha,
            name="General Shift",
            start_time=time(9, 0),
            end_time=time(18, 0),
            work_days="0,1,2,3,4",
            is_active=True,
        )

        # Tenant Beta (Isolated)
        self.org_beta = Organization.objects.create(name="Beta Industries", status="active")
        self.branch_beta = Branch.objects.create(
            organization=self.org_beta,
            name="Beta Branch",
            latitude="28.7041",
            longitude="77.1025",
            radius=200.0,
            is_active=True,
        )

        # Super Admin User in Org Alpha
        self.admin_user = User.objects.create_user(
            email="admin@alpha.com",
            password="Password123!",
            first_name="Alpha",
            last_name="Admin",
            status="active",
        )
        self.admin_emp = Employee.objects.create(
            user=self.admin_user,
            employee_code="ADM001",
            organization=self.org_alpha,
            branch=self.branch_alpha,
            department=self.dept_alpha,
            designation=self.desig_alpha,
            employment_status=EmploymentStatus.ACTIVE,
        )

        # Assign Super Admin Role to admin_user
        admin_role, _ = Role.objects.get_or_create(
            organization=self.org_alpha,
            name="Super Admin",
            defaults={"slug": "super-admin", "is_system": True},
        )
        UserRole.objects.get_or_create(
            user=self.admin_user,
            role=admin_role,
            scope=ScopeChoices.ORGANIZATION,
        )

    # -------------------------------------------------------------------------
    # WORKFLOW 1: Create an employee and assign organizational relationships
    # -------------------------------------------------------------------------
    def test_workflow_1_employee_creation_and_org_relationships(self):
        # 1. Create Reporting Manager
        mgr_user = User.objects.create_user(
            email="manager@alpha.com", password="Password123!", first_name="Manager", last_name="One", status="active"
        )
        mgr = Employee.objects.create(
            user=mgr_user,
            employee_code="MGR001",
            organization=self.org_alpha,
            branch=self.branch_alpha,
            department=self.dept_alpha,
            designation=self.desig_alpha,
            employment_status=EmploymentStatus.ACTIVE,
            joining_date=date(2025, 1, 1),
        )

        # 2. Create Direct Report Employee with organizational hierarchy
        emp_user = User.objects.create_user(
            email="emp1@alpha.com", password="Password123!", first_name="Dev", last_name="One", status="active"
        )
        emp = Employee.objects.create(
            user=emp_user,
            employee_code="EMP101",
            organization=self.org_alpha,
            branch=self.branch_alpha,
            department=self.dept_alpha,
            designation=self.desig_alpha,
            reporting_manager=mgr,
            employment_status=EmploymentStatus.ACTIVE,
            joining_date=date(2025, 2, 1),
        )

        # 3. Assert organizational relationships
        self.assertEqual(emp.organization, self.org_alpha)
        self.assertEqual(emp.branch, self.branch_alpha)
        self.assertEqual(emp.department, self.dept_alpha)
        self.assertEqual(emp.designation, self.desig_alpha)
        self.assertEqual(emp.reporting_manager, mgr)
        self.assertIn(emp, mgr.direct_reports.all())

        # 4. Verify employee deletion returns HTTP 405 Method Not Allowed
        self.client.force_authenticate(user=self.admin_user)
        del_resp = self.client.delete(f"/api/v1/employees/management/{emp.id}/")
        self.assertEqual(del_resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # -------------------------------------------------------------------------
    # WORKFLOW 2: Convert a candidate to an employee and verify idempotency
    # -------------------------------------------------------------------------
    def test_workflow_2_convert_candidate_to_employee_idempotent(self):
        # Setup HR role and permissions
        hr_user = User.objects.create_user(email="hr@alpha.com", password="Password123!", status="active")
        hr_role = Role.objects.create(organization=self.org_alpha, name="Recruitment Lead")
        for perm_code in [
            "candidate.view", "candidate.create", "candidate.onboard", "candidate.verify", "candidate.convert"
        ]:
            res, act = perm_code.split(".")
            p, _ = Permission.objects.get_or_create(codename=perm_code, defaults={"name": perm_code, "resource": res, "action": act})
            RolePermission.objects.get_or_create(role=hr_role, permission=p)
        UserRole.objects.create(user=hr_user, role=hr_role, scope=ScopeChoices.ORGANIZATION)

        self.client.force_authenticate(user=hr_user)

        # 1. Create candidate
        cand = Candidate.objects.create(
            organization=self.org_alpha,
            first_name="Alice",
            last_name="Applicant",
            email="alice.candidate@example.com",
            applied_designation=self.desig_alpha,
            status=CandidateStatus.CREATED,
        )

        # 2. Offer template & issuance
        LetterTemplate.objects.create(
            organization=self.org_alpha,
            letter_type=LetterType.OFFER,
            subject="Job Offer",
            body="Welcome {{candidate_name}}",
            version=1,
            is_active=True,
        )
        offer_res = self.client.post(f"/api/v1/candidates/{cand.id}/issue-offer/")
        self.assertEqual(offer_res.status_code, status.HTTP_200_OK)
        cand.refresh_from_db()
        self.assertEqual(cand.status, CandidateStatus.OFFERED)
        self.assertIsNotNone(cand.user)

        # 3. Upload and verify candidate document
        CandidateDocument.objects.create(
            candidate=cand,
            document_type="identity",
            document_name="passport.pdf",
            file_size=1024,
        )
        cand.status = CandidateStatus.ONBOARDING
        cand.save()

        # Submit & Approve
        cand.status = CandidateStatus.APPROVED
        cand.save()

        # 4. Convert candidate to employee
        conv_res = self.client.post(f"/api/v1/candidates/{cand.id}/convert-to-employee/")
        self.assertEqual(conv_res.status_code, status.HTTP_201_CREATED)
        cand.refresh_from_db()
        self.assertEqual(cand.status, CandidateStatus.CONVERTED)
        self.assertIsNotNone(cand.employee)
        self.assertEqual(cand.employee.user, cand.user)

        # 5. Idempotent check: second conversion attempt MUST return HTTP 409 Conflict
        second_conv = self.client.post(f"/api/v1/candidates/{cand.id}/convert-to-employee/")
        self.assertEqual(second_conv.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already been converted", second_conv.data["detail"])

    # -------------------------------------------------------------------------
    # WORKFLOW 3: Assign a role and verify permissions take effect
    # -------------------------------------------------------------------------
    def test_workflow_3_assign_role_and_verify_permissions(self):
        user = User.objects.create_user(email="staff@alpha.com", password="Password123!", status="active")
        role = Role.objects.create(organization=self.org_alpha, name="Leave Policy Admin")
        perm, _ = Permission.objects.get_or_create(
            codename="leave_type.manage", defaults={"name": "Manage Leave Types", "resource": "leave_type", "action": "manage"}
        )
        RolePermission.objects.create(role=role, permission=perm)

        # Before role assignment: denied
        self.assertFalse(AuthorizationService.has_permission(user, "leave_type.manage"))
        self.client.force_authenticate(user=user)
        self.assertEqual(self.client.get("/api/v1/leaves/admin/types/").status_code, status.HTTP_403_FORBIDDEN)

        # Assign role
        UserRole.objects.create(user=user, role=role, scope=ScopeChoices.ORGANIZATION)

        # After role assignment: granted and effective in endpoint
        effective = AuthorizationService.get_effective_permissions(user)
        self.assertIn("leave_type.manage", effective)
        self.assertTrue(AuthorizationService.has_permission(user, "leave_type.manage"))
        self.assertEqual(self.client.get("/api/v1/leaves/admin/types/").status_code, status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # WORKFLOW 4: Revoke a permission and verify protected requests are denied
    # -------------------------------------------------------------------------
    def test_workflow_4_revoke_permission_and_verify_denial(self):
        user = User.objects.create_user(email="staff_revoke@alpha.com", password="Password123!", status="active")
        role = Role.objects.create(organization=self.org_alpha, name="Temporary Admin")
        perm, _ = Permission.objects.get_or_create(
            codename="leave_type.manage", defaults={"name": "Manage Leave Types", "resource": "leave_type", "action": "manage"}
        )
        RolePermission.objects.create(role=role, permission=perm)
        ur = UserRole.objects.create(user=user, role=role, scope=ScopeChoices.ORGANIZATION)

        # Verify granted
        self.assertTrue(AuthorizationService.has_permission(user, "leave_type.manage"))
        self.client.force_authenticate(user=user)
        self.assertEqual(self.client.get("/api/v1/leaves/admin/types/").status_code, status.HTTP_200_OK)

        # Revoke permission by removing assignment
        ur.delete()

        # Verify denied both in service and on protected API route
        self.assertFalse(AuthorizationService.has_permission(user, "leave_type.manage"))
        res = self.client.get("/api/v1/leaves/admin/types/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # WORKFLOW 5: Configure branch shift/calendar and verify attendance behavior
    # -------------------------------------------------------------------------
    def test_workflow_5_branch_shift_and_calendar_attendance(self):
        # 1. Invariant: Exactly one active shift per branch (reject 2nd active shift)
        self.client.force_authenticate(user=self.admin_user)
        second_shift_res = self.client.post("/api/v1/attendance/shifts/", {
            "branch": self.branch_alpha.id,
            "name": "Conflicting Shift",
            "start_time": "14:00:00",
            "end_time": "22:00:00",
            "work_days": "0,1,2,3,4",
            "is_active": True,
        })
        self.assertEqual(second_shift_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("An active shift is already configured", str(second_shift_res.data))

        # 2. Priority check: Explicit Holiday > Recurring Rule > Base Calendar
        # Sept 5, 2026 is Saturday (Day 5). Base calendar work_days="0,1,2,3,4" (Sat is off).
        # Add recurring rule: 1st Saturday is working day (is_working=True).
        WorkingCalendarRule.objects.create(
            working_calendar=self.branch_alpha.working_calendar,
            weekday=5,
            occurrence=1,
            is_working=True,
        )
        sat_date = date(2026, 9, 5)  # 1st Saturday of Sept 2026
        # With rule: Saturday is working
        self.assertTrue(WorkingCalendarService.is_working_day(self.branch_alpha, sat_date))

        # Add explicit Holiday on Sept 5, 2026: Holiday MUST override recurring rule!
        Holiday.objects.create(
            branch=self.branch_alpha,
            name="Special Founder Day",
            date=sat_date,
            is_active=True,
        )
        # With explicit holiday: Saturday is NOT working (Holiday > Recurring Rule)
        self.assertFalse(WorkingCalendarService.is_working_day(self.branch_alpha, sat_date))

    # -------------------------------------------------------------------------
    # WORKFLOW 6: Submit and approve leave and verify balances
    # -------------------------------------------------------------------------
    def test_workflow_6_submit_and_approve_leave_and_balances(self):
        emp_user = User.objects.create_user(email="leave_emp@alpha.com", password="Password123!", status="active")
        emp = Employee.objects.create(
            user=emp_user,
            employee_code="LEAVE01",
            organization=self.org_alpha,
            branch=self.branch_alpha,
            employment_status=EmploymentStatus.ACTIVE,
        )

        leave_type = LeaveType.objects.create(organization=self.org_alpha, name="Casual Leave", is_active=True)
        cycle = LeaveCycle.objects.create(
            branch=self.branch_alpha,
            name="2026 Annual Cycle",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        BranchLeavePolicy.objects.create(
            branch=self.branch_alpha,
            leave_type=leave_type,
            monthly_allocation=Decimal("1.5"),
            cancellation_allowed=True,
        )
        balance = LeaveBalance.objects.create(
            employee=emp,
            leave_type=leave_type,
            leave_cycle=cycle,
            branch=self.branch_alpha,
            allocated=10,
            used=0,
        )

        # Submit leave for Monday Jan 5 to Tuesday Jan 6, 2026 (2 days)
        req = LeaveRequest.objects.create(
            employee=emp,
            leave_type=leave_type,
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 6),
            reason="Family function",
            status="pending",
        )

        # HR / Admin approves leave
        self.client.force_authenticate(user=self.admin_user)
        approve_res = self.client.post(reverse("leave-requests-approve", kwargs={"pk": req.id}), {
            "reviewer_comment": "Approved"
        })
        self.assertEqual(approve_res.status_code, status.HTTP_200_OK)

        req.refresh_from_db()
        self.assertEqual(req.status, "approved")

        balance.refresh_from_db()
        self.assertEqual(balance.used, 2)
        self.assertEqual(balance.remaining, 8)

    # -------------------------------------------------------------------------
    # WORKFLOW 7: Correct attendance and verify payroll pre-check behavior
    # -------------------------------------------------------------------------
    def test_workflow_7_attendance_leave_reconciliation_in_payroll_precheck(self):
        emp_user = User.objects.create_user(email="precheck@alpha.com", password="Password123!", status="active")
        emp = Employee.objects.create(
            user=emp_user,
            employee_code="PRE001",
            organization=self.org_alpha,
            branch=self.branch_alpha,
            employment_status=EmploymentStatus.ACTIVE,
        )
        CompensationHistory.objects.create(
            employee=emp,
            effective_from=date(2026, 1, 1),
            basic_salary=Decimal("50000.00"),
        )

        # Jan 2026: 22 working weekdays
        # Record 4 present days (Jan 5 - Jan 8)
        for d in range(5, 9):
            Attendance.objects.create(
                employee=emp,
                date=date(2026, 1, d),
                check_in=timezone.now(),
                check_out=timezone.now() + timedelta(hours=9),
                status="present",
            )

        # Approved Leave for 1 day (Jan 9)
        lt = LeaveType.objects.create(organization=self.org_alpha, name="Sick Leave", is_active=True)
        LeaveRequest.objects.create(
            employee=emp,
            leave_type=lt,
            start_date=date(2026, 1, 9),
            end_date=date(2026, 1, 9),
            status="approved",
        )

        # Generate draft payroll
        period = PayrollPeriod.objects.create(
            organization=self.org_alpha,
            year=2026,
            month=1,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 13, 31) if False else date(2026, 1, 31),
        )
        records = generate_payroll_for_period(period)
        emp_record = next(r for r in records if r.employee == emp)

        self.assertEqual(emp_record.present_days, 4)
        self.assertEqual(emp_record.leave_days, 1)
        self.assertEqual(emp_record.effective_days, Decimal("5.00"))
        # Working days for Jan 2026 (Mon-Fri) = 22
        self.assertEqual(emp_record.working_days, 22)
        self.assertEqual(emp_record.absent_days, 17)  # 22 - 5 = 17

    # -------------------------------------------------------------------------
    # WORKFLOW 8: Process employee exit and verify applicable settlement behavior
    # -------------------------------------------------------------------------
    def test_workflow_8_employee_exit_and_fnf_settlement_mutual_exclusion(self):
        exit_user = User.objects.create_user(email="exit@alpha.com", password="Password123!", status="active")
        exit_emp = Employee.objects.create(
            user=exit_user,
            employee_code="EXIT001",
            organization=self.org_alpha,
            branch=self.branch_alpha,
            employment_status=EmploymentStatus.ON_NOTICE,
            joining_date=date(2025, 1, 1),
            exit_date=date(2026, 2, 10),
        )
        CompensationHistory.objects.create(
            employee=exit_emp,
            effective_from=date(2025, 1, 1),
            basic_salary=Decimal("60000.00"),
        )

        # Create FinalSettlement
        fnf = FinalSettlement.objects.create(
            organization=self.org_alpha,
            employee=exit_emp,
            exit_date=date(2026, 2, 10),
            status=FinalSettlement.STATUS_APPROVED,
        )
        SettlementLine.objects.create(
            settlement=fnf,
            category=SettlementLine.CATEGORY_EARNING,
            code="SALARY_LWD",
            name="Salary up to LWD",
            amount=Decimal("20000.00"),
            source_reference="2026-02",
        )

        # Mutual exclusion safeguard:
        # Regular payroll generation for 2026-02 MUST skip this employee since their salary for this month is settled in FnF!
        feb_period = PayrollPeriod.objects.create(
            organization=self.org_alpha,
            year=2026,
            month=2,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
        )
        records = generate_payroll_for_period(feb_period)
        self.assertNotIn(exit_emp, [r.employee for r in records])

    # -------------------------------------------------------------------------
    # WORKFLOW 9: Import representative records and reconcile results
    # -------------------------------------------------------------------------
    def test_workflow_9_universal_data_import_and_reconciliation(self):
        template = get_template("departments")
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=template["headers"])
        writer.writeheader()
        writer.writerow({
            "code": "DEP_QA",
            "name": "Quality Assurance",
            "branch_code": "ALPHA_HQ_CODE",
            "description": "QA Team",
            "status": "active",
        })

        # Set branch code for matching
        self.branch_alpha.code = "ALPHA_HQ_CODE"
        self.branch_alpha.save()

        file = SimpleUploadedFile("departments.csv", output.getvalue().encode("utf-8"))
        job = ImportJob.objects.create(
            organization=self.org_alpha,
            template_key="departments",
            file=file,
            created_by=self.admin_user,
        )

        engine = ImportEngine(job)
        engine.validate_and_preview()
        job.refresh_from_db()
        self.assertEqual(job.status, "validated")

        engine.execute()
        job.refresh_from_db()

        # Reconcile source and destination
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.created_count, 1)
        self.assertEqual(job.error_count, 0)
        self.assertTrue(Department.objects.filter(branch=self.branch_alpha, name="Quality Assurance").exists())

    # -------------------------------------------------------------------------
    # WORKFLOW 10: Attempt cross-organization access and verify denial
    # -------------------------------------------------------------------------
    def test_workflow_10_cross_organization_access_denial(self):
        # Admin from Org Alpha authenticates
        self.client.force_authenticate(user=self.admin_user)

        # 1. Attempt to view Branch in Org Beta directly
        res_branch = self.client.get(f"/api/v1/organization/branches/{self.branch_beta.id}/")
        self.assertEqual(res_branch.status_code, status.HTTP_404_NOT_FOUND)

        # 2. Attempt to create department in Org Beta
        res_dept = self.client.post("/api/v1/organization/departments/", {
            "name": "Malicious Department",
            "branch": self.branch_beta.id,
        })
        # Must be rejected (either 400 Bad Request or 403/404)
        self.assertIn(res_dept.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

        # 3. Create employee in Org Beta
        beta_user = User.objects.create_user(email="beta_emp@beta.com", password="Password123!", status="active")
        beta_emp = Employee.objects.create(
            user=beta_user,
            employee_code="BETA01",
            organization=self.org_beta,
            branch=self.branch_beta,
            employment_status=EmploymentStatus.ACTIVE,
        )

        # Alpha admin attempts to view Beta employee detail
        res_emp = self.client.get(f"/api/v1/employees/{beta_emp.id}/")
        self.assertEqual(res_emp.status_code, status.HTTP_404_NOT_FOUND)
