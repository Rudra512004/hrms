import csv
import io
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

from apps.organization.models import Organization, Branch, Department, Designation
from apps.employees.models import Employee
from apps.attendance.models import Shift, Attendance, AttendanceProductivity, EmployeeShiftAssignment
from apps.leaves.models import LeaveType, LeaveBalance
from apps.authorization.models import Permission

from apps.data_import.registry import get_template, TEMPLATE_REGISTRY
from apps.data_import.models import ImportJob
from apps.data_import.engine import ImportEngine
from apps.data_import.parsers import parse_field_value

User = get_user_model()

class DataImportTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Test Org', code='TEST')
        self.user = User.objects.create_user(email='test@example.com')
        
        self.branch = Branch.objects.create(
            organization=self.org, name='HQ', code='HQ', timezone='UTC'
        )
        self.dept = Department.objects.create(
            branch=self.branch, name='IT', code='IT'
        )
        self.desig = Designation.objects.create(
            organization=self.org, name='Dev', code='DEV'
        )
        
        Permission.objects.get_or_create(codename='data_import.view', resource='data_import', action='view')
        Permission.objects.get_or_create(codename='data_import.execute', resource='data_import', action='execute')

    def test_registry_contains_templates(self):
        """Test that the 9 required templates are registered."""
        self.assertIn('employees', TEMPLATE_REGISTRY)
        self.assertIn('branches', TEMPLATE_REGISTRY)
        self.assertIn('departments', TEMPLATE_REGISTRY)
        self.assertIn('designations', TEMPLATE_REGISTRY)
        self.assertIn('leave_types', TEMPLATE_REGISTRY)
        self.assertIn('holidays', TEMPLATE_REGISTRY)
        self.assertIn('attendance', TEMPLATE_REGISTRY)
        self.assertIn('salary_structures', TEMPLATE_REGISTRY)
        self.assertIn('leave_balances', TEMPLATE_REGISTRY)

    def test_parser_valid_types(self):
        template = get_template('employees')
        
        # Test Date parsing
        date_field = next(f for f in template['fields'] if f['csv_header'] == 'date_of_joining')
        self.assertEqual(parse_field_value(date_field, '2023-01-15'), date(2023, 1, 15))
        self.assertEqual(parse_field_value(date_field, '15/01/2023'), date(2023, 1, 15))
        
        # Test Boolean parsing
        branch_tmpl = get_template('branches')
        bool_field = next(f for f in branch_tmpl['fields'] if f['csv_header'] == 'is_head_office')
        self.assertTrue(parse_field_value(bool_field, 'true'))
        self.assertTrue(parse_field_value(bool_field, 'Yes'))
        self.assertFalse(parse_field_value(bool_field, '0'))

    def test_import_engine_employees(self):
        """Test full import flow for employees."""
        template = get_template('employees')
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=template['headers'])
        writer.writeheader()
        
        row_data = {
            'employee_code': 'EMP001', 'first_name': 'John', 'last_name': 'Doe',
            'email': 'john@test.com', 'company_code': 'TEST', 'branch_code': 'HQ',
            'department_code': 'IT', 'designation_code': 'DEV', 'employment_type': 'full_time',
            'employment_status': 'active', 'date_of_joining': '2023-01-01', 'status': 'active'
        }
        writer.writerow(row_data)
        
        csv_content = output.getvalue()
        
        file = SimpleUploadedFile("employees.csv", csv_content.encode('utf-8'))
        job = ImportJob.objects.create(
            organization=self.org,
            template_key='employees',
            file=file
        )
        
        engine = ImportEngine(job)
        engine.validate_and_preview()
        job.refresh_from_db()
        self.assertEqual(job.status, 'validated')
        
        engine.execute()
        job.refresh_from_db()
        
        if job.status != 'completed':
            for error in job.errors.all():
                print(f"Error in employees test: {error.message} - {error.field} - {error.error_type} - {error.row_data}")
        
        self.assertEqual(job.status, 'completed')
        self.assertEqual(job.created_count, 1)
        
        emp = Employee.objects.get(employee_code='EMP001')
        self.assertEqual(emp.user.first_name, 'John')
        self.assertEqual(emp.branch, self.branch)
        self.assertEqual(emp.department, self.dept)
        self.assertEqual(emp.designation, self.desig)
        
        row_data['first_name'] = 'Johnny'
        output2 = io.StringIO()
        writer2 = csv.DictWriter(output2, fieldnames=template['headers'])
        writer2.writeheader()
        writer2.writerow(row_data)
        
        file2 = SimpleUploadedFile("employees2.csv", output2.getvalue().encode('utf-8'))
        job2 = ImportJob.objects.create(
            organization=self.org,
            template_key='employees',
            file=file2
        )
        engine2 = ImportEngine(job2)
        engine2.validate_and_preview()
        engine2.execute()
        job2.refresh_from_db()
        self.assertEqual(job2.updated_count, 1)
        
        emp.refresh_from_db()
        self.assertEqual(emp.user.first_name, 'Johnny')

    def test_import_engine_dynamic_components(self):
        """Test import of dynamic salary components."""
        emp_user = User.objects.create_user(email='emp@test.com')
        emp = Employee.objects.create(
            employee_code='EMP002', organization=self.org, user=emp_user,
            branch=self.branch, department=self.dept, designation=self.desig,
            employment_type='full_time', employment_status='active', joining_date=date.today()
        )
        
        template = get_template('salary_structures')
        output = io.StringIO()
        
        # Add dynamic components to header
        headers = template['headers'] + ['component:hra', 'component:med', 'component:tax']
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        
        row_data = {
            'employee_code': 'EMP002', 'effective_from': '2023-01-01',
            'ctc_annual': '1000000', 'basic_salary': '50000', 'currency': 'INR',
            'payment_mode': 'BANK_TRANSFER', 'notes': '',
            'component:hra': '10000', 'component:med': '5000', 'component:tax': '-2000'
        }
        writer.writerow(row_data)
        
        file = SimpleUploadedFile("salaries.csv", output.getvalue().encode('utf-8'))
        job = ImportJob.objects.create(
            organization=self.org,
            template_key='salary_structures',
            file=file
        )
        engine = ImportEngine(job)
        engine.validate_and_preview()
        engine.execute()
        job.refresh_from_db()
        
        if job.status != 'completed':
            for error in job.errors.all():
                print(f"Error in dynamic components test: {error.message} - {error.field} - {error.error_type} - {error.row_data}")

        self.assertEqual(job.status, 'completed')
        
        from apps.payroll.models import CompensationHistory, SalaryStructureComponent, SalaryComponent
        history = CompensationHistory.objects.get(employee=emp)
        self.assertEqual(history.basic_salary, Decimal('50000.00'))
        
        comps = SalaryStructureComponent.objects.filter(structure__organization=self.org)
        self.assertEqual(comps.count(), 3)
        tax_comp = comps.get(component__code='TAX')
        self.assertEqual(tax_comp.component.kind, 'deduction')
        self.assertEqual(tax_comp.amount, Decimal('2000.00'))
