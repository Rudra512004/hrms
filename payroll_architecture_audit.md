# Payroll Architecture Audit

## 1. Executive Summary
The single biggest architectural risk is: The complete absence of an extensible payroll calculation engine and lineage tracking. 

The current system hardcodes net pay to equal gross pay (`net_salary = gross`) and computes gross salary exclusively from a single `basic_salary` field on `CompensationHistory`. Recently added models for `SalaryComponent` and `SalaryStructure` are structurally disconnected from the actual payroll generation logic (`generate_payroll_for_period`). If this architecture is extended by simply adding more hardcoded Python math without a rule-evaluation engine or granular persistence, historical reproducibility and explainability (parallel payroll diffing) will be impossible to achieve.

## 2. Current Architecture
- **Payroll Run:** Managed via `PayrollPeriod` (one per org, per month).
- **Payroll Record:** `PayrollRecord` stores the snapshotted result for an employee.
- **Inputs:** `CompensationHistory` (basic_salary only), `Attendance` (present/half-day counts), `LeaveRequest` (approved days), and `WorkingCalendarService` (working days).
- **Outputs:** `Payslip` acts as an issued receipt pointing to an approved `PayrollRecord`.
- **Deductions:** Not implemented in the core engine. `lop_amount` is a dynamic property but isn't actually deducted from `net_salary`.
- **Salary Structures:** Models exist (`SalaryComponent`, `SalaryStructure`) but are disconnected from calculation logic.

## 3. Payroll Calculation Flow
Employee
  ↓
CompensationHistory (picks active `basic_salary` at period start/end)
  ↓
WorkingCalendarService (calculates total `working_days`)
  ↓
Attendance & LeaveRequest (calculates `effective_days`)
  ↓
Gross Salary (`basic_salary * effective_days / working_days`)
  ↓
Net Salary (hardcoded: `net_salary = gross_salary`)
  ↓
PayrollRecord (snapshots basic, gross, net, and day counts)
  ↓
Payslip (references PayrollRecord)

## 4. Payroll Data Lineage
| Payroll element | Current source | Calculation location | Persisted? | Effective-dated? | Auditable? | Reproducible? | Gap |
|---|---|---|---|---|---|---|---|
| Basic Salary | `CompensationHistory` | `_get_active_salary` | Yes (`PayrollRecord`) | Yes | Partial | Yes | No breakdown of components |
| Gross Pay | Hardcoded | `generate_payroll_for_period` | Yes | No | No | Yes | Hardcoded formula |
| Net Pay | Hardcoded | `generate_payroll_for_period` | Yes | No | No | Yes | Equals gross pay |
| LOP Deduction | N/A | `PayrollRecord.lop_amount` | No | No | No | Yes | Not actually deducted from net |
| Statutory Deductions | N/A | N/A | N/A | N/A | N/A | N/A | Missing entirely |
| Tax (TDS) | N/A | N/A | N/A | N/A | N/A | N/A | Missing entirely |

## 5. Historical Reproducibility
**PARTIALLY SAFE**
If we run payroll for September 2026, the inputs (working_days, basic_salary, effective_days, gross, net) are snapshotted into `PayrollRecord`.
- **SAFE**: The final numbers are preserved and immune to upstream changes because they are copied to `PayrollRecord`.
- **NOT SAFE**: The *reason* for the numbers is lost. If an employee's attendance record is subsequently modified or a leave is cancelled, the `PayrollRecord` will no longer match the live upstream data. There is no snapshot of the specific attendance rows used.
- **NOT SAFE**: Rule changes (e.g., how LOP is calculated) cannot be applied historically because rules are hardcoded in Python, not versioned.

## 6. Effective-Dated Rules
- **Rules as Data:** No. Statutory rules, tax brackets, and formulas do not exist in the database.
- **Rules Versioned:** No.
- **Effective Dating:** Only `CompensationHistory` is effective-dated. Formulas and rules are not.
- **Tenant-Specific Rules:** No.
- **Compliance Engine:** Does not exist.

## 7. Parallel Payroll Feasibility
**NOT FEASIBLE CURRENTLY**
The current architecture lacks the granularity to compare payrolls. It only generates a single "net salary" value. Without a robust `SalaryComponent` engine that breaks down Earnings and Deductions (HRA, PF, PT, LOP, etc.) into distinct line items, it is impossible to compare legacy payroll against HRMS payroll at the component or deduction level.

