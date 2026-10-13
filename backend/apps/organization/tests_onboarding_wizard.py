from datetime import time, timedelta
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
)
from apps.attendance.models import Shift, Holiday
from apps.authorization.models import Role, UserRole, ScopeChoices, Permission, RolePermission
from apps.accounts.models import TenantOwnerRegistration
from apps.audit.models import AuditLog

User = get_user_model()


class OrganizationWizardServiceAndAPITests(TestCase):
    """
    Focused verification suite for Phase 3C Organization Setup Wizard:
    - Multi-stage onboarding lifecycle (Stages 1 through 7)
    - Sequential progression & prerequisite enforcement
    - Atomic transactions & rollback behavior
    - Idempotency & retry without data duplication
    - Cross-tenant isolation & privilege escalation prevention
    - Dynamic RBAC authorization checks
    - Safe draft metadata & sensitive keyword rejection
    - Completion integrity & post-completion immutability
    - Audit logging integration
    """

    def setUp(self):
        self.client = APIClient()

        # User A: Verified Tenant Owner
        self.owner_user = User.objects.create_user(
            email='tenant_owner@example.com',
            password='Password123!',
            first_name='Owner',
            last_name='Tenant',
            status='active',
        )
        self.owner_registration = TenantOwnerRegistration.objects.create(
            user=self.owner_user,
            verified_at=timezone.now(),
            organization=None,
        )

        # User B: Other Tenant Owner / Competitor
        self.other_user = User.objects.create_user(
            email='other_owner@example.com',
            password='Password123!',
            first_name='Other',
            last_name='Owner',
            status='active',
        )
        self.other_registration = TenantOwnerRegistration.objects.create(
            user=self.other_user,
            verified_at=timezone.now(),
            organization=None,
        )

        # Platform Superuser
        self.platform_admin = User.objects.create_user(
            email='platform_admin@example.com',
            password='Password123!',
            first_name='Platform',
            last_name='Admin',
            is_superuser=True,
            is_staff=True,
            status='active',
        )

    def test_full_wizard_lifecycle_stage_1_to_7_happy_path(self):
        """End-to-end execution of all 7 onboarding wizard stages."""
        self.client.force_authenticate(user=self.owner_user)

        # --- Stage 1: Organization Details ---
        stage1_payload = {
            'name': 'Apex Global Corp',
            'code': 'APEX',
            'currency_code': 'INR',
            'date_format': 'DD/MM/YYYY',
            'timezone': 'Asia/Kolkata',
        }
        resp1 = self.client.post('/api/v1/organization/wizard/start/', stage1_payload, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED, resp1.data)
        self.assertEqual(resp1.data['current_stage'], 2)
        self.assertEqual(resp1.data['completed_stages'], [1])
        org_id = resp1.data['organization_id']
        org = Organization.objects.get(id=org_id)
        self.assertEqual(org.name, 'Apex Global Corp')
        self.assertEqual(org.code, 'APEX')

        # Check status endpoint
        resp_status = self.client.get('/api/v1/organization/wizard/status/')
        self.assertEqual(resp_status.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_status.data['status'], OnboardingStatus.IN_PROGRESS)
        self.assertEqual(resp_status.data['current_stage'], 2)
        self.assertEqual(resp_status.data['completed_stages'], [1])

        # --- Stage 2: Initial Branch (Head Office) ---
        stage2_payload = {
            'name': 'Headquarters Bengaluru',
            'code': 'HQ-BLR',
            'address_line1': '100 Tech Park Way',
            'city': 'Bengaluru',
            'state': 'Karnataka',
            'country': 'India',
            'postal_code': '560100',
            'timezone': 'Asia/Kolkata',
            'latitude': 12.9716,
            'longitude': 77.5946,
            'radius': 250.0,
        }
        resp2 = self.client.post('/api/v1/organization/wizard/stage-2/', stage2_payload, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_200_OK, resp2.data)
        self.assertEqual(resp2.data['current_stage'], 3)
        self.assertEqual(resp2.data['completed_stages'], [1, 2])
        branch = Branch.objects.get(organization=org, is_head_office=True)
        self.assertEqual(branch.name, 'Headquarters Bengaluru')
        self.assertEqual(branch.radius, 250.0)

        # --- Stage 3: Structure (Departments & Designations) ---
        stage3_payload = {
            'departments': [
                {'name': 'Engineering', 'code': 'ENG', 'description': 'Product Engineering'},
                {'name': 'Human Resources', 'code': 'HR', 'description': 'People Operations'},
            ],
            'designations': [
                {'name': 'Director of Engineering', 'code': 'DIR-ENG', 'level': 1},
                {'name': 'Senior Software Engineer', 'code': 'SR-SWE', 'level': 3},
            ],
        }
        resp3 = self.client.post('/api/v1/organization/wizard/stage-3/', stage3_payload, format='json')
        self.assertEqual(resp3.status_code, status.HTTP_200_OK, resp3.data)
        self.assertEqual(resp3.data['current_stage'], 4)
        self.assertEqual(resp3.data['completed_stages'], [1, 2, 3])
        self.assertEqual(Department.objects.filter(branch=branch).count(), 2)
        self.assertEqual(Designation.objects.filter(organization=org).count(), 2)

        # --- Stage 4: Working Calendar & Holidays ---
        stage4_payload = {
            'work_days': '0,1,2,3,4',
            'recurring_rules': [
                {'weekday': 5, 'occurrence': 2, 'is_working': False},
                {'weekday': 5, 'occurrence': 4, 'is_working': False},
            ],
            'holidays': [
                {'name': 'Republic Day', 'date': '2026-01-26', 'holiday_type': 'public'},
            ],
        }
        resp4 = self.client.post('/api/v1/organization/wizard/stage-4/', stage4_payload, format='json')
        self.assertEqual(resp4.status_code, status.HTTP_200_OK, resp4.data)
        self.assertEqual(resp4.data['current_stage'], 5)
        self.assertEqual(resp4.data['completed_stages'], [1, 2, 3, 4])
        calendar = WorkingCalendar.objects.get(branch=branch)
        self.assertEqual(calendar.work_days, '0,1,2,3,4')
        self.assertEqual(calendar.recurring_rules.count(), 2)
        self.assertEqual(Holiday.objects.filter(branch=branch).count(), 1)

        # --- Stage 5: Shift Schedule & Attendance Policy ---
        stage5_payload = {
            'shift': {
                'name': 'General Shift',
                'code': 'GEN-9TO6',
                'start_time': '09:00:00',
                'end_time': '18:00:00',
                'grace_period_minutes': 15,
                'work_days': '0,1,2,3,4',
            },
            'attendance_policy': {
                'is_office_gps_enabled': True,
                'is_office_ip_enabled': False,
                'is_wfh_enabled': True,
            },
            'office_network': {
                'name': 'HQ Wi-Fi',
                'network': '192.168.1.0/24',
                'description': 'Primary Office Subnet',
            },
        }
        resp5 = self.client.post('/api/v1/organization/wizard/stage-5/', stage5_payload, format='json')
        self.assertEqual(resp5.status_code, status.HTTP_200_OK, resp5.data)
        self.assertEqual(resp5.data['current_stage'], 6)
        self.assertEqual(resp5.data['completed_stages'], [1, 2, 3, 4, 5])
        shift = Shift.objects.get(branch=branch, is_active=True)
        self.assertEqual(shift.name, 'General Shift')
        self.assertEqual(shift.start_time, time(9, 0))

        # --- Stage 6: Initial Administrator & RBAC ---
        stage6_payload = {'confirm': True}
        resp6 = self.client.post('/api/v1/organization/wizard/stage-6/', stage6_payload, format='json')
        self.assertEqual(resp6.status_code, status.HTTP_200_OK, resp6.data)
        self.assertEqual(resp6.data['current_stage'], 7)
        self.assertEqual(resp6.data['completed_stages'], [1, 2, 3, 4, 5, 6])
        super_admin_role = Role.objects.get(organization=org, slug='super-admin')
        self.assertTrue(super_admin_role.is_system)
        self.assertTrue(UserRole.objects.filter(user=self.owner_user, role=super_admin_role, is_revoked=False).exists())

        # Check diagnostic readiness report
        resp_readiness = self.client.get('/api/v1/organization/wizard/readiness/')
        self.assertEqual(resp_readiness.status_code, status.HTTP_200_OK)
        self.assertIn('score', resp_readiness.data)
        self.assertIn('checks', resp_readiness.data)

        # --- Stage 7: Complete Setup ---
        resp_complete = self.client.post('/api/v1/organization/wizard/complete/', {}, format='json')
        self.assertEqual(resp_complete.status_code, status.HTTP_200_OK, resp_complete.data)
        self.assertEqual(resp_complete.data['status'], OnboardingStatus.COMPLETED)
        self.assertEqual(resp_complete.data['organization_id'], org.id)
        self.assertIsNotNone(resp_complete.data['completed_at'])

        # Verify database state after completion
        onboarding = OrganizationOnboarding.objects.get(organization=org)
        self.assertEqual(onboarding.status, OnboardingStatus.COMPLETED)
        self.assertTrue(onboarding.is_complete)
        self.assertEqual(onboarding.completed_stages, [1, 2, 3, 4, 5, 6, 7])
        self.assertIsNotNone(onboarding.completed_at)

        # Verify audit logs were created for stages and completion
        actions = list(AuditLog.objects.filter(organization=org).values_list('action', flat=True))
        self.assertIn('onboarding_stage_1_completed', actions)
        self.assertIn('onboarding_stage_2_completed', actions)
        self.assertIn('onboarding_stage_3_completed', actions)
        self.assertIn('onboarding_stage_4_completed', actions)
        self.assertIn('onboarding_stage_5_completed', actions)
        self.assertIn('onboarding_stage_6_completed', actions)
        self.assertIn('organization_onboarding_completed', actions)

    def test_stage_skipping_strictly_rejected(self):
        """Preceding stages must not be skipped."""
        self.client.force_authenticate(user=self.owner_user)

        # Start Stage 1
        resp1 = self.client.post('/api/v1/organization/wizard/start/', {
            'name': 'Skipper Corp',
            'code': 'SKIP',
        }, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        # Attempt to jump straight to Stage 3 without doing Stage 2
        resp3 = self.client.post('/api/v1/organization/wizard/stage-3/', {
            'departments': [{'name': 'Eng'}],
            'designations': [{'name': 'Dev'}],
        }, format='json')
        self.assertEqual(resp3.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Preceding stages must be completed first', str(resp3.data))

        # Attempt to jump straight to Stage 5
        resp5 = self.client.post('/api/v1/organization/wizard/stage-5/', {
            'shift': {'name': 'Shift 1', 'start_time': '09:00:00', 'end_time': '18:00:00'},
        }, format='json')
        self.assertEqual(resp5.status_code, status.HTTP_400_BAD_REQUEST)

        # Attempt to complete without stages 2-6
        resp_comp = self.client.post('/api/v1/organization/wizard/complete/', {}, format='json')
        self.assertEqual(resp_comp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_stage_retry_and_idempotency_without_duplication(self):
        """Re-running stages safely updates entities without creating duplicate records."""
        self.client.force_authenticate(user=self.owner_user)

        # Stage 1
        self.client.post('/api/v1/organization/wizard/start/', {
            'name': 'Idempotent Tech',
            'code': 'IDEM',
        }, format='json')

        # Stage 2: Initial Branch
        self.client.post('/api/v1/organization/wizard/stage-2/', {
            'name': 'Main Branch',
            'city': 'Mumbai',
            'radius': 150.0,
        }, format='json')
        org = Organization.objects.get(code='IDEM')
        self.assertEqual(Branch.objects.filter(organization=org).count(), 1)

        # Stage 2 Retry: Update Branch Address & Radius
        resp2_retry = self.client.post('/api/v1/organization/wizard/stage-2/', {
            'name': 'Main Branch Renamed',
            'city': 'Mumbai Suburbs',
            'radius': 300.0,
        }, format='json')
        self.assertEqual(resp2_retry.status_code, status.HTTP_200_OK)
        # Should still be exactly one branch for this org
        self.assertEqual(Branch.objects.filter(organization=org).count(), 1)
        branch = Branch.objects.get(organization=org)
        self.assertEqual(branch.name, 'Main Branch Renamed')
        self.assertEqual(branch.radius, 300.0)

        # Stage 3: Initial Departments & Designations
        self.client.post('/api/v1/organization/wizard/stage-3/', {
            'departments': [{'name': 'Finance', 'code': 'FIN'}],
            'designations': [{'name': 'Accountant', 'code': 'ACC'}],
        }, format='json')
        self.assertEqual(Department.objects.filter(branch=branch).count(), 1)
        self.assertEqual(Designation.objects.filter(organization=org).count(), 1)

        # Stage 3 Retry: Add more without duplicating existing
        self.client.post('/api/v1/organization/wizard/stage-3/', {
            'departments': [
                {'name': 'Finance', 'code': 'FIN'},
                {'name': 'Marketing', 'code': 'MKT'},
            ],
            'designations': [
                {'name': 'Accountant', 'code': 'ACC'},
                {'name': 'Marketing Executive', 'code': 'MKT-EXEC'},
            ],
        }, format='json')
        self.assertEqual(Department.objects.filter(branch=branch).count(), 2)
        self.assertEqual(Designation.objects.filter(organization=org).count(), 2)

    def test_transaction_rollback_on_failure(self):
        """Invalid stage submission rolls back cleanly without leaving partial records."""
        self.client.force_authenticate(user=self.owner_user)

        self.client.post('/api/v1/organization/wizard/start/', {
            'name': 'Rollback Corp',
            'code': 'RLBK',
        }, format='json')
        org = Organization.objects.get(code='RLBK')

        # Branch with radius < 100 meters (invalid)
        resp2_invalid = self.client.post('/api/v1/organization/wizard/stage-2/', {
            'name': 'Invalid Branch',
            'city': 'Delhi',
            'radius': 50.0,  # Below minimum 100m
        }, format='json')
        self.assertEqual(resp2_invalid.status_code, status.HTTP_400_BAD_REQUEST)
        # Branch must not exist
        self.assertEqual(Branch.objects.filter(organization=org).count(), 0)

        onboarding = OrganizationOnboarding.objects.get(organization=org)
        self.assertEqual(onboarding.current_stage, 2)
        self.assertEqual(onboarding.completed_stages, [1])

    def test_tenant_isolation_and_cross_tenant_access_rejection(self):
        """Users from Tenant B cannot view or modify Tenant A's onboarding."""
        # Tenant A owner creates onboarding
        self.client.force_authenticate(user=self.owner_user)
        resp1 = self.client.post('/api/v1/organization/wizard/start/', {
            'name': 'Tenant A Org',
            'code': 'T-A',
        }, format='json')
        org_a_id = resp1.data['organization_id']

        # Tenant B owner attempts to access without having an onboarding
        self.client.force_authenticate(user=self.other_user)
        resp_b_status = self.client.get('/api/v1/organization/wizard/status/')
        self.assertEqual(resp_b_status.status_code, status.HTTP_400_BAD_REQUEST)

        # Tenant B attempts to spoof org_id in query parameter
        resp_b_spoof = self.client.get(f'/api/v1/organization/wizard/status/?org_id={org_a_id}')
        self.assertEqual(resp_b_spoof.status_code, status.HTTP_403_FORBIDDEN)

        # Tenant B attempts to submit Stage 2 into Tenant A
        resp_b_stage2 = self.client.post(
            f'/api/v1/organization/wizard/stage-2/?org_id={org_a_id}',
            {'name': 'Spoofed Branch', 'city': 'Goa', 'radius': 150.0},
            format='json'
        )
        self.assertEqual(resp_b_stage2.status_code, status.HTTP_403_FORBIDDEN)

        # Global Django superuser without tenant role/ownership does NOT bypass tenant isolation
        self.client.force_authenticate(user=self.platform_admin)
        resp_admin_status = self.client.get(f'/api/v1/organization/wizard/status/?org_id={org_a_id}')
        self.assertEqual(resp_admin_status.status_code, status.HTTP_403_FORBIDDEN)

    def test_sensitive_metadata_rejected_in_drafts(self):
        """Saving drafts strictly blocks credentials, tokens, passwords, and secrets."""
        self.client.force_authenticate(user=self.owner_user)
        self.client.post('/api/v1/organization/wizard/start/', {
            'name': 'Draft Org',
            'code': 'DRFT',
        }, format='json')

        # Valid safe draft
        resp_safe = self.client.post('/api/v1/organization/wizard/draft/', {
            'stage': 2,
            'data': {'temp_branch_name': 'Pending Name', 'city': 'Pune'},
        }, format='json')
        self.assertEqual(resp_safe.status_code, status.HTTP_200_OK)

        onboarding = OrganizationOnboarding.objects.get(organization__code='DRFT')
        self.assertIn('drafts', onboarding.metadata)
        self.assertEqual(onboarding.metadata['drafts']['2']['temp_branch_name'], 'Pending Name')

        # Reject password
        resp_pwd = self.client.post('/api/v1/organization/wizard/draft/', {
            'stage': 2,
            'data': {'admin_password': 'SuperSecretPassword!'},
        }, format='json')
        self.assertEqual(resp_pwd.status_code, status.HTTP_400_BAD_REQUEST)

        # Reject auth token
        resp_tok = self.client.post('/api/v1/organization/wizard/draft/', {
            'stage': 2,
            'data': {'access_token': 'eyJh...'},
        }, format='json')
        self.assertEqual(resp_tok.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_completion_immutability(self):
        """Once completed, onboarding cannot be re-completed or mutated via wizard stages."""
        self.client.force_authenticate(user=self.owner_user)

        # Run through stages 1 to 6
        self.client.post('/api/v1/organization/wizard/start/', {'name': 'Final Org', 'code': 'FNL'}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-2/', {'name': 'HQ', 'city': 'Pune', 'radius': 150.0}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-3/', {
            'departments': [{'name': 'IT'}], 'designations': [{'name': 'Dev'}],
        }, format='json')
        self.client.post('/api/v1/organization/wizard/stage-4/', {'work_days': '0,1,2,3,4'}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-5/', {
            'shift': {'name': 'General', 'start_time': '09:00:00', 'end_time': '18:00:00'},
        }, format='json')
        self.client.post('/api/v1/organization/wizard/stage-6/', {'confirm': True}, format='json')
        self.client.post('/api/v1/organization/wizard/complete/', {}, format='json')

        # Attempt to call complete again — must succeed idempotently without error
        resp_recomp = self.client.post('/api/v1/organization/wizard/complete/', {}, format='json')
        self.assertEqual(resp_recomp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_recomp.data['status'], OnboardingStatus.COMPLETED)

        # Attempt to alter stage 2 after completion
        resp_post_mut = self.client.post('/api/v1/organization/wizard/stage-2/', {
            'name': 'Hacked Branch', 'city': 'Goa', 'radius': 200.0,
        }, format='json')
        self.assertEqual(resp_post_mut.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already completed', str(resp_post_mut.data))

    def test_persisted_prerequisites_catches_deleted_database_entities(self):
        """Direct database re-validation in Stage 7 prevents spoofing if entities are deleted."""
        self.client.force_authenticate(user=self.owner_user)

        # Run through stages 1 to 6
        self.client.post('/api/v1/organization/wizard/start/', {'name': 'Integrity Org', 'code': 'INTG'}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-2/', {'name': 'HQ', 'city': 'Pune', 'radius': 150.0}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-3/', {
            'departments': [{'name': 'IT'}], 'designations': [{'name': 'Dev'}],
        }, format='json')
        self.client.post('/api/v1/organization/wizard/stage-4/', {'work_days': '0,1,2,3,4'}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-5/', {
            'shift': {'name': 'General', 'start_time': '09:00:00', 'end_time': '18:00:00'},
        }, format='json')
        self.client.post('/api/v1/organization/wizard/stage-6/', {'confirm': True}, format='json')

        org = Organization.objects.get(code='INTG')
        # Simulate an anomaly: active shift was deleted out-of-band before completion
        Shift.objects.filter(branch__organization=org).delete()

        # Attempting completion must fail on database verification
        resp_comp = self.client.post('/api/v1/organization/wizard/complete/', {}, format='json')
        self.assertEqual(resp_comp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Stage 5 incomplete', str(resp_comp.data))

    def test_dynamic_rbac_delegation_and_isolation(self):
        """Tenant Super Admin can access onboarding session, while unrelated user is rejected."""
        self.client.force_authenticate(user=self.owner_user)
        resp1 = self.client.post('/api/v1/organization/wizard/start/', {'name': 'RBAC Org', 'code': 'RBAC'}, format='json')
        org_id = resp1.data['organization_id']
        org = Organization.objects.get(id=org_id)

        # Delegate Admin User (not the onboarding owner)
        delegate_user = User.objects.create_user(
            email='delegate_admin@example.com',
            password='Password123!',
            first_name='Delegate',
            last_name='Admin',
            status='active',
        )
        super_admin_role = Role.objects.create(
            organization=org,
            name='Super Admin',
            slug='super-admin',
            is_system=True,
            is_active=True,
        )
        UserRole.objects.create(
            user=delegate_user,
            role=super_admin_role,
            scope=ScopeChoices.ORGANIZATION,
            is_revoked=False,
        )

        # Authenticate as delegate admin
        self.client.force_authenticate(user=delegate_user)
        resp_status = self.client.get(f'/api/v1/organization/wizard/status/?org_id={org_id}')
        self.assertEqual(resp_status.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_status.data['organization_id'], org_id)

        # Normal employee with no roles attempting access is rejected
        normal_user = User.objects.create_user(
            email='normal_emp@example.com',
            password='Password123!',
            first_name='Normal',
            last_name='Emp',
            status='active',
        )
        self.client.force_authenticate(user=normal_user)
        resp_unauth = self.client.get(f'/api/v1/organization/wizard/status/?org_id={org_id}')
        self.assertEqual(resp_unauth.status_code, status.HTTP_403_FORBIDDEN)

    def test_stage_5_single_active_shift_invariant(self):
        """Resubmitting Stage 5 updates the existing active shift and never violates the single-active-shift invariant."""
        self.client.force_authenticate(user=self.owner_user)
        self.client.post('/api/v1/organization/wizard/start/', {'name': 'Shift Org', 'code': 'SHFT'}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-2/', {'name': 'HQ', 'city': 'Pune', 'radius': 150.0}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-3/', {
            'departments': [{'name': 'IT'}], 'designations': [{'name': 'Dev'}],
        }, format='json')
        self.client.post('/api/v1/organization/wizard/stage-4/', {'work_days': '0,1,2,3,4'}, format='json')

        # First shift submission
        resp5_1 = self.client.post('/api/v1/organization/wizard/stage-5/', {
            'shift': {
                'name': 'Morning Shift',
                'start_time': '08:00:00',
                'end_time': '16:00:00',
                'grace_period_minutes': 10,
            }
        }, format='json')
        self.assertEqual(resp5_1.status_code, status.HTTP_200_OK)

        org = Organization.objects.get(code='SHFT')
        branch = Branch.objects.get(organization=org, is_head_office=True)
        self.assertEqual(Shift.objects.filter(branch=branch, is_active=True).count(), 1)
        shift1 = Shift.objects.get(branch=branch, is_active=True)
        self.assertEqual(shift1.name, 'Morning Shift')
        self.assertEqual(shift1.start_time, time(8, 0))

        # Re-run Stage 5 with different timings
        resp5_2 = self.client.post('/api/v1/organization/wizard/stage-5/', {
            'shift': {
                'name': 'Standard Shift',
                'start_time': '09:00:00',
                'end_time': '18:00:00',
                'grace_period_minutes': 15,
            }
        }, format='json')
        self.assertEqual(resp5_2.status_code, status.HTTP_200_OK)
        # Must still be exactly one active shift
        self.assertEqual(Shift.objects.filter(branch=branch, is_active=True).count(), 1)
        shift2 = Shift.objects.get(branch=branch, is_active=True)
        self.assertEqual(shift2.id, shift1.id)
        self.assertEqual(shift2.name, 'Standard Shift')
        self.assertEqual(shift2.start_time, time(9, 0))

    def test_stage_input_validation_errors(self):
        """Input serializers properly validate and reject erroneous payloads."""
        self.client.force_authenticate(user=self.owner_user)

        # Stage 1: Blank name
        resp1_bad = self.client.post('/api/v1/organization/wizard/start/', {'name': '   '}, format='json')
        self.assertEqual(resp1_bad.status_code, status.HTTP_400_BAD_REQUEST)

        # Stage 1: Duplicate org name
        self.client.post('/api/v1/organization/wizard/start/', {'name': 'Dup Corp', 'code': 'DUP1'}, format='json')

        self.client.force_authenticate(user=self.other_user)
        resp1_dup = self.client.post('/api/v1/organization/wizard/start/', {'name': 'Dup Corp', 'code': 'DUP2'}, format='json')
        self.assertEqual(resp1_dup.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already exists', str(resp1_dup.data))

        # Stage 4: Invalid work_days
        self.client.force_authenticate(user=self.owner_user)
        self.client.post('/api/v1/organization/wizard/stage-2/', {'name': 'HQ', 'city': 'Pune', 'radius': 150.0}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-3/', {
            'departments': [{'name': 'IT'}], 'designations': [{'name': 'Dev'}],
        }, format='json')

        resp4_bad = self.client.post('/api/v1/organization/wizard/stage-4/', {'work_days': '1,2,7'}, format='json')
        self.assertEqual(resp4_bad.status_code, status.HTTP_400_BAD_REQUEST)

        # Stage 6: confirm=False
        self.client.post('/api/v1/organization/wizard/stage-4/', {'work_days': '0,1,2,3,4'}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-5/', {
            'shift': {'name': 'Gen', 'start_time': '09:00:00', 'end_time': '18:00:00'},
        }, format='json')
        resp6_bad = self.client.post('/api/v1/organization/wizard/stage-6/', {'confirm': False}, format='json')
        self.assertEqual(resp6_bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tenant_isolation_rejects_inactive_user(self):
        """Inactive user is strictly blocked from resolving onboarding session."""
        self.client.force_authenticate(user=self.owner_user)
        resp1 = self.client.post('/api/v1/organization/wizard/start/', {'name': 'Inactive User Org', 'code': 'INACT'}, format='json')
        org_id = resp1.data['organization_id']

        # Deactivate owner user
        self.owner_user.status = 'inactive'
        self.owner_user.save()

        resp_status = self.client.get(f'/api/v1/organization/wizard/status/?org_id={org_id}')
        # Should be rejected with 400 (no session for inactive user) or 401/403
        self.assertIn(resp_status.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_tenant_isolation_rejects_revoked_role(self):
        """User whose tenant role is revoked cannot access onboarding."""
        self.client.force_authenticate(user=self.owner_user)
        resp1 = self.client.post('/api/v1/organization/wizard/start/', {'name': 'Revoked Org', 'code': 'RVK'}, format='json')
        org_id = resp1.data['organization_id']
        org = Organization.objects.get(id=org_id)

        # Delegate Admin User with revoked role
        delegate_user = User.objects.create_user(
            email='revoked_admin@example.com',
            password='Password123!',
            status='active',
        )
        super_admin_role = Role.objects.create(
            organization=org,
            name='Super Admin',
            slug='super-admin',
            is_system=True,
            is_active=True,
        )
        UserRole.objects.create(
            user=delegate_user,
            role=super_admin_role,
            scope=ScopeChoices.ORGANIZATION,
            is_revoked=True,  # REVOKED
        )

        self.client.force_authenticate(user=delegate_user)
        resp = self.client.get(f'/api/v1/organization/wizard/status/?org_id={org_id}')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_tenant_isolation_rejects_expired_role(self):
        """User whose tenant role has expired cannot access onboarding."""
        self.client.force_authenticate(user=self.owner_user)
        resp1 = self.client.post('/api/v1/organization/wizard/start/', {'name': 'Expired Org', 'code': 'EXP'}, format='json')
        org_id = resp1.data['organization_id']
        org = Organization.objects.get(id=org_id)

        delegate_user = User.objects.create_user(
            email='expired_admin@example.com',
            password='Password123!',
            status='active',
        )
        super_admin_role = Role.objects.create(
            organization=org,
            name='Super Admin',
            slug='super-admin',
            is_system=True,
            is_active=True,
        )
        UserRole.objects.create(
            user=delegate_user,
            role=super_admin_role,
            scope=ScopeChoices.ORGANIZATION,
            is_revoked=False,
            expires_at=timezone.now() - timedelta(days=2),  # EXPIRED
        )

        self.client.force_authenticate(user=delegate_user)
        resp = self.client.get(f'/api/v1/organization/wizard/status/?org_id={org_id}')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_tenant_isolation_rejects_insufficient_permission_scope(self):
        """Branch-scoped or Team-scoped admin cannot access Organization Setup Wizard."""
        self.client.force_authenticate(user=self.owner_user)
        resp1 = self.client.post('/api/v1/organization/wizard/start/', {'name': 'Scope Org', 'code': 'SCP'}, format='json')
        org_id = resp1.data['organization_id']
        org = Organization.objects.get(id=org_id)

        # Stage 2 to have a branch
        self.client.post('/api/v1/organization/wizard/stage-2/', {'name': 'Main Branch', 'city': 'Pune', 'radius': 150.0}, format='json')
        branch = Branch.objects.get(organization=org)

        # Branch Manager with company.manage but scope=BRANCH
        branch_manager = User.objects.create_user(
            email='branch_mgr@example.com',
            password='Password123!',
            status='active',
        )
        bm_role = Role.objects.create(
            organization=org,
            name='Branch Manager',
            slug='branch-manager',
            is_active=True,
        )
        perm = Permission.objects.filter(codename='company.manage').first()
        if perm:
            RolePermission.objects.create(role=bm_role, permission=perm)

        UserRole.objects.create(
            user=branch_manager,
            role=bm_role,
            scope=ScopeChoices.BRANCH,  # INSUFFICIENT SCOPE
            branch=branch,
            is_revoked=False,
        )

        self.client.force_authenticate(user=branch_manager)
        resp = self.client.get(f'/api/v1/organization/wizard/status/?org_id={org_id}')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_tenant_admin_cannot_access_foreign_tenant(self):
        """Super Admin of Org 1 cannot access Org 2 onboarding."""
        # Create Org 1
        self.client.force_authenticate(user=self.owner_user)
        resp1 = self.client.post('/api/v1/organization/wizard/start/', {'name': 'Org 1', 'code': 'O1'}, format='json')
        org1_id = resp1.data['organization_id']
        org1 = Organization.objects.get(id=org1_id)

        # Create Org 2 with other user
        self.client.force_authenticate(user=self.other_user)
        resp2 = self.client.post('/api/v1/organization/wizard/start/', {'name': 'Org 2', 'code': 'O2'}, format='json')
        org2_id = resp2.data['organization_id']

        # Delegate admin in Org 1
        admin_org1 = User.objects.create_user(
            email='admin_org1@example.com',
            password='Password123!',
            status='active',
        )
        super_admin_role_1 = Role.objects.create(
            organization=org1,
            name='Super Admin',
            slug='super-admin',
            is_system=True,
            is_active=True,
        )
        UserRole.objects.create(
            user=admin_org1,
            role=super_admin_role_1,
            scope=ScopeChoices.ORGANIZATION,
            is_revoked=False,
        )

        # Admin of Org 1 attempts to query Org 2
        self.client.force_authenticate(user=admin_org1)
        resp = self.client.get(f'/api/v1/organization/wizard/status/?org_id={org2_id}')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_stage_6_administrator_provisioning_invariants(self):
        """Stage 6 provisions organization-scoped super-admin role without global elevation."""
        self.client.force_authenticate(user=self.owner_user)
        self.client.post('/api/v1/organization/wizard/start/', {'name': 'Stage 6 Invariant Org', 'code': 'S6INV'}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-2/', {'name': 'HQ', 'city': 'Pune', 'radius': 150.0}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-3/', {
            'departments': [{'name': 'IT'}], 'designations': [{'name': 'Dev'}],
        }, format='json')
        self.client.post('/api/v1/organization/wizard/stage-4/', {'work_days': '0,1,2,3,4'}, format='json')
        self.client.post('/api/v1/organization/wizard/stage-5/', {
            'shift': {'name': 'General', 'start_time': '09:00:00', 'end_time': '18:00:00'},
        }, format='json')

        # Execute Stage 6
        resp6 = self.client.post('/api/v1/organization/wizard/stage-6/', {'confirm': True}, format='json')
        self.assertEqual(resp6.status_code, status.HTTP_200_OK)

        org = Organization.objects.get(code='S6INV')
        role = Role.objects.get(organization=org, slug='super-admin')
        self.assertEqual(role.organization, org)  # Organization-scoped
        self.assertTrue(role.is_system)

        # Verify owner received organization-scoped UserRole
        ur = UserRole.objects.get(user=self.owner_user, role=role)
        self.assertEqual(ur.scope, ScopeChoices.ORGANIZATION)
        self.assertFalse(ur.is_revoked)

        # Invariant: Owner must NOT receive global Django superuser flag
        self.owner_user.refresh_from_db()
        self.assertFalse(self.owner_user.is_superuser)
        self.assertFalse(self.owner_user.is_staff)

        # Invariant: Canonical permissions were attached
        active_perm_count = Permission.objects.filter(is_active=True).count()
        role_perm_count = RolePermission.objects.filter(role=role).count()
        self.assertEqual(role_perm_count, active_perm_count)

        # Invariant: Re-running Stage 6 does not duplicate assignments
        resp6_retry = self.client.post('/api/v1/organization/wizard/stage-6/', {'confirm': True}, format='json')
        self.assertEqual(resp6_retry.status_code, status.HTTP_200_OK)
        self.assertEqual(UserRole.objects.filter(user=self.owner_user, role=role).count(), 1)


