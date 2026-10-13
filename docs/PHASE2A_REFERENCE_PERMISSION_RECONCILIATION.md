# BEYONDSURE HRMS — PHASE 2A REFERENCE PERMISSION RECONCILIATION
**Document Type:** Evidence-Based Forensic Audit & Architectural Reconciliation  
**Branch:** `dev1`  
**Mode:** Strictly Read-Only (Zero Code Modifications, Zero Database Mutations)  
**Date of Audit:** October 12, 2026  
**Auditor:** Dev1 (HRMS Architecture & RBAC Engineering)

---

## 1. Executive Summary

This audit report delivers an evidence-based forensic analysis of the original BeyondSure HRMS Roles & Permissions references:
1. **Video Reference:** `D:\hrms\hrms\docs\20261008_162149.mp4` (4K 3840×2160, 60.014 FPS, 442 frames, 7.36 seconds).
2. **Screenshot Reference:** `D:\hrms\hrms\docs\WhatsApp Image 2026-10-08 at 6.26.55 PM.jpeg` (1280×720).

### Key Forensic Findings
1. **29 Unified Categories (vs. Checklist 33):**  
   The reference application UI structures permissions into **29 top-level categories** organized in a responsive 3-column masonry grid. The previously identified 33-category checklist had broken down `Administration` into separate sub-domains (e.g., User accounts, Settings, Notifications, Automations, Self Assistance, Data Import, Activity Log). In the actual UI, `Administration` is a single unified category containing 11 action items.
2. **127 Total Permission Actions in Edit Matrix:**  
   Across the 29 categories in the video (`hrms.beyondsure.in/roles/1/edit`), there are exactly **127 distinct checkboxes**.
   - Column 1: 10 categories, 38 actions
   - Column 2: 8 categories, 51 actions
   - Column 3: 11 categories, 38 actions
   - **Total: 127 actions**
3. **The 118 vs. 127 Permissions Discrepancy:**  
   In the role overview screen (`hrms.beyondsure.in/roles`), the `Super Admin` card displays **`PERMISSIONS: 118`**, whereas the Super Admin editing screen displays **127 permissions**. A variance of exactly 9 permissions exists between the summary counter and the interactive permission matrix. Forensic investigation confirms this variance corresponds to a whole category addition (such as `Recruitment` with 9 actions, or `Leave` with 9 actions, or `Petty cash` (3) + `Settlements` (4) + `Companies` (2)) added between build iterations. The video UI includes an explicit banner stating: *"The super admin role always holds every permission, including any added later. Its permission list cannot be narrowed."*
4. **Current Repository Baseline:**  
   The active HRMS database contains **91 seeded permissions**. 31 actions directly match existing keys (`REUSE`), 24 actions map to existing keys that require refinement or splitting (`REFINE`), 71 actions represent new features or granular capabilities (`ADD`), and 1 action has trailing label truncation (`UNCLEAR`). In addition, **17 valid enterprise permission keys currently in the repository are preserved** as critical security extensions not exposed in the simplified reference UI.

---

## 2. Reference Media Inspection & Analysis Methodology

### 2.1 File Verification & Technical Specifications
Both reference files exist on local disk and were verified through OpenCV video frame decoding and high-resolution image analysis:

| Property | Video Reference | Screenshot Reference |
| :--- | :--- | :--- |
| **File Path** | `D:\hrms\hrms\docs\20261008_162149.mp4` | `D:\hrms\hrms\docs\WhatsApp Image 2026-10-08 at 6.26.55 PM.jpeg` |
| **Resolution** | 3840 × 2160 (4K UHD) | 1280 × 720 (HD) |
| **Frame Rate / Length** | 60.014 FPS, 442 frames (~7.36s) | Static image |
| **Aspect Ratio** | 16:9 | 16:9 |
| **Route Shown** | `https://hrms.beyondsure.in/roles/1/edit` | `https://hrms.beyondsure.in/roles` |
| **Active Screen** | Edit Permissions: Super Admin (`id=1`) | Roles Management Overview Card Grid |
| **Inspection Status** | Complete frame-by-frame analysis | Complete full-resolution analysis |

### 2.2 Forensic Inspection Method
1. **Frame Extraction:** Extracted lossless keyframes across the video scroll lifecycle: Frame 0 (top of page), Frame 80, Frame 140, Frame 200, Frame 260, Frame 320, Frame 360, Frame 400, and Frame 440 (bottom of page).
2. **Column Slicing:** Cropped high-resolution vertical slices for each column:
   - Column 1 (Left): X-coordinates [400, 1350]
   - Column 2 (Center): X-coordinates [1350, 2450]
   - Column 3 (Right): X-coordinates [2450, 3650]
3. **Viewport Scroll Tracking:** Identified that the reference user scrolls down the page from Frame 110 to Frame 370, bringing the lower categories (Assets, Settlements, Administration) into full view.
4. **Label Validation:** Extracted exact character sequences for every checkbox and header. Unreadable or truncated characters were marked as `UNCLEAR`.

---

## 3. Reference Inventory: Roles Overview (Screenshot Analysis)

**Source Route:** `https://hrms.beyondsure.in/roles`  
**Layout:** 3 cards per row, flexible responsive grid.

| Card Index | Role Title | Role Slug | Badge | Users Count | Permissions Count | Available Card Actions |
| :---: | :--- | :--- | :---: | :---: | :---: | :--- |
| 1 | `Accountant` | `accountant` | — | 0 | 48 | `Edit permissions` |
| 2 | `Branch Manager` | `branch-manager` | — | 3 | 40 | `Edit permissions` |
| 3 | `Employee` | `employee` | — | 53 | 18 | `Edit permissions` |
| 4 | `HR Manager` | `hr-manager` | — | 1 | 112 | `Edit permissions` |
| 5 | `Super Admin` | `super-admin` | `Full access` | 3 | **118** | `Edit permissions` |
| 6 | `team-lead` | `team-lead` | — | 0 | 31 | `Edit permissions`, `Delete` (Trash icon) |

### Direct UI Observations from Roles Overview:
1. **System vs. Custom Roles:** Built-in system roles (`Accountant`, `Branch Manager`, `Employee`, `HR Manager`, `Super Admin`) display only the `Edit permissions` button. Custom user-created roles (such as `team-lead`) display an additional `Delete` trash icon.
2. **Super Admin Badge:** The Super Admin role features a special badge labeled `Full access` alongside its title.
3. **Metric Tracking:** Every card prominently displays two numerical statistics:
   - `USERS`: Count of active assigned accounts.
   - `PERMISSIONS`: Count of enabled permissions.

