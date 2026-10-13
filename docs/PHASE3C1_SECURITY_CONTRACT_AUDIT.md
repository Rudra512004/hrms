# BEYONDSURE HRMS — PHASE 3C.1
## ONBOARDING BACKEND SECURITY AND CONTRACT AUDIT REPORT

**Document Version:** 1.0.0  
**Phase:** 3C.1 — Onboarding Backend Security and Contract Audit  
**Status:** AUDIT COMPLETE & ALL DEFECTS REMEDIATED  
**Developer / Auditor:** Dev1 Only  
**Branch:** `dev1`  
**HEAD Commit:** `8203b224b86b0b3cf7261a6f4c63a4ddb0685193`  
**Timestamp:** 2026-10-13T08:35:00+05:30  
**Reference Documents:**
- [PHASE3A_ORG_SETUP_WIZARD_DESIGN.md](file:///d:/hrms/hrms/docs/PHASE3A_ORG_SETUP_WIZARD_DESIGN.md)
- [PHASE3C_IMPLEMENTATION_REPORT.md](file:///d:/hrms/hrms/docs/PHASE3C_IMPLEMENTATION_REPORT.md)
- [PHASE3C_ONBOARDING_API_CONTRACT.md](file:///d:/hrms/hrms/docs/PHASE3C_ONBOARDING_API_CONTRACT.md)

---

## 1. Executive Summary

This audit evaluates the Phase 3C Organization Setup Wizard backend implementation against strict tenant security, dynamic RBAC boundaries, administrative provisioning invariants, transactional integrity, and API contract accuracy.

During the audit, two security defects were confirmed and remediated:
1. **Global Superuser Tenant Bypass Defect (Remediated):** A global Django superuser (`is_superuser=True`) previously bypassed tenant validation when querying with `org_id`, violating the fundamental BeyondSure HRMS rule that platform superusers do not receive automatic tenant authority without an explicit tenant role or direct ownership.
2. **Cross-Tenant Administrative Scope Defect (Remediated):** Permissions `company.manage` and `organization.manage` were previously checked using global user permission evaluation (`AuthorizationService.has_permission(user, ...)`), which evaluates the user's primary organization. If an administrator had `company.manage` in Tenant A and supplied `org_id=Tenant_B`, access to Tenant B was granted. This has been remediated with `OrganizationOnboardingService._has_tenant_admin_permission()`, which strictly checks permissions and roles scoped to the target tenant organization.

All 17 focused wizard test cases, 29 onboarding model tests, 37 authorization dynamic tests, 49 accounts tests, and 38 audit tests pass with 100% success.

---

## 2. Audit Classifications Summary

| Audit Item | Task Area | Classification | Remediated Status |
|---|---|---|---|
| Global Django superuser does not bypass tenant isolation | Task A | **VERIFIED** | Fixed in `resolve_onboarding()` |
| Explicit organization IDs verified authoritatively | Task A | **VERIFIED** | Enforced via `_has_tenant_admin_permission()` |
| Direct ownership cannot grant access to another tenant | Task A | **VERIFIED** | Confirmed by unit tests |
| Tenant super-admin access validated through dynamic RBAC | Task A | **VERIFIED** | Evaluated via `_is_active_org_superadmin()` |
| `company.manage` and `organization.manage` handled consistently | Task A | **VERIFIED** | Evaluated within target tenant context |
| Inactive users strictly rejected | Task A | **VERIFIED** | Evaluated via `user.is_active` |
| Revoked roles strictly rejected | Task A | **VERIFIED** | Evaluated via `is_revoked=False` |
| Expired roles strictly rejected | Task A | **VERIFIED** | Evaluated via `expires_at >= now` |
| Sub-organization scopes (Branch/Team) rejected | Task A | **VERIFIED** | Requires `scope=ScopeChoices.ORGANIZATION` |
| Readiness and status endpoints enforce same boundaries | Task A | **VERIFIED** | All views subclass `OrganizationWizardBaseView` |
| Super Admin role is organization-scoped | Task B | **VERIFIED** | `role.organization = org` |
| Shared/system roles cannot be modified accidentally | Task B | **VERIFIED** | Scoped queries prevent global role mutation |
| Permission assignments use canonical active permissions | Task B | **VERIFIED** | `Permission.objects.filter(is_active=True)` |
| Owner receives only organization-scoped role | Task B | **VERIFIED** | `scope=ScopeChoices.ORGANIZATION` |
| No global Django superuser flag granted | Task B | **VERIFIED** | `user.is_superuser` remains `False` |
| Repeated submissions cannot create duplicate assignments | Task B | **VERIFIED** | Idempotent lookup and unrevoking |
| Existing users and roles not overwritten | Task B | **VERIFIED** | `get_or_create` preserves attributes |
| Unauthorized actors cannot provision/replace admin | Task B | **VERIFIED** | Target is always `onboarding.owner` |
| Stage mutations are atomic | Task C | **VERIFIED** | Wrapped in `with transaction.atomic():` |
| Failed operations roll back all changes | Task C | **VERIFIED** | Clean rollback without partial records |
| Repeated requests do not duplicate records | Task C | **VERIFIED** | Idempotent upsert across stages 1–6 |
| Audit events do not claim success on rollback | Task C | **VERIFIED** | Emitted inside transaction block |
| Stage 7 revalidates all required persisted configuration | Task C | **VERIFIED** | Direct database checks across 6 stages |
| API Contract alignment | Task D | **VERIFIED** | Contract aligned with hardened security rules |

---

## 3. Detailed Audit Findings

### Task A — Tenant Authorization

#### Finding A.1: Global Superuser Isolation (Remediated)
- **Previous State:** `OrganizationOnboardingService.resolve_onboarding()` contained `if user.is_superuser: return onb`, which granted any global superuser unconstrained access to any tenant's onboarding session upon providing `org_id`.
- **Architectural Violation:** In BeyondSure HRMS, tenant isolation is strict. As established in Phase 2 RBAC (`apps/authorization/tests_superadmin_dynamic.py:205`), platform superusers without an active tenant role receive empty permissions.
- **Remediation:** Removed the superuser bypass from `resolve_onboarding()`. Now, all users (including superusers) must be the registered `owner`, hold an active tenant `super-admin` role, or hold tenant-scoped administrative permissions in that specific organization.
- **Verification:** `test_tenant_isolation_and_cross_tenant_access_rejection` verifies that a platform admin without a tenant role receives `HTTP 403 Forbidden` when attempting to access a tenant's onboarding.

#### Finding A.2: Cross-Tenant Permission Checking (Remediated)
- **Previous State:** `AuthorizationService.has_permission(user, 'company.manage')` evaluated permissions for `AuthorizationService.get_primary_organization(user)`. An admin of Org 1 who passed `org_id=Org 2` was granted access to Org 2.
- **Remediation:** Introduced `OrganizationOnboardingService._has_tenant_admin_permission(user, organization)`:
  - Specifically queries `UserRole` where `role__organization=organization` and `scope=ORGANIZATION`.
  - Specifically checks `is_revoked=False`, `role__is_active=True`, and `expires_at >= now`.
  - Checks for both canonical `company.manage` (ID 117) and legacy `organization.manage` (ID 46).
- **Verification:** `test_cross_tenant_admin_cannot_access_foreign_tenant` asserts that an administrator of Org 1 receives `HTTP 403 Forbidden` when attempting to access Org 2.

#### Finding A.3: Inactive Users, Revoked Roles, Expired Roles, and Insufficient Scopes
- **Verification:**
  - Inactive users (`user.is_active == False`): `test_tenant_isolation_rejects_inactive_user` confirms access rejection.
  - Revoked roles (`is_revoked == True`): `test_tenant_isolation_rejects_revoked_role` confirms `HTTP 403 Forbidden`.
  - Expired roles (`expires_at < now`): `test_tenant_isolation_rejects_expired_role` confirms `HTTP 403 Forbidden`.
  - Sub-organization scopes (`scope=BRANCH`): `test_tenant_isolation_rejects_insufficient_permission_scope` confirms `HTTP 403 Forbidden`.

#### Finding A.4: Uniform Boundary Enforcement
- All view endpoints (`StatusView`, `StageView`, `CompleteView`, `DraftView`, `ReadinessView`) inherit from `OrganizationWizardBaseView` and call `self.get_onboarding(request)`. Readiness and status endpoints enforce the identical tenant boundaries as mutation endpoints.

---

### Task B — Stage 6 Administrator Provisioning

#### Finding B.1: Organization Scope & Invariant Protection
- **Role Isolation:** `Role.objects.get_or_create(organization=org, slug='super-admin', ...)` strictly scopes the role to `organization=org`. Shared template roles (`organization=None`) or roles belonging to other tenants cannot be modified or referenced.
- **No Global Escalation:** `test_stage_6_administrator_provisioning_invariants` verifies that the owner's `is_superuser` and `is_staff` flags remain `False` before and after Stage 6 execution.
- **Permission Attachment:** Only active permissions (`Permission.objects.filter(is_active=True)`) are linked via `RolePermission`.
- **Assignment Idempotency:** If `UserRole` already exists, `execute_stage_6` re-enables it if revoked and does NOT create duplicate assignments.
- **Owner Preservation:** Target administrator is derived from `onboarding.owner`. A delegate admin assisting with onboarding cannot overwrite the target administrator with their own account.

---

### Task C — Transactional Integrity and Idempotency

#### Finding C.1: Atomicity & Rollback
- Every stage handler executes within `with transaction.atomic():`.
- `test_transaction_rollback_on_failure` verifies that if validation fails (e.g. branch radius < 100m in Stage 2), no partial database records are persisted, and the onboarding stage does not advance.

#### Finding C.2: Audit Log Timing & Truthfulness
- `AuditService.log` is called inside the `transaction.atomic()` block at the end of each handler.
- If a rollback occurs due to an exception, the SQL insert into `apps_audit_auditlog` is automatically rolled back with the transaction. Audit events never falsely claim success for failed operations.

#### Finding C.3: Stage 7 Direct Database Re-Validation
- `OrganizationOnboardingService.revalidate_persisted_prerequisites(org)` verifies database reality rather than trusting metadata:
  - Verifies active `Branch` exists.
  - Verifies active `Department` and `Designation` exist.
  - Verifies configured `WorkingCalendar` exists on active branch.
  - Verifies active `Shift` exists on active branch.
  - Verifies active organization-scoped administrator exists.
- `test_persisted_prerequisites_catches_deleted_database_entities` verifies that if a prerequisite (e.g. active shift) was deleted from the database before Stage 7, setup completion is blocked with `HTTP 400 Bad Request`.

---

### Task D — API Contract Accuracy

#### Finding D.1: Contract Verification
- Compared `docs/PHASE3C_ONBOARDING_API_CONTRACT.md` against views, serializers, and URL patterns.
- Updated Section 1.2 in `docs/PHASE3C_ONBOARDING_API_CONTRACT.md` to document:
  1. Strict tenant isolation applied to all callers without global superuser bypass.
  2. Authoritative RBAC verification for explicit `org_id` parameters.
  3. Rejection of inactive users, revoked roles, expired roles, and sub-organization scopes.
- Confirmed all HTTP methods, URLs, status codes, request schemas, and response formats match the implementation.

---

## 4. Test Execution & Results

### 4.1 Focused Onboarding Wizard Test Suite
Command:
```bash
python manage.py test apps.organization.tests_onboarding_wizard
```
Output:
```
Creating test database for alias 'default'...
.................
----------------------------------------------------------------------
Ran 17 tests in 30.812s

OK
Destroying test database for alias 'default'...
Found 17 test(s).
System check identified no issues (0 silenced).
```
**All 17 tests PASSED (100%).**

### 4.2 Onboarding Model Tests
Command:
```bash
python manage.py test apps.organization.tests_onboarding_model
```
Output:
```
Ran 29 tests in 30.149s
OK
```
**All 29 tests PASSED (100%).**

### 4.3 Authorization Dynamic Tests & API Contracts
Command:
```bash
python manage.py test apps.authorization.tests_superadmin_dynamic apps.authorization.tests_api_contracts
```
Output:
```
Ran 37 tests in 65.865s
OK
```
**All 37 tests PASSED (100%).**

### 4.4 Accounts Test Suite
Command:
```bash
python manage.py test apps.accounts
```
Output:
```
Ran 49 tests in 84.219s
OK
```
**All 49 tests PASSED (100%).**

### 4.5 Audit Log Test Suite
Command:
```bash
python manage.py test apps.audit
```
Output:
```
Ran 38 tests in 46.110s
OK
```
**All 38 tests PASSED (100%).**

### 4.6 Migrations Check
Command:
```bash
python manage.py makemigrations --check
```
Output:
```
No changes detected
```

---

## 5. Files Changed During Phase 3C.1

1. [`backend/apps/organization/services.py`](file:///d:/hrms/hrms/backend/apps/organization/services.py):
   - Added `_has_tenant_admin_permission()` to evaluate tenant-scoped `company.manage` and `organization.manage` permissions with active, unrevoked, unexpired, and organization-scoped constraints.
   - Hardened `resolve_onboarding()` to eliminate global superuser bypass and enforce strict tenant boundaries.
2. [`backend/apps/organization/views.py`](file:///d:/hrms/hrms/backend/apps/organization/views.py):
   - Removed superuser bypass condition in `OrganizationWizardBaseView.get_onboarding()`.
3. [`backend/apps/organization/tests_onboarding_wizard.py`](file:///d:/hrms/hrms/backend/apps/organization/tests_onboarding_wizard.py):
   - Added 6 new security test cases: inactive users, revoked roles, expired roles, insufficient scope, cross-tenant admin isolation, and Stage 6 provisioning invariants.
   - Expanded suite from 11 to 17 tests.
4. [`docs/PHASE3C_ONBOARDING_API_CONTRACT.md`](file:///d:/hrms/hrms/docs/PHASE3C_ONBOARDING_API_CONTRACT.md):
   - Updated Section 1.2 to document strict tenant isolation and no superuser bypass.
5. [`docs/PHASE3C1_SECURITY_CONTRACT_AUDIT.md`](file:///d:/hrms/hrms/docs/PHASE3C1_SECURITY_CONTRACT_AUDIT.md):
   - Authored this complete audit deliverable.

---

## 6. Remaining Risks

1. **Frontend Integration (Phase 3D):**
   - The wizard UI components in React remain to be built and connected to these backend endpoints in Phase 3D.
2. **Leave-Type Configuration:**
   - As per locked product requirements, statutory leave types are post-onboarding administrative configurations. Wizard completion does not block on leave cycles.

---

## 7. Git Working-Tree & Safety Summary

```
Branch: dev1
Ahead of origin/dev1: 25 commits
HEAD: 8203b224b86b0b3cf7261a6f4c63a4ddb0685193
Migrations Check: No changes detected (clean)
Total Focused Tests Run: 17 (100% Pass)
Total Regression Tests Run: 153 (100% Pass)
```

Phase 3C.1 audit and security remediation is complete.
