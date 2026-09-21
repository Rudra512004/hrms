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

  "personal_email": "alice.personal@gmail.com",

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

  "onboarding_email_status": "sent",

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



---



## 8. Attendance APIs



Record and retrieve employee attendance. The attendance API enforces the network access policy (requires Office IP or active WFH) unless the user is a Superadmin.



### List Attendance History



Retrieve the authenticated employee's attendance records.



- **Method:** `GET`

- **Path:** `/api/v1/attendance/`

- **Authentication Requirement:** Token

- **Authorization Requirement:** `IsNetworkAllowed` enforces Office IP or WFH.



**Successful Response (200 OK):**

```json

[

  {

    "id": 1,

    "employee": 1,

    "date": "2023-11-05",

    "check_in": "2023-11-05T09:00:00Z",

    "check_out": "2023-11-05T17:00:00Z",

    "status": "present"

  }

]

```



### Check-in



Record the start of the workday. Allowed exactly once per employee per day.



- **Method:** `POST`

- **Path:** `/api/v1/attendance/check-in/`

- **Authentication Requirement:** Token

- **Authorization Requirement:** `IsNetworkAllowed` enforces Office IP or WFH.



**Successful Response (201 Created):**

```json

{

  "id": 1,

  "employee": 1,

  "date": "2023-11-05",

  "check_in": "2023-11-05T09:00:00Z",

  "check_out": null,

  "status": "present"

}

```



**Validation Errors (400 Bad Request):**

- Duplicate check-in for the day: `{"detail": "Check-in already exists for today."}`



**Authorization Errors:**

- **403 Forbidden:** Lacks valid network context (not in office, no WFH).



### Check-out



Record the end of the workday. Must follow a valid check-in for the current day. Allowed exactly once per employee per day.



- **Method:** `POST`

- **Path:** `/api/v1/attendance/check-out/`

- **Authentication Requirement:** Token

- **Authorization Requirement:** `IsNetworkAllowed` enforces Office IP or WFH.



**Successful Response (200 OK):**

```json

{

  "id": 1,

  "employee": 1,

  "date": "2023-11-05",

  "check_in": "2023-11-05T09:00:00Z",

  "check_out": "2023-11-05T17:00:00Z",

  "status": "present"

}

```



**Validation Errors (400 Bad Request):**

- No check-in for today: `{"detail": "Cannot check out without a check-in."}`

- Already checked out: `{"detail": "Already checked out for today."}`



**Authorization Errors:**

- **403 Forbidden:** Lacks valid network context (not in office, no WFH).







---



## 9. Leave Management APIs



Manage leave types, balances, and requests. Leave operations are NOT blocked by OfficeNetwork policy, meaning employees can request leaves from any network (subject to normal authentication and RBAC).



### Leave Types



- **Method:** `GET`

- **Path:** `/api/v1/leaves/types/`

- **Authentication Requirement:** Token

- **Authorization Requirement:** Must be authenticated.



**Successful Response (200 OK):**

```json

[

  {

    "id": 1,

    "organization": 1,

    "name": "Sick Leave",

    "description": "Medical leave",

    "annual_allocation": 10,

    "is_active": true

  }

]

```



### Leave Balances



- **Method:** `GET`

- **Path:** `/api/v1/leaves/balances/`

- **Authentication Requirement:** Token

- **Authorization Requirement:** Inherently scopes to `request.user.employee`.



**Successful Response (200 OK):**

```json

[

  {

    "id": 1,

    "employee": 1,

    "leave_type": 1,

    "leave_type_name": "Sick Leave",

    "allocated": 10,

    "used": 2,

    "remaining": 8

  }

]

```



### Leave Requests



- **Method:** `GET` / `POST`

- **Path:** `/api/v1/leaves/requests/`

- **Authentication Requirement:** Token

- **Authorization Requirement (GET):** Employees inherently see their own requests. Users with `leave.view` see all.

- **Authorization Requirement (POST):** Requires `leave.request` permission.



**POST Request Body:**

```json

{

  "leave_type": 1,

  "start_date": "2023-12-01",

  "end_date": "2023-12-05",

  "reason": "Vacation"

}

```



**Successful Response (201 Created):**

```json

{

  "id": 1,

  "employee": 1,

  "leave_type": 1,

  "leave_type_name": "Sick Leave",

  "start_date": "2023-12-01",

  "end_date": "2023-12-05",

  "reason": "Vacation",

  "status": "pending",

  "duration_days": 5

}

```



**Validation Errors (400 Bad Request):**

- End date before start date: `{"end_date": ["End date must be after start date."]}`



### Approve / Reject Leave Request