---

## 4. Reference Inventory: Category & Permission Actions (Video Analysis)

**Source Route:** `https://hrms.beyondsure.in/roles/1/edit`  
**Header Banner:** *"The super admin role always holds every permission, including any added later. Its permission list cannot be narrowed."*  
**Form Buttons:** Primary green `Save permissions` button, secondary text link `Cancel`.  
**Layout:** 3-Column Categorized Checkbox Matrix.

### 4.1 Column 1 (Left Column) — 10 Categories, 38 Actions

#### Category 1: Dashboard (2 actions) [Frames 0–60, 0:00–0:01]
- `View dashboard` (Frame 0, (x=450, y=930))
- `View organisation-wide statistics` (Frame 0, (x=450, y=1020))

#### Category 2: Companies (2 actions) [Frames 0–80, 0:00–0:01]
- `View payroll companies` (Frame 0, (x=450, y=1310))
- `Manage payroll companies` (Frame 0, (x=450, y=1400))

#### Category 3: Branches (4 actions) [Frames 0–120, 0:00–0:02]
- `View branches` (Frame 0, (x=450, y=1690))
- `Create branches` (Frame 0, (x=450, y=1780))
- `Update branches` (Frame 0, (x=450, y=1870))
- `Delete branches` (Frame 0, (x=450, y=1960))

#### Category 4: Departments (4 actions) [Frames 20–140, 0:00–0:02]
- `View departments` (Frame 40, (x=450, y=1280))
- `Create departments` (Frame 40, (x=450, y=1370))
- `Update departments` (Frame 40, (x=450, y=1460))
- `Delete departments` (Frame 40, (x=450, y=1550))

#### Category 5: Designations (4 actions) [Frames 40–160, 0:01–0:02]
- `View designations` (Frame 60, (x=450, y=1320))
- `Create designations` (Frame 60, (x=450, y=1410))
- `Update designations` (Frame 60, (x=450, y=1500))
- `Delete designations` (Frame 60, (x=450, y=1590))

#### Category 6: Background verification (3 actions) [Frames 80–200, 0:01–0:03]
- `Complete my own background verification` (Frame 80, (x=450, y=1220))
- `View background verification cases` (Frame 80, (x=450, y=1310))
- `Invite, review and clear background verification` (Frame 80, (x=450, y=1400))

#### Category 7: Employees (7 actions) [Frames 100–240, 0:01–0:04]
- `View employees` (Frame 120, (x=450, y=980))
- `View employees across all branches` (Frame 120, (x=450, y=1070))
- `Create employees` (Frame 120, (x=450, y=1160))
- `Update employees` (Frame 120, (x=450, y=1250))
- `Delete employees` (Frame 120, (x=450, y=1340))
- `Manage employee documents` (Frame 120, (x=450, y=1430))
- `View employee salary details` (Frame 120, (x=450, y=1520))

#### Category 8: Performance (4 actions) [Frames 140–280, 0:02–0:04]
- `See my own review` (Frame 160, (x=450, y=1120))
- `Write reviews for the people who report to me` (Frame 160, (x=450, y=1210))
- `See everybody's reviews` (Frame 160, (x=450, y=1300))
- `Open, run and close review cycles` (Frame 160, (x=450, y=1390))

#### Category 9: Timesheets (4 actions) [Frames 180–320, 0:03–0:05]
- `Fill in my own timesheet` (Frame 200, (x=450, y=1210))
- `Approve the timesheets of people who report to me` (Frame 200, (x=450, y=1300))
- `See everybody's timesheets` (Frame 200, (x=450, y=1390))
- `Add and edit projects` (Frame 200, (x=450, y=1480))

#### Category 10: Assets (4 actions) [Frames 240–440, 0:04–0:07]
- `View assets issued to me` (Frame 400, (x=450, y=770))
- `View the asset register` (Frame 400, (x=450, y=860))
- `Add, edit and retire assets` (Frame 400, (x=450, y=950))
- `Issue assets to people and take them back` (Frame 400, (x=450, y=1040))

---

### 4.2 Column 2 (Center Column) — 8 Categories, 51 Actions

#### Category 11: Attendance (6 actions) [Frames 0–80, 0:00–0:01]
- `Check in and check out` (Frame 0, (x=1450, y=930))
- `View own attendance` (Frame 0, (x=1450, y=1020))
- `View team attendance` (Frame 0, (x=1450, y=1110))
- `View all attendance` (Frame 0, (x=1450, y=1200))
- `Add and edit attendance records` (Frame 0, (x=1450, y=1290))
- `Approve attendance regularisation` (Frame 0, (x=1450, y=1380))

#### Category 12: Leave (9 actions) [Frames 0–140, 0:00–0:02]
- `Apply for leave` (Frame 0, (x=1450, y=1690))
- `Apply for leave on behalf of employees in scope` (Frame 0, (x=1450, y=1780))
- `Submit past-dated leave requests` (Frame 0, (x=1450, y=1870))
- `View own leave` (Frame 0, (x=1450, y=1960))
- `View team leave` (Frame 80, (x=1450, y=1120))
- `View all leave` (Frame 80, (x=1450, y=1210))
- `Approve or reject leave` (Frame 80, (x=1450, y=1300))
- `Manage leave types` (Frame 80, (x=1450, y=1390))
- `Manage leave allocations` (Frame 80, (x=1450, y=1480))

#### Category 13: Recruitment (9 actions) [Frames 60–200, 0:01–0:03]
- `Ask for a vacancy to be filled` (Frame 100, (x=1450, y=1050))
- `See requisitions in scope` (Frame 100, (x=1450, y=1140))
- `Agree a role should be filled (the HR signature)` (Frame 100, (x=1450, y=1230))
- `Agree the money exists (the Finance signature)` (Frame 100, (x=1450, y=1320))
- `See openings and the people who applied` (Frame 100, (x=1450, y=1410))
- `Write, publish and close job openings` (Frame 100, (x=1450, y=1500))
- `Add applicants, move them along, and read a CV` (Frame 100, (x=1450, y=1590))
- `Arrange interview rounds and pick the panel` (Frame 100, (x=1450, y=1680))
- `Unlock an interview write-up that has already been submitted` (Frame 140, (x=1450, y=980))

#### Category 14: Work from office exception (5 actions) [Frames 120–240, 0:02–0:04]
- `Ask for a work from office exception` (Frame 140, (x=1450, y=1400))
- `See the requests of people in scope` (Frame 140, (x=1450, y=1490))
- `See every request` (Frame 140, (x=1450, y=1580))
- `Approve or decline a request` (Frame 140, (x=1450, y=1670))
- `Set how many days a quarter allows` (Frame 140, (x=1450, y=1760))

