import hashlib
import secrets
from datetime import date, timedelta
from typing import Optional, Set
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction, models
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied, NotAuthenticated
from apps.organization.models import (
    Branch, WorkingCalendar, OrganizationInvitation, InvitationStatus, EmailDeliveryStatus
)
from apps.organization.exceptions import WorkingCalendarConfigurationError
from apps.accounts.models import UserStatus


def _get_holiday_model():
    """Dynamically resolves the Holiday model without creating a static module-level dependency on apps.attendance."""
    return apps.get_model('attendance', 'Holiday')


class WorkingCalendarService:
    """
    Authoritative domain service for branch working calendar evaluations.
    Cross-domain consumers (Attendance, Leave, Payroll) rely on this service
    as the single source of truth for working-day calculations.

    Precedence Hierarchy:
    1. Explicit active Holiday (date is non-working)
    2. Recurring WorkingCalendarRule for matching (weekday, occurrence)
    3. Base WorkingCalendar configured weekdays (work_days)
    """

    @staticmethod
    def is_holiday(branch: Optional[Branch], target_date: date) -> bool:
        """Checks whether target_date is an active holiday for the specified branch."""
        if not branch:
            return False
        Holiday = _get_holiday_model()
        return Holiday.objects.filter(branch=branch, date=target_date, is_active=True).exists()

    @staticmethod
    def is_working_day(branch: Optional[Branch], target_date: date) -> bool:
        """
        Determines whether target_date is a working day for the given branch following strict precedence:
        1. Explicit active Holiday -> Non-working (False)
        2. Recurring WorkingCalendarRule for (weekday, occurrence) -> rule.is_working
        3. Base WorkingCalendar work_days -> weekday in work_days

        Raises WorkingCalendarConfigurationError if branch is None, WorkingCalendar is missing,
        or work_days is unconfigured/invalid. Does NOT fall back to Mon-Fri.
        """
        if not branch:
            raise WorkingCalendarConfigurationError("Branch is required to determine working day.")

        # Precedence 1: Explicit active branch holiday
        if WorkingCalendarService.is_holiday(branch, target_date):
            return False

        # Resolve branch WorkingCalendar
        try:
            wc = getattr(branch, 'working_calendar', None)
        except Exception:
            wc = None
        if not wc:
            raise WorkingCalendarConfigurationError(
                f"Working calendar is not configured for branch {branch.id}."
            )

        # Precedence 2 & 3: Calendar recurring rules and base weekdays
        return wc.is_working_day(target_date)

    @staticmethod
    def count_working_days(
        branch: Optional[Branch],
        start_date: date,
        end_date: date,
        exclude_dates: Optional[Set[date]] = None
    ) -> int:
        """
        Counts working days in the closed interval [start_date, end_date] for the given branch.
        Accounts for active holidays, recurring monthly rules, base work days, and optional excluded dates.
        Evaluates batch date ranges in O(days) time without N+1 queries.

        Raises WorkingCalendarConfigurationError if branch is None or has no WorkingCalendar.
        """
        if not branch:
            raise WorkingCalendarConfigurationError("Branch is required to count working days.")

        if start_date > end_date:
            return 0

        try:
            wc = getattr(branch, 'working_calendar', None)
        except Exception:
            wc = None
        if not wc:
            raise WorkingCalendarConfigurationError(
                f"Working calendar is not configured for branch {branch.id}."
            )

        base_work_days = set(wc.get_work_days_list())
        recurring_rules = wc.get_recurring_rules_dict()

        # Pre-fetch all active holiday dates within the interval
        Holiday = _get_holiday_model()
        holiday_dates = set(
            Holiday.objects.filter(
                branch=branch,
                date__range=[start_date, end_date],
                is_active=True
            ).values_list('date', flat=True)
        )

        working_day_count = 0
        current = start_date
        while current <= end_date:
            # Check exclusions & holidays
            if current in holiday_dates or (exclude_dates and current in exclude_dates):
                current += timedelta(days=1)
                continue

            weekday = current.weekday()
            occurrence = (current.day - 1) // 7 + 1

            # Precedence 2: Recurring rule override
            if (weekday, occurrence) in recurring_rules:
                is_working = recurring_rules[(weekday, occurrence)]
            else:
                # Precedence 3: Base weekday configuration
                is_working = weekday in base_work_days

            if is_working:
                working_day_count += 1

            current += timedelta(days=1)

        return working_day_count


