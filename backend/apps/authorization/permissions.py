from rest_framework import permissions
from .services import AuthorizationService

class HasRequiredPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        required_permission = getattr(view, 'required_permission', None)
        if not required_permission:
            return False
        return AuthorizationService.has_permission(request.user, required_permission)

def require_permission(permission_codename):
    class SpecificPermission(permissions.BasePermission):
        def has_permission(self, request, view):
            if not request.user or not request.user.is_authenticated:
                return False
            return AuthorizationService.has_permission(request.user, permission_codename)
    return SpecificPermission

from .network import NetworkAccessService

class IsSuperAdmin(permissions.BasePermission):
    """
    Enforces that the user is a superuser. Used for organization creation and global settings.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)

class IsNetworkAllowed(permissions.BasePermission):
    message = "Network access denied. You must be on an office network or have an active WFH request."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return True
        return NetworkAccessService.is_remote_access_allowed(request, request.user)