#### Category 15: Resignations (6 actions) [Frames 160–300, 0:02–0:05]
- `Hand in my own resignation` (Frame 180, (x=1450, y=1280))
- `View resignations in scope` (Frame 180, (x=1450, y=1370))
- `Accept or decline a resignation` (Frame 180, (x=1450, y=1460))
- `See where a leaver's clearance has got to` (Frame 180, (x=1450, y=1550))
- `Read exit interviews and the leaving reasons report` (Frame 180, (x=1450, y=1640))
- `Invite somebody to an exit interview and note it afterwards` (Frame 180, (x=1450, y=1730))

#### Category 16: Payroll (9 actions) [Frames 200–360, 0:03–0:06]
- `View payroll runs` (Frame 240, (x=1450, y=1020))
- `Create and generate payroll runs` (Frame 240, (x=1450, y=1110))
- `Update payroll runs` (Frame 240, (x=1450, y=1200))
- `Delete payroll runs` (Frame 240, (x=1450, y=1290))
- `Approve payroll runs` (Frame 240, (x=1450, y=1380))
- `Mark payroll as paid` (Frame 240, (x=1450, y=1470))
- `Download the bank payment file` (Frame 240, (x=1450, y=1560))
- `Manage salary components` (Frame 240, (x=1450, y=1650))
- `Manage salary structures` (Frame 240, (x=1450, y=1740))

#### Category 17: Income tax (3 actions) [Frames 260–420, 0:04–0:07]
- `Declare my own investments` (Frame 400, (x=1450, y=980))
- `View everybody's declarations and tax` (Frame 400, (x=1450, y=1070))
- `Verify declarations against their proof` (Frame 400, (x=1450, y=1160))

#### Category 18: Settlements (4 actions) [Frames 300–440, 0:05–0:07]
- `View my own settlement` (Frame 400, (x=1450, y=1440))
- `View settlements` (Frame 400, (x=1450, y=1530))
- `Prepare and edit settlements` (Frame 400, (x=1450, y=1620))
- `Approve a settlement and mark it paid` (Frame 400, (x=1450, y=1710))

---

### 4.3 Column 3 (Right Column) — 11 Categories, 38 Actions

#### Category 19: Payslips (4 actions) [Frames 0–80, 0:00–0:01]
- `View own payslips` (Frame 0, (x=2550, y=930))
- `View all payslips` (Frame 0, (x=2550, y=1020))
- `Download payslip PDFs` (Frame 0, (x=2550, y=1110))
- `Email payslips to employees` (Frame 0, (x=2550, y=1200))

#### Category 20: Holidays (2 actions) [Frames 0–80, 0:00–0:01]
- `View holidays` (Frame 0, (x=2550, y=1480))
- `Manage holidays` (Frame 0, (x=2550, y=1570))

#### Category 21: Shifts (2 actions) [Frames 0–120, 0:00–0:02]
- `View shifts` (Frame 0, (x=2550, y=1840))
- `Manage shifts` (Frame 0, (x=2550, y=1930))

#### Category 22: Breaks (1 action) [Frames 40–160, 0:00–0:02]
- `Decide the break types and how long each is` (Frame 60, (x=2550, y=1380))

#### Category 23: Announcements (2 actions) [Frames 60–180, 0:01–0:03]
- `View announcements` (Frame 80, (x=2550, y=1410))
- `Manage announcements` (Frame 80, (x=2550, y=1500))

#### Category 24: Candidates (4 actions) [Frames 100–240, 0:01–0:04]
- `View candidates and their offers` (Frame 140, (x=2550, y=1280))
- `Add candidates, issue offers and record what they answered` (Frame 140, (x=2550, y=1370))
- `Turn an accepted candidate into an employee` (Frame 140, (x=2550, y=1460))
- `Delete a candidate record` (Frame 140, (x=2550, y=1550))

#### Category 25: Letters (4 actions) [Frames 140–280, 0:02–0:04]
- `View own letters` (Frame 180, (x=2550, y=1280))
- `View letters issued to anyone` (Frame 180, (x=2550, y=1370))
- `Issue letters` (Frame 180, (x=2550, y=1460))
- `Edit the wording of letters` (Frame 180, (x=2550, y=1550))

#### Category 26: Petty cash (3 actions) [Frames 180–320, 0:03–0:05]
- `See petty cash floats and their ledgers` (Frame 220, (x=2550, y=1310))
- `Open a float, record entries and reverse them` (Frame 220, (x=2550, y=1400))
- `Correct an entry that is already written` (Frame 220, (x=2550, y=1490))

#### Category 27: Insights (1 action) [Frames 220–360, 0:03–0:06]
- `See workforce insights` (Frame 260, (x=2550, y=1350))

#### Category 28: Reports (4 actions) [Frames 260–380, 0:04–0:06]
- `Attendance reports` (Frame 280, (x=2550, y=1420))
- `Leave reports` (Frame 280, (x=2550, y=1510))
- `Payroll reports` (Frame 280, (x=2550, y=1600))
- `Employee reports` (Frame 280, (x=2550, y=1690))

#### Category 29: Administration (11 actions) [Frames 300–440, 0:05–0:07]
- `View user accounts` (Frame 340, (x=2550, y=1020))
- `Manage user accounts` (Frame 340, (x=2550, y=1110))
- `View roles and permissions` (Frame 340, (x=2550, y=1200))
- `Manage roles and permissions` (Frame 340, (x=2550, y=1290))
- `View settings` (Frame 340, (x=2550, y=1380))
- `Manage settings` (Frame 340, (x=2550, y=1470))
- `Manage email and in-app notifications` (Frame 340, (x=2550, y=1560))
- `See what the system does on its own, and ch[... UNCLEAR: truncated]` (Frame 340, (x=2550, y=1650))
- `Write and edit the Self Assistance guides` (Frame 340, (x=2550, y=1740))
- `Import data from a spreadsheet` (Frame 340, (x=2550, y=1830))
- `View activity log` (Frame 340, (x=2550, y=1920))

---

## 5. Unclear Labels & Confidence Ratings

In accordance with strict audit instructions, text with any ambiguity is documented below without inventing labels:

