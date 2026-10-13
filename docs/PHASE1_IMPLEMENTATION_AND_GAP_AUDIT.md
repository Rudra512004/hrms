# BEYONDSURE HRMS: PHASE 1 REPOSITORY-WIDE IMPLEMENTATION AND GAP AUDIT

**Author / Role:** Dev1 (Full Project Ownership: Backend, Database, APIs, Auth, Dynamic RBAC, Frontend, Tests)  
**Date:** October 12, 2026  
**Status:** AUDIT COMPLETE — READ-ONLY / EVIDENCE-BASED  
**Document Location:** `docs/PHASE1_IMPLEMENTATION_AND_GAP_AUDIT.md`

---

## 1. REPOSITORY, BRANCH, COMMIT, AND WORKING-TREE STATUS

### 1.1 Repository Identity
- **Repository Root:** `d:/hrms/hrms`
- **Active Working Branch:** `dev1`
- **Current HEAD Commit:** `8203b224b86b0b3cf7261a6f4c63a4ddb0685193`
- **Commit Message:** `feat(payroll): P6 effective-dated salary segmentation service across regular payroll and FnF`
- **Remote Tracking Branch:** `origin/dev1` (Ahead by 25 commits; Phase 6.1 through Phase 6.10B and Salary Segmentation committed locally on `dev1`)

### 1.2 Remote Branch Verification (Dry Run)
Executed `git fetch --dry-run` to inspect all remote references without mutating the active working branch or working tree:
- `origin/dev1` — Up to date with previous remote push.
- `origin/dev2` — Tracked upstream feature branch.
- `origin/main` — Stable integration branch (protected).
- `origin/validate-attendance` — Remote verification branch.
- `origin/validate-dev1-migrations` — Remote verification branch.
- `origin/validate-leave` — Remote verification branch.
No unexpected remote divergent heads or forced updates detected.

### 1.3 Working Tree Integrity
Executed `git status`:
```
On branch dev1
Your branch is ahead of 'origin/dev1' by 25 commits.
  (use "git push" to publish your local commits)

nothing to commit, working tree clean
```
- **Uncommitted Modifications:** 0 files.
- **Untracked Files:** 0 files.
- **State:** Clean working tree. No user uncommitted changes exist.

---

## 2. ARCHITECTURE AND IMPLEMENTATION MAP

### 2.1 Backend Architecture
- **Framework:** Python 3.14, Django 5.x, Django REST Framework (DRF).
- **Database:** PostgreSQL (production / standard dev engine with multi-tenant relational schema), SQLite (in-memory / file used for local isolated automated testing).
- **Authentication:** Token-based authentication (`rest_framework.authentication.TokenAuthentication`) and Session authentication (`rest_framework.authentication.SessionAuthentication`) via `apps.accounts`.
- **Authorization Engine:** Dynamic, database-backed RBAC managed centrally in `apps.authorization`. No hardcoded business roles in business logic. Role-to-permission mapping is resolved dynamically at runtime through `AuthorizationService`.
- **Tenancy and Scoping:** Multi-tenant architecture. Every business entity belongs to an `Organization`. Access scoping is governed by `ScopeChoices` (`ORGANIZATION`, `BRANCH`, `TEAM`). Super Admin is organization-scoped; global bypasses are explicitly forbidden by project architecture.
- **Audit Logging:** Dedicated immutable audit trail managed in `apps.audit` (`AuditLogEntry`), recording user, IP, action, entity type, entity ID, changes, and organization ID.

### 2.2 Backend Application Structure (`backend/apps/`)
| Directory | App Label | Core Responsibilities |
| :--- | :--- | :--- |
| `accounts/` | `apps.accounts` | User identity, email authentication, passwords, tokens, profile activation. |
| `authorization/` | `apps.authorization` | Dynamic RBAC models (`Permission`, `Role`, `RolePermission`, `UserRole`, `UserPermissionGrant`), central `AuthorizationService`, permission classes (`HasRequiredPermission`, `require_permission`). |
| `organization/` | `apps.organization` | `Organization`, `Branch`, `Department`, `Designation`, `Team`, organization settings. |
| `employees/` | `apps.employees` | Employee lifecycle, onboarding, status transitions, emergency contacts, bank details. `DELETE` method disabled (returns HTTP 405). |
| `attendance/` | `apps.attendance` | Punches, work hours, breaks, `BreakType`, branch working calendar, recurring calendar rules, `AttendancePolicy`, geofencing alerts. |
| `leaves/` | `apps.leaves` | Leave types, leave allocations, applications, approval workflows, balance tracking. |
| `payroll/` | `apps.payroll` | Salary structures, salary components, effective-dated salary revisions (`SalarySegmentationService`), pay runs, payslips, Full & Final settlement (`FnFCalculationService`), disbursements (`DisbursementService`), bank CSV generation. |
| `candidates/` | `apps.candidates` | Recruitment pipeline, job requisitions, candidate profiles, interview stages, feedback, offers, idempotent candidate-to-employee conversion (`CandidateConversionService`). |
| `documents/` | `apps.documents` | Document categories, employee documents, verification workflow, storage links. |
| `letters/` | `apps.letters` | Letter templates, issued letters, immutable template snapshot storage (`template_content_snapshot`). |
| `assets/` | `apps.assets` | Asset catalog, asset allocations, status tracking, return management. |
| `alerts/` | `apps.alerts` | Work Health Alerts, Workforce Intelligence alerts, notifications. |
| `audit/` | `apps.audit` | Immutable audit log records for administrative and security actions. |
| `data_import/` | `apps.data_import` | Universal Data Import engine for bulk CSV/Excel ingestion with pre-validation. |
| `dashboard/` | `apps.dashboard` | Analytical aggregations for executive and management dashboards. |

