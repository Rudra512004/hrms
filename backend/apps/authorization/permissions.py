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
