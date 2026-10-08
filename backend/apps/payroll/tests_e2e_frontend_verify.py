import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.organization.models import Organization, Branch, Department, Designation, OrganizationMembership
from apps.employees.models import Employee
from apps.authorization.models import Role, RolePermission, UserRole, Permission
from apps.leaves.models import LeaveType, LeaveBalance, LeaveRequest
from apps.attendance.models import Shift, Attendance
from apps.payroll.models import PayrollRun, SalaryStructure
from datetime import date

User = get_user_model()

class FrontendE2EVerification(TestCase):
    def setUp(self):
        self.client = Client()

    def test_full_frontend_e2e_flow(self):
        # 1. Register organization and admin
        org = Organization.objects.create(name="E2E Corp")
        admin = User.objects.create_superuser(email="admin@e2e.local", password="Password123!", status="active")
        OrganizationMembership.objects.create(user=admin, organization=org)
        
        # Give admin all permissions via a role (mimicking frontend setup)
        role = Role.objects.create(organization=org, name="Admin")
        UserRole.objects.create(user=admin, role=role, scope='organization')
        perms = [
            'org.create_branch', 'org.create_department', 'org.create_designation',
            'employee.create', 'payroll.manage_compensation', 'payroll.generate',
            'payroll.approve', 'payroll.view', 'attendance.create_record', 'payroll.finalize'
        ]
        for p in perms:
            perm, _ = Permission.objects.get_or_create(codename=p, defaults={'name': p, 'resource': p.split('.')[0], 'action': p.split('.')[1]})
            RolePermission.objects.create(role=role, permission=perm)
            
        # Login and get token (mimicking frontend)
        # Assuming frontend gets token from some login endpoint. For simplicity, we just force login.
        self.client.force_login(admin)
        
        # 2. Branch & Department & Designation (Organization Setup)
        headers = {"HTTP_X_ORGANIZATION_ID": str(org.id)}
        res = self.client.post(f"/api/v1/organization/branches/", {"name": "HQ", "code": "HQ", "country": "IN"}, content_type="application/json", **headers)
        if res.status_code != 201:
            print(res.content)
        self.assertEqual(res.status_code, 201)
        branch_id = res.json()["id"]
        
        res = self.client.post(f"/api/v1/organization/departments/", {"name": "Engineering", "branch": branch_id}, content_type="application/json", **headers)
        if res.status_code != 201:
            print(res.content)
        self.assertEqual(res.status_code, 201)
        dept_id = res.json()["id"]
        
        res = self.client.post(f"/api/v1/organization/designations/", {"name": "Engineer"}, content_type="application/json", **headers)
        if res.status_code != 201:
            print(res.content)
        self.assertEqual(res.status_code, 201)
        desig_id = res.json()["id"]

        # 3. Create 2 Employees
        emp1_res = self.client.post(f"/api/v1/employees/", {
            "first_name": "Alice", "last_name": "Smith", "email": "alice@e2e.local", "employee_code": "E001",
            "branch": branch_id, "department": dept_id, "designation": desig_id, "organization": str(org.id)
        }, content_type="application/json", **headers)
        if emp1_res.status_code != 201:
            print(emp1_res.content)
        self.assertEqual(emp1_res.status_code, 201)
        emp1_id = Employee.objects.get(employee_code="E001").id
        
        emp2_res = self.client.post(f"/api/v1/employees/", {
            "first_name": "Bob", "last_name": "Jones", "email": "bob@e2e.local", "employee_code": "E002",
            "branch": branch_id, "department": dept_id, "designation": desig_id, "organization": str(org.id)
        }, content_type="application/json", **headers)
        if emp2_res.status_code != 201:
            print(emp2_res.content)
        self.assertEqual(emp2_res.status_code, 201)
        emp2_id = Employee.objects.get(employee_code="E002").id
        Employee.objects.all().update(employment_status="active")

        # 4. Shift
        shift = Shift.objects.create(branch_id=branch_id, name="Regular", start_time="09:00:00", end_time="17:00:00")

        # Attendance (1 day present for E001, 1 day absent for E002)
        Attendance.objects.create(employee_id=emp1_id, date=date(2023, 10, 1), status='present')
        Attendance.objects.create(employee_id=emp2_id, date=date(2023, 10, 1), status='absent')

        # 5. Salary Structure
        sal1_res = self.client.post(f"/api/v1/payroll/compensation/set/", {
            "employee": emp1_id, "basic_salary": "50000.00", "effective_from": "2023-10-01"
        }, content_type="application/json", **headers)
        if sal1_res.status_code != 201:
            print(sal1_res.content)
        self.assertEqual(sal1_res.status_code, 201)

        sal2_res = self.client.post(f"/api/v1/payroll/compensation/set/", {
            "employee": emp2_id, "basic_salary": "40000.00", "effective_from": "2023-10-01"
        }, content_type="application/json", **headers)
        if sal2_res.status_code != 201:
            print(sal2_res.content)
        self.assertEqual(sal2_res.status_code, 201)

        # 6. Payroll Run
        period_res = self.client.post(f"/api/v1/payroll/periods/", {
            "year": 2023, "month": 10, "start_date": "2023-10-01", "end_date": "2023-10-31"
        }, content_type="application/json", **headers)
        if period_res.status_code != 201:
            print(period_res.content)
        self.assertEqual(period_res.status_code, 201)
        period_id = period_res.json()["id"]

        with self.settings(CELERY_TASK_ALWAYS_EAGER=True):
            gen_res = self.client.post(f"/api/v1/payroll/periods/{period_id}/generate/", {}, content_type="application/json", **headers)
            if gen_res.status_code != 200:
                print(gen_res.content)
            self.assertEqual(gen_res.status_code, 200)

        app_res = self.client.post(f"/api/v1/payroll/periods/{period_id}/approve/", {}, content_type="application/json", **headers)
        if app_res.status_code != 200:
            print(app_res.content)
        self.assertEqual(app_res.status_code, 200)

        fin_res = self.client.post(f"/api/v1/payroll/periods/{period_id}/finalize/", {}, content_type="application/json", **headers)
        if fin_res.status_code != 200:
            print(fin_res.content)
        self.assertEqual(fin_res.status_code, 200)

        # 7. EXPORT
        csv_res = self.client.get(f"/api/v1/payroll/periods/{period_id}/export_csv/", **headers)
        self.assertEqual(csv_res.status_code, 200)
        self.assertEqual(csv_res['Content-Type'], 'text/csv')

        pdf_res = self.client.get(f"/api/v1/payroll/periods/{period_id}/export_pdf/", **headers)
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res['Content-Type'], 'application/pdf')
        
        print("E2E Test Passed: CSV and PDF exported successfully.")