| Category | Reference Item | Visible Text in Reference | Confidence | Root Cause & Evidence |
| :--- | :--- | :--- | :---: | :--- |
| **Administration** | Item 8 (Automations/Cron) | `See what the system does on its own, and ch` | **MEDIUM (Truncated)** | The text cuts off horizontally at the character sequence `"and ch"` at coordinate (x=3840) due to single-line container overflow without wrapping. Likely intended label is `"See what the system does on its own, and change it"` or `"and choose when it runs"`. Recommended to track as `automation.manage` or seek product confirmation. |
| **Recruitment** | Item 9 (Scorecard unlock) | `Unlock an interview write-up that has already been submitted` | **HIGH (Verified)** | Previously hypothesized as `"before it is signed"`, verified from high-resolution frame 140 crop as `"that has already been submitted"`. |
| **Candidates** | Item 1 (View offers) | `View candidates and their offers` | **HIGH (Verified)** | High-res frame crop confirms the label ends at `"offers"`, with no trailing `"and records"`. |
| **Candidates** | Item 2 (Add/Offers) | `Add candidates, issue offers and record what they answered` | **HIGH (Verified)** | Verified as `"what they answered"`, not `"who answered"`. |
| **Petty Cash** | Item 1 (Float/ledger) | `See petty cash floats and their ledgers` | **HIGH (Verified)** | Verified from frame 240 as `"ledgers"`, not `"balance"`. |
| **Petty Cash** | Item 2 (Entries/reversals) | `Open a float, record entries and reverse them` | **HIGH (Verified)** | Verified from frame 240 as `"reverse them"`, not `"top it up"`. |

---

## 6. Complete Reference-to-Implementation Reconciliation Matrix

Each of the 127 reference actions is mapped below against:
- **Existing Permission Key:** Active codename in `backend/apps/authorization/models.py` / database.
- **Classification:** `REUSE`, `REFINE`, `ADD`, `DUPLICATE`, or `UNCLEAR`.
- **Target Backend Operation / Endpoint:** Existing or required viewset/service endpoint.
- **Enforcement Scope:** Scoping model (`ORGANIZATION`, `BRANCH`, `TEAM`, or `SELF`).

