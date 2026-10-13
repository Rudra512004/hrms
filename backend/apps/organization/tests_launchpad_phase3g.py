import hashlib
import json
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.organization.models import (
    Organization,
    Branch,
    Department,
    Designation,
    WorkingCalendar,
    AttendancePolicy,
    OrganizationOnboarding,
    OnboardingStatus,
    TenantBrandingAndConfig,
    OrganizationInvitation,
    InvitationStatus,
)
from apps.attendance.models import Shift
from apps.authorization.models import Role, UserRole, Permission, RolePermission, ScopeChoices
from apps.accounts.models import TenantOwnerRegistration, UserStatus
from apps.audit.models import AuditLog
from apps.organization.services import (
    OrganizationReadinessService,
    OrganizationOnboardingService,
)
from apps.authorization.services import AuthorizationService

User = get_user_model()


class OrganizationLaunchpadAndLiveTransitionTests(TestCase):
    """
    Phase 3G: Organization Launchpad and Live Transition Orchestration.
    Validates:
    - Incomplete onboarding blocking activation
    - Ready organization evaluating readiness (leave types non-blocking)
    - Unauthorized activation rejection (tenant boundary protection, no global is_superuser shortcut)
    - Successful activation transitioning organization to active and onboarding to completed
    - Repeated activation requests are idempotent (HTTP 200)
    - Invalid lifecycle transitions (e.g., abandoned)
    - Initial administrator self-assignment and invitation acceptance
    - Branding continuity across activation, organization switching, and tenant isolation
    - Audit log generation for activation and completion
    """

    def setUp(self):
        self.client = APIClient()

        # Tenant Owner 1
        self.owner = User.objects.create_user(
            email='owner1@tenantalpha.com',
            password='Password123!',
            first_name='Alpha',
            last_name='Owner',
            status=UserStatus.ACTIVE,
        )
        self.registration = TenantOwnerRegistration.objects.create(
            user=self.owner,
            verified_at=timezone.now(),
        )

        # Tenant Owner 2 (Different tenant)
        self.owner2 = User.objects.create_user(
            email='owner2@tenantbeta.com',
            password='Password123!',
            first_name='Beta',
            last_name='Owner',
            status=UserStatus.ACTIVE,
        )
        self.registration2 = TenantOwnerRegistration.objects.create(
            user=self.owner2,
            verified_at=timezone.now(),
        )

        # Global Superuser (Platform Admin without tenant roles)
        self.platform_admin = User.objects.create_superuser(
            email='platform.admin@beyondsure.com',
            password='AdminPassword123!',
            first_name='Platform',
            last_name='Admin',
        )

        # Resolve or create canonical permissions needed for super-admin
        self.perm1, _ = Permission.objects.get_or_create(
            codename='organization.manage',
            defaults={'name': 'Manage Org', 'resource': 'organization', 'action': 'manage', 'is_active': True}
        )
        self.perm2, _ = Permission.objects.get_or_create(
            codename='organization.view',
            defaults={'name': 'View Org', 'resource': 'organization', 'action': 'view', 'is_active': True}
        )
        self.perm3, _ = Permission.objects.get_or_create(
            codename='branding.manage',
            defaults={'name': 'Manage Branding', 'resource': 'branding', 'action': 'manage', 'is_active': True}
        )
        self.perm4, _ = Permission.objects.get_or_create(
            codename='attendance.view_all',
            defaults={'name': 'View Attendance', 'resource': 'attendance', 'action': 'view_all', 'is_active': True}
        )

    def _setup_organization_stages(self, org, stages_up_to=6, invite_admin=False):
        """Helper to create real persisted database entities up to the specified stage."""
        onboarding, _ = OrganizationOnboarding.objects.get_or_create(
            organization=org,
            defaults={
                'owner': self.owner,
                'status': OnboardingStatus.IN_PROGRESS,
                'current_stage': min(7, stages_up_to + 1),
                'completed_stages': list(range(1, stages_up_to + 1)),
            }
        )

        branch = None
        if stages_up_to >= 2:
            branch = Branch.objects.create(
                organization=org,
                name='Alpha HQ',
                address='100 Tech Park',
                radius=100,
                is_active=True,
            )

        if stages_up_to >= 3 and branch:
            dept = Department.objects.create(branch=branch, name='Engineering', is_active=True)
            desig = Designation.objects.create(organization=org, name='Lead Engineer', is_active=True)

        if stages_up_to >= 4 and branch:
            wc, _ = WorkingCalendar.objects.get_or_create(branch=branch)
            wc.work_days = '0,1,2,3,4'
            wc.save()

        if stages_up_to >= 5 and branch:
            Shift.objects.create(
                branch=branch,
                name='General Day Shift',
                start_time='09:00:00',
                end_time='18:00:00',
                work_days='0,1,2,3,4',
                is_active=True,
            )
            ap, _ = AttendancePolicy.objects.get_or_create(branch=branch)
            ap.is_office_gps_enabled = True
            ap.save()

        if stages_up_to >= 6:
            role = Role.objects.create(
                organization=org,
                name='Super Admin',
                slug='super-admin',
                is_active=True,
                is_system=True,
            )
            RolePermission.objects.create(role=role, permission=self.perm1)
            RolePermission.objects.create(role=role, permission=self.perm2)
            RolePermission.objects.create(role=role, permission=self.perm3)

            if not invite_admin:
                # Self assignment
                UserRole.objects.create(
                    user=self.owner,
                    role=role,
                    scope=ScopeChoices.ORGANIZATION,
                    assigned_by=self.owner,
                    is_revoked=False,
                )
            else:
                # Invited administrator
                OrganizationInvitation.objects.create(
                    organization=org,
                    email='invited.admin@tenantalpha.com',
                    first_name='Invited',
                    last_name='Admin',
                    role=role,
                    token_hash=hashlib.sha256(b'secret_token_123').hexdigest(),
                    status=InvitationStatus.PENDING,
                    invited_by=self.owner,
                    expires_at=timezone.now() + timedelta(days=7),
                )

        onboarding.completed_stages = list(range(1, stages_up_to + 1))
        onboarding.current_stage = min(7, stages_up_to + 1)
        onboarding.save()
        return onboarding

    def test_incomplete_onboarding_blocks_activation(self):
        """Activation must be rejected if stages 1 through 6 are not all completed."""
        org = Organization.objects.create(name='Incomplete Org', code='INC', status='active')
        onboarding = self._setup_organization_stages(org, stages_up_to=3)

        self.client.force_authenticate(user=self.owner)
        resp = self.client.post('/api/v1/organization/wizard/complete/', {'org_id': org.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Missing preceding stages', str(resp.data))

        # Organization must remain pending/onboarding
        onboarding.refresh_from_db()
        self.assertNotEqual(onboarding.status, OnboardingStatus.COMPLETED)

    def test_missing_database_prerequisites_blocks_activation(self):
        """Even if completed_stages claims 1..6, direct DB re-validation must catch missing assets."""
        org = Organization.objects.create(name='Fake Progress Org', code='FAK', status='active')
        onboarding = self._setup_organization_stages(org, stages_up_to=6)

        # Delete the shift out-of-band to simulate corrupted/incomplete state
        Shift.objects.filter(branch__organization=org).delete()

        self.client.force_authenticate(user=self.owner)
        resp = self.client.post('/api/v1/organization/wizard/complete/', {'org_id': org.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Stage 5 incomplete', str(resp.data))

    def test_leave_type_non_blocking_readiness_evaluation(self):
        """Leave types must NOT be a mandatory onboarding blocker; readiness score reflects 100% when stages 1-6 are met."""
        org = Organization.objects.create(name='Alpha Ready Org', code='ARO', status='active')
        onboarding = self._setup_organization_stages(org, stages_up_to=6)

        readiness = OrganizationReadinessService.assess(org)
        self.assertEqual(readiness['score'], 100)

        # Verify leave_types is present as recommended (required=False)
        leave_check = next(c for c in readiness['checks'] if c['key'] == 'leave_types')
        self.assertFalse(leave_check['required'])
        self.assertEqual(leave_check['state'], 'recommended')

        # Verify shifts is required (required=True) and ready
        shift_check = next(c for c in readiness['checks'] if c['key'] == 'shifts')
        self.assertTrue(shift_check['required'])
        self.assertEqual(shift_check['state'], 'ready')

    def test_successful_activation_and_transition(self):
        """Completing stage 7 activates the organization, marks onboarding completed, and logs audit events."""
        org = Organization.objects.create(name='Live Alpha Org', code='LAO', status='active')
        onboarding = self._setup_organization_stages(org, stages_up_to=6)

        self.client.force_authenticate(user=self.owner)
        resp = self.client.post('/api/v1/organization/wizard/complete/', {'org_id': org.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], OnboardingStatus.COMPLETED)
        self.assertEqual(resp.data['readiness_score'], 100)
        self.assertEqual(resp.data['redirect_url'], '/dashboard')

        onboarding.refresh_from_db()
        self.assertEqual(onboarding.status, OnboardingStatus.COMPLETED)
        self.assertTrue(onboarding.is_complete)
        self.assertIsNotNone(onboarding.completed_at)
        self.assertEqual(onboarding.completed_stages, [1, 2, 3, 4, 5, 6, 7])

        org.refresh_from_db()
        self.assertEqual(org.status, 'active')

        # Check audit events
        activated_log = AuditLog.objects.filter(action='organization_activated', organization=org).exists()
        completed_log = AuditLog.objects.filter(action='organization_onboarding_completed', organization=org).exists()
        self.assertTrue(activated_log)
        self.assertTrue(completed_log)

    def test_repeated_activation_requests_are_idempotent(self):
        """Submitting multiple completion requests for an already completed organization succeeds idempotently with 200 OK."""
        org = Organization.objects.create(name='Idempotent Org', code='IDM', status='active')
        onboarding = self._setup_organization_stages(org, stages_up_to=6)

        self.client.force_authenticate(user=self.owner)
        resp1 = self.client.post('/api/v1/organization/wizard/complete/', {'org_id': org.id}, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        # Duplicate activation call
        resp2 = self.client.post('/api/v1/organization/wizard/complete/', {'org_id': org.id}, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['status'], OnboardingStatus.COMPLETED)
        self.assertEqual(resp2.data['organization_id'], org.id)

    def test_invalid_lifecycle_transition_abandoned_rejected(self):
        """Cannot activate an onboarding session that was marked abandoned."""
        org = Organization.objects.create(name='Abandoned Org', code='ABN', status='active')
        onboarding = self._setup_organization_stages(org, stages_up_to=6)
        onboarding.status = OnboardingStatus.ABANDONED
        onboarding.save()

        self.client.force_authenticate(user=self.owner)
        resp = self.client.post('/api/v1/organization/wizard/complete/', {'org_id': org.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('abandoned', str(resp.data))

    def test_unauthorized_activation_blocked(self):
        """A user from another tenant cannot activate another organization (403 PermissionDenied)."""
        org = Organization.objects.create(name='Protected Org', code='PRT', status='active')
        self._setup_organization_stages(org, stages_up_to=6)

        # Authenticate as owner2 (Tenant Beta)
        self.client.force_authenticate(user=self.owner2)
        resp = self.client.post('/api/v1/organization/wizard/complete/', {'org_id': org.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_superuser_cannot_bypass_tenant_boundary_without_scope(self):
        """A global Django superuser cannot activate an organization unless holding tenant-scoped admin or owner rights."""
        org = Organization.objects.create(name='Tenant Boundary Org', code='TBO', status='active')
        self._setup_organization_stages(org, stages_up_to=6)

        # Platform admin without role in this tenant
        self.client.force_authenticate(user=self.platform_admin)
        resp = self.client.post('/api/v1/organization/wizard/complete/', {'org_id': org.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_initial_administrator_via_invitation_satisfies_activation_prerequisite(self):
        """Stage 6 completed via invitation satisfies Stage 7 activation prerequisite even before invitee accepts."""
        org = Organization.objects.create(name='Invited Admin Org', code='IAO', status='active')
        onboarding = self._setup_organization_stages(org, stages_up_to=6, invite_admin=True)

        self.client.force_authenticate(user=self.owner)
        resp = self.client.post('/api/v1/organization/wizard/complete/', {'org_id': org.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], OnboardingStatus.COMPLETED)

    def test_invitation_acceptance_activates_admin_with_branding_continuity(self):
        """When an invited administrator accepts, they receive the scoped Super Admin role and inherit org branding."""
        org = Organization.objects.create(name='Branded Org', code='BRO', status='active')
        branding, _ = TenantBrandingAndConfig.objects.get_or_create(organization=org)
        branding.branding_mode = 'custom'
        branding.primary_color = '#2563eb'
        branding.secondary_color = '#475569'
        branding.save()
        onboarding = self._setup_organization_stages(org, stages_up_to=6, invite_admin=True)

        # Activate the organization
        self.client.force_authenticate(user=self.owner)
        resp = self.client.post('/api/v1/organization/wizard/complete/', {'org_id': org.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Invite acceptance by new user
        invitation = OrganizationInvitation.objects.get(organization=org, status=InvitationStatus.PENDING)
        raw_token = 'secret_token_123'

        accepted_invitation, new_admin = OrganizationOnboardingService.accept_invitation(
            raw_token=raw_token,
            password='NewAdminPassword123!',
            first_name='Invited',
            last_name='Admin',
        )
        self.assertEqual(accepted_invitation.status, InvitationStatus.ACCEPTED)
        self.assertEqual(new_admin.status, UserStatus.ACTIVE)

        # Verify new admin has organization-scoped Super Admin role
        has_role = UserRole.objects.filter(
            user=new_admin,
            role__organization=org,
            role__slug='super-admin',
            is_revoked=False,
        ).exists()
        self.assertTrue(has_role)

        # Verify AuthorizationService resolves this organization as primary for the new admin
        primary_org = AuthorizationService.get_primary_organization(new_admin)
        self.assertEqual(primary_org.id, org.id)

        # Verify branding continuity: new admin queries branding and receives tenant's custom theme
        self.client.force_authenticate(user=new_admin)
        resp_branding = self.client.get(f'/api/v1/organization/organizations/{org.id}/branding/')
        self.assertEqual(resp_branding.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_branding.data['primary_color'], '#2563eb')
        self.assertEqual(resp_branding.data['branding_mode'], 'custom')

    def test_branding_continuity_across_activation(self):
        """Custom branding applied before/during onboarding remains identical and intact after activation."""
        org = Organization.objects.create(name='Theme Continuity Org', code='TCO', status='active')
        branding, _ = TenantBrandingAndConfig.objects.get_or_create(organization=org)
        branding.branding_mode = 'custom'
        branding.primary_color = '#0d9488'
        branding.sidebar_bg_color = '#134e4a'
        branding.logo_url = 'https://example.com/logo.png'
        branding.save()
        self._setup_organization_stages(org, stages_up_to=6)

        # Complete activation
        self.client.force_authenticate(user=self.owner)
        resp = self.client.post('/api/v1/organization/wizard/complete/', {'org_id': org.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Query branding post-activation
        resp_branding = self.client.get(f'/api/v1/organization/organizations/{org.id}/branding/')
        self.assertEqual(resp_branding.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_branding.data['primary_color'], '#0d9488')
        self.assertEqual(resp_branding.data['sidebar_bg_color'], '#134e4a')
        self.assertEqual(resp_branding.data['logo_url'], 'https://example.com/logo.png')

    def test_tenant_isolation_prevents_cross_tenant_branding_leakage(self):
        """Tenant A cannot read or mutate Tenant B's branding configuration."""
        org_a = Organization.objects.create(name='Tenant A Org', code='TAO', status='active')
        branding_a, _ = TenantBrandingAndConfig.objects.get_or_create(organization=org_a)
        branding_a.branding_mode = 'custom'
        branding_a.primary_color = '#ff0000'
        branding_a.save()
        self._setup_organization_stages(org_a, stages_up_to=6)

        org_b = Organization.objects.create(name='Tenant B Org', code='TBO', status='active')
        branding_b, _ = TenantBrandingAndConfig.objects.get_or_create(organization=org_b)
        branding_b.branding_mode = 'custom'
        branding_b.primary_color = '#00ff00'
        branding_b.save()
        # Setup org_b with owner2
        onboarding_b = OrganizationOnboarding.objects.create(
            organization=org_b,
            owner=self.owner2,
            status=OnboardingStatus.IN_PROGRESS,
            current_stage=2,
            completed_stages=[1],
        )

        # Authenticate as owner2 and attempt to PATCH org_a branding
        self.client.force_authenticate(user=self.owner2)
        resp_leak = self.client.patch(
            f'/api/v1/organization/organizations/{org_a.id}/branding/',
            {'primary_color': '#0000ff'},
            format='json'
        )
        # Must be rejected (403 or 404 because org_a is outside owner2's tenant scope)
        self.assertIn(resp_leak.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

        # Verify org_a's color did not change
        branding_a = TenantBrandingAndConfig.objects.get(organization=org_a)
        self.assertEqual(branding_a.primary_color, '#ff0000')