class OrganizationReadinessService:
    """Read-only operational readiness assessment for an organization.

    This is intentionally advisory: it never blocks existing workflows or
    silently creates configuration. It gives administrators a concise view of
    the prerequisites that make attendance, leave, and access reliable.
    """

    @staticmethod
    def assess(organization):
        LeaveType = apps.get_model('leaves', 'LeaveType')
        Role = apps.get_model('authorization', 'Role')
        Shift = apps.get_model('attendance', 'Shift')

        active_branches = Branch.objects.filter(organization=organization, is_active=True)
        branch_ids = list(active_branches.values_list('id', flat=True))
        calendar_branch_ids = set(WorkingCalendar.objects.filter(branch_id__in=branch_ids).exclude(work_days='').values_list('branch_id', flat=True))
        policy_branch_ids = set(
            apps.get_model('organization', 'AttendancePolicy').objects.filter(branch_id__in=branch_ids).values_list('branch_id', flat=True)
        )
        shift_branch_ids = set(Shift.objects.filter(branch_id__in=branch_ids, is_active=True).values_list('branch_id', flat=True))

        def check(key, label, state, detail, path, required=True):
            return {
                'key': key,
                'label': label,
                'state': state,
                'detail': detail,
                'path': path,
                'required': required,
            }

        missing_calendars = len(set(branch_ids) - calendar_branch_ids)
        missing_policies = len(set(branch_ids) - policy_branch_ids)
        missing_shifts = len(set(branch_ids) - shift_branch_ids)
        department_count = sum(branch.departments.filter(is_active=True).count() for branch in active_branches)
        team_count = sum(department.teams.filter(is_active=True).count() for branch in active_branches for department in branch.departments.all())
        designation_count = organization.designations.filter(is_active=True).count()
        leave_type_count = LeaveType.objects.filter(organization=organization, is_active=True).count()
        role_count = Role.objects.filter(organization=organization, is_active=True).count()

        checks = [
            check('branches', 'Active locations', 'ready' if branch_ids else 'action_required', f'{len(branch_ids)} active location(s) configured.', '/admin/branches'),
            check('calendars', 'Working calendars', 'ready' if branch_ids and not missing_calendars else 'action_required', 'Every active location has working days.' if not missing_calendars and branch_ids else f'{missing_calendars} active location(s) need working days.', '/admin/working-calendar'),
            check('attendance_policies', 'Attendance policies', 'ready' if branch_ids and not missing_policies else 'action_required', 'Every active location has an attendance policy.' if not missing_policies and branch_ids else f'{missing_policies} active location(s) need a policy.', '/admin/attendance-policy'),
            check('structure', 'Organization structure', 'ready' if department_count and designation_count else 'action_required', f'{department_count} department(s), {team_count} team(s), and {designation_count} designation(s).', '/admin/departments'),
            check('shifts', 'Shift schedules', 'ready' if branch_ids and not missing_shifts else 'action_required', 'Every active location has an active shift.' if not missing_shifts and branch_ids else f'{missing_shifts} active location(s) do not yet have a shift.', '/admin/shifts', required=True),
            check('roles', 'Roles and access', 'ready' if role_count else 'action_required', f'{role_count} active role(s).', '/admin/roles'),
            check('leave_types', 'Leave configuration', 'ready' if leave_type_count else 'recommended', f'{leave_type_count} active leave type(s). Optional for onboarding; can be configured after launch.', '/admin/leave-types', required=False),
        ]
        required_checks = [item for item in checks if item['required']]
        ready_required = sum(item['state'] == 'ready' for item in required_checks)
        return {
            'organization_id': organization.id,
            'organization_name': organization.name,
            'score': round((ready_required / len(required_checks)) * 100) if required_checks else 0,
            'checks': checks,
        }


