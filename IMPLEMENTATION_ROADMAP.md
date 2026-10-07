# HRMS SaaS — Implementation Roadmap
**Target:** Parity and superiority over Zoho People, Keka HR, and We360.ai
**Branch:** dev1
**Repository HEAD at creation:** 7fc1a3fd6af285641c128b5cb6702dd82a95f438
**Created:** 2026-10-05

---

## Pre-Flight Guardrails (Non-Negotiable)
- `.agent/ARCHITECTURE_RULES.md` — Decoupled SPA + API; strict modular Django apps
- `.agent/RBAC_RULES.md` — ALL auth is permission-based; NEVER hardcode role names
- `.agent/DATABASE_RULES.md` — All schema changes via Django migrations, ORM only
- `.agent/API_RULES.md` — RESTful, paginated, token-auth, strict permission checks
- `.agent/CODING_RULES.md` — PEP 8 backend, ESLint frontend, meaningful commits
- `.agent/GIT_RULES.md` — Descriptive commits, no secrets, no build artifacts

---

## Current Repository Baseline

### Backend Apps and Last Migration Numbers

| App | Last Migration | Key Existing Models |
|-----|---------------|---------------------|
| accounts | 0002 | User, TenantOwnerRegistration |
| organization | 0011 | Organization, Branch, Department, Team, Designation, WorkingCalendar, WorkingCalendarRule, OfficeNetwork, AttendancePolicy |
| employees | 0012 | Employee, WFHRequest, EmployeeIDSequence, EmployeeLifecycleEvent, EmployeeDocument, ReviewCycle, PerformanceReview |
| candidates | 0001 | Candidate, LetterTemplate, IssuedLetter, CandidateDocument, CandidateOnboardingNote |
| attendance | 0014 | Attendance, AttendanceBreak, BreakType, TimesheetPolicy, Project, Timesheet, TimeEntry, Holiday, Shift, EmployeeShiftAssignment |
| leaves | 0004 | LeaveType, BranchLeavePolicy, LeaveCycle, LeaveBalance, LeaveBalanceTransaction, LeaveRequest |
| payroll | 0006 | CompensationHistory, PayrollPeriod, PayrollRecord, Payslip, SalaryComponent, SalaryStructure, SalaryStructureComponent |
| assets | 0001 | AssetCategory, Asset, AssetAssignment |
| notifications | 0005 | Notification, Announcement |
| audit | 0003 | AuditLog |
| authorization | 0004 | Permission, Role, RolePermission, UserRole, UserPermissionGrant |
| dashboard | — | Analytics views |

### Existing Frontend Pages (already wired)
Admin: OrganizationsPage, BranchesPage, DepartmentsPage, TeamsPage, DesignationsPage, WorkingCalendarPage, ShiftsPage, HolidaysPage, AdminLeaveTypesPage, AdminLeavePage, EmployeesPage, EmployeeProfilePage, EmployeeAccessPage, RolesPage, RolePermissionsPage, AttendanceManagementPage, AttendancePolicyPage, BreakTypesPage, ProjectsPage, PayrollPage, SalaryConfigurationPage, AssetsPage, CandidatesPage, CandidateDetailPage, LetterTemplatesPage, AuditLogsPage, AnnouncementsPage, OfficeNetworksPage, LocationAlertsPage, WfhRequestsPage, DailyRosterPage, TimesheetPolicyPage, OrganizationLaunchpadPage, OrganizationControlCenterPage

Employee self-service: DashboardPage, AttendancePage, LeavePage, TimesheetsPage, CalendarPage, MyPayslipsPage, MyAssetsPage, ReviewsPage, EmployeeInformationPage, ProfilePage

Onboarding: OnboardingActivatePage, OnboardingProfilePage, OnboardingDocumentsPage, OnboardingLettersPage, OnboardingOverviewPage

---

## Phase Execution Status

| Phase | Name | Status |
|-------|------|--------|
| P1 | Tenant-Wise Dynamic UI Branding and First-Time Setup Customizer | NOT STARTED |
| P2 | Complete Hire-to-Retire Employee Lifecycle Data | NOT STARTED |
| P3 | Email Template Editor, Editable PDF Engine and Versioned Document Vault | NOT STARTED |
| P4 | We360.ai Workforce Intelligence and Productivity Suite | NOT STARTED |
| P5 | Default and Dynamic Employee Work Health Alerts | NOT STARTED |
| P6 | Statutory Payroll, Tax Declarations and Automated Exit/FnF Settlement | NOT STARTED |
| P7 | Enterprise Supportive and Self-Running HRMS Capabilities | NOT STARTED |
| P8 | Universal HRMS Data Migration and Smart Importer Engine | NOT STARTED |

