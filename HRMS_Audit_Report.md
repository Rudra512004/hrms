# 1. Repository / Git State

**Repository Location:** `d:\hrms\hrms`
**Remote URL:** `https://github.com/Rudra512004/hrms.git`
**Current Branch:** `dev2` (clean working tree)

**Branch Analysis:**
* **`main`:** Contains base functionality, user authentication, and early module scaffolds.
* **`dev1`:** Branched from `main`. Contains backend implementations for advanced attendance features (break tracking, work duration calculations), new database fields/models, and some frontend layout/CSS changes.
* **`dev2`:** Branched from `dev1` (or merged `dev1` into it). Contains everything in `dev1`, plus extensive frontend UI work specifically for `AttendancePage.tsx`, `DashboardPage.tsx`, and `services/attendance.ts`. 

**Divergence Summary:**
* `dev1` is `main` + backend attendance logic + minor UI updates.
* `dev2` is `dev1` + complete frontend UI implementation for attendance tracking.

---

# 2. Compare Dev1 vs Dev2 vs Main

| Area | main | dev1 | dev2 | Difference |
| :--- | :--- | :--- | :--- | :--- |
| **Backend** | Base setup, Auth, RBAC models | Adds Attendance breaks & logic | Same as dev1 | `dev1` added deep attendance logic. |
| **Database** | Base schema | Attendance migrations added | Same as dev1 | Schema updated in `dev1`. |
| **Authentication** | JWT, User Models | Same | Same | No difference. |
| **RBAC** | Dynamic permissions model | Same | Same | No difference. |
| **APIs** | Base endpoints | Attendance break endpoints added | Same as dev1 | `dev1` added `start-break`/`end-break`. |
| **Frontend** | Scaffolding | CSS & Dashboard skeleton | Full Attendance UI | `dev2` built out the full UI over `dev1` APIs. |
| **Dashboard** | Basic | Refactored | Fully integrated | `dev2` connected Dashboard to attendance state. |
| **Employees** | Basic CRUD | Same | Same | No difference. |
| **Attendance** | Basic check in/out | Backend logic for breaks | Full UI for breaks | `dev1` built backend, `dev2` built frontend. |
| **Leave** | Basic requests | Same | Same | No difference. |
| **Other modules** | Empty Payroll/Notify | Same | Same | Placeholders only. |

---

# 3. Project Structure

The project is structured into two main directories:
* **Backend (`d:\hrms\hrms\backend`):** Django 4.x project using Django Rest Framework. Apps include `accounts`, `attendance`, `audit`, `authorization`, `employees`, `leaves`, `notifications`, `organization`, and `payroll`.
* **Frontend (`d:\hrms\hrms\frontend`):** React + Vite + TypeScript application using Tailwind-like custom CSS tokens.
* **Infrastructure:** A `docker-compose.yml` exists at the root, currently only containing a `postgres:15` service.

---

# 4. DEV1 BACKEND AUDIT

**Authentication:**
* **Email registration:** `IMPLEMENTED` (via Employee Provisioning)
* **Email/password login:** `IMPLEMENTED` (JWT based)
* **Google/Gmail OAuth:** `PARTIAL` (`google_subject_id` field exists on User, but no OAuth endpoints found)
* **Email verification / Account activation:** `IMPLEMENTED` (Tokens sent via email)
* **Password reset:** `IMPLEMENTED`
* **Logout:** `UNKNOWN` (Stateless JWT implies client-side deletion, backend token blacklisting not explicitly seen)
* **Current-user/profile:** `IMPLEMENTED` (`EmployeeSelfServiceView`)

**Dynamic RBAC:**
* **User/Role/Permission Models:** `IMPLEMENTED` (`apps/authorization/models.py`)
* **Dynamic assignment:** `IMPLEMENTED` 
* **Backend permission enforcement:** `IMPLEMENTED` (e.g., `require_permission('leave.approve')` in views)
* **Hardcoded logic found:** `DashboardPage.tsx` relies on `user.isStaff` and `user.isSuperuser` rather than dynamic permissions.

