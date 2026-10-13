from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone

from apps.organization.models import Organization, Branch, Department, Team
from apps.employees.models import Employee, EmploymentStatus
from apps.authorization.models import Permission, Role, UserRole, RolePermission, ScopeChoices
from apps.authorization.services import AuthorizationService
from apps.audit.models import AuditLog

User = get_user_model()


class RBACAPIContractsComprehensiveTests(TestCase):
    """
    Comprehensive test suite validating Phase 2D Backend RBAC API Contracts and Enforcement:
    1. Role listing and role detail organization isolation & explicit counts.
    2. Permission listing, grouping (127 controls across 3 columns), ordering & inactive handling.
    3. Role creation, slug generation, system role protection.
    4. Role editing, system role immutability, slug tampering rejection.
    5. Role deletion, system role blocking, assigned user blocking, clean deletion.
    6. Role-permission assignment, atomic full replacement, unknown/inactive ID rejection, enterprise protection.
    7. User-role assignment, anti-privilege escalation, duplicate prevention.
    8. User-role revocation (POST /revoke/ and DELETE /) and audit logging.
    9. Dynamic permissions live reflection.
    """

    def setUp(self):
        self.client = APIClient()

        # Create two tenant organizations for strict isolation testing
        self.org1 = Organization.objects.create(name='Acme Corp', status='active')
        self.org2 = Organization.objects.create(name='Globex Corp', status='active')

        self.branch1 = Branch.objects.create(organization=self.org1, name='Acme HQ', is_active=True)
        self.dept1 = Department.objects.create(branch=self.branch1, name='Engineering')
        self.team1 = Team.objects.create(department=self.dept1, name='Backend', is_active=True)

        self.branch2 = Branch.objects.create(organization=self.org2, name='Globex HQ', is_active=True)
        self.dept2 = Department.objects.create(branch=self.branch2, name='Operations')
        self.team2 = Team.objects.create(department=self.dept2, name='DevOps', is_active=True)

        # Baseline Permissions
        # Baseline Permissions from canonical migration 0006
        self.perm_role_view = Permission.objects.get(codename='role.view')
        self.perm_role_manage = Permission.objects.get(codename='role.manage')
        self.perm_emp_view = Permission.objects.get(codename='employee.view')
        self.perm_emp_create = Permission.objects.get(codename='employee.create')

        self.perm_role_assign, _ = Permission.objects.get_or_create(
            codename='role.assign',
            defaults={
                'name': 'Assign Roles', 'resource': 'role', 'action': 'assign',
                'category': 'Administration', 'ui_label': 'Assign roles',
                'column_index': None, 'display_order': 0, 'is_active': True,
                'is_preserved_enterprise': True
            }
        )
        self.perm_role_revoke, _ = Permission.objects.get_or_create(
            codename='role.revoke',
            defaults={
                'name': 'Revoke Roles', 'resource': 'role', 'action': 'revoke',
                'category': 'Administration', 'ui_label': 'Revoke roles',
                'column_index': None, 'display_order': 0, 'is_active': True,
                'is_preserved_enterprise': True
            }
        )
        self.perm_perm_view, _ = Permission.objects.get_or_create(
            codename='permission.view',
            defaults={
                'name': 'View Permissions', 'resource': 'permission', 'action': 'view',
                'category': 'Administration', 'ui_label': 'View permissions',
                'column_index': None, 'display_order': 0, 'is_active': True,
                'is_preserved_enterprise': True
            }
        )
        self.perm_enterprise, _ = Permission.objects.get_or_create(
            codename='audit.compliance_export',
            defaults={
                'name': 'Export Statutory Compliance Logs', 'resource': 'audit', 'action': 'compliance_export',
                'category': 'Audit', 'ui_label': 'Export Compliance Logs',
                'column_index': None, 'display_order': 0, 'is_active': True,
                'is_preserved_enterprise': True
            }
        )
        self.perm_inactive, _ = Permission.objects.get_or_create(
            codename='test.quarantined_perm',
            defaults={
                'name': 'Quarantined Test Permission', 'resource': 'test', 'action': 'quarantined',
                'category': 'Testing', 'ui_label': 'Quarantined',
                'column_index': None, 'display_order': 99, 'is_active': False,
                'is_preserved_enterprise': False
            }
        )

        # 1. Super Admin in Org 1
        self.superadmin_role1 = Role.objects.create(
            organization=self.org1,
            name='Organization Owner (Super Admin)',
            slug='super-admin',
            is_system=True,
            is_active=True,
        )
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

        # 2. Standard Admin / HR in Org 1 (has role.view, role.manage, role.assign, role.revoke)
        self.hr_role1 = Role.objects.create(
            organization=self.org1,
            name='HR Manager',
            slug='hr-manager',
            is_system=True,
            is_active=True,
        )
        RolePermission.objects.create(role=self.hr_role1, permission=self.perm_role_view)
        RolePermission.objects.create(role=self.hr_role1, permission=self.perm_role_manage)
        RolePermission.objects.create(role=self.hr_role1, permission=self.perm_role_assign)
        RolePermission.objects.create(role=self.hr_role1, permission=self.perm_role_revoke)
        RolePermission.objects.create(role=self.hr_role1, permission=self.perm_perm_view)
        RolePermission.objects.create(role=self.hr_role1, permission=self.perm_emp_view)

        self.hr_user1 = User.objects.create_user(
            email='hr@acme.local',
            password='Password123!',
            status='active'
        )
        self.emp_hr1 = Employee.objects.create(
            user=self.hr_user1,
            organization=self.org1,
            employee_code='EMP-ACME-001',
            employment_status=EmploymentStatus.ACTIVE
        )
        self.hr_ur1 = UserRole.objects.create(
            user=self.hr_user1,
            role=self.hr_role1,
            scope=ScopeChoices.ORGANIZATION,
            is_revoked=False
        )

        # 3. Regular Employee in Org 1
        self.emp_user1 = User.objects.create_user(
            email='employee@acme.local',
            password='Password123!',
            status='active'
        )
        self.employee1 = Employee.objects.create(
            user=self.emp_user1,
            organization=self.org1,
            employee_code='EMP-ACME-002',
            employment_status=EmploymentStatus.ACTIVE
        )

        # 4. Super Admin and Role in Org 2
        self.superadmin_role2 = Role.objects.create(
            organization=self.org2,
            name='Organization Owner (Super Admin)',
            slug='super-admin',
            is_system=True,
            is_active=True,
        )
        self.superadmin_user2 = User.objects.create_user(
            email='superadmin@globex.local',
            password='Password123!',
            status='active'
        )
        self.superadmin_ur2 = UserRole.objects.create(
            user=self.superadmin_user2,
            role=self.superadmin_role2,
            scope=ScopeChoices.ORGANIZATION,
            is_revoked=False
        )

    # =========================================================================
    # A. ROLE LISTING AND DETAIL
    # =========================================================================

    def test_role_listing_and_detail_organization_isolation(self):
        """Roles list is strictly filtered to caller's tenant org; cross-tenant detail returns 404."""
        self.client.force_authenticate(user=self.hr_user1)
        response = self.client.get('/api/v1/authorization/roles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Org 1 roles must be present, Org 2 role must NOT be present
        role_ids = [r['id'] for r in response.data]
        self.assertIn(self.superadmin_role1.id, role_ids)
        self.assertIn(self.hr_role1.id, role_ids)
        self.assertNotIn(self.superadmin_role2.id, role_ids)

        # Detail for Org 1 role: 200 OK
        detail_resp = self.client.get(f'/api/v1/authorization/roles/{self.superadmin_role1.id}/')
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)

        # Detail for Org 2 role: 404 Not Found
        cross_resp = self.client.get(f'/api/v1/authorization/roles/{self.superadmin_role2.id}/')
        self.assertEqual(cross_resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_role_detail_contract_fields_and_counts(self):
        """Super Admin role and custom roles expose required contract fields with explicit count definitions."""
        self.client.force_authenticate(user=self.superadmin_user1)
        
        # Super Admin detail
        sa_resp = self.client.get(f'/api/v1/authorization/roles/{self.superadmin_role1.id}/')
        self.assertEqual(sa_resp.status_code, status.HTTP_200_OK)
        sa_data = sa_resp.data
        self.assertEqual(sa_data['slug'], 'super-admin')
        self.assertEqual(sa_data['badge'], 'Full access')
        self.assertEqual(sa_data['users_count'], 1)
        self.assertEqual(sa_data['permissions_count'], 127)  # UI-visible controls
        self.assertEqual(sa_data['can_delete'], False)
        self.assertTrue(sa_data['effective_permissions_count'] >= 144)
        self.assertEqual(len(sa_data['permission_ids']), 127)

        # HR Manager detail
        hr_resp = self.client.get(f'/api/v1/authorization/roles/{self.hr_role1.id}/')
        self.assertEqual(hr_resp.status_code, status.HTTP_200_OK)
        hr_data = hr_resp.data
        self.assertIsNone(hr_data['badge'])
        self.assertEqual(hr_data['users_count'], 1)
        self.assertEqual(hr_data['permissions_count'], 3)
        self.assertEqual(hr_data['effective_permissions_count'], 6)
        self.assertEqual(hr_data['can_delete'], False)  # is_system=True

    # =========================================================================
    # B. PERMISSION LISTING
    # =========================================================================

    def test_permission_listing_grouped_matrix_127_controls(self):
        """GET /permissions/ returns grouped matrix with exactly 127 UI controls across columns 1, 2, 3."""
        self.client.force_authenticate(user=self.hr_user1)
        response = self.client.get('/api/v1/authorization/permissions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertIn('total_visible_count', data)
        self.assertEqual(data['total_visible_count'], 127)
        self.assertIn('columns', data)
        self.assertIn('1', data['columns'])
        self.assertIn('2', data['columns'])
        self.assertIn('3', data['columns'])

        # Verify inactive permission is NOT included
        inactive_codenames = []
        for col in data['columns'].values():
            for cat in col:
                for action in cat['actions']:
                    if action['codename'] == self.perm_inactive.codename:
                        inactive_codenames.append(action['codename'])
        self.assertEqual(len(inactive_codenames), 0)

        # Verify preserved enterprise permissions are NOT in default matrix
        enterprise_codenames = []
        for col in data['columns'].values():
            for cat in col:
                for action in cat['actions']:
                    if action['codename'] == self.perm_enterprise.codename:
                        enterprise_codenames.append(action['codename'])
        self.assertEqual(len(enterprise_codenames), 0)

    def test_permission_listing_flat_format_and_include_preserved(self):
        """GET /permissions/?format=flat and ?include_preserved=true honor parameters."""
        self.client.force_authenticate(user=self.hr_user1)

        # Flat format
        flat_resp = self.client.get('/api/v1/authorization/permissions/?format=flat')
        self.assertEqual(flat_resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(flat_resp.data, list)
        self.assertEqual(len(flat_resp.data), 127)

        # With preserved enterprise
        preserved_resp = self.client.get('/api/v1/authorization/permissions/?include_preserved=true')
        self.assertEqual(preserved_resp.status_code, status.HTTP_200_OK)
        self.assertIn('preserved_enterprise', preserved_resp.data)
        enterprise_items = [p['codename'] for p in preserved_resp.data['preserved_enterprise']]
        self.assertIn(self.perm_enterprise.codename, enterprise_items)

    # =========================================================================
    # C. ROLE CREATION
    # =========================================================================

    def test_role_creation_valid_custom_role_and_audit(self):
        """Creating a custom role sets is_system=False, generates org-scoped slug, and logs audit."""
        self.client.force_authenticate(user=self.hr_user1)
        initial_audit_count = AuditLog.objects.filter(action='role_created').count()

        payload = {
            'name': 'Shift Supervisor',
            'description': 'Supervises branch floor shifts'
        }
        response = self.client.post('/api/v1/authorization/roles/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertEqual(data['name'], 'Shift Supervisor')
        self.assertEqual(data['slug'], 'shift-supervisor')
        self.assertFalse(data['is_system'])
        self.assertTrue(data['can_delete'])  # No assigned users yet

        # Audit verification
        self.assertEqual(AuditLog.objects.filter(action='role_created').count(), initial_audit_count + 1)
        log = AuditLog.objects.filter(action='role_created').latest('id')
        self.assertEqual(log.actor, self.hr_user1)
        self.assertEqual(log.metadata.get('slug'), 'shift-supervisor')

    def test_role_creation_rejects_reserved_system_names_and_slugs(self):
        """Attempts to create a role with Super Admin name or slug are rejected."""
        self.client.force_authenticate(user=self.hr_user1)

        # Attempt to create 'Super Admin'
        resp1 = self.client.post('/api/v1/authorization/roles/', {'name': 'Super Admin'}, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_400_BAD_REQUEST)

        # Attempt to create 'Organization Owner (Super Admin)'
        resp2 = self.client.post('/api/v1/authorization/roles/', {'name': 'Organization Owner (Super Admin)'}, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

    # =========================================================================
    # D. ROLE EDITING
    # =========================================================================

    def test_role_editing_system_role_immutability(self):
        """System role names and identities cannot be modified via PUT/PATCH."""
        self.client.force_authenticate(user=self.hr_user1)

        # Attempt to rename Super Admin
        patch_resp = self.client.patch(
            f'/api/v1/authorization/roles/{self.superadmin_role1.id}/',
            {'name': 'Renamed Super Admin'},
            format='json'
        )
        self.assertEqual(patch_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.superadmin_role1.refresh_from_db()
        self.assertNotEqual(self.superadmin_role1.name, 'Renamed Super Admin')

    def test_role_editing_custom_role_and_audit(self):
        """Custom role can be updated and records an audit event."""
        self.client.force_authenticate(user=self.hr_user1)
        custom_role = Role.objects.create(organization=self.org1, name='Team Helper', is_system=False)

        response = self.client.patch(
            f'/api/v1/authorization/roles/{custom_role.id}/',
            {'description': 'Updated helper description'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        custom_role.refresh_from_db()
        self.assertEqual(custom_role.description, 'Updated helper description')

        # Audit verification
        log = AuditLog.objects.filter(action='role_updated').latest('id')
        self.assertEqual(log.target_id, str(custom_role.id))

    # =========================================================================
    # E. ROLE DELETION
    # =========================================================================

    def test_role_deletion_rejects_system_role(self):
        """System roles cannot be deleted and return 400 Bad Request."""
        self.client.force_authenticate(user=self.hr_user1)
        response = self.client.delete(f'/api/v1/authorization/roles/{self.hr_role1.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('System roles cannot be deleted', response.data['detail'])

    def test_role_deletion_rejects_role_with_assigned_users(self):
        """Custom roles with active user assignments cannot be deleted."""
        self.client.force_authenticate(user=self.hr_user1)
        custom_role = Role.objects.create(organization=self.org1, name='Active Assigned Role', is_system=False)
        UserRole.objects.create(user=self.emp_user1, role=custom_role, is_revoked=False)

        response = self.client.delete(f'/api/v1/authorization/roles/{custom_role.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('active user assignments', response.data['detail'])

    def test_role_deletion_eligible_custom_role_succeeds_with_audit(self):
        """Custom role with zero active users is deleted cleanly with 204 No Content."""
        self.client.force_authenticate(user=self.hr_user1)
        custom_role = Role.objects.create(organization=self.org1, name='Temporary Role', is_system=False)
        role_id = custom_role.id

        response = self.client.delete(f'/api/v1/authorization/roles/{role_id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Role.objects.filter(id=role_id).exists())

        # Audit verification
        log = AuditLog.objects.filter(action='role_deleted').latest('id')
        self.assertEqual(log.target_id, str(role_id))
        self.assertEqual(log.metadata.get('role_name'), 'Temporary Role')

    # =========================================================================
    # F. ROLE-PERMISSION ASSIGNMENT (ATOMIC FULL REPLACEMENT)
    # =========================================================================

    def test_role_permission_assignment_atomic_replacement(self):
        """PUT /roles/{id}/permissions/ atomically replaces assignments and logs audit."""
        self.client.force_authenticate(user=self.hr_user1)
        custom_role = Role.objects.create(organization=self.org1, name='Ops Coordinator', is_system=False)
        RolePermission.objects.create(role=custom_role, permission=self.perm_emp_view)

        new_perm_ids = [self.perm_emp_create.id, self.perm_role_manage.id]
        response = self.client.put(
            f'/api/v1/authorization/roles/{custom_role.id}/permissions/',
            {'permission_ids': new_perm_ids},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['permissions_count'], 2)

        assigned_ids = set(custom_role.role_permissions.values_list('permission_id', flat=True))
        self.assertEqual(assigned_ids, set(new_perm_ids))
        self.assertNotIn(self.perm_emp_view.id, assigned_ids)

        # Audit verification
        log = AuditLog.objects.filter(action='role_permissions_updated').latest('id')
        self.assertEqual(log.target_id, str(custom_role.id))

    def test_role_permission_assignment_superadmin_narrowing_rejected(self):
        """Super Admin permissions cannot be narrowed or modified via permissions action."""
        self.client.force_authenticate(user=self.superadmin_user1)
        response = self.client.put(
            f'/api/v1/authorization/roles/{self.superadmin_role1.id}/permissions/',
            {'permission_ids': [self.perm_emp_view.id]},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cannot be narrowed', response.data['detail'])

    def test_role_permission_assignment_unknown_id_rejected_leaves_unchanged(self):
        """Unknown permission ID is rejected with 400 and leaves existing assignments unchanged."""
        self.client.force_authenticate(user=self.hr_user1)
        custom_role = Role.objects.create(organization=self.org1, name='QA Engineer', is_system=False)
        RolePermission.objects.create(role=custom_role, permission=self.perm_emp_view)

        response = self.client.put(
            f'/api/v1/authorization/roles/{custom_role.id}/permissions/',
            {'permission_ids': [self.perm_emp_create.id, 999999]},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Unknown permission IDs', response.data['detail'])

        # Assignments must remain unchanged
        assigned_ids = list(custom_role.role_permissions.values_list('permission_id', flat=True))
        self.assertEqual(assigned_ids, [self.perm_emp_view.id])

    def test_role_permission_assignment_inactive_id_rejected(self):
        """Inactive permission ID is rejected with 400."""
        self.client.force_authenticate(user=self.hr_user1)
        custom_role = Role.objects.create(organization=self.org1, name='Tester', is_system=False)

        response = self.client.put(
            f'/api/v1/authorization/roles/{custom_role.id}/permissions/',
            {'permission_ids': [self.perm_inactive.id]},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Inactive permissions cannot be assigned', response.data['detail'])

    def test_role_permission_assignment_enterprise_safeguard(self):
        """Non-superadmin caller cannot assign preserved enterprise permissions."""
        self.client.force_authenticate(user=self.hr_user1)  # Not Super Admin
        custom_role = Role.objects.create(organization=self.org1, name='Auditor Custom', is_system=False)

        response = self.client.put(
            f'/api/v1/authorization/roles/{custom_role.id}/permissions/',
            {'permission_ids': [self.perm_enterprise.id]},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only Super Admins can assign preserved enterprise permissions', response.data['detail'])

    # =========================================================================
    # G. USER-ROLE ASSIGNMENT & REVOCATION
    # =========================================================================

    def test_user_role_assignment_valid_and_audit(self):
        """Assigning a role to a user within the same tenant succeeds and writes audit log."""
        self.client.force_authenticate(user=self.hr_user1)
        custom_role = Role.objects.create(organization=self.org1, name='Junior Dev', is_system=False)

        payload = {
            'user': self.emp_user1.id,
            'role': custom_role.id,
            'scope': ScopeChoices.ORGANIZATION,
        }
        response = self.client.post('/api/v1/authorization/user-roles/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role_name'], 'Junior Dev')

        # Audit verification
        log = AuditLog.objects.filter(action='role_assigned').latest('id')
        self.assertEqual(log.target_id, str(self.emp_user1.id))
        self.assertEqual(log.metadata.get('role_id'), custom_role.id)

    def test_user_role_assignment_duplicate_prevention(self):
        """Assigning the same role with the same scope to a user is rejected as duplicate."""
        self.client.force_authenticate(user=self.hr_user1)
        custom_role = Role.objects.create(organization=self.org1, name='Support Lead', is_system=False)
        UserRole.objects.create(user=self.emp_user1, role=custom_role, scope=ScopeChoices.ORGANIZATION, is_revoked=False)

        payload = {
            'user': self.emp_user1.id,
            'role': custom_role.id,
            'scope': ScopeChoices.ORGANIZATION,
        }
        response = self.client.post('/api/v1/authorization/user-roles/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('User already has this role assigned', str(response.data))

    def test_user_role_assignment_cross_tenant_rejected(self):
        """Assigning a role from Org 1 to a user in Org 2 is rejected."""
        self.client.force_authenticate(user=self.hr_user1)
        
        # User in Org 2
        user_org2 = User.objects.create_user(email='foreign@globex.local', password='Password123!', status='active')
        Employee.objects.create(user=user_org2, organization=self.org2, employee_code='EMP-GLX-001')

        payload = {
            'user': user_org2.id,
            'role': self.hr_role1.id,
            'scope': ScopeChoices.ORGANIZATION,
        }
        response = self.client.post('/api/v1/authorization/user-roles/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Target user does not belong to your organization', str(response.data))

    def test_user_role_assignment_superadmin_anti_escalation(self):
        """Non-Super Admin cannot assign the Super Admin role."""
        self.client.force_authenticate(user=self.hr_user1)  # HR Manager (not Super Admin)

        payload = {
            'user': self.emp_user1.id,
            'role': self.superadmin_role1.id,
            'scope': ScopeChoices.ORGANIZATION,
        }
        response = self.client.post('/api/v1/authorization/user-roles/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Only Super Admins can assign the Super Admin role', str(response.data))

    def test_user_role_revocation_via_action_and_delete(self):
        """UserRole can be revoked via POST /revoke/ and DELETE /, both writing audit logs."""
        self.client.force_authenticate(user=self.hr_user1)
        custom_role = Role.objects.create(organization=self.org1, name='Temporary Staff', is_system=False)
        ur = UserRole.objects.create(user=self.emp_user1, role=custom_role, is_revoked=False)

        # 1. Revoke via POST action
        revoke_resp = self.client.post(f'/api/v1/authorization/user-roles/{ur.id}/revoke/')
        self.assertEqual(revoke_resp.status_code, status.HTTP_200_OK)
        ur.refresh_from_db()
        self.assertTrue(ur.is_revoked)

        # Audit verification
        log = AuditLog.objects.filter(action='role_revoked').latest('id')
        self.assertEqual(log.target_id, str(self.emp_user1.id))

        # 2. Attempting to revoke already-revoked role returns 400
        repeat_resp = self.client.post(f'/api/v1/authorization/user-roles/{ur.id}/revoke/')
        self.assertEqual(repeat_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already revoked', repeat_resp.data['detail'])

        # 3. Create another assignment and revoke via DELETE
        ur2 = UserRole.objects.create(user=self.emp_user1, role=custom_role, is_revoked=False)
        del_resp = self.client.delete(f'/api/v1/authorization/user-roles/{ur2.id}/')
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)
        ur2.refresh_from_db()
        self.assertTrue(ur2.is_revoked)

    def test_user_role_revocation_superadmin_protection(self):
        """Non-Super Admin cannot revoke a Super Admin user-role assignment."""
        self.client.force_authenticate(user=self.hr_user1)  # Non-Super Admin
        response = self.client.post(f'/api/v1/authorization/user-roles/{self.superadmin_ur1.id}/revoke/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only Super Admins can revoke the Super Admin role', response.data['detail'])
        self.superadmin_ur1.refresh_from_db()
        self.assertFalse(self.superadmin_ur1.is_revoked)

    # =========================================================================
    # H. DYNAMIC PERMISSIONS LIVE REFLECTION
    # =========================================================================

    def test_dynamic_permissions_live_reflection(self):
        """Assigning a new permission immediately reflects in user effective permissions without server restart."""
        # Baseline: emp_user1 has no permissions
        perms_before = AuthorizationService.get_effective_permissions(self.emp_user1)
        self.assertNotIn('employee.create', perms_before)

        # Assign role with employee.create to emp_user1
        role = Role.objects.create(organization=self.org1, name='Recruiter', is_system=False)
        RolePermission.objects.create(role=role, permission=self.perm_emp_create)
        UserRole.objects.create(user=self.emp_user1, role=role, is_revoked=False)

        perms_after = AuthorizationService.get_effective_permissions(self.emp_user1)
        self.assertIn('employee.create', perms_after)