---

## PHASE 1 — Tenant-Wise Dynamic UI Branding and First-Time Setup Customizer

### Backend Tasks
- [ ] Migration organization/0012: Create TenantBrandingAndConfig (OneToOne to Organization)
  - logo_url, favicon_url, login_banner_url, watermark_url, watermark_opacity (DecimalField 0-1)
  - primary_color, secondary_color, accent_color, sidebar_bg_color
  - default_theme_mode (light/dark), font_family, currency_code, date_format
  - enabled_modules_json (JSONField), custom_fields_schema (JSONField)
  - Auto-created via post_save signal on Organization creation
- [ ] TenantBrandingAndConfigSerializer in organization/serializers.py
- [ ] Inline action on OrganizationViewSet: GET/PATCH /api/v1/organization/{id}/branding/
  - Requires organization.manage (Super Admin) or organization.update (Tenant Admin scoped to own org)
- [ ] Embed branding inline on org detail GET response
- [ ] New RBAC permissions to seed: branding.manage, custom_fields.manage

### Frontend Tasks
- [ ] ThemeContext.tsx — Load TenantBrandingAndConfig from backend on auth; hydrate CSS variables --color-primary, --color-secondary, --color-accent, --sidebar-bg, --font-family on document.documentElement; apply default_theme_mode
- [ ] New BrandingContext.tsx — Branding state provider, re-hydrates on org switch
- [ ] GlobalWatermark.tsx — Dynamic watermark_url and watermark_opacity from branding context
- [ ] Sidebar.tsx — Dynamic logo_url with fallback; bind --sidebar-bg
- [ ] Header.tsx — Dynamic favicon injection via document.head link from favicon_url
- [ ] OrganizationLaunchpadPage.tsx — Brand and Theme Studio step: color pickers, font selector, live CSS preview, logo/favicon/watermark upload, module toggles, custom_fields_schema JSON builder
- [ ] OrganizationControlCenterPage.tsx — Mirror Brand Studio as persistent settings tab
- [ ] Service frontend/src/services/branding.ts — getBranding(orgId), updateBranding(orgId, data)
- [ ] Tests: apps/organization/tests_branding.py; OrganizationLaunchpadPage branding tab tests

---

## PHASE 2 — Complete Hire-to-Retire Employee Lifecycle Data

### Backend Tasks
- [ ] Migration employees/0013: Create EmployeeStatutoryAndBank (OneToOne to Employee)
  - pan_number, aadhaar_number (masked), passport_number, passport_expiry, driving_license_number
  - uan_number, pf_account_number, eps_number, esic_number
  - is_pt_applicable, is_lwf_applicable
  - bank_name, bank_branch, account_number, ifsc_code, swift_code
  - payment_mode (BANK_TRANSFER/CHEQUE/CASH), tax_regime (OLD/NEW)
- [ ] Migration employees/0014: Create EmployeeDependent (FK to Employee)
  - full_name, relationship, dob, gender
  - is_emergency_contact, is_insurance_dependent
  - pf_nominee_share, gratuity_nominee_share, esic_nominee_share (DecimalFields)
- [ ] Migration employees/0015: Create EmployeeEducation (FK to Employee)
  - degree, specialization, institution, completion_year, grade_or_cgpa
- [ ] Migration employees/0016: Create EmployeePriorExperience (FK to Employee)
  - employer_name, designation, start_date, end_date, last_drawn_ctc, reason_for_leaving
  - bgv_status (PENDING/IN_PROGRESS/VERIFIED/DISCREPANCY)
  - relieving_letter (FileField), experience_letter (FileField)
- [ ] Migration employees/0017: Add custom_fields_data (JSONField default {}) to Employee
- [ ] Migration candidates/0002: Create JobRequisition
  - organization (FK), branch (FK nullable), department (FK nullable), designation (FK)
  - headcount, budget_ctc, justification
  - approval_status (DRAFT/SUBMITTED/APPROVED/REJECTED)
  - approved_by (User FK nullable), created_by (User FK)