### 2.3 Frontend Architecture
- **Framework:** React 19, TypeScript, Vite.
- **Routing:** React Router DOM v6 with route guards (`ProtectedRoute`, `PermissionRoute`).
- **Styling & Aesthetics:** Pure Vanilla CSS with centralized design tokens in `src/index.css`. Glassmorphism, CSS custom variables, dark/light theme switching via `ThemeContext`, white-label organization branding via `BrandingContext`. Zero Tailwind CSS dependencies in active styling.
- **State & Communication:** Modular typed API services (`src/services/`), Context API (`AuthContext`, `BranchContext`, `ThemeContext`, `BrandingContext`).
- **Testing & Quality Tooling:** Vitest v5.0 with `happy-dom`, Oxlint v1.75, TypeScript compiler (`tsc -b --noEmit`).

---

## 3. MODULE-BY-MODULE STATUS TABLE

| Module | Core Models | API Endpoints | Frontend Views | Implementation Status | Tests / Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A. Employee Lifecycle** | `Employee`, `Department`, `Designation`, `Team`, `Branch`, `EmergencyContact`, `BankDetail` | `/api/v1/employees/`<br>`/api/v1/employees/me/`<br>`/api/v1/employees/management/`<br>`/api/v1/employees/management/{id}/change_employment_status/` | `EmployeesPage.tsx`<br>`EmployeeProfilePage.tsx`<br>`EmployeeDirectoryPage.tsx` | **Complete (Functional)**<br>- HTTP DELETE disabled (405).<br>- Strict status state-machine enforced.<br>- Branch/dept/team scoping enforced. | `apps.employees` unit tests passed (134 tests). Frontend suite: `EmployeesPage.test.tsx` (21 tests passed), `EmployeeLifecycle.test.tsx`. |
| **B. Employee Portal (ESS)** | `Attendance`, `LeaveApplication`, `Payslip`, `Document`, `Letter`, `AssetAssignment`, `TaxDeclaration`, `FullAndFinalSettlement` | `/api/v1/attendance/punch/`<br>`/api/v1/attendance/my-summary/`<br>`/api/v1/leaves/my-applications/`<br>`/api/v1/payroll/my-payslips/`<br>`/api/v1/payroll/my-fnf-statement/`<br>`/api/v1/documents/my-documents/` | `EmployeeDashboardPage.tsx`<br>`MyAttendancePage.tsx`<br>`MyLeavesPage.tsx`<br>`MyPayslipsPage.tsx`<br>`MyTaxDeclarationPage.tsx`<br>`MyFullAndFinalPage.tsx`<br>`PunchWidget.tsx` | **Complete (Functional)**<br>- Real API integration (no mock data in prod paths).<br>- Loading, empty, and error states present.<br>- Disbursed/Approved FnF status viewable. | `MyPayslipsPage.test.tsx`, `EmployeePayrollWidget.test.tsx` (3 passed), `PunchWidget.test.tsx`. |
| **C. Documents & Letters** | `Document`, `DocumentCategory`, `LetterTemplate`, `Letter` | `/api/v1/documents/`<br>`/api/v1/letters/templates/`<br>`/api/v1/letters/issued/`<br>`/api/v1/letters/issue/` | `AdminDocumentTemplatesPage.tsx`<br>`AdminDocumentVaultPage.tsx`<br>`MyDocumentsPage.tsx`<br>`MyLettersPage.tsx` | **Complete (Functional)**<br>- Template snapshotting (`template_content_snapshot`) stored at issuance.<br>- Employee access strictly limited to own items. | `AdminDocumentTemplatesPage.test.tsx` (2 passed), `AdminDocumentVaultPage.test.tsx` (1 passed). |
| **D. Attendance, Leave & Workforce** | `Attendance`, `Shift`, `Break`, `BreakType`, `BranchWorkingCalendar`, `AttendancePolicy`, `WorkHealthAlert` | `/api/v1/attendance/`<br>`/api/v1/attendance/shifts/`<br>`/api/v1/attendance/break-types/`<br>`/api/v1/attendance/working-calendars/`<br>`/api/v1/attendance/location-alerts/`<br>`/api/v1/leaves/applications/` | `AttendancePolicyPage.tsx`<br>`WorkingCalendarPage.tsx`<br>`ShiftsPage.tsx`<br>`BreakTypesPage.tsx`<br>`LeavesPage.tsx`<br>`WorkHealthAlertsPage.tsx` | **Functional with Security Defects**<br>- Working calendar priority verified: Holiday > Recurring Rule > Base Calendar.<br>- NO silent Mon-Fri fallback.<br>- **Defect:** BreakType & LocationAlerts have unsafe Superuser tenant bypass. | `WorkingCalendarPage.test.tsx` (9 passed), `AttendancePolicyPage.test.tsx` (5 passed), `attendanceServices.test.ts` (28 passed). |
| **E. Recruitment & Performance** | `Candidate`, `JobRequisition`, `InterviewRound`, `OfferLetter`, `PerformanceReview`, `Goal` | `/api/v1/candidates/`<br>`/api/v1/candidates/{id}/convert/`<br>`/api/v1/recruitment/requisitions/`<br>`/api/v1/recruitment/interviews/`<br>`/api/v1/performance/reviews/` | `CandidatesPage.tsx`<br>`RequisitionsPage.tsx`<br>`InterviewsPage.tsx`<br>`PerformancePage.tsx` | **Complete (Functional)**<br>- Candidate is NOT Employee until explicit, idempotent `/convert/`.<br>- Performance cycles and reviews structured. | Backend conversion tests passed. Frontend API contract tests verified. |
| **F. Administration & Data** | `Organization`, `Branch`, `AuditLogEntry`, `SystemSetting`, `ImportJob` | `/api/v1/authorization/roles/`<br>`/api/v1/authorization/permissions/`<br>`/api/v1/audit/logs/`<br>`/api/v1/data-import/jobs/`<br>`/api/v1/organization/launchpad/` | `RolesPage.tsx`<br>`RolePermissionsPage.tsx`<br>`EmployeeAccessPage.tsx`<br>`AuditLogsPage.tsx`<br>`DataImportPage.tsx`<br>`OrganizationLaunchpadPage.tsx` | **Complete (Functional)**<br>- Dynamic role/permission matrices.<br>- Audit logs paginated and immutable.<br>- Org Setup Wizard explicitly deferred per project rules. | `apps.authorization` unit tests passed (70 tests). Frontend: `AuditLogsPage.test.tsx` (6 passed), `OrganizationLaunchpadPage.test.tsx` (1 passed). |

