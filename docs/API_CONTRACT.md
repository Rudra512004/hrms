# HRMS API Contract (FROZEN FOR FRONTEND INTEGRATION)

This document is the frozen, authoritative contract between the backend and frontend for Authentication, Provisioning, and RBAC flows.

## 1. Identity Lifecycle & Authentication Flows

The HRMS implements a strictly HR-provisioned identity lifecycle.

**1. Provisioning:** Authorized HR users provision new employees using a company email. The system normalizes the email, checks for uniqueness, creates the `User` and `Employee` records, and generates an activation token. The account status is strictly `invited`.
**2. Activation:** The invited employee receives an activation mechanism (via email). The employee submits their activation credentials (uid, token, and a new password). The backend cryptographically validates the token, sets the password natively, and transitions the status to `active`.
**3. Login:** The active employee authenticates using their canonical company email and password. Personal emails and HRMS employee codes cannot be used for login.

*Remaining Business Decisions (Non-Blocking for Dev2):*
- Exact generation format/algorithm for the `employee_code`. The provisioning API currently accepts an authorized HR-supplied value.
- Future integration of Google Workspace OIDC (capacity exists via `google_subject_id`).
- Actual email delivery integration (currently, activation tokens are generated but must be exposed via API in DEBUG mode for development).

---

## 2. Authentication APIs

### Login

Authenticate an active user using their company email.

- **Method:** `POST`
- **Path:** `/api/v1/auth/login/`
- **Authentication Requirement:** None (Public)
- **State Transition:** Authenticates an already `active` user. Rejects `invited` or `inactive` users.

**Request Body:**
```json
{
  "email": "employee@company.com",
  "password": "yourpassword"
}
```

**Successful Response (200 OK):**
```json
{
  "token": "d7a4f9b8c3d...e2f1",
  "user": {
    "id": 1,
    "email": "employee@company.com",
    "first_name": "John",
    "last_name": "Doe",
    "status": "active",
    "is_staff": false,
    "is_superuser": false,
    "created_at": "2023-10-27T10:00:00Z",
    "updated_at": "2023-10-27T10:00:00Z",
    "employee_code": "EMP001"
  }
}
```

**Validation Errors (400 Bad Request):**
- Invalid credentials, personal email, HRMS ID attempt, or non-active status:
```json
{
  "non_field_errors": [
    "Invalid login credentials or account is not active."
  ]
}
```

---

### Logout

Invalidate the current user's token.

- **Method:** `POST`
- **Path:** `/api/v1/auth/logout/`
- **Authentication Requirement:** Token (`Authorization: Token <token>`)

**Successful Response (200 OK):**
```json
{
  "detail": "Successfully logged out."
}
```
**Authentication Error (401 Unauthorized):** Token missing or invalid.

---

### Get Current User (Me)

Retrieve the profile information of the currently authenticated user.

- **Method:** `GET`
- **Path:** `/api/v1/auth/me/`
- **Authentication Requirement:** Token (`Authorization: Token <token>`)

**Successful Response (200 OK):**
```json
{
  "id": 1,
  "email": "employee@company.com",
  "first_name": "John",
  "last_name": "Doe",
  "status": "active",
  "is_staff": false,
  "is_superuser": false,
  "created_at": "2023-10-27T10:00:00Z",
  "updated_at": "2023-10-27T10:00:00Z",
  "employee_code": "EMP001"
}
```
**Authentication Error (401 Unauthorized):** Token missing or invalid.

---

### Account Activation

Set password and activate an invited account using cryptographic tokens.

*Security Note:* The Base64 encoding of the `uid` is merely an encoding transport mechanism, not a security layer. The `token` is the actual cryptographic security credential evaluated by Django's token generator. Tokens expire, and they immediately invalidate upon successful password change (preventing replay attacks).

- **Method:** `POST`
- **Path:** `/api/v1/auth/activate/`
- **Authentication Requirement:** None (Public)
- **State Transition:** Evaluates an `invited` user; transitions to `active`.

**Request Body:**
```json
{
  "uid": "MQ",
  "token": "base64-token-string",
  "password": "NewSecurePassword123!"
}
```

**Successful Response (200 OK):**
```json
{
  "detail": "Account successfully activated."
}
```

**Validation Errors (400 Bad Request):**
- **Token invalid/expired/replayed:** `{"non_field_errors": ["Invalid or expired activation token."]}`
- **Account already active:** `{"non_field_errors": ["Account is already active or cannot be activated."]}`
- **Malformed UID:** `{"non_field_errors": ["Invalid user UID."]}`
- **Weak Password:** `{"password": ["This password is too short. It must contain at least 8 characters."]}`

---

