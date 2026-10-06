from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.models import ProtectedError

from apps.organization.models import Organization, Branch
from apps.employees.models import Employee, EmploymentStatus
from apps.attendance.models import Attendance
from apps.leaves.models import LeaveType, LeaveRequest
from apps.payroll.models import (
    CompensationHistory,
    PayrollRun,
    PayrollRecord,
    PayrollLineItem,
    SalaryComponent,
    SalaryStructure,
    SalaryStructureComponent,
    PayrollAdjustment,
)
from apps.payroll.services import (
    generate_payroll_for_period,
    finalize_payroll_run,
    PayrollImmutableError,
)

User = get_user_model()


class Phase5PayrollLineageTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Phase 5 Org')
        self.branch = Branch.objects.create(organization=self.org, name='HQ Branch')
        self.user = User.objects.create_user(
            email='emp5@example.com',
            password='password123',
            first_name='Phase5',
            last_name='Emp',
            status='active'
        )
        self.employee = Employee.objects.create(
            user=self.user,
            organization=self.org,
            branch=self.branch,
            employee_code='EMP-P5-001',
            employment_status=EmploymentStatus.ACTIVE,
        )

        # Salary Components
        self.basic_comp = SalaryComponent.objects.create(
            organization=self.org, name='Basic Pay', code='BASIC', kind='earning'
        )
        self.hra_comp = SalaryComponent.objects.create(
            organization=self.org, name='HRA', code='HRA', kind='earning'
        )
        self.bonus_comp = SalaryComponent.objects.create(
            organization=self.org, name='Bonus', code='BONUS', kind='earning'
        )

        # Structure
        self.structure = SalaryStructure.objects.create(
            organization=self.org, name='Phase 5 Structure'
        )
        self.ssc_basic = SalaryStructureComponent.objects.create(
            structure=self.structure,
            component=self.basic_comp,
            calculation_type='FIXED_AMOUNT',
            amount=Decimal('40000.00')
        )
        self.ssc_hra = SalaryStructureComponent.objects.create(
            structure=self.structure,
            component=self.hra_comp,
            calculation_type='PERCENTAGE_OF_BASIC',
            amount=Decimal('50.00') # 50%
        )

        self.compensation = CompensationHistory.objects.create(
            employee=self.employee,
            effective_from=date(2026, 1, 1),
            salary_structure=self.structure,
            basic_salary=Decimal('40000.00')
        )

        self.run = PayrollRun.objects.create(
            organization=self.org,
            run_type='REGULAR',
            year=2026,
            month=3,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )

        # March 2026 has 21 working days assuming standard weekends, but our test branch doesn't have a calendar attached by default.
        # Let's seed working days for March explicitly by creating Attendance/Leave as needed, 
        # or we just rely on the WorkingCalendarService which defaults to Monday-Friday if no rules exist.
        # Let's create Attendance for 19 days, Leave for 1 day, and 1 LOP day.
        # March 2 (Mon) to March 31 (Tue) has 22 working days.
        # Let's mock Attendance:
        # March 2 to March 26 (19 working days) - present
        # March 27 (Fri) - approved leave
        # March 30 (Mon) - half day
        # March 31 (Tue) - absent (LOP)
        
        # March 2 to March 25 are weekdays (18 days). 
        # March 26 is Thu.
        # Let's create Attendance for only 18 working days.
        for d in range(2, 26):
            # Skip weekends (March 7, 8, 14, 15, 21, 22)
            d_date = date(2026, 3, d)
            if d_date.weekday() < 5:
                Attendance.objects.create(
                    employee=self.employee,
                    date=d_date,
                    status='present'
                )
        
        Attendance.objects.create(
            employee=self.employee,
            date=date(2026, 3, 30),
            status='half_day'
        )
        
        self.leave_type = LeaveType.objects.create(
            organization=self.org, name='Annual'
        )
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 3, 27),
            end_date=date(2026, 3, 27),
            status='approved',
        )
        
        # Adjustment for bonus
        self.adjustment = PayrollAdjustment.objects.create(
            employee=self.employee,
            component=self.bonus_comp,
            amount=Decimal('5000.00'),
            period_year=2026,
            period_month=3,
            status=PayrollAdjustment.STATUS_APPROVED,
            reason='Performance Bonus'
        )

    def test_lineage_and_evidence(self):
        records = generate_payroll_for_period(self.run)
        self.assertEqual(len(records), 1)
        record = records[0]
        
        self.assertEqual(record.working_days, 22)
        self.assertEqual(record.effective_days, Decimal('19.5'))
        self.assertEqual(record.absent_days, 3) # max(0, 22 - int(19.5))
        self.assertIn('2026-03-26', record.lop_dates)
        self.assertIn('2026-03-31', record.lop_dates)
        self.assertEqual(len(record.lop_dates), 2)
        
        # Check PayrollRun calculation version
        run_db = PayrollRun.objects.get(id=self.run.id)
        self.assertEqual(run_db.calculation_version, 'v1')

        # Check Line Items
        items = record.line_items.all()
        self.assertEqual(items.count(), 3)
        
        basic_item = items.get(component__code='BASIC')
        hra_item = items.get(component__code='HRA')
        bonus_item = items.get(component__code='BONUS')

        # Basic Lineage
        self.assertEqual(basic_item.source_structure_component, self.ssc_basic)
        self.assertEqual(basic_item.calculation_type, 'FIXED_AMOUNT')
        self.assertEqual(basic_item.calculation_base, Decimal('40000.00'))
        self.assertIsNone(basic_item.rate)
        
        # HRA Lineage
        self.assertEqual(hra_item.source_structure_component, self.ssc_hra)
        self.assertEqual(hra_item.calculation_type, 'PERCENTAGE_OF_BASIC')
        self.assertEqual(hra_item.calculation_base, Decimal('40000.00'))
        self.assertEqual(hra_item.rate, Decimal('50.0000'))
        
        # Adjustment Lineage
        self.assertEqual(bonus_item.source_adjustment, self.adjustment)
        self.assertEqual(bonus_item.calculation_type, 'ADJUSTMENT')
        self.assertEqual(bonus_item.calculation_base, Decimal('5000.00'))

    def test_historical_immutability_and_protection(self):
        # Generate and finalize
        generate_payroll_for_period(self.run)
        self.run.status = PayrollRun.STATUS_APPROVED
        self.run.save()
        finalize_payroll_run(self.run)
        
        record = PayrollRecord.objects.get(employee=self.employee, period=self.run)
        original_net = record.net_salary
        
        # Now change HR data
        self.ssc_basic.amount = Decimal('60000.00')
        self.ssc_basic.save()
        
        self.ssc_hra.amount = Decimal('60.00')
        self.ssc_hra.save()
        
        # Try to delete the adjustment or structure component
        with self.assertRaises(ProtectedError):
            self.ssc_basic.delete()
            
        with self.assertRaises(ProtectedError):
            self.adjustment.delete()
            
        # Verify the finalized record still has the original amount and explanations
        record.refresh_from_db()
        self.assertEqual(record.net_salary, original_net)
        
        basic_item = record.line_items.get(component__code='BASIC')
        self.assertEqual(basic_item.calculation_base, Decimal('40000.00')) # Remains 40k despite change to 60k
        
        hra_item = record.line_items.get(component__code='HRA')
        self.assertEqual(hra_item.rate, Decimal('50.0000')) # Remains 50% despite change to 60%

    def test_legacy_backfill(self):
        # Remove salary structure to force legacy fallback
        self.compensation.salary_structure = None
        self.compensation.save()
        
        records = generate_payroll_for_period(self.run)
        record = records[0]
        
        items = record.line_items.exclude(calculation_type='ADJUSTMENT') # Filter out bonus
        self.assertEqual(items.count(), 1)
        
        legacy_item = items.first()
        self.assertEqual(legacy_item.calculation_type, 'LEGACY_RECONSTRUCTED')
        self.assertTrue(legacy_item.is_backfilled)
        self.assertEqual(legacy_item.calculation_base, legacy_item.amount) # base is the prorated gross
        self.assertIsNone(legacy_item.source_structure_component)