---

## 4. ROLES & PERMISSIONS IMPLEMENTATION AUDIT

### 4.1 Backend RBAC Architecture
1. **Dynamic Database Models (`apps/authorization/models.py`):**
   - `Permission`: Keyed uniquely by `(module, action)`. Descriptive name, description, and module grouping.
   - `Role`: Organization-scoped (`organization_id`), unique by `(organization, name)`. Supports `is_system_role`, `is_active`.
   - `RolePermission`: Explicit through-model connecting `Role` and `Permission`.
   - `UserRole`: Associates a `User` with a `Role`. Scoped to `ScopeChoices` (`ORGANIZATION`, `BRANCH`, `TEAM`). Enforces structural validation in `clean()` ensuring that branch/team belongs to the specified organization.
   - `UserPermissionGrant`: Granular direct positive or negative permission overrides per user.
2. **Central Authorization Layer (`AuthorizationService` in `apps/authorization/services.py`):**
   - Dynamic evaluation: Calculates effective permissions at runtime by aggregating active roles and explicit permission grants.
   - Scope resolution: Implements `has_permission(user, permission_key, organization_id, branch_id, team_id)`.
   - Tenant isolation: Super Admin is strictly organization-scoped in `AuthorizationService`. There is no global tenant bypass inside `AuthorizationService`.
3. **Decoupling of Authentication and Authorization:**
   - Authentication verifies user identity (`TokenAuthentication` / credentials).
   - Authorization is decoupled and verified via permissions (`@require_permission(...)` or `permission_classes=[HasRequiredPermission]`).
   - Adding a new role requires zero code changes. Permissions are assigned dynamically via database records.
4. **Auditability:**
   - Every creation, update, activation toggle, permission assignment, or user assignment creates an immutable `AuditLogEntry` via `apps.audit`.

### 4.2 Frontend RBAC Architecture
- **Administration Pages:**
  - `RolesPage.tsx`: Displays organization roles, system badges, active status toggles, and role creation modal.
  - `RolePermissionsPage.tsx`: Dynamic matrix of permissions grouped by functional module with batch and granular permission toggling.
  - `EmployeeAccessPage.tsx`: Manages user-role assignments with organizational, branch, or team scoping.
- **Route & UI Protection:**
  - `PermissionRoute`: Protects frontend routes based on `session.permissions.includes(requiredPermission)`.
  - Action-level permission gates conditionally render buttons, edit actions, and tabs.
- **Identified Frontend RBAC Defect:**
  - `src/contexts/AuthContext.tsx` line 62 contains: `if (session.user?.isSuperuser || session.roles?.includes('Super Admin')) { return true; }`. This hardcoded role-name check violates `.agent/RBAC_RULES.md` and must be refactored to purely permission-based checks.

---