- **Method:** `POST`

- **Path:** `/api/v1/leaves/requests/<id>/approve/` or `/api/v1/leaves/requests/<id>/reject/`

- **Authentication Requirement:** Token

- **Authorization Requirement:** `leave.approve` or `leave.reject`. An employee cannot approve their own request.



**State Transition Errors (400 Bad Request):**

- Insufficient balance (Approval): `{"detail": "Insufficient leave balance."}`

- Invalid transition: `{"detail": "Only pending requests can be approved."}`

- Self-approval attempt (403): `{"detail": "Cannot approve own request."}`



### Cancel Leave Request



- **Method:** `POST`

- **Path:** `/api/v1/leaves/requests/<id>/cancel/`

- **Authentication Requirement:** Token

- **Authorization Requirement:** Must own the request or hold `leave.cancel`. Request must be `pending`.







---



## 10. Control Plane APIs



Manage employees, roles, permissions, and access revocation.



### Employee Management



Manage employee provisioning, listing, activation, and deactivation.



- **Method:** `GET` / `POST` / `PATCH`

- **Path:** `/api/v1/employees/management/`

- **Authentication Requirement:** Token

- **Authorization Requirement:** `employee.view`, `employee.create`, `employee.update`, `employee.status`



**Activate Employee:**

- **Method:** `POST`

- **Path:** `/api/v1/employees/management/<id>/activate/`



**Deactivate Employee:**

- **Method:** `POST`

- **Path:** `/api/v1/employees/management/<id>/deactivate/`

- **Protection:** Users cannot deactivate themselves. Non-superadmins cannot deactivate superadmins.



### Role Management



Assign and revoke roles.



- **Method:** `GET` / `POST`

- **Path:** `/api/v1/authorization/user-roles/`

- **Authentication Requirement:** Token

- **Authorization Requirement:** `role.view`, `role.assign`



**POST Request Body:**

```json

{

  "user": 2,

  "role": 1

}

```



**Revoke Role:**

- **Method:** `POST`

- **Path:** `/api/v1/authorization/user-roles/<id>/revoke/`

- **Authorization Requirement:** `role.revoke`

- **Protection:** Superadmin roles can only be revoked by Superadmins.



### Permission Management



Grant and revoke specific direct permissions.



- **Method:** `GET` / `POST`

- **Path:** `/api/v1/authorization/user-permissions/`

- **Authentication Requirement:** Token

- **Authorization Requirement:** `permission.view`, `permission.assign`



**POST Request Body:**

```json

{

  "user": 2,

  "permission": 5

}

```



**Revoke Permission:**

- **Method:** `POST`

- **Path:** `/api/v1/authorization/user-permissions/<id>/revoke/`

- **Authorization Requirement:** `permission.revoke`

- **Protection:** Superadmin permissions can only be revoked by Superadmins.



### Effective Permissions



View all effective permissions calculated for the authenticated user.



- **Method:** `GET`

- **Path:** `/api/v1/authorization/permissions/my_permissions/`

- **Authentication Requirement:** Token

- **Response:** `["employee.view", "role.assign"]`







---



## 11. Audit Logs



View audit logs of administrative and employee actions.



### List Audit Logs



- **Method:** GET

- **Path:** /api/v1/audit-logs/

- **Authentication Requirement:** Token

- **Authorization Requirement:** udit.view



**Query Parameters (Optional):**

- ctor: Filter by actor's email.

- ction: Filter by action (e.g., employee_created).

- 	arget: Filter by target ID.



**Successful Response (200 OK):**

\\json

[

    {

        "id": 1,

        "actor": 1,

        "actor_email": "admin@company.com",

        "action": "employee_created",

        "target_type": "employee",

        "target_id": "2",

        "timestamp": "2023-11-05T10:00:00Z",

        "metadata": {},

        "ip_address": "127.0.0.1"

    }

]

\

**Authorization Errors:**

- **401 Unauthorized:** Missing token.

- **403 Forbidden:** Lacks \udit.view\ permission.



---



## 12. Admin Leave Type Configuration



Manage leave types for the organization.



### List / Create Leave Types (Admin)



- **Method:** `GET` / `POST`

- **Path:** `/api/v1/leaves/admin/types/`

- **Authentication Requirement:** Token

- **Authorization Requirement:** `leave_type.manage`



**POST Request Body:**

```json

{

  "name": "Sick Leave",

  "description": "Medical leave",

  "annual_allocation": 10,

  "is_active": true

}

```



**Successful Response (201 Created):**

```json

{

  "id": 1,

  "organization": 1,

  "name": "Sick Leave",

  "description": "Medical leave",

  "annual_allocation": 10,

  "is_active": true

}

```



