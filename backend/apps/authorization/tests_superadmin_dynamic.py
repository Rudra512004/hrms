from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework.test import APIClient
from rest_framework import status

from apps.organization.models import Organization, Branch, Department, Team
from apps.authorization.models import Permission, Role, UserRole, RolePermission, ScopeChoices
from apps.authorization.services import AuthorizationService
import importlib
migration_0006 = importlib.import_module('apps.authorization.migrations.0006_canonical_permissions_and_roles_backfill')
seed_canonical_permissions_and_backfill_roles = migration_0006.seed_canonical_permissions_and_backfill_roles
CANONICAL_PERMISSIONS = migration_0006.CANONICAL_PERMISSIONS

User = get_user_model()


class DynamicSuperAdminRBACComprehensiveTests(TestCase):
    """
    Focused automated test suite validating dynamic Super Admin permission resolution,
    system-role immutability, tenant isolation, and canonical registry stability.
    Covers Scenarios A through M as specified in Phase 2C.
    """

    def setUp(self):
        self.client = APIClient()

        # Create two tenant organizations for isolation testing
        self.org1 = Organization.objects.create(name='Acme Corp', status='active')
        self.org2 = Organization.objects.create(name='Globex Corp', status='active')

        # Create branches and teams in both organizations
        self.branch1 = Branch.objects.create(organization=self.org1, name='Acme HQ', is_active=True)
        self.dept1 = Department.objects.create(branch=self.branch1, name='Engineering')
        self.team1 = Team.objects.create(department=self.dept1, name='Backend', is_active=True)

        self.branch2 = Branch.objects.create(organization=self.org2, name='Globex HQ', is_active=True)
        self.dept2 = Department.objects.create(branch=self.branch2, name='Operations')
        self.team2 = Team.objects.create(department=self.dept2, name='DevOps', is_active=True)

        # Baseline canonical permissions (already populated by migration 0006 in test DB)
        self.perm_view, _ = Permission.objects.get_or_create(
            codename='employee.view',
            defaults={
                'name': 'View Employees', 'resource': 'employee', 'action': 'view',
                'category': 'Employees', 'ui_label': 'View employees', 'column_index': 1, 'display_order': 20, 'is_active': True
            }
        )
        self.perm_create, _ = Permission.objects.get_or_create(
            codename='employee.create',
            defaults={
                'name': 'Create Employees', 'resource': 'employee', 'action': 'create',
                'category': 'Employees', 'ui_label': 'Create employees', 'column_index': 1, 'display_order': 22, 'is_active': True
            }
        )
        self.perm_role_manage, _ = Permission.objects.get_or_create(
            codename='role.manage',
            defaults={
                'name': 'Manage Roles', 'resource': 'role', 'action': 'manage',
                'category': 'Administration', 'ui_label': 'Manage roles', 'column_index': 3, 'display_order': 120, 'is_active': True
            }
        )
        self.perm_role_assign, _ = Permission.objects.get_or_create(
            codename='role.assign',
            defaults={
                'name': 'Assign Roles', 'resource': 'role', 'action': 'assign',
                'category': 'Administration', 'ui_label': 'Assign roles', 'column_index': 3, 'display_order': 119, 'is_active': True
            }
        )
        self.perm_permission_assign, _ = Permission.objects.get_or_create(
            codename='permission.assign',
            defaults={
                'name': 'Assign Permissions', 'resource': 'permission', 'action': 'assign',
                'category': 'Administration', 'ui_label': 'Assign permissions', 'column_index': 3, 'display_order': 118, 'is_active': True
            }
        )

        # Create Super Admin role in Org 1
        self.superadmin_role1 = Role.objects.create(
            organization=self.org1,
            name='Organization Owner (Super Admin)',
            slug='super-admin',
            is_system=True,
            is_active=True,
        )

        # Create Super Admin user in Org 1
        self.superadmin_user1 = User.objects.create_user(
            email='superadmin@acme.local',
            password='Password123!',
            status='active'
        )
        self.superadmin_ur1 = UserRole.objects.create(
            user=self.superadmin_user1,
            role=self.superadmin_role1,
            scope=ScopeChoices.ORGANIZATION,
            is_revoked=False
        )

        # Create Standard HR role and user in Org 1
        self.hr_role1 = Role.objects.create(
            organization=self.org1,
            name='HR Manager',
            slug='hr-manager',
            is_system=True,
            is_active=True,
        )
        RolePermission.objects.create(role=self.hr_role1, permission=self.perm_view)

        self.hr_user1 = User.objects.create_user(
            email='hr@acme.local',
            password='Password123!',
            status='active'
        )
        self.hr_ur1 = UserRole.objects.create(
            user=self.hr_user1,
            role=self.hr_role1,
            scope=ScopeChoices.ORGANIZATION,
            is_revoked=False
        )

    # -------------------------------------------------------------------------
    # A. Organization-scoped Super Admin resolution
    # -------------------------------------------------------------------------
    def test_scenario_a_superadmin_dynamic_resolution(self):
        """User with active super-admin role receives all active permissions in Org 1."""
        perms = AuthorizationService.get_effective_permissions(self.superadmin_user1)
        self.assertIn('employee.view', perms)
        self.assertIn('employee.create', perms)
        self.assertIn('role.manage', perms)
        self.assertTrue(AuthorizationService.has_permission(self.superadmin_user1, 'employee.view'))
        self.assertTrue(AuthorizationService.has_permission(self.superadmin_user1, 'employee.create'))

    # -------------------------------------------------------------------------
    # B. Newly added active permission inheritance
    # -------------------------------------------------------------------------
    def test_scenario_b_new_active_permission_dynamic_inheritance(self):
        """Newly created active permissions reflect dynamically without RolePermission rows."""
        new_perm = Permission.objects.create(
            codename='finance.audit_export',
            name='Export Audit Log',
            resource='finance',
            action='audit_export',
            is_active=True
        )
        # Super Admin has not been statically linked to new_perm in DB
        self.assertFalse(RolePermission.objects.filter(role=self.superadmin_role1, permission=new_perm).exists())

        # Effective permissions query dynamically includes it
        perms = AuthorizationService.get_effective_permissions(self.superadmin_user1)
        self.assertIn('finance.audit_export', perms)
        self.assertTrue(AuthorizationService.has_permission(self.superadmin_user1, 'finance.audit_export'))

    # -------------------------------------------------------------------------
    # C. Inactive permissions are excluded
    # -------------------------------------------------------------------------
    def test_scenario_c_inactive_permissions_excluded(self):
        """Permissions with is_active=False are never granted to Super Admin."""
        inactive_perm = Permission.objects.create(
            codename='legacy.deprecate_feature',
            name='Deprecated Feature',
            resource='legacy',
            action='deprecate_feature',
            is_active=False
        )
        perms = AuthorizationService.get_effective_permissions(self.superadmin_user1)
        self.assertNotIn('legacy.deprecate_feature', perms)
        self.assertFalse(AuthorizationService.has_permission(self.superadmin_user1, 'legacy.deprecate_feature'))

    # -------------------------------------------------------------------------
    # D. Deactivating a permission removes its effective capability
    # -------------------------------------------------------------------------
    def test_scenario_d_deactivating_permission_removes_capability(self):
        """Marking an active permission inactive immediately removes it from runtime permissions."""
        self.assertTrue(AuthorizationService.has_permission(self.superadmin_user1, 'employee.create'))

        # Deactivate
        self.perm_create.is_active = False
        self.perm_create.save()

        # Immediate recalculation
        perms = AuthorizationService.get_effective_permissions(self.superadmin_user1)
        self.assertNotIn('employee.create', perms)
        self.assertFalse(AuthorizationService.has_permission(self.superadmin_user1, 'employee.create'))

    # -------------------------------------------------------------------------
    # E. Super Admin role revocation removes the dynamic grant
    # -------------------------------------------------------------------------
    def test_scenario_e_role_revocation_removes_dynamic_grant(self):
        """Revoking user role removes all dynamic capabilities immediately."""
        self.assertTrue(AuthorizationService.has_permission(self.superadmin_user1, 'employee.view'))

        # Revoke user role
        self.superadmin_ur1.is_revoked = True
        self.superadmin_ur1.save()

        perms = AuthorizationService.get_effective_permissions(self.superadmin_user1)
        self.assertEqual(perms, set())
        self.assertFalse(AuthorizationService.has_permission(self.superadmin_user1, 'employee.view'))

    # -------------------------------------------------------------------------
    # F. A user without a valid tenant role does not gain Super Admin access
    # -------------------------------------------------------------------------
    def test_scenario_f_superuser_without_tenant_role_denied(self):
        """User with is_superuser=True but no tenant UserRole receives empty permissions."""
        headless_admin = User.objects.create_user(
            email='headless@platform.local',
            password='Password123!',
            is_superuser=True,
            status='active'
        )
        perms = AuthorizationService.get_effective_permissions(headless_admin)
        self.assertEqual(perms, set())
        self.assertFalse(AuthorizationService.has_permission(headless_admin, 'employee.view'))

    # -------------------------------------------------------------------------
    # G. Cross-tenant objects remain inaccessible
    # -------------------------------------------------------------------------
    def test_scenario_g_cross_tenant_objects_inaccessible(self):
        """Super Admin from Org 1 receives empty permissions and no access for Org 2 resources."""
        # Querying permissions within Org 2 branch context returns empty set
        perms_branch2 = AuthorizationService.get_effective_permissions(
            self.superadmin_user1,
            branch_id=self.branch2.id
        )
        self.assertEqual(perms_branch2, set())

        # Querying permissions within Org 2 team context returns empty set
        perms_team2 = AuthorizationService.get_effective_permissions(
            self.superadmin_user1,
            team_id=self.team2.id
        )
        self.assertEqual(perms_team2, set())

        # Authorized branches for Org 1 Super Admin only return Org 1 branches
        auth_branches = AuthorizationService.get_authorized_branches(self.superadmin_user1, 'employee.view')
        self.assertIn(self.branch1, auth_branches)
        self.assertNotIn(self.branch2, auth_branches)

        # Authorized teams for Org 1 Super Admin only return Org 1 teams
        auth_teams = AuthorizationService.get_authorized_teams(self.superadmin_user1, 'employee.view')
        self.assertIn(self.team1, auth_teams)
        self.assertNotIn(self.team2, auth_teams)

        # API isolation: Org 1 Super Admin requesting Org 2 branch detail receives 404
        self.client.force_authenticate(user=self.superadmin_user1)
        resp = self.client.get(f'/api/v1/organization/branches/{self.branch2.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # -------------------------------------------------------------------------
    # H. System roles cannot be narrowed or deleted through existing APIs
    # -------------------------------------------------------------------------
    def test_scenario_h_system_role_immutability_and_deletion_protection(self):
        """Attempting to delete or narrow Super Admin role permissions via API returns 400 Bad Request."""
        self.client.force_authenticate(user=self.superadmin_user1)

        # 1. Attempting DELETE on system role
        delete_resp = self.client.delete(f'/api/v1/authorization/roles/{self.superadmin_role1.id}/')
        self.assertEqual(delete_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('System roles cannot be deleted', delete_resp.data.get('detail', ''))
        self.assertTrue(Role.objects.filter(id=self.superadmin_role1.id).exists())

        # 2. Attempting PUT on Super Admin permissions
        narrow_resp = self.client.put(
            f'/api/v1/authorization/roles/{self.superadmin_role1.id}/permissions/',
            {'permission_ids': [self.perm_view.id]},
            format='json'
        )
        self.assertEqual(narrow_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cannot be narrowed', narrow_resp.data.get('detail', ''))

        # 3. Attempting POST to manually create RolePermission on Super Admin role
        post_rp_resp = self.client.post(
            '/api/v1/authorization/role-permissions/',
            {'role': self.superadmin_role1.id, 'permission': self.perm_view.id},
            format='json'
        )
        self.assertEqual(post_rp_resp.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------------------
    # I. Existing non-Super Admin role permissions remain unchanged
    # -------------------------------------------------------------------------
    def test_scenario_i_non_superadmin_role_evaluation_preserved(self):
        """HR Manager only receives explicitly granted permissions, not dynamic superadmin set."""
        hr_perms = AuthorizationService.get_effective_permissions(self.hr_user1)
        self.assertIn('employee.view', hr_perms)
        self.assertNotIn('employee.create', hr_perms)
        self.assertNotIn('role.manage', hr_perms)
        self.assertTrue(AuthorizationService.has_permission(self.hr_user1, 'employee.view'))
        self.assertFalse(AuthorizationService.has_permission(self.hr_user1, 'employee.create'))

    # -------------------------------------------------------------------------
    # J. Repeated registry seeding does not create duplicate permissions
    # -------------------------------------------------------------------------
    def test_scenario_j_idempotent_seeding_prevents_duplicates(self):
        """Running the seeding logic repeatedly does not duplicate permissions."""
        class MockApps:
            @staticmethod
            def get_model(app_label, model_name):
                if model_name == 'Permission':
                    return Permission
                if model_name == 'Role':
                    return Role
                raise ValueError(f"Unknown model {model_name}")

        count_before = Permission.objects.count()
        seed_canonical_permissions_and_backfill_roles(MockApps(), None)
        count_after = Permission.objects.count()

        # Idempotent: no duplicate records
        self.assertEqual(count_before, count_after)
        self.assertEqual(Permission.objects.filter(codename='employee.view').count(), 1)

    # -------------------------------------------------------------------------
    # K. Existing role-permission assignments remain intact
    # -------------------------------------------------------------------------
    def test_scenario_k_existing_assignments_remain_intact(self):
        """Seeding does not erase or disturb existing role-permission relationships."""
        self.assertTrue(
            RolePermission.objects.filter(role=self.hr_role1, permission=self.perm_view).exists()
        )
        # Re-run seeding
        class MockApps:
            @staticmethod
            def get_model(app_label, model_name):
                return Permission if model_name == 'Permission' else Role

        seed_canonical_permissions_and_backfill_roles(MockApps(), None)

        self.assertTrue(
            RolePermission.objects.filter(role=self.hr_role1, permission=self.perm_view).exists()
        )

    # -------------------------------------------------------------------------
    # L. Organization-scoped role slug uniqueness
    # -------------------------------------------------------------------------
    def test_scenario_l_organization_scoped_slug_uniqueness(self):
        """Role slugs are unique within an organization, but can duplicate across different organizations."""
        # In Org 1: creating another role with slug 'hr-manager' must raise IntegrityError
        from django.db import transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Role.objects.create(
                    organization=self.org1,
                    name='Second HR Role',
                    slug='hr-manager',
                    is_system=False
                )

        # In Org 2: creating a role with slug 'hr-manager' succeeds cleanly
        role_org2 = Role.objects.create(
            organization=self.org2,
            name='HR Manager',
            slug='hr-manager',
            is_system=True
        )
        self.assertEqual(role_org2.slug, 'hr-manager')
        self.assertEqual(role_org2.organization, self.org2)

    # -------------------------------------------------------------------------
    # M. Legacy and test-artifact handling does not break fixtures
    # -------------------------------------------------------------------------
    def test_scenario_m_test_artifacts_quarantined_without_breaking_relations(self):
        """Test artifacts are marked is_active=False and excluded from effective permissions without FK deletion."""
        test_perm, _ = Permission.objects.get_or_create(
            codename='test.perm',
            defaults={
                'name': 'Test Perm Artifact',
                'resource': 'test',
                'action': 'perm',
                'is_active': False  # Quarantined
            }
        )
        test_perm.is_active = False
        test_perm.save()
        # Existing role assigned to test artifact
        RolePermission.objects.get_or_create(role=self.hr_role1, permission=test_perm)

        # Foreign key relationship is intact
        self.assertTrue(
            RolePermission.objects.filter(role=self.hr_role1, permission=test_perm).exists()
        )

        # But HR user does not receive the inactive permission
        hr_perms = AuthorizationService.get_effective_permissions(self.hr_user1)
        self.assertNotIn('test.perm', hr_perms)

        # Super Admin also does not receive the inactive permission
        sa_perms = AuthorizationService.get_effective_permissions(self.superadmin_user1)
        self.assertNotIn('test.perm', sa_perms)


class MigrationForwardBackwardVerificationTests(TestCase):
    """
    Validates migration forward, backward, and fresh database initialization
    for migrations 0005, 0006, and 0007.
    """

    def test_migration_forward_and_backward_lifecycle(self):
        from django.core.management import call_command
        from apps.authorization.models import Permission, Role

        # 1. Reverse migrate to 0005 (reverses 0007 constraint and 0006 data migration)
        call_command('migrate', 'authorization', '0005', verbosity=0)

        # Verify test artifacts restored to is_active=True after reversing 0006
        for code in ['test.p', 'test.perm', 'test.perm.manage']:
            p = Permission.objects.filter(codename=code).first()
            if p:
                self.assertTrue(p.is_active, f"Expected {code} to be is_active=True on rollback")

        # 2. Reverse migrate to 0004 (reverses 0005 metadata & role fields)
        call_command('migrate', 'authorization', '0004', verbosity=0)

        # 3. Migrate forward to 0005 (applies schema fields)
        call_command('migrate', 'authorization', '0005', verbosity=0)

        # 4. Migrate forward to 0006 (seeds 144 canonical permissions, quarantines test artifacts)
        call_command('migrate', 'authorization', '0006', verbosity=0)

        # 5. Migrate forward to 0007 (applies unique constraint on role slug)
        call_command('migrate', 'authorization', '0007', verbosity=0)

        # Verify post-forward migration counts and properties
        canonical_ui_codes = [p['codename'] for p in CANONICAL_PERMISSIONS if not p.get('is_preserved_enterprise')]
        canonical_preserved_codes = [p['codename'] for p in CANONICAL_PERMISSIONS if p.get('is_preserved_enterprise')]

        ui_visible_count = Permission.objects.filter(codename__in=canonical_ui_codes).count()
        self.assertEqual(ui_visible_count, 127)

        preserved_count = Permission.objects.filter(codename__in=canonical_preserved_codes).count()
        self.assertEqual(preserved_count, 17)

        # Verify 9 missing permissions are present and active
        missing_9 = [
            'payroll.fnf_view', 'payroll.fnf_prepare', 'payroll.fnf_approve', 'payroll.fnf_finalize',
            'payroll.disburse', 'payroll.disburse_prepare', 'payroll.disburse_approve',
            'payroll.disburse_export', 'payroll.disburse_configure'
        ]
        for code in missing_9:
            perm = Permission.objects.filter(codename=code).first()
            self.assertIsNotNone(perm, f"Missing permission {code} not found")
            self.assertTrue(perm.is_active, f"Expected {code} to be active")

        # Verify quarantined test artifacts
        for code in ['test.p', 'test.perm', 'test.perm.manage']:
            perm = Permission.objects.filter(codename=code).first()
            if perm:
                self.assertFalse(perm.is_active, f"Expected {code} to be quarantined (is_active=False)")

