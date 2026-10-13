# BEYONDSURE HRMS — PHASE 3E.1
# SECURITY DESIGN REVIEW & ARCHITECTURAL CORRECTIONS

**Date:** 2026-10-13  
**Role:** Dev1 only  
**Branch:** `dev1`  
**Review Type:** Architecture and Security Contract Audit  
**Status:** REVISED & APPROVED FOR IMPLEMENTATION

---

## 1. Executive Summary

This Security Design Review documents the mandatory corrective enhancements to the Phase 3E implementation plan (`docs/PHASE3E_IMPLEMENTATION_PLAN.md`). It addresses 12 critical security and architectural requirements governing administrator invitations, authentication isolation, token lifecycles, and tenant boundaries.

No application code or database migrations have been executed in this phase. All existing uncommitted changes are strictly preserved.

---

## 2. Review and Correction Matrix

| Item | Architectural Area | Initial Plan Vulnerability / Gap | Corrected Security Specification |
|---|---|---|---|
| **1** | Existing Account Authentication | Unauthenticated existing users were permitted to submit passwords to `/accept/` (parallel login). | **Eliminated parallel login.** Existing accounts **must** authenticate through the existing `/api/v1/accounts/login/` flow. `/accept/` requires `IsAuthenticated` for existing accounts and verifies identity match. |
| **2** | Token Issuance Contract | `/accept/` was proposed to issue and return DRF auth tokens (`Token.key`). | **No auth tokens issued.** Acceptance endpoints return standard completion metadata. Authentication tokens are issued strictly and exclusively via `/login/`. |
| **3** | Transactional Dispatch & Email Status | Email dispatch was combined with DB transaction; failures coupled to invitation status. | **Decoupled email status.** Invitations persist atomically; email dispatches via `transaction.on_commit()`. Added explicit `email_delivery_status` (`sent`, `failed`, `pending`) separate from invitation `status`. |
| **4** | Public Information Disclosure | `GET /verify/` returned `has_existing_account`. | **Removed `has_existing_account`** from public verification response. Zero user enumeration disclosure. |
| **5** | Account State Handling | Undefined behavior for existing inactive and invited accounts. | **Explicit state handling:**<br>• Active: authenticate then accept.<br>• Inactive: rejected with `403 Forbidden`.<br>• Invited: must set password to activate account and accept. |
| **6** | Conflict & Boundary Constraints | Missing DB constraints on pending invites; role tenant matching unenforced at DB level. | **Added DB constraints:**<br>• `unique_pending_invitation_per_org_role` partial unique index on `(organization, role)` where `status='pending'`.<br>• Foreign key validation ensuring `role.organization_id == organization_id`. |
| **7** | Creator Access Preservation | Ambiguity regarding creator's role post-handover. | **Creator access strictly preserved.** Creator retains organization ownership and organization-scoped access. Invitee becomes co-administrator. Zero global privileges. |
| **8** | Token Expiry & Resend Invalidation | Expiry behavior and resend invalidation semantics underspecified. | **Configurable 7-day default** (`ORGANIZATION_INVITATION_EXPIRY_DAYS = 7`). Resend generates fresh 256-bit token, overwrites `token_hash`, resets timer, increments `resend_count`, and invalidates prior token. |
| **9** | Concurrency & Token Redaction | Race condition risk on double-accept; log leakage risk. | **`select_for_update()`** row-level locking on acceptance. Strict token redaction: raw tokens never persisted or logged. Strict IP/user rate throttling. |
| **10** | State Decoupling | Risk of conflating wizard status with invitation status. | **Four distinct dimensions:**<br>1. Wizard Status (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`)<br>2. Admin Activation (active vs pending)<br>3. Invitation Status (`pending`, `accepted`, `expired`, `revoked`)<br>4. Email Delivery Status (`pending`, `sent`, `failed`). |
| **11** | Stage 6 Backward Compatibility | Risk of breaking existing tests expecting `{"confirm": true}`. | **100% backward compatible.** Legacy payload `{ "confirm": true }` maps to `{ "assignment_type": "self", "confirm": true }`. Zero breaking changes. |
| **12** | Exact API Contracts | Contracts were high-level. | **Complete formal contracts** with method, path, headers, payloads, status codes, and error codes defined in Section 4. |

---

## 3. Detailed Security Invariants

### 3.1 Authentication Isolation (Items 1 & 2)
1. **No Parallel Authentication:** Under no circumstances will `/api/v1/organization/invitations/accept/` authenticate users via password verification. If an email address already belongs to an existing `User`:
   - The user must log in through `/api/v1/accounts/login/`.
   - Once authenticated, the user submits `POST /api/v1/organization/invitations/accept/` with `{"token": "<raw_token>"}`.
   - The view verifies that `request.user.email.lower() == invitation.email.lower()`.
   - If `request.user.email.lower() != invitation.email.lower()`, the view returns HTTP `403 Forbidden` (`{"detail": "You are currently authenticated as a different user. Please switch accounts to accept this invitation."}`).
2. **Contract-Conforming Token Return:** Neither `/verify/` nor `/accept/` issues DRF authentication tokens. Users who create a new account during acceptance must log in through the canonical login endpoint.

### 3.2 Account State Matrix (Item 5)
```
+------------------+-------------------------------------------------------------+
| Account Status   | Acceptance Behavior                                         |
+------------------+-------------------------------------------------------------+
| Non-Existent     | Accepts with new password, creates active User, sets status |
| (New User)       | to 'active', and grants organization-scoped Super Admin.    |
+------------------+-------------------------------------------------------------+
| Active           | Must be authenticated as that user; grants organization-   |
| (status=active)  | scoped Super Admin. Returns 401 if unauthenticated.         |
+------------------+-------------------------------------------------------------+
| Inactive         | Rejects immediately with HTTP 403 Forbidden:                |
| (status=inactive)| "This user account is inactive. Please contact support."    |
+------------------+-------------------------------------------------------------+
| Invited          | User exists in 'invited' status (e.g. from employee import).|
| (status=invited) | Accepts with password: sets password, transitions user to   |
|                  | 'active', and grants organization-scoped Super Admin.       |
+------------------+-------------------------------------------------------------+
```

### 3.3 Transactional Persistence and Asynchronous Email Dispatch (Item 3)
```python
with transaction.atomic():
    invitation = OrganizationInvitation.objects.create(
        organization=org,
        role=super_admin_role,
        email=normalized_email,
        token_hash=token_hash,
        expires_at=expires_at,
        status=InvitationStatus.PENDING,
        email_delivery_status=EmailDeliveryStatus.PENDING,
        invited_by=user,
    )
    # Register post-commit email dispatch hook
    transaction.on_commit(lambda: send_invitation_email_task(invitation.id, raw_token))
```
- If DB transaction rolls back: no email is ever sent.
- If email delivery fails after commit: `email_delivery_status = 'failed'`, `email_delivery_error = str(e)`. The invitation record remains valid and can be resent via the dedicated resend endpoint.

### 3.4 Concurrency and Atomic Acceptance (Item 9)
```python
with transaction.atomic():
    invitation = OrganizationInvitation.objects.select_for_update().filter(
        token_hash=token_hash
    ).first()

    if not invitation:
        raise ValidationError({"token": ["Invalid or expired invitation token."]})

    if invitation.status != InvitationStatus.PENDING:
        if invitation.status == InvitationStatus.ACCEPTED:
            raise ValidationError({"token": ["This invitation has already been accepted."]})
        raise ValidationError({"token": [f"This invitation is {invitation.status} and cannot be accepted."]})

    if invitation.is_expired():
        invitation.status = InvitationStatus.EXPIRED
        invitation.save(update_fields=['status', 'updated_at'])
        raise ValidationError({"token": ["This invitation has expired."]})

    # Grant role & mark accepted atomically...
```

### 3.5 Token Redaction Invariant (Item 9)
- `raw_token` is generated using `secrets.token_urlsafe(32)`.
- It exists only in memory during token generation and dispatch, and in memory during request validation.
- It is **never** written to `OrganizationInvitation` (only `token_hash = sha256(raw_token)` is saved).
- It is **never** passed to `AuditService.log()`.
- It is **never** included in API error bodies or logs.

---

## 4. Formal API Specifications (Item 12)

### 4.1 Stage 6 Submission: `POST /api/v1/organization/wizard/stage-6/`
- **Auth:** Bearer Token (`IsAuthenticated`)
- **Permission:** `IsOrganizationAdminOrCreator`
- **Headers:** `Content-Type: application/json`

#### Option A: Self-Assignment
- **Request:**
  ```json
  {
    "assignment_type": "self",
    "confirm": true
  }
  ```
  *(Legacy payload `{"confirm": true}` is supported and automatically interpreted as Option A).*
- **Response (200 OK):**
  ```json
  {
    "current_stage": 7,
    "completed_stages": [1, 2, 3, 4, 5, 6],
    "status": "in_progress",
    "stage_6": {
      "assignment_type": "self",
      "admin_email": "creator@example.com",
      "status": "active"
    }
  }
  ```

#### Option B: Email Invitation
- **Request:**
  ```json
  {
    "assignment_type": "invite",
    "first_name": "Sarah",
    "last_name": "Connor",
    "email": "sarah.connor@example.com"
  }
  ```
- **Validation Errors (400 Bad Request):**
  - Self-invitation attempt: `{"email": ["To assign yourself, choose 'Assign myself' (Option A)."]}`
  - Invalid email format: `{"email": ["Enter a valid email address."]}`
  - Missing first name: `{"first_name": ["This field is required."]}`
- **Response (200 OK):**
  ```json
  {
    "current_stage": 7,
    "completed_stages": [1, 2, 3, 4, 5, 6],
    "status": "in_progress",
    "stage_6": {
      "assignment_type": "invite",
      "invitation_id": 14,
      "invitee_email": "sarah.connor@example.com",
      "invitee_name": "Sarah Connor",
      "invitation_status": "pending",
      "email_delivery_status": "sent",
      "expires_at": "2026-10-20T10:30:00Z"
    }
  }
  ```

---

### 4.2 Resend Invitation: `POST /api/v1/organization/wizard/stage-6/resend/`
- **Auth:** Bearer Token (`IsAuthenticated`)
- **Permission:** `IsOrganizationAdminOrCreator`
- **Rate Limit:** 5/minute per user
- **Response (200 OK):**
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

### 4.3 Revoke Invitation: `POST /api/v1/organization/wizard/stage-6/revoke/`
- **Auth:** Bearer Token (`IsAuthenticated`)
- **Permission:** `IsOrganizationAdminOrCreator`
- **Rate Limit:** 5/minute per user
- **Response (200 OK):**
  ```json
  {
    "detail": "Invitation revoked successfully.",
    "invitation_id": 14,
    "status": "revoked"
  }
  ```

---

### 4.4 Public Verification: `GET /api/v1/organization/invitations/verify/`
- **Auth:** `AllowAny`
- **Rate Limit:** 15/minute per IP (`AnonRateThrottle`)
- **Query Param:** `?token=<raw_token>`
- **Response (200 OK):**
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
  *(Note: `has_existing_account` is **strictly excluded** from this response).*
- **Error (400 Bad Request):**
  ```json
  {
    "valid": false,
    "code": "INVALID_OR_EXPIRED_TOKEN",
    "detail": "Invalid, expired, or revoked invitation token."
  }
  ```

---

### 4.5 Accept Invitation: `POST /api/v1/organization/invitations/accept/`
- **Auth:** `AllowAny` (Rate-throttled: 5/minute per IP)
- **Headers:** `Content-Type: application/json`

#### Case 1: Existing Account (Authenticated)
- **Request:**
  ```json
  {
    "token": "<raw_token>"
  }
  ```
- **Prerequisite:** Caller must send valid `Authorization: Token <key>` header matching `invitation.email`.
- **Response (200 OK):**
  ```json
  {
    "detail": "Invitation accepted successfully. Organization Super Admin role provisioned.",
    "organization_id": 1,
    "organization_name": "Apex Global Corp",
    "role": "super-admin",
    "status": "accepted"
  }
  ```
- **Error if Unauthenticated (401 Unauthorized):**
  ```json
  {
    "detail": "An account for this email already exists. Please log in before accepting."
  }
  ```

#### Case 2: New Account / Invited Account
- **Request:**
  ```json
  {
    "token": "<raw_token>",
    "password": "SecurePassword123!",
    "first_name": "Sarah",
    "last_name": "Connor"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "detail": "Account activated and invitation accepted successfully. Please sign in to access your organization.",
    "organization_id": 1,
    "organization_name": "Apex Global Corp",
    "role": "super-admin",
    "status": "accepted"
  }
  ```

---

## 5. Implementation Readiness Confirmation

This Security Design Review satisfies all 12 directives of Phase 3E.1. The updated implementation plan in [`docs/PHASE3E_IMPLEMENTATION_PLAN.md`](file:///d:/hrms/hrms/docs/PHASE3E_IMPLEMENTATION_PLAN.md) serves as the formal specification for Phase 3E.
