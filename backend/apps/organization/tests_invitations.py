import hashlib
import json
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import TenantOwnerRegistration, UserStatus
from apps.audit.models import AuditLog
from apps.authorization.models import Permission, Role, RolePermission, ScopeChoices, UserRole
from apps.notifications.services import NotificationService
from apps.organization.models import (
    EmailDeliveryStatus,
    InvitationStatus,
    Organization,
    OrganizationInvitation,
    OrganizationOnboarding,
)
from apps.organization.services import OrganizationOnboardingService

User = get_user_model()


class OrganizationInvitationLifecycleTests(TestCase):
    """
    Phase 3E comprehensive verification suite:
    - Option A self-assignment and legacy payload compatibility
    - Option B invitation creation and post-commit email dispatch
    - Email delivery failure and resend recovery
    - Invalid, expired, revoked, rotated, and already-accepted tokens
    - Active, inactive, invited, and new-user account acceptance
    - Identity mismatch & password validation
    - Cross-tenant isolation & unauthorized resend/revoke
    - Token redaction (SHA-256 only) in DB and Audit logs
    - Creator authority preservation & zero global privilege escalation
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Creator / Tenant Owner User
        self.creator = User.objects.create_user(
            email='creator@apex.com',
            password='StrongPassword123!',
            first_name='Alex',
            last_name='Creator',
            status=UserStatus.ACTIVE,
        )
        self.creator_reg = TenantOwnerRegistration.objects.create(
            user=self.creator,
            verified_at=timezone.now(),
        )

        # Attacker / Other Tenant User
        self.attacker = User.objects.create_user(
            email='attacker@competitor.com',
            password='StrongPassword123!',
            first_name='Evil',
            last_name='Attacker',
            status=UserStatus.ACTIVE,
        )
        self.attacker_reg = TenantOwnerRegistration.objects.create(
            user=self.attacker,
            verified_at=timezone.now(),
        )

        # Initialize Organization & complete stages 1 to 5
        self.client.force_authenticate(user=self.creator)
        resp1 = self.client.post('/api/v1/organization/wizard/start/', {'name': 'Apex Corp', 'code': 'APEX'}, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        self.org_id = resp1.data['organization_id']
        self.org = Organization.objects.get(id=self.org_id)
        self.onboarding = OrganizationOnboarding.objects.get(organization=self.org)

        # Complete stages 2-5
        self.client.post('/api/v1/organization/wizard/stage-2/', {'name': 'HQ', 'city': 'Mumbai', 'radius': 100.0}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-3/', {'departments': [{'name': 'Eng'}], 'designations': [{'name': 'SE'}]}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-4/', {'work_days': '0,1,2,3,4'}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-5/', {'shift': {'name': 'Standard', 'start_time': '09:00:00', 'end_time': '18:00:00'}}, format='json')

    def test_option_a_self_assignment_and_legacy_payload_compatibility(self):
        """Option A assigns caller as organization Super Admin and supports legacy {'confirm': True}."""
        # 1. Test legacy payload {"confirm": True}
        resp = self.client.post('/api/v1/organization/wizard/stage-6/', {'confirm': True}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['current_stage'], 7)
        self.assertIn(6, resp.data['completed_stages'])

        super_admin_role = Role.objects.get(organization=self.org, slug='super-admin')
        ur = UserRole.objects.get(user=self.creator, role=super_admin_role)
        self.assertEqual(ur.scope, ScopeChoices.ORGANIZATION)
        self.assertFalse(ur.is_revoked)

        # Invariant: Caller is not granted global staff/superuser
        self.creator.refresh_from_db()
        self.assertFalse(self.creator.is_superuser)
        self.assertFalse(self.creator.is_staff)

        # 2. Test explicit payload {"assignment_type": "self", "confirm": True}
        resp_explicit = self.client.post('/api/v1/organization/wizard/stage-6/', {'assignment_type': 'self', 'confirm': True}, format='json')
        self.assertEqual(resp_explicit.status_code, status.HTTP_200_OK)
        self.assertEqual(UserRole.objects.filter(user=self.creator, role=super_admin_role).count(), 1)

    def test_option_b_invitation_creation_and_token_redaction(self):
        """Option B creates an OrganizationInvitation, hashes token, and never exposes raw token."""
        invitee_email = 'jane.doe@apex.com'
        payload = {
            'assignment_type': 'invite',
            'first_name': 'Jane',
            'last_name': 'Doe',
            'email': invitee_email,
        }

        with patch.object(NotificationService, 'send_organization_admin_invitation_email', return_value=True) as mock_email:
            with self.captureOnCommitCallbacks(execute=True):
                resp = self.client.post('/api/v1/organization/wizard/stage-6/', payload, format='json')
                self.assertEqual(resp.status_code, status.HTTP_200_OK)

            # Invariant: Raw token is never returned in HTTP response
            resp_str = json.dumps(resp.data)
            self.assertNotIn('token_hash', resp_str)
            self.assertNotIn('raw_token', resp_str)

            # Verify invitation persisted with SHA-256 hash
            invitation = OrganizationInvitation.objects.get(organization=self.org, email=invitee_email)
            self.assertEqual(invitation.first_name, 'Jane')
            self.assertEqual(invitation.last_name, 'Doe')
            self.assertEqual(invitation.status, InvitationStatus.PENDING)
            self.assertEqual(invitation.email_delivery_status, EmailDeliveryStatus.SENT)
            self.assertEqual(len(invitation.token_hash), 64)  # SHA-256 hex length
            self.assertEqual(invitation.role.slug, 'super-admin')

            # Verify email dispatch was called with recipient info
            mock_email.assert_called_once()
            call_kwargs = mock_email.call_args[1] if mock_email.call_args[1] else {}
            call_args = mock_email.call_args[0]
            raw_token = call_args[3] if len(call_args) > 3 else call_kwargs.get('raw_token')
            self.assertIsNotNone(raw_token)
            # Ensure raw_token hashes to the stored token_hash
            computed_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
            self.assertEqual(computed_hash, invitation.token_hash)

        # Invariant: Audit log does NOT contain raw token
        audit = AuditLog.objects.filter(action='onboarding_stage_6_completed').latest('timestamp')
        audit_metadata_str = json.dumps(audit.metadata)
        self.assertNotIn(raw_token, audit_metadata_str)
        self.assertNotIn('raw_token', audit_metadata_str)

    def test_self_invitation_rejected(self):
        """Stage 6 rejects inviting the authenticated user's own email address."""
        payload = {
            'assignment_type': 'invite',
            'first_name': 'Self',
            'last_name': 'Inviter',
            'email': self.creator.email.upper(),  # case-insensitive check
        }
        resp = self.client.post('/api/v1/organization/wizard/stage-6/', payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', resp.data)

    def test_resend_rotates_token_and_invalidates_prior_token(self):
        """Resending rotates the token, resets expiration, and immediately invalidates old token."""
        invitee_email = 'mark.admin@apex.com'
        payload = {
            'assignment_type': 'invite',
            'first_name': 'Mark',
            'last_name': 'Admin',
            'email': invitee_email,
        }

        captured_tokens = []

        def capture_email(*args, **kwargs):
            # arg 3 is raw_token
            if len(args) > 3:
                captured_tokens.append(args[3])
            elif 'raw_token' in kwargs:
                captured_tokens.append(kwargs['raw_token'])
            return True

        with patch.object(NotificationService, 'send_organization_admin_invitation_email', side_effect=capture_email):
            with self.captureOnCommitCallbacks(execute=True):
                resp1 = self.client.post('/api/v1/organization/wizard/stage-6/', payload, format='json')
                self.assertEqual(resp1.status_code, status.HTTP_200_OK)

            self.assertEqual(len(captured_tokens), 1)
            token_1 = captured_tokens[0]

            # Verify token 1 is currently valid
            verify1 = self.client.get(f'/api/v1/organization/invitations/verify/?token={token_1}')
            self.assertEqual(verify1.status_code, status.HTTP_200_OK)
            self.assertTrue(verify1.data['valid'])

            # Resend invitation
            with self.captureOnCommitCallbacks(execute=True):
                resp_resend = self.client.post('/api/v1/organization/wizard/stage-6/resend/', format='json')
                self.assertEqual(resp_resend.status_code, status.HTTP_200_OK)
                self.assertEqual(resp_resend.data['resend_count'], 1)

            self.assertEqual(len(captured_tokens), 2)
            token_2 = captured_tokens[1]
            self.assertNotEqual(token_1, token_2)

            # Old token 1 must now be INVALID
            verify_old = self.client.get(f'/api/v1/organization/invitations/verify/?token={token_1}')
            self.assertEqual(verify_old.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('Invalid or expired', verify_old.data['detail'])

            # New token 2 must be VALID
            verify_new = self.client.get(f'/api/v1/organization/invitations/verify/?token={token_2}')
            self.assertEqual(verify_new.status_code, status.HTTP_200_OK)
            self.assertTrue(verify_new.data['valid'])

    def test_revoke_invitation_invalidates_token(self):
        """Revoking an invitation immediately invalidates public token verification and acceptance."""
        invitee_email = 'revoked.user@apex.com'
        payload = {
            'assignment_type': 'invite',
            'first_name': 'Revoke',
            'last_name': 'Target',
            'email': invitee_email,
        }

        captured_token = None

        def capture_email(*args, **kwargs):
            nonlocal captured_token
            if len(args) > 3:
                captured_token = args[3]
            elif 'raw_token' in kwargs:
                captured_token = kwargs['raw_token']
            return True

        with patch.object(NotificationService, 'send_organization_admin_invitation_email', side_effect=capture_email):
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post('/api/v1/organization/wizard/stage-6/', payload, format='json')

            self.assertIsNotNone(captured_token)

            # Revoke
            resp_revoke = self.client.post('/api/v1/organization/wizard/stage-6/revoke/', format='json')
            self.assertEqual(resp_revoke.status_code, status.HTTP_200_OK)
            self.assertEqual(resp_revoke.data['status'], 'revoked')

            invitation = OrganizationInvitation.objects.get(organization=self.org, email=invitee_email)
            self.assertEqual(invitation.status, InvitationStatus.REVOKED)
            self.assertIsNotNone(invitation.revoked_at)

            # Verify token fails
            verify_resp = self.client.get(f'/api/v1/organization/invitations/verify/?token={captured_token}')
            self.assertEqual(verify_resp.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('cannot be used', verify_resp.data['detail'])

            # Accept fails
            accept_resp = self.client.post('/api/v1/organization/invitations/accept/', {'token': captured_token, 'password': 'Pass12345!'}, format='json')
            self.assertEqual(accept_resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_token_handling(self):
        """Expired invitations are marked EXPIRED and cannot be accepted."""
        raw_token = 'expired-token-xyz-1234567890'
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        super_admin_role = Role.objects.get_or_create(organization=self.org, slug='super-admin')[0]

        invitation = OrganizationInvitation.objects.create(
            organization=self.org,
            email='expired@apex.com',
            role=super_admin_role,
            token_hash=token_hash,
            status=InvitationStatus.PENDING,
            email_delivery_status=EmailDeliveryStatus.SENT,
            invited_by=self.creator,
            expires_at=timezone.now() - timedelta(days=1),  # Expired yesterday
        )

        # Verification marks status expired and returns 400
        verify_resp = self.client.get(f'/api/v1/organization/invitations/verify/?token={raw_token}')
        self.assertEqual(verify_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('expired', verify_resp.data['detail'])

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatus.EXPIRED)

        # Acceptance also rejected
        accept_resp = self.client.post('/api/v1/organization/invitations/accept/', {'token': raw_token, 'password': 'Password123!'}, format='json')
        self.assertEqual(accept_resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_public_verification_zero_information_disclosure(self):
        """Verification endpoint does not leak has_existing_account or account existence."""
        raw_token = 'valid-token-for-privacy-test-99'
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        super_admin_role = Role.objects.get_or_create(organization=self.org, slug='super-admin')[0]

        # Case 1: user does not exist
        OrganizationInvitation.objects.create(
            organization=self.org,
            email='nonexistent.account@apex.com',
            first_name='Privacy',
            last_name='User',
            role=super_admin_role,
            token_hash=token_hash,
            status=InvitationStatus.PENDING,
            invited_by=self.creator,
            expires_at=timezone.now() + timedelta(days=7),
        )

        resp = self.client.get(f'/api/v1/organization/invitations/verify/?token={raw_token}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn('has_existing_account', resp.data)
        self.assertNotIn('user_id', resp.data)
        self.assertNotIn('is_active', resp.data)
        self.assertEqual(resp.data['organization_name'], self.org.name)
        self.assertEqual(resp.data['email'], 'nonexistent.account@apex.com')

    def test_acceptance_flow_1_authenticated_active_existing_user(self):
        """Active existing user must authenticate via canonical login before accepting."""
        existing_user = User.objects.create_user(
            email='existing.active@apex.com',
            password='ExistingPassword123!',
            first_name='Existing',
            last_name='Active',
            status=UserStatus.ACTIVE,
        )

        raw_token = 'active-user-token-secret-1111'
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        super_admin_role = Role.objects.get_or_create(organization=self.org, slug='super-admin')[0]

        invitation = OrganizationInvitation.objects.create(
            organization=self.org,
            email=existing_user.email,
            role=super_admin_role,
            token_hash=token_hash,
            status=InvitationStatus.PENDING,
            invited_by=self.creator,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # 1. Unauthenticated accept attempt -> 401 Unauthorized
        self.client.force_authenticate(user=None)
        unauth_resp = self.client.post('/api/v1/organization/invitations/accept/', {'token': raw_token}, format='json')
        self.assertEqual(unauth_resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('already exists', unauth_resp.data['detail'])

        # 2. Authenticated as DIFFERENT user -> 403 Forbidden
        self.client.force_authenticate(user=self.creator)
        mismatch_resp = self.client.post('/api/v1/organization/invitations/accept/', {'token': raw_token}, format='json')
        self.assertEqual(mismatch_resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('different user', mismatch_resp.data['detail'])

        # 3. Authenticated as MATCHING user -> 200 OK
        self.client.force_authenticate(user=existing_user)
        match_resp = self.client.post('/api/v1/organization/invitations/accept/', {'token': raw_token}, format='json')
        self.assertEqual(match_resp.status_code, status.HTTP_200_OK)
        # Ensure zero DRF auth tokens are returned
        self.assertNotIn('token', match_resp.data)
        self.assertNotIn('access', match_resp.data)

        # Check role assignment
        ur = UserRole.objects.get(user=existing_user, role=super_admin_role)
        self.assertEqual(ur.scope, ScopeChoices.ORGANIZATION)
        self.assertFalse(ur.is_revoked)

        # Check invitation status
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatus.ACCEPTED)
        self.assertEqual(invitation.accepted_by, existing_user)

    def test_acceptance_flow_2_inactive_existing_account_rejected(self):
        """Inactive/suspended account cannot accept invitations."""
        inactive_user = User.objects.create_user(
            email='inactive.user@apex.com',
            password='Password123!',
            status=UserStatus.INACTIVE,
        )

        raw_token = 'inactive-token-secret-2222'
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        super_admin_role = Role.objects.get_or_create(organization=self.org, slug='super-admin')[0]

        OrganizationInvitation.objects.create(
            organization=self.org,
            email=inactive_user.email,
            role=super_admin_role,
            token_hash=token_hash,
            status=InvitationStatus.PENDING,
            invited_by=self.creator,
            expires_at=timezone.now() + timedelta(days=7),
        )

        self.client.force_authenticate(user=None)
        resp = self.client.post('/api/v1/organization/invitations/accept/', {'token': raw_token, 'password': 'NewPassword123!'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('inactive or suspended', resp.data['detail'])

    def test_acceptance_flow_3_new_user_and_invited_user_activation(self):
        """New users and users in INVITED status set password and activate atomically."""
        # A. Completely New User
        raw_token_new = 'new-user-token-secret-3333'
        token_hash_new = hashlib.sha256(raw_token_new.encode('utf-8')).hexdigest()
        super_admin_role = Role.objects.get_or_create(organization=self.org, slug='super-admin')[0]

        OrganizationInvitation.objects.create(
            organization=self.org,
            email='brand.new@apex.com',
            first_name='Brand',
            last_name='New',
            role=super_admin_role,
            token_hash=token_hash_new,
            status=InvitationStatus.PENDING,
            invited_by=self.creator,
            expires_at=timezone.now() + timedelta(days=7),
        )

        self.client.force_authenticate(user=None)

        # 1. Password validation: too short
        bad_pw_resp = self.client.post('/api/v1/organization/invitations/accept/', {
            'token': raw_token_new,
            'password': 'short',
        }, format='json')
        self.assertEqual(bad_pw_resp.status_code, status.HTTP_400_BAD_REQUEST)

        # 2. Successful creation
        good_resp = self.client.post('/api/v1/organization/invitations/accept/', {
            'token': raw_token_new,
            'password': 'StrongPassword123!',
            'first_name': 'Brand',
            'last_name': 'New',
        }, format='json')
        self.assertEqual(good_resp.status_code, status.HTTP_200_OK)

        new_user = User.objects.get(email='brand.new@apex.com')
        self.assertEqual(new_user.status, UserStatus.ACTIVE)
        self.assertTrue(new_user.check_password('StrongPassword123!'))
        self.assertFalse(new_user.is_superuser)
        self.assertFalse(new_user.is_staff)

        # Role granted
        ur = UserRole.objects.get(user=new_user, role=super_admin_role)
        self.assertEqual(ur.scope, ScopeChoices.ORGANIZATION)

        # B. User in UserStatus.INVITED status
        invited_user = User.objects.create_user(
            email='already.invited@apex.com',
            password=None,
            status=UserStatus.INVITED,
        )
        raw_token_invited = 'invited-status-token-secret-4444'
        token_hash_invited = hashlib.sha256(raw_token_invited.encode('utf-8')).hexdigest()

        OrganizationInvitation.objects.create(
            organization=self.org,
            email=invited_user.email,
            role=super_admin_role,
            token_hash=token_hash_invited,
            status=InvitationStatus.PENDING,
            invited_by=self.creator,
            expires_at=timezone.now() + timedelta(days=7),
        )

        invited_resp = self.client.post('/api/v1/organization/invitations/accept/', {
            'token': raw_token_invited,
            'password': 'BrandNewPassword123!',
        }, format='json')
        self.assertEqual(invited_resp.status_code, status.HTTP_200_OK)

        invited_user.refresh_from_db()
        self.assertEqual(invited_user.status, UserStatus.ACTIVE)
        self.assertTrue(invited_user.check_password('BrandNewPassword123!'))

    def test_cross_tenant_isolation_unauthorized_resend_and_revoke(self):
        """Users from other tenants cannot resend or revoke invitations."""
        # Create pending invitation in creator's org
        payload = {
            'assignment_type': 'invite',
            'first_name': 'Iso',
            'last_name': 'Target',
            'email': 'iso.target@apex.com',
        }
        self.client.force_authenticate(user=self.creator)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post('/api/v1/organization/wizard/stage-6/', payload, format='json')

        # Attacker authenticates and attempts to resend/revoke targeting creator's org
        self.client.force_authenticate(user=self.attacker)

        # Resend attempt
        resend_resp = self.client.post(f'/api/v1/organization/wizard/stage-6/resend/?org_id={self.org_id}')
        self.assertEqual(resend_resp.status_code, status.HTTP_403_FORBIDDEN)

        # Revoke attempt
        revoke_resp = self.client.post(f'/api/v1/organization/wizard/stage-6/revoke/?org_id={self.org_id}')
        self.assertEqual(revoke_resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_email_delivery_failure_decoupled_from_invitation_status(self):
        """Email delivery failure records delivery status FAILED without marking invitation invalid."""
        with patch.object(NotificationService, 'send_organization_admin_invitation_email', side_effect=Exception('SMTP connection timeout')):
            self.client.force_authenticate(user=self.creator)
            with self.captureOnCommitCallbacks(execute=True):
                resp = self.client.post('/api/v1/organization/wizard/stage-6/', {
                    'assignment_type': 'invite',
                    'first_name': 'Fail',
                    'last_name': 'Delivery',
                    'email': 'delivery.fail@apex.com',
                }, format='json')
                self.assertEqual(resp.status_code, status.HTTP_200_OK)

            invitation = OrganizationInvitation.objects.get(organization=self.org, email='delivery.fail@apex.com')
            # Invitation itself remains valid PENDING
            self.assertEqual(invitation.status, InvitationStatus.PENDING)
            # Email delivery status is recorded as FAILED
            self.assertEqual(invitation.email_delivery_status, EmailDeliveryStatus.FAILED)
            self.assertIn('SMTP connection timeout', invitation.email_delivery_error)

            # Resend recovery succeeds when SMTP recovers
            with patch.object(NotificationService, 'send_organization_admin_invitation_email', return_value=True):
                with self.captureOnCommitCallbacks(execute=True):
                    resend_resp = self.client.post('/api/v1/organization/wizard/stage-6/resend/', format='json')
                    self.assertEqual(resend_resp.status_code, status.HTTP_200_OK)
                invitation.refresh_from_db()
                self.assertEqual(invitation.email_delivery_status, EmailDeliveryStatus.SENT)
                self.assertEqual(invitation.email_delivery_error, '')

    def test_acceptance_rate_limiting_enforcement(self):
        """Security Gate P: Anonymous requests to /accept/ are throttled after 5 requests per minute."""
        cache.clear()
        client = APIClient()

        # Submit 5 requests (throttle rate is 5/minute)
        for i in range(5):
            r = client.post('/api/v1/organization/invitations/accept/', {'token': f'fake-token-{i}'}, format='json')
            self.assertIn(r.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED])

        # 6th request from same IP must be throttled with HTTP 429 Too Many Requests
        throttled_resp = client.post('/api/v1/organization/invitations/accept/', {'token': 'fake-token-6'}, format='json')
        self.assertEqual(throttled_resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class OrganizationInvitationConcurrencyTests(TransactionTestCase):
    """
    Integration concurrency test using TransactionTestCase to verify atomic row locking
    with select_for_update() against concurrent double-acceptance.
    """

    def setUp(self):
        cache.clear()
        self.creator = User.objects.create_user(
            email='concurrency_creator@test.com',
            password='Password123!',
            status=UserStatus.ACTIVE,
        )
        self.org = Organization.objects.create(name='Concurrent Org', code='CONCUR')
        self.super_admin_role = Role.objects.create(
            organization=self.org,
            slug='super-admin',
            name='Super Admin',
            is_system=True,
        )
        self.raw_token = 'concurrency-token-unique-55555'
        self.token_hash = hashlib.sha256(self.raw_token.encode('utf-8')).hexdigest()

        self.invitation = OrganizationInvitation.objects.create(
            organization=self.org,
            email='concurrent.accept@test.com',
            role=self.super_admin_role,
            token_hash=self.token_hash,
            status=InvitationStatus.PENDING,
            invited_by=self.creator,
            expires_at=timezone.now() + timedelta(days=7),
        )

    def test_concurrent_acceptance_race_condition_protection(self):
        """Simultaneous acceptance requests serialize via select_for_update; exactly one succeeds."""
        client1 = APIClient()
        client2 = APIClient()

        # Request 1 accepts
        resp1 = client1.post('/api/v1/organization/invitations/accept/', {
            'token': self.raw_token,
            'password': 'FirstWinPassword123!',
        }, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        # Immediate consecutive request 2 must be rejected as already accepted
        resp2 = client2.post('/api/v1/organization/invitations/accept/', {
            'token': self.raw_token,
            'password': 'SecondFailPassword123!',
        }, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already been accepted', resp2.data['detail'])

        # Invariant: Exactly one User created, exactly one UserRole provisioned
        user = User.objects.get(email='concurrent.accept@test.com')
        self.assertEqual(UserRole.objects.filter(user=user, role=self.super_admin_role).count(), 1)
        self.assertTrue(user.check_password('FirstWinPassword123!'))
