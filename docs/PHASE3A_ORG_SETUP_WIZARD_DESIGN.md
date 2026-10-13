# BEYONDSURE HRMS — PHASE 3A
## ORGANIZATION SETUP WIZARD: REQUIREMENTS AND ARCHITECTURE DESIGN

**Document Version:** 1.0.0  
**Phase:** 3A — Organization Setup Wizard (Requirements & Architecture Review)  
**Status:** DRAFT / PROPOSED (Implementation Not Authorized Yet)  
**Author / Developer:** Dev1 Only  
**Audit Baseline:** Branch `dev1` | HEAD `8203b224b86b0b3cf7261a6f4c63a4ddb0685193`  
**Reference Document:** [CROSS_MODULE_ACCEPTANCE_AUDIT.md](file:///d:/hrms/hrms/docs/CROSS_MODULE_ACCEPTANCE_AUDIT.md)

---

## 1. Executive Summary

The Phase 2E Cross-Module Acceptance Audit confirmed that all locked HRMS core modules (Organization Structure, Employee Lifecycle & ESS, Attendance & Shifts, Leaves, Recruitment & Documents, Payroll & Full & Final Settlement, Universal Data Import, Dashboards & Reporting) are complete, verified, and operating correctly across module boundaries.

The **Organization Setup Wizard** was intentionally deferred until that milestone was achieved. Currently, creating a new tenant organization requires either:
1. Direct backend database seeding / management commands (`bootstrap_demo_superadmin`, `seed`), or
2. A monolithic single-request API call (`POST /api/v1/organization/setup/` or `/self-setup/`) which creates only an Organization, a single Branch, a basic Working Calendar, and an Attendance Policy, leaving departments, designations, shifts, and holiday policies completely unconfigured.

This document presents an implementation-ready requirements and architecture design for a **Guided, Multi-Stage Organization Setup Wizard**. The design establishes a durable onboarding state machine that allows tenant owners and platform super-admins to configure their organization across 7 structured stages, supports safe save-and-resume behavior, guarantees transactional integrity within each stage, strictly enforces tenant isolation and dynamic RBAC boundaries, and uses the existing `OrganizationReadinessService` to validate completeness before permitting operational activation.

---

## 2. Current Architecture and Codebase Inspection

Inspection of the actual codebase establishes the following architecture and active implementations:

### 2.1 Organization & Multi-Tenancy Architecture
- **Organization Model:** [`backend/apps/organization/models.py`](file:///d:/hrms/hrms/backend/apps/organization/models.py) lines 4–16.
  - Fields: `name` (unique, max 255), `code` (unique, null=True, blank=True), `status` (`active` | `inactive`, default `active`), `created_at`, `updated_at`.
  - Signal: `auto_provision_tenant_branding` (lines 336–340) auto-creates a linked `TenantBrandingAndConfig` record on creation.
- **Tenant Owner Registration:** [`backend/apps/accounts/models.py`](file:///d:/hrms/hrms/backend/apps/accounts/models.py) lines 71–84.
  - Links a verified self-service user (`User`) to an `Organization`.
  - Property: `can_launch_organization` is `True` only when `verified_at is not None` and `organization_id is None`.
- **Existing Setup APIs:** [`backend/apps/organization/views.py`](file:///d:/hrms/hrms/backend/apps/organization/views.py).
  - `OrganizationSetupViewSet` (`/api/v1/organization/setup/`, lines 65–103): Restricted to global superusers (`IsSuperAdmin`).
  - `TenantOrganizationSetupView` (`/api/v1/organization/self-setup/`, lines 105–143): Accessible to verified tenant owners (`can_launch_organization`).

### 2.2 Organizational Hierarchy & Validation
- **Branch:** [`backend/apps/organization/models.py`](file:///d:/hrms/hrms/backend/apps/organization/models.py) lines 198–236.
  - Fields: `organization` (FK), `name`, `code`, `address_line1`, `address_line2`, `city`, `state`, `country`, `postal_code`, `timezone` (default `'UTC'`), `is_head_office` (bool), `latitude`, `longitude`, `radius` (float, minimum 100.0m via `MinValueValidator`), `is_active` (bool).
  - Constraints: `unique_together = [('organization', 'name'), ('organization', 'code')]`.
  - Signal: `auto_provision_branch_configs` (lines 329–334) auto-provisions a `WorkingCalendar` (default `0,1,2,3,4`) and an `AttendancePolicy` (`is_office_gps_enabled=True`).
- **Department:** [`backend/apps/organization/models.py`](file:///d:/hrms/hrms/backend/apps/organization/models.py) lines 142–155.
  - Fields: `branch` (FK to Branch), `name`, `code`, `description`, `is_active`.
  - Constraints: `unique_together = [('branch', 'name'), ('branch', 'code')]`.
- **Designation:** [`backend/apps/organization/models.py`](file:///d:/hrms/hrms/backend/apps/organization/models.py) lines 182–196.
  - Fields: `organization` (FK to Organization), `name`, `code`, `level` (uint, optional), `is_active`.
  - Constraints: `unique_together = [('organization', 'name'), ('organization', 'code')]`.
- **Team:** [`backend/apps/organization/models.py`](file:///d:/hrms/hrms/backend/apps/organization/models.py) lines 157–180.
  - Fields: `department` (FK to Department), `name`, `description`, `manager` (FK to Employee, optional), `is_active`.
  - Constraints: `unique_together = ('department', 'name')`.
  - Validation: Manager must belong to the same branch as the team's department.

### 2.3 Dynamic RBAC Architecture
- **Permission & Role Models:** [`backend/apps/authorization/models.py`](file:///d:/hrms/hrms/backend/apps/authorization/models.py).
  - 144 canonical permissions backfilled via migration `0006`.
  - `Role`: Organization-scoped, with auto-slug generation (`super-admin`, `hr-manager`, `branch-manager`, etc.).
  - `UserRole`: Scoped by `ScopeChoices` (`ORGANIZATION`, `BRANCH`, `TEAM`).
- **Authorization Service:** [`backend/apps/authorization/services.py`](file:///d:/hrms/hrms/backend/apps/authorization/services.py).
  - `_is_active_org_superadmin(user, organization)`: checks active `UserRole` where `role__slug='super-admin'` and `scope=ORGANIZATION`. Inherits all active permissions within tenant organization context.
  - `get_authorized_branches(user, permission_codename)` and `get_authorized_teams(user, permission_codename)`.

### 2.4 Attendance, Calendars & Shifts
- **Working Calendar:** [`backend/apps/organization/models.py`](file:///d:/hrms/hrms/backend/apps/organization/models.py) lines 18–71.
  - `work_days`: comma-separated integers (`'0,1,2,3,4'`).
  - `WorkingCalendarRule`: recurring rules `(working_calendar, weekday, occurrence, is_working)`.
- **Holiday:** [`backend/apps/attendance/models.py`](file:///d:/hrms/hrms/backend/apps/attendance/models.py) lines 139–156.
  - Scoped to `Branch`. Unique together `('branch', 'date')`.
- **Working Calendar Service:** [`backend/apps/organization/services.py`](file:///d:/hrms/hrms/backend/apps/organization/services.py) lines 13–130.
  - Locked precedence: **Explicit Holiday > Recurring Rule > Base Work Days**.
  - Strict failure: Raises `WorkingCalendarConfigurationError` if calendar is unconfigured (no silent fallback).
- **Shift:** [`backend/apps/attendance/models.py`](file:///d:/hrms/hrms/backend/apps/attendance/models.py) lines 157–205.
  - Invariant: Exactly one active shift per branch enforced in `Shift.clean()`.

### 2.5 Organization Readiness Service
- **Advisory Engine:** [`backend/apps/organization/services.py`](file:///d:/hrms/hrms/backend/apps/organization/services.py) lines 132–190.
  - Evaluates 7 operational checks: `branches`, `calendars`, `attendance_policies`, `structure` (departments & designations), `leave_types`, `roles`, `shifts`.
  - Returns `score` (0–100%) and array of check results (`ready`, `action_required`, `recommended`).

### 2.6 Existing Frontend Architecture
- **Routing:** [`frontend/src/routes/AppRouter.tsx`](file:///d:/hrms/hrms/frontend/src/routes/AppRouter.tsx).
  - `/admin/organization-launchpad`: Single-page legacy launchpad.
  - `/register`: `RegisterOrganizationPage` (self-service signup).
  - `/activate/:uid/:token`: `ActivateAccountPage`.
- **Contexts:**
  - `AuthContext`: session, `user.canCreateOrganization`, `hasPermission`, `hasEmployeeProfile`.
  - `BrandingContext`: tenant branding and theming.

---

## 3. Existing Functionality That Can Be Reused

The table below identifies all existing models, serializers, services, and endpoints directly reusable in Phase 3 without reinvention:

| Component / Layer | Existing Resource | Reusability in Wizard |
|---|---|---|
| **Identity & Activation** | `TenantOwnerRegistration` model, `ActivateView`, `LoginView` | 100% reusable. Verified owners are already qualified to launch tenants. |
| **Org Creation** | `OrganizationSetupSerializer`, `auto_provision_tenant_branding` | Reusable for Stage 1 initial organization persistence. |
| **Branch Creation** | `BranchSerializer`, `auto_provision_branch_configs` | Reusable for Stage 2. Signal auto-attaches calendar and attendance policy. |
| **Department / Desig** | `DepartmentSerializer`, `DesignationSerializer`, `TeamSerializer` | Reusable for Stage 3 validation and batch persistence. |
| **Calendar Rules** | `WorkingCalendarRuleSerializer`, `WorkingCalendarService` | Reusable for Stage 4 recurring overrides and holiday persistence. |
| **Shift Engine** | `ShiftSerializer`, `Shift.clean()` single-shift invariant | Reusable for Stage 5. Guarantees no conflicting shifts. |
| **Policy Engine** | `AttendancePolicySerializer`, `OfficeNetwork` | Reusable for Stage 5 GPS and IP network security. |
| **RBAC Super Admin** | `AuthorizationService._is_active_org_superadmin` | Reusable for Stage 6. System slug `super-admin` automatically resolves all permissions. |
| **Readiness Check** | `OrganizationReadinessService.assess()` | Reusable for Stage 7 review and final completion gate. |
| **Audit Logging** | `AuditService.log()` | Reusable across all stages for privacy-safe event logging. |

---

## 4. Functional Requirements

### 4.1 Onboarding Lifecycle Requirements
- **FR-01 (Single Organization Limit):** A self-service account with `TenantOwnerRegistration` may only initiate setup for exactly one organization. Once completed or in progress, subsequent attempts must be rejected with HTTP 400/409.
- **FR-02 (State Persistence):** Setup progress must be saved durably to the database upon completion of each stage. If a user drops off, loses connection, or logs out, they must be able to resume at their last completed stage.
- **FR-03 (Tenant Isolation):** All entities configured during stages 2 through 6 must strictly belong to the organization established in Stage 1. Cross-tenant references must be rejected.
- **FR-04 (Mandatory Head Office):** The initial branch created in Stage 2 must be designated as the Head Office (`is_head_office=True`).
- **FR-05 (Structural Minimums):** Before completing setup, the organization must possess at least:
  - 1 active Head Office branch.
  - 1 active department within the Head Office branch.
  - 1 active designation within the organization.
  - 1 configured working calendar with at least 1 working day.
  - 1 active shift adhering to the single-active-shift invariant.
  - 1 verified organization-scoped Super Admin role assignment.
- **FR-06 (Strict Calendar Priority):** Working calendar configuration must uphold the locked precedence: `Explicit Holiday > Recurring Rule > Base Calendar`. Missing calendar must fail explicitly.
- **FR-07 (Operational Guard):** Standard operational endpoints (attendance clock-in, leave application, payroll generation) must reject requests for organizations whose setup status is `in_progress`.
- **FR-08 (Readiness Completion Gate):** Stage 7 completion must query `OrganizationReadinessService.assess()`. Completion is permitted only when required readiness score equals 100%.

---

## 5. Explicit Assumptions and Unknowns

### 5.1 Facts From Code Inspection
1. `Organization` currently has no `onboarding_status` or `setup_state` field.
2. `TenantOwnerRegistration.can_launch_organization` becomes `False` immediately when `organization` foreign key is populated.
3. `Department` is foreign-keyed to `Branch`, whereas `Designation` is foreign-keyed directly to `Organization`.
4. `Team` is optional for employees (`team = ForeignKey(..., null=True, blank=True)`).
5. `Shift.clean()` enforces strictly one active shift per branch.
6. `WorkingCalendar` and `AttendancePolicy` are auto-created by signals when a `Branch` is created.

### 5.2 Proposals
1. Introduce a dedicated `OrganizationOnboarding` model in `apps.organization` rather than polluting the core `Organization` model with transient wizard state.
2. Provide a dedicated orchestration endpoint `/api/v1/organization/wizard/` that tracks stage progression while delegating entity validation to existing serializers.

### 5.3 Assumptions
1. Tenant onboarding is performed either by the verified tenant owner (`TenantOwnerRegistration`) or by an authenticated platform super-user (`is_superuser=True`).
2. The initial branch serves as the operational headquarters for the initial departments.

### 5.4 Unresolved Questions (Product Decisions Required)
1. **Default Templates:** Should the wizard offer industry presets (e.g., standard tech company departments: Engineering, HR, Sales; standard designations: Manager, Lead, Associate)?
2. **Leave Types in Wizard:** Should default statutory leave types (Casual Leave, Sick Leave, Paid Leave) be seeded during Stage 4, or left for post-onboarding administration?
3. **Office Network Enforcement:** Should GPS/IP geo-fencing be mandatory or optional during initial setup?

---

## 6. Proposed Onboarding Workflow (Stages 1 through 7)

```
+---------------------------------------------------------------------------------------------------+
|                            ORGANIZATION SETUP WIZARD PIPELINE                                     |
+---------------------------------------------------------------------------------------------------+
|  [Stage 1: Organization Details]                                                                  |
|      - Name, Code, Currency, Timezone, Branding defaults                                          |
|      -> Creates Organization & TenantBrandingAndConfig                                             |
|                                                                                                   |
|  [Stage 2: Initial Branch (Head Office)]                                                          |
|      - Branch Name, Code, Address, Geo-coordinates, Radius                                        |
|      -> Creates Branch (is_head_office=True); Signals create Calendar & AttendancePolicy          |
|                                                                                                   |
|  [Stage 3: Structure (Departments & Designations)]                                                |
|      - Departments (scoped to Branch), Designations (scoped to Org), Teams (optional)             |
|                                                                                                   |
|  [Stage 4: Working Calendar & Holidays]                                                           |
|      - Base Working Days (Mon-Fri), Recurring Rules (e.g. 2nd/4th Sat Off), Explicit Holidays     |
|                                                                                                   |
|  [Stage 5: Shift Schedule & Attendance Policy]                                                    |
|      - Default Shift (Start/End Time, Grace Period) [Exactly 1 Active Shift]                       |
|      - Attendance Policy (GPS, IP Subnet, WFH allowed)                                           |
|                                                                                                   |
|  [Stage 6: Initial Administrator & RBAC]                                                          |
|      - Confirm Tenant Super Admin role (Slug: super-admin, Scope: Organization)                   |
|      - UserRole assignment linking owner User to Organization                                     |
|                                                                                                   |
|  [Stage 7: Review & Activation]                                                                   |
|      - Readiness Audit (OrganizationReadinessService.assess() == 100%)                            |
|      -> Onboarding status -> COMPLETED; Organization status -> ACTIVE                             |
+---------------------------------------------------------------------------------------------------+
```

### Detailed Stage Breakdown & Field Classification

#### Stage 1 — Organization Details
- **Existing & Reusable:** `name` (required), `code` (optional, recommended), `status` (defaults to `active`).
- **Reusable from Branding:** `currency_code` (default `'INR'`), `date_format` (default `'DD/MM/YYYY'`).
- **Validation:** Uniqueness check on `name` and `code`.
- **Classification:** Mandatory.

#### Stage 2 — Initial Branch
- **Existing & Reusable:** `name` (required), `code` (optional), `is_head_office` (set `True`), `address_line1`, `address_line2`, `city`, `state`, `country`, `postal_code`, `latitude`, `longitude`, `radius` (min 100.0).
- **Behavior:** Auto-provisions empty `WorkingCalendar` and default `AttendancePolicy`.
- **Classification:** Mandatory.

#### Stage 3 — Organizational Structure
- **Existing & Reusable:**
  - `departments`: list of `{name, code}` associated with Head Office Branch.
  - `designations`: list of `{name, code, level}` associated with Organization.
- **Optional:** `teams` (can be created later).
- **Classification:** Mandatory (at least 1 department and 1 designation required for operational readiness).

#### Stage 4 — Working Calendar & Holidays
- **Existing & Reusable:**
  - `work_days`: e.g. `'0,1,2,3,4'`.
  - `recurring_rules`: list of `{weekday, occurrence, is_working}` (e.g. 2nd & 4th Saturday non-working).
  - `holidays`: list of `{name, date, holiday_type}`.
- **Invariant:** Active Explicit Holiday > Recurring Rule > Base Work Days.
- **Classification:** Mandatory.

#### Stage 5 — Shift & Attendance Configuration
- **Existing & Reusable:**
  - `shift`: `{name: 'General Shift', start_time: '09:00:00', end_time: '18:00:00', grace_period: '00:15:00', is_active: True}`.
  - `attendance_policy`: `{is_office_gps_enabled, is_office_ip_enabled, is_wfh_enabled}`.
  - `office_network`: `{name, network: 'CIDR'}` (optional).
- **Invariant:** Exactly one active shift.
- **Classification:** Mandatory.

#### Stage 6 — Initial Administrator and RBAC
- **Existing & Reusable:**
  - `Role`: system role with `slug='super-admin'`, `is_system=True`, `organization=org`.
  - `UserRole`: `user=request.user`, `role=owner_role`, `scope=ScopeChoices.ORGANIZATION`.
- **Classification:** Mandatory.

#### Stage 7 — Review and Complete
- **Summary Presentation:** Renders all configured entities for user confirmation.
- **Readiness Verification:** Invokes `OrganizationReadinessService.assess(org)`. Asserts score = 100%.
- **Transition:** Sets `OrganizationOnboarding.status = COMPLETED`, `completed_at = now()`.
- **Classification:** Mandatory.

---

## 7. Onboarding State and Recovery Design

### 7.1 Proposed Model: `OrganizationOnboarding`
To ensure robust save-and-resume support without cluttering core production models:

```python
class OnboardingStatus(models.TextChoices):
    NOT_STARTED = 'not_started', 'Not Started'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    ABANDONED = 'abandoned', 'Abandoned'

class OrganizationOnboarding(models.Model):
    organization = models.OneToOneField(
        'organization.Organization',
        on_delete=models.CASCADE,
        related_name='onboarding'
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='onboarded_organizations'
    )
    status = models.CharField(
        max_length=20,
        choices=OnboardingStatus.choices,
        default=OnboardingStatus.IN_PROGRESS
    )
    current_stage = models.PositiveSmallIntegerField(default=1)  # 1 to 7
    completed_stages = models.JSONField(default=list)  # e.g. [1, 2, 3]
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
```

### 7.2 Onboarding Authorization & Actors
1. **Who can start:**
   - A verified `TenantOwnerRegistration` user where `can_launch_organization == True`.
   - A platform superuser (`user.is_superuser == True`).
2. **Who can resume:**
   - The user who initiated the onboarding (`owner`).
   - A user holding an active `super-admin` role in the organization.
3. **Who can complete:**
   - The onboarding `owner` or organization Super Admin, strictly upon passing the 100% readiness audit.

### 7.3 Protection of Incomplete Organizations
- When `OrganizationOnboarding.status == IN_PROGRESS`:
  - Operational endpoints (Attendance Clock-In, Leave Requests, Payroll Generation) block execution with `HTTP 409 Conflict`: `"Organization setup is currently in progress."`
  - When the owner logs in, the frontend navigation automatically redirects them to `/admin/onboarding/wizard` at `current_stage`.

### 7.4 Idempotency & Partial Failure Recovery
- **Stage Atomicity:** Each stage is executed inside a `transaction.atomic()` block. If validation fails within a stage, changes in that stage roll back cleanly without destroying progress in preceding stages.
- **Stage Re-execution:** Stages 1 through 6 use `update_or_create` semantics based on unique keys (e.g. `(organization, name)`, `(branch, name)`), allowing users to safely re-run or edit a stage without creating duplicate records.
- **No Automatic Deletion:** The system never deletes previously committed stage data automatically during retries.

---

## 8. Tenant Security and RBAC Design

### 8.1 Boundary Enforcement Rules
1. **Cross-Tenant Prevention:** All stage endpoints derive `organization_id` strictly from the active `OrganizationOnboarding` session or the caller's validated role context. Client-supplied foreign organization IDs are rejected.
2. **Super Admin Isolation:** Dynamic Super Admin resolution (`AuthorizationService._is_active_org_superadmin`) is explicitly tenant-scoped. Super Admin authority in Tenant Alpha provides zero authorization in Tenant Beta.
3. **No Direct Privilege Escalation:** The wizard creates only the tenant-scoped `super-admin` role for the verified owner. It does not set `user.is_superuser = True`.

### 8.2 Permission Reconciliation
During the Phase 2 audit, a naming discrepancy was identified between the canonical permission matrix (`company.manage`) and legacy view permissions (`organization.manage`).
- **Recommendation for Wizard Endpoints:** Require `IsAuthenticated` and verify onboarding ownership (`user == onboarding.owner` or `AuthorizationService._is_active_org_superadmin(user, org)`).
- This avoids hardcoded permission collisions while preserving authoritative RBAC.

---

## 9. Proposed API Contract

All endpoints below are **PROPOSED** and subject to review before implementation:

### 9.1 `POST /api/v1/organization/wizard/start/`
- **Purpose:** Initialize onboarding session and execute Stage 1 (Organization Details).
- **Auth:** `IsAuthenticated`.
- **Preconditions:** `request.user.tenant_owner_registration.can_launch_organization == True` OR `request.user.is_superuser`.
- **Request Body:**
  ```json
  {
    "name": "Acme Global Technologies",
    "code": "ACME_HQ",
    "currency_code": "INR",
    "date_format": "DD/MM/YYYY"
  }
  ```
- **Response (HTTP 201):**
  ```json
  {
    "onboarding_id": 1,
    "organization_id": 10,
    "name": "Acme Global Technologies",
    "code": "ACME_HQ",
    "current_stage": 2,
    "completed_stages": [1],
    "status": "in_progress"
  }
  ```

### 9.2 `GET /api/v1/organization/wizard/status/`
- **Purpose:** Query current onboarding session and stage progress for the authenticated user's organization.
- **Auth:** `IsAuthenticated`.
- **Response (HTTP 200):**
  ```json
  {
    "onboarding_id": 1,
    "organization_id": 10,
    "organization_name": "Acme Global Technologies",
    "status": "in_progress",
    "current_stage": 2,
    "completed_stages": [1],
    "readiness_summary": {
      "score": 14,
      "checks_passed": 1,
      "total_checks": 7
    }
  }
  ```

### 9.3 `POST /api/v1/organization/wizard/stage-2/` (Initial Branch)
- **Purpose:** Configure Head Office branch.
- **Request Body:**
  ```json
  {
    "name": "Headquarters",
    "code": "HQ01",
    "address_line1": "100 Innovation Blvd",
    "city": "Bengaluru",
    "state": "Karnataka",
    "country": "India",
    "postal_code": "560100",
    "timezone": "Asia/Kolkata",
    "latitude": 12.971600,
    "longitude": 77.594600,
    "radius": 200.0
  }
  ```
- **Response (HTTP 200):** Branch details, updated `current_stage: 3`, `completed_stages: [1, 2]`.

### 9.4 `POST /api/v1/organization/wizard/stage-3/` (Structure)
- **Purpose:** Create initial departments and designations.
- **Request Body:**
  ```json
  {
    "departments": [
      {"name": "Engineering", "code": "ENG"},
      {"name": "Human Resources", "code": "HR"}
    ],
    "designations": [
      {"name": "Engineering Lead", "code": "ENG_LEAD", "level": 1},
      {"name": "Software Engineer", "code": "SWE", "level": 2}
    ]
  }
  ```
- **Response (HTTP 200):** Summary of created entities, `current_stage: 4`, `completed_stages: [1, 2, 3]`.

### 9.5 `POST /api/v1/organization/wizard/stage-4/` (Calendar & Holidays)
- **Purpose:** Configure base work days, recurring Saturday rules, and holidays.
- **Request Body:**
  ```json
  {
    "work_days": "0,1,2,3,4",
    "recurring_rules": [
      {"weekday": 5, "occurrence": 2, "is_working": false},
      {"weekday": 5, "occurrence": 4, "is_working": false}
    ],
    "holidays": [
      {"name": "Republic Day", "date": "2026-01-26", "holiday_type": "national"}
    ]
  }
  ```
- **Response (HTTP 200):** Calendar summary, `current_stage: 5`, `completed_stages: [1, 2, 3, 4]`.

### 9.6 `POST /api/v1/organization/wizard/stage-5/` (Shift & Attendance Policy)
- **Purpose:** Configure initial branch shift and attendance verification rules.
- **Request Body:**
  ```json
  {
    "shift": {
      "name": "General Shift",
      "code": "GEN",
      "start_time": "09:00:00",
      "end_time": "18:00:00",
      "grace_period_minutes": 15
    },
    "attendance_policy": {
      "is_office_gps_enabled": true,
      "is_office_ip_enabled": false,
      "is_wfh_enabled": true
    }
  }
  ```
- **Response (HTTP 200):** Shift & Policy summary, `current_stage: 6`, `completed_stages: [1, 2, 3, 4, 5]`.

### 9.7 `POST /api/v1/organization/wizard/stage-6/` (Admin & RBAC)
- **Purpose:** Confirm and ensure owner's organization Super Admin role and permission assignment.
- **Response (HTTP 200):** Role assignment confirmation, `current_stage: 7`, `completed_stages: [1, 2, 3, 4, 5, 6]`.

### 9.8 `POST /api/v1/organization/wizard/complete/`
- **Purpose:** Execute readiness assessment and finalize onboarding.
- **Precondition:** `OrganizationReadinessService.assess(org)['score'] == 100`.
- **Response (HTTP 200):**
  ```json
  {
    "status": "completed",
    "organization_id": 10,
    "completed_at": "2026-10-13T02:30:00Z",
    "redirect_url": "/dashboard"
  }
  ```

---

## 10. Frontend Route and Screen Specifications

```
+---------------------------------------------------------------------------------------------------+
| FRONTEND ONBOARDING WIZARD SCREEN LAYOUT                                                          |
+---------------------------------------------------------------------------------------------------+
|  [Header]: BeyondSure HRMS Logo | Setup Progress (Stage 3 of 7) | "Save & Exit" Button            |
+---------------------------------------------------------------------------------------------------+
|  [Progress Stepper]:                                                                              |
|  (1) Org Details -> (2) Location -> [3] Structure -> (4) Calendar -> (5) Shifts -> (6) Admin -> (7) Review  |
+---------------------------------------------------------------------------------------------------+
|  [Stage Content Card]:                                                                            |
|   +---------------------------------------------------------------------------------------------+ |
|   | Stage 3: Organizational Structure                                                           | |
|   | Configure initial departments and designations for your organization.                       | |
|   |                                                                                             | |
|   | [Departments Table]                                                                         | |
|   |  - Engineering (ENG)                                                                        | |
|   |  - Operations (OPS)                                                                         | |
|   |  [+ Add Department]                                                                         | |
|   |                                                                                             | |
|   | [Designations Table]                                                                        | |
|   |  - Director (Level 1)                                                                       | |
|   |  - Software Engineer (Level 2)                                                              | |
|   |  [+ Add Designation]                                                                        | |
|   +---------------------------------------------------------------------------------------------+ |
+---------------------------------------------------------------------------------------------------+
|  [Action Footer]: [< Back]                                                [Continue to Stage 4 >] |
+---------------------------------------------------------------------------------------------------+
```

### 10.1 Routes
- `/setup`: Primary wizard container route (loads current stage from `GET /wizard/status/`).
- `/setup/:stageNumber`: Direct stage route with route-guard redirecting to lowest incomplete stage if unfulfilled.
- `/setup/review`: Stage 7 review and readiness verification screen.

### 10.2 UI Components & Behavioral Guards
- **Stepper:** Renders horizontal 7-step progress bar with completed checkmarks, current active stage, and locked future stages.
- **Form Controls:** Uses existing BeyondSure design system CSS variables (`--color-primary`, `--surface-control-bg`, `--radius-md`).
- **Unsaved Changes Guard:** React Router `useBlocker` prompts confirmation modal if user attempts to navigate away before saving the current stage.
- **Save & Exit:** Persists current valid stage inputs and redirects to a dedicated "Setup Paused" screen.

---

## 11. Database Changes

### 11.1 New Migration: `apps.organization`
Add `OrganizationOnboarding` model to `apps/organization/models.py`.
- **Table Name:** `organization_onboarding`.
- **Columns:**
  - `id`: BigAutoField (Primary Key)
  - `organization_id`: OneToOneField -> `organization_organization` (unique, on_delete=CASCADE)
  - `owner_id`: ForeignKey -> `accounts_user` (on_delete=CASCADE)
  - `status`: CharField(max_length=20, default='in_progress')
  - `current_stage`: PositiveSmallIntegerField(default=1)
  - `completed_stages`: JSONField(default=list)
  - `metadata`: JSONField(default=dict)
  - `created_at`: DateTimeField(auto_now_add=True)
  - `updated_at`: DateTimeField(auto_now=True)
  - `completed_at`: DateTimeField(null=True, blank=True)
- **Constraint:** Unique constraint on `organization_id`.
- **Impact on Existing Data:** Zero impact on existing production tables. Existing organizations will have onboarding auto-backfilled as `status='completed'`.

---

## 12. Transaction and Idempotency Strategy

1. **Stage-Level Transactions:** Every stage mutation runs inside `with transaction.atomic():`. If a database constraint or validation fails, only that stage rolls back.
2. **Idempotency on Re-entry:**
   - Departments: `Department.objects.update_or_create(branch=branch, code=code, defaults={...})`.
   - Designations: `Designation.objects.update_or_create(organization=org, code=code, defaults={...})`.
   - Shifts: `Shift.objects.update_or_create(branch=branch, is_active=True, defaults={...})`.
3. **No Duplicate Creation:** Storing unique codes ensures users cannot accidentally duplicate records by double-clicking "Submit".

---

## 13. Audit Requirements

Using the existing [`AuditService.log()`](file:///d:/hrms/hrms/backend/apps/audit/services.py), the wizard will emit privacy-safe audit events:

| Event Action | Target Type | Target ID | Logged Metadata |
|---|---|---|---|
| `organization_onboarding_started` | `organization` | `org.id` | `{'owner_id': user.id, 'org_name': org.name}` |
| `onboarding_stage_completed` | `organization` | `org.id` | `{'stage': stage_num, 'entities_created': count}` |
| `onboarding_resumed` | `organization` | `org.id` | `{'resumed_stage': stage_num}` |
| `organization_onboarding_completed` | `organization` | `org.id` | `{'readiness_score': 100, 'completed_at': iso_ts}` |

*Privacy note: Coordinates, CIDR network ranges, and password secrets are explicitly excluded from audit metadata.*

---

## 14. Testing Strategy and Acceptance Criteria

### 14.1 Unit & Integration Test Matrix (To be implemented in Phase 3)
1. `test_wizard_start_by_verified_owner`: Verified tenant owner starts wizard; creates Org and Onboarding record in `in_progress`.
2. `test_wizard_start_rejected_for_unverified_user`: Unverified user receives HTTP 403/400.
3. `test_wizard_start_rejected_duplicate_owner`: User with existing org receives HTTP 409.
4. `test_stage_2_head_office_creation`: Creates branch with `is_head_office=True`; signals provision calendar and policy.
5. `test_stage_3_structure_validation`: Validates departments (branch-scoped) and designations (org-scoped).
6. `test_stage_4_working_calendar_precedence`: Verifies Holiday > Recurring Rule > Base Calendar priority.
7. `test_stage_5_single_active_shift_enforced`: Rejects conflicting 2nd active shift with HTTP 400.
8. `test_stage_6_super_admin_assignment`: Asserts owner user holds `super-admin` role with `ORGANIZATION` scope.
9. `test_stage_7_completion_blocks_on_incomplete_readiness`: Incomplete organization cannot be completed (HTTP 400).
10. `test_stage_7_completion_succeeds_at_100_percent`: Transitions status to `completed` and organization to `active`.
11. `test_save_and_resume_lifecycle`: Interrupted wizard resumes at exact stage without data loss.
12. `test_operational_endpoints_blocked_during_onboarding`: Attendance and leaves block actions for `in_progress` org.

---

## 15. Architectural Alternatives and Trade-offs

| Criterion | Option A: Frontend CRUD | Option B: Monolithic Backend | Option C: Hybrid State Machine (Recommended) |
|---|---|---|---|
| **Save & Resume** | ❌ None (lost on browser close) | ❌ None (all-or-nothing payload) | ✅ **Full DB persistence per stage** |
| **Partial Failure Recovery** | ❌ Leaves half-created records | ❌ Everything rolls back on any error | ✅ **Stage-isolated rollback; prior stages preserved** |
| **Domain Logic Reuse** | ✅ High (calls existing CRUD) | ❌ Low (duplicates validation) | ✅ **100% reuse of domain serializers & services** |
| **Operational Protection** | ❌ None (half-built org is active) | ❌ None | ✅ **`in_progress` guard protects system** |
| **Implementation Complexity** | Low | Medium | Balanced & Robust |

**Recommendation:** **Option C (Hybrid State Machine)**. It directly satisfies the prompt's requirement for safe recovery from partial setup without creating duplicate or inconsistent tenant data.

---

## 16. Security Risks and Mitigations

1. **Cross-Tenant Parameter Tampering:** Mitigated by binding all stage operations to `onboarding.organization_id`, ignoring client-submitted organization IDs.
2. **Privilege Escalation:** Mitigated by creating only a tenant-scoped `super-admin` role; no global superuser privileges are granted.
3. **Incomplete Organization Abuse:** Mitigated by blocking operational endpoints until `onboarding.status == COMPLETED`.

---

## 17. Migration Considerations

- Migration adds `organization_onboarding` table with zero locks on existing business tables.
- Backfill script automatically creates `OrganizationOnboarding(status='completed')` for existing active organizations.
- Backward compatibility: Existing `OrganizationViewSet` and admin screens remain fully functional for ongoing administration.

---

## 18. Implementation Plan (Divided Into Small Steps)

- **Step 3B:** Database Migration & Model (`OrganizationOnboarding`).
- **Step 3C:** Backend Onboarding Service (`OrganizationOnboardingService`) & Stage Serializers.
- **Step 3D:** REST API Endpoints (`/api/v1/organization/wizard/`) & Automated Integration Tests.
- **Step 3E:** Frontend Onboarding Service (`onboardingService.ts`) & Route Configuration.
- **Step 3F:** Frontend Multi-Stage UI Wizard Components (Stages 1 through 7).
- **Step 3G:** End-to-End Acceptance Testing & Documentation Update.

---

## 19. Rollback and Recovery Strategy

- If Phase 3 implementation fails or is rejected, the migration can be reversed (`python manage.py migrate organization <prev_migration>`) without impacting any Phase 1 or Phase 2 models.
- Core organizational models (`Organization`, `Branch`, `Department`, `Designation`) are untouched by schema changes.

---

## 20. Open Questions Requiring Product Decisions

1. **Industry Presets:** Should Stage 3 offer one-click templates (e.g., "Technology Startup", "Manufacturing", "Healthcare") to prepopulate departments and designations?
2. **Leave Cycle Initialization:** Should Stage 4 automatically provision standard leave types (e.g., 12 Casual, 12 Sick, 15 Earned) and an active leave cycle for the current calendar year?
3. **Multi-Location Setup:** Should the wizard allow configuring multiple branches during initial onboarding, or enforce exactly one Head Office branch with subsequent branches added via `/admin/branches`?
