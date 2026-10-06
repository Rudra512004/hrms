from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.attendance.models import Attendance
from apps.organization.models import Organization, Branch, WorkingCalendar
from apps.employees.models import Employee, EmployeeStatutoryInfo
from apps.payroll.models import (
    PayrollRun,
    PayrollRecord,
    PayrollLineItem,
    CompensationHistory,
    SalaryComponent,
    SalaryStructure,
    SalaryStructureComponent,
    StatutoryRule
)
from apps.payroll.services import generate_payroll_for_period
from apps.payroll.statutory_services import StatutoryService

User = get_user_model()

class Phase7StatutoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Base setup
        cls.org1 = Organization.objects.create(name="Phase 7 Org")
        cls.branch1 = Branch.objects.create(organization=cls.org1, name="Branch 7")
        cls.calendar = WorkingCalendar.objects.get(branch=cls.branch1)
        cls.calendar.work_days = "0,1,2,3,4" # Mon-Fri
        cls.calendar.save()

        # Employee 1
        cls.user1 = User.objects.create(first_name="John", email="john@p7.com")
        cls.emp1 = Employee.objects.create(
            user=cls.user1,
            organization=cls.org1,
            branch=cls.branch1,
            employee_code="EMP-P7-01",
            joining_date=date(2026, 1, 1),
            employment_status='active',
            state='MH'
        )
        
        # Statutory Rules
        StatutoryRule.objects.create(
            rule_type='PF',
            effective_from=date(2025, 1, 1),
            employee_rate=Decimal('12.00'),
            employer_rate=Decimal('13.00'),
            applicable_limit=Decimal('15000.00')
        )
        StatutoryRule.objects.create(
            rule_type='ESI',
            effective_from=date(2025, 1, 1),
            employee_rate=Decimal('0.75'),
            employer_rate=Decimal('3.25'),
            applicable_limit=Decimal('21000.00')
        )
        StatutoryRule.objects.create(
            rule_type='PT',
            state='MH',
            effective_from=date(2025, 1, 1),
            rule_metadata={
                'slabs': [
                    {'gender': 'Male', 'min': 0, 'max': 7500, 'amount': 0},
                    {'gender': 'Male', 'min': 7500, 'max': 10000, 'amount': 175},
                    {'gender': 'Male', 'min': 10000, 'max': None, 'amount': 200, 'feb_amount': 250},
                ]
            }
        )
        
        # Salary Structure
        cls.comp_basic = SalaryComponent.objects.create(organization=cls.org1, name="Basic", code="basic", kind="earning")
        cls.struct = SalaryStructure.objects.create(organization=cls.org1, name="Standard")
        SalaryStructureComponent.objects.create(structure=cls.struct, component=cls.comp_basic, calculation_type='FIXED_AMOUNT', amount=Decimal('20000.00'))
        
        CompensationHistory.objects.create(
            employee=cls.emp1,
            effective_from=date(2026, 1, 1),
            salary_structure=cls.struct,
            basic_salary=Decimal('20000.00')
        )

    def test_pf_calculation_correctness(self):
        stat_info, _ = EmployeeStatutoryInfo.objects.get_or_create(employee=self.emp1)
        stat_info.pf_wage_cap = Decimal('15000.00')
        stat_info.save()

        # Generate Payroll for Jan 2026
        # Mark Attendance
        for day in range(1, 32):
            dt = date(2026, 1, day)
            if dt.weekday() < 5:  # Mon-Fri
                Attendance.objects.create(employee=self.emp1, date=dt, status='present')
                
        run = PayrollRun.objects.create(
            organization=self.org1,
            year=2026,
            month=1,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31)
        )
        generate_payroll_for_period(run)
        
        record = run.records.get(employee=self.emp1)
        pf_emp = record.line_items.get(calculation_type='STATUTORY_PF_EMPLOYEE')
        pf_empr = record.line_items.get(calculation_type='STATUTORY_PF_EMPLOYER')
        
        self.assertEqual(pf_emp.amount, Decimal('1800.00')) # 12% of 15000
        self.assertEqual(pf_empr.amount, Decimal('1950.00')) # 13% of 15000
        
    def test_esi_eligibility_cap(self):
        # Gross salary is 20000 (Basic), which is <= 21000. So ESI should apply.
        stat_info, _ = EmployeeStatutoryInfo.objects.get_or_create(employee=self.emp1)
        
        for day in range(1, 32):
            dt = date(2026, 1, day)
            if dt.weekday() < 5:  # Mon-Fri
                Attendance.objects.create(employee=self.emp1, date=dt, status='present')
                
        run = PayrollRun.objects.create(
            organization=self.org1,
            year=2026,
            month=1,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31)
        )
        generate_payroll_for_period(run)
        
        record = run.records.get(employee=self.emp1)
        esi_emp = record.line_items.filter(calculation_type='STATUTORY_ESI_EMPLOYEE').first()
        
        # 0.75% of 20000 = 150
        self.assertIsNotNone(esi_emp)
        self.assertEqual(esi_emp.amount, Decimal('150.00'))
        
    def test_pt_calculation(self):
        self.emp1.gender = 'Male'
        self.emp1.save()
        
        for day in range(1, 32):
            dt = date(2026, 1, day)
            if dt.weekday() < 5:  # Mon-Fri
                Attendance.objects.create(employee=self.emp1, date=dt, status='present')
                
        run = PayrollRun.objects.create(
            organization=self.org1,
            year=2026,
            month=1, # Not Feb
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31)
        )
        generate_payroll_for_period(run)
        record = run.records.get(employee=self.emp1)
        pt = record.line_items.get(calculation_type='STATUTORY_PT')
        self.assertEqual(pt.amount, Decimal('200.00'))
        
        for day in range(1, 29):
            dt = date(2026, 2, day)
            if dt.weekday() < 5:  # Mon-Fri
                Attendance.objects.create(employee=self.emp1, date=dt, status='present')
                
        run_feb = PayrollRun.objects.create(
            organization=self.org1,
            year=2026,
            month=2, # Feb
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28)
        )
        generate_payroll_for_period(run_feb)
        record_feb = run_feb.records.get(employee=self.emp1)
        pt_feb = record_feb.line_items.get(calculation_type='STATUTORY_PT')
        self.assertEqual(pt_feb.amount, Decimal('250.00'))

    def test_effective_dates_and_historical_reproducibility(self):
        stat_info, _ = EmployeeStatutoryInfo.objects.get_or_create(employee=self.emp1)
        stat_info.pf_wage_cap = Decimal('15000.00')
        stat_info.save()
        
        for day in range(1, 32):
            dt = date(2026, 1, day)
            if dt.weekday() < 5:
                Attendance.objects.create(employee=self.emp1, date=dt, status='present')
                
        run = PayrollRun.objects.create(
            organization=self.org1,
            year=2026,
            month=1,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31)
        )
        generate_payroll_for_period(run)
        
        # Update PF rule effective March 2026
        StatutoryRule.objects.create(
            rule_type='PF',
            effective_from=date(2026, 3, 1),
            employee_rate=Decimal('10.00'), # Reduced to 10%
            employer_rate=Decimal('10.00'),
            applicable_limit=Decimal('15000.00')
        )
        
        # Re-run January payroll (Draft)
        generate_payroll_for_period(run)
        record = run.records.get(employee=self.emp1)
        pf_emp = record.line_items.get(calculation_type='STATUTORY_PF_EMPLOYEE')
        
        # Should still use old rule (12%)
        self.assertEqual(pf_emp.amount, Decimal('1800.00'))
        
        for day in range(1, 32):
            dt = date(2026, 3, day)
            if dt.weekday() < 5:  # Mon-Fri
                Attendance.objects.create(employee=self.emp1, date=dt, status='present')
                
        # Run March payroll
        run_mar = PayrollRun.objects.create(
            organization=self.org1,
            year=2026,
            month=3,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31)
        )
        generate_payroll_for_period(run_mar)
        record_mar = run_mar.records.get(employee=self.emp1)
        pf_emp_mar = record_mar.line_items.get(calculation_type='STATUTORY_PF_EMPLOYEE')
        
        # Should use new rule (10% of 15000 = 1500)
        self.assertEqual(pf_emp_mar.amount, Decimal('1500.00'))

    def test_ctc_simulation_does_not_mutate(self):
        stat_info, _ = EmployeeStatutoryInfo.objects.get_or_create(employee=self.emp1)
        
        # Initial payroll count
        count_before = PayrollRecord.objects.count()
        
        # Run CTC sim
        res = StatutoryService.calculate_ctc(stat_info, date(2026, 1, 31), Decimal('20000.00'), Decimal('20000.00'))
        
        count_after = PayrollRecord.objects.count()
        self.assertEqual(count_before, count_after)
        
        self.assertEqual(res['gross_salary'], Decimal('20000.00'))
        self.assertTrue(res['employer_pf'] > 0)
        self.assertTrue(res['employer_esi'] > 0)
        
        ctc_expected = res['gross_salary'] + res['employer_pf'] + res['employer_esi']
        self.assertEqual(res['ctc'], ctc_expected)
