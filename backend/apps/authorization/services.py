from django.utils import timezone
from .models import Permission, UserRole, UserPermissionGrant

class AuthorizationService:
    @staticmethod
    def get_effective_permissions(user):
        if not user.is_authenticated or not user.is_active:
            return set()

        now = timezone.now()

        active_role_permissions = Permission.objects.filter(
            is_active=True,
            role_permissions__role__is_active=True,
            role_permissions__role__user_roles__user=user,
            role_permissions__role__user_roles__is_revoked=False,
        ).exclude(
            role_permissions__role__user_roles__expires_at__lt=now
        ).values_list('codename', flat=True)

        active_direct_permissions = Permission.objects.filter(
            is_active=True,
            direct_grants__user=user,
            direct_grants__is_revoked=False,
        ).exclude(
            direct_grants__expires_at__lt=now
        ).values_list('codename', flat=True)

        return set(active_role_permissions) | set(active_direct_permissions)

    @staticmethod
    def has_permission(user, permission_codename):
        if not user.is_authenticated or not user.is_active:
            return False
        if user.is_superuser:
            return True
        return permission_codename in AuthorizationService.get_effective_permissions(user)