**APIs (Key Endpoints):**
* `POST /api/v1/attendance/start-break/`: Functional, requires auth, logs breaks.
* `POST /api/v1/attendance/end-break/`: Functional, calculates durations.
* `GET /api/v1/leaves/types/`: `BROKEN / PARTIAL` (See Database Audit below).

---

# 5. DATABASE AUDIT

* **Models/Tables:** Exist for Users, Roles, Permissions, Employees, LeaveRequests, LeaveTypes, Attendance, WFHRequests, Organizations, and OfficeNetworks.
* **Relationships:** Well-defined Foreign Keys (e.g., `Employee` -> `User`, `LeaveRequest` -> `LeaveType`). 
* **Empty Apps:** `payroll` and `notifications` models are completely empty (`0 bytes`).
* **Migrations:** Cannot be fully validated as applied because the Postgres Docker container is currently offline, but the migration files exist.

**Leave Types Investigation (`GET /api/v1/leaves/types/`):**
* Code in `LeaveTypeViewSet` filters by `LeaveType.objects.filter(is_active=True)`.
* **Why it returns an empty list:** There is no automated seed data, fixture, or default data migration for Leave Types. The list is empty simply because the database tables are empty and an administrator has not manually created any `LeaveType` records via the Admin API.

---

# 6. DEV2 FRONTEND AUDIT

**Routing (`AppRouter.tsx`):**
* **Public:** `/login`, `/forgot-password`, `/reset-password`, `/pending-activation`
* **Protected:** `/dashboard`, `/attendance`, `/leaves`, `/profile`
* **Admin (Protected):** `/admin`, `/admin/employees`, `/admin/office-networks`, `/admin/wfh`, `/admin/leaves`, `/admin/leave-types`, `/admin/audit-logs`

**UI / Application Shell:**
* **Auth UI:** Login, Forgot Password, Reset Password, Activation are implemented.
* **Dashboard:** Implemented with real-time API integrations for attendance states.
* **Attendance:** UI is fully implemented with real-time break timers integrated with backend endpoints.
* **RBAC:** `utils/permissions.ts` contains a mocked function `hasPermission()` that currently hardcodes `return true;`.

---

# 7. FRONTEND ↔ BACKEND INTEGRATION

* **Authentication Mismatch:** None critical detected. JWT tokens are correctly attached to `Bearer`/`Token` headers via `services/*.ts`.
* **Authorization Mismatch:** **HIGH RISK**. Backend strictly enforces dynamic RBAC via `AuthorizationService`. Frontend bypasses this by using a hardcoded `hasPermission` mock and checking `user.isStaff` / `user.isSuperuser` to render UI elements.
* **Missing Backend:** Frontend has admin routes (e.g., `/admin/office-networks`) but the organization APIs are barebones.

---

# 8. DOCKER / INFRASTRUCTURE

* **Services:** Only `db` (Postgres 15) is present in `docker-compose.yml`.
* **Mailpit:** **DOES NOT EXIST.** The `docker-compose.yml` does not contain a Mailpit service. Email relies entirely on Django's SMTP settings.

---

# 9. TESTING / BUILD STATUS

* **Backend Tests:** `apps/attendance/tests.py` exists and is highly comprehensive (tests IP spoofing, breaks, duplicate checkouts, IDOR). Django commands could not be run because the database is offline and virtual environment wasn't active initially.
* **Frontend Build:** `npm run lint` passes successfully (0 errors, 0 warnings).

---

# 10. SECURITY AUDIT

* **Hardcoded Roles:** Frontend uses `isStaff` / `isSuperuser` for UI visibility.
* **IDOR:** Mitigated on backend. Attendance and Leave views restrict querysets strictly to `user.employee`.
* **Network Restrictions:** `IsNetworkAllowed` permission class explicitly checks IP addresses for office-only actions. Highly secure.
* **Secrets:** None hardcoded in inspected files, relying correctly on `.env` (a `.env.example` exists).

