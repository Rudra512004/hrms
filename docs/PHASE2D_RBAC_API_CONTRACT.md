# BEYONDSURE HRMS — PHASE 2D: RBAC API CONTRACTS & ENFORCEMENT SPECIFICATION

**Document Version:** 1.0 (Frozen & Implementation-Verified)  
**Date:** October 12, 2026  
**Status:** AUTHORITATIVE BACKEND RBAC CONTRACT  
**Owner:** Dev1 (HRMS Architecture & Dynamic RBAC Engineering)  
**Target Consumers:** Dev2 (Frontend Engineering), Quality Assurance, Security Engineering  

---

## 1. Executive Summary & Architecture Invariants

This specification provides the exhaustive, frozen contract for all backend Roles & Permissions APIs implemented in Phase 2D. Dev2 can directly consume these endpoints for building the Phase 2E UI without guesswork regarding request shapes, headers, query parameters, response structures, or status codes.

### 1.1 Mandatory Security & Multi-Tenant Invariants
1. **Strict Organization Scoping:** Every role, permission query, and user assignment is isolated to the authenticated caller's tenant organization (`request.user.organization_id`). Cross-tenant access is rejected with `404 Not Found` (detail inspection) or `400 Bad Request` (mutations).
2. **Dynamic Super Admin Permission Resolution:** Super Admin permissions are not statically linked rows in `authorization_rolepermission`. A user with the active `super-admin` role dynamically resolves all active permissions ($N_{\text{active}} \ge 144$) in runtime within their tenant context.
3. **Super Admin Immutability:** Super Admin role permissions cannot be narrowed, modified, or deleted (`PUT /roles/{id}/permissions/` returns `400 Bad Request`).
4. **Anti-Privilege Escalation:**
   - Only active Super Admins can assign or revoke the `super-admin` role.
   - Non-Super Admins cannot assign preserved enterprise security permissions (`is_preserved_enterprise=True`).
   - Callers cannot create roles with reserved system names/slugs or manipulate system-role identities.
5. **Atomic Full Replacement for Permissions:** Mutating role permissions operates strictly under atomic full replacement semantics (`@transaction.atomic`). Partial or corrupted states are strictly prevented.
6. **Soft Revocation & Data Integrity:** Revoking user roles sets `is_revoked=True` and `revoked_at=now()`; historical assignment rows and audit trails are preserved.

---

## 2. API Contract Summary Matrix

