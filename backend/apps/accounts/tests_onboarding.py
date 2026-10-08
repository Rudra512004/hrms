from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from unittest.mock import patch
from apps.accounts.models import TenantOwnerRegistration, UserStatus
from apps.organization.models import Organization, Branch, OrganizationMembership
from apps.employees.models import Employee, EmploymentStatus
from django.urls import reverse
from apps.authorization.models import Permission, UserRole
from django.core.cache import cache

User = get_user_model()

class OnboardingLifecycleTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.registration_url = reverse('tenant-owner-register')
        self.activation_url = reverse('activate')
        self.login_url = reverse('login')
        self.setup_url = reverse('tenant-organization-setup')
        
        # Setup permissions for the Owner Role
        for codename in (
            'organization.view', 'organization.manage', 'branch.view', 'branch.manage',
            'employee.view', 'employee.create', 'role.view', 'role.assign',
            'permission.view', 'permission.assign',
        ):
            resource, action = codename.split('.')
            Permission.objects.get_or_create(name=codename, codename=codename, resource=resource, action=action)

        
    def test_happy_path_onboarding(self):
        # 1. Registration
        reg_data = {
            'first_name': 'Alice',
            'last_name': 'Smith',
            'email': 'alice@example.com'
        }
        res = self.client.post(self.registration_url, reg_data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        
        user = User.objects.get(email='alice@example.com')
        self.assertEqual(user.status, UserStatus.INVITED)
        self.assertTrue(hasattr(user, 'tenant_owner_registration'))
        
        # 2. Extract activation details
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        
        # 3. Activation
        activation_data = {
            'uid': uid,
            'token': token,
            'password': 'SecurePassword123!'
        }
        res = self.client.post(self.activation_url, activation_data, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        user.refresh_from_db()
        self.assertEqual(user.status, UserStatus.ACTIVE)
        self.assertIsNotNone(user.tenant_owner_registration.verified_at)
        
        # 4. Authentication (Login)
        login_data = {
            'email': 'alice@example.com',
            'password': 'SecurePassword123!'
        }
        res = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        auth_token = res.data['token']
        
        # 5. Organization Setup
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + auth_token)
        setup_data = {
            'name': 'Alice Corp',
            'status': 'active',
            'working_calendar': {'work_days': '1,2,3,4,5'},
            'attendance_policy': {
                'is_office_gps_enabled': True,
                'is_office_ip_enabled': False,
                'is_wfh_enabled': True,
                'wfh_bypasses_office_restrictions': True
            },
            'branches': [
                {
                    'name': 'HQ',
                    'radius': 150.0
                }
            ]
        }
        res = self.client.post(self.setup_url, setup_data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        
        # Verification
        org = Organization.objects.get(name='Alice Corp')
        branch = Branch.objects.get(organization=org, name='HQ')
        self.assertTrue(hasattr(branch, 'working_calendar'))
        membership = OrganizationMembership.objects.get(user=user, organization=org)
        self.assertEqual(membership.status, 'active')
        employee = Employee.objects.get(user=user, organization=org)
        self.assertEqual(employee.employee_code, 'OWNER-001')
        self.assertEqual(employee.employment_status, EmploymentStatus.ACTIVE)
        
        user_role = UserRole.objects.get(user=user)
        self.assertEqual(user_role.role.name, 'Organization Owner')
        self.assertEqual(user_role.role.organization, org)
        
        # 6. Check tenant context and access
        res = self.client.get('/api/v1/organization/organizations/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['name'], 'Alice Corp')
        
    def test_activation_edge_cases(self):
        user = User.objects.create_user(email='bob@example.com', first_name='Bob', status=UserStatus.INVITED)
        TenantOwnerRegistration.objects.create(user=user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        
        # Invalid token
        res = self.client.post(self.activation_url, {'uid': uid, 'token': 'invalid', 'password': 'SecurePassword123!'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Missing data
        res = self.client.post(self.activation_url, {'uid': uid, 'token': token}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Already used token / Already active
        res = self.client.post(self.activation_url, {'uid': uid, 'token': token, 'password': 'SecurePassword123!'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        res = self.client.post(self.activation_url, {'uid': uid, 'token': token, 'password': 'SecurePassword123!'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_registration_edge_cases(self):
        # Valid
        res = self.client.post(self.registration_url, {'first_name': 'C', 'last_name': 'D', 'email': 'c@d.com'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        
        # Duplicate
        res = self.client.post(self.registration_url, {'first_name': 'C', 'last_name': 'D', 'email': 'c@d.com'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Invalid email
        res = self.client.post(self.registration_url, {'first_name': 'C', 'last_name': 'D', 'email': 'invalid'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_duplicate_organization_setup(self):
        user = User.objects.create_user(email='dup@example.com', password='password', status=UserStatus.ACTIVE)
        TenantOwnerRegistration.objects.create(user=user, verified_at=timezone.now())
        self.client.force_authenticate(user=user)
        
        setup_data = {
            'name': 'Dup Corp',
            'status': 'active',
            'branches': [{'name': 'HQ'}]
        }
        
        res = self.client.post(self.setup_url, setup_data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        
        res = self.client.post(self.setup_url, setup_data, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        
        self.assertEqual(Organization.objects.filter(name='Dup Corp').count(), 1)
        org = Organization.objects.get(name='Dup Corp')
        self.assertEqual(Branch.objects.filter(organization=org).count(), 1)
        self.assertEqual(OrganizationMembership.objects.filter(user=user).count(), 1)
        self.assertEqual(Employee.objects.filter(user=user).count(), 1)

    def test_tenant_isolation(self):
        user_a = User.objects.create_user(email='ownera@example.com', password='password', status=UserStatus.ACTIVE)
        TenantOwnerRegistration.objects.create(user=user_a, verified_at=timezone.now())
        self.client.force_authenticate(user=user_a)
        res_a = self.client.post(self.setup_url, {'name': 'Tenant A', 'status': 'active', 'branches': [{'name': 'Branch A'}]}, format='json')
        self.assertEqual(res_a.status_code, status.HTTP_201_CREATED)
        org_a = Organization.objects.get(name='Tenant A')
        branch_a = Branch.objects.get(organization=org_a)
        
        user_b = User.objects.create_user(email='ownerb@example.com', password='password', status=UserStatus.ACTIVE)
        TenantOwnerRegistration.objects.create(user=user_b, verified_at=timezone.now())
        self.client.force_authenticate(user=user_b)
        res_b = self.client.post(self.setup_url, {'name': 'Tenant B', 'status': 'active', 'branches': [{'name': 'Branch B'}]}, format='json')
        self.assertEqual(res_b.status_code, status.HTTP_201_CREATED)
        org_b = Organization.objects.get(name='Tenant B')
        branch_b = Branch.objects.get(organization=org_b)
        
        self.client.force_authenticate(user=user_b)
        res = self.client.get('/api/v1/organization/organizations/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['name'], 'Tenant B')
        
        res = self.client.get(f'/api/v1/organization/branches/{branch_a.id}/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        
        res = self.client.get('/api/v1/organization/branches/')
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['name'], 'Branch B')
        
        emp_a = Employee.objects.get(user=user_a)
        res = self.client.get(f'/api/v1/employees/employees/{emp_a.id}/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch('apps.employees.models.Employee.objects.create')
    def test_transaction_rollback_on_failure(self, mock_create):
        mock_create.side_effect = Exception("Database error")
        
        user = User.objects.create_user(email='roll@example.com', password='password', status=UserStatus.ACTIVE)
        TenantOwnerRegistration.objects.create(user=user, verified_at=timezone.now())
        self.client.force_authenticate(user=user)
        
        setup_data = {
            'name': 'Rollback Corp',
            'status': 'active',
            'branches': [{'name': 'HQ'}]
        }
        
        with self.assertRaises(Exception):
            self.client.post(self.setup_url, setup_data, format='json')
        
        self.assertFalse(Organization.objects.filter(name='Rollback Corp').exists())
        self.assertFalse(OrganizationMembership.objects.filter(user=user).exists())
