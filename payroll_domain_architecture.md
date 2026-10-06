# Payroll Domain & Calculation Architecture

## 1. Purpose
This document finalizes the domain architecture required to support trustworthy, explainable, and verifiable payroll calculations. It bridges the gap between the current MVP implementation and a production-grade calculation engine capable of historical reproducibility, manual adjustments, and future parallel payroll validation.

## 2. Current Architecture
- **Payroll Run:** Managed via `PayrollPeriod` (one per org, per month). Unique by `(organization, year, month)`.
- **Payroll Record:** `PayrollRecord` stores aggregate results.
- **Inputs:** `CompensationHistory.basic_salary`, `Attendance` (present/half-day counts), `LeaveRequest` (approved days).
- **Calculation:** Hardcoded in Python (`net_salary = gross_salary`).
- **Deficiencies:** No component breakdown, no deductions, no manual adjustments, no way to preserve exact historical calculation inputs if upstream records change.

## 3. Design Goals
1. Deterministic calculation.
2. Tenant isolation.
3. Historical reproducibility.
4. Finalized payroll immutability.
5. Idempotent draft recalculation.
6. Durable approved adjustments.
7. Explicit earnings/deductions/employer contributions.
8. Explainable line items.
9. Future statutory-rule extensibility.
10. Future parallel payroll support.

## 4. Biggest Failure Risk
The single biggest reason this design could fail is: Designing a generic, highly-abstracted "rules engine" that tries to compute everything dynamically instead of focusing on persisting explicit `PayrollLineItem` records with clear source lineage. If we over-engineer the calculation logic while under-engineering the data persistence, we will never achieve safe historical reproducibility or parallel payroll capabilities. 

## 5. Domain Model
```text
Organization (Existing)
  |-- 1:N -- SalaryStructure
  |-- 1:N -- SalaryComponent
  |-- 1:N -- PayrollRun
  |-- 1:N -- Employee

Employee (Existing)
  |-- 1:N -- CompensationHistory (FK: SalaryStructure)
  |-- 1:N -- PayrollRecord
  |-- 1:N -- PayrollAdjustment

SalaryStructure
  |-- 1:N -- SalaryStructureComponent (FK: SalaryComponent)

PayrollRun (renamed/extended from PayrollPeriod)
  |-- 1:N -- PayrollRecord

PayrollRecord
  |-- 1:N -- PayrollLineItem
  |-- 1:1 -- Payslip

PayrollLineItem
  |-- FK: SalaryComponent (nullable, for system/statutory)
  |-- FK: PayrollAdjustment (nullable)
  |-- FK: SalaryStructureComponent (nullable)

PayrollAdjustment
  |-- FK: SalaryComponent
```

## 6. Payroll Lifecycle
**States:**
1. `DRAFT`: Actively being worked on. Can be recalculated. Recalculation deletes all `PayrollRecord`s and `PayrollLineItem`s for the run and regenerates them.
2. `APPROVED`: Locked. Cannot be recalculated. Payslips can be issued.
3. `FINALIZED`: Funds disbursed/Accounting closed. Absolutely immutable.
- *Corrections after FINALIZED:* Must be handled as a `PayrollAdjustment` in the *next* open `DRAFT` run. Finalized runs are never edited.

## 7. PayrollLineItem Semantics
`PayrollLineItem` represents the granular financial breakdown of a payroll calculation.
**Categories:**
- `EARNING`: Increases net pay (e.g., Basic, HRA).
- `DEDUCTION`: Decreases net pay (e.g., LOP, PF, PT).
- `EMPLOYER_CONTRIBUTION`: Does not affect net pay, tracks organizational liability (e.g., Employer PF).
- `TAX`: Decreases net pay (e.g., TDS).

**Fields:**
- `amount` (Decimal)
- `category` (Enum)
- `is_backfilled` (Boolean) - Identifies legacy data
- `calculation_metadata` (JSON) - Snapshot of input values (e.g., {"days_deducted": 2, "daily_rate": 1000})

## 8. Salary Component Calculation Model
**RECOMMENDATION:** Do NOT create a generic formula language. Constrain the engine to specific calculation types to guarantee deterministic evaluation.
**Types:**
- `FIXED_AMOUNT`: A static monthly value prorated by effective days.
- `PERCENTAGE_OF_BASIC`: Calculated dynamically based on the resolved `FIXED_AMOUNT` of the Basic component.
- `STATUTORY`: Handled exclusively by Python strategy classes (future).

## 9. Payroll Calculation Pipeline
Employee
→ Identify active `CompensationHistory`
→ Resolve `SalaryStructure`
→ Fetch `Attendance` & `Leave` aggregates (effective days)
→ Calculate `FIXED_AMOUNT` components
→ Calculate `PERCENTAGE_OF_BASIC` components
→ Fetch `APPROVED` `PayrollAdjustment`s for the period
→ Calculate `STATUTORY` & LOP deductions
→ Create `PayrollLineItem`s
→ Aggregate into `PayrollRecord` totals

## 10. Payroll Adjustment Model
Handles manual overrides, bonuses, and corrections.
- **Lifecycle:** `PENDING_APPROVAL` → `APPROVED` → `PROCESSED`.
- **Behavior:** The engine only pulls `APPROVED` adjustments. Once pulled into a `PayrollRun` that becomes `APPROVED`, the adjustment transitions to `PROCESSED` and cannot be pulled again.
- **Immutability:** An adjustment cannot be modified once `PROCESSED`.

