from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.organization.models import Organization, Department, Designation, OfficeNetwork, Branch, Team
from apps.employees.models import Employee, EmploymentStatus
from apps.authorization.models import Role, Permission, UserRole, RolePermission
from apps.audit.models import AuditLog

User = get_user_model()


class MultiTenantIsolationSecurityTests(TestCase):
    """
    Security regression test suite verifying cross-tenant isolation and IDOR prevention
    across Authorization, Organization, and Audit modules.
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Create Organization A and Organization B
        self.org_a = Organization.objects.create(name='Tenant Alpha', status='active')
        self.org_b = Organization.objects.create(name='Tenant Beta', status='active')

        # 2. Permissions required for admin operations
        self.perm_codenames = [
            'role.view', 'role.assign', 'role.revoke',
            'permission.view', 'permission.assign', 'permission.revoke',
            'department.view', 'department.manage',
            'team.view', 'team.manage',
            'designation.view', 'designation.manage',
            'office_network.view', 'office_network.create', 'office_network.update', 'office_network.delete',
            'organization.view', 'organization.manage',
            'audit.view',
        ]
        self.permissions = {}
        for code in self.perm_codenames:
            res, act = code.split('.')
            perm, _ = Permission.objects.get_or_create(
                codename=code,
                defaults={'name': code, 'resource': res, 'action': act}
            )
            self.permissions[code] = perm

        # 3. Create Admin A & Role A in Org A
        self.user_admin_a = User.objects.create_user(email='admin_a@alpha.local', password='Password123!', status='active')
        self.emp_admin_a = Employee.objects.create(
            user=self.user_admin_a,
            organization=self.org_a,
            employee_code='EMP-A-001',
            employment_status=EmploymentStatus.ACTIVE
        )
        self.role_admin_a = Role.objects.create(organization=self.org_a, name='Admin Role Alpha')
        for perm in self.permissions.values():
            RolePermission.objects.create(role=self.role_admin_a, permission=perm)
        UserRole.objects.create(user=self.user_admin_a, role=self.role_admin_a)

        # 4. Create Employee A in Org A
        self.user_emp_a = User.objects.create_user(email='emp_a@alpha.local', password='Password123!', status='active')
        self.emp_a = Employee.objects.create(
            user=self.user_emp_a,
            organization=self.org_a,
            employee_code='EMP-A-002',
            employment_status=EmploymentStatus.ACTIVE
        )
        self.role_member_a = Role.objects.create(organization=self.org_a, name='Member Role Alpha')
        self.user_role_a = UserRole.objects.create(user=self.user_emp_a, role=self.role_member_a)
        self.role_perm_a = RolePermission.objects.create(role=self.role_member_a, permission=self.permissions['department.view'])

        # 5. Create Admin B & Role B in Org B
        self.user_admin_b = User.objects.create_user(email='admin_b@beta.local', password='Password123!', status='active')
        self.emp_admin_b = Employee.objects.create(
            user=self.user_admin_b,
            organization=self.org_b,
            employee_code='EMP-B-001',
            employment_status=EmploymentStatus.ACTIVE
        )
        self.role_admin_b = Role.objects.create(organization=self.org_b, name='Admin Role Beta')
        for perm in self.permissions.values():
            RolePermission.objects.create(role=self.role_admin_b, permission=perm)
        UserRole.objects.create(user=self.user_admin_b, role=self.role_admin_b)

        # 6. Create Employee B in Org B
        self.user_emp_b = User.objects.create_user(email='emp_b@beta.local', password='Password123!', status='active')
        self.emp_b = Employee.objects.create(
            user=self.user_emp_b,
            organization=self.org_b,
            employee_code='EMP-B-002',
            employment_status=EmploymentStatus.ACTIVE
        )
        self.role_member_b = Role.objects.create(organization=self.org_b, name='Member Role Beta')
        self.user_role_b = UserRole.objects.create(user=self.user_emp_b, role=self.role_member_b)
        self.role_perm_b = RolePermission.objects.create(role=self.role_member_b, permission=self.permissions['department.view'])

        # 7. Create Organization Resources for Org A and Org B
        self.branch_a = Branch.objects.create(organization=self.org_a, name='HQ Alpha')
        self.branch_b = Branch.objects.create(organization=self.org_b, name='HQ Beta')
        self.net_a = OfficeNetwork.objects.create(branch=self.branch_a, name='Net Alpha', network='127.0.0.1/32')
        self.net_b = OfficeNetwork.objects.create(branch=self.branch_b, name='Net Beta', network='172.16.0.0/16')

        self.dept_a = Department.objects.create(branch=self.branch_a, name='Engineering Alpha')
        self.dept_b = Department.objects.create(branch=self.branch_b, name='Engineering Beta')

        self.team_a = Team.objects.create(department=self.dept_a, name='Backend Alpha')
        self.team_b = Team.objects.create(department=self.dept_b, name='Backend Beta')

        self.desig_a = Designation.objects.create(organization=self.org_a, name='Developer Alpha')
        self.desig_b = Designation.objects.create(organization=self.org_b, name='Developer Beta')

        # 8. Create Audit Logs
        self.audit_a = AuditLog.objects.create(
            organization=self.org_a,
            actor=self.user_admin_a,
            action='dept_created',
            target_type='department',
            target_id=str(self.dept_a.id)
        )
        self.audit_b = AuditLog.objects.create(
            organization=self.org_b,
            actor=self.user_admin_b,
            action='dept_created',
            target_type='department',
            target_id=str(self.dept_b.id)
        )
        self.audit_system = AuditLog.objects.create(
            organization=None,
            actor=None,
            action='login_failure',
            metadata={'ip': '198.51.100.1'}
        )

        # 9. Superuser
        self.superuser = User.objects.create_superuser(email='super@hrms.local', password='Password123!')

    # =========================================================================
    # A. AUTHORIZATION MODULE: ROLES
    # =========================================================================

    def test_role_list_excludes_other_tenant_roles(self):
        """Admin A must only see Org A roles, never Org B roles."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get('/api/v1/authorization/roles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        role_ids = [r['id'] for r in response.data]
        self.assertIn(self.role_admin_a.id, role_ids)
        self.assertIn(self.role_member_a.id, role_ids)
        self.assertNotIn(self.role_admin_b.id, role_ids)
        self.assertNotIn(self.role_member_b.id, role_ids)

    def test_role_retrieve_idor_blocked(self):
        """Admin A attempting to retrieve Org B role directly must receive 404."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get(f'/api/v1/authorization/roles/{self.role_admin_b.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_role_update_idor_blocked(self):
        """Admin A attempting to modify Org B role must receive 404."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.patch(f'/api/v1/authorization/roles/{self.role_admin_b.id}/', {'name': 'Hacked Role'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.role_admin_b.refresh_from_db()
        self.assertEqual(self.role_admin_b.name, 'Admin Role Beta')

    def test_role_delete_idor_blocked(self):
        """Admin A attempting to delete Org B role must receive 404."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.delete(f'/api/v1/authorization/roles/{self.role_admin_b.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Role.objects.filter(id=self.role_admin_b.id).exists())

    def test_role_create_bound_to_requesting_org(self):
        """Creating a role assigns it strictly to the user's organization."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.post('/api/v1/authorization/roles/', {'name': 'Custom Alpha Role'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_role = Role.objects.get(id=response.data['id'])
        self.assertEqual(created_role.organization, self.org_a)

    # =========================================================================
    # B. AUTHORIZATION MODULE: USER ROLES
    # =========================================================================

    def test_user_role_list_excludes_other_tenant_assignments(self):
        """Admin A must only see user roles for Org A, never Org B."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get('/api/v1/authorization/user-roles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_role_ids = [ur['id'] for ur in response.data]
        self.assertIn(self.user_role_a.id, user_role_ids)
        self.assertNotIn(self.user_role_b.id, user_role_ids)

    def test_user_role_revoke_idor_blocked(self):
        """Admin A attempting to revoke Org B user role must receive 404."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.post(f'/api/v1/authorization/user-roles/{self.user_role_b.id}/revoke/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.user_role_b.refresh_from_db()
        self.assertFalse(self.user_role_b.is_revoked)

    def test_user_role_assign_cross_tenant_role_rejected(self):
        """Admin A cannot assign Org B role to Org A employee."""
        self.client.force_authenticate(user=self.user_admin_a)
        payload = {'user': self.user_emp_a.id, 'role': self.role_member_b.id}
        response = self.client.post('/api/v1/authorization/user-roles/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role', response.data)

    def test_user_role_assign_cross_tenant_user_rejected(self):
        """Admin A cannot assign Org A role to Org B employee."""
        self.client.force_authenticate(user=self.user_admin_a)
        payload = {'user': self.user_emp_b.id, 'role': self.role_member_a.id}
        response = self.client.post('/api/v1/authorization/user-roles/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('user', response.data)

    # =========================================================================
    # C. AUTHORIZATION MODULE: ROLE PERMISSIONS
    # =========================================================================

    def test_role_permission_list_excludes_other_tenant(self):
        """Admin A querying role permissions cannot see Org B role permissions."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get(f'/api/v1/authorization/role-permissions/?role={self.role_member_b.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_role_permission_assign_cross_tenant_rejected(self):
        """Admin A cannot assign permissions to an Org B role."""
        self.client.force_authenticate(user=self.user_admin_a)
        payload = {'role': self.role_member_b.id, 'permission': self.permissions['department.view'].id}
        response = self.client.post('/api/v1/authorization/role-permissions/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_role_permission_revoke_cross_tenant_blocked(self):
        """Admin A cannot revoke permissions from an Org B role."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.post(f'/api/v1/authorization/role-permissions/{self.role_perm_b.id}/revoke/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(RolePermission.objects.filter(id=self.role_perm_b.id).exists())

    # =========================================================================
    # D. ORGANIZATION MODULE: DEPARTMENTS
    # =========================================================================

    def test_department_list_isolation(self):
        """Admin A only sees Org A departments."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get('/api/v1/organization/departments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dept_ids = [d['id'] for d in response.data]
        self.assertIn(self.dept_a.id, dept_ids)
        self.assertNotIn(self.dept_b.id, dept_ids)

    def test_department_retrieve_idor_blocked(self):
        """Admin A cannot retrieve Org B department."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get(f'/api/v1/organization/departments/{self.dept_b.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_department_update_idor_blocked(self):
        """Admin A cannot modify Org B department."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.patch(f'/api/v1/organization/departments/{self.dept_b.id}/', {'name': 'Hacked Dept'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.dept_b.refresh_from_db()
        self.assertEqual(self.dept_b.name, 'Engineering Beta')

    def test_department_delete_idor_blocked(self):
        """Admin A cannot delete Org B department."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.delete(f'/api/v1/organization/departments/{self.dept_b.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Department.objects.filter(id=self.dept_b.id).exists())

    def test_department_create_payload_injection_rejected(self):
        """Admin A attempting to specify Org B in create payload is rejected with 400."""
        self.client.force_authenticate(user=self.user_admin_a)
        payload = {'organization': self.org_b.id, 'name': 'Injected Dept'}
        response = self.client.post('/api/v1/organization/departments/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('branch', response.data)

    def test_team_list_isolation(self):
        """Admin A only sees Org A teams."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get('/api/v1/organization/teams/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        team_ids = [t['id'] for t in response.data]
        self.assertIn(self.team_a.id, team_ids)
        self.assertNotIn(self.team_b.id, team_ids)

    def test_team_retrieve_idor_blocked(self):
        """Admin A cannot retrieve Org B team."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get(f'/api/v1/organization/teams/{self.team_b.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_team_update_idor_blocked(self):
        """Admin A cannot modify Org B team."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.patch(f'/api/v1/organization/teams/{self.team_b.id}/', {'name': 'Hacked Team'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_team_delete_idor_blocked(self):
        """Admin A cannot delete Org B team."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.delete(f'/api/v1/organization/teams/{self.team_b.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_team_create_payload_injection_rejected(self):
        """Admin A attempting to specify Org B department in create payload is rejected with 400."""
        self.client.force_authenticate(user=self.user_admin_a)
        payload = {'department': self.dept_b.id, 'name': 'Injected Team'}
        response = self.client.post('/api/v1/organization/teams/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('department', response.data)

    # =========================================================================
    # E. ORGANIZATION MODULE: DESIGNATIONS
    # =========================================================================

    def test_designation_list_isolation(self):
        """Admin A only sees Org A designations."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get('/api/v1/organization/designations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        desig_ids = [d['id'] for d in response.data]
        self.assertIn(self.desig_a.id, desig_ids)
        self.assertNotIn(self.desig_b.id, desig_ids)

    def test_designation_retrieve_idor_blocked(self):
        """Admin A cannot retrieve Org B designation."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get(f'/api/v1/organization/designations/{self.desig_b.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_designation_update_idor_blocked(self):
        """Admin A cannot update Org B designation."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.patch(f'/api/v1/organization/designations/{self.desig_b.id}/', {'name': 'Hacked Desig'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_designation_create_payload_injection_rejected(self):
        """Admin A specifying Org B ID on designation creation is rejected."""
        self.client.force_authenticate(user=self.user_admin_a)
        payload = {'organization': self.org_b.id, 'name': 'Injected Desig'}
        response = self.client.post('/api/v1/organization/designations/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # =========================================================================
    # F. ORGANIZATION MODULE: OFFICE NETWORKS
    # =========================================================================

    def test_office_network_list_isolation(self):
        """Admin A only sees Org A office networks."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get('/api/v1/organization/office-networks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        net_ids = [n['id'] for n in response.data]
        self.assertIn(self.net_a.id, net_ids)
        self.assertNotIn(self.net_b.id, net_ids)

    def test_office_network_retrieve_idor_blocked(self):
        """Admin A cannot retrieve Org B office network."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get(f'/api/v1/organization/office-networks/{self.net_b.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_office_network_update_idor_blocked(self):
        """Admin A cannot modify Org B office network."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.patch(f'/api/v1/organization/office-networks/{self.net_b.id}/', {'name': 'Hacked Net'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_office_network_create_payload_injection_rejected(self):
        """Admin A specifying Org B ID on network creation is rejected."""
        self.client.force_authenticate(user=self.user_admin_a)
        payload = {'organization': self.org_b.id, 'name': 'Injected Net', 'network': '192.168.1.0/24'}
        response = self.client.post('/api/v1/organization/office-networks/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # =========================================================================
    # G. ORGANIZATION VIEWSET ISOLATION
    # =========================================================================

    def test_organization_list_isolation(self):
        """Admin A only sees their own organization in the list."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get('/api/v1/organization/organizations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        org_ids = [o['id'] for o in response.data]
        self.assertIn(self.org_a.id, org_ids)
        self.assertNotIn(self.org_b.id, org_ids)

    def test_organization_retrieve_idor_blocked(self):
        """Admin A cannot retrieve Org B organization details."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get(f'/api/v1/organization/organizations/{self.org_b.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_organization_update_idor_blocked(self):
        """Admin A cannot modify Org B organization."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.patch(f'/api/v1/organization/organizations/{self.org_b.id}/', {'name': 'Hacked Org'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # H. AUDIT LOG ISOLATION
    # =========================================================================

    def test_audit_log_list_isolation(self):
        """Admin A only sees Org A audit logs, never Org B or unassigned system logs."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get('/api/v1/audit-logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log_ids = [l['id'] for l in response.data]
        self.assertIn(self.audit_a.id, log_ids)
        self.assertNotIn(self.audit_b.id, log_ids)
        self.assertNotIn(self.audit_system.id, log_ids)

    def test_audit_log_retrieve_idor_blocked(self):
        """Admin A cannot retrieve Org B audit log."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get(f'/api/v1/audit-logs/{self.audit_b.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_audit_log_system_event_inaccessible_to_tenant_admin(self):
        """Admin A cannot retrieve unassigned system audit logs."""
        self.client.force_authenticate(user=self.user_admin_a)
        response = self.client.get(f'/api/v1/audit-logs/{self.audit_system.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_audit_log_superadmin_global_access(self):
        """Superadmin can see all audit logs and filter by organization."""
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get('/api/v1/audit-logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log_ids = [l['id'] for l in response.data]
        self.assertIn(self.audit_a.id, log_ids)
        self.assertIn(self.audit_b.id, log_ids)
        self.assertIn(self.audit_system.id, log_ids)

        # Filter by Org A
        filtered_resp = self.client.get(f'/api/v1/audit-logs/?organization={self.org_a.id}')
        self.assertEqual(filtered_resp.status_code, status.HTTP_200_OK)
        filtered_ids = [l['id'] for l in filtered_resp.data]
        self.assertIn(self.audit_a.id, filtered_ids)
        self.assertNotIn(self.audit_b.id, filtered_ids)

    # =========================================================================
    # I. SUPERADMIN GLOBAL ACCESS
    # =========================================================================

    def test_superadmin_can_view_all_roles_and_filter(self):
        """Superadmin can see roles across all organizations and filter."""
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get('/api/v1/authorization/roles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        role_ids = [r['id'] for r in response.data]
        self.assertIn(self.role_admin_a.id, role_ids)
        self.assertIn(self.role_admin_b.id, role_ids)

        filtered = self.client.get(f'/api/v1/authorization/roles/?organization={self.org_a.id}')
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        filtered_ids = [r['id'] for r in filtered.data]
        self.assertIn(self.role_admin_a.id, filtered_ids)
        self.assertNotIn(self.role_admin_b.id, filtered_ids)

    # =========================================================================
    # J. UNAUTHENTICATED & UNAUTHORIZED ACCESS
    # =========================================================================

    def test_unauthenticated_requests_receive_401(self):
        """Unauthenticated requests to all endpoints receive 401."""
        endpoints = [
            '/api/v1/authorization/roles/',
            '/api/v1/authorization/user-roles/',
            '/api/v1/organization/departments/',
            '/api/v1/organization/designations/',
            '/api/v1/organization/office-networks/',
            '/api/v1/organization/organizations/',
            '/api/v1/audit-logs/',
        ]
        for url in endpoints:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED, f"Expected 401 for {url}")

    def test_unauthorized_user_receives_403(self):
        """User without required permissions receives 403."""
        unprivileged = User.objects.create_user(email='unprivileged@alpha.local', password='Password123!', status='active')
        Employee.objects.create(
            user=unprivileged,
            organization=self.org_a,
            employee_code='EMP-A-999',
            employment_status=EmploymentStatus.ACTIVE
        )
        self.client.force_authenticate(user=unprivileged)

        protected_endpoints = [
            '/api/v1/authorization/roles/',
            '/api/v1/organization/departments/',
            '/api/v1/organization/office-networks/',
            '/api/v1/audit-logs/',
        ]
        for url in protected_endpoints:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, f"Expected 403 for {url}")

    # =========================================================================
    # K. USER PERMISSION GRANT ISOLATION
    # =========================================================================

    def test_user_permission_grant_list_isolation(self):
        """Admin A only sees direct permission grants of Org A users."""
        from apps.authorization.models import UserPermissionGrant
        perm = Permission.objects.first()
        grant_a = UserPermissionGrant.objects.create(user=self.user_emp_a, permission=perm, granted_by=self.user_admin_a)
        grant_b = UserPermissionGrant.objects.create(user=self.user_emp_b, permission=perm, granted_by=self.user_admin_b)

        self.client.force_authenticate(user=self.user_admin_a)
        resp = self.client.get('/api/v1/authorization/user-permissions/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        grant_ids = [g['id'] for g in resp.data]
        self.assertIn(grant_a.id, grant_ids)
        self.assertNotIn(grant_b.id, grant_ids)

    def test_user_permission_grant_retrieve_idor_blocked(self):
        """Admin A cannot retrieve Org B user permission grant."""
        from apps.authorization.models import UserPermissionGrant
        perm = Permission.objects.first()
        grant_b = UserPermissionGrant.objects.create(user=self.user_emp_b, permission=perm, granted_by=self.user_admin_b)

        self.client.force_authenticate(user=self.user_admin_a)
        resp = self.client.get(f'/api/v1/authorization/user-permissions/{grant_b.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_permission_grant_cross_tenant_create_blocked(self):
        """Admin A cannot grant direct permission to Org B user."""
        perm = Permission.objects.first()
        self.client.force_authenticate(user=self.user_admin_a)
        resp = self.client.post('/api/v1/authorization/user-permissions/', {
            'user': self.user_emp_b.id,
            'permission': perm.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('user', resp.data)

    def test_user_permission_grant_revoke_idor_blocked(self):
        """Admin A cannot revoke direct permission of Org B user."""
        from apps.authorization.models import UserPermissionGrant
        perm = Permission.objects.first()
        grant_b = UserPermissionGrant.objects.create(user=self.user_emp_b, permission=perm, granted_by=self.user_admin_b)

        self.client.force_authenticate(user=self.user_admin_a)
        resp = self.client.post(f'/api/v1/authorization/user-permissions/{grant_b.id}/revoke/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_permission_grant_cross_tenant_patch_put_delete_blocked(self):
        """Admin A cannot PATCH, PUT, or DELETE an Org B user permission grant."""
        from apps.authorization.models import UserPermissionGrant
        perm = Permission.objects.first()
        grant_b = UserPermissionGrant.objects.create(user=self.user_emp_b, permission=perm, granted_by=self.user_admin_b)

        self.client.force_authenticate(user=self.user_admin_a)
        # PATCH cross-tenant
        patch_resp = self.client.patch(f'/api/v1/authorization/user-permissions/{grant_b.id}/', {'is_revoked': True})
        self.assertEqual(patch_resp.status_code, status.HTTP_404_NOT_FOUND)

        # PUT cross-tenant
        put_resp = self.client.put(f'/api/v1/authorization/user-permissions/{grant_b.id}/', {
            'user': self.user_emp_a.id,
            'permission': perm.id,
        })
        self.assertEqual(put_resp.status_code, status.HTTP_404_NOT_FOUND)

        # DELETE cross-tenant
        del_resp = self.client.delete(f'/api/v1/authorization/user-permissions/{grant_b.id}/')
        self.assertEqual(del_resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_permission_grant_same_tenant_authorized_lifecycle(self):
        """Admin A can create, retrieve, update, revoke, and delete a grant for Org A user."""
        from apps.authorization.models import UserPermissionGrant
        perm = Permission.objects.first()
        self.client.force_authenticate(user=self.user_admin_a)

        # 1. Create same-tenant
        create_resp = self.client.post('/api/v1/authorization/user-permissions/', {
            'user': self.user_emp_a.id,
            'permission': perm.id,
        })
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        grant_id = create_resp.data['id']

        # 2. Retrieve same-tenant
        get_resp = self.client.get(f'/api/v1/authorization/user-permissions/{grant_id}/')
        self.assertEqual(get_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(get_resp.data['user'], self.user_emp_a.id)

        # 3. Patch same-tenant target user to Org B user rejected
        patch_bad_resp = self.client.patch(f'/api/v1/authorization/user-permissions/{grant_id}/', {
            'user': self.user_emp_b.id,
        })
        self.assertEqual(patch_bad_resp.status_code, status.HTTP_400_BAD_REQUEST)

        # 4. Revoke same-tenant
        revoke_resp = self.client.post(f'/api/v1/authorization/user-permissions/{grant_id}/revoke/')
        self.assertEqual(revoke_resp.status_code, status.HTTP_200_OK)
        grant = UserPermissionGrant.objects.get(id=grant_id)
        self.assertTrue(grant.is_revoked)

        # Revoked grant is excluded from active queryset
        revoked_get = self.client.get(f'/api/v1/authorization/user-permissions/{grant_id}/')
        self.assertEqual(revoked_get.status_code, status.HTTP_404_NOT_FOUND)

        # 5. Delete active same-tenant grant
        perm2 = Permission.objects.exclude(id=perm.id).first()
        create_resp2 = self.client.post('/api/v1/authorization/user-permissions/', {
            'user': self.user_emp_a.id,
            'permission': perm2.id,
        })
        self.assertEqual(create_resp2.status_code, status.HTTP_201_CREATED)
        grant2_id = create_resp2.data['id']

        del_resp = self.client.delete(f'/api/v1/authorization/user-permissions/{grant2_id}/')
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(UserPermissionGrant.objects.filter(id=grant2_id).exists())