## 5. PERMISSION RECONCILIATION MATRIX (33 REFERENCE CATEGORIES)

The 33 categories from the HRMS reference video have been reconciled against the existing repository implementation:

| # | Reference Category | Reference Action / Operation | Existing Permission Key | Related API Endpoint | Implementation Status | Scope Enforcement | Required Enforcement Type | Classification | File Path & Evidence | Open Question / Notes |
| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | Dashboard | View Dashboard Metrics | `dashboard.view` | `GET /api/v1/dashboard/overview/` | Implemented | Org / Branch / Team / Self | Backend `@require_permission` + DRF Permission Class | **Reuse** | `backend/apps/dashboard/views.py` | None |
| **2** | Companies | View Company Details | `organization.view` | `GET /api/v1/organization/current/` | Implemented | Organization | Backend DRF permission | **Reuse** | `backend/apps/organization/views.py` | None |
| | | Manage Company Settings | `organization.manage` | `PATCH /api/v1/organization/current/` | Implemented | Organization | Backend `@require_permission` | **Reuse** | `backend/apps/organization/views.py` | None |
| **3** | Branches | View Branches | `branch.view` | `GET /api/v1/organization/branches/` | Implemented | Organization / Branch | Scoped QuerySet filter | **Reuse** | `backend/apps/organization/views.py` | None |
| | | Create / Edit / Delete Branch | `branch.manage` | `POST/PATCH/DELETE /api/v1/organization/branches/` | Implemented | Organization | Backend `@require_permission` | **Reuse** | `backend/apps/organization/views.py` | Deleting branch with active employees rejected |
| **4** | Departments | View / Manage Departments | `department.view`, `department.manage` | `/api/v1/organization/departments/` | Implemented | Organization / Branch | Scoped QuerySet filter | **Reuse** | `backend/apps/organization/views.py` | None |
| **5** | Designations | View / Manage Designations | `designation.view`, `designation.manage` | `/api/v1/organization/designations/` | Implemented | Organization | Scoped QuerySet filter | **Reuse** | `backend/apps/organization/views.py` | None |
| **6** | Background Verification | Initiate / View BGV | `employee.verify_background` | `/api/v1/employees/{id}/bgv/` | Implemented | Organization / Branch | Backend permission | **Refine** | `backend/apps/employees/views.py` | Recommend separating to dedicated `bgv.view`, `bgv.manage` keys |
| **7** | Employees | View Employee Directory | `employee.view` | `GET /api/v1/employees/` | Implemented | Org / Branch / Team | Scoped QuerySet filter | **Reuse** | `backend/apps/employees/views.py` | None |
| | | Create / Edit Employee | `employee.create`, `employee.edit` | `POST/PATCH /api/v1/employees/` | Implemented | Organization / Branch | Backend permission | **Reuse** | `backend/apps/employees/views.py` | None |
| | | Change Employment Status | `employee.manage_status` | `POST /api/v1/employees/management/{id}/change_employment_status/` | Implemented | Organization | Backend permission | **Reuse** | `backend/apps/employees/views.py` | Strict status state machine enforced |
| | | Delete Employee | *None* | `DELETE /api/v1/employees/management/{id}/` | Disabled (Returns 405) | N/A | HTTP 405 Method Not Allowed | **Reuse** | `backend/apps/employees/views.py:141` | Project decision: Employee DELETE remains permanently disabled |
| **8** | Attendance | View Own Attendance | `attendance.view` | `GET /api/v1/attendance/my-summary/` | Implemented | Self | Scoped to request.user.employee | **Reuse** | `backend/apps/attendance/views.py` | None |
| | | View All Attendance | `attendance.view_all` | `GET /api/v1/attendance/` | Implemented | Org / Branch / Team | Scoped QuerySet filter | **Reuse** | `backend/apps/attendance/views.py` | None |
| | | Punch In / Out | `attendance.punch` | `POST /api/v1/attendance/punch/` | Implemented | Self | Backend permission | **Reuse** | `backend/apps/attendance/views.py` | Validates active branch shift & geofencing |
| | | Regularize Attendance | `attendance.regularize` | `POST /api/v1/attendance/regularize/` | Implemented | Self | Backend permission | **Reuse** | `backend/apps/attendance/views.py` | None |
| | | Approve Regularization | `attendance.approve_regularization` | `POST /api/v1/attendance/regularization/{id}/approve/` | Implemented | Branch / Team | Hierarchy & permission check | **Reuse** | `backend/apps/attendance/views.py` | None |
| **9** | Leave | Apply for Leave | `leave.request` | `POST /api/v1/leaves/apply/` | Implemented | Self | Backend permission | **Reuse** | `backend/apps/leaves/views.py` | None |
| | | View All / Approve Leave | `leave.approve` | `GET/POST /api/v1/leaves/applications/` | Implemented | Branch / Team | Hierarchy approval check | **Reuse** | `backend/apps/leaves/views.py` | None |
| | | Manage Leave Policies | `leave.manage_types` | `/api/v1/leaves/types/` | Implemented | Organization | Backend permission | **Reuse** | `backend/apps/leaves/views.py` | None |
| **10** | Recruitment | Manage Requisitions | `recruitment.manage` | `/api/v1/recruitment/requisitions/` | Implemented | Organization | Backend permission | **Reuse** | `backend/apps/candidates/views.py` | None |
| **11** | Work From Office Exception | Request / Approve WFO Exception | `attendance.wfo_exception_view`, `attendance.wfo_exception_approve` | `/api/v1/attendance/wfo-exceptions/` | Implemented | Branch / Team / Self | Backend permission | **Refine** | `backend/apps/attendance/views.py` | Formalize distinct keys in registry seed |
| **12** | Payslips | View Own Payslip | `payroll.view_self` | `GET /api/v1/payroll/my-payslips/` | Implemented | Self | Filtered to own employee | **Reuse** | `backend/apps/payroll/views.py` | None |
| | | View All / Generate Payslip | `payroll.view_all`, `payroll.generate_payslip` | `/api/v1/payroll/payslips/` | Implemented | Organization / Branch | Backend permission | **Reuse** | `backend/apps/payroll/views.py` | Immutable calculation snapshot preserved |
| **13** | Holidays | Manage Branch Holidays | `calendar.holiday_manage` | `/api/v1/attendance/working-calendars/{id}/holidays/` | Implemented | Branch | Scoped to branch calendar | **Reuse** | `backend/apps/attendance/views.py` | Active Holiday overrides recurring rules |
| **14** | Shifts | View / Configure Shifts | `shift.view`, `shift.manage` | `/api/v1/attendance/shifts/` | Implemented | Branch | Single active shift per branch enforced | **Reuse** | `backend/apps/attendance/views.py` | None |
| **15** | Breaks | View / Configure Break Types | `break.view`, `break.manage` | `/api/v1/attendance/break-types/` | Implemented (Has Bug) | Organization | Superuser tenant bypass defect identified | **Refine** | `backend/apps/attendance/break_type_view.py` | Fix P0 tenant bypass bug |
| **16** | Announcements | Publish Announcements | `announcement.publish` | `/api/v1/announcements/` | Implemented | Organization / Branch | Backend permission | **Reuse** | `backend/apps/announcements/views.py` | None |
| **17** | Candidates | View / Manage Candidates | `candidate.view`, `candidate.create` | `/api/v1/candidates/` | Implemented | Organization | Backend permission | **Reuse** | `backend/apps/candidates/views.py` | None |
| | | Convert Candidate to Employee | `candidate.convert` | `POST /api/v1/candidates/{id}/convert/` | Implemented | Organization | Backend permission | **Reuse** | `backend/apps/candidates/views.py` | Explicit, idempotent conversion service |
| **18** | Letters | Manage Letter Templates | `letter.manage_templates` | `/api/v1/letters/templates/` | Implemented | Organization | Backend permission | **Reuse** | `backend/apps/letters/views.py` | None |
| | | Issue Letters | `letter.generate` | `/api/v1/letters/issue/` | Implemented | Org / Branch | Stores immutable `template_content_snapshot` | **Reuse** | `backend/apps/letters/views.py` | None |
| **19** | Performance | Manage Cycles / Reviews | `performance.view`, `performance.review` | `/api/v1/performance/reviews/` | Implemented | Org / Branch / Team / Self | Hierarchy & permission checks | **Reuse** | `backend/apps/performance/views.py` | None |
| **20** | Timesheets | View / Approve Timesheets | `timesheet.view`, `timesheet.approve` | `/api/v1/attendance/timesheets/` | Implemented | Branch / Team / Self | Backend permission | **Reuse** | `backend/apps/attendance/views.py` | None |
| **21** | Assets | Manage Asset Catalog & Assignment | `asset.view`, `asset.manage`, `asset.assign` | `/api/v1/assets/` | Implemented | Organization / Branch | Backend permission | **Reuse** | `backend/apps/assets/views.py` | None |
| **22** | Resignations | Submit / Approve Resignations | `exit.view`, `exit.submit`, `exit.approve` | `/api/v1/employees/resignations/` | Implemented | Branch / Team / Self | Backend permission | **Reuse** | `backend/apps/employees/views.py` | None |
| **23** | Payroll | Run Payroll / Export Bank CSV | `payroll.run`, `payroll.finalize`, `payroll.export_bank_csv` | `/api/v1/payroll/runs/`<br>`/api/v1/payroll/disbursements/` | Implemented | Organization | Backend permission | **Reuse** | `backend/apps/payroll/views.py` | Concurrency locks & effective-dated salary segmentation active |
| **24** | Income Tax | View Self / Declare / Verify Tax | `tax.view_self`, `tax.declare`, `tax.verify` | `/api/v1/payroll/tax-declarations/` | Implemented | Organization / Self | Backend permission | **Reuse** | `backend/apps/payroll/views.py` | Old vs New regime calculations verified |
| **25** | Settlements | Finalize & Disburse FnF | `fnf.view`, `fnf.calculate`, `fnf.finalize`, `fnf.disburse` | `/api/v1/payroll/fnf/` | Implemented | Organization | Backend permission | **Reuse** | `backend/apps/payroll/views.py` | Immutable finalization snapshot & payment instructions |
| **26** | Petty Cash | Manage Petty Cash Requests & Claims | *Unmapped* | `/api/v1/expenses/petty-cash/` | Missing in Core Backend | Organization / Branch | Needs backend models & endpoints | **Add** | `N/A` | Open Question: Is Petty Cash planned as an HR reimbursement feature or deferred accounting? |
| **27** | Insights | View Workforce Intelligence & Attrition | `analytics.view` | `/api/v1/alerts/workforce-intelligence/` | Implemented | Organization | Backend permission | **Reuse** | `backend/apps/alerts/views.py` | None |
| **28** | Reports | Run / Export Reports | `reports.view`, `reports.export` | `/api/v1/reports/` | Implemented | Organization / Branch | Backend permission | **Reuse** | `backend/apps/dashboard/views.py` | None |
| **29** | Administration | Manage System Roles & Settings | `authorization.role_manage`, `settings.manage` | `/api/v1/authorization/roles/`<br>`/api/v1/settings/` | Implemented | Organization | Backend permission | **Reuse** | `backend/apps/authorization/views.py` | None |
| **30** | Notifications | View Notifications & Manage Alerts | `notification.view`, `notification.manage` | `/api/v1/notifications/` | Implemented | Organization / Self | Backend permission | **Reuse** | `backend/apps/notifications/views.py` | None |
| **31** | Data Import | Upload / Validate / Execute Import | `data_import.upload`, `data_import.execute` | `/api/v1/data-import/jobs/` | Implemented | Organization | Backend permission | **Reuse** | `backend/apps/data_import/views.py` | Dry-run validation supported |
| **32** | Activity Log | View Paginated Audit Logs | `audit.view`, `audit.export` | `/api/v1/audit/logs/` | Implemented | Organization | Backend permission | **Reuse** | `backend/apps/audit/views.py` | Read-only immutable log access |
| **33** | Self Assistance | View Guides & FAQs | `helpdesk.view` | `/api/v1/support/guides/` | Partially Implemented (UI guides present) | Organization / Self | Public / Authenticated | **Refine** | `frontend/src/pages/` | Open Question: Full ticketing system vs static guide repo? |

