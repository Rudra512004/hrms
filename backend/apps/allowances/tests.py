from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.utils import timezone
from datetime import timedelta

from apps.organization.models import Organization, Branch, Department, OrganizationMembership
from apps.employees.models import Employee, Designation
from apps.accounts.models import User
from apps.authorization.models import Permission, Role, RolePermission, UserRole
from apps.authorization.services import AuthorizationService
from apps.allowances.models import AllowanceType, EmployeeAllowance, ReimbursementClaim
from unittest.mock import patch

class AllowanceTestBase(TestCase):
    def setUp(self):
        # Patch NetworkAccessService to always allow remote access during tests
        self.network_patcher = patch('apps.authorization.network.NetworkAccessService.is_remote_access_allowed', return_value=True)
        self.network_patcher.start()
        
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        self.branch1 = Branch.objects.create(organization=self.org1, name="Branch 1")
        self.dept1 = Department.objects.create(branch=self.branch1, name="Dept 1")
        self.desig1 = Designation.objects.create(organization=self.org1, name="Desig 1")

        self.branch2 = Branch.objects.create(organization=self.org2, name="Branch 2")
        self.dept2 = Department.objects.create(branch=self.branch2, name="Dept 2")
        self.desig2 = Designation.objects.create(organization=self.org2, name="Desig 2")

        self.user1 = User.objects.create_user(email="emp1@org1.com", password="password", status="active")
        self.emp1 = Employee.objects.create(
            user=self.user1, organization=self.org1, branch=self.branch1, department=self.dept1, designation=self.desig1, employee_code="E001"
        )
        OrganizationMembership.objects.get_or_create(user=self.user1, organization=self.org1, defaults={'status': 'active'})
        self.emp1.user.is_verified = True
        self.emp1.user.save()

        self.user2 = User.objects.create_user(email="emp2@org2.com", password="password", status="active")
        self.emp2 = Employee.objects.create(
            user=self.user2, organization=self.org2, branch=self.branch2, department=self.dept2, designation=self.desig2, employee_code="E002"
        )
        OrganizationMembership.objects.get_or_create(user=self.user2, organization=self.org2, defaults={'status': 'active'})
        self.emp2.user.is_verified = True
        self.emp2.user.save()

        self.hr_user = User.objects.create_user(email="hr@org1.com", password="password", status="active")
        self.hr_emp = Employee.objects.create(
            user=self.hr_user, organization=self.org1, branch=self.branch1, department=self.dept1, designation=self.desig1, employee_code="HR001"
        )
        OrganizationMembership.objects.get_or_create(user=self.hr_user, organization=self.org1, defaults={'status': 'active'})
        self.hr_emp.user.is_verified = True
        self.hr_emp.user.save()

        self.permissions = {
            'allowance.view': Permission.objects.create(codename='allowance.view', resource='allowance', action='view'),
            'allowance.manage': Permission.objects.create(codename='allowance.manage', resource='allowance', action='manage'),
            'allowance.assign': Permission.objects.create(codename='allowance.assign', resource='allowance', action='assign'),
            'reimbursement.view': Permission.objects.create(codename='reimbursement.view', resource='reimbursement', action='view'),
            'reimbursement.create': Permission.objects.create(codename='reimbursement.create', resource='reimbursement', action='create'),
            'reimbursement.approve': Permission.objects.create(codename='reimbursement.approve', resource='reimbursement', action='approve'),
            'reimbursement.pay': Permission.objects.create(codename='reimbursement.pay', resource='reimbursement', action='pay'),
        }

        self.hr_role = Role.objects.create(organization=self.org1, name="HR Role")
        for perm in self.permissions.values():
            RolePermission.objects.create(role=self.hr_role, permission=perm)
        UserRole.objects.create(user=self.hr_user, role=self.hr_role)

        self.emp_role = Role.objects.create(organization=self.org1, name="Emp Role")
        RolePermission.objects.create(role=self.emp_role, permission=self.permissions['allowance.view'])
        RolePermission.objects.create(role=self.emp_role, permission=self.permissions['reimbursement.view'])
        RolePermission.objects.create(role=self.emp_role, permission=self.permissions['reimbursement.create'])
        UserRole.objects.create(user=self.user1, role=self.emp_role)

        self.allowance_type1 = AllowanceType.objects.create(
            organization=self.org1, name="Travel Allowance", code="TA", category="travel", calculation_type="fixed", default_amount=1000
        )
        self.allowance_type2 = AllowanceType.objects.create(
            organization=self.org2, name="Housing Allowance", code="HRA", category="housing", calculation_type="fixed", default_amount=2000
        )

    def tearDown(self):
        self.network_patcher.stop()
        super().tearDown()