- [ ] Migration candidates/0003: Create InterviewScorecard
  - candidate (FK), round_name, interviewer (User FK)
  - technical_score, cultural_score, recommendation (STRONG_YES/YES/MAYBE/NO)
  - comments, interviewed_at
- [ ] Service candidates/services.py: convert_candidate_to_employee() — atomic transaction creating User (pending activation), Employee, updating EmployeeIDSequence, migrating CandidateDocument to EmployeeDocument, setting candidate.status=CONVERTED, emitting AuditLog
- [ ] Serializers for all new models in employees/serializers.py and candidates/serializers.py
- [ ] Nested ViewSets: /api/v1/employees/{id}/statutory/, /dependents/, /education/, /experience/
- [ ] ViewSets: /api/v1/candidates/requisitions/, /api/v1/candidates/{id}/scorecards/
- [ ] New RBAC permissions: employee.view_statutory, employee.manage_statutory, bgv.manage, candidate.requisition.manage, candidate.interview.manage

### Frontend Tasks
- [ ] EmployeeProfilePage.tsx — Structured tabs: Personal | Job and Hierarchy | Statutory and Banking (masked, RBAC-gated) | Family and Nominees | Education | Prior Experience (BGV badges) | Assets | Documents | Custom Fields
- [ ] EmployeeInformationPage.tsx — Read-only tabs for employee self-service with field masking
- [ ] OnboardingProfilePage.tsx — Add statutory/bank fields, education, prior experience sections
- [ ] CandidateDetailPage.tsx — Interview Scorecard section; 1-Click Convert to Employee workflow modal
- [ ] CandidatesPage.tsx — Add Job Requisitions tab

---

## PHASE 3 — Email Template Editor, Editable PDF Engine and Versioned Document Vault

### Backend Tasks
- [ ] Migration candidates/0004: Create EmailTemplate (org-scoped)
  - organization (FK), name
  - category TextChoices: CANDIDATE_OFFER, APPOINTMENT, PROBATION_CONFIRMATION, PROMOTION, BRANCH_TRANSFER, SALARY_INCREMENT, WARNING_SHOW_CAUSE, PIP_CHARTER, RESIGNATION_ACCEPTANCE, RELIEVING_EXPERIENCE, NOC_BONAFIDE
  - subject, body_html, is_active
- [ ] Extend LetterTemplate in candidates/models.py: add category (same choices), body_html, variables_schema (JSONField listing allowed merge tags)
- [ ] Merge-Tag Renderer Service in candidates/services.py: whitelist-only variable substitution; sanitize with bleach; supported tags: employee_name, employee_id, designation, old_designation, new_designation, branch, old_branch, new_branch, department, reporting_manager, ctc, revised_ctc, joining_date, effective_date, last_working_day, exit_reason
- [ ] Migration employees/0018: Extend EmployeeDocument + create EmployeeDocumentVersion
  - EmployeeDocument new fields: document_source (EMPLOYEE_UPLOAD/SYSTEM_ISSUED_LETTER), lifecycle_category, linked_lifecycle_event_type, current_version_number (PositiveSmallIntegerField default 1), verification_qr_token (UUIDField unique), doc_status (DRAFT/ISSUED/SUPERSEDED)
  - EmployeeDocumentVersion: document (FK), version_number, editable_fields_snapshot (JSONField), rendered_html_snapshot (TextField), pdf_file (FileField), modified_by (User FK), change_summary, email_sent_at (DateTimeField nullable)
- [ ] Migration notifications/0006: Create CommunicationLog
  - organization (FK), employee (FK nullable), candidate (FK nullable)
  - email_template (FK nullable), subject, to_email, sent_at
  - status (SENT/FAILED/BOUNCED), document_version (FK to EmployeeDocumentVersion nullable)
- [ ] PDF Generation Service employees/pdf_service.py: HTML to PDF via weasyprint; embed letterhead from TenantBrandingAndConfig.logo_url; embed verification_qr_token as QR code in footer
- [ ] Email Dispatch Service employees/email_service.py: Send with PDF attachment; log to CommunicationLog; update email_sent_at
- [ ] API: GET/POST /api/v1/candidates/email-templates/
- [ ] API: POST /api/v1/employees/{id}/documents/{doc_id}/generate-pdf/
- [ ] API: POST /api/v1/employees/{id}/documents/{doc_id}/send-email/
- [ ] API: GET /api/v1/employees/{id}/documents/{doc_id}/versions/
- [ ] New RBAC permissions: letter_template.manage, employee.document.issue, employee.document.send_email