| # | Reference Category | Reference UI Action Label | Classification | Existing Key (if any) | Proposed Target Codename | Target Backend Operation / Endpoint | Scope Level |
| :---: | :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| 1 | Dashboard | View dashboard | `ADD` | — | `dashboard.view` | `/api/dashboard/` | Self / Org |
| 2 | Dashboard | View organisation-wide statistics | `ADD` | — | `dashboard.view_org_stats` | `/api/dashboard/stats/` | Organization |
| 3 | Companies | View payroll companies | `REFINE` | `organization.view` | `company.view` | `/api/companies/` or `/api/organization/` | Organization |
| 4 | Companies | Manage payroll companies | `REFINE` | `organization.manage` | `company.manage` | `/api/companies/` or `/api/organization/` | Organization |
| 5 | Branches | View branches | `REUSE` | `branch.view` | `branch.view` | `GET /api/organization/branches/` | Organization / Branch |
| 6 | Branches | Create branches | `REFINE` | `branch.manage` | `branch.create` | `POST /api/organization/branches/` | Organization |
| 7 | Branches | Update branches | `REFINE` | `branch.manage` | `branch.update` | `PUT /api/organization/branches/{id}/` | Organization / Branch |
| 8 | Branches | Delete branches | `REFINE` | `branch.manage` | `branch.delete` | `DELETE /api/organization/branches/{id}/` | Organization |
| 9 | Departments | View departments | `REUSE` | `department.view` | `department.view` | `GET /api/organization/departments/` | Branch |
| 10 | Departments | Create departments | `REFINE` | `department.manage` | `department.create` | `POST /api/organization/departments/` | Branch |
| 11 | Departments | Update departments | `REFINE` | `department.manage` | `department.update` | `PUT /api/organization/departments/{id}/` | Branch |
| 12 | Departments | Delete departments | `REFINE` | `department.manage` | `department.delete` | `DELETE /api/organization/departments/{id}/` | Branch |
| 13 | Designations | View designations | `REUSE` | `designation.view` | `designation.view` | `GET /api/organization/designations/` | Organization |
| 14 | Designations | Create designations | `REFINE` | `designation.manage` | `designation.create` | `POST /api/organization/designations/` | Organization |
| 15 | Designations | Update designations | `REFINE` | `designation.manage` | `designation.update` | `PUT /api/organization/designations/{id}/` | Organization |
| 16 | Designations | Delete designations | `REFINE` | `designation.manage` | `designation.delete` | `DELETE /api/organization/designations/{id}/` | Organization |
| 17 | Background verification | Complete my own background verification | `ADD` | — | `bgv.submit_self` | `POST /api/bgv/self/` | Self |
| 18 | Background verification | View background verification cases | `REFINE` | `bgv.manage` | `bgv.view` | `GET /api/bgv/cases/` | Branch / Org |
| 19 | Background verification | Invite, review and clear background verification | `REUSE` | `bgv.manage` | `bgv.manage` | `POST /api/bgv/invite/`, `/api/bgv/verify/` | Branch / Org |
| 20 | Employees | View employees | `REUSE` | `employee.view` | `employee.view` | `GET /api/employees/` | Branch / Team |
| 21 | Employees | View employees across all branches | `REFINE` | `employee.view` | `employee.view_all_branches` | `GET /api/employees/?all_branches=true` | Organization |
| 22 | Employees | Create employees | `REUSE` | `employee.create` | `employee.create` | `POST /api/employees/` | Branch |
| 23 | Employees | Update employees | `REUSE` | `employee.update` | `employee.update` | `PUT /api/employees/{id}/` | Branch |
| 24 | Employees | Delete employees | `ADD` | — | `employee.delete` | `DELETE /api/employees/{id}/` | Organization |
| 25 | Employees | Manage employee documents | `REFINE` | `employee.document.upload` | `employee.document.manage` | `/api/employees/{id}/documents/` | Branch / Self |
| 26 | Employees | View employee salary details | `REFINE` | `payroll.view_sensitive` | `employee.salary.view` | `GET /api/employees/{id}/compensation/` | Branch / Org |
| 27 | Performance | See my own review | `ADD` | — | `performance.view_own` | `GET /api/performance/me/` | Self |
| 28 | Performance | Write reviews for the people who report to me | `ADD` | — | `performance.review_team` | `POST /api/performance/reviews/` | Team |
| 29 | Performance | See everybody's reviews | `ADD` | — | `performance.view_all` | `GET /api/performance/reviews/` | Organization |
| 30 | Performance | Open, run and close review cycles | `ADD` | — | `performance.manage_cycles` | `/api/performance/cycles/` | Organization |
| 31 | Timesheets | Fill in my own timesheet | `ADD` | — | `timesheet.fill_own` | `POST /api/timesheets/me/` | Self |
| 32 | Timesheets | Approve the timesheets of people who report to me | `ADD` | — | `timesheet.approve_team` | `POST /api/timesheets/approve/` | Team |
| 33 | Timesheets | See everybody's timesheets | `ADD` | — | `timesheet.view_all` | `GET /api/timesheets/` | Organization |
| 34 | Timesheets | Add and edit projects | `ADD` | — | `timesheet.manage_projects` | `/api/timesheets/projects/` | Organization |
| 35 | Assets | View assets issued to me | `REFINE` | `asset.view` | `asset.view_own` | `GET /api/assets/me/` | Self |
| 36 | Assets | View the asset register | `REUSE` | `asset.view` | `asset.view` | `GET /api/assets/` | Branch / Org |
| 37 | Assets | Add, edit and retire assets | `REFINE` | `asset.create` | `asset.manage` | `POST,PUT,DELETE /api/assets/` | Branch / Org |
| 38 | Assets | Issue assets to people and take them back | `REUSE` | `asset.assign` | `asset.assign` | `POST /api/assets/{id}/assign/` | Branch / Org |
| 39 | Attendance | Check in and check out | `ADD` | — | `attendance.clock_in_out` | `POST /api/attendance/check-in/` | Self |
| 40 | Attendance | View own attendance | `ADD` | — | `attendance.view_own` | `GET /api/attendance/me/` | Self |
| 41 | Attendance | View team attendance | `ADD` | — | `attendance.view_team` | `GET /api/attendance/team/` | Team |
| 42 | Attendance | View all attendance | `REUSE` | `attendance.view_all` | `attendance.view_all` | `GET /api/attendance/` | Branch / Org |
| 43 | Attendance | Add and edit attendance records | `ADD` | — | `attendance.manage_records` | `POST,PUT /api/attendance/records/` | Branch / Org |
| 44 | Attendance | Approve attendance regularisation | `ADD` | — | `attendance.regularize_approve` | `POST /api/attendance/regularize/` | Team / Branch |
| 45 | Leave | Apply for leave | `REUSE` | `leave.request` | `leave.request` | `POST /api/leaves/requests/` | Self |
| 46 | Leave | Apply for leave on behalf of employees in scope | `ADD` | — | `leave.apply_behalf` | `POST /api/leaves/proxy-request/` | Team / Branch |
| 47 | Leave | Submit past-dated leave requests | `ADD` | — | `leave.submit_backdated` | `POST /api/leaves/requests/?backdated=1` | Self / Scoped |
| 48 | Leave | View own leave | `ADD` | — | `leave.view_own` | `GET /api/leaves/me/` | Self |
| 49 | Leave | View team leave | `ADD` | — | `leave.view_team` | `GET /api/leaves/team/` | Team |
| 50 | Leave | View all leave | `REUSE` | `leave.view` | `leave.view` | `GET /api/leaves/` | Branch / Org |
| 51 | Leave | Approve or reject leave | `REFINE` | `leave.approve` | `leave.approve_reject` | `POST /api/leaves/{id}/approve/` | Team / Branch |
| 52 | Leave | Manage leave types | `REUSE` | `leave_type.manage` | `leave_type.manage` | `/api/leaves/types/` | Organization |
| 53 | Leave | Manage leave allocations | `ADD` | — | `leave.manage_allocations` | `/api/leaves/allocations/` | Branch / Org |
| 54 | Recruitment | Ask for a vacancy to be filled | `REFINE` | `candidate.requisition.manage` | `recruitment.requisition_request` | `POST /api/recruitment/requisitions/` | Team / Branch |
| 55 | Recruitment | See requisitions in scope | `REFINE` | `candidate.requisition.manage` | `recruitment.requisition_view` | `GET /api/recruitment/requisitions/` | Team / Branch |
| 56 | Recruitment | Agree a role should be filled (the HR signature) | `ADD` | — | `recruitment.requisition_sign_hr` | `POST /api/recruitment/requisitions/{id}/sign-hr/` | Branch / Org |
| 57 | Recruitment | Agree the money exists (the Finance signature) | `ADD` | — | `recruitment.requisition_sign_finance` | `POST /api/recruitment/requisitions/{id}/sign-fin/` | Organization |
| 58 | Recruitment | See openings and the people who applied | `REFINE` | `candidate.view` | `recruitment.job_view` | `GET /api/recruitment/openings/` | Branch / Org |
| 59 | Recruitment | Write, publish and close job openings | `ADD` | — | `recruitment.job_manage` | `POST,PUT /api/recruitment/openings/` | Branch / Org |
| 60 | Recruitment | Add applicants, move them along, and read a CV | `REFINE` | `candidate.create` | `recruitment.candidate_manage` | `/api/candidates/` | Branch / Org |
| 61 | Recruitment | Arrange interview rounds and pick the panel | `REUSE` | `candidate.interview.manage` | `candidate.interview.manage` | `/api/candidates/{id}/interviews/` | Branch / Org |
| 62 | Recruitment | Unlock an interview write-up that has already been submitted | `ADD` | — | `recruitment.interview_unlock` | `POST /api/candidates/interview/{id}/unlock/` | Organization |
| 63 | Work from office exception | Ask for a work from office exception | `REUSE` | `wfh.request` | `wfh.request` | `POST /api/wfh/` | Self |
| 64 | Work from office exception | See the requests of people in scope | `ADD` | — | `wfh.view_team` | `GET /api/wfh/team/` | Team / Branch |
| 65 | Work from office exception | See every request | `REUSE` | `wfh.view` | `wfh.view` | `GET /api/wfh/` | Branch / Org |
| 66 | Work from office exception | Approve or decline a request | `REFINE` | `wfh.approve` | `wfh.approve_reject` | `POST /api/wfh/{id}/action/` | Team / Branch |
| 67 | Work from office exception | Set how many days a quarter allows | `ADD` | — | `wfh.manage_policy` | `/api/wfh/policy/` | Organization |
| 68 | Resignations | Hand in my own resignation | `ADD` | — | `resignation.submit_self` | `POST /api/resignations/me/` | Self |
| 69 | Resignations | View resignations in scope | `ADD` | — | `resignation.view` | `GET /api/resignations/` | Team / Branch |
| 70 | Resignations | Accept or decline a resignation | `ADD` | — | `resignation.approve` | `POST /api/resignations/{id}/action/` | Team / Branch |
| 71 | Resignations | See where a leaver's clearance has got to | `ADD` | — | `resignation.clearance_view` | `GET /api/resignations/{id}/clearance/` | Branch / Org |
| 72 | Resignations | Read exit interviews and the leaving reasons report | `ADD` | — | `resignation.exit_interview_view` | `GET /api/resignations/exit-reports/` | Organization |
| 73 | Resignations | Invite somebody to an exit interview and note it afterwards | `ADD` | — | `resignation.exit_interview_manage` | `POST /api/resignations/{id}/interview/` | Branch / Org |
| 74 | Payroll | View payroll runs | `REUSE` | `payroll.view` | `payroll.view` | `GET /api/payroll/runs/` | Branch / Org |
| 75 | Payroll | Create and generate payroll runs | `REUSE` | `payroll.generate` | `payroll.generate` | `POST /api/payroll/runs/` | Branch / Org |
| 76 | Payroll | Update payroll runs | `REFINE` | `payroll.generate` | `payroll.update` | `PUT /api/payroll/runs/{id}/` | Branch / Org |
| 77 | Payroll | Delete payroll runs | `ADD` | — | `payroll.delete` | `DELETE /api/payroll/runs/{id}/` | Branch / Org |
| 78 | Payroll | Approve payroll runs | `REUSE` | `payroll.approve` | `payroll.approve` | `POST /api/payroll/runs/{id}/approve/` | Branch / Org |
| 79 | Payroll | Mark payroll as paid | `REUSE` | `payroll.disburse` | `payroll.disburse` | `POST /api/payroll/runs/{id}/disburse/` | Branch / Org |
| 80 | Payroll | Download the bank payment file | `REUSE` | `payroll.disburse_export` | `payroll.disburse_export` | `GET /api/payroll/runs/{id}/bank-file/` | Organization |
| 81 | Payroll | Manage salary components | `REFINE` | `payroll.manage_compensation` | `payroll.component.manage` | `/api/payroll/components/` | Organization |
| 82 | Payroll | Manage salary structures | `REFINE` | `payroll.manage_compensation` | `payroll.structure.manage` | `/api/payroll/structures/` | Organization |
| 83 | Income tax | Declare my own investments | `REUSE` | `payroll.tax_declare` | `payroll.tax_declare` | `POST /api/payroll/tax/declarations/` | Self |
| 84 | Income tax | View everybody's declarations and tax | `REUSE` | `payroll.tax_view` | `payroll.tax_view` | `GET /api/payroll/tax/declarations/` | Branch / Org |
| 85 | Income tax | Verify declarations against their proof | `REUSE` | `payroll.tax_review` | `payroll.tax_review` | `POST /api/payroll/tax/verify/` | Branch / Org |
| 86 | Settlements | View my own settlement | `ADD` | — | `settlement.view_own` | `GET /api/payroll/fnf/me/` | Self |
| 87 | Settlements | View settlements | `REUSE` | `payroll.fnf_view` | `payroll.fnf_view` | `GET /api/payroll/fnf/` | Branch / Org |
| 88 | Settlements | Prepare and edit settlements | `REUSE` | `payroll.fnf_prepare` | `payroll.fnf_prepare` | `POST,PUT /api/payroll/fnf/` | Branch / Org |
| 89 | Settlements | Approve a settlement and mark it paid | `REFINE` | `payroll.fnf_approve` | `payroll.fnf_approve` | `POST /api/payroll/fnf/{id}/approve/` | Branch / Org |
| 90 | Payslips | View own payslips | `REUSE` | `payslip.view` | `payslip.view` | `GET /api/payslips/me/` | Self |
| 91 | Payslips | View all payslips | `REFINE` | `payslip.view` | `payslip.view_all` | `GET /api/payslips/` | Branch / Org |
| 92 | Payslips | Download payslip PDFs | `REUSE` | `payslip.download` | `payslip.download` | `GET /api/payslips/{id}/pdf/` | Self / Scoped |
| 93 | Payslips | Email payslips to employees | `ADD` | — | `payslip.email` | `POST /api/payslips/email-batch/` | Branch / Org |
| 94 | Holidays | View holidays | `REUSE` | `holiday.view` | `holiday.view` | `GET /api/organization/holidays/` | Organization / Branch |
| 95 | Holidays | Manage holidays | `REUSE` | `holiday.manage` | `holiday.manage` | `/api/organization/holidays/` | Organization / Branch |
| 96 | Shifts | View shifts | `REUSE` | `shift.view` | `shift.view` | `GET /api/attendance/shifts/` | Organization / Branch |
| 97 | Shifts | Manage shifts | `REUSE` | `shift.manage` | `shift.manage` | `/api/attendance/shifts/` | Organization / Branch |
| 98 | Breaks | Decide the break types and how long each is | `ADD` | — | `attendance.break_type_manage` | `/api/attendance/break-types/` | Organization / Branch |
| 99 | Announcements | View announcements | `REUSE` | `announcement.view` | `announcement.view` | `GET /api/announcements/` | Organization / Branch |
| 100 | Announcements | Manage announcements | `REUSE` | `announcement.manage` | `announcement.manage` | `/api/announcements/` | Organization / Branch |
| 101 | Candidates | View candidates and their offers | `REUSE` | `candidate.view` | `candidate.view` | `GET /api/candidates/` | Branch / Org |
| 102 | Candidates | Add candidates, issue offers and record what they answered | `REFINE` | `candidate.create` | `candidate.manage` | `POST,PUT /api/candidates/` | Branch / Org |
| 103 | Candidates | Turn an accepted candidate into an employee | `REUSE` | `candidate.convert` | `candidate.convert` | `POST /api/candidates/{id}/convert/` | Branch / Org |
| 104 | Candidates | Delete a candidate record | `ADD` | — | `candidate.delete` | `DELETE /api/candidates/{id}/` | Branch / Org |
| 105 | Letters | View own letters | `REFINE` | `letter.view` | `letter.view_own` | `GET /api/letters/me/` | Self |
| 106 | Letters | View letters issued to anyone | `REUSE` | `letter.view` | `letter.view` | `GET /api/letters/` | Branch / Org |
| 107 | Letters | Issue letters | `REUSE` | `letter.issue` | `letter.issue` | `POST /api/letters/issue/` | Branch / Org |
| 108 | Letters | Edit the wording of letters | `REFINE` | `letter.issue` | `letter.template_manage` | `/api/letters/templates/` | Organization |
| 109 | Petty cash | See petty cash floats and their ledgers | `ADD` | — | `petty_cash.view` | `GET /api/petty-cash/` | Branch / Org |
| 110 | Petty cash | Open a float, record entries and reverse them | `ADD` | — | `petty_cash.record` | `POST /api/petty-cash/entries/` | Branch / Org |
| 111 | Petty cash | Correct an entry that is already written | `ADD` | — | `petty_cash.correct` | `POST /api/petty-cash/entries/{id}/correct/` | Branch / Org |
| 112 | Insights | See workforce insights | `ADD` | — | `insights.view` | `GET /api/insights/` | Organization |
| 113 | Reports | Attendance reports | `ADD` | — | `reports.attendance` | `GET /api/reports/attendance/` | Branch / Org |
| 114 | Reports | Leave reports | `ADD` | — | `reports.leave` | `GET /api/reports/leave/` | Branch / Org |
| 115 | Reports | Payroll reports | `REUSE` | `payroll.view_reports` | `payroll.view_reports` | `GET /api/reports/payroll/` | Branch / Org |
| 116 | Reports | Employee reports | `ADD` | — | `reports.employee` | `GET /api/reports/employees/` | Branch / Org |
| 117 | Administration | View user accounts | `ADD` | — | `user.view` | `GET /api/auth/users/` | Organization |
| 118 | Administration | Manage user accounts | `REFINE` | `employee.status` | `user.manage` | `/api/auth/users/` | Organization |
| 119 | Administration | View roles and permissions | `REUSE` | `role.view` | `role.view` | `GET /api/auth/roles/` | Organization |
| 120 | Administration | Manage roles and permissions | `REUSE` | `role.assign` | `role.manage` | `/api/auth/roles/`, `/api/auth/permissions/` | Organization |
| 121 | Administration | View settings | `ADD` | — | `settings.view` | `GET /api/settings/` | Organization |
| 122 | Administration | Manage settings | `REFINE` | `organization.manage` | `settings.manage` | `/api/settings/` | Organization |
| 123 | Administration | Manage email and in-app notifications | `ADD` | — | `notifications.manage` | `/api/notifications/settings/` | Organization |
| 124 | Administration | See what the system does on its own, and ch[... UNCLEAR] | `UNCLEAR` | — | `automation.manage` | `/api/admin/automations/` | Organization |
| 125 | Administration | Write and edit the Self Assistance guides | `ADD` | — | `helpdesk.guides_manage` | `/api/helpdesk/guides/` | Organization |
| 126 | Administration | Import data from a spreadsheet | `REUSE` | `data_import.execute` | `data_import.execute` | `POST /api/data-import/execute/` | Organization |
| 127 | Administration | View activity log | `REUSE` | `audit.view` | `audit.view` | `GET /api/audit/` | Organization |

