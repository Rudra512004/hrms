# BEYONDSURE HRMS — PHASE 3C
## ORGANIZATION SETUP WIZARD API CONTRACT

**Document Version:** 1.0.0  
**Phase:** Phase 3C (Organization Setup Wizard Services & API Endpoints)  
**Status:** APPROVED & IMPLEMENTED  
**Author / Developer:** Dev1 Only  
**Branch:** `dev1` | **HEAD:** `8203b224b86b0b3cf7261a6f4c63a4ddb0685193`  
**Base URL:** `/api/v1/organization/wizard/` (Canonical) | `/api/v1/organization/onboarding/` (Alias)  

---

## 1. Authentication & Security Architecture

### 1.1 Authentication
All wizard endpoints require standard HTTP Bearer Token or Session Authentication:
```http
Authorization: Bearer <access_token>
```
Unauthenticated requests are rejected with `HTTP 401 Unauthorized`.

### 1.2 Tenant-Scoped Authorization
Tenant resolution is performed strictly on the backend via `OrganizationOnboardingService.resolve_onboarding(user, org_id=None)`:
1. **Self-Service Owner Resolution:** For standard verified tenant owners, the active onboarding session is resolved from `request.user.tenant_owner_registration` or direct `onboarding.owner == request.user`.
2. **Explicit Organization ID Access:** A client-supplied `org_id` query parameter or body field is evaluated with strict authoritative RBAC verification:
   - **No Superuser Bypass:** A global Django superuser (`is_superuser=True`) does NOT automatically bypass tenant isolation. Tenant isolation applies strictly to all users.
   - Access is granted ONLY if:
     a) The caller is the direct onboarding `owner` of that organization, OR
     b) The caller holds an active, unrevoked, unexpired `super-admin` role within that specific tenant organization, OR
     c) The caller holds active, unrevoked, unexpired organization-scoped `company.manage` or `organization.manage` permissions in that specific organization context.
   - Any other caller attempting to query or mutate a foreign organization's onboarding is rejected with `HTTP 403 Forbidden` (`PermissionDenied`).
3. **No Cross-Tenant Escalation:** Client-supplied organization IDs are never trusted blindly. Direct ownership of Tenant A grants zero authority over Tenant B. Inactive users, revoked roles, expired roles, or sub-organization scopes (`BRANCH` or `TEAM`) cannot access organization setup wizard endpoints.

---

## 2. API Endpoints Catalog

### 2.1 Start Wizard Session (Stage 1)
- **Method:** `POST`
- **Path:** `/api/v1/organization/wizard/start/`
- **Purpose:** Initializes tenant organization, auto-provisions branding, and creates durable `OrganizationOnboarding` session.
- **Precondition:** Caller must be a verified owner (`can_launch_organization == True`) or platform superuser.