## 8. Payroll Preflight Feasibility
**PARTIALLY FEASIBLE**
We could implement basic checks (e.g., negative net pay, unusually large absence), but because the engine doesn't produce granular deduction line items, we cannot validate specific statutory compliance or detect component-level anomalies prior to approval.

## 9. Attendance → LOP → Payroll
- **Flow:** Attendance/Leaves are aggregated by `_attendance_summary` and `_approved_leave_days`. LOP days are calculated as a property (`lop_days`), but *not* explicitly persisted as a distinct deduction line item with a reason.
- **Gap:** The exact dates considered for LOP are not saved. If an employee asks "Which days was I docked pay for?", the system cannot definitively answer from the payroll record alone; it must guess by re-querying the current state of Attendance.

## 10. Rerun / Idempotency Analysis
- **Rerun Safety:** Re-generating a draft period safely deletes existing draft `PayrollRecord`s and recreates them.
- **Locking:** Once a `PayrollPeriod` is marked `approved`, re-generation raises an exception.
- **Gap:** Manual adjustments are not supported. If an admin manually corrects a `PayrollRecord`, re-generating the draft would blindly overwrite their corrections.

## 11. Multi-Tenant Security Findings
- `PayrollPeriod` is explicitly linked to `Organization`.
- Employee querying in `generate_payroll_for_period` correctly filters by `organization=period.organization`.
- Tenant isolation appears structurally sound in the core engine. No IDOR risks identified here.

## 12. Test Coverage
- Basic calculation correctness is tested (`test_reconciliation_output_correctness`).
- Workflow locking (cannot regenerate approved) is tested.
- **Gap:** No tests for statutory calculations, adjustments, or component breakdowns, as these features do not exist.

## 13. Critical Gaps
1. **No Calculation Engine:** Hardcoded Python math instead of a rule-based engine.
2. **Disconnected Component Models:** `SalaryComponent` exists but does nothing.
3. **No Line Item Persistence:** `PayrollRecord` stores aggregate numbers, not granular earning/deduction line items.
4. **No Manual Adjustments:** Cannot add ad-hoc bonuses or corrections.
5. **Loss of Source Lineage:** The exact attendance rows/leave requests used for calculation are not linked to the `PayrollRecord`.

## 14. Recommended Architecture Changes
1. **Implement `PayrollLineItem`:** Create a model linked to `PayrollRecord` to store granular components (Basic, HRA, PF, LOP) so we can answer "Why is this number?".
2. **Integrate `SalaryStructure`:** Rewrite `generate_payroll_for_period` to iterate over an employee's effective `SalaryStructureComponent`s.
3. **Introduce `CalculationRule` / Formula Engine:** Store statutory and calculation rules as versioned, effective-dated records rather than hardcoded Python.
4. **Snapshot Inputs:** Store a serialized snapshot of the exact attendance/leave IDs used to compute effective days.

---

### Current State
Backend test suite is fully passing (774/774). Uncommitted migration and test files for the Multi-Tenant identity foundation were committed successfully prior to this audit. 

### Biggest Risk
The single biggest architectural risk is the complete absence of an extensible payroll calculation engine and lineage tracking. The current system hardcodes net pay to equal gross pay (`net_salary = gross`) and computes gross salary exclusively from a single `basic_salary` field on `CompensationHistory`.

### P0 Findings
- `SalaryComponent` and `SalaryStructure` models exist but are entirely disconnected from `generate_payroll_for_period`. 
- `PayrollRecord` lacks the ability to store granular earning/deduction line items (`PayrollLineItem`). Without line items, we cannot provide parallel payroll variance tracking.

### P1 Findings
- The exact attendance rows and leave requests used for a given calculation are not linked to the `PayrollRecord`.
- Manual adjustments (ad-hoc bonuses or corrections) cannot survive a draft period recalculation.

### P2 Findings
- No versioned `CalculationRule` engine exists for statutory compliance; logic is fully hardcoded in Python.

### Recommended Next Step
Refactor the payroll engine to correctly iterate over `SalaryStructureComponent`s and persist the output into a new `PayrollLineItem` model. This is the minimum required foundational step before lineage and parallel payrolls can be attempted.

### Files Inspected
- `backend/apps/payroll/models.py`
- `backend/apps/payroll/services.py`
- `backend/apps/payroll/views.py`
- `backend/apps/payroll/tests.py`

### Files Changed
None (audit only).

### Tests Run
N/A (No functional code changed; backend baseline 774/774 verified prior).

### Test Results
N/A

### Commit Recommendation
NO COMMIT (No code changes were made during this phase).