---

# 11. Compare Against OUR NEW RESEARCHED HRMS SCOPE

| Feature | Dev1 (Backend) | Dev2 (Frontend) |
| :--- | :--- | :--- |
| 1. Authentication | ✅ Implemented | ✅ Implemented |
| 2. Dynamic RBAC | ✅ Implemented | 🔵 Frontend only (Mocked) |
| 3. User management | ✅ Implemented | ✅ Implemented |
| 4. Org/company settings | 🟡 Partial | ❌ Not implemented |
| 5. Departments | ❌ Not implemented | ❌ Not implemented |
| 6. Designations | ❌ Not implemented | ❌ Not implemented |
| 7. Reporting hierarchy | ❌ Not implemented | ❌ Not implemented |
| 8. Employee management | ✅ Implemented | ✅ Implemented |
| 9. Employee onboarding | ✅ Implemented | ✅ Implemented |
| 10. Employee documents | ❌ Not implemented | ❌ Not implemented |
| 11. Attendance | ✅ Implemented | ✅ Implemented |
| 12. Leave management | ✅ Implemented | ✅ Implemented |
| 13. Leave policies | ✅ Implemented | 🟡 Partial |
| 14. Holiday calendar | ❌ Not implemented | ❌ Not implemented |
| 15. Approval workflows | ✅ Implemented | 🟡 Partial |
| 16. Payroll | 🟣 Backend only (Empty App) | ❌ Not implemented |
| 17. Recruitment | ❌ Not implemented | ❌ Not implemented |
| 18. Performance | ❌ Not implemented | ❌ Not implemented |
| 19. Expenses | ❌ Not implemented | ❌ Not implemented |
| 20. Assets | ❌ Not implemented | ❌ Not implemented |
| 21. Notifications | 🟣 Backend only (Email) | ❌ Not implemented |
| 22. Calendar | ❌ Not implemented | ❌ Not implemented |
| 23. Dashboards | 🟣 Backend only (APIs) | ✅ Implemented |
| 24. Reports/analytics | ❌ Not implemented | ❌ Not implemented |
| 25. Audit logs | ✅ Implemented | 🟡 Partial (UI Route exists) |
| 26. Security/testing | ✅ Implemented | ✅ Implemented |
| 27. Advanced UI/UX | ❌ N/A | ✅ Implemented |

---

# 12. Critical Conflict Detection

* **CRITICAL:** Frontend RBAC is mocked. The backend has a robust role/permission system, but the frontend hardcodes `hasPermission` to `return true` and relies on `user.isStaff`/`user.isSuperuser`. If the backend denies a request that the frontend allows visually, users will experience constant HTTP 403 errors.
* **MEDIUM:** The `LeaveType` model cannot be assigned to an Organization because the `Employee` model lacks a relationship to `Organization`. The code explicitly contains a comment: `ARCHITECTURAL LIMITATION: Employee model does not have an organization relationship.`

---

# 13. FINAL CONSOLIDATED REPORT

## A. CURRENT PROJECT STATE
The repository is functionally split across branches. `dev1` has successfully implemented advanced backend attendance capabilities and database schema updates, while `dev2` has built the corresponding frontend UI. The project possesses a robust foundation but is missing massive chunks of the standard HRMS scope (Payroll, Recruitment, Performance, Departments).

## B. DEV1 STATUS
Has successfully built the backend architecture for attendance tracking (including network constraints and breaks), leave management, dynamic RBAC, and robust automated testing.

## C. DEV2 STATUS
Has successfully consumed Dev1's attendance and auth APIs to build a modern, responsive frontend Dashboard and Attendance tracker. 

## D. MAIN STATUS
Stable, but out of date. It lacks the advanced attendance functionality present in `dev1` and `dev2`.