### Frontend Tasks
- [ ] LetterTemplatesPage.tsx — Full Email and Letter Template Studio: rich-text editor (TipTap), clickable merge-tag pills, live email preview panel, PDF preview drawer
- [ ] PromotionModal.tsx, TransferModal.tsx, ExitModal.tsx — Add Communication and Document Dispatch step: template picker, field editor, PDF preview, send email button
- [ ] CandidateDetailPage.tsx — Offer rollout communication step
- [ ] EmployeeProfilePage.tsx Documents Tab — Version badges (v1/v2), Preview PDF, Edit Fields and Regenerate, Version History Timeline, Send/Resend Email actions
- [ ] EmployeeInformationPage.tsx / OnboardingLettersPage.tsx — Self-service view of ISSUED letters

---

## PHASE 4 — We360.ai Workforce Intelligence and Productivity Suite

### Backend Tasks
- [ ] Migration attendance/0015: Create AppProductivityRule
  - organization (FK), department (FK nullable), app_name, domain_url
  - category (PRODUCTIVE/NEUTRAL/UNPRODUCTIVE), is_active
- [ ] Migration attendance/0016: Create WorkforceActivitySession
  - employee (FK), date, online_time, active_time, idle_time, offline_time
  - activity_score_pct, app_usage_breakdown (JSONField), created_at
- [ ] Migration attendance/0017: Create ActivitySnapshot
  - session (FK), captured_at, activity_pct, is_blurred (BooleanField), snapshot_metadata (JSONField)
- [ ] API: GET/POST /api/v1/attendance/productivity/rules/ (CRUD AppProductivityRule)
- [ ] API: GET /api/v1/attendance/productivity/sessions/ (manager/HR view)
- [ ] API: POST /api/v1/attendance/productivity/sessions/sync/ (desktop agent push)
- [ ] New RBAC permissions: productivity.view_all, productivity.manage_rules, productivity.view_self

### Frontend Tasks
- [ ] AttendanceManagementPage.tsx — Workforce Productivity tab: real-time status grid (Active/Idle/On Break/Offline), Active vs Idle timeline per employee, Productive App utilization donut chart
- [ ] DashboardPage.tsx — Productivity KPI widgets for managers

---

## PHASE 5 — Default and Dynamic Employee Work Health Alerts

### Backend Tasks
- [ ] Migration organization/0013: Create OrganizationWellnessPolicy (OneToOne to Organization)
  - hydration_interval_mins (default 60), eye_relaxation_interval_mins (default 20), posture_interval_mins (default 90)
  - is_hydration_enabled, is_eye_relaxation_enabled, is_posture_enabled
  - Auto-created via post_save signal on Organization creation
- [ ] Migration employees/0019: Create EmployeeWellnessPreference (OneToOne to Employee)
  - hydration_interval_mins (nullable, overrides org), eye_interval_mins (nullable), posture_interval_mins (nullable)
  - hydration_enabled, eye_enabled, posture_enabled
  - notification_style (TOAST/BROWSER/SOUND)
  - daily_hydration_goal, daily_break_goal
- [ ] Migration employees/0020: Create EmployeeWellnessDailyLog (FK to Employee, unique on employee+date)
  - date, glasses_logged, eye_breaks_completed, posture_breaks_completed
- [ ] API: GET/PATCH /api/v1/employees/{id}/wellness-preferences/ (SELF scope only)
- [ ] API: POST /api/v1/employees/{id}/wellness/log/ (quick log: glass of water, break completed)
- [ ] API: GET/PATCH /api/v1/organization/{id}/wellness-policy/ (Tenant Admin)

### Frontend Tasks
- [ ] AppLayout.tsx — Mount useWellnessReminders hook: triggers only when CHECKED_IN, pauses during breaks, cross-tab sync via localStorage; micro-break cards with 20s eye relaxation countdown; +1 Glass quick log; native Web Notification API
- [ ] ProfilePage.tsx — Work Health and Wellness tab for employee self-service configuration
- [ ] DashboardPage.tsx — Daily wellness streak widget
- [ ] AttendancePolicyPage.tsx — Default org wellness policy settings

---

## PHASE 6 — Statutory Payroll, Tax Declarations and Automated Exit/FnF Settlement

