import io
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.organization.models import Organization, Branch, Department, Designation
from apps.employees.models import Employee
from apps.attendance.models import Holiday, Attendance
from apps.leaves.models import LeaveType, BranchLeavePolicy, LeaveBalance, LeaveCycle
from apps.payroll.models import (
    SalaryStructure, SalaryComponent, SalaryStructureComponent, CompensationHistory
)
from apps.imports.models import DataImport
from apps.imports.importers import (
    EmployeeImporter,
    DesignationImporter,
    HolidayImporter,
    LeaveTypeImporter,
    LeaveBalanceImporter,
    SalaryStructureImporter,
    AttendanceImporter,
)
import datetime

User = get_user_model()


# ---------------------------------------------------------------------------
# Helper: create a DataImport object with the given CSV content
# ---------------------------------------------------------------------------

def make_import(org, user, import_type, csv_data):
    obj = DataImport.objects.create(
        organization=org,
        uploaded_by=user,
        import_type=import_type,
    )
    obj.file.save('test.csv', io.StringIO(csv_data))
    return obj


# ---------------------------------------------------------------------------
# Existing Employee Importer Security Tests (unchanged)
# ---------------------------------------------------------------------------

class ImporterSecurityTestCase(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        self.user1 = User.objects.create_user(email="user1@org1.com", password="pwd")
        self.user2 = User.objects.create_user(email="user2@org2.com", password="pwd")

        self.branch_org1 = Branch.objects.create(organization=self.org1, name="B1-CODE")
        self.branch_org2 = Branch.objects.create(organization=self.org2, name="B2-CODE")

        self.dept_org1 = Department.objects.create(branch=self.branch_org1, name="D1-CODE")

        self.import_obj = DataImport.objects.create(
            organization=self.org1,
            uploaded_by=self.user1,
            import_type='employee',
        )

    def test_cross_tenant_import_reference_blocked(self):
        csv_data = (
            "employee_code,first_name,last_name,email,branch_code\n"
            "EMP-01,Test,User,test1@org.com,B2-CODE\n"
        )
        self.import_obj.file.save('test.csv', io.StringIO(csv_data))
        importer = EmployeeImporter(self.import_obj)
        importer.run()
        self.assertEqual(importer.import_obj.status, 'failed')
        self.assertIn("not found", importer.import_obj.error_log.get(1, [""])[0])
        self.assertEqual(Employee.objects.count(), 0)

    def test_dry_run_persistence(self):
        csv_data = (
            "employee_code,first_name,last_name,email,branch_code,department_code\n"
            "EMP-02,Test,User,test2@org.com,B1-CODE,D1-CODE\n"
        )
        self.import_obj.file.save('test.csv', io.StringIO(csv_data))
        importer = EmployeeImporter(self.import_obj, dry_run=True)
        importer.run()
        self.assertEqual(importer.import_obj.status, 'dry_run')
        self.assertEqual(Employee.objects.count(), 0)

    def test_importer_transaction_rollback_on_partial_failure(self):
        csv_data = (
            "employee_code,first_name,last_name,email,branch_code,department_code\n"
            "EMP-03,Valid,User,valid@org.com,B1-CODE,D1-CODE\n"
            "EMP-04,Invalid,User,,B1-CODE,D1-CODE\n"
        )
        self.import_obj.file.save('test.csv', io.StringIO(csv_data))
        importer = EmployeeImporter(self.import_obj)
        importer.run()
        self.assertEqual(importer.import_obj.status, 'failed')
        self.assertEqual(Employee.objects.count(), 0)

    def test_manager_lookup_success(self):
        manager = Employee.objects.create(
            organization=self.org1, employee_code="MGR-1",
            user=User.objects.create_user(email="m@org.com")
        )
        csv_data = (
            "employee_code,first_name,last_name,email,branch_code,reporting_manager_code\n"
            "EMP-10,Test,User,test10@org.com,B1-CODE,MGR-1\n"
        )
        self.import_obj.file.save('test.csv', io.StringIO(csv_data))
        importer = EmployeeImporter(self.import_obj)
        importer.run()
        if importer.import_obj.status != 'completed':
            print(f"Error log: {importer.import_obj.error_log}")
        self.assertEqual(importer.import_obj.status, 'completed')
        emp = Employee.objects.get(employee_code="EMP-10")
        self.assertEqual(emp.reporting_manager, manager)

    def test_manager_lookup_nonexistent_fails(self):
        csv_data = (
            "employee_code,first_name,last_name,email,branch_code,reporting_manager_code\n"
            "EMP-11,Test,User,test11@org.com,B1-CODE,INVALID_MGR\n"
        )
        self.import_obj.file.save('test.csv', io.StringIO(csv_data))
        importer = EmployeeImporter(self.import_obj)
        importer.run()
        self.assertEqual(importer.import_obj.status, 'failed')
        self.assertIn("not found", importer.import_obj.error_log.get(1, [""])[0])

    def test_manager_lookup_cross_tenant_fails(self):
        Employee.objects.create(
            organization=self.org2, employee_code="MGR-2",
            user=User.objects.create_user(email="m2@org.com")
        )
        csv_data = (
            "employee_code,first_name,last_name,email,branch_code,reporting_manager_code\n"
            "EMP-12,Test,User,test12@org.com,B1-CODE,MGR-2\n"
        )
        self.import_obj.file.save('test.csv', io.StringIO(csv_data))
        importer = EmployeeImporter(self.import_obj)
        importer.run()
        self.assertEqual(importer.import_obj.status, 'failed')
        self.assertIn("not found", importer.import_obj.error_log.get(1, [""])[0])

    def test_blank_manager_valid(self):
        csv_data = (
            "employee_code,first_name,last_name,email,branch_code,reporting_manager_code\n"
            "EMP-13,Test,User,test13@org.com,B1-CODE,\n"
        )
        self.import_obj.file.save('test.csv', io.StringIO(csv_data))
        importer = EmployeeImporter(self.import_obj)
        importer.run()
        self.assertEqual(importer.import_obj.status, 'completed')
        emp = Employee.objects.get(employee_code="EMP-13")
        self.assertIsNone(emp.reporting_manager)

    def test_manager_dry_run_no_persist(self):
        Employee.objects.create(
            organization=self.org1, employee_code="MGR-1",
            user=User.objects.create_user(email="m3@org.com")
        )
        csv_data = (
            "employee_code,first_name,last_name,email,branch_code,reporting_manager_code\n"
            "EMP-14,Test,User,test14@org.com,B1-CODE,MGR-1\n"
        )
        self.import_obj.file.save('test.csv', io.StringIO(csv_data))
        importer = EmployeeImporter(self.import_obj, dry_run=True)
        importer.run()
        self.assertEqual(importer.import_obj.status, 'dry_run')
        self.assertFalse(Employee.objects.filter(employee_code="EMP-14").exists())


# ---------------------------------------------------------------------------
# Designation Importer Tests
# ---------------------------------------------------------------------------

class DesignationImporterTestCase(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="DesOrg1")
        self.org2 = Organization.objects.create(name="DesOrg2")
        self.user = User.objects.create_user(email="des@test.com", password="pwd")

    def _run(self, csv_data, dry_run=False):
        obj = make_import(self.org1, self.user, 'designation', csv_data)
        imp = DesignationImporter(obj, dry_run=dry_run)
        imp.run()
        return imp

    def test_valid_import(self):
        imp = self._run(
            "designation_name,description,is_active\n"
            "Senior Engineer,Top-level engineer,true\n"
        )
        self.assertEqual(imp.import_obj.status, 'completed')
        self.assertTrue(Designation.objects.filter(organization=self.org1, name="Senior Engineer").exists())

    def test_missing_required_field(self):
        imp = self._run("designation_name,description\n,Some desc\n")
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertIn("required", imp.import_obj.error_log.get(1, [""])[0])

    def test_duplicate_upsert(self):
        Designation.objects.create(organization=self.org1, name="Manager", description="Old")
        imp = self._run("designation_name,description\nManager,Updated\n")
        self.assertEqual(imp.import_obj.status, 'completed')
        d = Designation.objects.get(organization=self.org1, name="Manager")
        self.assertEqual(d.description, "Updated")

    def test_cross_tenant_isolation(self):
        # org2 designation should not appear in org1
        Designation.objects.create(organization=self.org2, name="Director")
        imp = self._run("designation_name,description\nDirector,Same name\n")
        self.assertEqual(imp.import_obj.status, 'completed')
        # org1 should now have its own Director
        self.assertTrue(Designation.objects.filter(organization=self.org1, name="Director").exists())
        # org2's record unchanged
        self.assertEqual(
            Designation.objects.filter(organization=self.org2, name="Director").first().description,
            ""
        )

    def test_dry_run(self):
        imp = self._run("designation_name\nCTO\n", dry_run=True)
        self.assertEqual(imp.import_obj.status, 'dry_run')
        self.assertFalse(Designation.objects.filter(organization=self.org1, name="CTO").exists())

    def test_rollback_on_partial_failure(self):
        imp = self._run(
            "designation_name,description\n"
            "ValidRole,Good\n"
            ",Missing name\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertFalse(Designation.objects.filter(organization=self.org1).exists())

    def test_missing_header(self):
        imp = self._run("description,is_active\nSome desc,true\n")
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertIn("Missing required columns", imp.import_obj.error_log.get(0, [""])[0])


# ---------------------------------------------------------------------------
# Holiday Importer Tests
# ---------------------------------------------------------------------------

class HolidayImporterTestCase(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="HolOrg1")
        self.org2 = Organization.objects.create(name="HolOrg2")
        self.user = User.objects.create_user(email="hol@test.com", password="pwd")
        self.branch = Branch.objects.create(organization=self.org1, name="HQ")
        self.branch2 = Branch.objects.create(organization=self.org2, name="HQ")

    def _run(self, csv_data, dry_run=False):
        obj = make_import(self.org1, self.user, 'holiday', csv_data)
        imp = HolidayImporter(obj, dry_run=dry_run)
        imp.run()
        return imp

    def test_valid_import(self):
        imp = self._run("branch_code,holiday_name,date\nHQ,Diwali,2026-11-01\n")
        self.assertEqual(imp.import_obj.status, 'completed')
        self.assertTrue(Holiday.objects.filter(branch=self.branch, name="Diwali").exists())

    def test_cross_tenant_branch_blocked(self):
        # org2's HQ should not be found under org1
        # We give branch_code = ORG2-HQ which doesn't exist in org1
        imp = self._run("branch_code,holiday_name,date\nORG2-HQ,NewYear,2026-01-01\n")
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertEqual(Holiday.objects.count(), 0)

    def test_invalid_date_format(self):
        imp = self._run("branch_code,holiday_name,date\nHQ,Xmas,25-12-2026\n")
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertIn("Invalid date format", imp.import_obj.error_log.get(1, [""])[0])

    def test_duplicate_upsert(self):
        Holiday.objects.create(branch=self.branch, name="OldName", date=datetime.date(2026, 11, 1))
        imp = self._run("branch_code,holiday_name,date\nHQ,NewName,2026-11-01\n")
        self.assertEqual(imp.import_obj.status, 'completed')
        h = Holiday.objects.get(branch=self.branch, date=datetime.date(2026, 11, 1))
        self.assertEqual(h.name, "NewName")

    def test_missing_required_branch(self):
        imp = self._run("branch_code,holiday_name,date\n,Diwali,2026-11-01\n")
        self.assertEqual(imp.import_obj.status, 'failed')

    def test_dry_run(self):
        imp = self._run("branch_code,holiday_name,date\nHQ,Republic Day,2026-01-26\n", dry_run=True)
        self.assertEqual(imp.import_obj.status, 'dry_run')
        self.assertFalse(Holiday.objects.exists())

    def test_rollback_on_partial_failure(self):
        imp = self._run(
            "branch_code,holiday_name,date\n"
            "HQ,Diwali,2026-11-01\n"
            "HQ,Xmas,BAD-DATE\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertFalse(Holiday.objects.exists())


# ---------------------------------------------------------------------------
# Leave Type Importer Tests
# ---------------------------------------------------------------------------

class LeaveTypeImporterTestCase(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="LTOrg1")
        self.org2 = Organization.objects.create(name="LTOrg2")
        self.user = User.objects.create_user(email="lt@test.com", password="pwd")
        self.branch = Branch.objects.create(organization=self.org1, name="HQ")

    def _run(self, csv_data, dry_run=False):
        obj = make_import(self.org1, self.user, 'leave_type', csv_data)
        imp = LeaveTypeImporter(obj, dry_run=dry_run)
        imp.run()
        return imp

    def test_valid_import_no_policy(self):
        imp = self._run("name,description,is_active\nAnnual Leave,For annual rest,true\n")
        self.assertEqual(imp.import_obj.status, 'completed')
        self.assertTrue(LeaveType.objects.filter(organization=self.org1, name="Annual Leave").exists())

    def test_valid_import_with_branch_policy(self):
        imp = self._run(
            "name,branch_code,monthly_allocation,is_paid,half_day_allowed\n"
            "Sick Leave,HQ,1.5,true,true\n"
        )
        self.assertEqual(imp.import_obj.status, 'completed')
        lt = LeaveType.objects.get(organization=self.org1, name="Sick Leave")
        policy = BranchLeavePolicy.objects.get(branch=self.branch, leave_type=lt)
        self.assertEqual(policy.monthly_allocation, Decimal('1.5'))
        self.assertTrue(policy.half_day_allowed)

    def test_cross_tenant_branch_blocked(self):
        imp = self._run("name,branch_code\nCasual Leave,NONEXISTENT_BRANCH\n")
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertFalse(LeaveType.objects.filter(organization=self.org1).exists())

    def test_duplicate_upsert(self):
        LeaveType.objects.create(organization=self.org1, name="Maternity Leave", description="Old")
        imp = self._run("name,description\nMaternity Leave,Updated description\n")
        self.assertEqual(imp.import_obj.status, 'completed')
        lt = LeaveType.objects.get(organization=self.org1, name="Maternity Leave")
        self.assertEqual(lt.description, "Updated description")

    def test_missing_required_name(self):
        imp = self._run("name,description\n,Some desc\n")
        self.assertEqual(imp.import_obj.status, 'failed')

    def test_dry_run(self):
        imp = self._run("name\nPaternity Leave\n", dry_run=True)
        self.assertEqual(imp.import_obj.status, 'dry_run')
        self.assertFalse(LeaveType.objects.filter(organization=self.org1).exists())

    def test_invalid_proration_rounding(self):
        imp = self._run(
            "name,branch_code,proration_rounding\n"
            "CL,HQ,INVALID_ROUNDING\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertIn("proration_rounding", imp.import_obj.error_log.get(1, [""])[0])

    def test_days_per_month_alias(self):
        """days_per_month CSV column maps to monthly_allocation."""
        imp = self._run(
            "name,branch_code,days_per_month\n"
            "EL,HQ,2.0\n"
        )
        self.assertEqual(imp.import_obj.status, 'completed')
        lt = LeaveType.objects.get(organization=self.org1, name="EL")
        policy = BranchLeavePolicy.objects.get(branch=self.branch, leave_type=lt)
        self.assertEqual(policy.monthly_allocation, Decimal('2.0'))

    def test_rollback_on_partial_failure(self):
        imp = self._run(
            "name,description\n"
            "Valid Leave,Good\n"
            ",Missing name\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertFalse(LeaveType.objects.filter(organization=self.org1).exists())


# ---------------------------------------------------------------------------
# Leave Balance Importer Tests
# ---------------------------------------------------------------------------

class LeaveBalanceImporterTestCase(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="LBOrg1")
        self.org2 = Organization.objects.create(name="LBOrg2")
        self.user = User.objects.create_user(email="lb@test.com", password="pwd")

        self.branch = Branch.objects.create(organization=self.org1, name="HQ")
        self.branch2 = Branch.objects.create(organization=self.org2, name="HQ")

        emp_user = User.objects.create_user(email="emp@lb.com", password="pwd")
        self.employee = Employee.objects.create(
            organization=self.org1, employee_code="EMP-LB-ORG1-01", user=emp_user
        )

        org2_user = User.objects.create_user(email="emp2@lb.com", password="pwd")
        self.employee_org2 = Employee.objects.create(
            organization=self.org2, employee_code="EMP-LB-ORG2-01", user=org2_user
        )

        self.leave_type = LeaveType.objects.create(organization=self.org1, name="Annual Leave")
        self.leave_type_org2 = LeaveType.objects.create(organization=self.org2, name="Annual Leave")

        # Create leave cycle for org1's branch
        self.cycle = LeaveCycle.objects.create(
            branch=self.branch, name="2026",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            is_active=True,
        )

    def _run(self, csv_data, dry_run=False):
        obj = make_import(self.org1, self.user, 'leave_balance', csv_data)
        imp = LeaveBalanceImporter(obj, dry_run=dry_run)
        imp.run()
        return imp

    def test_valid_import(self):
        imp = self._run(
            "employee_code,leave_type_name,branch_code,year,allocated_days,carried_forward_days,used_days\n"
            "EMP-LB-ORG1-01,Annual Leave,HQ,2026,12,2,3\n"
        )
        self.assertEqual(imp.import_obj.status, 'completed')
        lb = LeaveBalance.objects.get(employee=self.employee, leave_type=self.leave_type)
        self.assertEqual(lb.allocated, Decimal('12'))
        self.assertEqual(lb.carried_forward, Decimal('2'))
        self.assertEqual(lb.used, Decimal('3'))

    def test_invalid_employee(self):
        imp = self._run(
            "employee_code,leave_type_name,branch_code,year,allocated_days\n"
            "EMP-LB-NONEXIST,Annual Leave,HQ,2026,12\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertIn("not found", imp.import_obj.error_log.get(1, [""])[0])

    def test_cross_tenant_employee_blocked(self):
        # org2-only employee code must not be reachable from org1 importer
        org2_emp_user = User.objects.create_user(email="org2emp@lb.com")
        Employee.objects.create(
            organization=self.org2, employee_code="EMP-LB-ORG2-ONLY", user=org2_emp_user
        )
        imp = self._run(
            "employee_code,leave_type_name,branch_code,year,allocated_days\n"
            "EMP-LB-ORG2-ONLY,Annual Leave,HQ,2026,12\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertFalse(LeaveBalance.objects.filter(employee__organization=self.org1).exists())

    def test_cross_tenant_leave_type_blocked(self):
        imp = self._run(
            "employee_code,leave_type_name,branch_code,year,allocated_days\n"
            "EMP-LB-01,Nonexistent Type,HQ,2026,12\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')

    def test_no_leave_cycle_fails(self):
        imp = self._run(
            "employee_code,leave_type_name,branch_code,year,allocated_days\n"
            "EMP-LB-ORG1-01,Annual Leave,HQ,2099,12\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertIn("LeaveCycle", imp.import_obj.error_log.get(1, [""])[0])

    def test_negative_days_rejected(self):
        imp = self._run(
            "employee_code,leave_type_name,branch_code,year,allocated_days\n"
            "EMP-LB-ORG1-01,Annual Leave,HQ,2026,-5\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')

    def test_dry_run(self):
        imp = self._run(
            "employee_code,leave_type_name,branch_code,year,allocated_days\n"
            "EMP-LB-ORG1-01,Annual Leave,HQ,2026,10\n",
            dry_run=True
        )
        self.assertEqual(imp.import_obj.status, 'dry_run')
        self.assertFalse(LeaveBalance.objects.exists())

    def test_duplicate_upsert(self):
        LeaveBalance.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            leave_cycle=self.cycle, branch=self.branch,
            allocated=Decimal('5'), used=Decimal('1'), carried_forward=Decimal('0')
        )
        imp = self._run(
            "employee_code,leave_type_name,branch_code,year,allocated_days,used_days\n"
            "EMP-LB-ORG1-01,Annual Leave,HQ,2026,15,2\n"
        )
        self.assertEqual(imp.import_obj.status, 'completed')
        lb = LeaveBalance.objects.get(employee=self.employee, leave_type=self.leave_type)
        self.assertEqual(lb.allocated, Decimal('15'))
        self.assertEqual(lb.used, Decimal('2'))

    def test_rollback_on_partial_failure(self):
        imp = self._run(
            "employee_code,leave_type_name,branch_code,year,allocated_days\n"
            "EMP-LB-ORG1-01,Annual Leave,HQ,2026,10\n"
            "EMP-LB-NONEXIST,Annual Leave,HQ,2026,5\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertFalse(LeaveBalance.objects.exists())


# ---------------------------------------------------------------------------
# Salary Structure Importer Tests
# ---------------------------------------------------------------------------

class SalaryStructureImporterTestCase(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="SalOrg1")
        self.org2 = Organization.objects.create(name="SalOrg2")
        self.user = User.objects.create_user(email="sal@test.com", password="pwd")

        emp_user = User.objects.create_user(email="sal_emp@test.com", password="pwd")
        self.employee = Employee.objects.create(
            organization=self.org1, employee_code="EMP-SAL-ORG1-01", user=emp_user
        )

        self.comp_basic = SalaryComponent.objects.create(
            organization=self.org1, name="Basic", code="basic", kind="earning"
        )
        self.comp_hra = SalaryComponent.objects.create(
            organization=self.org1, name="HRA", code="hra", kind="earning"
        )

    def _run(self, csv_data, dry_run=False):
        obj = make_import(self.org1, self.user, 'salary_structure', csv_data)
        imp = SalaryStructureImporter(obj, dry_run=dry_run)
        imp.run()
        return imp

    def test_valid_structure_with_components(self):
        imp = self._run(
            "structure_name,component:basic,component:hra\n"
            "Standard,50000,20000\n"
        )
        self.assertEqual(imp.import_obj.status, 'completed')
        struct = SalaryStructure.objects.get(organization=self.org1, name="Standard")
        self.assertTrue(
            SalaryStructureComponent.objects.filter(structure=struct, component=self.comp_basic, amount=50000).exists()
        )
        self.assertTrue(
            SalaryStructureComponent.objects.filter(structure=struct, component=self.comp_hra, amount=20000).exists()
        )

    def test_valid_with_employee_compensation(self):
        imp = self._run(
            "structure_name,employee_code,basic_salary,effective_date,component:basic\n"
            "Standard,EMP-SAL-ORG1-01,60000,2026-01-01,60000\n"
        )
        self.assertEqual(imp.import_obj.status, 'completed')
        self.assertTrue(
            CompensationHistory.objects.filter(
                employee=self.employee, basic_salary=Decimal('60000')
            ).exists()
        )

    def test_unknown_component_code_fails(self):
        imp = self._run(
            "structure_name,component:unknown_code\n"
            "Standard,10000\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertIn("unknown_code", imp.import_obj.error_log.get(1, [""])[0])

    def test_cross_tenant_employee_blocked(self):
        org2_user = User.objects.create_user(email="org2sal@test.com")
        org2_emp = Employee.objects.create(
            organization=self.org2, employee_code="EMP-SAL-ORG2-ONLY", user=org2_user
        )
        imp = self._run(
            "structure_name,employee_code,basic_salary,effective_date\n"
            "Standard,EMP-SAL-ORG2-ONLY,50000,2026-01-01\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertFalse(CompensationHistory.objects.filter(employee__organization=self.org1).exists())

    def test_negative_amount_rejected(self):
        imp = self._run("structure_name,component:basic\nStandard,-1000\n")
        self.assertEqual(imp.import_obj.status, 'failed')

    def test_invalid_effective_date(self):
        imp = self._run(
            "structure_name,employee_code,basic_salary,effective_date\n"
            "Standard,EMP-SAL-ORG1-01,50000,NOT-A-DATE\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')

    def test_dry_run(self):
        imp = self._run("structure_name,component:basic\nDryRun,50000\n", dry_run=True)
        self.assertEqual(imp.import_obj.status, 'dry_run')
        self.assertFalse(SalaryStructure.objects.filter(organization=self.org1).exists())

    def test_rollback_on_partial_failure(self):
        imp = self._run(
            "structure_name,component:basic,component:unknown\n"
            "Standard,50000,10000\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertFalse(SalaryStructure.objects.filter(organization=self.org1).exists())


# ---------------------------------------------------------------------------
# Attendance Importer Tests
# ---------------------------------------------------------------------------

class AttendanceImporterTestCase(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="AttOrg1")
        self.org2 = Organization.objects.create(name="AttOrg2")
        self.user = User.objects.create_user(email="att@test.com", password="pwd")

        emp_user = User.objects.create_user(email="att_emp@test.com", password="pwd")
        self.employee = Employee.objects.create(
            organization=self.org1, employee_code="EMP-ATT-ORG1-01", user=emp_user
        )

        org2_user = User.objects.create_user(email="att_emp2@test.com", password="pwd")
        self.employee_org2 = Employee.objects.create(
            organization=self.org2, employee_code="EMP-ATT-ORG2-01", user=org2_user
        )

    def _run(self, csv_data, dry_run=False):
        obj = make_import(self.org1, self.user, 'attendance', csv_data)
        imp = AttendanceImporter(obj, dry_run=dry_run)
        imp.run()
        return imp

    def test_valid_present(self):
        imp = self._run(
            "employee_code,date,check_in,check_out,status\n"
            "EMP-ATT-ORG1-01,2026-10-01,2026-10-01T09:00:00,2026-10-01T18:00:00,present\n"
        )
        self.assertEqual(imp.import_obj.status, 'completed')
        self.assertTrue(
            Attendance.objects.filter(
                employee=self.employee, date=datetime.date(2026, 10, 1), status='present'
            ).exists()
        )

    def test_valid_absent_no_times(self):
        imp = self._run(
            "employee_code,date,check_in,check_out,status\n"
            "EMP-ATT-ORG1-01,2026-10-02,,,absent\n"
        )
        self.assertEqual(imp.import_obj.status, 'completed')
        att = Attendance.objects.get(employee=self.employee, date=datetime.date(2026, 10, 2))
        self.assertEqual(att.status, 'absent')
        self.assertIsNone(att.check_in)

    def test_invalid_status(self):
        imp = self._run(
            "employee_code,date,check_in,check_out,status\n"
            "EMP-ATT-ORG1-01,2026-10-03,,,on_leave\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertIn("Invalid status", imp.import_obj.error_log.get(1, [""])[0])

    def test_invalid_date(self):
        imp = self._run(
            "employee_code,date,check_in,check_out,status\n"
            "EMP-ATT-ORG1-01,01/10/2026,,,present\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')

    def test_checkout_before_checkin_rejected(self):
        imp = self._run(
            "employee_code,date,check_in,check_out,status\n"
            "EMP-ATT-ORG1-01,2026-10-04,2026-10-04T18:00:00,2026-10-04T09:00:00,present\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertIn("check_out cannot be before check_in", imp.import_obj.error_log.get(1, [""])[0])

    def test_cross_tenant_employee_blocked(self):
        # org2-only employee must not be reachable from org1 importer
        org2_only_user = User.objects.create_user(email="org2att_only@test.com")
        org2_emp = Employee.objects.create(
            organization=self.org2, employee_code="EMP-ATT-ORG2-ONLY", user=org2_only_user
        )
        imp = self._run(
            "employee_code,date,status\n"
            "EMP-ATT-ORG2-ONLY,2026-10-01,present\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertFalse(Attendance.objects.filter(employee__organization=self.org1).exists())

    def test_duplicate_upsert(self):
        Attendance.objects.create(
            employee=self.employee,
            date=datetime.date(2026, 10, 5),
            status='absent'
        )
        imp = self._run(
            "employee_code,date,status\n"
            "EMP-ATT-ORG1-01,2026-10-05,present\n"
        )
        self.assertEqual(imp.import_obj.status, 'completed')
        att = Attendance.objects.get(employee=self.employee, date=datetime.date(2026, 10, 5))
        self.assertEqual(att.status, 'present')

    def test_dry_run(self):
        imp = self._run(
            "employee_code,date,status\n"
            "EMP-ATT-ORG1-01,2026-10-06,present\n",
            dry_run=True
        )
        self.assertEqual(imp.import_obj.status, 'dry_run')
        self.assertFalse(Attendance.objects.filter(date=datetime.date(2026, 10, 6)).exists())

    def test_rollback_on_partial_failure(self):
        imp = self._run(
            "employee_code,date,status\n"
            "EMP-ATT-ORG1-01,2026-10-07,present\n"
            "EMP-ATT-NONEXIST,2026-10-08,present\n"
        )
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertFalse(Attendance.objects.exists())

    def test_missing_required_headers(self):
        imp = self._run("employee_code,date\nEMP-ATT-01,2026-10-09\n")
        self.assertEqual(imp.import_obj.status, 'failed')
        self.assertIn("Missing required columns", imp.import_obj.error_log.get(0, [""])[0])