## E. COMPLETED
JWT Authentication, Employee Provisioning (Basic), Check-in/Check-out/Breaks, IP-restricted actions, Leave Requests (Basic).

## F. PARTIAL / BROKEN
Frontend RBAC (mocked), Organization architecture (lacks link to employees), Leave Types (no seed data, endpoint returns empty).

## G. NOT IMPLEMENTED
Payroll, Departments, Designations, Documents, Recruitment, Performance, Expenses, Assets, Calendar, Mailpit Infrastructure.

## H. CRITICAL RISKS
1. The frontend's mocked RBAC will cause user experience failures when interacting with secured backend APIs.
2. The Database lacks baseline seed data (Leave Types, Default Roles), causing empty UI states.

## I. DEV1 NEXT TASKS
1. Create a database seeder/fixture for `LeaveType`, `Role`, and `Permission`.
2. Fix the architectural limitation by linking `Employee` to `Organization` or `Department`.
3. Expose a `/api/v1/authorization/me/` endpoint returning a user's exact permission array.

## J. DEV2 NEXT TASKS
1. Update `utils/permissions.ts` to fetch and store the actual permission array from the backend.
2. Replace all `user.isStaff` and `user.isSuperuser` checks with `hasPermission('permission.codename')`.

## K. DEV1 → DEV2 DEPENDENCIES
Dev1 must provide a dedicated API endpoint that returns the current user's granted permissions so Dev2 can un-mock the frontend RBAC.

## L. DEV2 → DEV1 DEPENDENCIES
Dev2 requires Dev1 to seed the database with `LeaveType` objects so the Leave UI can function correctly.

## M. RECOMMENDED IMMEDIATE NEXT STEP
Merge `dev1` and `dev2` to synchronize frontend and backend states, then immediately seed the database with base `LeaveType` and `Role` data to make the existing UI functional.

---

# 14. FINAL STATUS TABLE

| Module | main | dev1 | dev2 | Integration Status | Main Gap |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Authentication | ✅ | ✅ | ✅ | Integrated | None |
| RBAC | 🟣 | 🟣 | 🔵 | Conflict (Mocked UI) | Needs API Endpoint |
| Users | ✅ | ✅ | ✅ | Integrated | None |
| Organization | 🟣 | 🟣 | ❌ | Backend Only | UI Missing |
| Departments | ❌ | ❌ | ❌ | Not Started | Full Module |
| Designations | ❌ | ❌ | ❌ | Not Started | Full Module |
| Employees | 🟡 | 🟡 | 🟡 | Partial (No Org Link) | Architectural Fix |
| Attendance | 🟡 | ✅ | ✅ | Integrated | None |
| Leave | 🟡 | 🟡 | 🟡 | Blocked (No Data) | Database Seed |
| Payroll | ❌ | ❌ | ❌ | Not Started | Full Module |
| Recruitment | ❌ | ❌ | ❌ | Not Started | Full Module |
| Performance | ❌ | ❌ | ❌ | Not Started | Full Module |
| Expenses | ❌ | ❌ | ❌ | Not Started | Full Module |
| Assets | ❌ | ❌ | ❌ | Not Started | Full Module |
| Documents | ❌ | ❌ | ❌ | Not Started | Full Module |
| Notifications | 🟣 | 🟣 | ❌ | Emails sent, No UI | UI Missing |
| Calendar | ❌ | ❌ | ❌ | Not Started | Full Module |
| Dashboard | 🟡 | 🟡 | ✅ | Integrated | None |
| Reports | ❌ | ❌ | ❌ | Not Started | Full Module |
| Audit Logs | 🟣 | 🟣 | 🔵 | Backend Only | UI Route Empty |
| Docker/Database | 🟡 | 🟡 | 🟡 | Postgres Only | Missing Mailpit |
| Testing | 🟡 | ✅ | ✅ | Integrated | End-to-End Tests |