### Backend Tasks
- [ ] Migration payroll/0007: Create TaxDeclaration
  - employee (FK), fiscal_year, regime (OLD/NEW)
  - section_80c_investments (JSONField), section_80d_amount, hra_rent_receipts (JSONField)
  - declaration_status (DRAFT/SUBMITTED/VERIFIED)
- [ ] Migration payroll/0008: Create ExpenseClaim
  - employee (FK), organization (FK), claim_date, category, amount, description, receipt_file
  - status (PENDING/APPROVED/REJECTED/PAID)
- [ ] Migration payroll/0009: Create EmployeeLoan
  - employee (FK), organization (FK), principal_amount, emi_amount, disbursement_date
  - tenure_months, outstanding_amount, status (ACTIVE/CLOSED)
- [ ] Migration payroll/0010: Create ExitClearanceChecklist and FullAndFinalSettlement
  - ExitClearanceChecklist: employee (FK), it_asset_cleared, manager_kt_cleared, finance_cleared, hr_cleared (BooleanFields with timestamps)
  - FullAndFinalSettlement: employee (FK), unpaid_salary, leave_encashment, gratuity, notice_shortfall_recovery, unreturned_asset_deduction, pending_loan_deduction, net_payable, status (DRAFT/FINALIZED)
- [ ] Payslip computation bridge in payroll/services.py: pull LOP days from Attendance, unpaid leaves from LeaveRequest, compute gross/net with PF/ESIC/PT/TDS deductions
- [ ] Auto-issue Relieving and Experience Letters on FnF finalization via Phase 3 services

### Frontend Tasks
- [ ] PayrollPage.tsx — TaxDeclaration tab (employee self-service form)
- [ ] New FnFSettlementPage.tsx — FnF calculator + Clearance checklist
- [ ] ExitModal.tsx — Integrate clearance checklist trigger on exit initiation
- [ ] MyPayslipsPage.tsx — Show statutory deduction breakdown (PF, ESIC, PT, TDS)

---

## PHASE 7 — Enterprise Supportive and Self-Running HRMS Capabilities

### Backend Tasks
- [x] API: GET /api/v1/organization/{id}/org-chart/ — Hierarchical JSON of reporting_manager tree with headcount, designation, department
- [x] Letter Request API: POST /api/v1/employees/{id}/letter-requests/ (employee self-service); GET/PATCH for HR approval; auto-generate PDF on approval
- [x] Migration employees/0021: Create ApprovalDelegation
  - delegator (User FK), delegate (User FK), organization (FK)
  - valid_from, valid_until, delegate_types (JSONField: ['leave', 'wfh', 'attendance', 'timesheet'])
  - is_active
- [x] Migration notifications/0007: Add requires_acknowledgement (BooleanField), policy_pdf_url to Announcement; create AnnouncementAcknowledgement model
- [x] API: GET /api/v1/dashboard/celebrations/ — Birthdays, work anniversaries, new joinees from Employee

### Frontend Tasks
- [ ] New OrgChartPage.tsx — Zoomable tree (D3/vis.js) with headcount badges and profile quick-drawers
- [ ] Global Command Palette — Ctrl+K / Cmd+K spotlight search mounted in AppLayout.tsx; RBAC-filtered nav items + employee quick-lookup
- [ ] AnnouncementsPage.tsx — Acknowledgement modal + compliance tracking view
- [ ] DashboardPage.tsx — Birthdays/anniversaries/joinees celebrations widget; Peer Kudos widget
- [ ] ProfilePage.tsx — Approval delegation modal for managers

---

## PHASE 8 — Universal HRMS Data Migration and Smart Importer Engine

### Backend Tasks
- [ ] New Django app apps/migration_engine/ (add to INSTALLED_APPS, config/urls.py)
- [ ] Migration migration_engine/0001: Create MigrationJob and MigrationStagingRow
  - MigrationJob: organization (FK), source_platform (KEKA/ZOHO/WE360/GREYTHR/CUSTOM_CSV), status (PENDING/STAGING/DRY_RUN_COMPLETE/COMMITTED/ROLLED_BACK), batch_uuid (UUIDField unique), uploaded_file (FileField), zip_archive (FileField nullable), column_mapping (JSONField), created_by (User FK), timestamps
  - MigrationStagingRow: job (FK), row_index, raw_data (JSONField), mapped_data (JSONField), validation_errors (JSONField), status (PENDING/VALID/ERROR/IMPORTED)
