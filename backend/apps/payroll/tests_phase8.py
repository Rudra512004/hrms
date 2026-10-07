from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.payroll.models import PayrollRun, PayrollRecord, PayrollLineItem, SalaryStructure, SalaryComponent, CompensationHistory, PayrollAdjustment
from apps.organization.models import Organization, Branch
from apps.employees.models import Employee, EmploymentStatus
from apps.payroll.validation import PayrollValidator, PayrollValidationIssue
from apps.payroll.variance import PayrollVarianceEngine
from datetime import date

class Phase8Tests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.org = Organization.objects.create(name="Test Org")
        self.branch = Branch.objects.create(name="HQ", organization=self.org)
        self.user1 = User.objects.create(email="test@user.com", first_name="Test", last_name="User")
        self.emp = Employee.objects.create(
            user=self.user1,
            organization=self.org, 
            branch=self.branch, 
            employee_code="EMP001",
            employment_status=EmploymentStatus.ACTIVE
        )
        self.structure = SalaryStructure.objects.create(organization=self.org, name="Standard")
        self.comp = CompensationHistory.objects.create(
            employee=self.emp, 
            effective_from=date(2023, 1, 1), 
            basic_salary=Decimal('50000.00'),
            salary_structure=self.structure
        )
        
        self.run1 = PayrollRun.objects.create(
            organization=self.org, year=2023, month=1, start_date=date(2023,1,1), end_date=date(2023,1,31), status=PayrollRun.STATUS_FINALIZED
        )
        self.rec1 = PayrollRecord.objects.create(
            period=self.run1, employee=self.emp, working_days=22, present_days=22, absent_days=0, leave_days=0, effective_days=Decimal('22.0'),
            basic_salary=Decimal('50000.00'), gross_salary=Decimal('50000.00'), net_salary=Decimal('50000.00'), status=PayrollRecord.STATUS_APPROVED
        )
        
        self.run2 = PayrollRun.objects.create(
            organization=self.org, year=2023, month=2, start_date=date(2023,2,1), end_date=date(2023,2,28), status=PayrollRun.STATUS_DRAFT
        )
        self.rec2 = PayrollRecord.objects.create(
            period=self.run2, employee=self.emp, working_days=20, present_days=20, absent_days=0, leave_days=0, effective_days=Decimal('20.0'),
            basic_salary=Decimal('55000.00'), gross_salary=Decimal('55000.00'), net_salary=Decimal('55000.00'), status=PayrollRecord.STATUS_DRAFT
        )

    def test_validation_negative_net(self):
        self.rec2.net_salary = Decimal('-100.00')
        self.rec2.save()
        validator = PayrollValidator(self.run2)
        issues = validator.validate()
        self.assertTrue(any(i.code == 'NEGATIVE_NET_PAY' for i in issues))

    def test_validation_missing_line_items(self):
        # gross > 0 but no line items
        validator = PayrollValidator(self.run2)
        issues = validator.validate()
        self.assertTrue(any(i.code == 'MISSING_LINE_ITEMS' for i in issues))

    def test_variance_salary_change(self):
        engine = PayrollVarianceEngine(self.run2)
        res = engine.analyze()
        emp_var = res['employee_variances'][0]
        self.assertEqual(emp_var['net_variance'], '5000.00')
        causes = [c['code'] for c in emp_var['causes']]
        self.assertIn('SALARY_CHANGE', causes)
        
    def test_variance_new_employee(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user2 = User.objects.create(email="new@user.com", first_name="New", last_name="User")
        emp2 = Employee.objects.create(
            user=self.user2,
            organization=self.org, 
            branch=self.branch, 
            employee_code="EMP002",
            employment_status=EmploymentStatus.ACTIVE
        )
        rec3 = PayrollRecord.objects.create(
            period=self.run2, employee=emp2, working_days=20, present_days=20, absent_days=0, leave_days=0, effective_days=Decimal('20.0'),
            basic_salary=Decimal('60000.00'), gross_salary=Decimal('60000.00'), net_salary=Decimal('60000.00'), status=PayrollRecord.STATUS_DRAFT
        )
        engine = PayrollVarianceEngine(self.run2)
        res = engine.analyze()
        
        new_emp_var = next(ev for ev in res['employee_variances'] if ev['employee_id'] == emp2.id)
        causes = [c['code'] for c in new_emp_var['causes']]
        self.assertIn('NEW_EMPLOYEE_OR_FIRST_PAYROLL', causes)
        self.assertEqual(new_emp_var['previous_net'], '0')
        self.assertEqual(new_emp_var['current_net'], '60000.00')
