from decimal import Decimal
from datetime import date
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from apps.organization.models import Organization, Branch, Department
from apps.employees.models import Employee, EmploymentStatus
from apps.authorization.models import Role, Permission, RolePermission, UserRole, ScopeChoices
from apps.payroll.models import PayrollRun, PayrollRecord

User = get_user_model()


class PayrollExportTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.org = Organization.objects.create(name='Test Org')
        self.branch = Branch.objects.create(organization=self.org, name='Test Branch')
        self.dept = Department.objects.create(branch=self.branch, name='IT')

        self.user_hr = User.objects.create_user(email='hr@test.com', password='Password123!', status='active')
        self.emp_hr = Employee.objects.create(
            user=self.user_hr, employee_code='HR01', organization=self.org, branch=self.branch,
            department=self.dept, employment_status=EmploymentStatus.ACTIVE
        )

        role = Role.objects.create(organization=self.org, name='HR Role')
        perm, _ = Permission.objects.get_or_create(codename='payroll.view', defaults={'name':'view','resource':'payroll','action':'view'})
        RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(user=self.user_hr, role=role, scope=ScopeChoices.ORGANIZATION)

        self.period = PayrollRun.objects.create(
            organization=self.org,
            year=2025,
            month=1,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            status=PayrollRun.STATUS_FINALIZED
        )

        self.record = PayrollRecord.objects.create(
            period=self.period,
            employee=self.emp_hr,
            working_days=22,
            present_days=20,
            half_days=0,
            absent_days=2,
            leave_days=0,
            effective_days=Decimal('20.0'),
            basic_salary=Decimal('50000.00'),
            gross_salary=Decimal('45454.55'),
            net_salary=Decimal('45454.55'),
            status=PayrollRecord.STATUS_FINALIZED
        )

    def test_export_csv_success(self):
        self.client.force_authenticate(user=self.user_hr)
        res = self.client.get(f'/api/v1/payroll/periods/{self.period.id}/export_csv/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="payroll_', res['Content-Disposition'])

        csv_content = res.content.decode('utf-8')
        self.assertIn('Employee Code', csv_content)
        self.assertIn('HR01', csv_content)
        self.assertIn('50000.00', csv_content)
        self.assertIn('45454.55', csv_content)

    def test_export_pdf_success(self):
        self.client.force_authenticate(user=self.user_hr)
        res = self.client.get(f'/api/v1/payroll/periods/{self.period.id}/export_pdf/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="payroll_', res['Content-Disposition'])
        
        self.assertTrue(res.content.startswith(b'%PDF-'))
        
    def test_export_unauthorized(self):
        # User without permission
        user_other = User.objects.create_user(email='other@test.com', password='pwd', status='active')
        Employee.objects.create(
            user=user_other, employee_code='OT01', organization=self.org, branch=self.branch
        )
        self.client.force_authenticate(user=user_other)
        
        res_csv = self.client.get(f'/api/v1/payroll/periods/{self.period.id}/export_csv/')
        self.assertEqual(res_csv.status_code, status.HTTP_403_FORBIDDEN)
        
        res_pdf = self.client.get(f'/api/v1/payroll/periods/{self.period.id}/export_pdf/')
        self.assertEqual(res_pdf.status_code, status.HTTP_403_FORBIDDEN)
