from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.organization.models import Organization, OrganizationMembership
from apps.authorization.models import Role
from apps.employees.models import Employee
from unittest.mock import patch

User = get_user_model()

class SaaSLifecycleIntegrationTests(APITestCase):
    def setUp(self):
        from apps.authorization.models import Permission
        Permission.objects.get_or_create(codename='employee.create', defaults={'name': 'Create Employee', 'resource': 'employee', 'action': 'create'})
        Permission.objects.get_or_create(codename='department.view', defaults={'name': 'View Departments', 'resource': 'department', 'action': 'view'})

    @patch('apps.accounts.views.NotificationService.send_tenant_owner_verification_email', return_value=True)
    @patch('apps.employees.views.NotificationService.send_employee_onboarding_email', return_value=True)
    @patch('apps.authorization.permissions.NetworkAccessService.is_remote_access_allowed', return_value=True)
    def test_complete_saas_lifecycle_flow(self, mock_network, mock_onboard, mock_verify):
        # 1. Register
        register_url = reverse('tenant-owner-register')
        res = self.client.post(register_url, {
            'email': 'founder@startup.com',
            'first_name': 'Frank',
            'last_name': 'Founder'
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        
        user = User.objects.get(email='founder@startup.com')
        # Simulate email verification (registration.verified_at = now)
        registration = user.tenant_owner_registration
        from django.utils import timezone
        registration.verified_at = timezone.now()
        registration.save()
        user.status = 'active'
        user.save()
        
        # 2. Login (using force_authenticate for test simplicity)
        self.client.force_authenticate(user=user)
        
        # 3. Create Organization
        setup_url = reverse('tenant-organization-setup')
        res = self.client.post(setup_url, {
            'name': 'Startup Inc',
            'branches': [{
                'name': 'HQ',
                'address': '123 Tech St, SF, CA, USA, 94105'
            }]
        }, format='json')
        if res.status_code != status.HTTP_201_CREATED:
            print("SETUP ERRORS:", res.data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        org = Organization.objects.get(name='Startup Inc')
        
        # Verify ownership / context
        self.assertEqual(OrganizationMembership.objects.filter(user=user, organization=org).count(), 1)
        self.assertTrue(user.user_roles.filter(role__name='Organization Owner', role__organization=org).exists())
        
        # We need to simulate the X-Organization-Id header for the invitation request
        # because EmployeeManagementViewSet requires tenant context to assign the employee to the right org
        # 4. User Invitation
        invite_url = '/api/v1/employees/management/'
        res = self.client.post(invite_url, {
            'email': 'dev@startup.com',
            'first_name': 'Dave',
            'last_name': 'Developer'
        }, HTTP_X_ORGANIZATION_ID=str(org.id), format='json')
        if res.status_code != status.HTTP_201_CREATED:
            print("INVITE ERRORS:", res.data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        
        dev_user = User.objects.get(email='dev@startup.com')
        # Employee should be created
        dev_employee = Employee.objects.get(user=dev_user)
        self.assertEqual(dev_employee.organization, org)
        # Membership auto-provisioned
        self.assertEqual(OrganizationMembership.objects.filter(user=dev_user, organization=org).count(), 1)

    def test_multi_org_switching_and_fail_closed(self):
        org_a = Organization.objects.create(name='Org A')
        org_b = Organization.objects.create(name='Org B')
        
        user = User.objects.create_user(email='multi@example.com', password='Password123!')
        user.status = 'active'
        user.save()
        Employee.objects.create(user=user, organization=org_a, employee_code='EMP-A')
        Employee.objects.create(user=user, organization=org_b, employee_code='EMP-B')
        
        from apps.authorization.models import Permission, Role, RolePermission, ScopeChoices, UserRole
        role_a = Role.objects.create(organization=org_a, name='Admin A')
        role_b = Role.objects.create(organization=org_b, name='Admin B')
        perm, _ = Permission.objects.get_or_create(codename='department.view', defaults={'name': 'View Departments', 'resource': 'department', 'action': 'view'})
        RolePermission.objects.create(role=role_a, permission=perm)
        RolePermission.objects.create(role=role_b, permission=perm)
        ur_a = UserRole.objects.create(user=user, role=role_a, assigned_by=user, scope=ScopeChoices.ORGANIZATION)
        UserRole.objects.create(user=user, role=role_b, assigned_by=user, scope=ScopeChoices.ORGANIZATION)
        
        # Memberships auto-provisioned via signal
        
        self.client.force_authenticate(user=user)
        
        url = reverse('department-list') # any org-scoped endpoint
        
        # Missing context -> Fail closed (403 Forbidden since _resolve_organization returns None)
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        
        # Explicit Org A
        res = self.client.get(url, HTTP_X_ORGANIZATION_ID=str(org_a.id))
        if res.status_code != status.HTTP_200_OK:
            print("ORG A 403:", res.data)
            print("UR A active?", ur_a.is_revoked, ur_a.expires_at)
            print("Role A active?", role_a.is_active)
            print("Perm active?", perm.is_active)
            from apps.authorization.services import AuthorizationService
            print("Effective permissions:", AuthorizationService.get_effective_permissions(user, org_a))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Explicit Org B
        res = self.client.get(url, HTTP_X_ORGANIZATION_ID=str(org_b.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Invalid Context
        res = self.client.get(url, HTTP_X_ORGANIZATION_ID='9999')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        
        # Unrelated Context
        org_c = Organization.objects.create(name='Org C')
        res = self.client.get(url, HTTP_X_ORGANIZATION_ID=str(org_c.id))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