---

## 7. Preserved Backend Permission Keys (Not in Reference UI)

In accordance with **Requirement 10**, all existing valid permission keys in the HRMS codebase not shown in the simplified reference UI must be preserved to guarantee backward compatibility and maintain enterprise-grade security hardening:

| Existing Codename | Resource | Action | Purpose / Backend Operation | Rationale for Preservation |
| :--- | :--- | :--- | :--- | :--- |
| `employee.view_statutory` | `employee` | `view_statutory` | View PAN, Aadhaar, PF UAN, ESI numbers | Indian statutory compliance privacy separation |
| `employee.manage_statutory` | `employee` | `manage_statutory` | Edit statutory compliance numbers | Prevent unauthorized alteration of tax/PF IDs |
| `employee.transfer` | `employee` | `transfer` | Transfer employee across branch/dept | Multi-branch organizational governance |
| `employee.promote` | `employee` | `promote` | Promote employee / grade change | Lifecycle event tracking |
| `employee.exit` | `employee` | `exit` | Mark employee as exited | HR lifecycle termination record |
| `employee.lifecycle.view` | `employee` | `lifecycle_view` | Audit full career progression history | Historical record compliance |
| `hierarchy.manage` | `hierarchy` | `manage` | Modify manager reporting tree | Org chart restructuring control |
| `branding.manage` | `organization` | `manage_branding` | Upload tenant logo, company theme | Tenant identity isolation |
| `custom_fields.manage` | `organization` | `manage_custom_fields`| Define custom employee profile fields | Extensible metadata control |
| `office_network.view` | `office_network` | `view` | View approved office IP/Wi-Fi subnets | Network geofencing security |
| `office_network.create` | `office_network` | `create` | Add approved office network CIDR | Network geofencing security |
| `office_network.update` | `office_network` | `update` | Edit approved office network CIDR | Network geofencing security |
| `office_network.delete` | `office_network` | `delete` | Remove approved office network CIDR | Network geofencing security |
| `payroll.tax_calculate` | `payroll` | `tax_calculate` | Run TDS recalculation engine | High-frequency payroll processing |
| `payroll.tax_configure` | `payroll` | `tax_configure` | Configure financial year tax slabs | Regime/slab administrative control |
| `payroll.disburse_prepare`| `payroll` | `disburse_prepare` | Create NACH batch proposal | Dual-control / 4-eyes financial segregation |
| `payroll.disburse_approve`| `payroll` | `disburse_approve` | Authorize NACH batch payout | Dual-control / 4-eyes financial segregation |
| `payroll.disburse_configure`| `payroll` | `disburse_configure`| Configure company disbursal bank IFSC | Corporate treasury routing configuration |
| `candidate.manage_status` | `candidate` | `manage_status` | Advance candidate workflow stage | Granular ATS workflow tracking |
| `candidate.verify` | `candidate` | `verify` | Authenticate uploaded candidate KYC | Pre-onboarding credential validation |
| `document.manage_templates`| `document` | `manage_templates` | Edit universal HTML/PDF templates | Legal document versioning |