## 11. Historical Reproducibility
**FACT:** Finalized payroll must NOT silently change.
**Mechanism:** `PayrollLineItem` stores the exact `amount` calculated at that moment. If a `SalaryStructure` is changed the next day, past `PayrollLineItem`s remain completely unaffected because they are static records, not live views of formulas.

## 12. Calculation Input Snapshot / Evidence Model
**RECOMMENDATION:** Relying purely on live `Attendance` rows is dangerous if they are hard-deleted.
**Strategy:** We will not duplicate the entire attendance system into snapshot models. Instead, we persist the aggregate input evidence (e.g., `working_days`, `present_days`, `leave_days`) explicitly on the `PayrollRecord`. The specific LOP rationale is saved in the `calculation_metadata` JSON of the LOP `PayrollLineItem`.

## 13. Lineage Strategy
**FACT:** The previous audit suggested polymorphic `source_type`/`source_id`. This is unsafe as it bypasses PostgreSQL referential integrity and risks orphaned data.
**RECOMMENDATION:** Use explicit, nullable Foreign Keys on `PayrollLineItem` instead:
- `source_adjustment` (FK to `PayrollAdjustment`)
- `source_structure_component` (FK to `SalaryStructureComponent`)
This guarantees referential integrity.

## 14. Draft Recalculation / Idempotency
- Recalculating a `DRAFT` run performs a hard delete of all existing `PayrollRecord`s and `PayrollLineItem`s for that run.
- It then regenerates everything from the current effective-dated inputs.
- `PayrollAdjustment`s survive because they live independently and are simply re-applied during the recalculation.

## 15. Finalized Payroll Immutability
**FACT:** Once `APPROVED` or `FINALIZED`, the `PayrollRun` and all child records are permanently locked. There is no "un-finalize" button. Errors discovered here require a reversal/adjustment in the next operational period.

## 16. PayrollRun Uniqueness + Parallel Payroll Readiness
**FACT:** Currently, `PayrollPeriod` enforces uniqueness on `(organization, year, month)`.
**RECOMMENDATION:** To support parallel payroll (e.g., comparing Legacy against HRMS), we must add a `run_type` field (defaulting to `REGULAR`). Uniqueness becomes `(organization, year, month, run_type)`. This allows a `PARALLEL_A` run to coexist safely without corrupting the operational `REGULAR` run.

## 17. Historical Backfill Strategy
**RECOMMENDATION:** We cannot invent component breakdowns for past payrolls.
**Strategy:** For historically approved `PayrollRecord`s, we will create a single `EARNING` `PayrollLineItem` labeled "Legacy Gross" mapping to the old `gross_salary`, and mark `is_backfilled = True`. This maintains aggregate parity without falsifying historical precision.

## 18. CompensationHistory Migration Strategy
**RECOMMENDATION:** Do not immediately drop `basic_salary`.
**Strategy:**
1. Add nullable `salary_structure` FK to `CompensationHistory`.
2. Map all employees to new `SalaryStructure`s matching their `basic_salary`.
3. Update calculation logic to prefer `salary_structure` and fallback to `basic_salary`.
4. Phase out `basic_salary` in a future major release.

## 19. Tenant Isolation
- **FACT:** `PayrollRun`, `SalaryStructure`, and `SalaryComponent` natively include `organization`.
- **RECOMMENDATION:** API endpoints fetching adjustments or creating runs must validate `request.user.employee.organization == target.organization`. No new tenancy model is needed.

## 20. Future Statutory CalculationRule Architecture
**UNKNOWN:** Exact state-specific rules are not yet defined.
**RECOMMENDATION:** In the future, introduce a `CalculationRule` model linking an `organization` and `component` to a `formula_identifier` (String matching a Python strategy class) and an `effective_from` date. Do not build an eval-based generic engine.

## 21. Database Constraints and Indexes
- `PayrollRun`: `UNIQUE(organization, year, month, run_type)`
- `PayrollRecord`: `UNIQUE(run, employee)`
- `SalaryStructureComponent`: `UNIQUE(structure, component)`
- **Indexes:** `PayrollLineItem.payroll_record`, `PayrollLineItem.category`

## 22. API Impact
Future endpoints:
- `POST /api/v1/payroll/adjustments/`
- `POST /api/v1/payroll/runs/{id}/recalculate/`
- `GET /api/v1/payroll/records/{id}/line-items/`

## 23. Testing Strategy
- **Idempotency:** Verify that calling recalculate multiple times yields the exact same Line Items and preserves Adjustments.
- **Historical Reproducibility:** Create a finalized run, alter a `SalaryStructure`, and verify the finalized run remains unchanged.
- **Lineage:** Assert that line items contain the correct `source_adjustment` FKs.

## 24. P0 Decisions
- Convert `PayrollPeriod` to `PayrollRun` (add `run_type`).
- Create `PayrollLineItem` model with explicit FK lineage (`source_adjustment`, `source_structure_component`).
- Refactor `generate_payroll_for_period` to iterate `SalaryStructureComponent`s.

## 25. P1 Decisions
- Implement `PayrollAdjustment` model and approval lifecycle.
- Add `salary_structure` FK to `CompensationHistory`.
- Perform the non-destructive legacy backfill script.

## 26. P2 / Future Decisions
- Implement `CalculationRule` framework for statutory deductions.
- Implement Soft Deletes on `Attendance` and `LeaveRequest` to preserve historical integrity perfectly.

## 27. Open Questions
- **UNKNOWN:** Will `SalaryStructureComponent` need to support complex custom formulas beyond `PERCENTAGE_OF_BASIC`? If yes, a constrained parser will be required later.
- **UNKNOWN:** How will annualized taxes (TDS) be calculated since they require forecasting across future payroll runs?
