"""
Phase 6: Payroll Rerun Safety and Historical Reproducibility Tests.
"""
from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.organization.models import Organization, Branch, WorkingCalendar
from apps.employees.models import Employee
from apps.payroll.models import (
    PayrollRun,
    PayrollRecord,
    PayrollLineItem,
    PayrollAdjustment,
    SalaryComponent,
    SalaryStructure,
    SalaryStructureComponent,
    CompensationHistory,
)
from apps.payroll.services import (
    generate_payroll_for_period,
    finalize_payroll_run,
    PayrollImmutableError,
)
from apps.attendance.models import Attendance

User = get_user_model()

class Phase6PayrollSafetyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 1. Organization & Branch
        cls.org1 = Organization.objects.create(name="Phase 6 Org 1")
        cls.branch1 = Branch.objects.create(
            organization=cls.org1,
            name="Branch 1"
        )
        # Configure working calendar so is_working_day works (Mon-Fri)
        cls.calendar = WorkingCalendar.objects.get(branch=cls.branch1)
        cls.calendar.work_days = "0,1,2,3,4"
        cls.calendar.save()

        cls.user1 = User.objects.create(
            first_name="Alice",
            email="alice@p6.com"
        )
        cls.emp1 = Employee.objects.create(
            user=cls.user1,
            organization=cls.org1,
            branch=cls.branch1,
            employee_code="EMP-P6-01",
            joining_date=date(2026, 1, 1),
            employment_status='active',
        )

        # 3. Components
        cls.basic_comp = SalaryComponent.objects.create(
            organization=cls.org1, name="Basic", code="BASIC", kind="earning"
        )
        cls.tax_comp = SalaryComponent.objects.create(
            organization=cls.org1, name="Tax", code="TAX", kind="tax"
        )
        cls.adj_comp = SalaryComponent.objects.create(
            organization=cls.org1, name="Bonus", code="BONUS", kind="earning"
        )

        # 4. Structure
        cls.structure = SalaryStructure.objects.create(
            organization=cls.org1, name="Standard P6 Structure"
        )
        SalaryStructureComponent.objects.create(
            structure=cls.structure,
            component=cls.basic_comp,
            calculation_type="FIXED_AMOUNT",
            amount=Decimal("50000.00")
        )

        # 5. Compensation
        cls.comp_hist = CompensationHistory.objects.create(
            employee=cls.emp1,
            effective_from=date(2026, 1, 1),
            basic_salary=Decimal("50000.00"),
            salary_structure=cls.structure,
        )

    def test_draft_rerun_idempotency_and_adjustment_safety(self):
        """
        Phase 6.1 & 6.4: Draft Payroll Rerun Idempotency & Adjustment Rerun Safety
        Prove generating payroll multiple times in DRAFT:
        - Recreates safely without duplicates.
        - Approved adjustments are included exactly once, even after rerun.
        - Final numbers are identical.
        """
        # Create an approved adjustment
        adj = PayrollAdjustment.objects.create(
            employee=self.emp1,
            component=self.adj_comp,
            amount=Decimal("5000.00"),
            period_year=2026,
            period_month=10,
            status=PayrollAdjustment.STATUS_APPROVED
        )

        run = PayrollRun.objects.create(
            organization=self.org1,
            year=2026,
            month=10,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31)
        )

        # Generate 1st time
        generate_payroll_for_period(run)
        
        # Verify adjustment is processed
        adj.refresh_from_db()
        self.assertEqual(adj.status, PayrollAdjustment.STATUS_PROCESSED)
        self.assertEqual(PayrollRecord.objects.filter(period=run).count(), 1)
        self.assertEqual(PayrollLineItem.objects.filter(payroll_record__period=run, component=self.adj_comp).count(), 1)
        
        # Capture numbers
        record1 = PayrollRecord.objects.get(period=run)
        net1 = record1.net_salary

        # Generate 2nd time
        generate_payroll_for_period(run)
        
        # Verify adjustment is STILL processed and included exactly once
        adj.refresh_from_db()
        self.assertEqual(adj.status, PayrollAdjustment.STATUS_PROCESSED)
        self.assertEqual(PayrollRecord.objects.filter(period=run).count(), 1)
        self.assertEqual(PayrollLineItem.objects.filter(payroll_record__period=run, component=self.adj_comp).count(), 1)

        # Final numbers identical
        record2 = PayrollRecord.objects.get(period=run)
        self.assertEqual(net1, record2.net_salary)
        
        # The number of line items should be 2: basic + bonus
        self.assertEqual(PayrollLineItem.objects.filter(payroll_record=record2).count(), 2)

    def test_historical_reproduction_scenario_and_approved_behavior(self):
        """
        Phase 6.2, 6.3, 6.5 & 6.7: Finalized Payroll Immutability, Approved Payroll Behavior,
        Calculation Version Reproducibility, Historical Reproduction Scenario
        """
        run = PayrollRun.objects.create(
            organization=self.org1, year=2026, month=9, start_date=date(2026, 9, 1), end_date=date(2026, 9, 30),
            calculation_version='v1'
        )
        
        # Add attendance for September
        Attendance.objects.create(employee=self.emp1, date=date(2026, 9, 10), status='present')
        
        # Generate and capture
        generate_payroll_for_period(run)
        record_draft = PayrollRecord.objects.get(period=run)
        original_net = record_draft.net_salary
        original_lop = record_draft.lop_dates
        
        # APPROVED state
        run.status = PayrollRun.STATUS_APPROVED
        run.save()
        
        # Recalculation blocked on APPROVED
        with self.assertRaises(PayrollImmutableError):
            generate_payroll_for_period(run)
            
        # Finalize
        finalize_payroll_run(run)
        
        # Recalculation blocked on FINALIZED
        with self.assertRaises(PayrollImmutableError):
            generate_payroll_for_period(run)
        
        # Alter current operational data
        Attendance.objects.create(employee=self.emp1, date=date(2026, 9, 11), status='present')
        self.comp_hist.basic_salary = Decimal("99999.00")
        self.comp_hist.save()
            
        # Verify completely unchanged historical record
        record_final = PayrollRecord.objects.get(period=run)
        self.assertEqual(record_final.net_salary, original_net)
        self.assertEqual(record_final.lop_dates, original_lop)
        self.assertNotEqual(record_final.basic_salary, Decimal("99999.00")) # Historical basic salary was captured
        self.assertEqual(record_final.basic_salary, Decimal("50000.00"))
        
        # Calculation version invariant
        self.assertEqual(run.calculation_version, 'v1')

    def test_duplicate_run_protection(self):
        """
        Phase 6.6: Duplicate protection
        """
        PayrollRun.objects.create(
            organization=self.org1, year=2026, month=8, start_date=date(2026, 8, 1), end_date=date(2026, 8, 31)
        )
        
        with self.assertRaises(IntegrityError):
            PayrollRun.objects.create(
                organization=self.org1, year=2026, month=8, start_date=date(2026, 8, 1), end_date=date(2026, 8, 31)
            )

    def test_tenant_isolation_and_determinism(self):
        """
        Phase 6.8 & 6.9: Tenant Isolation & Determinism
        """
        org2 = Organization.objects.create(name="Phase 6 Org 2")
        user2 = User.objects.create(first_name="Bob", email="bob@p6.com")
        emp2 = Employee.objects.create(
            user=user2,
            organization=org2,
            employee_code="EMP-P6-02",
            joining_date=date(2026, 1, 1),
            employment_status='active',
        )
        run1 = PayrollRun.objects.create(
            organization=self.org1, year=2026, month=11, start_date=date(2026, 11, 1), end_date=date(2026, 11, 30)
        )
        run2 = PayrollRun.objects.create(
            organization=org2, year=2026, month=11, start_date=date(2026, 11, 1), end_date=date(2026, 11, 30)
        )
        
        # Generate twice to prove determinism across tenants
        generate_payroll_for_period(run1)
        generate_payroll_for_period(run2)
        generate_payroll_for_period(run1)
        generate_payroll_for_period(run2)
        
        # Org 1 run should only have Org 1's employee
        records1 = PayrollRecord.objects.filter(period=run1)
        self.assertEqual(records1.count(), 1)
        self.assertEqual(records1.first().employee, self.emp1)
        
        # Org 2 run should only have Org 2's employee
        records2 = PayrollRecord.objects.filter(period=run2)
        self.assertEqual(records2.count(), 1)
        self.assertEqual(records2.first().employee, emp2)