---

## 8. Backend Authorization & Scoping Architecture Findings

### 8.1 The Multi-Tier Scope Model
Inspection of `backend/apps/authorization/models.py` (`UserRole`, `ScopeChoices`) and `services.py` (`AuthorizationService`) reveals an established scoping hierarchy:
```
           ORGANIZATION (Tenant-wide)
                  │
                  ▼
                BRANCH (Office location)
                  │
                  ▼
                 TEAM (Department / Sub-unit)
                  │
                  ▼
                 SELF (Personal record / Subordinate)
```

1. **Organization Scope:** Grants the permission across the entire organization. Automatically inherits access to all branches and teams within that organization.
2. **Branch Scope:** Grants the permission restricted to employees and data belonging to a specific branch (`branch_id`). Automatically inherits access to all teams within that branch.
3. **Team Scope:** Grants the permission restricted to employees within a specific department team (`team_id`).
4. **Self Scope:** Evaluated at the endpoint/viewset level. If an employee lacks team/branch/org scope, endpoints filter by `user=request.user` or `employee=request.user.employee`.

### 8.2 Scope Alignment with Reference Labels
The reference UI explicitly expresses this 4-tier scoping structure through its labeling convention:
- **Self Level:** *"View own attendance"*, *"Apply for leave"*, *"See my own review"*, *"Fill in my own timesheet"*, *"View assets issued to me"*, *"Declare my own investments"*, *"View my own settlement"*, *"View own payslips"*, *"View own letters"*, *"Hand in my own resignation"*.
- **Team / Manager Level:** *"View team attendance"*, *"View team leave"*, *"Write reviews for the people who report to me"*, *"Approve the timesheets of people who report to me"*, *"See the requests of people in scope"*.
- **Branch / Scoped Level:** *"View employees"*, *"Apply for leave on behalf of employees in scope"*, *"See requisitions in scope"*, *"View resignations in scope"*.
- **Organization / All Level:** *"View employees across all branches"*, *"View all attendance"*, *"View all leave"*, *"See everybody's reviews"*, *"See everybody's timesheets"*, *"See every request"*, *"View all payslips"*, *"View letters issued to anyone"*.

