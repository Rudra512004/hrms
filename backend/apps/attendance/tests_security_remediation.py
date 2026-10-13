from datetime import date
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.organization.models import Organization, Branch
from apps.employees.models import Employee
from apps.authorization.models import (
    Role, Permission, RolePermission, UserRole, UserPermissionGrant, ScopeChoices
)
from apps.attendance.models import BreakType, Attendance

User = get_user_model()


class BreakTypeTenantIsolationTests(TestCase):
    """
    Phase 1A Regression Suite:
    Verify that BreakTypeViewSet strictly isolates break types by organization
    for all users, including superusers, and safely denies unassociated contexts.
    """

    def setUp(self):
        self.client = APIClient()

        # Create two separate organizations
        self.org1 = Organization.objects.create(name='Tenant Alpha')
        self.org2 = Organization.objects.create(name='Tenant Beta')

        self.branch1 = Branch.objects.create(organization=self.org1, name='Alpha Main')
        self.branch2 = Branch.objects.create(organization=self.org2, name='Beta Main')

        # Permissions needed for BreakType endpoints
        self.perm_shift_view = Permission.objects.get(codename='shift.view')
        self.perm_shift_manage = Permission.objects.get(codename='shift.manage')

        # Roles for Org 1 and Org 2
        self.role_org1 = Role.objects.create(organization=self.org1, name='Shift Manager Org1')
        RolePermission.objects.create(role=self.role_org1, permission=self.perm_shift_view)
        RolePermission.objects.create(role=self.role_org1, permission=self.perm_shift_manage)

        self.role_org2 = Role.objects.create(organization=self.org2, name='Shift Manager Org2')
        RolePermission.objects.create(role=self.role_org2, permission=self.perm_shift_view)
        RolePermission.objects.create(role=self.role_org2, permission=self.perm_shift_manage)

        # User in Org 1
        self.user_org1 = User.objects.create_user(
            email='manager@alpha.com', password='Password123!', status='active'
        )
        self.emp_org1 = Employee.objects.create(
            user=self.user_org1, employee_code='EMP-A1',
            organization=self.org1, branch=self.branch1
        )
        UserRole.objects.create(
            user=self.user_org1, role=self.role_org1, scope=ScopeChoices.ORGANIZATION
        )

        # User in Org 2
        self.user_org2 = User.objects.create_user(
            email='manager@beta.com', password='Password123!', status='active'
        )
        self.emp_org2 = Employee.objects.create(
            user=self.user_org2, employee_code='EMP-B1',
            organization=self.org2, branch=self.branch2
        )
        UserRole.objects.create(
            user=self.user_org2, role=self.role_org2, scope=ScopeChoices.ORGANIZATION
        )

        # Superuser scoped to Org 1
        self.super_org1 = User.objects.create_user(
            email='super@alpha.com', password='Password123!',
            status='active', is_superuser=True
        )
        self.emp_super_org1 = Employee.objects.create(
            user=self.super_org1, employee_code='SUP-A1',
            organization=self.org1, branch=self.branch1
        )
        UserRole.objects.create(
            user=self.super_org1, role=self.role_org1, scope=ScopeChoices.ORGANIZATION
        )

        # Unassigned user with direct permission grants but NO organization context
        self.user_no_org = User.objects.create_user(
            email='headless@nowhere.com', password='Password123!', status='active'
        )
        UserPermissionGrant.objects.create(
            user=self.user_no_org, permission=self.perm_shift_view, scope=ScopeChoices.ORGANIZATION
        )
        UserPermissionGrant.objects.create(
            user=self.user_no_org, permission=self.perm_shift_manage, scope=ScopeChoices.ORGANIZATION
        )

        # Seed BreakTypes for both organizations
        self.bt_org1 = BreakType.objects.create(
            organization=self.org1, name='Org1 Tea Break', max_duration_minutes=15
        )
        self.bt_org2 = BreakType.objects.create(
            organization=self.org2, name='Org2 Lunch Break', max_duration_minutes=45
        )

    def test_list_isolates_break_types_by_organization(self):
        """User in Org 1 only lists Org 1 break types, never Org 2."""
        self.client.force_authenticate(user=self.user_org1)
        res = self.client.get(reverse('break-type-list'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        names = [item['name'] for item in res.data]
        self.assertIn('Org1 Tea Break', names)
        self.assertNotIn('Org2 Lunch Break', names)

    def test_superuser_list_is_scoped_without_bypass(self):
        """Superuser in Org 1 cannot see Org 2 break types (no is_superuser bypass)."""
        self.client.force_authenticate(user=self.super_org1)
        res = self.client.get(reverse('break-type-list'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        names = [item['name'] for item in res.data]
        self.assertIn('Org1 Tea Break', names)
        self.assertNotIn('Org2 Lunch Break', names, "Superuser must not bypass tenant isolation.")

    def test_unassigned_user_list_denied_safely(self):
        """User with no resolvable organization is denied with 403."""
        self.client.force_authenticate(user=self.user_no_org)
        res = self.client.get(reverse('break-type-list'))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Cannot determine organization context', res.data['detail'])

    def test_retrieve_cross_organization_returns_404(self):
        """User in Org 1 attempting to retrieve Org 2 break type receives 404."""
        self.client.force_authenticate(user=self.user_org1)
        # Own break type
        res_own = self.client.get(reverse('break-type-detail', args=[self.bt_org1.id]))
        self.assertEqual(res_own.status_code, status.HTTP_200_OK)

        # Cross-tenant break type
        res_cross = self.client.get(reverse('break-type-detail', args=[self.bt_org2.id]))
        self.assertEqual(res_cross.status_code, status.HTTP_404_NOT_FOUND)

    def test_superuser_retrieve_cross_organization_returns_404(self):
        """Superuser in Org 1 attempting to retrieve Org 2 break type receives 404."""
        self.client.force_authenticate(user=self.super_org1)
        res_cross = self.client.get(reverse('break-type-detail', args=[self.bt_org2.id]))
        self.assertEqual(res_cross.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_enforces_user_organization(self):
        """Creating a break type binds it to the caller's organization regardless of payload."""
        self.client.force_authenticate(user=self.user_org1)
        payload = {
            'name': 'Org1 Coffee Break',
            'max_duration_minutes': 20,
            'organization': self.org2.id,  # Caller attempts to spoof tenant
        }
        res = self.client.post(reverse('break-type-list'), payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        created_bt = BreakType.objects.get(name='Org1 Coffee Break')
        self.assertEqual(created_bt.organization_id, self.org1.id)

    def test_unassigned_user_create_denied_safely(self):
        """User with no resolvable organization cannot create break types."""
        self.client.force_authenticate(user=self.user_no_org)
        payload = {'name': 'Orphan Break'}
        res = self.client.post(reverse('break-type-list'), payload)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_cross_organization_returns_404(self):
        """Attempting to update another organization's break type returns 404."""
        self.client.force_authenticate(user=self.user_org1)

        # Attempt to patch Org 2 break type
        res_cross = self.client.patch(
            reverse('break-type-detail', args=[self.bt_org2.id]),
            {'name': 'Tampered Lunch'}
        )
        self.assertEqual(res_cross.status_code, status.HTTP_404_NOT_FOUND)

        # Verify record in DB is unchanged
        self.bt_org2.refresh_from_db()
        self.assertEqual(self.bt_org2.name, 'Org2 Lunch Break')

    def test_superuser_update_cross_organization_returns_404(self):
        """Superuser cannot update another organization's break type."""
        self.client.force_authenticate(user=self.super_org1)
        res_cross = self.client.patch(
            reverse('break-type-detail', args=[self.bt_org2.id]),
            {'name': 'Super Tampered'}
        )
        self.assertEqual(res_cross.status_code, status.HTTP_404_NOT_FOUND)
        self.bt_org2.refresh_from_db()
        self.assertEqual(self.bt_org2.name, 'Org2 Lunch Break')


class LocationAlertTenantIsolationTests(TestCase):
    """
    Phase 1B Regression Suite:
    Verify that LocationAlertView scopes alerts strictly to authorized branches
    and organizations, eliminating cross-tenant visibility for all callers.
    """

    def setUp(self):
        self.client = APIClient()
        self.today = date.today()
        now_dt = timezone.now()

        # Two organizations
        self.org1 = Organization.objects.create(name='Geo Tenant 1')
        self.org2 = Organization.objects.create(name='Geo Tenant 2')

        # Org 1 Branches
        # Branch 1: Bangalore center
        self.branch1 = Branch.objects.create(
            organization=self.org1, name='Geo Branch Alpha',
            latitude='12.971600', longitude='77.594600', radius=100.0
        )
        # Branch 2: Second branch in Org 1 with no out-of-fence punch
        self.branch2 = Branch.objects.create(
            organization=self.org1, name='Geo Branch Alpha-North',
            latitude='13.030000', longitude='77.560000', radius=100.0
        )

        # Org 2 Branch: Mumbai center
        self.branch3 = Branch.objects.create(
            organization=self.org2, name='Geo Branch Beta',
            latitude='19.076000', longitude='72.877700', radius=100.0
        )

        # Permission
        self.perm_view_all = Permission.objects.get(codename='attendance.view_all')

        # Roles
        self.role_org1 = Role.objects.create(organization=self.org1, name='Geo Admin Org1')
        RolePermission.objects.create(role=self.role_org1, permission=self.perm_view_all)

        self.role_branch2 = Role.objects.create(organization=self.org1, name='Branch 2 Geo Admin')
        RolePermission.objects.create(role=self.role_branch2, permission=self.perm_view_all)

        self.role_org2 = Role.objects.create(organization=self.org2, name='Geo Admin Org2')
        RolePermission.objects.create(role=self.role_org2, permission=self.perm_view_all)

        # Users and Employees
        # Admin Org 1 (Org scope)
        self.user_org1 = User.objects.create_user(
            email='geoadmin@org1.com', password='Password123!', status='active'
        )
        self.emp_admin1 = Employee.objects.create(
            user=self.user_org1, employee_code='GEO-ADM1',
            organization=self.org1, branch=self.branch1
        )
        UserRole.objects.create(
            user=self.user_org1, role=self.role_org1, scope=ScopeChoices.ORGANIZATION
        )

        # Superuser scoped to Org 1
        self.super_org1 = User.objects.create_user(
            email='supergeo@org1.com', password='Password123!',
            status='active', is_superuser=True
        )
        self.emp_super = Employee.objects.create(
            user=self.super_org1, employee_code='GEO-SUP',
            organization=self.org1, branch=self.branch1
        )
        UserRole.objects.create(
            user=self.super_org1, role=self.role_org1, scope=ScopeChoices.ORGANIZATION
        )

        # Admin for Branch 2 only
        self.user_branch2 = User.objects.create_user(
            email='branch2admin@org1.com', password='Password123!', status='active'
        )
        self.emp_branch2 = Employee.objects.create(
            user=self.user_branch2, employee_code='GEO-B2ADM',
            organization=self.org1, branch=self.branch2
        )
        UserRole.objects.create(
            user=self.user_branch2, role=self.role_branch2,
            scope=ScopeChoices.BRANCH, branch=self.branch2
        )

        # Regular employee in Org 1 (no attendance.view_all)
        self.user_regular = User.objects.create_user(
            email='regular@org1.com', password='Password123!', status='active'
        )
        self.emp_regular = Employee.objects.create(
            user=self.user_regular, employee_code='GEO-REG',
            organization=self.org1, branch=self.branch1
        )

        # Employee in Org 2
        self.user_org2 = User.objects.create_user(
            email='emp@org2.com', password='Password123!', status='active'
        )
        self.emp_org2 = Employee.objects.create(
            user=self.user_org2, employee_code='GEO-BETA',
            organization=self.org2, branch=self.branch3
        )

        # Attendance records with out-of-fence coordinates (> 100m)
        # Org 1: Punch in ~1.5km away from branch1
        self.att_org1 = Attendance.objects.create(
            employee=self.emp_admin1,
            date=self.today,
            check_in=now_dt,
            check_in_latitude='12.985000',
            check_in_longitude='77.605000',
            status='present'
        )

        # Org 2: Punch in ~2km away from branch3
        self.att_org2 = Attendance.objects.create(
            employee=self.emp_org2,
            date=self.today,
            check_in=now_dt,
            check_in_latitude='19.095000',
            check_in_longitude='72.895000',
            status='present'
        )

    def test_org1_admin_sees_only_org1_location_alerts(self):
        """Org 1 admin sees out-of-fence alerts for Org 1 only."""
        self.client.force_authenticate(user=self.user_org1)
        res = self.client.get(reverse('location-alerts'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        attendance_ids = [a['attendance_id'] for a in res.data['results']]
        self.assertIn(self.att_org1.id, attendance_ids)
        self.assertNotIn(self.att_org2.id, attendance_ids, "Org 2 alert must not be exposed.")
        self.assertEqual(res.data['count'], 1)

    def test_superuser_location_alerts_scoped_to_own_organization(self):
        """Superuser in Org 1 does NOT see cross-tenant location alerts (bypass removed)."""
        self.client.force_authenticate(user=self.super_org1)
        res = self.client.get(reverse('location-alerts'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        attendance_ids = [a['attendance_id'] for a in res.data['results']]
        self.assertIn(self.att_org1.id, attendance_ids)
        self.assertNotIn(self.att_org2.id, attendance_ids, "Superuser must be tenant-scoped.")
        self.assertEqual(res.data['count'], 1)

    def test_branch_scoped_admin_sees_only_assigned_branch(self):
        """Admin scoped only to Branch 2 sees 0 alerts when violation is in Branch 1."""
        self.client.force_authenticate(user=self.user_branch2)
        res = self.client.get(reverse('location-alerts'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 0)
        self.assertEqual(len(res.data['results']), 0)

    def test_unauthorized_user_forbidden(self):
        """User without attendance.view_all permission receives 403."""
        self.client.force_authenticate(user=self.user_regular)
        res = self.client.get(reverse('location-alerts'))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
