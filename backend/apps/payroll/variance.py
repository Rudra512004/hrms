from decimal import Decimal
from typing import List, Dict, Any, Optional

from .models import PayrollRun, PayrollRecord

class VarianceCause:
    def __init__(self, code: str, amount_change: Decimal, description: str, evidence: Dict[str, Any] = None):
        self.code = code
        self.amount_change = amount_change
        self.description = description
        self.evidence = evidence or {}

    def as_dict(self):
        return {
            'code': self.code,
            'amount_change': str(self.amount_change),
            'description': self.description,
            'evidence': self.evidence,
        }

class EmployeeVariance:
    def __init__(self, current_record: PayrollRecord, previous_record: Optional[PayrollRecord]):
        self.current_record = current_record
        self.previous_record = previous_record
        self.causes: List[VarianceCause] = []
        
        self.current_net = current_record.net_salary
        if previous_record:
            self.previous_net = previous_record.net_salary
            self.net_variance = self.current_net - self.previous_net
            if self.previous_net > 0:
                self.net_variance_pct = (self.net_variance / self.previous_net) * Decimal('100')
            else:
                self.net_variance_pct = Decimal('0')
        else:
            self.previous_net = Decimal('0')
            self.net_variance = self.current_net
            self.net_variance_pct = Decimal('0') # Special case for new employees
            
    def analyze(self):
        if not self.previous_record:
            self.causes.append(VarianceCause(
                code='NEW_EMPLOYEE_OR_FIRST_PAYROLL',
                amount_change=self.net_variance,
                description="No previous comparable payroll record found.",
                evidence={'current_net': str(self.current_net)}
            ))
            return
            
        # Compare Basic Salary
        if self.current_record.basic_salary != self.previous_record.basic_salary:
            diff = self.current_record.basic_salary - self.previous_record.basic_salary
            self.causes.append(VarianceCause(
                code='SALARY_CHANGE',
                amount_change=diff, # Note: this is basic salary diff
                description=f"Basic salary changed from {self.previous_record.basic_salary} to {self.current_record.basic_salary}",
                evidence={'prev_basic': str(self.previous_record.basic_salary), 'curr_basic': str(self.current_record.basic_salary)}
            ))
            
        # Compare LOP
        curr_lop = self.current_record.lop_amount
        prev_lop = self.previous_record.lop_amount
        if curr_lop != prev_lop:
            diff = prev_lop - curr_lop # If LOP increases, net pay goes down, so diff is negative
            self.causes.append(VarianceCause(
                code='LOP_CHANGE',
                amount_change=diff,
                description=f"LOP deduction changed from {prev_lop} to {curr_lop}",
                evidence={
                    'prev_lop': str(prev_lop), 
                    'curr_lop': str(curr_lop), 
                    'prev_lop_days': str(self.previous_record.lop_days), 
                    'curr_lop_days': str(self.current_record.lop_days)
                }
            ))
            
        # Compare other line items grouped by component/category
        curr_items = { (li.category, li.component_id, li.calculation_type): li for li in self.current_record.line_items.all() }
        prev_items = { (li.category, li.component_id, li.calculation_type): li for li in self.previous_record.line_items.all() }
        
        all_keys = set(curr_items.keys()).union(set(prev_items.keys()))
        for key in all_keys:
            cat, comp_id, calc_type = key
            curr_amt = curr_items[key].amount if key in curr_items else Decimal('0')
            prev_amt = prev_items[key].amount if key in prev_items else Decimal('0')
            
            if curr_amt != prev_amt:
                diff = curr_amt - prev_amt
                
                # If it's a deduction/tax, increase in amount means DECREASE in net pay
                if cat in ['DEDUCTION', 'TAX']:
                    effect = -diff
                elif cat == 'EARNING':
                    # Skip EARNING changes if they are just basic salary changes (already tracked) or LOP prorations (already tracked)
                    # We will only track if it's a new component or removed component
                    if (curr_amt > 0 and prev_amt == 0) or (curr_amt == 0 and prev_amt > 0):
                         effect = diff
                    else:
                         continue # Earning changes handled by salary & LOP change above to avoid double counting
                else:
                    # Employer contribution doesn't affect net pay directly
                    effect = Decimal('0')
                    
                if effect != Decimal('0'):
                    if calc_type and 'STATUTORY' in calc_type:
                        self.causes.append(VarianceCause(
                            code='STATUTORY_CHANGE',
                            amount_change=effect,
                            description=f"Statutory {calc_type} changed",
                            evidence={'category': cat, 'prev_amount': str(prev_amt), 'curr_amount': str(curr_amt)}
                        ))
                    elif calc_type == 'ADJUSTMENT':
                        self.causes.append(VarianceCause(
                            code='ADJUSTMENT_CHANGE',
                            amount_change=effect,
                            description=f"Adjustment changed",
                            evidence={'category': cat, 'prev_amount': str(prev_amt), 'curr_amount': str(curr_amt)}
                        ))
                    elif cat == 'EARNING':
                         self.causes.append(VarianceCause(
                            code='EARNING_COMPONENT_CHANGE',
                            amount_change=effect,
                            description=f"Earning component {comp_id} changed",
                            evidence={'category': cat, 'prev_amount': str(prev_amt), 'curr_amount': str(curr_amt)}
                        ))

    def as_dict(self):
        return {
            'employee_id': self.current_record.employee_id,
            'employee_code': self.current_record.employee.employee_code,
            'current_net': str(self.current_net),
            'previous_net': str(self.previous_net),
            'net_variance': str(self.net_variance),
            'net_variance_pct': str(self.net_variance_pct),
            'causes': [c.as_dict() for c in self.causes]
        }

class PayrollVarianceEngine:
    def __init__(self, current_run: PayrollRun):
        self.current_run = current_run
        
    def analyze(self) -> Dict[str, Any]:
        from django.db.models import Q
        
        prev_run = PayrollRun.objects.filter(
            organization=self.current_run.organization,
            run_type=self.current_run.run_type,
            status__in=[PayrollRun.STATUS_APPROVED, PayrollRun.STATUS_FINALIZED]
        ).filter(
            Q(year__lt=self.current_run.year) | Q(year=self.current_run.year, month__lt=self.current_run.month)
        ).order_by('-year', '-month').first()
        
        curr_records = {r.employee_id: r for r in self.current_run.records.select_related('employee').prefetch_related('line_items')}
        prev_records = {}
        if prev_run:
            prev_records = {r.employee_id: r for r in prev_run.records.select_related('employee').prefetch_related('line_items')}
            
        results = []
        for emp_id, curr_rec in curr_records.items():
            prev_rec = prev_records.get(emp_id)
            ev = EmployeeVariance(curr_rec, prev_rec)
            ev.analyze()
            results.append(ev.as_dict())
            
        return {
            'run_id': self.current_run.id,
            'previous_run_id': prev_run.id if prev_run else None,
            'employee_variances': results
        }
