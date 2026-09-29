from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.organization.models import Organization, Branch, OfficeNetwork, WorkingCalendar
from apps.employees.models import Employee, EmploymentStatus
from apps.authorization.models import Role, Permission, UserRole, RolePermission, ScopeChoices

User = get_user_model()


class WorkingCalendarIDORSecurityTests(TestCase):
    """
    C5.5.3.1 Security Verification:
    Verifies the security boundary and branch-level isolation of the WorkingCalendar API:
    1. A user authorized for Branch A cannot GET Branch B's WorkingCalendar by changing {id}.
    2. A user authorized for Branch A cannot PATCH Branch B's WorkingCalendar by changing {id}.
    3. Database mutation is completely rejected; Branch B remains unmodified.
    4. Authorized Branch A access works (GET & PATCH).
    5. All-Locations / organization-wide access works only for authorized scope within the tenant.
    6. Cross-tenant isolation: Org A user cannot GET or PATCH Org B calendar.
    7. Super Admin positive control case works across branches.
    8. Query parameter tampering cannot bypass authorization.
    9. Unauthenticated and unauthorized users are blocked (401 / 403).
    """

    def setUp(self):
        self.client = APIClient()

        # ----------------------------------------------------
        # Tenant Alpha (Organization A)
        # ----------------------------------------------------
        self.org_a = Organization.objects.create(name='Tenant Alpha', status='active')

        # Branch A & Branch B (both under Org A)
        self.branch_a = Branch.objects.create(
            organization=self.org_a, name='Branch A', radius=100
        )
        self.cal_a = self.branch_a.working_calendar
        self.cal_a.work_days = '0,1,2,3,4'
        self.cal_a.save()

        self.branch_b = Branch.objects.create(
            organization=self.org_a, name='Branch B', radius=100
        )
        self.cal_b = self.branch_b.working_calendar
        self.cal_b.work_days = '0,1,2,3,4'
        self.cal_b.save()

        # Office network allowing 127.0.0.1 for Org A
        OfficeNetwork.objects.create(
            branch=self.branch_a,
            name='Alpha Net',
            network='127.0.0.1/32',
            is_active=True
        )

        # ----------------------------------------------------
        # Tenant Beta (Organization B) - for cross-tenant isolation
        # ----------------------------------------------------
        self.org_b = Organization.objects.create(name='Tenant Beta', status='active')
        self.branch_c = Branch.objects.create(
            organization=self.org_b, name='Branch C', radius=100
        )
        self.cal_c = self.branch_c.working_calendar
        self.cal_c.work_days = '6,0,1,2,3'
        self.cal_c.save()

        OfficeNetwork.objects.create(
            branch=self.branch_c,
            name='Beta Net',
            network='127.0.0.1/32',
            is_active=True
        )

        # ----------------------------------------------------
        # Permissions
        # ----------------------------------------------------
        self.perm_update, _ = Permission.objects.get_or_create(
            codename='organization.update',
            defaults={'name': 'Update Organization', 'resource': 'organization', 'action': 'update'}
        )

        # ----------------------------------------------------
        # User 1: Scoped strictly to Branch A
        # ----------------------------------------------------
        self.user_branch_a = User.objects.create_user(
            email='user_branch_a@alpha.local', password='Password123!', status='active'
        )
        self.emp_branch_a = Employee.objects.create(
            user=self.user_branch_a,
            organization=self.org_a,
            branch=self.branch_a,
            employee_code='EMP-A1',
            employment_status=EmploymentStatus.ACTIVE
        )
        role_branch_a = Role.objects.create(organization=self.org_a, name='Branch A Admin Role')
        RolePermission.objects.create(role=role_branch_a, permission=self.perm_update)
        UserRole.objects.create(
            user=self.user_branch_a,
            role=role_branch_a,
            scope=ScopeChoices.BRANCH,
            branch=self.branch_a
        )

        # ----------------------------------------------------
        # User 2: Organization-wide scope in Org A (All Locations)
        # ----------------------------------------------------
        self.user_org_wide = User.objects.create_user(
            email='user_org_wide@alpha.local', password='Password123!', status='active'
        )
        self.emp_org_wide = Employee.objects.create(
            user=self.user_org_wide,
            organization=self.org_a,
            branch=self.branch_a,
            employee_code='EMP-ORG1',
            employment_status=EmploymentStatus.ACTIVE
        )
        role_org_wide = Role.objects.create(organization=self.org_a, name='Org Wide Admin Role')
        RolePermission.objects.create(role=role_org_wide, permission=self.perm_update)
        UserRole.objects.create(
            user=self.user_org_wide,
            role=role_org_wide,
            scope=ScopeChoices.ORGANIZATION
        )

        # ----------------------------------------------------
        # User 3: User without organization.update permission
        # ----------------------------------------------------
        self.user_no_perm = User.objects.create_user(
            email='no_perm@alpha.local', password='Password123!', status='active'
        )
        self.emp_no_perm = Employee.objects.create(
            user=self.user_no_perm,
            organization=self.org_a,
            branch=self.branch_a,
            employee_code='EMP-NO-PERM',
            employment_status=EmploymentStatus.ACTIVE
        )

        # ----------------------------------------------------
        # Super Admin
        # ----------------------------------------------------
        self.super_user = User.objects.create_superuser(
            email='superadmin@system.local', password='Password123!'
        )

    # =========================================================================
    # TEST 1 — GET IDOR: Branch A user cannot GET Branch B's WorkingCalendar
    # =========================================================================
    def test_01_branch_a_user_cannot_get_branch_b_calendar(self):
        """
        TEST 1 — GET IDOR:
        A user authorized only for Branch A requests GET /api/v1/organization/working-calendars/{cal_b_id}/.
        Must be rejected with 404 Not Found (object-level isolation hides existence).
        Branch B calendar data must never be exposed.
        """
        self.client.force_authenticate(user=self.user_branch_a)
        response = self.client.get(f'/api/v1/organization/working-calendars/{self.cal_b.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # Ensure response payload does not leak Branch B data
        self.assertNotIn('work_days', response.data)
        self.assertNotIn(self.cal_b.id, [getattr(response, 'data', {}).get('id')])

    # =========================================================================
    # TEST 2 — PATCH IDOR: Branch A user cannot PATCH Branch B's WorkingCalendar
    # =========================================================================
    def test_02_branch_a_user_cannot_patch_branch_b_calendar(self):
        """
        TEST 2 — PATCH IDOR:
        A user authorized only for Branch A attempts to mutate Branch B's WorkingCalendar.
        Must be rejected with 404 Not Found.
        Critical assertion: Branch B's actual database record must remain unchanged.
        """
        self.client.force_authenticate(user=self.user_branch_a)
        original_work_days = self.cal_b.work_days

        response = self.client.patch(
            f'/api/v1/organization/working-calendars/{self.cal_b.id}/',
            {'work_days': '0,1,2'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Assert database state remains completely unchanged
        self.cal_b.refresh_from_db()
        self.assertEqual(self.cal_b.work_days, original_work_days)
        self.assertNotEqual(self.cal_b.work_days, '0,1,2')

    # =========================================================================
    # TEST 3 — QUERY PARAMETER TAMPERING CANNOT BYPASS SCOPE
    # =========================================================================
    def test_03_query_parameter_tampering_cannot_bypass_scope(self):
        """
        TEST 3 — Parameter Tampering:
        A Branch-A-only user attempts to supply query parameters (e.g. ?branch={id} or ?scope=all)
        to manipulate backend evaluation.
        Backend authorization must evaluate strictly via AuthorizationService and reject access.
        """
        self.client.force_authenticate(user=self.user_branch_a)

        # Attempt with branch query param pointing to Branch A while targeting Calendar B
        resp1 = self.client.get(
            f'/api/v1/organization/working-calendars/{self.cal_b.id}/?branch={self.branch_a.id}'
        )
        self.assertEqual(resp1.status_code, status.HTTP_404_NOT_FOUND)

        # Attempt PATCH with branch parameter
        resp2 = self.client.patch(
            f'/api/v1/organization/working-calendars/{self.cal_b.id}/?branch_id={self.branch_a.id}',
            {'work_days': '0,1'},
            format='json'
        )
        self.assertEqual(resp2.status_code, status.HTTP_404_NOT_FOUND)

        self.cal_b.refresh_from_db()
        self.assertEqual(self.cal_b.work_days, '0,1,2,3,4')

    # =========================================================================
    # TEST 4 — ALL-LOCATIONS / BROADER SCOPE WITHIN TENANT
    # =========================================================================
    def test_04_organization_wide_scope_within_tenant(self):
        """
        TEST 4 — Organization-Wide / All-Locations Scope:
        User with ScopeChoices.ORGANIZATION in Org A can access both Branch A and Branch B calendars,
        as both belong to Tenant Alpha.
        """
        self.client.force_authenticate(user=self.user_org_wide)

        # Can GET Branch A calendar
        resp_a = self.client.get(f'/api/v1/organization/working-calendars/{self.cal_a.id}/')
        self.assertEqual(resp_a.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_a.data['id'], self.cal_a.id)

        # Can GET Branch B calendar
        resp_b = self.client.get(f'/api/v1/organization/working-calendars/{self.cal_b.id}/')
        self.assertEqual(resp_b.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_b.data['id'], self.cal_b.id)

        # List returns both Branch A and Branch B calendars
        resp_list = self.client.get('/api/v1/organization/working-calendars/')
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        list_ids = [c['id'] for c in resp_list.data]
        self.assertIn(self.cal_a.id, list_ids)
        self.assertIn(self.cal_b.id, list_ids)

    # =========================================================================
    # TEST 5 — CROSS-TENANT / CROSS-ORGANIZATION ISOLATION
    # =========================================================================
    def test_05_cross_tenant_isolation(self):
        """
        TEST 5 — Cross-Tenant Safety:
        Even an Organization-Wide user in Tenant Alpha CANNOT access Tenant Beta's calendar.
        GET and PATCH on Calendar C (under Org B) must return 404 Not Found.
        """
        self.client.force_authenticate(user=self.user_org_wide)
        original_c_days = self.cal_c.work_days

        # Cross-tenant GET rejected
        resp_get = self.client.get(f'/api/v1/organization/working-calendars/{self.cal_c.id}/')
        self.assertEqual(resp_get.status_code, status.HTTP_404_NOT_FOUND)

        # Cross-tenant PATCH rejected
        resp_patch = self.client.patch(
            f'/api/v1/organization/working-calendars/{self.cal_c.id}/',
            {'work_days': '0,1,2,3,4'},
            format='json'
        )
        self.assertEqual(resp_patch.status_code, status.HTTP_404_NOT_FOUND)

        # Database record for Calendar C remains unmodified
        self.cal_c.refresh_from_db()
        self.assertEqual(self.cal_c.work_days, original_c_days)

        # List endpoint must never leak Tenant Beta calendars
        resp_list = self.client.get('/api/v1/organization/working-calendars/')
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        list_ids = [c['id'] for c in resp_list.data]
        self.assertNotIn(self.cal_c.id, list_ids)

    # =========================================================================
    # TEST 6 — SUPER ADMIN CONTROL CASE
    # =========================================================================
    def test_06_super_admin_control_case(self):
        """
        TEST 6 — Super Admin Positive Control:
        Super Admin bypasses branch scoping and can view and update any calendar.
        """
        self.client.force_authenticate(user=self.super_user)

        # Super Admin can GET Branch B calendar
        resp_get = self.client.get(f'/api/v1/organization/working-calendars/{self.cal_b.id}/')
        self.assertEqual(resp_get.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_get.data['id'], self.cal_b.id)

        # Super Admin can PATCH Branch B calendar
        resp_patch = self.client.patch(
            f'/api/v1/organization/working-calendars/{self.cal_b.id}/',
            {'work_days': '6,0,1,2,3'},
            format='json'
        )
        self.assertEqual(resp_patch.status_code, status.HTTP_200_OK)

        self.cal_b.refresh_from_db()
        self.assertEqual(self.cal_b.work_days, '6,0,1,2,3')

        # Super Admin list returns all calendars across all organizations
        resp_list = self.client.get('/api/v1/organization/working-calendars/')
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        list_ids = [c['id'] for c in resp_list.data]
        self.assertIn(self.cal_a.id, list_ids)
        self.assertIn(self.cal_b.id, list_ids)
        self.assertIn(self.cal_c.id, list_ids)

    # =========================================================================
    # TEST 7 — AUTHORIZED BRANCH A ACCESS (POSITIVE CONTROL)
    # =========================================================================
    def test_07_authorized_branch_a_access_works(self):
        """
        TEST 7 — Authorized Access:
        User authorized for Branch A CAN retrieve and update Branch A's calendar.
        """
        self.client.force_authenticate(user=self.user_branch_a)

        # Authorized GET
        resp_get = self.client.get(f'/api/v1/organization/working-calendars/{self.cal_a.id}/')
        self.assertEqual(resp_get.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_get.data['id'], self.cal_a.id)
        self.assertEqual(resp_get.data['branch'], self.branch_a.id)

        # Authorized PATCH
        resp_patch = self.client.patch(
            f'/api/v1/organization/working-calendars/{self.cal_a.id}/',
            {'work_days': '0,1,2,3,4,5'},
            format='json'
        )
        self.assertEqual(resp_patch.status_code, status.HTTP_200_OK)

        self.cal_a.refresh_from_db()
        self.assertEqual(self.cal_a.work_days, '0,1,2,3,4,5')

        # Authorized LIST: returns ONLY Branch A
        resp_list = self.client.get('/api/v1/organization/working-calendars/')
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        list_ids = [c['id'] for c in resp_list.data]
        self.assertEqual(list_ids, [self.cal_a.id])

    # =========================================================================
    # TEST 8 — UNAUTHENTICATED & UNAUTHORIZED REQUESTS
    # =========================================================================
    def test_08_unauthenticated_and_unauthorized_rejected(self):
        """
        TEST 8 — Negative Controls:
        1. Unauthenticated request returns 401 Unauthorized.
        2. Authenticated user without organization.update returns 403 Forbidden.
        """
        # Unauthenticated
        resp_unauth = self.client.get(f'/api/v1/organization/working-calendars/{self.cal_a.id}/')
        self.assertEqual(resp_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        # User without permission
        self.client.force_authenticate(user=self.user_no_perm)
        resp_forbidden = self.client.get(f'/api/v1/organization/working-calendars/{self.cal_a.id}/')
        self.assertEqual(resp_forbidden.status_code, status.HTTP_403_FORBIDDEN)