class OrganizationOnboardingService:
    """
    Transactional domain service orchestrating the multi-stage Organization Setup Wizard.
    Enforces sequential progression, prevents skipped stages, guarantees stage atomicity,
    prevents cross-tenant access, safely stores metadata drafts, and validates
    prerequisites before finalizing onboarding.
    """

    @classmethod
    def _has_tenant_admin_permission(cls, user, organization):
        """
        Validates whether user has active, unrevoked, unexpired organization-scoped administrative
        privileges for the specified organization via dynamic RBAC (super-admin role or company.manage / organization.manage).
        """
        if not user or not user.is_authenticated or not user.is_active or not organization:
            return False

        from apps.authorization.services import AuthorizationService
        from apps.authorization.models import UserRole, UserPermissionGrant, ScopeChoices

        # 1. Dynamic Super Admin within this specific tenant organization
        if AuthorizationService._is_active_org_superadmin(user, organization):
            return True

        now = timezone.now()

        # 2. Organization-scoped role with company.manage or organization.manage
        has_role_perm = UserRole.objects.filter(
            user=user,
            is_revoked=False,
            scope=ScopeChoices.ORGANIZATION,
            role__is_active=True,
            role__organization=organization,
            role__role_permissions__permission__codename__in=['company.manage', 'organization.manage'],
            role__role_permissions__permission__is_active=True,
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gte=now)
        ).exists()

        if has_role_perm:
            return True

        # 3. Direct grant with organization scope for this organization
        has_direct_grant = UserPermissionGrant.objects.filter(
            user=user,
            is_revoked=False,
            scope=ScopeChoices.ORGANIZATION,
            permission__codename__in=['company.manage', 'organization.manage'],
            permission__is_active=True,
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gte=now)
        ).filter(
            models.Q(branch__organization=organization) |
            models.Q(team__department__branch__organization=organization)
        ).exists()

        return has_direct_grant

    @classmethod
    def resolve_onboarding(cls, user, org_id=None):
        """
        Resolves the active OrganizationOnboarding for the requesting user safely.
        Never trusts client-supplied organization IDs. A global Django superuser does
        NOT automatically bypass tenant isolation. Authorizes access only if user is direct
        onboarding owner or holds valid organization-scoped administrative role/permissions
        in that organization.
        """
        from apps.organization.models import OrganizationOnboarding, Organization
        from apps.authorization.services import AuthorizationService
        from rest_framework.exceptions import PermissionDenied, NotFound

        if not user or not user.is_authenticated or not user.is_active:
            return None

        if org_id is not None:
            onb = OrganizationOnboarding.objects.filter(organization_id=org_id).select_related('organization', 'owner').first()
            if not onb:
                raise NotFound(f"No onboarding session found for organization ID {org_id}.")

            # Verify caller authorization for the specified organization
            if onb.owner_id == user.id:
                return onb
            if cls._has_tenant_admin_permission(user, onb.organization):
                return onb

            raise PermissionDenied("You do not have administrative access to this organization's onboarding.")

        # Default resolution order when org_id is omitted:
        # 1. Linked TenantOwnerRegistration
        reg = getattr(user, 'tenant_owner_registration', None)
        if reg and reg.organization_id:
            onb = OrganizationOnboarding.objects.filter(organization=reg.organization).select_related('organization', 'owner').first()
            if onb:
                return onb

        # 2. Direct Onboarding Owner
        onb = OrganizationOnboarding.objects.filter(owner=user).select_related('organization', 'owner').first()
        if onb:
            return onb

        # 3. User's primary organization (only if user has tenant admin permission in that organization)
        primary_org = AuthorizationService.get_primary_organization(user)
        if primary_org:
            onb = OrganizationOnboarding.objects.filter(organization=primary_org).select_related('organization', 'owner').first()
            if onb and cls._has_tenant_admin_permission(user, primary_org):
                return onb

        return None

    @staticmethod
    def get_status(onboarding):
        """Returns comprehensive onboarding progress payload including diagnostic readiness."""
        readiness = OrganizationReadinessService.assess(onboarding.organization)
        checks = readiness.get('checks', [])
        ready_checks = sum(1 for c in checks if c.get('state') == 'ready')

        return {
            'onboarding_id': onboarding.id,
            'organization_id': onboarding.organization.id,
            'organization_name': onboarding.organization.name,
            'organization_code': onboarding.organization.code,
            'status': onboarding.status,
            'current_stage': onboarding.current_stage,
            'completed_stages': onboarding.completed_stages,
            'completed_at': onboarding.completed_at,
            'metadata': onboarding.metadata or {},
            'readiness_summary': {
                'score': readiness.get('score', 0),
                'total_checks': len(checks),
                'ready_checks': ready_checks,
            },
        }

    @staticmethod
    def validate_prerequisites(onboarding, target_stage):
        """Enforces that all stages preceding target_stage are completed and onboarding is active."""
        from apps.organization.models import OnboardingStatus
        from rest_framework.exceptions import ValidationError

        if onboarding.status == OnboardingStatus.COMPLETED:
            raise ValidationError("Onboarding is already completed for this organization.")

        completed = set(onboarding.completed_stages or [])
        required = list(range(1, target_stage))
        missing = [s for s in required if s not in completed]
        if missing:
            names = [f"Stage {s} ({onboarding.STAGE_NAMES.get(s, '')})" for s in missing]
            raise ValidationError(
                f"Cannot advance to Stage {target_stage}. Preceding stages must be completed first: {', '.join(names)}."
            )

    @staticmethod
    def revalidate_persisted_prerequisites(organization):
        """
        Directly validates database records for all 6 prerequisite stages before Stage 7 completion.
        Guarantees that database integrity is proven and no step was spoofed.
        """
        from apps.organization.models import Branch, Department, Designation, WorkingCalendar
        from apps.attendance.models import Shift
        from apps.authorization.models import UserRole
        from apps.accounts.models import TenantOwnerRegistration
        from rest_framework.exceptions import ValidationError

        has_branches = Branch.objects.filter(organization=organization, is_active=True).exists()
        if not has_branches:
            raise ValidationError({"branches": "Stage 2 incomplete: At least one active branch is required."})

        has_depts = Department.objects.filter(branch__organization=organization, branch__is_active=True, is_active=True).exists()
        has_desigs = Designation.objects.filter(organization=organization, is_active=True).exists()
        if not (has_depts and has_desigs):
            raise ValidationError({"structure": "Stage 3 incomplete: Both active departments and designations are required."})

        has_calendar = WorkingCalendar.objects.filter(branch__organization=organization, branch__is_active=True).exclude(work_days='').exists()
        if not has_calendar:
            raise ValidationError({"calendar": "Stage 4 incomplete: Active branch must have a configured working calendar."})

        has_shift = Shift.objects.filter(branch__organization=organization, branch__is_active=True, is_active=True).exists()
        if not has_shift:
            raise ValidationError({"shift": "Stage 5 incomplete: Active branch must have an active shift schedule."})

        now = timezone.now()
        has_admin_role = UserRole.objects.filter(
            role__organization=organization,
            scope='organization',
            is_revoked=False,
            role__is_active=True,
            user__status='active',
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gte=now)
        ).filter(
            models.Q(role__slug__in=['super-admin', 'organization-owner', 'company-admin', 'admin', 'owner', 'tenant-admin']) |
            models.Q(role__name__icontains='owner') |
            models.Q(role__name__icontains='super admin')
        ).exists()

        has_reg = TenantOwnerRegistration.objects.filter(
            organization=organization,
            user__isnull=False,
            user__status='active',
        ).exists()

        has_pending_invitation = OrganizationInvitation.objects.filter(
            organization=organization,
            status=InvitationStatus.PENDING,
        ).exists()

        if not (has_admin_role or has_reg or has_pending_invitation):
            raise ValidationError({"admin": "Stage 6 incomplete: Organization must have an active, organization-scoped administrator or pending invitation."})

    @classmethod
    def execute_stage_1(cls, user, validated_data, request=None):
        """
        Stage 1: Organization Details.
        Initializes tenant organization and creates durable onboarding session.
        """
        from apps.organization.models import Organization, OrganizationOnboarding, OnboardingStatus
        from apps.audit.services import AuditService
        from rest_framework.exceptions import ValidationError

        # Limit check: self-service owner may only create one tenant
        registration = getattr(user, 'tenant_owner_registration', None)
        if not user.is_superuser:
            if not registration or not registration.can_launch_organization:
                raise ValidationError("You are not authorized to launch a new organization or have already launched one.")

        name = validated_data['name'].strip()
        code = validated_data.get('code', '').strip() or None

        if Organization.objects.filter(name__iexact=name).exists():
            raise ValidationError({"name": "An organization with this name already exists."})
        if code and Organization.objects.filter(code__iexact=code).exists():
            raise ValidationError({"code": "An organization with this code already exists."})

        with transaction.atomic():
            org = Organization.objects.create(name=name, code=code, status='active')

            # Update auto-provisioned branding
            branding = getattr(org, 'branding', None)
            if branding:
                if 'currency_code' in validated_data and validated_data['currency_code']:
                    branding.currency_code = validated_data['currency_code']
                if 'date_format' in validated_data and validated_data['date_format']:
                    branding.date_format = validated_data['date_format']
                branding.save(update_fields=['currency_code', 'date_format'])

            onboarding = OrganizationOnboarding.objects.create(
                organization=org,
                owner=user,
                status=OnboardingStatus.IN_PROGRESS,
                current_stage=2,
                completed_stages=[1],
                metadata={'stage_1': {
                    'name': name,
                    'code': code,
                    'currency_code': validated_data.get('currency_code', 'INR'),
                    'date_format': validated_data.get('date_format', 'DD/MM/YYYY'),
                    'timezone': validated_data.get('timezone', 'UTC'),
                }}
            )

            if registration:
                registration.organization = org
                registration.save(update_fields=['organization'])

            AuditService.log(
                action='onboarding_stage_1_completed',
                actor=user,
                target_type='organization_onboarding',
                target_id=onboarding.id,
                metadata={'organization_id': org.id, 'stage': 1},
                request=request,
                organization=org,
            )

        return onboarding, org

    @classmethod
    def execute_stage_2(cls, onboarding, user, validated_data, request=None):
        """
        Stage 2: Initial Branch (Head Office).
        Configures head office branch location. Auto-attaches calendar and attendance policy via signals.
        """
        from apps.organization.models import Branch
        from apps.audit.services import AuditService

        cls.validate_prerequisites(onboarding, 2)
        org = onboarding.organization

        with transaction.atomic():
            branch_name = validated_data['name'].strip()
            branch_code = validated_data.get('code', '').strip() or None

            branch = Branch.objects.filter(organization=org, is_head_office=True).first()
            if not branch:
                branch = Branch(organization=org, is_head_office=True)

            branch.name = branch_name
            branch.code = branch_code
            branch.address_line1 = validated_data.get('address_line1', '')
            branch.address_line2 = validated_data.get('address_line2', '')
            branch.city = validated_data.get('city', '')
            branch.state = validated_data.get('state', '')
            branch.country = validated_data.get('country', '')
            branch.postal_code = validated_data.get('postal_code', '')
            branch.timezone = validated_data.get('timezone', 'UTC')
            if 'latitude' in validated_data and validated_data['latitude'] is not None:
                branch.latitude = validated_data['latitude']
            if 'longitude' in validated_data and validated_data['longitude'] is not None:
                branch.longitude = validated_data['longitude']
            branch.radius = validated_data.get('radius', 100.0)
            branch.is_active = True
            branch.full_clean()
            branch.save()

            onboarding.mark_stage_complete(2)
            meta = onboarding.metadata or {}
            meta['stage_2'] = {
                'branch_id': branch.id,
                'name': branch.name,
                'code': branch.code,
                'city': branch.city,
            }
            onboarding.metadata = meta
            onboarding.save(update_fields=['metadata', 'updated_at'])

            AuditService.log(
                action='onboarding_stage_2_completed',
                actor=user,
                target_type='organization_onboarding',
                target_id=onboarding.id,
                metadata={'branch_id': branch.id, 'stage': 2},
                request=request,
                organization=org,
            )

        return onboarding, branch

    @classmethod
    def execute_stage_3(cls, onboarding, user, validated_data, request=None):
        """
        Stage 3: Organizational Structure.
        Creates initial departments (branch-scoped) and designations (org-scoped).
        """
        from apps.organization.models import Branch, Department, Designation
        from apps.audit.services import AuditService
        from rest_framework.exceptions import ValidationError

        cls.validate_prerequisites(onboarding, 3)
        org = onboarding.organization
        head_office = Branch.objects.filter(organization=org, is_head_office=True, is_active=True).first()
        if not head_office:
            head_office = Branch.objects.filter(organization=org, is_active=True).first()
        if not head_office:
            raise ValidationError("No active branch found. Please complete Stage 2 first.")

        departments_data = validated_data['departments']
        designations_data = validated_data['designations']

        with transaction.atomic():
            created_depts = []
            for d in departments_data:
                dept_name = d['name'].strip()
                dept_code = d.get('code', '').strip() or None
                dept, _ = Department.objects.update_or_create(
                    branch=head_office,
                    name=dept_name,
                    defaults={
                        'code': dept_code,
                        'description': d.get('description', ''),
                        'is_active': True,
                    }
                )
                created_depts.append(dept)

            created_desigs = []
            for desig in designations_data:
                desig_name = desig['name'].strip()
                desig_code = desig.get('code', '').strip() or None
                des, _ = Designation.objects.update_or_create(
                    organization=org,
                    name=desig_name,
                    defaults={
                        'code': desig_code,
                        'level': desig.get('level'),
                        'is_active': True,
                    }
                )
                created_desigs.append(des)

            onboarding.mark_stage_complete(3)
            meta = onboarding.metadata or {}
            meta['stage_3'] = {
                'department_count': len(created_depts),
                'designation_count': len(created_desigs),
            }
            onboarding.metadata = meta
            onboarding.save(update_fields=['metadata', 'updated_at'])

            AuditService.log(
                action='onboarding_stage_3_completed',
                actor=user,
                target_type='organization_onboarding',
                target_id=onboarding.id,
                metadata={'departments_count': len(created_depts), 'designations_count': len(created_desigs), 'stage': 3},
                request=request,
                organization=org,
            )

        return onboarding, created_depts, created_desigs

    @classmethod
    def execute_stage_4(cls, onboarding, user, validated_data, request=None):
        """
        Stage 4: Working Calendar & Holidays.
        Updates base work days, recurring rules, and branch holidays.
        """
        from apps.organization.models import Branch, WorkingCalendar, WorkingCalendarRule
        from apps.attendance.models import Holiday
        from apps.audit.services import AuditService
        from rest_framework.exceptions import ValidationError

        cls.validate_prerequisites(onboarding, 4)
        org = onboarding.organization
        head_office = Branch.objects.filter(organization=org, is_head_office=True, is_active=True).first()
        if not head_office:
            head_office = Branch.objects.filter(organization=org, is_active=True).first()
        if not head_office:
            raise ValidationError("No active branch found. Please complete Stage 2 first.")

        with transaction.atomic():
            wc, _ = WorkingCalendar.objects.get_or_create(branch=head_office)
            wc.work_days = validated_data['work_days']
            wc.full_clean()
            wc.save()

            if 'recurring_rules' in validated_data and validated_data['recurring_rules'] is not None:
                wc.recurring_rules.all().delete()
                for rule_data in validated_data['recurring_rules']:
                    r = WorkingCalendarRule(working_calendar=wc, **rule_data)
                    r.full_clean()
                    r.save()

            if 'holidays' in validated_data and validated_data['holidays']:
                for h_data in validated_data['holidays']:
                    h_name = h_data['name'].strip()
                    h_date = h_data['date']
                    Holiday.objects.update_or_create(
                        branch=head_office,
                        date=h_date,
                        defaults={
                            'name': h_name,
                            'holiday_type': h_data.get('holiday_type', 'public'),
                            'is_active': True,
                        }
                    )

            onboarding.mark_stage_complete(4)
            meta = onboarding.metadata or {}
            meta['stage_4'] = {
                'work_days': wc.work_days,
                'recurring_rules_count': wc.recurring_rules.count(),
                'holidays_count': head_office.holidays.count(),
            }
            onboarding.metadata = meta
            onboarding.save(update_fields=['metadata', 'updated_at'])

            AuditService.log(
                action='onboarding_stage_4_completed',
                actor=user,
                target_type='organization_onboarding',
                target_id=onboarding.id,
                metadata={'calendar_id': wc.id, 'stage': 4},
                request=request,
                organization=org,
            )

        return onboarding, wc

    @classmethod
    def execute_stage_5(cls, onboarding, user, validated_data, request=None):
        """
        Stage 5: Shift & Attendance Policy.
        Configures active work shift (satisfying single-active-shift invariant) and GPS/IP attendance rules.
        """
        from apps.organization.models import Branch, AttendancePolicy, OfficeNetwork
        from apps.attendance.models import Shift
        from apps.audit.services import AuditService
        from rest_framework.exceptions import ValidationError

        cls.validate_prerequisites(onboarding, 5)
        org = onboarding.organization
        head_office = Branch.objects.filter(organization=org, is_head_office=True, is_active=True).first()
        if not head_office:
            head_office = Branch.objects.filter(organization=org, is_active=True).first()
        if not head_office:
            raise ValidationError("No active branch found. Please complete Stage 2 first.")

        shift_data = validated_data['shift']
        policy_data = validated_data.get('attendance_policy', {})
        network_data = validated_data.get('office_network')

        with transaction.atomic():
            # Update existing active shift or create new
            existing_shift = Shift.objects.filter(branch=head_office, is_active=True).first()
            if not existing_shift:
                existing_shift = Shift(branch=head_office, is_active=True)

            existing_shift.name = shift_data.get('name', 'General Shift')
            existing_shift.code = shift_data.get('code', '').strip() or None
            existing_shift.start_time = shift_data['start_time']
            existing_shift.end_time = shift_data['end_time']
            if 'grace_period_minutes' in shift_data and shift_data['grace_period_minutes'] is not None:
                existing_shift.grace_period = timedelta(minutes=shift_data['grace_period_minutes'])
            if 'work_days' in shift_data and shift_data['work_days']:
                existing_shift.work_days = shift_data['work_days']
            existing_shift.is_active = True
            existing_shift.clean()
            existing_shift.save()

            if policy_data:
                ap, _ = AttendancePolicy.objects.get_or_create(branch=head_office)
                for k, v in policy_data.items():
                    setattr(ap, k, v)
                ap.save()

            if network_data:
                OfficeNetwork.objects.update_or_create(
                    branch=head_office,
                    name=network_data['name'].strip(),
                    defaults={
                        'network': network_data['network'].strip(),
                        'description': network_data.get('description', ''),
                        'is_active': True,
                    }
                )

            onboarding.mark_stage_complete(5)
            meta = onboarding.metadata or {}
            meta['stage_5'] = {
                'shift_id': existing_shift.id,
                'shift_name': existing_shift.name,
                'start_time': str(existing_shift.start_time),
                'end_time': str(existing_shift.end_time),
            }
            onboarding.metadata = meta
            onboarding.save(update_fields=['metadata', 'updated_at'])

            AuditService.log(
                action='onboarding_stage_5_completed',
                actor=user,
                target_type='organization_onboarding',
                target_id=onboarding.id,
                metadata={'shift_id': existing_shift.id, 'stage': 5},
                request=request,
                organization=org,
            )

        return onboarding, existing_shift

    @classmethod
    def execute_stage_6(cls, onboarding, user, validated_data=None, request=None):
        """
        Stage 6: Initial Administrator & RBAC.
        Option A: Self-assignment to organization-scoped Super Admin role.
        Option B: Email invitation to another intended administrator.
        """
        from apps.authorization.models import Permission, Role, RolePermission, ScopeChoices, UserRole
        from apps.audit.services import AuditService

        cls.validate_prerequisites(onboarding, 6)
        org = onboarding.organization
        validated_data = validated_data or {}
        assignment_type = validated_data.get('assignment_type', 'self')

        with transaction.atomic():
            super_admin_role, _ = Role.objects.get_or_create(
                organization=org,
                slug='super-admin',
                defaults={
                    'name': 'Super Admin',
                    'description': 'Full administrative access within this organization only.',
                    'is_system': True,
                    'is_active': True,
                }
            )

            # Ensure canonical permissions are attached
            existing_perm_ids = set(super_admin_role.role_permissions.values_list('permission_id', flat=True))
            all_active_perms = Permission.objects.filter(is_active=True)
            missing_perms = [
                RolePermission(role=super_admin_role, permission=p)
                for p in all_active_perms if p.id not in existing_perm_ids
            ]
            if missing_perms:
                RolePermission.objects.bulk_create(missing_perms)

            if assignment_type == 'self':
                target_admin = onboarding.owner or user

                # Assign UserRole if not already assigned
                ur = UserRole.objects.filter(
                    user=target_admin,
                    role=super_admin_role,
                    scope=ScopeChoices.ORGANIZATION,
                ).first()

                if not ur:
                    UserRole.objects.create(
                        user=target_admin,
                        role=super_admin_role,
                        scope=ScopeChoices.ORGANIZATION,
                        assigned_by=user,
                        is_revoked=False,
                    )
                elif ur.is_revoked:
                    ur.is_revoked = False
                    ur.save(update_fields=['is_revoked'])

                # Revoke any outstanding pending invitation for this role to maintain uniqueness
                OrganizationInvitation.objects.filter(
                    organization=org,
                    role=super_admin_role,
                    status=InvitationStatus.PENDING,
                ).update(status=InvitationStatus.REVOKED, revoked_at=timezone.now())

                if not onboarding.owner_id:
                    onboarding.owner = target_admin

                onboarding.mark_stage_complete(6)
                meta = onboarding.metadata or {}
                meta['stage_6'] = {
                    'assignment_type': 'self',
                    'role_id': super_admin_role.id,
                    'admin_user_id': target_admin.id,
                    'admin_email': target_admin.email,
                    'status': 'active',
                }
                onboarding.metadata = meta
                onboarding.save(update_fields=['metadata', 'owner', 'updated_at'])

                AuditService.log(
                    action='onboarding_stage_6_completed',
                    actor=user,
                    target_type='organization_onboarding',
                    target_id=onboarding.id,
                    metadata={'role_id': super_admin_role.id, 'admin_user_id': target_admin.id, 'stage': 6, 'assignment_type': 'self'},
                    request=request,
                    organization=org,
                )
                return onboarding, super_admin_role

            elif assignment_type == 'invite':
                invitee_email = validated_data['email'].strip().lower()
                invitee_first_name = validated_data.get('first_name', '').strip()
                invitee_last_name = validated_data.get('last_name', '').strip()

                # Revoke any prior pending invitation for this role in this organization
                OrganizationInvitation.objects.filter(
                    organization=org,
                    role=super_admin_role,
                    status=InvitationStatus.PENDING,
                ).update(status=InvitationStatus.REVOKED, revoked_at=timezone.now())

                # Generate secure single-use token and store SHA-256 hash only
                raw_token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
                expiry_days = getattr(settings, 'ORGANIZATION_INVITATION_EXPIRY_DAYS', 7)
                expires_at = timezone.now() + timedelta(days=expiry_days)

                invitation = OrganizationInvitation.objects.create(
                    organization=org,
                    email=invitee_email,
                    first_name=invitee_first_name,
                    last_name=invitee_last_name,
                    role=super_admin_role,
                    token_hash=token_hash,
                    status=InvitationStatus.PENDING,
                    email_delivery_status=EmailDeliveryStatus.PENDING,
                    invited_by=user,
                    expires_at=expires_at,
                )

                onboarding.mark_stage_complete(6)
                meta = onboarding.metadata or {}
                meta['stage_6'] = {
                    'assignment_type': 'invite',
                    'role_id': super_admin_role.id,
                    'invitation_id': invitation.id,
                    'invitee_email': invitation.email,
                    'invitee_name': f"{invitation.first_name} {invitation.last_name}".strip(),
                    'invitation_status': invitation.status,
                    'email_delivery_status': invitation.email_delivery_status,
                    'expires_at': invitation.expires_at.isoformat(),
                }
                onboarding.metadata = meta
                onboarding.save(update_fields=['metadata', 'updated_at'])

                AuditService.log(
                    action='onboarding_stage_6_completed',
                    actor=user,
                    target_type='organization_onboarding',
                    target_id=onboarding.id,
                    metadata={
                        'role_id': super_admin_role.id,
                        'stage': 6,
                        'assignment_type': 'invite',
                        'invitation_id': invitation.id,
                        'recipient_email': invitation.email,
                    },
                    request=request,
                    organization=org,
                )

                # Dispatch email strictly post-commit
                transaction.on_commit(lambda: cls._dispatch_invitation_email(invitation.id, raw_token))

                return onboarding, invitation

    @classmethod
    def resend_stage_6_invitation(cls, onboarding, user, request=None):
        """
        Resends an active pending invitation for this organization's administrator.
        Rotates the token, resets the expiration timer, and dispatches fresh email post-commit.
        """
        from apps.audit.services import AuditService
        org = onboarding.organization
        with transaction.atomic():
            invitation = OrganizationInvitation.objects.select_for_update().filter(
                organization=org,
                status=InvitationStatus.PENDING,
            ).first()

            if not invitation:
                raise ValidationError({"detail": "No active pending administrator invitation found to resend."})

            raw_token = secrets.token_urlsafe(32)
            invitation.token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
            expiry_days = getattr(settings, 'ORGANIZATION_INVITATION_EXPIRY_DAYS', 7)
            invitation.expires_at = timezone.now() + timedelta(days=expiry_days)
            invitation.resend_count += 1
            invitation.email_delivery_status = EmailDeliveryStatus.PENDING
            invitation.email_delivery_error = ''
            invitation.save(update_fields=[
                'token_hash', 'expires_at', 'resend_count',
                'email_delivery_status', 'email_delivery_error', 'updated_at'
            ])

            meta = onboarding.metadata or {}
            if 'stage_6' in meta:
                meta['stage_6']['expires_at'] = invitation.expires_at.isoformat()
                meta['stage_6']['resend_count'] = invitation.resend_count
                meta['stage_6']['email_delivery_status'] = invitation.email_delivery_status
                onboarding.metadata = meta
                onboarding.save(update_fields=['metadata', 'updated_at'])

            AuditService.log(
                action='organization_invitation_resent',
                actor=user,
                target_type='organization_invitation',
                target_id=invitation.id,
                metadata={'invitation_id': invitation.id, 'recipient_email': invitation.email, 'resend_count': invitation.resend_count},
                request=request,
                organization=org,
            )

            transaction.on_commit(lambda: cls._dispatch_invitation_email(invitation.id, raw_token))
            return invitation

    @classmethod
    def revoke_stage_6_invitation(cls, onboarding, user, request=None):
        """
        Revokes an active pending administrator invitation.
        """
        from apps.audit.services import AuditService
        org = onboarding.organization
        with transaction.atomic():
            invitation = OrganizationInvitation.objects.select_for_update().filter(
                organization=org,
                status=InvitationStatus.PENDING,
            ).first()

            if not invitation:
                raise ValidationError({"detail": "No active pending administrator invitation found to revoke."})

            invitation.status = InvitationStatus.REVOKED
            invitation.revoked_at = timezone.now()
            invitation.save(update_fields=['status', 'revoked_at', 'updated_at'])

            meta = onboarding.metadata or {}
            if 'stage_6' in meta:
                meta['stage_6']['invitation_status'] = InvitationStatus.REVOKED
                onboarding.metadata = meta
                onboarding.save(update_fields=['metadata', 'updated_at'])

            AuditService.log(
                action='organization_invitation_revoked',
                actor=user,
                target_type='organization_invitation',
                target_id=invitation.id,
                metadata={'invitation_id': invitation.id, 'recipient_email': invitation.email},
                request=request,
                organization=org,
            )
            return invitation

    @classmethod
    def _dispatch_invitation_email(cls, invitation_id, raw_token):
        """
        Asynchronously dispatches the invitation email post-commit.
        Updates email_delivery_status without disrupting the transaction.
        """
        from apps.notifications.services import NotificationService
        invitation = OrganizationInvitation.objects.filter(id=invitation_id).select_related('organization', 'invited_by').first()
        if not invitation:
            return

        inviter_name = invitation.invited_by.get_full_name() if invitation.invited_by else "BeyondSure Team"
        try:
            sent = NotificationService.send_organization_admin_invitation_email(
                recipient_email=invitation.email,
                recipient_name=invitation.first_name or invitation.email,
                organization_name=invitation.organization.name,
                raw_token=raw_token,
                inviter_name=inviter_name,
            )
            error_msg = '' if sent else 'SMTP dispatch failed. Please retry.'
        except Exception as e:
            sent = False
            error_msg = str(e)

        invitation.email_delivery_status = EmailDeliveryStatus.SENT if sent else EmailDeliveryStatus.FAILED
        if sent:
            invitation.email_sent_at = timezone.now()
            invitation.email_delivery_error = ''
        else:
            invitation.email_delivery_error = error_msg
        invitation.save(update_fields=['email_delivery_status', 'email_delivery_error', 'email_sent_at', 'updated_at'])

        # Synchronize stage 6 metadata if applicable
        onboarding = getattr(invitation.organization, 'onboarding', None)
        if onboarding and onboarding.metadata and 'stage_6' in onboarding.metadata:
            if onboarding.metadata['stage_6'].get('invitation_id') == invitation.id:
                onboarding.metadata['stage_6']['email_delivery_status'] = invitation.email_delivery_status
                onboarding.save(update_fields=['metadata', 'updated_at'])

    @classmethod
    def verify_invitation_token(cls, raw_token):
        """
        Validates an invitation token hash.
        Does NOT disclose whether arbitrary accounts exist.
        """
        if not raw_token or not raw_token.strip():
            raise ValidationError({"detail": "Invitation token is required."}, code='INVALID_TOKEN')

        token_hash = hashlib.sha256(raw_token.strip().encode('utf-8')).hexdigest()
        invitation = OrganizationInvitation.objects.filter(token_hash=token_hash).select_related('organization', 'role').first()

        if not invitation:
            raise ValidationError({"detail": "Invalid or expired invitation token."}, code='INVALID_TOKEN')

        if invitation.status != InvitationStatus.PENDING:
            if invitation.status == InvitationStatus.ACCEPTED:
                raise ValidationError({"detail": "This invitation has already been accepted."}, code='ALREADY_ACCEPTED')
            raise ValidationError({"detail": f"This invitation is {invitation.status} and cannot be used."}, code='INVALID_TOKEN')

        if invitation.is_expired():
            invitation.status = InvitationStatus.EXPIRED
            invitation.save(update_fields=['status', 'updated_at'])
            raise ValidationError({"detail": "This invitation has expired."}, code='TOKEN_EXPIRED')

        return invitation

    @classmethod
    def accept_invitation(cls, raw_token, authenticated_user=None, password=None, first_name='', last_name='', request=None):
        """
        Atomically accepts an invitation.
        Strictly enforces account state rules:
        - Active account: must be authenticated via canonical login with matching email.
        - Inactive account: rejected (403).
        - Invited account: requires password to activate.
        - New account: creates active user with validated password.
        Zero DRF tokens issued from this method.
        """
        from apps.authorization.models import ScopeChoices, UserRole
        from apps.audit.services import AuditService
        User = get_user_model()

        if not raw_token or not raw_token.strip():
            raise ValidationError({"detail": "Invitation token is required."}, code='INVALID_TOKEN')

        token_hash = hashlib.sha256(raw_token.strip().encode('utf-8')).hexdigest()

        with transaction.atomic():
            invitation = OrganizationInvitation.objects.select_for_update().filter(
                token_hash=token_hash
            ).select_related('organization', 'role').first()

            if not invitation:
                raise ValidationError({"detail": "Invalid or expired invitation token."}, code='INVALID_TOKEN')

            if invitation.status != InvitationStatus.PENDING:
                if invitation.status == InvitationStatus.ACCEPTED:
                    raise ValidationError({"detail": "This invitation has already been accepted."}, code='ALREADY_ACCEPTED')
                raise ValidationError({"detail": f"This invitation is {invitation.status} and cannot be used."}, code='INVALID_TOKEN')

            if invitation.is_expired():
                invitation.status = InvitationStatus.EXPIRED
                invitation.save(update_fields=['status', 'updated_at'])
                raise ValidationError({"detail": "This invitation has expired."}, code='TOKEN_EXPIRED')

            target_email = invitation.email.strip().lower()
            existing_user = User.objects.filter(email=target_email).first()

            if existing_user:
                if existing_user.status == UserStatus.INACTIVE:
                    raise PermissionDenied("This user account is inactive or suspended. Please contact support.")

                if existing_user.status == UserStatus.ACTIVE:
                    if not authenticated_user or not authenticated_user.is_authenticated:
                        raise NotAuthenticated("An account for this email already exists. Please log in before accepting.")
                    if authenticated_user.email.strip().lower() != target_email:
                        raise PermissionDenied("You are currently authenticated as a different user. Please switch accounts to accept this invitation.")
                    target_user = existing_user

                elif existing_user.status == UserStatus.INVITED:
                    if not password:
                        raise ValidationError({"password": ["Password is required to activate this account."]})
                    try:
                        validate_password(password, user=existing_user)
                    except DjangoValidationError as e:
                        raise ValidationError({"password": list(e.messages)})
                    existing_user.set_password(password)
                    existing_user.status = UserStatus.ACTIVE
                    if first_name and not existing_user.first_name:
                        existing_user.first_name = first_name.strip()
                    if last_name and not existing_user.last_name:
                        existing_user.last_name = last_name.strip()
                    existing_user.save()
                    target_user = existing_user
                else:
                    raise PermissionDenied(f"Account in state '{existing_user.status}' cannot accept invitations.")
            else:
                if not password:
                    raise ValidationError({"password": ["Password is required to create your administrator account."]})
                try:
                    validate_password(password)
                except DjangoValidationError as e:
                    raise ValidationError({"password": list(e.messages)})
                target_user = User.objects.create_user(
                    email=target_email,
                    password=password,
                    first_name=(first_name or invitation.first_name).strip(),
                    last_name=(last_name or invitation.last_name).strip(),
                    status=UserStatus.ACTIVE,
                )

            # Assign organization-scoped super-admin role
            ur, created = UserRole.objects.get_or_create(
                user=target_user,
                role=invitation.role,
                scope=ScopeChoices.ORGANIZATION,
                defaults={
                    'assigned_by': invitation.invited_by,
                    'is_revoked': False,
                }
            )
            if not created and ur.is_revoked:
                ur.is_revoked = False
                ur.save(update_fields=['is_revoked'])

            # Mark invitation accepted
            invitation.status = InvitationStatus.ACCEPTED
            invitation.accepted_by = target_user
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=['status', 'accepted_by', 'accepted_at', 'updated_at'])

            # Update stage 6 onboarding metadata if matching
            onboarding = getattr(invitation.organization, 'onboarding', None)
            if onboarding and onboarding.metadata and 'stage_6' in onboarding.metadata:
                if onboarding.metadata['stage_6'].get('invitation_id') == invitation.id:
                    onboarding.metadata['stage_6']['invitation_status'] = InvitationStatus.ACCEPTED
                    onboarding.metadata['stage_6']['admin_user_id'] = target_user.id
                    onboarding.save(update_fields=['metadata', 'updated_at'])

            AuditService.log(
                action='organization_invitation_accepted',
                actor=target_user,
                target_type='organization_invitation',
                target_id=invitation.id,
                metadata={'email': invitation.email, 'role_slug': invitation.role.slug, 'user_id': target_user.id},
                request=request,
                organization=invitation.organization,
            )

            return invitation, target_user

    @classmethod
    def execute_stage_7(cls, onboarding, user, request=None):
        """
        Stage 7: Review & Complete.
        Re-validates database records for all preceding stages, transitions onboarding to COMPLETED,
        marks the organization active, and returns advisory readiness diagnostics.
        """
        from apps.organization.models import OnboardingStatus
        from apps.audit.services import AuditService
        from rest_framework.exceptions import ValidationError

        if onboarding.status == OnboardingStatus.COMPLETED:
            # Idempotent response: ensure organization is marked active and return existing completed state
            org = onboarding.organization
            if org.status != 'active':
                org.status = 'active'
                org.save(update_fields=['status', 'updated_at'])
            readiness = OrganizationReadinessService.assess(org)
            return onboarding, readiness

        if onboarding.status == OnboardingStatus.ABANDONED:
            raise ValidationError("Cannot activate an abandoned onboarding session.")

        completed_set = set(onboarding.completed_stages or [])
        if not set(range(1, 7)).issubset(completed_set):
            missing = [s for s in range(1, 7) if s not in completed_set]
            raise ValidationError(f"Cannot finalize setup. Missing preceding stages: {missing}.")

        # Direct database integrity re-validation
        cls.revalidate_persisted_prerequisites(onboarding.organization)

        with transaction.atomic():
            onboarding.mark_completed()
            org = onboarding.organization
            org.status = 'active'
            org.save(update_fields=['status', 'updated_at'])

            meta = onboarding.metadata or {}
            meta['stage_7'] = {
                'completed_at': onboarding.completed_at.isoformat() if onboarding.completed_at else timezone.now().isoformat(),
            }
            onboarding.metadata = meta
            onboarding.save(update_fields=['metadata', 'updated_at'])

            AuditService.log(
                action='organization_activated',
                actor=user,
                target_type='organization',
                target_id=org.id,
                metadata={'organization_id': org.id, 'onboarding_id': onboarding.id},
                request=request,
                organization=org,
            )

            AuditService.log(
                action='organization_onboarding_completed',
                actor=user,
                target_type='organization_onboarding',
                target_id=onboarding.id,
                metadata={'organization_id': org.id},
                request=request,
                organization=org,
            )

        readiness = OrganizationReadinessService.assess(onboarding.organization)
        return onboarding, readiness

    @classmethod
    def save_draft(cls, onboarding, user, stage_number, draft_data, request=None):
        """Saves non-sensitive workflow step draft data without advancing stage."""
        from apps.organization.models import validate_onboarding_metadata
        from apps.audit.services import AuditService
        from rest_framework.exceptions import ValidationError
        from django.core.exceptions import ValidationError as DjangoValidationError

        try:
            validate_onboarding_metadata(draft_data)
        except DjangoValidationError as e:
            raise ValidationError(e.messages if hasattr(e, 'messages') else str(e))

        meta = onboarding.metadata or {}
        drafts = meta.get('drafts', {})
        drafts[str(stage_number)] = draft_data
        meta['drafts'] = drafts
        onboarding.metadata = meta
        onboarding.save(update_fields=['metadata', 'updated_at'])

        AuditService.log(
            action='onboarding_draft_saved',
            actor=user,
            target_type='organization_onboarding',
            target_id=onboarding.id,
            metadata={'stage': stage_number},
            request=request,
            organization=onboarding.organization,
        )

        return onboarding