- [ ] Column mapping presets per source platform seeded in seed.py
- [ ] 6-Pass Topological Ingestion Pipeline in migration_engine/services.py inside transaction.atomic():
  - Pass 1: Resolve/create Branch, Department, Designation, Team, Shift
  - Pass 2: Upsert User, Employee, EmployeeStatutoryAndBank, EmployeeDependent, EmployeePriorExperience
  - Pass 3: Link reporting_manager FKs; assign RBAC roles via UserRole/UserPermissionGrant
  - Pass 4: Import LeaveBalance + AssetAssignment
  - Pass 5: Import SalaryStructure, CTC, mid-year YTD earnings
  - Pass 6: Import historical Attendance + unpack document ZIP archives into EmployeeDocument/EmployeeDocumentVersion
- [ ] API: POST /api/v1/migration/jobs/{id}/dry-run/ (staging validation)
- [ ] API: PATCH /api/v1/migration/staging-rows/{id}/ (inline error fix)
- [ ] API: POST /api/v1/migration/jobs/{id}/commit/ (atomic commit)
- [ ] API: POST /api/v1/migration/jobs/{id}/rollback/ (delete all records with batch_uuid)
- [ ] Security: CSV formula injection sanitization (strip leading =, +, -, @); ZIP traversal protection; max file size enforcement
- [ ] New RBAC permission: migration.manage

### Frontend Tasks
- [ ] New MigrationWizardPage.tsx (5 steps):
  1. Platform selector (Keka / Zoho / We360.ai / greytHR / Custom CSV) + file/ZIP upload
  2. Interactive field mapper + custom field mapper with auto-suggestions
  3. Dry-Run health report with inline browser cell editor for fixing errors
  4. Atomic commit + summary dashboard (imported/skipped/failed counts)
  5. Staged bulk account activation (send invite emails)
- [ ] Link from OrganizationLaunchpadPage.tsx to MigrationWizardPage.tsx

---

## Seed Data Additions Per Phase

| Permissions to Add | Phase | File |
|--------------------|-------|------|
| branding.manage, custom_fields.manage | P1 | seed.py + bootstrap_demo_superadmin.py |
| employee.view_statutory, employee.manage_statutory, bgv.manage, candidate.requisition.manage, candidate.interview.manage | P2 | seed.py + bootstrap_demo_superadmin.py |
| letter_template.manage, employee.document.issue, employee.document.send_email | P3 | seed.py |
| productivity.view_all, productivity.manage_rules, productivity.view_self | P4 | seed.py |
| OrganizationWellnessPolicy auto-created per org | P5 | signal in organization/signals.py |
| payroll.tax_declaration, payroll.fnf.manage | P6 | seed.py |
| org_chart.view, delegation.manage, announcement.acknowledge | P7 | seed.py |
| migration.manage | P8 | seed.py |

---

## Migration Dependency Chain

P1: organization/0012
P2: employees/0013 -> 0017; candidates/0002 -> 0003
P3: candidates/0004; employees/0018; notifications/0006
P4: attendance/0015 -> 0017
P5: organization/0013; employees/0019 -> 0020
P6: payroll/0007 -> 0010
P7: employees/0021; notifications/0007
P8: new app migration_engine/0001

---

## Testing Checkpoints Per Phase

After completing each phase:
1. python manage.py makemigrations --check (must show no pending migrations)
2. python manage.py migrate (must complete cleanly)
3. Focused backend unit tests for new models and endpoints only (NOT the full 696-test suite)
4. cd frontend && npx tsc --noEmit (must show zero TypeScript errors)
5. Git commit with message: feat(phaseN): <summary>

---

## Definition of Done

- All 8 phases fully implemented
- Zero migration conflicts
- TypeScript strict-mode passing
- All existing 696 backend tests still pass
- All new features covered by focused tests
- Seed data updated in seed.py and bootstrap_demo_superadmin.py
- No hardcoded role names anywhere in authorization logic
- No Organization.objects.first() fallback anywhere
- All new endpoints RBAC-gated with appropriate Permission codenames
- All new models have organization FK for strict tenant isolation
- All state-mutating actions emit an AuditLog entry
- render.yaml still valid for Render deployment
- All .agent/ guardrails fully respected
