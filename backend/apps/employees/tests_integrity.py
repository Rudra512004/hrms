from django.test import TestCase
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.serializers import ValidationError as DRFValidationError
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.employees.serializers import EmployeeSerializer
from apps.organization.models import Organization, Department, Designation

User = get_user_model()

class EmployeeIntegrityTests(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name='Org 1')
        self.org2 = Organization.objects.create(name='Org 2')
        self.dept1 = Department.objects.create(organization=self.org1, name='Dept 1')
        self.desig1 = Designation.objects.create(organization=self.org1, name='Desig 1')
        self.dept2 = Department.objects.create(organization=self.org2, name='Dept 2')
        self.desig2 = Designation.objects.create(organization=self.org2, name='Desig 2')
        
        self.user1 = User.objects.create_user(email='emp1@example.com')
        self.user2 = User.objects.create_user(email='emp2@example.com')
        self.user3 = User.objects.create_user(email='emp3@example.com')

    def test_valid_same_organization_assignment(self):
        emp = Employee(user=self.user1, employee_code='E001', organization=self.org1, department=self.dept1, designation=self.desig1)
        emp.full_clean()
        emp.save()
        self.assertEqual(Employee.objects.count(), 1)

    def test_invalid_cross_organization_department(self):
        emp = Employee(user=self.user1, employee_code='E001', organization=self.org1, department=self.dept2)
        with self.assertRaises(DjangoValidationError):
            emp.full_clean()
            emp.save()

    def test_invalid_cross_organization_designation(self):
        emp = Employee(user=self.user1, employee_code='E001', organization=self.org1, designation=self.desig2)
        with self.assertRaises(DjangoValidationError):
            emp.full_clean()
            emp.save()

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
