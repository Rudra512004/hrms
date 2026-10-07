from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.organization.models import Organization, TenantBrandingAndConfig

User = get_user_model()

class TenantBrandingTests(APITestCase):
    def setUp(self):
        self.superadmin = User.objects.create_superuser(
            password='password123', email='super@test.com', status='active'
        )
        # Create an org; signal should auto-provision branding
        self.organization = Organization.objects.create(name='Acme Corp')
        
        # Super Admins are "headless", their context comes from a role
        from apps.authorization.models import Role, UserRole, ScopeChoices
        owner_role = Role.objects.create(
            organization=self.organization,
            name='Organization Owner'
        )
        UserRole.objects.create(
            user=self.superadmin,
            role=owner_role,
            assigned_by=self.superadmin,
            scope=ScopeChoices.ORGANIZATION,
        )
        from apps.authorization.models import Permission, RolePermission
        for codename in ['organization.view', 'branding.manage']:
            res, act = codename.split('.')
            perm, _ = Permission.objects.get_or_create(codename=codename, defaults={'name': codename, 'resource': res, 'action': act, 'is_active': True})
            RolePermission.objects.get_or_create(role=owner_role, permission=perm)
        
        self.branding_url = f'/api/v1/organization/organizations/{self.organization.id}/branding/'

    def test_signal_auto_provisions_branding(self):
        """Test that a new Organization gets an empty branding config via post_save signal."""
        from decimal import Decimal
        self.assertTrue(TenantBrandingAndConfig.objects.filter(organization=self.organization).exists())
        config = self.organization.branding
        self.assertEqual(str(config.watermark_opacity), '0.08')
        self.assertEqual(config.default_theme_mode, 'light')

    def test_get_branding(self):
        """Test retrieving branding configuration."""
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.get(self.branding_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('logo_url', response.data)
        self.assertIn('custom_fields_schema', response.data)
        self.assertEqual(response.data['default_theme_mode'], 'light')

    def test_superadmin_can_update_their_own_org_branding(self):
        """Test partial update of branding configuration."""
        self.client.force_authenticate(user=self.superadmin)
        payload = {
            'primary_color': '#FF0000',
            'default_theme_mode': 'dark',
            'custom_fields_schema': [
                {'key': 'blood_group', 'label': 'Blood Group', 'type': 'select', 'module': 'employee'}
            ]
        }
        response = self.client.patch(self.branding_url, data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['primary_color'], '#FF0000')
        self.assertEqual(response.data['default_theme_mode'], 'dark')
        
        # Verify DB updated
        self.organization.branding.refresh_from_db()
        self.assertEqual(self.organization.branding.primary_color, '#FF0000')
        self.assertEqual(len(self.organization.branding.custom_fields_schema), 1)

    def test_superadmin_cannot_update_other_org_branding(self):
        """Test that Super Admin A cannot modify Organization B branding."""
        org_b = Organization.objects.create(name='Org B')
        branding_url_b = f'/api/v1/organization/organizations/{org_b.id}/branding/'
        
        self.client.force_authenticate(user=self.superadmin)
        # Even though they are is_superuser, they don't belong to org_b, so they should get 403 or 404
        response = self.client.patch(branding_url_b, data={'primary_color': '#999999'}, format='json')
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_invalid_custom_fields_schema(self):
        """Test validation blocks invalid custom fields schema."""
        self.client.force_authenticate(user=self.superadmin)
        # Missing 'module' key
        payload = {
            'custom_fields_schema': [
                {'key': 'blood_group', 'label': 'Blood Group', 'type': 'select'}
            ]
        }
        response = self.client.patch(self.branding_url, data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('custom_fields_schema', response.data)

    def test_tenant_admin_cannot_update_branding(self):
        """Test that non-Super Admin (even Tenant Admin) receives 403 when trying to update branding."""
        from apps.employees.models import Employee
        from apps.authorization.models import Role, UserRole, Permission, UserPermissionGrant
        
        tenant_admin = User.objects.create_user(password='pass', email='admin@acme.com', first_name='A', last_name='B', status='active')
        Employee.objects.create(user=tenant_admin, organization=self.organization)
        
        # Grant them organization.manage explicitly, just in case they would otherwise fail earlier
        perm, _ = Permission.objects.get_or_create(codename='organization.manage', defaults={'name': 'Manage Org', 'resource': 'organization', 'action': 'manage'})
        UserPermissionGrant.objects.create(user=tenant_admin, permission=perm, scope='organization')
        
        self.client.force_authenticate(user=tenant_admin)
        response = self.client.patch(self.branding_url, data={'primary_color': '#000000'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
    def test_employee_can_read_branding(self):
        """Test that regular employees can read branding for their organization."""
        from apps.employees.models import Employee
        from apps.authorization.models import Permission, UserPermissionGrant
        employee = User.objects.create_user(password='pass', email='emp@acme.com', first_name='E', last_name='M', status='active')
        Employee.objects.create(user=employee, organization=self.organization)
        
        # Grant organization.view
        perm, _ = Permission.objects.get_or_create(codename='organization.view', defaults={'name': 'View Org', 'resource': 'organization', 'action': 'view'})
        UserPermissionGrant.objects.create(user=employee, permission=perm, scope='organization')
        
        self.client.force_authenticate(user=employee)
        response = self.client.get(self.branding_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Ensure employee cannot patch
        response_patch = self.client.patch(self.branding_url, data={'primary_color': '#000000'}, format='json')
        self.assertEqual(response_patch.status_code, status.HTTP_403_FORBIDDEN)