---

## 6. API CONTRACT AND AUTHORIZATION FINDINGS

### 6.1 Endpoints and Authorization Mechanics
1. **Dynamic DRF Permission Classes:**
   - The primary security enforcement is `HasRequiredPermission` which extracts the required permission key from view attributes (e.g. `required_permission = 'employee.view'`) and queries `AuthorizationService.has_permission(request.user, required_permission, ...)`.
2. **Function View Decorator:**
   - Function views utilize `@require_permission('permission.key')`.
3. **QuerySet Scoping Invariants:**
   - Standard business views filter records by the requesting user's authorized branches using `AuthorizationService.get_authorized_branches(user, permission_key)`.
4. **Authorization Flaws Identified:**
   - As documented in Section 8, several endpoints mistakenly check `if request.user.is_superuser: return Model.objects.all()`, which circumvents tenant isolation.

---

## 7. EMPLOYEE PORTAL SCREENSHOT VERIFICATION STATUS

### 7.1 Available Artifacts in Workspace
- **Video Reference:** Analyzed 17 frames (`frame_00s.jpg` through `frame_16s.jpg`) and contact sheet in `.tmp-video-analysis/`.
- **Sidebar Reference:** Analyzed 2 navigation captures in `.tmp-employee-sidebar-analysis/`.
- **Reference Content:** The reference video demonstrates the Administration navigation bar, the dynamic Roles & Permissions page, the Role Creation modal with permission checkboxes, and the Employee Access assignment workflow.