**Validation Errors (400 Bad Request):**

- Duplicate Name: `{"name": ["A leave type with this name already exists."]}`

- Invalid allocation: `{"annual_allocation": ["Ensure this value is greater than or equal to 0."]}`



### Retrieve / Update / Delete Leave Type (Admin)



- **Method:** `GET` / `PUT` / `PATCH` / `DELETE`

- **Path:** `/api/v1/leaves/admin/types/<id>/`

- **Authentication Requirement:** Token

- **Authorization Requirement:** `leave_type.manage`



**Delete Protection (409 Conflict):**

- Cannot delete if assigned to an employee or request: `{"detail": "Cannot delete leave type that is in use by balances or requests."}`
## 13. Employee Management APIs

The Employee Management APIs provide full CRUD and lifecycle management capabilities over employees for authorized users (HR, Branch Admins, Team Managers).

### List Employees
- **Method:** `GET`
- **Path:** `/api/v1/employees/management/`
- **Authentication:** Required (Token)
- **Authorization:** `employee.view`
- **Scope Behavior:** Natively bounded by dynamic RBAC. Returns only employees within the requester's authorized scope (Org/Branch/Team).
- **Query Parameters Supported:** Handled via DRF standard mechanisms if any (e.g. `?search=`, `?status=`, `?branch_id=`).
- **Response Serializer:** `EmployeeSerializer`
- **Pagination:** Uses standard project pagination (`count`, `next`, `previous`, `results`).

### Retrieve Employee Detail
- **Method:** `GET`
- **Path:** `/api/v1/employees/management/{id}/`
- **Authentication:** Required (Token)
- **Authorization:** `employee.view`
- **Scope Behavior:** Bounded by scope. IDOR protection prevents retrieving an employee outside authorized boundaries.
- **Response:** `EmployeeSerializer` representation.

### Create (Provision) Employee
- **Method:** `POST`
- **Path:** `/api/v1/employees/management/`
- **Authentication:** Required (Token)
- **Authorization:** `employee.create`
- **Hierarchy Derivation:** If `team` is provided, `department` and `branch` are implicitly derived from it. If `department` is provided without `team`, `branch` is derived from it.
- **Hierarchy Restrictions:** Payload must not contain contradictory hierarchies (e.g., `team` belonging to a different `branch` than explicitly provided). All entities must belong to the same `organization`.
- **Reporting Manager Validation:** The assigned reporting manager must be `active` and belong to the same organization.
- **Scope Restrictions:** You can only provision an employee into an explicitly authorized destination (Branch or Team) according to your `employee.create` scope.

### Update Employee
- **Method:** `PATCH` or `PUT`
- **Path:** `/api/v1/employees/management/{id}/`
- **Authentication:** Required (Token)
- **Authorization:** `employee.update`
- **Scope Behavior:** Source IDOR strictly enforces that you can only update employees you are authorized to manage.
- **Hierarchy Restrictions:** General employee updates CANNOT modify `branch` or `department` (transfers require the dedicated lifecycle endpoint). `team` reassignment is allowed *only* if the new team remains within the *exact same* department.
- **Reporting Manager Validation:** Same as creation.

### Delete Employee
- **Method:** `DELETE`
- **Path:** `/api/v1/employees/management/{id}/`
- **Behavior:** Explicitly disabled. Returns `HTTP 405 Method Not Allowed`. Employee records are never hard-deleted to preserve HR/payroll history. Use lifecycle actions (e.g., `exit`, `deactivate`) instead.

---

## 14. Employee Lifecycle Actions

These are highly restricted RPC-style endpoints for modifying employee states and generating `EmployeeLifecycleEvent` audit trails.

### Activate / Deactivate
- **Method:** `POST`
- **Path:** `/api/v1/employees/management/{id}/activate/` and `/api/v1/employees/management/{id}/deactivate/`
- **Authorization:** `employee.status`
- **Behavior:** Toggles user login capabilities without altering formal employment status.

### Change Employment Status
- **Method:** `POST`
- **Path:** `/api/v1/employees/management/{id}/change_employment_status/`
- **Authorization:** `employee.manage_status` (or Super Admin)
- **Behavior:** Updates formal `employment_status`.

### Transfer Employee
- **Method:** `POST`
- **Path:** `/api/v1/employees/management/{id}/transfer/`
- **Authorization:** `employee.transfer` ONLY. (`employee.update` is explicitly NOT accepted).
- **Scope Behavior (Source):** Must have `employee.transfer` access to the employee's *current* location.
- **Scope Behavior (Destination):** Must have `employee.transfer` access to the *target* location (Branch/Team). Cross-branch transfers will nullify conflicting department/team values automatically.
- **Payload:** Requires at least one of `branch`, `department`, or `team`.
- **Event:** Generates `EmployeeLifecycleEvent` (type: `transfer`).

