# BEYONDSURE HRMS — PHASE 3B.2 REPORT
## ONBOARDING MIGRATION CORRECTIONS & VERIFICATION

**Document Version:** 1.0.0  
**Phase:** 3B.2 — Onboarding Migration Corrections  
**Status:** IMPLEMENTED AND VERIFIED  
**Developer / Owner:** Dev1 Only  
**Branch:** `dev1` | **HEAD:** `8203b224b86b0b3cf7261a6f4c63a4ddb0685193`  
**Reference Documents:**  
- [PHASE3A_ORG_SETUP_WIZARD_DESIGN.md](file:///d:/hrms/hrms/docs/PHASE3A_ORG_SETUP_WIZARD_DESIGN.md)
- [PHASE3B_ONBOARDING_MODEL_REPORT.md](file:///d:/hrms/hrms/docs/PHASE3B_ONBOARDING_MODEL_REPORT.md)
- [PHASE3B1_MIGRATION_LIFECYCLE_REVIEW.md](file:///d:/hrms/hrms/docs/PHASE3B1_MIGRATION_LIFECYCLE_REVIEW.md)

---

## 1. Executive Summary

Phase 3B.2 resolves the confirmed architectural and lifecycle defects identified during the Phase 3B.1 audit:
1. **Replaced False-Positive Backfill:** Replaced the permissive disjunctive backfill (`is_operational = has_branches or has_employees or ...`) with an evidence-based, stage-aware classification algorithm that inspects real historical schema artifacts stage-by-stage.
2. **Deterministic Owner Resolution:** Eliminated arbitrary unordered role lookups. The owner resolution algorithm now prioritizes verified `TenantOwnerRegistration`, followed by canonical tenant administrator roles (`super-admin`, `organization-owner`), with deterministic ID ordering. Non-administrative users (branch managers, viewers, employees) are explicitly excluded from owner assignment.
3. **Database CheckConstraints:** Added PostgreSQL database-level `CheckConstraint`s on `OrganizationOnboarding`:
   - `org_onboarding_valid_status`: Enforces `status IN ('not_started', 'in_progress', 'completed', 'abandoned')`.
   - `org_onboarding_valid_current_stage`: Enforces `current_stage >= 1 AND current_stage <= 7`.
   These constraints protect the database even against `QuerySet.update()` or raw SQL bypasses.
4. **Safety and Reversibility:** Tested forward execution, rollback, and reapplication on a disposable test database, strictly preserving development and test tenant data without destructive rollbacks.

All 85 organization tests and 49 accounts tests pass with zero regressions.

---

## 2. Files Changed and Created

| File Path | Status | Action Description |
|---|---|---|
| [`backend/apps/organization/models.py`](file:///d:/hrms/hrms/backend/apps/organization/models.py) | **Modified** | Added database `CheckConstraint`s (`org_onboarding_valid_status`, `org_onboarding_valid_current_stage`) in `OrganizationOnboarding.Meta.constraints`. |
| [`backend/apps/organization/migrations/0014_organizationonboarding.py`](file:///d:/hrms/hrms/backend/apps/organization/migrations/0014_organizationonboarding.py) | **Modified** | Updated schema definition with CheckConstraints, added dependency on `attendance.0003_holiday_shift`, implemented deterministic owner resolution, and stage-aware backfill logic. |
| [`backend/apps/organization/tests_onboarding_model.py`](file:///d:/hrms/hrms/backend/apps/organization/tests_onboarding_model.py) | **Modified** | Expanded from 17 to 28 tests covering CheckConstraint bypass rejection, stage-by-stage backfill cases, owner resolution precedence, and data preservation. |
| [`docs/PHASE3B2_MIGRATION_CORRECTIONS_REPORT.md`](file:///d:/hrms/hrms/docs/PHASE3B2_MIGRATION_CORRECTIONS_REPORT.md) | **Created** | Comprehensive implementation and verification report for Phase 3B.2. |

---

## 3. Corrected Backfill Algorithm & Stage Evidence Rules

### 3.1 Minimum Evidence Proving Wizard Stages
The completion predicate does not invent evidence. It evaluates historical database artifacts across the 7 wizard stages:

- **Stage 1 (Organization Details):** `Organization` record exists.
- **Stage 2 (Initial Branch):** At least one `Branch` linked to the organization exists.
- **Stage 3 (Organizational Structure):** Both at least one `Department` (branch-scoped) AND at least one `Designation` (org-scoped) exist.
- **Stage 4 (Working Calendar):** At least one `WorkingCalendar` linked to an active branch with non-empty `work_days` exists.
- **Stage 5 (Shift Schedule):** At least one active `Shift` linked to an active branch exists.
- **Stage 6 (Administrator & RBAC):** At least one active administrative `UserRole` (`role__slug in ['super-admin', 'organization-owner', 'company-admin', 'admin', 'owner', 'hr-manager']` or name containing `'owner'`) exists, OR a linked `TenantOwnerRegistration` exists.
- **Stage 7 (Completion):** All stages 1 through 6 must be satisfied for `status = 'completed'` and `current_stage = 7`.

### 3.2 Stage-Aware Classification Logic

```python
# Exact classification rule in 0014_organizationonboarding.py:
if not has_branches:
    if not has_any_role and not has_employees and not has_reg:
        return {'status': 'not_started', 'current_stage': 1, 'completed_stages': []}
    else:
        return {'status': 'in_progress', 'current_stage': 2, 'completed_stages': [1]}

completed_stages = [1, 2]
if not has_structure:
    return {'status': 'in_progress', 'current_stage': 3, 'completed_stages': completed_stages}

completed_stages.append(3)
if not has_calendar:
    return {'status': 'in_progress', 'current_stage': 4, 'completed_stages': completed_stages}

completed_stages.append(4)
if not has_shift:
    return {'status': 'in_progress', 'current_stage': 5, 'completed_stages': completed_stages}

completed_stages.append(5)
if not has_admin:
    return {'status': 'in_progress', 'current_stage': 6, 'completed_stages': completed_stages}

completed_stages.extend([6, 7])
return {'status': 'completed', 'current_stage': 7, 'completed_stages': [1, 2, 3, 4, 5, 6, 7]}
```

### 3.3 Verification of Database Reclassification
The table below displays the exact outcome on the 18 development database organizations after applying the corrected rule:

| Org ID | Name | Classification | Stage | Completed Stages | Reason |
|---|---|---|---|---|---|
| **6** | TestOrg | `in_progress` | 3 | `[1, 2]` | Has branches & employees, but missing departments/designations. |
| **8** | Default Org | `completed` | 7 | `[1, 2, 3, 4, 5, 6, 7]` | Fully operational (branches, structure, calendar, shift, HR admin, employees). |
| **9** | Test Org | `in_progress` | 3 | `[1, 2]` | Has branch and employee, but missing departments/designations. |
| **10** | Org 1 | `in_progress` | 4 | `[1, 2, 3]` | Has branch, department, and designation, but calendar unconfigured. |
| **11** | Org 2 | `in_progress` | 4 | `[1, 2, 3]` | Has branch, department, and designation, but calendar unconfigured. |
| **12** | TestOrgX | `in_progress` | 3 | `[1, 2]` | Has branch only; 0 structure. Correctly demoted from false completed. |
| **13** | TestOrgY | `in_progress` | 3 | `[1, 2]` | Has branch only; 0 structure. Correctly demoted from false completed. |
| **14** | Pune | `not_started` | 1 | `[]` | Empty shell. Correctly classified. |
| **15** | org | `not_started` | 1 | `[]` | Empty shell. Correctly classified. |
| **16** | org2 | `not_started` | 1 | `[]` | Empty shell. Correctly classified. |
| **17** | org_debug_3 | `not_started` | 1 | `[]` | Empty shell. Correctly classified. |
| **18** | Org A | `in_progress` | 2 | `[1]` | Has user role, but 0 branches. Correctly demoted from false completed. |
| **19** | Org B | `in_progress` | 2 | `[1]` | Has user role, but 0 branches. Correctly demoted from false completed. |
| **20** | T Org | `in_progress` | 2 | `[1]` | Has employees, but 0 branches. Correctly demoted from false completed. |
| **21** | BeyondSure Pvt Ltd | `in_progress` | 3 | `[1, 2]` | Has branch and Super Admin role, but 0 departments/designations. |
| **22** | Org Test | `in_progress` | 2 | `[1]` | Has employee and role, but 0 branches. |
| **24** | Org Test2 | `in_progress` | 2 | `[1]` | Has employee, but 0 branches. |
| **25** | T | `in_progress` | 2 | `[1]` | Has user role, but 0 branches. |

---

## 4. Deterministic Owner Resolution

### 4.1 Resolution Hierarchy
1. **Verified Tenant Owner:** `TenantOwnerRegistration` where `verified_at is not None`.
2. **Linked Tenant Owner:** `TenantOwnerRegistration` linked to the organization.
3. **Canonical Tenant Super Admin:** Active `UserRole` where `scope='organization'` and `role__slug='super-admin'`.
4. **Secondary Administrative Roles:** Active `UserRole` where `role__slug in ['organization-owner', 'company-admin', 'admin', 'owner', 'tenant-admin']` or `role__name` contains `'owner'` or `'super admin'`.
5. **Organization HR Manager:** Active `UserRole` where `role__slug='hr-manager'` with organization scope.
6. **Tie-Breaking:** Always ordered deterministically by `id` (`.order_by('id').first()`).
7. **Strict Non-Admin Exclusion:** If an organization only has non-administrative roles (e.g. `branch-manager`, `employee-viewer`, `employee`), the owner is left as `None`. Non-admin accounts are never falsely promoted to tenant owners.

---

## 5. Database Integrity & CheckConstraints

### 5.1 Enforced Database Constraints
Added to `OrganizationOnboarding.Meta.constraints` and generated in migration `0014`:

```python
constraints = [
    models.CheckConstraint(
        condition=models.Q(status__in=OnboardingStatus.values),
        name='org_onboarding_valid_status',
    ),
    models.CheckConstraint(
        condition=models.Q(current_stage__gte=1, current_stage__lte=7),
        name='org_onboarding_valid_current_stage',
    ),
]
```

### 5.2 Enforcement Boundary Matrix

| Invariant | Enforced at DB Engine? | Enforced on `save()`? | Enforced on `QuerySet.update()`? | Write-Layer Responsibility |
|---|---|---|---|---|
| **OneToOne Uniqueness** | **YES** (`UNIQUE` index) | Yes | **YES** | Database engine authoritative. |
| **Status Choices** | **YES** (`CheckConstraint`) | Yes | **YES** | Database engine rejects invalid status values. |
| **Stage Boundaries (1..7)** | **YES** (`CheckConstraint`) | Yes | **YES** | Database engine rejects stage < 1 or > 7. |
| **Completed Stages List** | NO (JSON column) | Yes | NO | Serializer & Service layer must validate before saving. |
| **Completion Timestamp** | NO (Nullable DateTime) | Yes | NO | `mark_completed()` and Service layer must assign. |
| **Owner-to-Org Consistency** | NO (Application logic) | Yes | NO | Serializer & Service layer must enforce. |
| **Metadata Protection** | NO (JSON column) | Yes | NO | `validate_onboarding_metadata` & Serializer. |

---

## 6. Migration Reversibility and Safety Verification

1. **Safety Rule Followed:** Zero destructive rollbacks were run against the valuable development database.
2. **Disposable Test Database Verification:** Reversibility was verified using a temporary, isolated SQLite test database running the exact migration graph:
   - **Forward Migration:** Applied migrations `0001` through `0014` cleanly. **VERIFIED.**
   - **Rollback to 0013:** Executed `migrate organization 0013_alter_branch_unique_together_and_more`. Successfully unapplied `0014_organizationonboarding`. Table dropped without affecting `organization` or `branch` tables. **VERIFIED.**
   - **Re-application of 0014:** Executed `migrate organization 0014_organizationonboarding`. Successfully re-applied `0014` and recreated table with CheckConstraints. **VERIFIED.**
3. **Limitation Documented:** Reversing migration 0014 drops table `organization_onboarding`. Any onboarding draft progress stored within that table will be permanently deleted if the migration is reversed. Core organization, branch, and user tables remain unaffected.

---

## 7. Test Execution & Verified Results

### 7.1 Focused Onboarding Model & Backfill Suite (28 Tests)
Command: `python manage.py test apps.organization.tests_onboarding_model`  
Output: `Ran 28 tests in 29.273s. OK.`

| Test Case | Finding | Status |
|---|---|---|
| `test_valid_onboarding_creation` | Default creation at stage 1, not_started | **VERIFIED** |
| `test_duplicate_onboarding_rejected` | OneToOne constraint rejects second record | **VERIFIED** |
| `test_invalid_status_value_rejected` | Model validation rejects invalid status | **VERIFIED** |
| `test_invalid_stage_boundaries_rejected` | Model validation rejects stage 0, 8, -1, 10 | **VERIFIED** |
| `test_invalid_completed_stages_rejected` | Model validation rejects invalid stage lists | **VERIFIED** |
| `test_completed_status_requires_all_stages` | Model validation requires stages 1..7 | **VERIFIED** |
| `test_completed_status_auto_sets_completed_at` | Automatically assigns timestamp | **VERIFIED** |
| `test_not_started_cannot_have_completed_stages` | Rejects stages for not_started status | **VERIFIED** |
| `test_tenant_owner_consistency_check` | Rejects mismatched owner if registration exists | **VERIFIED** |
| `test_mark_stage_complete_lifecycle` | Advances stages and status | **VERIFIED** |
| `test_mark_completed_helper` | Transitions all 7 stages and completed_at | **VERIFIED** |
| `test_metadata_validation_forbidden_credentials` | Rejects passwords, tokens, API keys | **VERIFIED** |
| `test_metadata_validation_forbidden_privileges_and_identities` | Rejects identity & permission override keys | **VERIFIED** |
| `test_metadata_validation_nested_structures` | Traverses nested dicts and lists of dicts | **VERIFIED** |
| `test_metadata_validation_jwt_and_hashes_rejected` | Rejects hashed passwords and JWT tokens | **VERIFIED** |
| `test_metadata_safe_draft_data_allowed` | Permits legitimate workflow draft JSON | **VERIFIED** |
| `test_database_check_constraint_rejects_invalid_status_on_update` | DB CheckConstraint rejects invalid status on `update()` | **VERIFIED** |
| `test_database_check_constraint_rejects_invalid_stage_on_update` | DB CheckConstraint rejects stage < 1 or > 7 on `update()` | **VERIFIED** |
| `test_backfill_organization_with_no_configuration` | Classifies as `not_started`, stage 1, `[]` | **VERIFIED** |
| `test_backfill_organization_with_only_branch` | Classifies as `in_progress`, stage 3, `[1, 2]` | **VERIFIED** |
| `test_backfill_organization_with_only_user_role` | Classifies as `in_progress`, stage 2, `[1]` | **VERIFIED** |
| `test_backfill_organization_with_branch_and_partial_structure` | Classifies as `in_progress`, stage 3, `[1, 2]` | **VERIFIED** |
| `test_backfill_organization_with_sufficient_evidence_for_completion` | Classifies as `completed`, stage 7, `[1..7]` | **VERIFIED** |
| `test_existing_organization_data_remains_unchanged_by_backfill` | Preserves all organization attributes & timestamps | **VERIFIED** |
| `test_owner_resolution_prefers_verified_tenant_owner` | Prioritizes verified registration | **VERIFIED** |
| `test_owner_resolution_prefers_superadmin_over_manager_or_viewer` | Prioritizes super-admin role | **VERIFIED** |
| `test_owner_resolution_deterministic_tie_breaking` | Uses lowest ID for deterministic tie-breaking | **VERIFIED** |
| `test_owner_resolution_leaves_owner_none_for_non_admin_roles` | Leaves owner as None when only non-admins exist | **VERIFIED** |

### 7.2 Full Organization App Regression Suite (85 Tests)
Command: `python manage.py test apps.organization`  
Output: `Ran 85 tests in 101.582s. OK.` — **VERIFIED.**

### 7.3 Accounts App Regression Suite (49 Tests)
Command: `python manage.py test apps.accounts`  
Output: `Ran 49 tests in 83.802s. OK.` — **VERIFIED.**

### 7.4 Migration Graph Consistency
Command: `python manage.py makemigrations --check ; python manage.py showmigrations organization`  
Output: `No changes detected. [X] 0014_organizationonboarding applied.` — **VERIFIED.**

---

## 8. Unresolved Questions & Risks

1. **Route Guard Enforcement (Phase 3E):** Because organizations like `BeyondSure Pvt Ltd`, `TestOrgX`, `Org 1`, and `Org 2` are now accurately classified as `in_progress` rather than `completed`, Phase 3E route guards will redirect their administrators to complete their missing setup stages upon login. This is the desired behavior for strict data integrity, but represents a user flow change for any legacy stubs.
2. **Leave Cycle Provisioning:** Stage 7 review requires confirmation whether default leave types should be initialized on wizard completion.

---

## 9. Verification Classification Matrix

| Check / Requirement | Status | Evidence |
|---|---|---|
| Repository Safety & Working Tree Preservation | **VERIFIED** | Branch `dev1`, HEAD `8203b22`, 0 commits, 0 destructive git actions |
| Stage Evidence Completion Predicate | **VERIFIED** | Tested across 6 discrete structural scenarios |
| Database CheckConstraints | **VERIFIED** | Enforced at PostgreSQL engine level; unit tested on `update()` |
| Deterministic Owner Resolution | **VERIFIED** | Verified registration prioritized; non-admins excluded; tie-breaking deterministic |
| Migration Graph & Lineage | **VERIFIED** | `makemigrations --check` passed with 0 changes |
| Disposable Database Rollback & Reapply | **VERIFIED** | Verified forward, unapply to 0013, and reapply cleanly on disposable DB |
| Zero Regressions in Core Apps | **VERIFIED** | 85 organization tests & 49 accounts tests passed |
| Deliverable Report Created | **VERIFIED** | `docs/PHASE3B2_MIGRATION_CORRECTIONS_REPORT.md` |

---

**STATUS: Phase 3B.2 Onboarding Migration Corrections complete. All confirmed defects resolved. Standing by for review before Phase 3C.**