## 3. Employee APIs

### Provision Employee

Create a new employee record and associated invited user account.

- **Method:** `POST`
- **Path:** `/api/v1/employees/`
- **Authentication Requirement:** Token
- **Authorization Requirement:** Must dynamically hold `employee.create` permission.
- **State Transition:** Creates User/Employee uniquely. Status defaults to `invited`.

**Request Body:**
```json
{
  "email": "new@company.com",
  "first_name": "Alice",
  "last_name": "Smith",
  "employee_code": "EMP002"
}
```

**Successful Response (201 Created):**
*Note: `activation_info` is strictly omitted in Production. It is temporarily exposed here only when `settings.DEBUG = True` to facilitate local development until the email delivery service is fully integrated.*
```json
{
  "detail": "Employee provisioned successfully.",
  "employee": {
    "id": 2,
    "email": "new@company.com",
    "first_name": "Alice",
    "last_name": "Smith",
    "status": "invited",
    "employee_code": "EMP002",
    "phone_number": "",
    "address": "",
    "emergency_contact_name": "",
    "emergency_contact_phone": ""
  },
  "activation_info": {
    "uid": "Mg",
    "token": "token-string"
  }
}
```

**Validation Errors (400 Bad Request):**
- Duplicate email: `{"email": ["A user with this email already exists."]}`
- Duplicate code: `{"employee_code": ["An employee with this code already exists."]}`

**Authorization Errors:**
- **401 Unauthorized:** Missing token.
- **403 Forbidden:** Valid token, but lacks `employee.create` permission.

---

### Retrieve/Update Employee Self-Service Profile

View or securely modify self-service fields. Prevent IDOR by intrinsically operating on `request.user.employee`.

- **Method:** `GET` or `PATCH`
- **Path:** `/api/v1/employees/me/`
- **Authentication Requirement:** Token

**PATCH Request Body (Example):**
```json
{
  "phone_number": "+1234567890",
  "address": "123 Main St"
}
```

**Editable Self-Service Fields:**
- `phone_number`
- `address`
- `emergency_contact_name`
- `emergency_contact_phone`

**Read-Only / HR-Controlled Fields:**
*(Attempting to send these in a PATCH request will be safely ignored. They cannot be modified via self-service)*
- `employee_code`
- `email` (company email)
- `status`
- `role` / `permissions` (handled via separate RBAC endpoints)
- Any arbitrary ID injection (to modify another user) is explicitly ignored.

**Successful Response (200 OK):**
```json
{
  "id": 1,
  "email": "employee@company.com",
  "first_name": "John",
  "last_name": "Doe",
  "status": "active",
  "employee_code": "EMP001",
  "phone_number": "+1234567890",
  ...
}
```

---

## 4. Dynamic RBAC & Role Assignment

Authorization remains purely dynamic.
The backend explicitly uses `AuthorizationService.has_permission(user, 'permission.codename')` and strictly avoids any hardcoded role strings like `if role == "HR"`.

- Role checks require a `403 Forbidden` response if the active user lacks the required permission codename (e.g., `employee.create`).
- Normal employees cannot provision others or arbitrarily elevate their permissions through provisioning endpoints.

---

## 5. Network Policy & WFH

The HRMS enforces a strict network access policy. Once authenticated, a user's API requests must pass network access constraints unless the endpoint is explicitly public (e.g., login, activation).

**Network Policy Algorithm:**
1. Determine the trusted client IP. For direct requests, this uses `REMOTE_ADDR`. We do not blindly trust `X-Forwarded-For` to prevent trivial spoofing.
2. The `NetworkAccessService` evaluates if the IP falls within any active `OfficeNetwork` CIDR range. If yes, access is allowed.
3. If outside an active office network, the system checks for an active, approved `WFHRequest` for the employee spanning the current time. If active, access is allowed.
4. Otherwise, access is denied (403 Forbidden).

**Note:** The WFH exception bypasses network restrictions, but *does not* bypass authentication. A user must always authenticate with valid credentials.

---

## 6. Office Network APIs

Manage allowed office networks (Requires authorized users).

### List / Create Office Networks

- **Method:** `GET` / `POST`
- **Path:** `/api/v1/organization/office-networks/`
- **Authentication Requirement:** Token
- **Authorization Requirement:** `office_network.view` (GET), `office_network.create` (POST)

**POST Request Body:**
```json
{
  "organization": 1,
  "name": "Headquarters",
  "network": "203.0.113.0/24",
  "description": "Main HQ network",
  "is_active": true
}
```