### Promote Employee
- **Method:** `POST`
- **Path:** `/api/v1/employees/management/{id}/promote/`
- **Authorization:** `employee.promote` ONLY. (`employee.update` is explicitly NOT accepted).
- **Scope Behavior:** Must have `employee.promote` access to the employee's current location.
- **Event:** Generates `EmployeeLifecycleEvent` (type: `promotion`).

### Exit Employee
- **Method:** `POST`
- **Path:** `/api/v1/employees/management/{id}/exit/`
- **Authorization:** `employee.exit`
- **Behavior:** Processes formal offboarding (resignation/termination date, disables login, marks `exited`).
- **Event:** Generates `EmployeeLifecycleEvent` (type: `exit`).

### Reactivate Employee
- **Method:** `POST`
- **Path:** `/api/v1/employees/management/{id}/reactivate/`
- **Authorization:** `employee.manage_status` (or Super Admin)
- **Behavior:** Reinstates an exited/inactive employee back to `active`.

---

## 15. Organizational Selectors

These endpoints expose dropdown/selector data for the frontend. They strictly filter data based on dynamic RBAC scopes. They never expose unauthorized records.

### Branches
- **Method:** `GET`
- **Path:** `/api/v1/organization/branches/`
- **Authorization:** `branch.view` or `branch.manage`
- **Scope Behavior:** Retrieves exactly the branches the user is authorized to view via `AuthorizationService`.
- **Response:** List of `BranchSerializer` objects.

### Departments
- **Method:** `GET`
- **Path:** `/api/v1/organization/departments/`
- **Authorization:** `department.view` or `department.manage`
- **Query Parameters:** `?branch=<id>` (Acts as a cascade filter on already-authorized data).
- **Scope Behavior:** Safely bounded by `AuthorizationService.get_authorized_branches()`. A Branch Admin sees only their branch's departments.
- **Note:** Standard Employees have `department.view` at the ORGANIZATION level, intentionally allowing them to view the entire organization's department structure.

### Teams
- **Method:** `GET`
- **Path:** `/api/v1/organization/teams/`
- **Authorization:** `team.view` or `team.manage`
- **Query Parameters:** `?department=<id>` (Acts as a cascade filter on already-authorized data).
- **Scope Behavior:** Safely bounded by `AuthorizationService.get_authorized_teams()`. A Team Admin sees ONLY their explicitly assigned team; it does not broaden to sibling teams in the same department.

---

## 16. Dynamic RBAC Scope Contracts

The system utilizes three rigid scopes for resolving data visibility:
- **ORGANIZATION:** Grants visibility/mutation access across the entire organization.
- **BRANCH:** Grants access to the specific Branch and its direct descendants (Departments and Teams). It NEVER expands outward or upward.
- **TEAM:** Grants access strictly to the assigned Team. It NEVER grants access to sibling teams, parent departments, or the branch.

Super Admin: Superusers automatically bypass RBAC capability checks and scope filters.

---

## 17. Common Error Contract
The backend enforces these consistent HTTP error semantics:
- **400 Bad Request:** Validation failure. The payload usually contains a dict of fields and array of string errors (e.g., `{"team": ["Cannot transfer to an inactive team."]}`).
- **401 Unauthorized:** Invalid, expired, or missing authentication token.
- **403 Forbidden:** The authenticated user lacks the required explicit Permission (e.g. `employee.transfer`) OR lacks the required Scope for the target resource.
- **404 Not Found:** The resource does not exist OR the user is completely outside the authorized IDOR scope to perceive it.
- **405 Method Not Allowed:** The HTTP verb is deliberately blocked (e.g., `DELETE` on Employee Management).

---

## 18. Frontend Integration Notes

**Selector Cascade Dependency:**
To build forms (like provisioning or transfer), the frontend MUST cascade its queries in this exact sequence:
1. Fetch Branches (`GET /api/v1/organization/branches/`)
2. Fetch Departments for selected branch (`GET /api/v1/organization/departments/?branch=<id>`)
3. Fetch Teams for selected department (`GET /api/v1/organization/teams/?department=<id>`)

**Payload Optimization:**
When provisioning or transferring, the backend auto-derives parent hierarchy if a child is sent. Sending only `team` is sufficient for the backend to resolve `department` and `branch`. If you send all three, they MUST logically match the database hierarchy, or a `400` validation error will be triggered.
