import importlib
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.organization.models import (
    Organization,
    Branch,
    Department,
    Designation,
    WorkingCalendar,
    AttendancePolicy,
    OrganizationOnboarding,
    OnboardingStatus,
    validate_onboarding_metadata,
)
from apps.attendance.models import Shift
from apps.authorization.models import Role, UserRole, ScopeChoices
from apps.accounts.models import TenantOwnerRegistration

User = get_user_model()


class OrganizationOnboardingModelTests(TestCase):
    """Focused tests for OrganizationOnboarding model, validation, and lifecycle."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='owner@example.com',
            password='testpassword123',
            first_name='Owner',
            last_name='User',
            status='active',
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='testpassword123',
            first_name='Other',
            last_name='User',
            status='active',
        )
        self.org = Organization.objects.create(
            name='Acme Corp',
            code='ACME',
        )

    def test_valid_onboarding_creation(self):
        """Valid default onboarding state creation."""
        onboarding = OrganizationOnboarding.objects.create(
            organization=self.org,
            owner=self.user,
        )
        self.assertEqual(onboarding.status, OnboardingStatus.NOT_STARTED)
        self.assertEqual(onboarding.current_stage, 1)
        self.assertEqual(onboarding.completed_stages, [])
        self.assertEqual(onboarding.metadata, {})
        self.assertIsNone(onboarding.completed_at)
        self.assertFalse(onboarding.is_complete)
        self.assertFalse(onboarding.is_in_progress)
        self.assertIn('Acme Corp', str(onboarding))
        self.assertEqual(self.org.onboarding, onboarding)
        self.assertIn(onboarding, self.user.organization_onboardings.all())

    def test_duplicate_onboarding_rejected(self):
        """Ensure OneToOne relationship prevents duplicate onboarding records for the same organization."""
        OrganizationOnboarding.objects.create(
            organization=self.org,
            owner=self.user,
        )
        with self.assertRaises((IntegrityError, ValidationError)):
            OrganizationOnboarding.objects.create(
                organization=self.org,
                owner=self.other_user,
            )

    def test_invalid_status_value_rejected(self):
        """Invalid status values must be rejected."""
        onboarding = OrganizationOnboarding(
            organization=self.org,
            owner=self.user,
            status='invalid_status',
        )
        with self.assertRaises(ValidationError) as ctx:
            onboarding.full_clean()
        self.assertIn('status', ctx.exception.message_dict)

    def test_invalid_stage_boundaries_rejected(self):
        """Stage must be an integer between 1 and 7."""
        for invalid_stage in [0, 8, -1, 10]:
            onboarding = OrganizationOnboarding(
                organization=self.org,
                owner=self.user,
                current_stage=invalid_stage,
            )
            with self.assertRaises(ValidationError) as ctx:
                onboarding.full_clean()
            self.assertIn('current_stage', ctx.exception.message_dict)

    def test_invalid_completed_stages_rejected(self):
        """completed_stages must be a list containing only valid stage numbers (1 to 7)."""
        # Non-list type
        onboarding = OrganizationOnboarding(
            organization=self.org,
            owner=self.user,
            completed_stages="1,2,3",
        )
        with self.assertRaises(ValidationError) as ctx:
            onboarding.full_clean()
        self.assertIn('completed_stages', ctx.exception.message_dict)

        # Invalid stage numbers in list
        onboarding = OrganizationOnboarding(
            organization=self.org,
            owner=self.user,
            completed_stages=[1, 8],
        )
        with self.assertRaises(ValidationError) as ctx:
            onboarding.full_clean()
        self.assertIn('completed_stages', ctx.exception.message_dict)

    def test_completed_status_requires_all_stages(self):
        """Setting status to COMPLETED requires stages 1 through 7 in completed_stages."""
        onboarding = OrganizationOnboarding(
            organization=self.org,
            owner=self.user,
            status=OnboardingStatus.COMPLETED,
            current_stage=7,
            completed_stages=[1, 2, 3],
        )
        with self.assertRaises(ValidationError) as ctx:
            onboarding.full_clean()
        self.assertIn('status', ctx.exception.message_dict)

    def test_completed_status_auto_sets_completed_at(self):
        """When marked completed with all stages, completed_at is automatically assigned."""
        onboarding = OrganizationOnboarding(
            organization=self.org,
            owner=self.user,
            status=OnboardingStatus.COMPLETED,
            current_stage=7,
            completed_stages=[1, 2, 3, 4, 5, 6, 7],
            completed_at=None,
        )
        onboarding.save()
        self.assertIsNotNone(onboarding.completed_at)
        self.assertTrue(onboarding.is_complete)

    def test_not_started_cannot_have_completed_stages(self):
        """Status not_started cannot have non-empty completed_stages."""
        onboarding = OrganizationOnboarding(
            organization=self.org,
            owner=self.user,
            status=OnboardingStatus.NOT_STARTED,
            completed_stages=[1],
        )
        with self.assertRaises(ValidationError) as ctx:
            onboarding.full_clean()
        self.assertIn('status', ctx.exception.message_dict)

    def test_tenant_owner_consistency_check(self):
        """If organization has a registered owner, onboarding owner must match that user."""
        TenantOwnerRegistration.objects.create(
            user=self.user,
            organization=self.org,
            verified_at=timezone.now(),
        )
        # Matching owner works
        onboarding = OrganizationOnboarding(
            organization=self.org,
            owner=self.user,
        )
        onboarding.full_clean()

        # Mismatched owner fails
        onboarding_invalid = OrganizationOnboarding(
            organization=self.org,
            owner=self.other_user,
        )
        with self.assertRaises(ValidationError) as ctx:
            onboarding_invalid.full_clean()
        self.assertIn('owner', ctx.exception.message_dict)

    def test_mark_stage_complete_lifecycle(self):
        """mark_stage_complete updates stages, advances current_stage, and transitions status."""
        onboarding = OrganizationOnboarding.objects.create(
            organization=self.org,
            owner=self.user,
        )
        self.assertEqual(onboarding.status, OnboardingStatus.NOT_STARTED)

        onboarding.mark_stage_complete(1)
        onboarding.refresh_from_db()
        self.assertEqual(onboarding.status, OnboardingStatus.IN_PROGRESS)
        self.assertEqual(onboarding.completed_stages, [1])
        self.assertEqual(onboarding.current_stage, 2)

        onboarding.mark_stage_complete(2)
        onboarding.refresh_from_db()
        self.assertEqual(onboarding.completed_stages, [1, 2])
        self.assertEqual(onboarding.current_stage, 3)

        # Invalid stage numbers
        with self.assertRaises(ValueError):
            onboarding.mark_stage_complete(0)
        with self.assertRaises(ValueError):
            onboarding.mark_stage_complete(8)

    def test_mark_completed_helper(self):
        """mark_completed helper transitions onboarding to COMPLETED with all stages."""
        onboarding = OrganizationOnboarding.objects.create(
            organization=self.org,
            owner=self.user,
        )
        onboarding.mark_completed()
        onboarding.refresh_from_db()
        self.assertEqual(onboarding.status, OnboardingStatus.COMPLETED)
        self.assertEqual(onboarding.current_stage, 7)
        self.assertEqual(onboarding.completed_stages, [1, 2, 3, 4, 5, 6, 7])
        self.assertIsNotNone(onboarding.completed_at)
        self.assertTrue(onboarding.is_complete)

    def test_metadata_validation_forbidden_credentials(self):
        """Passwords, tokens, credentials, and secrets are strictly forbidden in metadata."""
        forbidden_keys = [
            'password', 'secret', 'token', 'access_token', 'refresh_token',
            'auth_token', 'credentials', 'api_key', 'private_key',
        ]
        for key in forbidden_keys:
            onboarding = OrganizationOnboarding(
                organization=self.org,
                owner=self.user,
                metadata={key: 'confidential_val'},
            )
            with self.assertRaises(ValidationError):
                onboarding.full_clean()

    def test_metadata_validation_forbidden_privileges_and_identities(self):
        """Identity override attempts and authorization flags are forbidden in metadata."""
        forbidden_keys = [
            'organization_id', 'org_id', 'owner_id', 'user_id',
            'is_superuser', 'is_staff', 'roles', 'permissions', 'role',
        ]
        for key in forbidden_keys:
            onboarding = OrganizationOnboarding(
                organization=self.org,
                owner=self.user,
                metadata={key: 123},
            )
            with self.assertRaises(ValidationError):
                onboarding.full_clean()

    def test_metadata_validation_nested_structures(self):
        """Forbidden keys are caught inside nested dictionaries and lists."""
        nested_meta = {
            'draft_info': {
                'step_details': {
                    'admin_token': 'secret123',
                }
            }
        }
        onboarding = OrganizationOnboarding(
            organization=self.org,
            owner=self.user,
            metadata=nested_meta,
        )
        with self.assertRaises(ValidationError):
            onboarding.full_clean()

        list_nested = {
            'branches': [
                {'name': 'Main Branch', 'secret_key': '1234'},
            ]
        }
        onboarding2 = OrganizationOnboarding(
            organization=self.org,
            owner=self.user,
            metadata=list_nested,
        )
        with self.assertRaises(ValidationError):
            onboarding2.full_clean()

    def test_metadata_validation_jwt_and_hashes_rejected(self):
        """Values that look like hashed credentials or JWT tokens are rejected."""
        jwt_value = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        onboarding = OrganizationOnboarding(
            organization=self.org,
            owner=self.user,
            metadata={'step_data': jwt_value},
        )
        with self.assertRaises(ValidationError):
            onboarding.full_clean()

        hash_value = "pbkdf2_sha256$260000$something$hashvalue"
        onboarding2 = OrganizationOnboarding(
            organization=self.org,
            owner=self.user,
            metadata={'step_data': hash_value},
        )
        with self.assertRaises(ValidationError):
            onboarding2.full_clean()

    def test_metadata_safe_draft_data_allowed(self):
        """Legitimate wizard drafts and UI state can be stored in metadata."""
        safe_meta = {
            'industry': 'technology',
            'estimated_employees': 50,
            'wizard_draft': {
                'branch_city': 'Pune',
                'working_days_preset': 'standard_5_day',
            }
        }
        onboarding = OrganizationOnboarding.objects.create(
            organization=self.org,
            owner=self.user,
            metadata=safe_meta,
        )
        onboarding.refresh_from_db()
        self.assertEqual(onboarding.metadata['industry'], 'technology')

        # Safe update via update_metadata
        onboarding.update_metadata({'notes': 'Initial setup in progress'})
        onboarding.refresh_from_db()
        self.assertEqual(onboarding.metadata['notes'], 'Initial setup in progress')
        self.assertEqual(onboarding.metadata['industry'], 'technology')

    # =========================================================================
    # TASK C: Database CheckConstraint Tests
    # =========================================================================

    def test_database_check_constraint_rejects_invalid_status_on_update(self):
        """Database CheckConstraint rejects invalid status values even via QuerySet.update()."""
        from django.db import transaction
        onboarding = OrganizationOnboarding.objects.create(
            organization=self.org,
            owner=self.user,
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                OrganizationOnboarding.objects.filter(id=onboarding.id).update(status='invalid_val')

    def test_database_check_constraint_rejects_invalid_stage_on_update(self):
        """Database CheckConstraint rejects stage numbers outside 1..7 even via QuerySet.update()."""
        from django.db import transaction
        onboarding = OrganizationOnboarding.objects.create(
            organization=self.org,
            owner=self.user,
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                OrganizationOnboarding.objects.filter(id=onboarding.id).update(current_stage=0)

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                OrganizationOnboarding.objects.filter(id=onboarding.id).update(current_stage=8)

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                OrganizationOnboarding.objects.filter(id=onboarding.id).update(current_stage=99)

    # =========================================================================
    # TASK A: Corrected Backfill Tests (Stage-by-Stage Evidence)
    # =========================================================================

    def _run_backfill(self):
        migration_module = importlib.import_module('apps.organization.migrations.0014_organizationonboarding')
        from django.apps import apps
        migration_module.backfill_existing_organizations(apps, None)

    def test_backfill_organization_with_no_configuration(self):
        """Organization with no configuration is classified not_started at Stage 1."""
        empty_org = Organization.objects.create(name='Empty Shell', code='EMPTY1')
        self._run_backfill()

        onb = OrganizationOnboarding.objects.get(organization=empty_org)
        self.assertEqual(onb.status, OnboardingStatus.NOT_STARTED)
        self.assertEqual(onb.current_stage, 1)
        self.assertEqual(onb.completed_stages, [])
        self.assertIsNone(onb.completed_at)
        self.assertEqual(onb.metadata.get('classification_reason'), 'unconfigured_empty_shell')

    def test_backfill_organization_with_only_branch(self):
        """Organization with only a branch is classified in_progress at Stage 3."""
        branch_org = Organization.objects.create(name='Branch Only Org', code='BR1')
        Branch.objects.create(organization=branch_org, name='HQ', code='HQ1')
        self._run_backfill()

        onb = OrganizationOnboarding.objects.get(organization=branch_org)
        self.assertEqual(onb.status, OnboardingStatus.IN_PROGRESS)
        self.assertEqual(onb.current_stage, 3)
        self.assertEqual(onb.completed_stages, [1, 2])
        self.assertIsNone(onb.completed_at)
        self.assertEqual(onb.metadata.get('classification_reason'), 'missing_or_partial_structure')

    def test_backfill_organization_with_only_user_role(self):
        """Organization with only a user role (no branch) is classified in_progress at Stage 2."""
        role_only_org = Organization.objects.create(name='Role Only Org', code='RO1')
        role = Role.objects.create(organization=role_only_org, name='Admin', slug='admin')
        UserRole.objects.create(user=self.user, role=role, scope=ScopeChoices.ORGANIZATION)
        self._run_backfill()

        onb = OrganizationOnboarding.objects.get(organization=role_only_org)
        self.assertEqual(onb.status, OnboardingStatus.IN_PROGRESS)
        self.assertEqual(onb.current_stage, 2)
        self.assertEqual(onb.completed_stages, [1])
        self.assertIsNone(onb.completed_at)
        self.assertEqual(onb.metadata.get('classification_reason'), 'missing_branch_setup')

    def test_backfill_organization_with_branch_and_partial_structure(self):
        """Organization with branch and department but missing designation is in_progress at Stage 3."""
        partial_org = Organization.objects.create(name='Partial Struct Org', code='PS1')
        b = Branch.objects.create(organization=partial_org, name='Main', code='MAIN')
        Department.objects.create(branch=b, name='Engineering', code='ENG')
        # No designation created
        self._run_backfill()

        onb = OrganizationOnboarding.objects.get(organization=partial_org)
        self.assertEqual(onb.status, OnboardingStatus.IN_PROGRESS)
        self.assertEqual(onb.current_stage, 3)
        self.assertEqual(onb.completed_stages, [1, 2])
        self.assertIsNone(onb.completed_at)

    def test_backfill_organization_with_sufficient_evidence_for_completion(self):
        """Organization with branch, depts, desigs, calendar, shift, and admin is completed at Stage 7."""
        full_org = Organization.objects.create(name='Full Enterprise Org', code='FE1')
        b = Branch.objects.create(organization=full_org, name='HQ', code='FEHQ')
        Department.objects.create(branch=b, name='Engineering', code='FEENG')
        Designation.objects.create(organization=full_org, name='Engineer', code='FESE')
        # Working calendar with work days
        WorkingCalendar.objects.filter(branch=b).update(work_days='0,1,2,3,4')
        # Shift
        Shift.objects.create(
            branch=b,
            name='General Shift',
            start_time='09:00',
            end_time='18:00',
            is_active=True,
        )
        # Administrative role
        admin_role = Role.objects.create(organization=full_org, name='Super Admin', slug='super-admin')
        UserRole.objects.create(user=self.user, role=admin_role, scope=ScopeChoices.ORGANIZATION)

        self._run_backfill()

        onb = OrganizationOnboarding.objects.get(organization=full_org)
        self.assertEqual(onb.status, OnboardingStatus.COMPLETED)
        self.assertEqual(onb.current_stage, 7)
        self.assertEqual(onb.completed_stages, [1, 2, 3, 4, 5, 6, 7])
        self.assertIsNotNone(onb.completed_at)
        self.assertEqual(onb.owner, self.user)
        self.assertEqual(onb.metadata.get('classification_reason'), 'fully_proven_operational_setup')

    def test_existing_organization_data_remains_unchanged_by_backfill(self):
        """Backfill strictly preserves organization name, code, status, timestamps, and related records."""
        org = Organization.objects.create(name='Untouched Org', code='UNTOUCH', status='active')
        b = Branch.objects.create(organization=org, name='Branch A', code='BA')
        orig_created_at = org.created_at
        orig_updated_at = org.updated_at

        self._run_backfill()

        org.refresh_from_db()
        self.assertEqual(org.name, 'Untouched Org')
        self.assertEqual(org.code, 'UNTOUCH')
        self.assertEqual(org.status, 'active')
        self.assertEqual(org.created_at, orig_created_at)
        self.assertEqual(Branch.objects.filter(organization=org).count(), 1)

    # =========================================================================
    # TASK B: Deterministic Owner Resolution Tests
    # =========================================================================

    def test_owner_resolution_prefers_verified_tenant_owner(self):
        """Verified TenantOwnerRegistration is prioritized over other user roles."""
        org = Organization.objects.create(name='Verified Owner Org', code='VO1')
        TenantOwnerRegistration.objects.create(
            user=self.user,
            organization=org,
            verified_at=timezone.now(),
        )
        # Also create a user role for other_user
        admin_role = Role.objects.create(organization=org, name='Admin Role', slug='admin')
        UserRole.objects.create(user=self.other_user, role=admin_role, scope=ScopeChoices.ORGANIZATION)

        self._run_backfill()

        onb = OrganizationOnboarding.objects.get(organization=org)
        self.assertEqual(onb.owner, self.user)

    def test_owner_resolution_prefers_superadmin_over_manager_or_viewer(self):
        """Administrative role (super-admin) is prioritized over non-admin manager or viewer."""
        org = Organization.objects.create(name='Multi Role Org', code='MR1')
        # Create non-admin role first (lower ID)
        manager_role = Role.objects.create(organization=org, name='Branch Manager', slug='branch-manager')
        UserRole.objects.create(user=self.other_user, role=manager_role, scope=ScopeChoices.ORGANIZATION)

        # Create admin role second (higher ID)
        admin_role = Role.objects.create(organization=org, name='Super Admin', slug='super-admin')
        UserRole.objects.create(user=self.user, role=admin_role, scope=ScopeChoices.ORGANIZATION)

        self._run_backfill()

        onb = OrganizationOnboarding.objects.get(organization=org)
        # Must resolve to self.user (super-admin), NOT self.other_user (branch-manager)
        self.assertEqual(onb.owner, self.user)

    def test_owner_resolution_deterministic_tie_breaking(self):
        """When multiple users hold administrative roles, lowest ID provides deterministic tie-breaking."""
        org = Organization.objects.create(name='Tie Org', code='TIE1')
        admin_role = Role.objects.create(organization=org, name='Super Admin', slug='super-admin')
        ur1 = UserRole.objects.create(user=self.user, role=admin_role, scope=ScopeChoices.ORGANIZATION)
        ur2 = UserRole.objects.create(user=self.other_user, role=admin_role, scope=ScopeChoices.ORGANIZATION)

        self._run_backfill()

        onb = OrganizationOnboarding.objects.get(organization=org)
        expected_user = self.user if ur1.id < ur2.id else self.other_user
        self.assertEqual(onb.owner, expected_user)

    def test_owner_resolution_leaves_owner_none_for_non_admin_roles(self):
        """Organizations with only non-administrative roles (e.g. viewer or manager) leave owner as None."""
        org = Organization.objects.create(name='Viewer Only Org', code='VO2')
        viewer_role = Role.objects.create(organization=org, name='Employee Viewer', slug='employee-viewer')
        UserRole.objects.create(user=self.other_user, role=viewer_role, scope=ScopeChoices.ORGANIZATION)

        self._run_backfill()

        onb = OrganizationOnboarding.objects.get(organization=org)
        self.assertIsNone(onb.owner)


class MigrationReversibilityTests(TestCase):
    """Verifies that migration 0014 can be cleanly rolled back and re-applied on a test database."""

    def test_migration_0014_rollback_and_reapply_lifecycle(self):
        from django.core.management import call_command
        from django.db import connection

        # Verify initial state: table exists
        with connection.cursor() as cursor:
            tables = connection.introspection.table_names(cursor)
            self.assertIn('organization_onboarding', tables)

        # 1. Rollback organization app to 0013
        call_command('migrate', 'organization', '0013', verbosity=0)
        with connection.cursor() as cursor:
            tables = connection.introspection.table_names(cursor)
            self.assertNotIn('organization_onboarding', tables)
            self.assertIn('organization_organization', tables)

        # 2. Re-apply organization 0014
        call_command('migrate', 'organization', '0014', verbosity=0)
        with connection.cursor() as cursor:
            tables = connection.introspection.table_names(cursor)
            self.assertIn('organization_onboarding', tables)

