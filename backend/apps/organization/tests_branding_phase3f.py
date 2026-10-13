import io
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authorization.models import Permission, Role, RolePermission, ScopeChoices, UserRole
from apps.organization.models import Organization, TenantBrandingAndConfig, BrandingMode
from apps.organization.branding_service import OrganizationBrandingService

User = get_user_model()


def create_test_image(format='PNG', size=(100, 100), color=(22, 101, 52, 255)):
    """Helper to generate valid in-memory image bytes."""
    img = Image.new('RGBA', size, color=color)
    output = io.BytesIO()
    img.save(output, format=format)
    output.seek(0)
    return output.getvalue()


class OrganizationBrandingPhase3FTests(APITestCase):
    def setUp(self):
        # Organization A
        self.org_a = Organization.objects.create(name='Acme Corp', code='ACME')
        # Organization B (for cross-tenant testing)
        self.org_b = Organization.objects.create(name='Beta Inc', code='BETA')

        # Admin User for Org A
        self.admin_a = User.objects.create_user(
            email='admin@acme.com',
            password='Password123!',
            first_name='Admin',
            last_name='Acme',
            status='active',
            is_superuser=False,  # Strict multi-tenant RBAC
        )

        # Employee User for Org A (read-only)
        self.emp_a = User.objects.create_user(
            email='emp@acme.com',
            password='Password123!',
            first_name='Employee',
            last_name='Acme',
            status='active',
            is_superuser=False,
        )

        # Admin User for Org B
        self.admin_b = User.objects.create_user(
            email='admin@beta.com',
            password='Password123!',
            first_name='Admin',
            last_name='Beta',
            status='active',
            is_superuser=False,
        )

        # Setup Roles & Permissions
        self.perm_view, _ = Permission.objects.get_or_create(
            codename='organization.view',
            defaults={'name': 'View Org', 'resource': 'organization', 'action': 'view', 'is_active': True}
        )
        self.perm_manage, _ = Permission.objects.get_or_create(
            codename='branding.manage',
            defaults={'name': 'Manage Branding', 'resource': 'branding', 'action': 'manage', 'is_active': True}
        )

        # Role for Org A Admin
        self.role_admin_a = Role.objects.create(
            organization=self.org_a,
            name='Org Admin A',
            slug='org-admin-a',
        )
        RolePermission.objects.get_or_create(role=self.role_admin_a, permission=self.perm_view)
        RolePermission.objects.get_or_create(role=self.role_admin_a, permission=self.perm_manage)

        UserRole.objects.create(
            user=self.admin_a,
            role=self.role_admin_a,
            assigned_by=self.admin_a,
            scope=ScopeChoices.ORGANIZATION,
        )

        # Role for Org A Employee (view only)
        self.role_emp_a = Role.objects.create(
            organization=self.org_a,
            name='Employee A',
            slug='emp-a',
        )
        RolePermission.objects.get_or_create(role=self.role_emp_a, permission=self.perm_view)
        UserRole.objects.create(
            user=self.emp_a,
            role=self.role_emp_a,
            assigned_by=self.admin_a,
            scope=ScopeChoices.ORGANIZATION,
        )

        # Role for Org B Admin
        self.role_admin_b = Role.objects.create(
            organization=self.org_b,
            name='Org Admin B',
            slug='org-admin-b',
        )
        RolePermission.objects.get_or_create(role=self.role_admin_b, permission=self.perm_view)
        RolePermission.objects.get_or_create(role=self.role_admin_b, permission=self.perm_manage)
        UserRole.objects.create(
            user=self.admin_b,
            role=self.role_admin_b,
            assigned_by=self.admin_b,
            scope=ScopeChoices.ORGANIZATION,
        )

        self.branding_url_a = f'/api/v1/organization/organizations/{self.org_a.id}/branding/'
        self.logo_url_a = f'/api/v1/organization/organizations/{self.org_a.id}/branding/logo/'
        self.branding_url_b = f'/api/v1/organization/organizations/{self.org_b.id}/branding/'

    # -------------------------------------------------------------
    # 1. Deterministic Color Extraction & Palette Service Tests
    # -------------------------------------------------------------
    def test_color_extraction_service(self):
        """Test deterministic color extraction from image."""
        img_bytes = create_test_image(color=(22, 101, 52, 255))
        dominant = OrganizationBrandingService.extract_dominant_colors(img_bytes)
        self.assertTrue(len(dominant) >= 1)
        self.assertTrue(dominant[0].startswith('#'))

    def test_palette_generation_service(self):
        """Test generation of 3 coordinated, WCAG-tested color palettes."""
        palettes = OrganizationBrandingService.generate_coordinated_palettes('#166534')
        self.assertEqual(len(palettes), 3)
        self.assertEqual(palettes[0]['id'], 'vibrant')
        self.assertEqual(palettes[1]['id'], 'professional')
        self.assertEqual(palettes[2]['id'], 'deep')

        for pal in palettes:
            self.assertTrue(OrganizationBrandingService.validate_hex_color(pal['primary_color']))
            self.assertTrue(OrganizationBrandingService.validate_hex_color(pal['secondary_color']))
            self.assertTrue(OrganizationBrandingService.validate_hex_color(pal['accent_color']))
            self.assertTrue(OrganizationBrandingService.validate_hex_color(pal['sidebar_bg_color']))

    # -------------------------------------------------------------
    # 2. Mode A (Default Theme + Organization Logo) Tests
    # -------------------------------------------------------------
    def test_mode_a_initial_state_and_update(self):
        """Verify Mode A preserves platform defaults and permits logo management."""
        self.client.force_authenticate(user=self.admin_a)

        # GET branding
        res = self.client.get(self.branding_url_a)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['branding_mode'], 'default')

        # Update mode to default explicitly
        res_patch = self.client.patch(self.branding_url_a, {'branding_mode': 'default'}, format='json')
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch.data['branding_mode'], 'default')

    def test_mode_a_logo_upload_and_removal(self):
        """Upload and remove logo in Mode A."""
        self.client.force_authenticate(user=self.admin_a)

        img_content = create_test_image(format='PNG')
        uploaded = SimpleUploadedFile('test_logo.png', img_content, content_type='image/png')

        # Upload logo
        res_upload = self.client.post(self.logo_url_a, {'file': uploaded}, format='multipart')
        self.assertEqual(res_upload.status_code, status.HTTP_200_OK)
        self.assertTrue(res_upload.data['logo_url'].startswith('http'))
        self.assertTrue(len(res_upload.data['palette_suggestions']) >= 3)

        # Remove logo
        res_del = self.client.delete(self.logo_url_a)
        self.assertEqual(res_del.status_code, status.HTTP_200_OK)
        self.assertEqual(res_del.data['logo_url'], '')

    def test_mode_switch_preserves_uploaded_logo(self):
        """Switching between Mode A and Mode B must not delete uploaded logo."""
        self.client.force_authenticate(user=self.admin_a)

        # Upload logo
        img_content = create_test_image(format='PNG')
        uploaded = SimpleUploadedFile('test_logo.png', img_content, content_type='image/png')
        res_upload = self.client.post(self.logo_url_a, {'file': uploaded}, format='multipart')
        logo_url = res_upload.data['logo_url']

        # Switch to custom
        res_custom = self.client.patch(self.branding_url_a, {'branding_mode': 'custom'}, format='json')
        self.assertEqual(res_custom.data['branding_mode'], 'custom')
        self.assertEqual(res_custom.data['logo_url'], logo_url)

        # Switch back to default
        res_default = self.client.patch(self.branding_url_a, {'branding_mode': 'default'}, format='json')
        self.assertEqual(res_default.data['branding_mode'], 'default')
        self.assertEqual(res_default.data['logo_url'], logo_url)

    # -------------------------------------------------------------
    # 3. Mode B (Custom Theme) Tests
    # -------------------------------------------------------------
    def test_mode_b_save_palette_and_manual_overrides(self):
        """Save selected palette and manual overrides in Mode B."""
        self.client.force_authenticate(user=self.admin_a)

        payload = {
            'branding_mode': 'custom',
            'selected_palette': 'vibrant',
            'primary_color': '#166534',
            'secondary_color': '#15803D',
            'accent_color': '#4ADE80',
            'sidebar_bg_color': '#F0FDF4',
            'manual_overrides': {'primary_color': '#166534'},
        }
        res = self.client.patch(self.branding_url_a, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['branding_mode'], 'custom')
        self.assertEqual(res.data['primary_color'], '#166534')
        self.assertEqual(res.data['manual_overrides']['primary_color'], '#166534')

    def test_logo_change_does_not_silently_replace_active_theme(self):
        """When logo is changed, new palettes are attached but active custom theme is preserved."""
        self.client.force_authenticate(user=self.admin_a)

        # Set custom colors
        self.client.patch(self.branding_url_a, {
            'branding_mode': 'custom',
            'primary_color': '#7C2D12',
            'secondary_color': '#9A3412',
        }, format='json')

        # Upload a green logo
        img_content = create_test_image(format='PNG', color=(22, 101, 52, 255))
        uploaded = SimpleUploadedFile('green_logo.png', img_content, content_type='image/png')
        res_upload = self.client.post(self.logo_url_a, {'file': uploaded}, format='multipart')

        self.assertEqual(res_upload.status_code, status.HTTP_200_OK)
        # Active primary color MUST still be #7C2D12 (not silently replaced!)
        self.assertEqual(res_upload.data['primary_color'], '#7C2D12')
        # Palette suggestions updated
        self.assertTrue(len(res_upload.data['palette_suggestions']) >= 3)

    # -------------------------------------------------------------
    # 4. Validation Tests
    # -------------------------------------------------------------
    def test_invalid_hex_color_validation(self):
        """Invalid hex colors must be rejected."""
        self.client.force_authenticate(user=self.admin_a)

        res = self.client.patch(self.branding_url_a, {'primary_color': 'invalid-hex'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('primary_color', res.data)

    def test_invalid_logo_file_type(self):
        """Non-image files must be rejected."""
        self.client.force_authenticate(user=self.admin_a)

        bad_file = SimpleUploadedFile('test.txt', b'hello text file', content_type='text/plain')
        res = self.client.post(self.logo_url_a, {'file': bad_file}, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_oversized_logo_file(self):
        """File larger than 2MB must be rejected."""
        self.client.force_authenticate(user=self.admin_a)

        large_bytes = b'0' * (2 * 1024 * 1024 + 10)
        large_file = SimpleUploadedFile('large.png', large_bytes, content_type='image/png')
        res = self.client.post(self.logo_url_a, {'file': large_file}, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------
    # 5. Dynamic RBAC & Cross-Tenant Isolation Tests
    # -------------------------------------------------------------
    def test_unauthorized_user_cannot_modify_branding(self):
        """User without branding.manage cannot patch or upload logo."""
        self.client.force_authenticate(user=self.emp_a)

        res_patch = self.client.patch(self.branding_url_a, {'primary_color': '#112233'}, format='json')
        self.assertEqual(res_patch.status_code, status.HTTP_403_FORBIDDEN)

        img_content = create_test_image()
        uploaded = SimpleUploadedFile('logo.png', img_content, content_type='image/png')
        res_upload = self.client.post(self.logo_url_a, {'file': uploaded}, format='multipart')
        self.assertEqual(res_upload.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_tenant_isolation(self):
        """Admin of Org A cannot access or modify Org B's branding."""
        self.client.force_authenticate(user=self.admin_a)

        # Attempt to read Org B
        res_get = self.client.get(self.branding_url_b)
        self.assertIn(res_get.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

        # Attempt to update Org B
        res_patch = self.client.patch(self.branding_url_b, {'primary_color': '#990000'}, format='json')
        self.assertIn(res_patch.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])