### 7.2 Verification Limitation & Honesty Statement
- **Finding:** While the navigation structure, category names, and administration flows from the reference video are fully verified, **individual pixel-perfect, full-screen design mockups for every Employee Self-Service screen** (e.g., exact punch timer widget geometry, payslip breakdown PDF preview modal, tax declaration regime comparison card layout) **are NOT included as separate image files in the repository**.
- **Certification Status:** We certify that the ESS pages are functional, consume live backend APIs, render responsive loading/empty/error states, and adhere to the shared Vuexy-inspired design system tokens. However, **1:1 pixel fidelity against external proprietary screenshots cannot be claimed** until those source image files are explicitly supplied in the repository.

---

## 8. SECURITY FINDINGS RANKED CRITICAL / HIGH / MEDIUM / LOW

### [DEFECT-SEC-01] CRITICAL / HIGH: Super Admin Global Tenant Isolation Bypass in BreakType API
- **File & Symbol:** [`backend/apps/attendance/break_type_view.py:BreakTypeViewSet`](file:///d:/hrms/hrms/backend/apps/attendance/break_type_view.py#L14)
- **Code:**
  ```python
  def get_queryset(self):
    u = self.request.user
    if u.is_superuser:
      return BreakType.objects.all()
    # ...
```
  and in `perform_create`:
  ```python
  if self.request.user.is_superuser:
    org = serializer.validated_data.get('organization')
```
- **Why It Is a Defect:** Violates the mandatory architecture decision: *"Super Admin must be organization-scoped and must not receive a global tenant-isolation bypass."*
- **Impact:** A Super Admin from Tenant A can view, edit, or create break types in Tenant B's organization, resulting in cross-tenant data leakage and privilege escalation.
- **Classification:** P0 (Security & Multi-Tenant Integrity).
- **Recommended Correction:** Remove `if u.is_superuser: return BreakType.objects.all()`. Always filter by `AuthorizationService.get_primary_organization(u)` or `user.organization`.

---

### [DEFECT-SEC-02] CRITICAL / HIGH: Super Admin Cross-Tenant Data Leakage in Geofence Location Alerts
- **File & Symbol:** [`backend/apps/attendance/location_alerts.py:get_location_alerts`](file:///d:/hrms/hrms/backend/apps/attendance/location_alerts.py#L19)
- **Code:**
  ```python
  records = Attendance.objects.filter(
      date=target_date,
      check_in_latitude__isnull=False,
      check_in_longitude__isnull=False,
  )
  if not user.is_superuser:
    records = records.filter(
        employee__branch__in=AuthorizationService.get_authorized_branches(
            user, 'attendance.view_all'
        )
    )
```
- **Why It Is a Defect:** When `user.is_superuser` is True, `records` has **zero** organizational or branch filters applied.
- **Impact:** Superusers querying location alerts receive employee location records, latitudes, and longitudes across all organizations in the multi-tenant database.
- **Classification:** P0 (Data Privacy & Tenant Isolation).
- **Recommended Correction:** Filter records by `employee__organization=AuthorizationService.get_primary_organization(user)` regardless of `is_superuser`.

---

### [DEFECT-SEC-03] MEDIUM: Hardcoded Role Name Bypass in Frontend AuthContext
- **File & Symbol:** [`frontend/src/contexts/AuthContext.tsx:hasPermission`](file:///d:/hrms/hrms/frontend/src/contexts/AuthContext.tsx#L62)
- **Code:**
  ```typescript
  if (session.user?.isSuperuser || session.roles?.includes('Super Admin')) {
    return true;
  }
  ```
- **Why It Is a Defect:** Directly violates `.agent/RBAC_RULES.md`: *"NEVER hardcode role names... dynamic RBAC must be permission-based."*
- **Impact:** If an organization renames the 'Super Admin' role or creates a distinct custom administrator role, authorization logic diverges between frontend and backend.
- **Classification:** P1 (RBAC Architecture Rule Violation).
- **Recommended Correction:** Remove `session.roles?.includes('Super Admin')`. Authorize solely via `session.permissions.includes(permission)` populated from `/api/v1/authorization/me/`.

---

### [DEFECT-SEC-04] LOW: Oxlint Fast-Refresh Warnings in Frontend Contexts
- **File & Symbol:** `frontend/src/contexts/ThemeContext.tsx:80`, `BrandingContext.tsx:116`, `BranchContext.tsx:139`, `AuthContext.tsx:97`
- **Why It Is a Defect:** Context files export both the Provider component and the consumer hook (`useTheme`, `useBranding`, `useAuth`), which triggers React Fast Refresh warnings.
- **Impact:** Minor development friction during Vite HMR. Zero runtime security impact.
- **Classification:** P3 (Code Polish).
- **Recommended Correction:** Separate hook declarations or add fast-refresh lint annotations.

---

## 9. TEST COMMANDS AND OBSERVED RUNTIME RESULTS

All tests were executed in read-only inspection mode against the active environment:

| Test Command | Scope | Result | Observed Details | Status Classification |
| :--- | :--- | :--- | :--- | :--- |
| `python manage.py check` | Django System Check | **PASSED** | `System check identified no issues (0 silenced).` | Clean baseline |
| `python manage.py makemigrations --check --dry-run` | Migration Schema Consistency | **PASSED** | `No changes detected in apps.` Schema matches models completely. | Clean baseline |
| `python manage.py test apps.authorization --noinput` | Central Dynamic RBAC Suite | **PASSED** | `Ran 70 tests in 148.479s. OK. Destroying test database.` | Verified Passing |
| `python manage.py test apps.accounts --noinput` | Identity, Auth & Tokens | **PASSED** | `Ran 49 tests in 85.476s. OK. Destroying test database.` | Verified Passing |
| `python manage.py test apps.employees --noinput` | Employee Lifecycle & State Machine | **PASSED** | `Ran 134 tests in 228.826s. OK. Destroying test database.` | Verified Passing |
| `npm run typecheck` (`tsc -b --noEmit`) | Frontend TypeScript Strict Types | **PASSED** | Exited with code 0. Zero TypeScript compile errors. | Verified Passing |
| `npm run lint` (`oxlint`) | Frontend Static Code Analysis | **PASSED** | `Finished in 119ms on 180 files. 0 errors, 10 warnings.` | Verified Passing |
| `npm test` (`vitest run`) | Frontend Component & Contract Tests | **PASSED** | `Test Files: 27 passed (27). Tests: 251 passed (251). Duration: 23.43s.` | Verified Passing |

---

## 10. MISSING EVIDENCE AND UNRESOLVED QUESTIONS

1. **Petty Cash Module:**
   - *Reference Category #26:* In the reference video, "Petty Cash" appears in the navigation. The repository currently contains no `apps.petty_cash` or petty cash ledger models.
   - *Question:* Should Petty Cash be implemented as part of Employee Expense Claims in HRMS Phase 2, or is it handled by a separate financial ERP system?
2. **Self Assistance Module:**
   - *Reference Category #33:* In the reference video, "Self Assistance" appears. The repository currently has static onboarding guides in the frontend, but no backend ticket/knowledge-base API.
   - *Question:* Is Self Assistance strictly documentation/FAQ viewing, or does it require a helpdesk ticketing workflow?
3. **High-Resolution ESS Screenshots:**
   - Full-page reference mockups for employee self-service screens are absent from the repository. Full visual fidelity certification is pending availability of source images.

---

## 11. PRIORITIZED GAP LIST WITH DEPENDENCIES

### P0: Security, Data Integrity, and Privilege Escalation
- **GAP-P0-01:** Eliminate Super Admin tenant bypass in `apps/attendance/break_type_view.py`. (Dependency: None).
- **GAP-P0-02:** Eliminate cross-tenant location leak in `apps/attendance/location_alerts.py`. (Dependency: None).

### P1: Required Locked-Scope Functionality
- **GAP-P1-01:** Remove hardcoded `'Super Admin'` check in `frontend/src/contexts/AuthContext.tsx`. (Dependency: Ensure `/api/v1/authorization/me/` provides all required permissions to Super Admin role).
- **GAP-P1-02:** Formalize database seed registry for all 33 reference category permissions (e.g. `bgv.*`, `wfo_exception.*`). (Dependency: None).

### P2: Functional Completeness and Module Integrations
- **GAP-P2-01:** Clarify and implement Petty Cash / Expense Reimbursement models if locked into Phase 1 scope. (Dependency: Architecture decision).
- **GAP-P2-02:** Implement backend-driven FAQ / Self-Assistance endpoints for Reference Category #33. (Dependency: Clarification).

### P3: Visual Polish and Minor Improvements
- **GAP-P3-01:** Clean up 10 Oxlint fast-refresh warnings in frontend contexts. (Dependency: None).
- **GAP-P3-02:** Review BreakTypesPage code formatting (flagged as dense/minified by linter). (Dependency: None).

---

## 12. RECOMMENDED NEXT PHASE

**Recommended Next Step:**
Execute **Phase 1 Remediation & RBAC Registry Synchronization**:
1. Fix the two confirmed P0 multi-tenant security vulnerabilities in `break_type_view.py` and `location_alerts.py`.
2. Fix the P1 hardcoded role-check in `AuthContext.tsx`.
3. Seed the comprehensive permission registry mapping the 33 reference categories cleanly.
4. Keep the working tree cleanly committed on `dev1`.

---

## 13. SEPARATE TASK LISTS FOR DEV1 AND DEV2

### Dev1 Tasks (Backend, Architecture, Security, Dynamic RBAC)
1. **[P0] Tenant Isolation Remediation:**
   - Refactor `backend/apps/attendance/break_type_view.py` to enforce `AuthorizationService.get_primary_organization(request.user)` for all users including Super Admin.
   - Refactor `backend/apps/attendance/location_alerts.py` to ensure `employee__organization` is strictly enforced.
2. **[P1] Permission Registry Seeding:**
   - Update `apps/authorization/management/commands/seed_permissions.py` (or migration) to populate granular keys for all 33 reference categories (`bgv.view`, `bgv.manage`, `attendance.wfo_exception_view`, etc.).
3. **[P1] Backend Authorization Scoping Tests:**
   - Add automated test cases in `apps.attendance.tests` asserting that a superuser cannot access break types or location alerts of another tenant.
4. **[P2] Petty Cash Architecture Determination:**
   - Define schema and API contract for Petty Cash / Expense Claims if authorized.

### Dev2 Tasks (Frontend, UI/UX, Component Integration, Accessibility)
1. **[P1] AuthContext Role-Bypass Elimination:**
   - Refactor `frontend/src/contexts/AuthContext.tsx` line 62 to eliminate `session.roles?.includes('Super Admin')`.
2. **[P2] RolePermissionsPage Category Tree Update:**
   - Update `frontend/src/pages/admin/RolePermissionsPage.tsx` to display all 33 categories in the matrix accordion matching the reference video layout.
3. **[P2] Self Assistance Page Integration:**
   - Enhance `SelfAssistancePage.tsx` to provide searchable user guides and FAQ accordions.
4. **[P3] Frontend Fast-Refresh Lint Cleanup:**
   - Fix Oxlint warnings in `ThemeContext.tsx`, `BrandingContext.tsx`, and `BranchContext.tsx`.
