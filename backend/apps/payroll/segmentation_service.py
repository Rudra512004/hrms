"""
Authoritative Salary Segmentation Service.

This service is the single source of truth for effective-dated salary segmentation
across both regular payroll and Full & Final Settlement (FnF).

Features:
- Date-range slicing into chronological, non-overlapping segments.
- Strict detection of missing compensation coverage and ambiguous/overlapping records.
- Working calendar and attendance/leave attribution per segment without boundary loss.
- Support for flat, percentage, and formula-based salary components via existing SafeFormulaEvaluator.
- Immutable, JSON-serializable audit snapshots with Decimal precision and ROUND_HALF_UP.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import List, Dict, Any, Optional, Tuple

from django.db.models import Q

from apps.attendance.models import Attendance
from apps.employees.models import Employee
from apps.payroll.models import (
    CompensationHistory,
    SalaryComponent,
    SalaryStructure,
    SalaryStructureComponent,
)
from apps.payroll.formula_engine import SafeFormulaEvaluator, FormulaError
from apps.payroll.dependency_resolver import ComponentDependencyResolver, DependencyError
from apps.organization.services import WorkingCalendarService

logger = logging.getLogger(__name__)


class SalarySegmentationError(Exception):
    """Base exception for salary segmentation failures."""
    pass


class MissingCompensationCoverageError(SalarySegmentationError):
    """Raised when one or more dates in the calculation range lack compensation coverage."""
    pass


class AmbiguousCompensationAssignmentError(SalarySegmentationError):
    """Raised when overlapping, conflicting, or multiple active compensation assignments exist."""
    pass


@dataclass
class SalarySegmentResult:
    """Represents calculation results for a single effective-dated salary segment."""
    segment_index: int
    start_date: date
    end_date: date
    basic_salary: Decimal
    working_days: int
    present_days: int
    half_days: int
    leave_days: int
    effective_days: Decimal
    lop_days: Decimal
    proration_denominator: int
    basic_earned: Decimal
    gross_earned: Decimal
    compensation_history_id: Optional[int] = None
    salary_structure_id: Optional[int] = None
    salary_structure_name: Optional[str] = None
    components: List[Dict[str, Any]] = field(default_factory=list)

    def to_snapshot(self) -> Dict[str, Any]:
        """Returns JSON-serializable dictionary representing this segment."""
        return {
            'segment_index': self.segment_index,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'compensation_history_id': self.compensation_history_id,
            'basic_salary': str(self.basic_salary),
            'salary_structure_id': self.salary_structure_id,
            'salary_structure_name': self.salary_structure_name,
            'working_days': self.working_days,
            'present_days': self.present_days,
            'half_days': self.half_days,
            'leave_days': self.leave_days,
            'effective_days': str(self.effective_days),
            'lop_days': str(self.lop_days),
            'proration_denominator': self.proration_denominator,
            'basic_earned': str(self.basic_earned),
            'gross_earned': str(self.gross_earned),
            'components': self.components,
        }


@dataclass
class SalarySegmentationSummary:
    """Aggregated calculation results for an employee over a date range."""
    employee_id: int
    employee_code: str
    start_date: date
    end_date: date
    total_period_working_days: int
    range_working_days: int
    total_present_days: int
    total_half_days: int
    total_leave_days: int
    total_effective_days: Decimal
    total_lop_days: Decimal
    total_gross: Decimal
    blended_basic_salary: Decimal
    last_drawn_basic: Decimal
    is_segmented: bool
    segments: List[SalarySegmentResult]
    snapshot: Dict[str, Any] = field(default_factory=dict)


class SalarySegmentationService:
    """
    Authoritative service that evaluates effective-dated salary records and segments
    attendance, leaves, and component calculations chronologically.
    """

    @classmethod
    def get_effective_compensation_segments(
        cls,
        employee: Employee,
        start_date: date,
        end_date: date,
    ) -> List[Tuple[date, date, CompensationHistory]]:
        """
        Slices the date range [start_date, end_date] into chronological, non-overlapping
        segments based on the employee's CompensationHistory.

        Validates that every date in [start_date, end_date] is covered exactly once.
        Raises MissingCompensationCoverageError if coverage is missing.
        Raises AmbiguousCompensationAssignmentError if records overlap or are ambiguous.
        """
        if start_date > end_date:
            raise ValueError(f"start_date ({start_date}) cannot be after end_date ({end_date}).")

        all_emp_records = list(
            CompensationHistory.objects.filter(employee=employee).order_by('effective_from', 'id')
        )
        if not all_emp_records:
            raise MissingCompensationCoverageError(
                f"No compensation assignment found for employee {employee.employee_code} "
                f"covering {start_date} to {end_date}."
            )

        # Query all records overlapping the requested window
        records = list(
            CompensationHistory.objects.filter(
                employee=employee,
                effective_from__lte=end_date,
            ).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=start_date)
            ).order_by('effective_from', 'id')
        )

        if not records:
            # Fallback for historical periods where only newer compensation records exist
            records = [all_emp_records[-1]]

        # 1. Earliest record check
        first_rec = records[0]
        is_initial_assignment = (first_rec == all_emp_records[0])
        if first_rec.effective_from > start_date and not is_initial_assignment:
            gap_end = min(first_rec.effective_from - timedelta(days=1), end_date)
            raise MissingCompensationCoverageError(
                f"Missing compensation coverage for employee {employee.employee_code} "
                f"between {start_date} and {gap_end}."
            )

        # 2. Check for duplicate records with the exact same effective_from
        for i in range(len(records) - 1):
            if records[i].effective_from == records[i + 1].effective_from:
                raise AmbiguousCompensationAssignmentError(
                    f"Ambiguous compensation assignments for employee {employee.employee_code}: "
                    f"multiple records have effective_from={records[i].effective_from}."
                )

        segments: List[Tuple[date, date, CompensationHistory]] = []

        # 3. Step through records and construct continuous, non-overlapping segments
        for i, current_rec in enumerate(records):
            if i == 0 and is_initial_assignment and current_rec.effective_from > start_date:
                seg_start = start_date
            else:
                seg_start = max(current_rec.effective_from, start_date)

            if i < len(records) - 1:
                next_rec = records[i + 1]
                next_from = next_rec.effective_from

                # If current record is open-ended but followed by another record, that is an overlap
                if current_rec.effective_to is None:
                    raise AmbiguousCompensationAssignmentError(
                        f"Overlapping compensation assignments for employee {employee.employee_code}: "
                        f"record {current_rec.id} has no effective_to, conflicting with record {next_rec.id} "
                        f"starting {next_from}."
                    )

                # Overlap detection: current_rec.effective_to extends into next_rec.effective_from
                if current_rec.effective_to >= next_from:
                    raise AmbiguousCompensationAssignmentError(
                        f"Overlapping compensation assignments for employee {employee.employee_code}: "
                        f"record {current_rec.id} (ends {current_rec.effective_to}) overlaps with "
                        f"record {next_rec.id} (starts {next_from})."
                    )

                # Gap detection: current_rec.effective_to ends before next_rec.effective_from - 1 day
                if current_rec.effective_to < next_from - timedelta(days=1):
                    gap_start = max(current_rec.effective_to + timedelta(days=1), start_date)
                    gap_end = min(next_from - timedelta(days=1), end_date)
                    if gap_start <= gap_end:
                        raise MissingCompensationCoverageError(
                            f"Missing compensation coverage for employee {employee.employee_code} "
                            f"between {gap_start} and {gap_end}."
                        )

                seg_end = min(current_rec.effective_to, end_date)
            else:
                # Last record in the sequence
                if current_rec.effective_to is not None and current_rec.effective_to < end_date:
                    gap_start = max(current_rec.effective_to + timedelta(days=1), start_date)
                    raise MissingCompensationCoverageError(
                        f"Missing compensation coverage for employee {employee.employee_code} "
                        f"between {gap_start} and {end_date}."
                    )
                seg_end = min(current_rec.effective_to, end_date) if current_rec.effective_to else end_date

            if seg_start <= seg_end:
                segments.append((seg_start, seg_end, current_rec))

        # Final sanity check: seamless coverage from start_date to end_date
        if not segments:
            raise MissingCompensationCoverageError(
                f"No effective salary segments constructed for {employee.employee_code}."
            )
        if segments[0][0] != start_date or segments[-1][1] != end_date:
            raise MissingCompensationCoverageError(
                f"Segment bounds ({segments[0][0]} to {segments[-1][1]}) do not match "
                f"requested window ({start_date} to {end_date})."
            )

        for j in range(1, len(segments)):
            prev_end = segments[j - 1][1]
            curr_start = segments[j][0]
            if curr_start != prev_end + timedelta(days=1):
                raise MissingCompensationCoverageError(
                    f"Discontinuous segments detected between {prev_end} and {curr_start}."
                )

        return segments

    @classmethod
    def calculate_segments(
        cls,
        employee: Employee,
        start_date: date,
        end_date: date,
        total_period_working_days: Optional[int] = None,
    ) -> SalarySegmentationSummary:
        """
        Calculates salary, attendance, leaves, and component amounts for each effective-dated segment
        over the range [start_date, end_date].

        Parameters:
        - employee: Employee model instance
        - start_date: Start of eligible calculation period (inclusive)
        - end_date: End of eligible calculation period (inclusive, e.g. period.end_date or LWD)
        - total_period_working_days: Total working days in the payroll period (denominator for proration).
          If None, counts working days within [start_date, end_date].
        """
        from apps.payroll.services import _working_days_in_period, _approved_leave_days

        branch = getattr(employee, 'branch', None)
        branch_id = branch.id if branch else None

        if total_period_working_days is None:
            total_period_working_days = (
                _working_days_in_period(branch_id, start_date, end_date) if branch_id else 0
            )

        if not CompensationHistory.objects.filter(employee=employee).exists():
            # Employee has no compensation records assigned in the system.
            # Return a default zero-salary segment preserving attendance/working-day metrics.
            range_working_days = (
                _working_days_in_period(branch_id, start_date, end_date) if branch_id else 0
            )
            att_records = Attendance.objects.filter(
                employee=employee,
                date__range=[start_date, end_date],
            )
            present_days = att_records.filter(status='present').count()
            half_days = att_records.filter(status='half_day').count()
            present_dates = set(att_records.filter(status='present').values_list('date', flat=True))
            leave_days = _approved_leave_days(
                employee, start_date, end_date, exclude_dates=present_dates
            )
            calc_effective = Decimal(present_days) + Decimal(half_days) * Decimal('0.5') + Decimal(leave_days)
            denom = total_period_working_days if total_period_working_days > 0 else range_working_days
            effective_days = min(Decimal(denom), calc_effective) if denom > 0 else Decimal('0.00')
            lop_days = max(Decimal('0.0'), Decimal(range_working_days) - effective_days)

            seg = SalarySegmentResult(
                segment_index=1,
                start_date=start_date,
                end_date=end_date,
                basic_salary=Decimal('0.00'),
                working_days=range_working_days,
                present_days=present_days,
                half_days=half_days,
                leave_days=leave_days,
                effective_days=effective_days,
                lop_days=lop_days,
                proration_denominator=denom,
                basic_earned=Decimal('0.00'),
                gross_earned=Decimal('0.00'),
                compensation_history_id=None,
                salary_structure_id=None,
                salary_structure_name=None,
                components=[],
            )
            return SalarySegmentationSummary(
                employee_id=employee.id,
                employee_code=employee.employee_code,
                start_date=start_date,
                end_date=end_date,
                total_period_working_days=total_period_working_days,
                range_working_days=range_working_days,
                total_present_days=present_days,
                total_half_days=half_days,
                total_leave_days=leave_days,
                total_effective_days=effective_days,
                total_lop_days=lop_days,
                total_gross=Decimal('0.00'),
                blended_basic_salary=Decimal('0.00'),
                last_drawn_basic=Decimal('0.00'),
                is_segmented=False,
                segments=[seg],
                snapshot={
                    'is_segmented': False,
                    'segments_count': 1,
                    'total_gross': '0.00',
                    'blended_basic_salary': '0.00',
                    'last_drawn_basic': '0.00',
                    'total_effective_days': str(effective_days),
                    'total_lop_days': str(lop_days),
                    'segments': [seg.to_snapshot()],
                },
            )

        raw_segments = cls.get_effective_compensation_segments(employee, start_date, end_date)

        segment_results: List[SalarySegmentResult] = []

        for idx, (seg_start, seg_end, record) in enumerate(raw_segments, start=1):
            seg_working_days = (
                _working_days_in_period(branch_id, seg_start, seg_end) if branch_id else 0
            )

            # Attendance within this segment
            att_records = Attendance.objects.filter(
                employee=employee,
                date__range=[seg_start, seg_end],
            )
            present_days = att_records.filter(status='present').count()
            half_days = att_records.filter(status='half_day').count()
            present_dates = set(att_records.filter(status='present').values_list('date', flat=True))

            # Approved leave within this segment (deduplicated against present days)
            leave_days = _approved_leave_days(
                employee, seg_start, seg_end, exclude_dates=present_dates
            )

            calc_effective = (
                Decimal(present_days)
                + Decimal(half_days) * Decimal('0.5')
                + Decimal(leave_days)
            )
            effective_days = (
                min(Decimal(seg_working_days), calc_effective)
                if seg_working_days > 0
                else Decimal('0.00')
            )
            lop_days = max(Decimal('0.0'), Decimal(seg_working_days) - effective_days)

            # Multipliers
            if total_period_working_days > 0:
                attendance_multiplier = effective_days / Decimal(total_period_working_days)
                working_ratio = Decimal(seg_working_days) / Decimal(total_period_working_days)
            else:
                attendance_multiplier = Decimal('0.00')
                working_ratio = Decimal('0.00')

            basic_rate = record.basic_salary
            basic_earned = (basic_rate * attendance_multiplier).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

            # Salary structure & component resolution
            structure = record.salary_structure
            components: List[Dict[str, Any]] = []
            gross_earned = Decimal('0.00')

            if structure:
                struct_comps = list(
                    structure.components.select_related('component').filter(component__is_active=True)
                )
                if struct_comps:
                    comp_defs = []
                    comp_map = {}
                    for ssc in struct_comps:
                        c = ssc.component
                        calc_type = ssc.override_calculation_type or c.calculation_type
                        expr = ssc.override_formula_expression or c.formula_expression
                        comp_defs.append({
                            'code': c.code,
                            'formula_expression': expr,
                            'calculation_type': calc_type,
                        })
                        comp_map[c.code] = (ssc, c, calc_type, expr)

                    try:
                        resolver = ComponentDependencyResolver(
                            provided_variables={'BASIC', 'GROSS', 'ATTENDANCE_MULTIPLIER'}
                        )
                        sorted_codes = resolver.resolve_order(comp_defs)
                    except DependencyError as e:
                        raise SalarySegmentationError(
                            f"Dependency error in salary structure '{structure.name}': {str(e)}"
                        )

                    allowed_vars = {'BASIC', 'GROSS', 'ATTENDANCE_MULTIPLIER'} | set(comp_map.keys())
                    evaluator = SafeFormulaEvaluator(allowed_variables=allowed_vars)
                    eval_context = {
                        'BASIC': basic_rate,
                        'ATTENDANCE_MULTIPLIER': attendance_multiplier,
                    }

                    has_basic_component = any(code == 'BASIC' for code in comp_map)
                    if not has_basic_component:
                        gross_earned = basic_earned
                        components.append({
                            'code': 'BASIC',
                            'name': 'Basic Salary',
                            'kind': 'earning',
                            'calculation_type': 'base',
                            'base_rate': str(basic_rate),
                            'earned_amount': str(basic_earned),
                            'is_prorated': True,
                        })

                    for code in sorted_codes:
                        ssc, c, calc_type, expr = comp_map[code]
                        if code == 'BASIC':
                            base_amount = basic_rate
                            earned_amount = basic_earned
                        elif calc_type == 'flat':
                            base_amount = (
                                ssc.amount
                                if ssc.amount > Decimal('0.00')
                                else (Decimal(expr.strip()) if expr and expr.strip() else Decimal('0.00'))
                            )
                            earned_amount = (
                                (base_amount * attendance_multiplier).quantize(
                                    Decimal('0.01'), rounding=ROUND_HALF_UP
                                )
                                if c.is_prorated
                                else (base_amount * working_ratio).quantize(
                                    Decimal('0.01'), rounding=ROUND_HALF_UP
                                )
                            )
                        elif calc_type == 'percentage':
                            pct_str = expr.replace('%', '').strip() if expr else '0'
                            try:
                                pct_val = Decimal(pct_str)
                                if pct_val > 1:
                                    pct_val = pct_val / Decimal('100')
                            except Exception:
                                pct_val = Decimal('0.00')
                            base_amount = (basic_rate * pct_val).quantize(
                                Decimal('0.01'), rounding=ROUND_HALF_UP
                            )
                            earned_amount = (
                                (base_amount * attendance_multiplier).quantize(
                                    Decimal('0.01'), rounding=ROUND_HALF_UP
                                )
                                if c.is_prorated
                                else (base_amount * working_ratio).quantize(
                                    Decimal('0.01'), rounding=ROUND_HALF_UP
                                )
                            )
                        elif calc_type == 'formula':
                            try:
                                base_amount = evaluator.evaluate(expr, eval_context).quantize(
                                    Decimal('0.01'), rounding=ROUND_HALF_UP
                                )
                            except FormulaError as fe:
                                raise SalarySegmentationError(
                                    f"Formula error evaluating component '{code}': {str(fe)}"
                                )
                            earned_amount = (
                                (base_amount * attendance_multiplier).quantize(
                                    Decimal('0.01'), rounding=ROUND_HALF_UP
                                )
                                if c.is_prorated
                                else (base_amount * working_ratio).quantize(
                                    Decimal('0.01'), rounding=ROUND_HALF_UP
                                )
                            )
                        else:
                            base_amount = Decimal('0.00')
                            earned_amount = Decimal('0.00')

                        eval_context[code] = base_amount

                        if c.kind == 'earning':
                            gross_earned += earned_amount

                        components.append({
                            'code': c.code,
                            'name': c.name,
                            'kind': c.kind,
                            'calculation_type': calc_type,
                            'formula_expression': expr,
                            'base_rate': str(base_amount),
                            'earned_amount': str(earned_amount),
                            'is_prorated': c.is_prorated,
                        })
                else:
                    gross_earned = basic_earned
                    components.append({
                        'code': 'BASIC',
                        'name': 'Basic Salary',
                        'kind': 'earning',
                        'calculation_type': 'base',
                        'base_rate': str(basic_rate),
                        'earned_amount': str(basic_earned),
                        'is_prorated': True,
                    })
            else:
                gross_earned = basic_earned
                components.append({
                    'code': 'BASIC',
                    'name': 'Basic Salary',
                    'kind': 'earning',
                    'calculation_type': 'base',
                    'base_rate': str(basic_rate),
                    'earned_amount': str(basic_earned),
                    'is_prorated': True,
                })

            seg_res = SalarySegmentResult(
                segment_index=idx,
                start_date=seg_start,
                end_date=seg_end,
                compensation_history_id=record.id,
                basic_salary=basic_rate,
                salary_structure_id=structure.id if structure else None,
                salary_structure_name=structure.name if structure else None,
                working_days=seg_working_days,
                present_days=present_days,
                half_days=half_days,
                leave_days=leave_days,
                effective_days=effective_days,
                lop_days=lop_days,
                proration_denominator=total_period_working_days,
                basic_earned=basic_earned,
                gross_earned=gross_earned,
                components=components,
            )
            segment_results.append(seg_res)

        # Aggregate across segments
        range_working_days = sum(s.working_days for s in segment_results)
        total_present_days = sum(s.present_days for s in segment_results)
        total_half_days = sum(s.half_days for s in segment_results)
        total_leave_days = sum(s.leave_days for s in segment_results)
        total_effective_days = sum(s.effective_days for s in segment_results)
        total_lop_days = sum(s.lop_days for s in segment_results)
        total_gross = sum(s.gross_earned for s in segment_results)
        is_segmented = len(segment_results) > 1

        if is_segmented and total_period_working_days > 0:
            blended_basic = (
                sum(s.basic_salary * Decimal(s.working_days) for s in segment_results)
                / Decimal(total_period_working_days)
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            blended_basic = segment_results[-1].basic_salary

        last_drawn_basic = segment_results[-1].basic_salary

        snapshot = {
            'employee_id': employee.id,
            'employee_code': employee.employee_code,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'total_period_working_days': total_period_working_days,
            'range_working_days': range_working_days,
            'total_present_days': total_present_days,
            'total_half_days': total_half_days,
            'total_leave_days': total_leave_days,
            'total_effective_days': str(total_effective_days),
            'total_lop_days': str(total_lop_days),
            'total_gross': str(total_gross),
            'blended_basic_salary': str(blended_basic),
            'last_drawn_basic': str(last_drawn_basic),
            'is_segmented': is_segmented,
            'segments_count': len(segment_results),
            'segments': [s.to_snapshot() for s in segment_results],
        }

        return SalarySegmentationSummary(
            employee_id=employee.id,
            employee_code=employee.employee_code,
            start_date=start_date,
            end_date=end_date,
            total_period_working_days=total_period_working_days,
            range_working_days=range_working_days,
            total_present_days=total_present_days,
            total_half_days=total_half_days,
            total_leave_days=total_leave_days,
            total_effective_days=total_effective_days,
            total_lop_days=total_lop_days,
            total_gross=total_gross,
            blended_basic_salary=blended_basic,
            last_drawn_basic=last_drawn_basic,
            is_segmented=is_segmented,
            segments=segment_results,
            snapshot=snapshot,
        )
