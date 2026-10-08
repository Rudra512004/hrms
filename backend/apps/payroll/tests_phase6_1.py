from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.utils import timezone
from datetime import timedelta
from apps.payroll.models import (
    SalaryComponent, SalaryStructure, SalaryStructureComponent, CompensationHistory
)
from apps.organization.models import Organization
from apps.employees.models import Employee
from apps.payroll.formula_engine import SafeFormulaEvaluator, FormulaError
from apps.payroll.dependency_resolver import ComponentDependencyResolver, DependencyError
from apps.authorization.models import Permission, Role, RolePermission, UserRole, ScopeChoices
from django.contrib.auth import get_user_model
User = get_user_model()

class Phase61PayrollModelsTest(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

    def test_salary_component_creation(self):
        # Valid component
        comp = SalaryComponent.objects.create(
            organization=self.org1,
            name="Basic Salary",
            code="BASIC",
            kind="earning",
            calculation_type="flat",
            is_prorated=True
        )
        self.assertEqual(comp.code, "BASIC")
        self.assertTrue(comp.is_prorated)
        self.assertFalse(comp.is_taxable)

        # Duplicate code in same org should fail via IntegrityError due to unique constraint
        with self.assertRaises(IntegrityError):
            SalaryComponent.objects.create(
                organization=self.org1,
                name="Basic Again",
                code="BASIC",
                kind="earning"
            )

    def test_organization_isolation(self):
        # Same code in different org should succeed
        SalaryComponent.objects.create(
            organization=self.org1,
            name="Basic",
            code="BASIC",
            kind="earning"
        )
        SalaryComponent.objects.create(
            organization=self.org2,
            name="Basic",
            code="BASIC",
            kind="earning"
        )

    def test_salary_structure_cross_org_rejected(self):
        struct = SalaryStructure.objects.create(organization=self.org1, name="Standard")
        comp2 = SalaryComponent.objects.create(organization=self.org2, name="HRA", code="HRA", kind="earning")

        # Assigning an org2 component to an org1 structure
        assignment = SalaryStructureComponent(structure=struct, component=comp2)
        with self.assertRaises(ValidationError):
            assignment.clean()

class Phase61FormulaEngineTest(TestCase):
    def setUp(self):
        self.evaluator = SafeFormulaEvaluator(allowed_variables={'BASIC', 'GROSS', 'ATTENDANCE_MULTIPLIER'})

    def test_basic_arithmetic(self):
        context = {'BASIC': Decimal('10000')}
        self.assertEqual(self.evaluator.evaluate("BASIC + 5000", context), Decimal('15000.00'))
        self.assertEqual(self.evaluator.evaluate("BASIC - 2000", context), Decimal('8000.00'))
        self.assertEqual(self.evaluator.evaluate("BASIC * 2", context), Decimal('20000.00'))
        self.assertEqual(self.evaluator.evaluate("BASIC / 2", context), Decimal('5000.00'))

    def test_percentage_calculation(self):
        context = {'BASIC': Decimal('10000')}
        self.assertEqual(self.evaluator.evaluate("BASIC * 0.40", context), Decimal('4000.00'))

    def test_parentheses_and_multiple_vars(self):
        context = {'BASIC': Decimal('10000'), 'ATTENDANCE_MULTIPLIER': Decimal('0.5')}
        self.assertEqual(self.evaluator.evaluate("(BASIC + 2000) * ATTENDANCE_MULTIPLIER", context), Decimal('6000.00'))

    def test_division_by_zero(self):
        context = {'BASIC': Decimal('10000')}
        with self.assertRaisesMessage(FormulaError, "Division by zero in formula."):
            self.evaluator.evaluate("BASIC / 0", context)

    def test_invalid_syntax(self):
        context = {'BASIC': Decimal('10000')}
        with self.assertRaises(FormulaError):
            self.evaluator.evaluate("BASIC + * 5", context)

    def test_unknown_variable(self):
        context = {'BASIC': Decimal('10000')}
        with self.assertRaisesMessage(FormulaError, "Unknown or unapproved variable: HRA"):
            self.evaluator.evaluate("BASIC + HRA", context)

    def test_missing_context(self):
        self.evaluator.allowed_variables.add('HRA')
        context = {'BASIC': Decimal('10000')}
        with self.assertRaisesMessage(FormulaError, "Variable 'HRA' not provided in context."):
            self.evaluator.evaluate("BASIC + HRA", context)

    def test_security_rejections(self):
        context = {'BASIC': Decimal('10000')}
        
        # Function call rejected
        with self.assertRaises(FormulaError):
            self.evaluator.evaluate("sum(1, 2)", context)
            
        # Attribute access rejected
        with self.assertRaises(FormulaError):
            self.evaluator.evaluate("BASIC.__class__", context)
            
        # Import rejected (handled by ast syntax or ast evaluation restrictions)
        with self.assertRaises((FormulaError, SyntaxError)):
            self.evaluator.evaluate("import os", context)
            
        # String expressions rejected
        with self.assertRaises(FormulaError):
            self.evaluator.evaluate("BASIC + '1000'", context)
            
        # Assignment rejected
        with self.assertRaises((FormulaError, SyntaxError)):
            self.evaluator.evaluate("BASIC = 5", context)

class Phase61DependencyEngineTest(TestCase):
    def setUp(self):
        self.resolver = ComponentDependencyResolver(provided_variables={'BASIC'})

    def test_simple_dependency(self):
        components = [
            {'code': 'HRA', 'formula_expression': 'BASIC * 0.4', 'calculation_type': 'formula'},
            {'code': 'DA', 'formula_expression': 'BASIC * 0.1', 'calculation_type': 'formula'}
        ]
        order = self.resolver.resolve_order(components)
        self.assertEqual(set(order), {'HRA', 'DA'}) # Both depend only on BASIC, order can be any

    def test_multi_level_dependency(self):
        components = [
            {'code': 'GROSS', 'formula_expression': 'BASIC + HRA + SPECIAL', 'calculation_type': 'formula'},
            {'code': 'SPECIAL', 'formula_expression': 'BASIC * 0.2', 'calculation_type': 'formula'},
            {'code': 'HRA', 'formula_expression': 'BASIC * 0.4', 'calculation_type': 'formula'}
        ]
        order = self.resolver.resolve_order(components)
        # HRA and SPECIAL must come before GROSS
        self.assertTrue(order.index('HRA') < order.index('GROSS'))
        self.assertTrue(order.index('SPECIAL') < order.index('GROSS'))

    def test_missing_dependency(self):
        components = [
            {'code': 'HRA', 'formula_expression': 'UNKNOWN_COMP * 0.4', 'calculation_type': 'formula'},
        ]
        with self.assertRaisesMessage(DependencyError, "Component 'HRA' references unknown variable/component 'UNKNOWN_COMP'"):
            self.resolver.resolve_order(components)

    def test_self_reference(self):
        components = [
            {'code': 'HRA', 'formula_expression': 'HRA * 0.4', 'calculation_type': 'formula'},
        ]
        with self.assertRaisesMessage(DependencyError, "Component 'HRA' contains self-reference."):
            self.resolver.resolve_order(components)

    def test_circular_dependency(self):
        components = [
            {'code': 'A', 'formula_expression': 'B * 0.4', 'calculation_type': 'formula'},
            {'code': 'B', 'formula_expression': 'A * 0.4', 'calculation_type': 'formula'}
        ]
        with self.assertRaisesMessage(DependencyError, "Circular dependency detected"):
            self.resolver.resolve_order(components)

class Phase61EmployeeAssignmentTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")
        self.emp_user = User.objects.create_user(email="emp@test.com", password="pwd")
        self.emp = Employee.objects.create(
            user=self.emp_user,
            organization=self.org,
            employee_code="EMP001",
        )
        self.struct = SalaryStructure.objects.create(organization=self.org, name="Standard")
        self.struct2 = SalaryStructure.objects.create(organization=self.org2, name="Other")

    def test_valid_assignment(self):
        assignment = CompensationHistory.objects.create(
            employee=self.emp,
            salary_structure=self.struct,
            effective_from=timezone.now().date(),
            basic_salary=10000
        )
        self.assertEqual(assignment.salary_structure, self.struct)

    def test_overlapping_effective_dates_fail(self):
        with self.assertRaises(IntegrityError):
            CompensationHistory.objects.create(
                employee=self.emp,
                salary_structure=self.struct,
                effective_from=timezone.now().date(),
                effective_to=timezone.now().date() - timedelta(days=1),
                basic_salary=10000
            )

class Phase61RBACTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org")
        self.user = User.objects.create_user(email="admin@test.com", password="password", status='active')
        self.role = Role.objects.create(organization=self.org, name="Payroll Admin")
        UserRole.objects.create(user=self.user, role=self.role, scope=ScopeChoices.ORGANIZATION)
        
        self.perm = Permission.objects.create(codename="salary_structure.view", resource="salary_structure", action="view")
        RolePermission.objects.create(role=self.role, permission=self.perm)

    def test_authorized_user_can_access(self):
        from apps.authorization.services import AuthorizationService
        self.assertTrue(AuthorizationService.has_permission(self.user, "salary_structure.view"))

    def test_unauthorized_user_denied(self):
        from apps.authorization.services import AuthorizationService
        self.assertFalse(AuthorizationService.has_permission(self.user, "salary_structure.manage"))