| Method | Endpoint Path | Required Permission | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/authorization/roles/` | `role.view` or `role.manage` | List all tenant roles with metrics and badges |
| `GET` | `/api/v1/authorization/roles/{id}/` | `role.view` or `role.manage` | Retrieve single role detail with permission IDs |
| `POST` | `/api/v1/authorization/roles/` | `role.manage` or `role.assign` | Create custom tenant role with auto-slugification |
| `PUT,PATCH` | `/api/v1/authorization/roles/{id}/` | `role.manage` or `role.assign` | Update role metadata (system names protected) |
| `DELETE` | `/api/v1/authorization/roles/{id}/` | `role.manage` or `role.assign` | Delete eligible custom role (0 assigned users) |
| `PUT` | `/api/v1/authorization/roles/{id}/permissions/` | `role.manage` or `role.assign` | Atomic full replacement of role permissions |
| `GET` | `/api/v1/authorization/permissions/` | `permission.view`, `role.view`, or `role.manage` | List permissions grouped across 3 columns (127 UI controls) |
| `POST` | `/api/v1/authorization/user-roles/` | `role.assign` or `role.manage` | Assign role to tenant user with scope |
| `POST` | `/api/v1/authorization/user-roles/{id}/revoke/` | `role.revoke`, `role.assign`, or `role.manage` | Explicit soft revocation of user-role assignment |
| `DELETE` | `/api/v1/authorization/user-roles/{id}/` | `role.revoke`, `role.assign`, or `role.manage` | RESTful soft revocation of user-role assignment |
| `GET` | `/api/v1/authorization/me/` | Authenticated | Current user effective profile, roles, and permissions |

---

## 3. Detailed Endpoint Contracts

### 3.1 Role Listing & Detail

#### `GET /api/v1/authorization/roles/`
* **Authentication:** Bearer JWT token (`IsAuthenticated`)
* **Required Permission:** `role.view` or `role.manage`
* **Tenant Scope:** Scoped to `_get_user_organization(request.user)`
* **Response Status:** `200 OK`
* **Response Schema:**
```json
[
  {
    "id": 1,
    "organization": 1,
    "name": "Organization Owner (Super Admin)",
    "slug": "super-admin",
    "description": "Full access to all system modules",
    "badge": "Full access",
    "users_count": 2,
    "permissions_count": 127,
    "effective_permissions_count": 144,
    "can_delete": false,
    "is_system": true,
    "is_active": true,
    "permission_ids": [1, 2, 3, 4, 5, "... (127 IDs)"],
    "created_at": "2026-10-12T10:00:00Z",
    "updated_at": "2026-10-12T10:00:00Z"
  },
  {
    "id": 2,
    "organization": 1,
    "name": "HR Manager",
    "slug": "hr-manager",
    "description": "Manages human resources, onboarding, and leaves",
    "badge": null,
    "users_count": 3,
    "permissions_count": 112,
    "effective_permissions_count": 112,
    "can_delete": false,
    "is_system": true,
    "is_active": true,
    "permission_ids": [1, 2, 5, 8, "..."],
    "created_at": "2026-10-12T10:00:00Z",
    "updated_at": "2026-10-12T10:00:00Z"
  },
  {
    "id": 8,
    "organization": 1,
    "name": "Shift Supervisor",
    "slug": "shift-supervisor",
    "description": "Manages floor shifts and attendance verification",
    "badge": null,
    "users_count": 0,
    "permissions_count": 14,
    "effective_permissions_count": 14,
    "can_delete": true,
    "is_system": false,
    "is_active": true,
    "permission_ids": [39, 40, 41, 42],
    "created_at": "2026-10-12T11:00:00Z",
    "updated_at": "2026-10-12T11:00:00Z"
  }
]
```

#### Field Definitions & Counting Rules:
* `badge`: `'Full access'` for Super Admin (`slug == 'super-admin'`); `null` for all other roles.
* `users_count`: Count of active, non-revoked user assignments in caller's organization (`role.user_roles.filter(is_revoked=False).distinct().count()`).
* `permissions_count`: Count of assigned active UI-visible controls (`column_index__in=[1, 2, 3]`). For Super Admin, this evaluates to **127**.
* `effective_permissions_count`: Total active runtime permissions. For Super Admin, evaluates to all active permissions in the registry ($\ge 144$). For custom roles, counts all assigned active permissions.
* `can_delete`: `false` if `is_system == true` OR `users_count > 0`. `true` only for custom roles with 0 active users.
* `permission_ids`: List of active permission integer IDs.

#### `GET /api/v1/authorization/roles/{id}/`
* **Response Status:** `200 OK` (if belongs to caller's org)
* **Error Response:** `404 Not Found` (if belongs to another org or non-existent)

---

### 3.2 Permission Listing (Grouped Matrix)

#### `GET /api/v1/authorization/permissions/`
* **Authentication:** Bearer JWT token (`IsAuthenticated`)
* **Required Permission:** `permission.view`, `role.view`, or `role.manage`
* **Query Parameters:**
  * `format` (optional): `'flat'` to return a flat array of permission objects.
  * `include_preserved` (optional): `'true'` to include preserved enterprise security controls. Default is `'false'`.
* **Response Status:** `200 OK`
* **Default Response Schema (Grouped Matrix for 3-Column UI Rendering):**
```json
{
  "total_visible_count": 127,
  "columns": {
    "1": [
      {
        "category": "Dashboard",
        "actions": [
          {
            "id": 1,
            "codename": "dashboard.view",
            "label": "View dashboard",
            "name": "View Dashboard",
            "description": "Allows viewing operational metrics and overview cards",
            "column": 1,
            "category": "Dashboard"
          },
          {
            "id": 2,
            "codename": "dashboard.view_org_stats",
            "label": "View organisation-wide statistics",
            "name": "View Organisation-wide Statistics",
            "description": "Allows viewing company-wide aggregation charts",
            "column": 1,
            "category": "Dashboard"
          }
        ]
      },
      {
        "category": "Companies",
        "actions": [ "..." ]
      }
    ],
    "2": [
      {
        "category": "Attendance",
        "actions": [
          {
            "id": 39,
            "codename": "attendance.clock_in_out",
            "label": "Check in and check out",
            "name": "Check in and check out",
            "description": "Clock in and out of shift",
            "column": 2,
            "category": "Attendance"
          }
        ]
      }
    ],
    "3": [
      {
        "category": "Payslips",
        "actions": [
          {
            "id": 90,
            "codename": "payslip.view",
            "label": "View own payslips",
            "name": "View Own Payslips",
            "description": "Access self payslips",
            "column": 3,
            "category": "Payslips"
          }
        ]
      }
    ]
  }
}
```

#### Category & Control Distribution:
* **Column 1:** 10 categories, 38 interactive controls.
* **Column 2:** 8 categories, 51 interactive controls.
* **Column 3:** 11 categories, 38 interactive controls.
* **Total UI Controls:** **127**.
* **Inactive Handling:** Inactive permissions (`is_active=False`) are never exposed in the UI matrix.

---

### 3.3 Role Creation

#### `POST /api/v1/authorization/roles/`
* **Authentication:** Bearer JWT token
* **Required Permission:** `role.manage` or `role.assign`
* **Request Schema:**
```json
{
  "name": "Shift Supervisor",
  "description": "Floor shift supervisor and attendance verification"
}
```
* **Validation & Security Invariants:**
  * `name` cannot be empty.
  * Role name cannot duplicate an existing role within the same tenant org.
  * System role names (`Super Admin`, `Organization Owner (Super Admin)`) or reserved slugs (`super-admin`) are strictly rejected with `400 Bad Request`.
  * `is_system` is automatically forced to `False`.
  * `slug` is auto-generated using `slugify(name)` with tenant-scoped collision avoidance (`slug`, `slug-1`, `slug-2`).
* **Success Response:** `201 Created` with full `RoleSerializer` payload.
* **Audit Event:** `role_created` logged with actor, target role ID, role name, and slug.

---

### 3.4 Role Editing

#### `PUT, PATCH /api/v1/authorization/roles/{id}/`
* **Authentication:** Bearer JWT token
* **Required Permission:** `role.manage` or `role.assign`
* **Request Schema (PATCH):**
```json
{
  "description": "Updated shift supervisor responsibilities"
}
```
* **Validation & Security Invariants:**
  * Cross-tenant access returns `404 Not Found`.
  * For system roles (`is_system=True`), modifying `name` or `slug` returns `400 Bad Request` (*"System role name and identity cannot be modified."*).
  * Modifying `slug` on any role is blocked (read-only field).
  * Renaming a custom role to `Super Admin` is rejected with `400 Bad Request`.
* **Success Response:** `200 OK` with updated `RoleSerializer` object.
* **Audit Event:** `role_updated` logged with actor, role ID, role name, and slug.

---

### 3.5 Role Deletion

#### `DELETE /api/v1/authorization/roles/{id}/`
* **Authentication:** Bearer JWT token
* **Required Permission:** `role.manage` or `role.assign`
* **Validation & Safety Rules:**
  * Cross-tenant access returns `404 Not Found`.
  * If `is_system == True`: Returns `400 Bad Request` (`{"detail": "System roles cannot be deleted."}`).
  * If `role.user_roles.filter(is_revoked=False).exists()`: Returns `400 Bad Request` (`{"detail": "Cannot delete role with active user assignments. Reassign users first."}`).
  * Clean deletion removes the custom role without cascading deletions to user accounts or audit logs.
* **Success Response:** `204 No Content`.
* **Audit Event:** `role_deleted` logged with actor, role ID, role name, and slug.

---

### 3.6 Role-Permission Assignment (Atomic Full Replacement)

#### `PUT /api/v1/authorization/roles/{id}/permissions/`
* **Authentication:** Bearer JWT token
* **Required Permission:** `role.manage` or `role.assign`
* **Request Schema:**
```json
{
  "permission_ids": [1, 2, 5, 8, 20, 39, 40, 90]
}
```
* **Validation & Security Rules:**
  1. `permission_ids` must be an array of integers.
  2. **Super Admin Immutability:** If `role.slug == 'super-admin'`, returns `400 Bad Request` (*"Super Admin permissions cannot be narrowed. Super Admin automatically holds all system permissions."*).
  3. **Unknown Permission IDs:** If any ID in `permission_ids` does not exist, returns `400 Bad Request` (`{"detail": "Unknown permission IDs: [...]", "invalid_ids": [...]}`). Assignments remain completely unchanged.
  4. **Inactive Permission IDs:** If any ID in `permission_ids` has `is_active=False`, returns `400 Bad Request` (`{"detail": "Inactive permissions cannot be assigned: [...]", "inactive_ids": [...]}`).
  5. **Enterprise Permission Safeguard:** Non-Super Admin callers attempting to assign preserved enterprise permissions (`is_preserved_enterprise=True`) are rejected with `403 Forbidden`.
  6. **Atomic Replacement:** All operations execute within `@transaction.atomic`. If any error occurs, all mutations rollback cleanly.
* **Success Response (`200 OK`):**
```json
{
  "role_id": 8,
  "role_name": "Shift Supervisor",
  "permissions_count": 8,
  "effective_permissions_count": 8,
  "updated_at": "2026-10-12T11:45:00Z"
}
```
* **Audit Event:** `role_permissions_updated` logged with actor, role ID, permissions count, and list of assigned permission IDs.

---

### 3.7 Scoped User-Role Assignment

#### `POST /api/v1/authorization/user-roles/`
* **Authentication:** Bearer JWT token
* **Required Permission:** `role.assign` or `role.manage`
* **Request Schema:**
```json
{
  "user": 14,
  "role": 8,
  "scope": "organization",
  "branch": null,
  "team": null
}
```
* **Supported Scopes:** `'organization'`, `'branch'`, `'team'`.
* **Validation & Anti-Privilege Escalation:**
  * Role must belong to caller's tenant organization.
  * Target user must belong to caller's tenant organization.
  * Only Super Admins can assign the `super-admin` role. Non-super-admins receive `400 ValidationError` (*"Only Super Admins can assign the Super Admin role."*).
  * Scope permission checks: Caller must hold `role.assign` or `role.manage` at the requested organizational, branch, or team level.
  * **Duplicate Prevention:** If an active, non-revoked assignment already exists for the same `(user, role, scope, branch, team)`, returns `400 Bad Request` (*"User already has this role assigned with the same scope."*).
* **Success Response:** `201 Created` with full `UserRoleSerializer` payload (`id`, `user`, `role`, `role_name`, `role_slug`, `scope`, `is_revoked`, `assigned_at`).
* **Audit Event:** `role_assigned` logged with actor, target user ID, role ID, role name, and scope.

---

### 3.8 User-Role Revocation

#### Explicit Action: `POST /api/v1/authorization/user-roles/{id}/revoke/`
#### RESTful Action: `DELETE /api/v1/authorization/user-roles/{id}/`
* **Authentication:** Bearer JWT token
* **Required Permission:** `role.revoke`, `role.assign`, or `role.manage`
* **Validation & Security Invariants:**
  * Cross-tenant access returns `404 Not Found`.
  * **Super Admin Protection:** Only Super Admins can revoke a Super Admin assignment. Non-super-admin attempts return `403 Forbidden`.
  * **Already Revoked Check:** Calling `POST /revoke/` on an already-revoked assignment returns `400 Bad Request` (`{"detail": "Role already revoked."}`).
  * **Soft Revocation Guarantee:** Sets `is_revoked=True` and `revoked_at=timezone.now()`. The assignment record is never hard-deleted.
* **Success Responses:**
  * `POST /revoke/`: Returns `200 OK` with serialized `UserRole` showing `is_revoked=True`.
  * `DELETE /`: Returns `204 No Content`.
* **Audit Event:** `role_revoked` logged with actor, target user ID, role ID, and role name.

---

### 3.9 Current User Permissions (`/me/`)

#### `GET /api/v1/authorization/me/`
* **Authentication:** Bearer JWT token (`IsAuthenticated`)
* **Response Status:** `200 OK`
* **Response Schema:**
```json
{
  "user": {
    "id": 1,
    "email": "superadmin@acme.local",
    "first_name": "Admin",
    "last_name": "User",
    "is_superuser": false,
    "has_employee_profile": false,
    "employee_code": null,
    "can_create_organization": true
  },
  "roles": ["Organization Owner (Super Admin)"],
  "permissions": [
    "dashboard.view",
    "employee.view",
    "employee.create",
    "payroll.fnf_view",
    "..."
  ]
}
```

---

## 4. Contract Status & Traceability

### 4.1 Implemented & Fully Verified Contracts
* `GET /api/v1/authorization/roles/` (tenant isolated, counts verified)
* `GET /api/v1/authorization/roles/{id}/` (404 cross-tenant verified)
* `POST /api/v1/authorization/roles/` (slug generation, reserved slug protection verified)
* `PUT, PATCH /api/v1/authorization/roles/{id}/` (system role immutability verified)
* `DELETE /api/v1/authorization/roles/{id}/` (system role and active user protection verified)
* `PUT /api/v1/authorization/roles/{id}/permissions/` (atomic replacement, unknown/inactive ID rejection, enterprise protection verified)
* `GET /api/v1/authorization/permissions/` (127 controls grouped across 3 columns, flat format verified)
* `POST /api/v1/authorization/user-roles/` (anti-escalation, cross-tenant check, duplicate prevention verified)
* `POST /api/v1/authorization/user-roles/{id}/revoke/` & `DELETE /user-roles/{id}/` (soft revocation, superadmin protection verified)

### 4.2 Reused Contracts Without Change
* `GET /api/v1/authorization/me/` (Current user dynamic permissions and profile inspection)
* `apps/authorization/permissions.py` (Object-level dynamic permission evaluation helpers)

### 4.3 Deferred Features (Out of Scope for Phase 2D)
* Role Cloning / Duplicate Action (planned for future release).
* Custom Permission Creation (permissions are canonical and governed by system registry).
* Frontend Roles & Permissions UI (designated for Phase 2E).

### 4.4 Unresolved Questions
* **None.** All Phase 2B.2 and Phase 2C design ambiguities (Super Admin matrix vs effective counting, enterprise permission assignment safeguards, atomic full replacement semantics, soft vs hard revocation) have been reconciled, implemented, and verified via automated test suites.