**Successful Response (201 Created):**
```json
{
  "id": 1,
  "organization": 1,
  "name": "Headquarters",
  "network": "203.0.113.0/24",
  "description": "Main HQ network",
  "is_active": true,
  "created_at": "2023-11-01T10:00:00Z",
  "updated_at": "2023-11-01T10:00:00Z"
}
```

**Validation Errors (400 Bad Request):**
- Invalid CIDR: `{"network": ["Invalid CIDR network"]}`

### Retrieve / Update / Delete Office Network

- **Method:** `GET` / `PUT` / `PATCH` / `DELETE`
- **Path:** `/api/v1/organization/office-networks/<id>/`
- **Authentication Requirement:** Token
- **Authorization Requirement:** `office_network.view` (GET), `office_network.update` (PUT/PATCH), `office_network.delete` (DELETE)

---

## 7. Work From Home (WFH) APIs

Manage and approve WFH requests.

### List / Create WFH Requests

- **Method:** `GET` / `POST`
- **Path:** `/api/v1/employees/wfh-requests/`
- **Authentication Requirement:** Token
- **Authorization Requirement (GET):** Employees inherently see their own requests. Users with `wfh.view` see all requests.
- **Authorization Requirement (POST):** Requires `wfh.request` permission.

**POST Request Body:**
```json
{
  "start_at": "2023-11-05T00:00:00Z",
  "end_at": "2023-11-05T23:59:59Z",
  "reason": "Doctor appointment"
}
```
*Note: `employee` ID injection is ignored. The system intrinsically maps it to `request.user.employee`.*

**Successful Response (201 Created):**
```json
{
  "id": 1,
  "employee": 1,
  "start_at": "2023-11-05T00:00:00Z",
  "end_at": "2023-11-05T23:59:59Z",
  "reason": "Doctor appointment",
  "status": "pending",
  "requested_at": "2023-11-01T10:00:00Z",
  "reviewed_by": null,
  "reviewed_at": null,
  "reviewer_comment": ""
}
```

**Validation Errors (400 Bad Request):**
- End date before start date: `{"end_at": ["End date must be after start date."]}`

### Cancel Request

- **Method:** `POST`
- **Path:** `/api/v1/employees/wfh-requests/<id>/cancel/`
- **Authentication Requirement:** Token
- **Authorization Requirement:** Must own the request, or hold `wfh.cancel`. The request must be in `pending` state.

### Approve / Reject Request

- **Method:** `POST`
- **Path:** `/api/v1/employees/wfh-requests/<id>/approve/` or `/api/v1/employees/wfh-requests/<id>/reject/`
- **Authentication Requirement:** Token
- **Authorization Requirement:** `wfh.approve` or `wfh.reject`. *An employee cannot approve their own request.*
- **State Transition:** Pending -> Approved, or Pending -> Rejected.

**POST Request Body (Optional Comment):**
```json
{
  "reviewer_comment": "Approved as per discussion."
}
```

