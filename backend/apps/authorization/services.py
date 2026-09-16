from django.utils import timezone
from .models import Permission, UserRole, UserPermissionGrant, ScopeChoices
from apps.organization.models import Branch
from django.db.models import Q

class AuthorizationService:
    @staticmethod
    def get_effective_permissions(user, branch_id=None):
        if not user.is_authenticated or not user.is_active:
            return set()

        if user.is_superuser:
            # Superusers have all active permissions
            return set(Permission.objects.filter(is_active=True).values_list('codename', flat=True))

        now = timezone.now()

        role_filter = Q(
            is_active=True,
            role_permissions__role__is_active=True,
            role_permissions__role__user_roles__user=user,
            role_permissions__role__user_roles__is_revoked=False,
        ) & ~Q(role_permissions__role__user_roles__expires_at__lt=now)

        grant_filter = Q(
            is_active=True,
            direct_grants__user=user,
            direct_grants__is_revoked=False,
        ) & ~Q(direct_grants__expires_at__lt=now)

        if branch_id:
            role_scope = Q(role_permissions__role__user_roles__scope=ScopeChoices.ORGANIZATION) | \
                         Q(role_permissions__role__user_roles__scope=ScopeChoices.BRANCH, role_permissions__role__user_roles__branch_id=branch_id)
            grant_scope = Q(direct_grants__scope=ScopeChoices.ORGANIZATION) | \
                          Q(direct_grants__scope=ScopeChoices.BRANCH, direct_grants__branch_id=branch_id)

            role_filter &= role_scope
            grant_filter &= grant_scope

        active_role_permissions = Permission.objects.filter(role_filter).values_list('codename', flat=True)
        active_direct_permissions = Permission.objects.filter(grant_filter).values_list('codename', flat=True)

        return set(active_role_permissions) | set(active_direct_permissions)

    @staticmethod
    def has_permission(user, permission_codename, branch_id=None):
        if not user.is_authenticated or not user.is_active:
            return False
        if user.is_superuser:
            return True
        return permission_codename in AuthorizationService.get_effective_permissions(user, branch_id=branch_id)

    @staticmethod
    def get_authorized_branches(user, permission_codename):
        """Returns a QuerySet of branches the user has the given permission for."""
        if not user.is_authenticated or not user.is_active:
            return Branch.objects.none()

        if user.is_superuser:
            return Branch.objects.filter(is_active=True)

        now = timezone.now()

        # Check if user has ORG-WIDE permission
        has_org_role = UserRole.objects.filter(
            user=user,
            is_revoked=False,
            scope=ScopeChoices.ORGANIZATION,
            role__is_active=True,
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
            if hasattr(user, 'employee') and user.employee:
                return Branch.objects.filter(is_active=True, organization_id=user.employee.organization_id)
            return Branch.objects.filter(is_active=True)

        # Collect branch-scoped permissions
        branch_ids = set()

        branch_roles = UserRole.objects.filter(
            user=user,
            is_revoked=False,
            scope=ScopeChoices.BRANCH,
            role__is_active=True,
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

        return Branch.objects.filter(id__in=branch_ids, is_active=True)
