from django.utils import timezone
from .models import Permission, UserRole, UserPermissionGrant, ScopeChoices
from apps.organization.models import Branch
from django.db.models import Q

class AuthorizationService:
    @staticmethod
    def get_primary_organization(request_or_user):
        """Return the current organization context for the request."""
        return AuthorizationService._resolve_organization(request_or_user)

    @staticmethod
    def get_effective_permissions(request_or_user, organization=None, branch_id=None, team_id=None, global_only=False):
        user = request_or_user.user if hasattr(request_or_user, 'user') else request_or_user
        organization = AuthorizationService._resolve_organization(request_or_user, organization)
        
        if not getattr(user, 'is_authenticated', False):
            return set()
        if not getattr(user, 'is_active', False):
            return set()
        if not organization:
            return set()

        if user.is_superuser:
            return set(Permission.objects.filter(is_active=True).values_list('codename', flat=True))

        now = timezone.now()

        role_filter = Q(
            is_active=True,
            role_permissions__role__is_active=True,
            role_permissions__role__organization=organization,
            role_permissions__role__user_roles__user=user,
            role_permissions__role__user_roles__is_revoked=False,
        ) & (Q(role_permissions__role__user_roles__expires_at__isnull=True) | Q(role_permissions__role__user_roles__expires_at__gte=now))

        grant_filter = Q(
            is_active=True,
            direct_grants__user=user,
            direct_grants__is_revoked=False,
        ) & (Q(direct_grants__expires_at__isnull=True) | Q(direct_grants__expires_at__gte=now))

        if team_id:
            from apps.organization.models import Team
            team = Team.objects.filter(id=team_id).select_related('department__branch').first()
            inferred_branch_id = team.department.branch_id if team else None
            
            role_scope = Q(role_permissions__role__user_roles__scope=ScopeChoices.ORGANIZATION) | \
                         Q(role_permissions__role__user_roles__scope=ScopeChoices.BRANCH, role_permissions__role__user_roles__branch_id=inferred_branch_id) | \
                         Q(role_permissions__role__user_roles__scope=ScopeChoices.TEAM, role_permissions__role__user_roles__team_id=team_id)
                         
            grant_scope = Q(direct_grants__scope=ScopeChoices.ORGANIZATION) | \
                          Q(direct_grants__scope=ScopeChoices.BRANCH, direct_grants__branch_id=inferred_branch_id) | \
                          Q(direct_grants__scope=ScopeChoices.TEAM, direct_grants__team_id=team_id)
                          
            role_filter &= role_scope
            grant_filter &= grant_scope
            
        elif branch_id:
            role_scope = Q(role_permissions__role__user_roles__scope=ScopeChoices.ORGANIZATION) | \
                         Q(role_permissions__role__user_roles__scope=ScopeChoices.BRANCH, role_permissions__role__user_roles__branch_id=branch_id)
            grant_scope = Q(direct_grants__scope=ScopeChoices.ORGANIZATION) | \
                          Q(direct_grants__scope=ScopeChoices.BRANCH, direct_grants__branch_id=branch_id)

            role_filter &= role_scope
            grant_filter &= grant_scope
        elif global_only:
            role_scope = Q(role_permissions__role__user_roles__scope=ScopeChoices.ORGANIZATION)
            grant_scope = Q(direct_grants__scope=ScopeChoices.ORGANIZATION)
            role_filter &= role_scope
            grant_filter &= grant_scope

        active_role_permissions = Permission.objects.filter(role_filter).values_list('codename', flat=True)
        active_direct_permissions = Permission.objects.filter(grant_filter).values_list('codename', flat=True)

        return set(active_role_permissions) | set(active_direct_permissions)

    @staticmethod
    def _resolve_organization(request_or_user, organization=None):
        if organization:
            return organization
            
        if hasattr(request_or_user, 'user'):
            from apps.organization.context import get_current_organization
            try:
                return get_current_organization(request_or_user)
            except Exception:
                # FAIL CLOSED: Missing or invalid context.
                # We must not guess the organization if headers are omitted.
                return None
                
        user = request_or_user.user if hasattr(request_or_user, 'user') else request_or_user
        if getattr(user, 'is_authenticated', False):
            from apps.organization.models import OrganizationMembership
            memberships = OrganizationMembership.objects.filter(user=user, status='active').select_related('organization')
            if memberships.count() == 1:
                return memberships.first().organization
            # If the user has multiple active memberships, we CANNOT safely guess. FAIL CLOSED.
            return None
            
        return None

    @staticmethod
    def has_permission(request_or_user, permission_codename, branch_id=None, team_id=None, global_only=False, organization=None):
        user = request_or_user.user if hasattr(request_or_user, 'user') else request_or_user
        if not user.is_authenticated or not user.is_active:
            return False
        if user.is_superuser:
            return True
            
        org = AuthorizationService._resolve_organization(request_or_user, organization)
        if not org:
            return False
            
        return permission_codename in AuthorizationService.get_effective_permissions(user, org, branch_id=branch_id, team_id=team_id, global_only=global_only)

    @staticmethod
    def get_authorized_branches(request_or_user, permission_codename, organization=None):
        user = request_or_user.user if hasattr(request_or_user, 'user') else request_or_user
        if not user.is_authenticated or not user.is_active:
            return Branch.objects.none()
        if user.is_superuser:
            return Branch.objects.filter(is_active=True)
            
        org = AuthorizationService._resolve_organization(request_or_user, organization)
        if not org:
            return Branch.objects.none()

        now = timezone.now()

        has_org_role = UserRole.objects.filter(
            user=user,
            is_revoked=False,
            scope=ScopeChoices.ORGANIZATION,
            role__is_active=True,
            role__organization=org,
            role__role_permissions__permission__codename=permission_codename,
            role__role_permissions__permission__is_active=True
        ).exclude(expires_at__lt=now).exists()

        has_org_grant = UserPermissionGrant.objects.filter(
            user=user,
            is_revoked=False,
            scope=ScopeChoices.ORGANIZATION,
            permission__codename=permission_codename,
            permission__is_active=True
        ).exclude(expires_at__lt=now).exists()

        if has_org_role or has_org_grant:
            return Branch.objects.filter(is_active=True, organization_id=org.id)

        branch_ids = set()

        branch_roles = UserRole.objects.filter(
            user=user,
            is_revoked=False,
            scope=ScopeChoices.BRANCH,
            role__is_active=True,
            role__organization=org,
            role__role_permissions__permission__codename=permission_codename,
            role__role_permissions__permission__is_active=True
        ).exclude(expires_at__lt=now).values_list('branch_id', flat=True)

        branch_grants = UserPermissionGrant.objects.filter(
            user=user,
            is_revoked=False,
            scope=ScopeChoices.BRANCH,
            permission__codename=permission_codename,
            permission__is_active=True
        ).exclude(expires_at__lt=now).values_list('branch_id', flat=True)

        branch_ids.update(branch_roles)
        branch_ids.update(branch_grants)

        return Branch.objects.filter(id__in=branch_ids, organization_id=org.id, is_active=True)

    @staticmethod
    def get_authorized_teams(request_or_user, permission_codename, organization=None):
        from apps.organization.models import Team
        user = request_or_user.user if hasattr(request_or_user, 'user') else request_or_user
        if not user.is_authenticated or not user.is_active:
            return Team.objects.none()
        if user.is_superuser:
            return Team.objects.filter(is_active=True)
            
        org = AuthorizationService._resolve_organization(request_or_user, organization)
        if not org:
            return Team.objects.none()

        now = timezone.now()

        has_org_role = UserRole.objects.filter(
            user=user,
            is_revoked=False,
            scope=ScopeChoices.ORGANIZATION,
            role__is_active=True,
            role__organization=org,
            role__role_permissions__permission__codename=permission_codename,
            role__role_permissions__permission__is_active=True
        ).exclude(expires_at__lt=now).exists()

        has_org_grant = UserPermissionGrant.objects.filter(
            user=user,
            is_revoked=False,
            scope=ScopeChoices.ORGANIZATION,
            permission__codename=permission_codename,
            permission__is_active=True
        ).exclude(expires_at__lt=now).exists()

        if has_org_role or has_org_grant:
            return Team.objects.filter(is_active=True, department__branch__organization_id=org.id)

        team_ids = set()

        team_roles = UserRole.objects.filter(
            user=user,
            is_revoked=False,
            scope=ScopeChoices.TEAM,
            role__is_active=True,
            role__organization=org,
            role__role_permissions__permission__codename=permission_codename,
            role__role_permissions__permission__is_active=True
        ).exclude(expires_at__lt=now).values_list('team_id', flat=True)

        team_grants = UserPermissionGrant.objects.filter(
            user=user,
            is_revoked=False,
            scope=ScopeChoices.TEAM,
            permission__codename=permission_codename,
            permission__is_active=True
        ).exclude(expires_at__lt=now).values_list('team_id', flat=True)

        team_ids.update(team_roles)
        team_ids.update(team_grants)
        
        explicit_teams_qs = Team.objects.filter(id__in=team_ids, department__branch__organization_id=org.id, is_active=True)
        
        authorized_branches = AuthorizationService.get_authorized_branches(request_or_user, permission_codename, org)
        branch_teams_qs = Team.objects.filter(is_active=True, department__branch__organization_id=org.id, department__branch__in=authorized_branches)
        
        return explicit_teams_qs | branch_teams_qs