**State Transition Errors (400 Bad Request):**
- Invalid transition: `{"detail": "Only pending requests can be approved."}`
- Self-approval attempt (403): `{"detail": "Cannot approve own request."}`

 - - - 
 
 # #   8 .   A t t e n d a n c e   A P I s 
 
 R e c o r d   a n d   r e t r i e v e   e m p l o y e e   a t t e n d a n c e .   T h e   a t t e n d a n c e   A P I   e n f o r c e s   t h e   n e t w o r k   a c c e s s   p o l i c y   ( r e q u i r e s   O f f i c e   I P   o r   a c t i v e   W F H )   u n l e s s   t h e   u s e r   i s   a   S u p e r a d m i n . 
 
 # # #   L i s t   A t t e n d a n c e   H i s t o r y 
 
 R e t r i e v e   t h e   a u t h e n t i c a t e d   e m p l o y e e ' s   a t t e n d a n c e   r e c o r d s . 
 
 -   * * M e t h o d : * *   ` G E T ` 
 -   * * P a t h : * *   ` / a p i / v 1 / a t t e n d a n c e / ` 
 -   * * A u t h e n t i c a t i o n   R e q u i r e m e n t : * *   T o k e n 
 -   * * A u t h o r i z a t i o n   R e q u i r e m e n t : * *   ` I s N e t w o r k A l l o w e d `   e n f o r c e s   O f f i c e   I P   o r   W F H . 
 
 * * S u c c e s s f u l   R e s p o n s e   ( 2 0 0   O K ) : * * 
 ` ` ` j s o n 
 [ 
     { 
         " i d " :   1 , 
         " e m p l o y e e " :   1 , 
         " d a t e " :   " 2 0 2 3 - 1 1 - 0 5 " , 
         " c h e c k _ i n " :   " 2 0 2 3 - 1 1 - 0 5 T 0 9 : 0 0 : 0 0 Z " , 
         " c h e c k _ o u t " :   " 2 0 2 3 - 1 1 - 0 5 T 1 7 : 0 0 : 0 0 Z " , 
         " s t a t u s " :   " p r e s e n t " 
     } 
 ] 
 ` ` ` 
 
 # # #   C h e c k - i n 
 
 R e c o r d   t h e   s t a r t   o f   t h e   w o r k d a y .   A l l o w e d   e x a c t l y   o n c e   p e r   e m p l o y e e   p e r   d a y . 
 
 -   * * M e t h o d : * *   ` P O S T ` 
 -   * * P a t h : * *   ` / a p i / v 1 / a t t e n d a n c e / c h e c k - i n / ` 
 -   * * A u t h e n t i c a t i o n   R e q u i r e m e n t : * *   T o k e n 
 -   * * A u t h o r i z a t i o n   R e q u i r e m e n t : * *   ` I s N e t w o r k A l l o w e d `   e n f o r c e s   O f f i c e   I P   o r   W F H . 
 
 * * S u c c e s s f u l   R e s p o n s e   ( 2 0 1   C r e a t e d ) : * * 
 ` ` ` j s o n 
 { 
     " i d " :   1 , 
     " e m p l o y e e " :   1 , 
     " d a t e " :   " 2 0 2 3 - 1 1 - 0 5 " , 
     " c h e c k _ i n " :   " 2 0 2 3 - 1 1 - 0 5 T 0 9 : 0 0 : 0 0 Z " , 
     " c h e c k _ o u t " :   n u l l , 
     " s t a t u s " :   " p r e s e n t " 
 } 
 ` ` ` 
 
 * * V a l i d a t i o n   E r r o r s   ( 4 0 0   B a d   R e q u e s t ) : * * 
 -   D u p l i c a t e   c h e c k - i n   f o r   t h e   d a y :   ` { " d e t a i l " :   " C h e c k - i n   a l r e a d y   e x i s t s   f o r   t o d a y . " } ` 
 
 * * A u t h o r i z a t i o n   E r r o r s : * * 
 -   * * 4 0 3   F o r b i d d e n : * *   L a c k s   v a l i d   n e t w o r k   c o n t e x t   ( n o t   i n   o f f i c e ,   n o   W F H ) . 
 
 # # #   C h e c k - o u t 
 
 R e c o r d   t h e   e n d   o f   t h e   w o r k d a y .   M u s t   f o l l o w   a   v a l i d   c h e c k - i n   f o r   t h e   c u r r e n t   d a y .   A l l o w e d   e x a c t l y   o n c e   p e r   e m p l o y e e   p e r   d a y . 
 
 -   * * M e t h o d : * *   ` P O S T ` 
 -   * * P a t h : * *   ` / a p i / v 1 / a t t e n d a n c e / c h e c k - o u t / ` 
 -   * * A u t h e n t i c a t i o n   R e q u i r e m e n t : * *   T o k e n 
 -   * * A u t h o r i z a t i o n   R e q u i r e m e n t : * *   ` I s N e t w o r k A l l o w e d `   e n f o r c e s   O f f i c e   I P   o r   W F H . 
 
 * * S u c c e s s f u l   R e s p o n s e   ( 2 0 0   O K ) : * * 
 ` ` ` j s o n 
 { 
     " i d " :   1 , 
     " e m p l o y e e " :   1 , 
     " d a t e " :   " 2 0 2 3 - 1 1 - 0 5 " , 
     " c h e c k _ i n " :   " 2 0 2 3 - 1 1 - 0 5 T 0 9 : 0 0 : 0 0 Z " , 
     " c h e c k _ o u t " :   " 2 0 2 3 - 1 1 - 0 5 T 1 7 : 0 0 : 0 0 Z " , 
     " s t a t u s " :   " p r e s e n t " 
 } 
 ` ` ` 
 
 * * V a l i d a t i o n   E r r o r s   ( 4 0 0   B a d   R e q u e s t ) : * * 
 -   N o   c h e c k - i n   f o r   t o d a y :   ` { " d e t a i l " :   " C a n n o t   c h e c k   o u t   w i t h o u t   a   c h e c k - i n . " } ` 
 -   A l r e a d y   c h e c k e d   o u t :   ` { " d e t a i l " :   " A l r e a d y   c h e c k e d   o u t   f o r   t o d a y . " } ` 
 
 * * A u t h o r i z a t i o n   E r r o r s : * * 
 -   * * 4 0 3   F o r b i d d e n : * *   L a c k s   v a l i d   n e t w o r k   c o n t e x t   ( n o t   i n   o f f i c e ,   n o   W F H ) . 
  
 