from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Optional, Dict, Any
from datetime import date
from django.db.models import Q

from apps.payroll.models import StatutoryRule
from apps.employees.models import EmployeeStatutoryInfo

class StatutoryService:
    @staticmethod
    def get_effective_rule(rule_type: str, target_date: date, organization_id: int = None, state: str = None) -> Optional[StatutoryRule]:
        """
        Fetches the active statutory rule for the target date.
        Tenant-scoped rules override global rules.
        """
        qs = StatutoryRule.objects.filter(
            rule_type=rule_type,
            effective_from__lte=target_date,
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=target_date)
        )
        if state:
            qs = qs.filter(state=state)
        
        tenant_rules = []
        global_rules = []
        
        for rule in qs:
            if rule.organization_id == organization_id:
                tenant_rules.append(rule)
            elif rule.organization_id is None:
                global_rules.append(rule)
                
        valid_rules = tenant_rules if tenant_rules else global_rules
        if not valid_rules:
            return None
            
        valid_rules.sort(key=lambda r: r.effective_from, reverse=True)
        return valid_rules[0]

    @staticmethod
    def calculate_pf(
        employee_stat_info: EmployeeStatutoryInfo, 
        target_date: date, 
        earned_basic: Decimal,
    ) -> Dict[str, Any]:
        if not employee_stat_info.is_pf_applicable:
            return {
                'employee_pf': Decimal('0.00'),
                'employer_pf': Decimal('0.00'),
                'is_applicable': False,
                'metadata': {'reason': 'Employee not covered by PF'}
            }
            
        rule = StatutoryService.get_effective_rule('PF', target_date, employee_stat_info.employee.organization_id)
        if not rule:
            return {
                'employee_pf': Decimal('0.00'),
                'employer_pf': Decimal('0.00'),
                'is_applicable': False,
                'metadata': {'reason': 'No active PF rule found for date'}
            }
            
        pf_limit = employee_stat_info.pf_wage_cap if employee_stat_info.pf_wage_cap is not None else rule.applicable_limit
        
        employee_pf_base = earned_basic
        employer_pf_base = earned_basic
        
        if pf_limit:
            employee_pf_base = min(earned_basic, pf_limit)
            if employee_stat_info.employer_pf_capped:
                employer_pf_base = min(earned_basic, pf_limit)
                
        employee_rate = rule.employee_rate
        employer_rate = rule.employer_rate
        vpf_rate = employee_stat_info.vpf_percentage or Decimal('0.00')
        
        total_employee_rate = employee_rate + vpf_rate
        
        employee_pf = (employee_pf_base * (total_employee_rate / Decimal('100'))).quantize(Decimal('1.'), rounding=ROUND_HALF_UP).quantize(Decimal('0.01'))
        employer_pf = (employer_pf_base * (employer_rate / Decimal('100'))).quantize(Decimal('1.'), rounding=ROUND_HALF_UP).quantize(Decimal('0.01'))
        
        return {
            'employee_pf': employee_pf,
            'employer_pf': employer_pf,
            'is_applicable': True,
            'metadata': {
                'rule_id': rule.id,
                'effective_from': str(rule.effective_from),
                'employee_base': str(employee_pf_base),
                'employer_base': str(employer_pf_base),
                'employee_rate': str(employee_rate),
                'vpf_rate': str(vpf_rate),
                'employer_rate': str(employer_rate),
                'cap_applied': str(pf_limit) if pf_limit else None,
            }
        }

    @staticmethod
    def calculate_esi(
        employee_stat_info: EmployeeStatutoryInfo, 
        target_date: date, 
        gross_salary: Decimal,
        earned_gross: Decimal
    ) -> Dict[str, Any]:
        if not employee_stat_info.is_esi_applicable:
            return {
                'employee_esi': Decimal('0.00'),
                'employer_esi': Decimal('0.00'),
                'is_applicable': False,
                'metadata': {'reason': 'Employee not covered by ESI'}
            }
            
        rule = StatutoryService.get_effective_rule('ESI', target_date, employee_stat_info.employee.organization_id)
        if not rule:
            return {
                'employee_esi': Decimal('0.00'),
                'employer_esi': Decimal('0.00'),
                'is_applicable': False,
                'metadata': {'reason': 'No active ESI rule found for date'}
            }
            
        if rule.applicable_limit and gross_salary > rule.applicable_limit:
             return {
                'employee_esi': Decimal('0.00'),
                'employer_esi': Decimal('0.00'),
                'is_applicable': False,
                'metadata': {'reason': f'Gross salary {gross_salary} exceeds ESI limit {rule.applicable_limit}'}
            }
            
        employee_esi = Decimal(math.ceil(earned_gross * (rule.employee_rate / Decimal('100')))).quantize(Decimal('0.01'))
        employer_esi = Decimal(math.ceil(earned_gross * (rule.employer_rate / Decimal('100')))).quantize(Decimal('0.01'))
        
        return {
            'employee_esi': employee_esi,
            'employer_esi': employer_esi,
            'is_applicable': True,
            'metadata': {
                'rule_id': rule.id,
                'effective_from': str(rule.effective_from),
                'base': str(earned_gross),
                'employee_rate': str(rule.employee_rate),
                'employer_rate': str(rule.employer_rate),
                'limit_checked': str(rule.applicable_limit)
            }
        }
        
    @staticmethod
    def calculate_pt(
        employee_stat_info: EmployeeStatutoryInfo, 
        target_date: date, 
        earned_gross: Decimal
    ) -> Dict[str, Any]:
        if not employee_stat_info.is_pt_applicable:
            return {
                'employee_pt': Decimal('0.00'),
                'is_applicable': False,
                'metadata': {'reason': 'Employee not covered by PT'}
            }
            
        state = employee_stat_info.employee.state
        if not state:
            return {
                'employee_pt': Decimal('0.00'),
                'is_applicable': False,
                'metadata': {'reason': 'Employee has no state assigned for PT'}
            }
            
        rule = StatutoryService.get_effective_rule('PT', target_date, employee_stat_info.employee.organization_id, state)
        if not rule:
            return {
                'employee_pt': Decimal('0.00'),
                'is_applicable': False,
                'metadata': {'reason': f'No PT rule found for state {state}'}
            }
            
        gender = employee_stat_info.employee.gender or 'All'
        slabs = rule.rule_metadata.get('slabs', [])
        
        pt_amount = Decimal('0.00')
        slab_matched = None
        
        for slab in slabs:
            slab_gender = slab.get('gender', 'All')
            if slab_gender != 'All' and slab_gender != gender:
                continue
                
            min_val = Decimal(str(slab.get('min', 0)))
            max_val = slab.get('max')
            max_val = Decimal(str(max_val)) if max_val is not None else None
            
            if min_val <= earned_gross and (max_val is None or earned_gross <= max_val):
                slab_matched = slab
                if target_date.month == 2 and 'feb_amount' in slab:
                    pt_amount = Decimal(str(slab['feb_amount'])).quantize(Decimal('0.01'))
                else:
                    pt_amount = Decimal(str(slab.get('amount', 0))).quantize(Decimal('0.01'))
                break
                
        return {
            'employee_pt': pt_amount,
            'is_applicable': True,
            'metadata': {
                'rule_id': rule.id,
                'state': state,
                'base': str(earned_gross),
                'gender': gender,
                'slab_matched': slab_matched
            }
        }
        
    @staticmethod
    def calculate_tds(
        employee_stat_info: EmployeeStatutoryInfo,
        target_date: date,
        earned_gross: Decimal
    ) -> Dict[str, Any]:
        return {
            'employee_tds': Decimal('0.00'),
            'is_applicable': False,
            'metadata': {'reason': 'Full Annualized TDS is explicitly unsupported in Phase 7.'}
        }

    @staticmethod
    def calculate_ctc(employee_stat_info: EmployeeStatutoryInfo, target_date: date, basic_salary: Decimal, gross_salary: Decimal) -> Dict[str, Any]:
        """
        Calculates theoretical monthly CTC.
        CTC = Gross Salary + Employer PF + Employer ESI
        """
        pf_result = StatutoryService.calculate_pf(employee_stat_info, target_date, basic_salary)
        esi_result = StatutoryService.calculate_esi(employee_stat_info, target_date, gross_salary, gross_salary)
        
        employer_pf = pf_result['employer_pf'] if pf_result['is_applicable'] else Decimal('0.00')
        employer_esi = esi_result['employer_esi'] if esi_result['is_applicable'] else Decimal('0.00')
        
        ctc = gross_salary + employer_pf + employer_esi
        
        return {
            'gross_salary': gross_salary,
            'employer_pf': employer_pf,
            'employer_esi': employer_esi,
            'ctc': ctc
        }
