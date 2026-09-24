from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR, ROUND_CEILING
from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import date
import calendar

from apps.leaves.models import (
    LeaveType, BranchLeavePolicy, LeaveCycle,
    LeaveBalance, LeaveBalanceTransaction
)
from apps.employees.models import Employee


class LeaveAllocationEngine:
    @classmethod
    def apply_rounding(cls, value: Decimal, rounding_mode: str) -> Decimal:
        if rounding_mode == 'nearest_half':
            return (value * Decimal('2')).quantize(Decimal('1'), rounding=ROUND_HALF_UP) / Decimal('2')
        elif rounding_mode == 'floor':
            return value.quantize(Decimal('1'), rounding=ROUND_FLOOR)
        elif rounding_mode == 'ceiling':
            return value.quantize(Decimal('1'), rounding=ROUND_CEILING)
        return value

    @classmethod
    @transaction.atomic
    def process_monthly_allocation(cls, branch, leave_cycle, year: int, month: int, actor=None) -> dict:
        first_day_of_month = date(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        last_day_of_month = date(year, month, last_day)

        if first_day_of_month > leave_cycle.end_date or last_day_of_month < leave_cycle.start_date:
            raise ValidationError("Target month is outside the active leave cycle boundaries.")

        policies = BranchLeavePolicy.objects.filter(branch=branch).select_related('leave_type')
        employees = Employee.objects.filter(
            branch=branch,
            employment_status__in=['active', 'onboarding'],
            joining_date__lte=last_day_of_month
        )

        allocation_period = f"{year}-{month:02d}"
        results = {
            'allocated': 0,
            'skipped_idempotent': 0,
        }

        for employee in employees:
            for policy in policies:
                if policy.leave_type.organization_id != employee.organization_id:
                    continue

                ref = f"ALLOC-{allocation_period}-{leave_cycle.id}"
                if LeaveBalanceTransaction.objects.filter(
                    employee=employee,
                    leave_type=policy.leave_type,
                    leave_cycle=leave_cycle,
                    reference=ref
                ).exists():
                    results['skipped_idempotent'] += 1
                    continue

                joined_this_cycle = employee.joining_date >= leave_cycle.start_date
                joined_this_month = (employee.joining_date.year == year and 
                                     employee.joining_date.month == month)
                
                amount_to_allocate = policy.monthly_allocation

                if not policy.proration_enabled and joined_this_month and joined_this_cycle:
                    missed_months = (year - leave_cycle.start_date.year) * 12 + (month - leave_cycle.start_date.month)
                    amount_to_allocate = policy.monthly_allocation * Decimal(missed_months + 1)
                elif policy.proration_enabled and joined_this_month:
                    amount_to_allocate = policy.monthly_allocation

                amount_to_allocate = cls.apply_rounding(amount_to_allocate, policy.proration_rounding)

                if amount_to_allocate <= 0:
                    continue

                balance, _ = LeaveBalance.objects.get_or_create(
                    employee=employee,
                    leave_type=policy.leave_type,
                    leave_cycle=leave_cycle,
                    defaults={'branch': branch}
                )

                balance = LeaveBalance.objects.select_for_update().get(pk=balance.pk)
                balance.allocated += amount_to_allocate
                balance.save(update_fields=['allocated'])

                LeaveBalanceTransaction.objects.create(
                    balance=balance,
                    employee=employee,
                    leave_type=policy.leave_type,
                    leave_cycle=leave_cycle,
                    actor=actor,
                    transaction_type='monthly_accrual',
                    amount=amount_to_allocate,
                    effective_date=last_day_of_month,
                    reference=ref
                )
                results['allocated'] += 1

        return results