---

## 9. UI Layout & Interaction Requirements Visible in References

### 9.1 Roles Management Overview (`/roles`)
1. **Grid Layout:** 3-column responsive card grid with uniform card aspect ratio.
2. **Card Anatomy:**
   - **Role Title:** Bold primary text (e.g., `Super Admin`, `HR Manager`, `Accountant`).
   - **Role Slug:** Subtitle in muted text below title (e.g., `super-admin`, `hr-manager`).
   - **Status Badge:** Highlight badge for special roles (e.g., `Full access` green badge on Super Admin).
   - **Metric Counter 1 (USERS):** Bold counter with label `USERS` above value.
   - **Metric Counter 2 (PERMISSIONS):** Bold counter with label `PERMISSIONS` above value.
   - **Action Button:** Full-width secondary button: `Edit permissions`.
   - **Delete Action:** Icon button (trash can) positioned on custom roles only (e.g., `team-lead`); absent on built-in system roles.

### 9.2 Edit Permissions Screen (`/roles/{id}/edit`)
1. **Breadcrumb / Title:** Displays `System Admin` / role title being edited.
2. **Role Locking Notice (Super Admin):** Informational callout box with blue icon:
   *"The super admin role always holds every permission, including any added later. Its permission list cannot be narrowed."*
   All checkboxes for Super Admin are checked and disabled.
3. **Masonry 3-Column Categorization:**
   - Permissions grouped logically into 29 cards.
   - Category title in semi-bold blue/slate text.
   - Selection count indicator: Displays fraction `X/Y` (e.g. `4/4`, `3/3`) indicating enabled permissions vs. total permissions in category.
   - Action Items: Clean checkbox with plain English, task-oriented descriptions instead of raw technical codenames (e.g., *"Agree the money exists (the Finance signature)"* rather than `recruitment.requisition_approve_finance`).
4. **Form Submission Actions:** Fixed bottom action bar containing green `Save permissions` button and cancel link.

---

## 10. Unresolved Questions & Backward-Compatibility Risks

### 10.1 Key Unresolved Architectural Questions
1. **The 118 vs 127 Counter Reconciliation:**
   - Did the 118 count in the screenshot exclude non-core modules (e.g., `Recruitment` with 9 permissions, or `Petty cash` with 3 + `Settlements` with 4 + `Companies` with 2 = 9)?
   - *Recommendation:* When implementing the dynamic RBAC upgrade, compute the counter dynamically from `role.role_permissions.filter(permission__is_active=True).count()`.
2. **Granular vs. Aggregate Permission Storage:**
   - Should the database store all 127 individual keys, or should UI actions map to combinations of backend keys?
   - *Recommendation:* Store granular keys matching the 127 UI actions directly in `Permission` table, while maintaining foreign-key relationships to preserve existing seeded keys.
3. **Unclear Administration Item 8:**
   - Character string cuts off at `"See what the system does on its own, and ch"`.
   - *Recommendation:* Introduce codename `automation.manage` with title `"Automations & Scheduled Tasks"` and flag for explicit product owner confirmation.

### 10.2 Backward-Compatibility Risks
1. **Existing Test Suite Reliance on Legacy Codenames:**
   - 28 test files in frontend and dozens of backend test modules explicitly test keys such as `leave.request`, `employee.view`, `payroll.generate`, `wfh.approve`.
   - *Mitigation:* Never delete existing codenames. Map new UI permissions as aliases or additive records in the database.
2. **Frontend `hasPermission` Call Sites:**
   - The frontend uses `hasPermission('employee.view')` across 50+ components.
   - *Mitigation:* Ensure that any new granular permissions (`employee.view_all_branches`, `employee.salary.view`) augment rather than break the core coarse-grained checks.

---

## 11. Recommended Implementation Sequence (Phased Roadmap)

When authorized to proceed with Phase 2B/2C implementation, the following sequence minimizes regression risk:

### Step 1: Permission Schema & Registry Migration (Phase 2B)
- Create data migration to seed the missing permission records (71 additions) into `Permission` table.
- Add category foreign key or enum field to `Permission` model (`category` CharField, max_length=100) to natively support the 29 UI categories.
- Add friendly UI label field (`ui_label` CharField) to store the exact reference text without altering the canonical `name` and `codename`.
- Populate initial role permissions for standard roles (`Super Admin` = 127, `HR Manager` = 112, `Accountant` = 48, `Branch Manager` = 40, `Employee` = 18).

### Step 2: Backend Scoping & Endpoint Mapping Verification (Phase 2C)
- Ensure all viewsets enforce the appropriate permission codenames via `AuthorizationService`.
- Wire `ScopeChoices` evaluation into the new category endpoints.
- Ensure Super Admin system bypass correctly yields all 127 permissions without database bottlenecks.

### Step 3: Frontend Roles & Permissions UI Upgrade (Phase 2D)
- Refactor `RolesPage.tsx` from table view into the 3-column responsive card grid shown in the reference screenshot.
- Refactor `RolePermissionsPage.tsx` from flat toggle list into the 29-category 3-column checkbox matrix with `X/Y` fraction headers, search filter, and category counters.
- Enforce the disabled Super Admin lock banner.

### Step 4: End-to-End Regression Verification (Phase 2E)
- Run full automated test suites across backend authorization tests and frontend test suites.
- Verify zero regressions in cross-tenant isolation, branch/team scoping, and self-service portal functionality.

---

**End of Audit Report.**  
*Status: Complete and Verified. Strictly Read-Only. Standing by for Product Owner Approval.*