#### Request Body
```json
{
  "name": "Apex Global Technologies",
  "code": "APEX",
  "currency_code": "INR",
  "date_format": "DD/MM/YYYY",
  "timezone": "Asia/Kolkata"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Unique organization name (max 255 chars). Cannot be whitespace. |
| `code` | string | No | Unique organization code (max 50 chars). Optional, defaults to empty. |
| `currency_code` | string | No | Currency code (default: `"INR"`). Configured on tenant branding. |
| `date_format` | string | No | Standard date format string (default: `"DD/MM/YYYY"`). |
| `timezone` | string | No | Organization-level default timezone (default: `"UTC"`). |

#### Response (`HTTP 201 Created`)
```json
{
  "onboarding_id": 12,
  "organization_id": 45,
  "name": "Apex Global Technologies",
  "code": "APEX",
  "current_stage": 2,
  "completed_stages": [1],
  "status": "in_progress"
}
```

---

### 2.2 Get Wizard Status
- **Method:** `GET`
- **Path:** `/api/v1/organization/wizard/status/`
- **Query Params:** `?org_id=<id>` (optional, permitted for superusers / authorized admins only)
- **Purpose:** Queries current onboarding progress, completed stages, saved metadata, and diagnostic readiness summary.

#### Response (`HTTP 200 OK`)
```json
{
  "onboarding_id": 12,
  "organization_id": 45,
  "organization_name": "Apex Global Technologies",
  "organization_code": "APEX",
  "status": "in_progress",
  "current_stage": 2,
  "completed_stages": [1],
  "completed_at": null,
  "metadata": {
    "stage_1": {
      "name": "Apex Global Technologies",
      "code": "APEX",
      "currency_code": "INR",
      "date_format": "DD/MM/YYYY",
      "timezone": "Asia/Kolkata"
    }
  },
  "readiness_summary": {
    "score": 14,
    "total_checks": 7,
    "ready_checks": 1
  }
}
```

---

### 2.3 Stage Execution Endpoints

#### Dispatcher Route
- **Method:** `POST`
- **Path:** `/api/v1/organization/wizard/stage/<int:stage_number>/`

#### Dedicated Stage Routes (Aliases)
- `POST /api/v1/organization/wizard/stage-2/`
- `POST /api/v1/organization/wizard/stage-3/`
- `POST /api/v1/organization/wizard/stage-4/`
- `POST /api/v1/organization/wizard/stage-5/`
- `POST /api/v1/organization/wizard/stage-6/`

---

### 2.4 Stage 2: Initial Branch (Head Office)
- **Method:** `POST`
- **Path:** `/api/v1/organization/wizard/stage-2/`
- **Prerequisite:** Stage 1 must be completed.
- **Idempotency:** Re-execution updates the existing head office branch without duplicating branch records.

#### Request Body
```json
{
  "name": "Headquarters Bengaluru",
  "code": "HQ-BLR",
  "address_line1": "100 Tech Park Way",
  "address_line2": "Tower B, 4th Floor",
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

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Unique branch name within organization. |
| `code` | string | No | Unique branch code within organization. |
| `address_line1` | string | No | Physical street address. |
| `city` | string | No | Branch city. |
| `state` | string | No | Branch state / province. |
| `country` | string | No | Branch country. |
| `postal_code` | string | No | Postal code / PIN code. |
| `timezone` | string | No | Local timezone (default: `"UTC"`). |
| `latitude` | decimal | No | Geolocation latitude (-90 to +90). |
| `longitude` | decimal | No | Geolocation longitude (-180 to +180). |
| `radius` | float | No | Geofence radius in meters (minimum 100.0m). |

#### Response (`HTTP 200 OK`)
Returns complete wizard status payload showing `current_stage: 3`, `completed_stages: [1, 2]`.

---

### 2.5 Stage 3: Structure (Departments & Designations)
- **Method:** `POST`
- **Path:** `/api/v1/organization/wizard/stage-3/`
- **Prerequisite:** Stage 2 must be completed.
- **Idempotency:** Departments and designations are updated or created based on name; re-execution safely merges changes.

#### Request Body
```json
{
  "departments": [
    {"name": "Engineering", "code": "ENG", "description": "Software Engineering"},
    {"name": "Human Resources", "code": "HR", "description": "People Ops"}
  ],
  "designations": [
    {"name": "Director of Engineering", "code": "DIR-ENG", "level": 1},
    {"name": "Senior Software Engineer", "code": "SR-SWE", "level": 3}
  ]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `departments` | array | Yes | Non-empty list of branch departments. Duplicates within list are rejected. |
| `designations` | array | Yes | Non-empty list of organization designations. Duplicates within list are rejected. |

#### Response (`HTTP 200 OK`)
Returns wizard status payload showing `current_stage: 4`, `completed_stages: [1, 2, 3]`.

---

### 2.6 Stage 4: Working Calendar & Holidays
- **Method:** `POST`
- **Path:** `/api/v1/organization/wizard/stage-4/`
- **Prerequisite:** Stage 3 must be completed.
- **Idempotency:** Working calendar is updated; recurring rules and holidays are updated idempotently.

#### Request Body
```json
{
  "work_days": "0,1,2,3,4",
  "recurring_rules": [
    {"weekday": 5, "occurrence": 2, "is_working": false},
    {"weekday": 5, "occurrence": 4, "is_working": false}
  ],
  "holidays": [
    {"name": "Republic Day", "date": "2026-01-26", "holiday_type": "public"}
  ]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `work_days` | string | Yes | Comma-separated weekdays (`0`=Monday, `6`=Sunday). Validated strictly. |
| `recurring_rules`| array | No | Rules for specific weekday occurrences (e.g., 2nd/4th Saturday off). |
| `holidays` | array | No | Branch-scoped explicit holidays (`name`, `date`, `holiday_type`). |

#### Response (`HTTP 200 OK`)
Returns wizard status payload showing `current_stage: 5`, `completed_stages: [1, 2, 3, 4]`.

---

### 2.7 Stage 5: Shift Schedule & Attendance Policy
- **Method:** `POST`
- **Path:** `/api/v1/organization/wizard/stage-5/`
- **Prerequisite:** Stage 4 must be completed.
- **Single-Active-Shift Invariant:** If an active shift already exists for the head office branch, it is updated in place. Multiple active shifts are strictly prohibited.

#### Request Body
```json
{
  "shift": {
    "name": "General Shift",
    "code": "GEN-9TO6",
    "start_time": "09:00:00",
    "end_time": "18:00:00",
    "grace_period_minutes": 15,
    "work_days": "0,1,2,3,4"
  },
  "attendance_policy": {
    "is_office_gps_enabled": true,
    "is_office_ip_enabled": false,
    "is_wfh_enabled": true,
    "wfh_bypasses_office_restrictions": true
  },
  "office_network": {
    "name": "HQ Wi-Fi",
    "network": "192.168.1.0/24",
    "description": "Office subnet for clock-in"
  }
}
```

#### Response (`HTTP 200 OK`)
Returns wizard status payload showing `current_stage: 6`, `completed_stages: [1, 2, 3, 4, 5]`.

---

### 2.8 Stage 6: Initial Administrator & RBAC
- **Method:** `POST`
- **Path:** `/api/v1/organization/wizard/stage-6/`
- **Prerequisite:** Stage 5 must be completed.
- **Behavior:** Ensures the tenant `super-admin` role exists with all 144 canonical permissions. Supports Option A (Self-Assignment, preserving legacy `{"confirm": true}`) and Option B (Cryptographic Email Invitation).

#### Request Body — Option A (Self-Assignment)
Legacy format:
```json
{
  "confirm": true
}
```
Explicit format:
```json
{
  "assignment_type": "self",
  "confirm": true
}
```

#### Request Body — Option B (Email Invitation)
```json
{
  "assignment_type": "invite",
  "first_name": "Sarah",
  "last_name": "Connor",
  "email": "sarah.connor@example.com"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `assignment_type` | string | No | `"self"` (default) or `"invite"`. |
| `confirm` | boolean | Conditional | Required (`true`) if `assignment_type == "self"`. |
| `first_name` | string | Conditional | Required if `assignment_type == "invite"`. |
| `last_name` | string | No | Optional invitee surname. |
| `email` | string | Conditional | Required if `assignment_type == "invite"`. Normalized to lowercase. Self-invitation is strictly rejected. |

#### Response (`HTTP 200 OK`)
Returns wizard status payload showing `current_stage: 7`, `completed_stages: [1, 2, 3, 4, 5, 6]`, and `metadata.stage_6`.

---

### 2.8.1 Stage 6 Resend Invitation
- **Method:** `POST`
- **Path:** `/api/v1/organization/wizard/stage-6/resend/`
- **Authentication:** `IsAuthenticated` (verified owner or tenant super-admin)
- **Throttling:** 5 requests/minute per user (`UserRateThrottle`)
- **Behavior:** Rotates invitation token, generates a new SHA-256 hash, resets expiration to `now + 7 days`, increments `resend_count`, and re-dispatches invitation email post-commit.

#### Response (`HTTP 200 OK`)
```json
{
  "detail": "Invitation resent successfully.",
  "invitation_id": 14,
  "email": "sarah.connor@example.com",
  "status": "pending",
  "email_delivery_status": "sent",
  "resend_count": 1,
  "expires_at": "2026-10-20T11:00:00Z"
}
```

---

### 2.8.2 Stage 6 Revoke Invitation
- **Method:** `POST`
- **Path:** `/api/v1/organization/wizard/stage-6/revoke/`
- **Authentication:** `IsAuthenticated` (verified owner or tenant super-admin)
- **Throttling:** 5 requests/minute per user (`UserRateThrottle`)
- **Behavior:** Marks pending invitation as `REVOKED`, sets `revoked_at`, and prevents any subsequent verification or acceptance.

#### Response (`HTTP 200 OK`)
```json
{
  "detail": "Invitation revoked successfully.",
  "invitation_id": 14,
  "status": "revoked"
}
```

---

### 2.8.3 Public Invitation Verification
- **Method:** `GET`
- **Path:** `/api/v1/organization/invitations/verify/?token=<raw_token>`
- **Authentication:** `AllowAny`
- **Throttling:** 15 requests/minute per IP (`OrganizationInvitationThrottle`)
- **Behavior:** Hashes token via SHA-256 and retrieves invitation. If expired, transitions status to `EXPIRED`. Zero account existence disclosure (`has_existing_account` is omitted).

#### Response (`HTTP 200 OK`)
```json
{
  "valid": true,
  "organization_name": "Apex Global Corp",
  "organization_code": "APEX",
  "email": "sarah.connor@example.com",
  "first_name": "Sarah",
  "last_name": "Connor",
  "expires_at": "2026-10-20T11:00:00Z"
}
```

---

### 2.8.4 Public Invitation Acceptance
- **Method:** `POST`
- **Path:** `/api/v1/organization/invitations/accept/`
- **Authentication:** `AllowAny`
- **Throttling:** 5 requests/minute per IP (`OrganizationInvitationAcceptThrottle`)
- **Concurrency Protection:** Uses `select_for_update()` inside `transaction.atomic()`.

#### Flows:
1. **Existing Active Account:** Caller must be authenticated via canonical `/api/v1/accounts/login/` matching `invitation.email`. If unauthenticated: `HTTP 401`. If wrong email: `HTTP 403`.
2. **Inactive Account:** Returns `HTTP 403 Forbidden` (`"inactive or suspended"`).
3. **New / Invited Account:** Supplies `password` (and optional names). Validates against Django password validators, activates account, and provisions `super-admin` `UserRole`. Zero DRF tokens issued.

#### Request Body
```json
{
  "token": "<raw_token>",
  "password": "SecurePassword123!",
  "first_name": "Sarah",
  "last_name": "Connor"
}
```

#### Response (`HTTP 200 OK`)
```json
{
  "detail": "Invitation accepted successfully. Organization Super Admin role provisioned.",
  "organization_id": 1,
  "organization_name": "Apex Global Corp",
  "role": "super-admin",
  "status": "accepted"
}
```

---

### 2.9 Stage 7: Complete Setup
- **Method:** `POST`
- **Path:** `/api/v1/organization/wizard/complete/`
- **Prerequisites:**
  1. All stages 1 through 6 recorded in `completed_stages`.
  2. Direct database re-validation: `revalidate_persisted_prerequisites` verifies active branch, structure, calendar, shift, and admin role in the database.
- **Post-Completion State:** Sets `onboarding.status = COMPLETED`, sets `completed_at = now()`, activates organization (`org.status = 'active'`). Subsequent calls are rejected with `HTTP 400 Bad Request`.

#### Response (`HTTP 200 OK`)
```json
{
  "status": "completed",
  "organization_id": 45,
  "completed_at": "2026-10-13T02:30:00Z",
  "readiness_score": 86,
  "redirect_url": "/dashboard"
}
```

---

### 2.10 Save Draft Metadata
- **Method:** `POST`
- **Path:** `/api/v1/organization/wizard/draft/`
- **Purpose:** Saves intermediate UI form progress without validating or committing domain entities.
- **Security Check:** Evaluated by `validate_onboarding_metadata`. Strictly rejects any sensitive keys or values (passwords, JWTs, secret keys, bearer tokens).

#### Request Body
```json
{
  "stage": 2,
  "data": {
    "draft_branch_name": "Proposed Regional Office",
    "draft_city": "Hyderabad"
  }
}
```

#### Response (`HTTP 200 OK`)
```json
{
  "detail": "Draft saved successfully.",
  "stage": 2,
  "current_stage": 2
}
```

---

### 2.11 Diagnostic Readiness Assessment
- **Method:** `GET`
- **Path:** `/api/v1/organization/wizard/readiness/`
- **Query Params:** `?org_id=<id>` (optional, authorized users only)
- **Purpose:** Runs `OrganizationReadinessService.assess(org)` and returns full checklist diagnostic scores.

#### Response (`HTTP 200 OK`)
```json
{
  "score": 86,
  "ready": false,
  "checks": [
    {"name": "branches", "state": "ready", "message": "At least one active branch is configured."},
    {"name": "calendars", "state": "ready", "message": "All active branches have working calendars."},
    {"name": "attendance_policies", "state": "ready", "message": "All active branches have attendance policies."},
    {"name": "structure", "state": "ready", "message": "Departments and designations are configured."},
    {"name": "leave_types", "state": "action_required", "message": "No leave types configured for this organization."},
    {"name": "roles", "state": "ready", "message": "At least one active role is configured."},
    {"name": "shifts", "state": "ready", "message": "All active branches have configured shifts."}
  ]
}
```

---

## 3. Error Contract & Standard Codes

| HTTP Status | Error Scenario | Example Response Body |
|---|---|---|
| `400 Bad Request` | Missing or invalid field validation | `{"radius": ["Branch radius must be at least 100.0 meters."]}` |
| `400 Bad Request` | Prerequisite stage skipping | `{"detail": "Cannot advance to Stage 3. Preceding stages must be completed first: Stage 2 (Initial Branch)."}` |
| `400 Bad Request` | Sensitive metadata in draft | `{"data": ["Draft data contains disallowed sensitive key 'password'."]}` |
| `400 Bad Request` | Post-completion modification attempt | `{"detail": "Onboarding is already completed for this organization."}` |
| `401 Unauthorized` | Missing / invalid credentials | `{"detail": "Authentication credentials were not provided."}` |
| `403 Forbidden` | Cross-tenant access attempt | `{"detail": "You do not have administrative access to this organization's onboarding."}` |
| `404 Not Found` | Unknown organization ID | `{"detail": "No onboarding session found for organization ID 999."}` |