class AllowanceModelTests(AllowanceTestBase):
    def test_allowance_assignment(self):
        assignment = EmployeeAllowance.objects.create(
            organization=self.org1, employee=self.emp1, allowance_type=self.allowance_type1,
            amount=1000, frequency="monthly", effective_from=timezone.now().date()
        )
        self.assertEqual(assignment.organization, self.org1)

    def test_reimbursement_lifecycle(self):
        claim = ReimbursementClaim.objects.create(
            organization=self.org1, employee=self.emp1, allowance_type=self.allowance_type1,
            amount_claimed=500, expense_date=timezone.now().date(), status="draft"
        )
        self.assertEqual(claim.status, "draft")
        claim.status = "submitted"
        claim.save()
        self.assertEqual(claim.status, "submitted")

class AllowanceAPITests(AllowanceTestBase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def test_hr_can_create_allowance_type(self):
        self.client.force_authenticate(user=self.hr_user)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org1.id))
        
        url = reverse('allowances:allowancetype-list')
        data = {
            "name": "Food Allowance",
            "code": "FA",
            "category": "food",
            "calculation_type": "fixed",
            "frequency": "monthly",
            "default_amount": "500.00"
        }
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_emp_cannot_create_allowance_type(self):
        self.client.force_authenticate(user=self.user1)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org1.id))
        url = reverse('allowances:allowancetype-list')
        res = self.client.post(url, {"name": "Test"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_tenant_isolation(self):
        self.client.force_authenticate(user=self.user1)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org1.id))
        
        # Grant view permission to user1
        emp_role = Role.objects.create(organization=self.org1, name="Employee Role")
        RolePermission.objects.create(role=emp_role, permission=self.permissions['allowance.view'])
        RolePermission.objects.create(role=emp_role, permission=self.permissions['reimbursement.create'])
        UserRole.objects.create(user=self.user1, role=emp_role)

        url = reverse('allowances:allowancetype-list')
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = [t['id'] for t in res.data['results']] if 'results' in res.data else [t['id'] for t in res.data]
        self.assertIn(self.allowance_type1.id, ids)
        self.assertNotIn(self.allowance_type2.id, ids)

class ReimbursementWorkflowTests(AllowanceTestBase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.claim = ReimbursementClaim.objects.create(
            organization=self.org1, employee=self.emp1, allowance_type=self.allowance_type1,
            amount_claimed=500, expense_date=timezone.now().date(), status="submitted"
        )
        # Grant permissions to user1 for submitting claims
        emp_role = Role.objects.create(organization=self.org1, name="Employee Role")
        RolePermission.objects.create(role=emp_role, permission=self.permissions['reimbursement.create'])
        UserRole.objects.create(user=self.user1, role=emp_role)

    def test_hr_can_approve(self):
        self.client.force_authenticate(user=self.hr_user)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org1.id))
        url = reverse('allowances:reimbursementclaim-approve', kwargs={'pk': self.claim.pk})
        res = self.client.post(url, {"amount_approved": "500"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, "approved")

    def test_emp_cannot_approve_own_claim(self):
        self.client.force_authenticate(user=self.user1)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org1.id))
        url = reverse('allowances:reimbursementclaim-approve', kwargs={'pk': self.claim.pk})
        res = self.client.post(url, {"amount_approved": "500"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_emp_submit_claim(self):
        self.client.force_authenticate(user=self.user1)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org1.id))
        url = reverse('allowances:reimbursementclaim-list')
        data = {
            "allowance_type": self.allowance_type1.id,
            "amount_claimed": "200.00",
            "expense_date": timezone.now().date().isoformat(),
            "description": "Lunch",
            "status": "submitted"
        }
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
