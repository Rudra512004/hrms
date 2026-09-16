from django.test import TestCase
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.serializers import ValidationError as DRFValidationError
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.employees.serializers import EmployeeSerializer
from apps.organization.models import Organization, Department, Designation, Branch, Team

User = get_user_model()

class EmployeeIntegrityTests(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name='Org 1')
        self.org2 = Organization.objects.create(name='Org 2')
        self.branch1 = Branch.objects.create(organization=self.org1, name='Branch 1', radius=100)
        self.branch2 = Branch.objects.create(organization=self.org1, name='Branch 2', radius=100)
        self.branch_org2 = Branch.objects.create(organization=self.org2, name='Branch Org2', radius=100)
        self.dept1 = Department.objects.create(branch=self.branch1, name='Dept 1')
        self.dept_b2 = Department.objects.create(branch=self.branch2, name='Dept B2')
        self.desig1 = Designation.objects.create(organization=self.org1, name='Desig 1')
        self.dept2 = Department.objects.create(branch=self.branch_org2, name='Dept 2')
        self.desig2 = Designation.objects.create(organization=self.org2, name='Desig 2')
        
        self.team1 = Team.objects.create(department=self.dept1, name='Team 1')
        self.team2 = Team.objects.create(department=self.dept2, name='Team 2')
        self.team_b2 = Team.objects.create(department=self.dept_b2, name='Team B2')
        self.team_inactive = Team.objects.create(department=self.dept1, name='Team Inactive', is_active=False)
        
        self.user1 = User.objects.create_user(email='emp1@example.com')
        self.user2 = User.objects.create_user(email='emp2@example.com')
        self.user3 = User.objects.create_user(email='emp3@example.com')

    def test_valid_same_organization_assignment(self):
        emp = Employee(user=self.user1, employee_code='E001', organization=self.org1, branch=self.branch1, department=self.dept1, designation=self.desig1)
        emp.full_clean()
        emp.save()
        self.assertEqual(Employee.objects.count(), 1)

    def test_invalid_cross_organization_department(self):
        emp = Employee(user=self.user1, employee_code='E001', organization=self.org1, department=self.dept2)
        with self.assertRaises(DjangoValidationError):
            emp.full_clean()
            emp.save()

    def test_invalid_cross_branch_department(self):
        # Assigning an employee to branch 1, but department in branch 2
        emp = Employee(user=self.user1, employee_code='E002', organization=self.org1, branch=self.branch1, department=self.dept_b2)
        with self.assertRaises(DjangoValidationError):
            emp.full_clean()
            emp.save()

    def test_invalid_cross_organization_designation(self):
        emp = Employee(user=self.user1, employee_code='E001', organization=self.org1, designation=self.desig2)
        with self.assertRaises(DjangoValidationError):
            emp.full_clean()
            emp.save()

    def test_valid_team_assignment(self):
        emp = Employee(user=self.user1, employee_code='E003', organization=self.org1, branch=self.branch1, department=self.dept1, team=self.team1)
        emp.full_clean()
        emp.save()
        self.assertEqual(emp.team, self.team1)

    def test_invalid_cross_department_team(self):
        # Assigning an employee to dept 1, but team in dept b2
        emp = Employee(user=self.user1, employee_code='E004', organization=self.org1, branch=self.branch1, department=self.dept1, team=self.team_b2)
        with self.assertRaisesMessage(DjangoValidationError, 'Team must belong to the same department as the employee.'):
            emp.full_clean()

    def test_invalid_inactive_team_for_active_employee(self):
        emp = Employee(user=self.user1, employee_code='E005', organization=self.org1, branch=self.branch1, department=self.dept1, team=self.team_inactive)
        with self.assertRaisesMessage(DjangoValidationError, 'Cannot assign an inactive team to an active employee.'):
            emp.full_clean()

    def test_null_relationships_remain_valid(self):
        emp = Employee(user=self.user1, employee_code='E001')
        emp.full_clean()
        emp.save()
        self.assertEqual(Employee.objects.count(), 1)

    def test_reporting_manager_valid(self):
        manager = Employee.objects.create(user=self.user1, employee_code='M001', organization=self.org1)
        emp = Employee(user=self.user2, employee_code='E001', organization=self.org1, reporting_manager=manager)
        emp.full_clean()
        emp.save()
        self.assertEqual(emp.reporting_manager, manager)

    def test_reporting_manager_self_reporting_rejected(self):
        emp = Employee.objects.create(user=self.user1, employee_code='E001', organization=self.org1)
        emp.reporting_manager = emp
        with self.assertRaises(DjangoValidationError):
            emp.full_clean()
            emp.save()

    def test_reporting_manager_cross_organization_rejected(self):
        manager = Employee.objects.create(user=self.user1, employee_code='M001', organization=self.org1)
        emp = Employee(user=self.user2, employee_code='E001', organization=self.org2, reporting_manager=manager)
        with self.assertRaises(DjangoValidationError):
            emp.full_clean()
            emp.save()

    def test_serializer_validation(self):
        emp = Employee.objects.create(user=self.user1, employee_code='E001')
        serializer = EmployeeSerializer(emp, data={'organization': self.org1.id, 'department': self.dept2.id}, partial=True)
        with self.assertRaises(DRFValidationError):
            serializer.is_valid(raise_exception=True)

    def test_serializer_cross_branch_validation(self):
        emp = Employee.objects.create(user=self.user1, employee_code='E001', organization=self.org1)
        serializer = EmployeeSerializer(emp, data={'branch': self.branch1.id, 'department': self.dept_b2.id}, partial=True)
        with self.assertRaises(DRFValidationError):
            serializer.is_valid(raise_exception=True)

    def test_serializer_cross_department_team_validation(self):
        emp = Employee.objects.create(user=self.user1, employee_code='E006', organization=self.org1, branch=self.branch1, department=self.dept1)
        serializer = EmployeeSerializer(emp, data={'team': self.team_b2.id}, partial=True)
        with self.assertRaisesMessage(DRFValidationError, 'Team must belong to the same department as the employee.'):
            serializer.is_valid(raise_exception=True)
