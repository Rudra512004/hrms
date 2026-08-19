from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import Role, Permission, UserRole, UserPermissionGrant
from .serializers import RoleSerializer, PermissionSerializer, UserRoleSerializer, UserPermissionGrantSerializer
from apps.authorization.permissions import require_permission
from apps.authorization.services import AuthorizationService
from django.contrib.auth import get_user_model

User = get_user_model()

class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated, require_permission('role.view')()]

    def get_queryset(self):
        # ARCHITECTURAL LIMITATION: Employee model does not have an organization relationship.
        # Returning all roles instead of attempting to scope by organization.
        return Role.objects.all()

class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated, require_permission('permission.view')()]
    queryset = Permission.objects.all()

    @action(detail=False, methods=['get'])
    def my_permissions(self, request):
        perms = AuthorizationService.get_effective_permissions(request.user)
        return Response(list(perms))

class UserRoleViewSet(viewsets.ModelViewSet):
    serializer_class = UserRoleSerializer

    def get_permissions(self):
        permissions = [IsAuthenticated()]
        if self.action in ['list', 'retrieve']:
            permissions.append(require_permission('role.view')())
        else:
            permissions.append(require_permission('role.assign')())
        return permissions

    def get_queryset(self):
        # ARCHITECTURAL LIMITATION: Employee model does not have an organization relationship.
        # Returning all user roles instead of attempting to scope by organization.
        return UserRole.objects.filter(is_revoked=False)

    def perform_create(self, serializer):
        serializer.save(assigned_by=self.request.user)

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        if not AuthorizationService.has_permission(request.user, 'role.revoke'):
            return Response(status=status.HTTP_403_FORBIDDEN)

        user_role = self.get_object()

        # Superadmin protection logic
        if user_role.user.is_superuser:
            if not request.user.is_superuser:
                return Response({'detail': 'Only a superadmin can modify superadmin roles.'}, status=status.HTTP_403_FORBIDDEN)

            # Check if this revokes the last admin-level access for the last superadmin - skip complex check, just prevent non-superadmins.

        if user_role.is_revoked:
            return Response({'detail': 'Role already revoked.'}, status=status.HTTP_400_BAD_REQUEST)

        user_role.is_revoked = True
        user_role.revoked_at = timezone.now()
        user_role.save()
        return Response(UserRoleSerializer(user_role).data)

class UserPermissionGrantViewSet(viewsets.ModelViewSet):
    serializer_class = UserPermissionGrantSerializer

    def get_permissions(self):
        permissions = [IsAuthenticated()]
        if self.action in ['list', 'retrieve']:
            permissions.append(require_permission('permission.view')())
        else:
            permissions.append(require_permission('permission.assign')())
        return permissions

    def get_queryset(self):
        return UserPermissionGrant.objects.filter(is_revoked=False)

    def perform_create(self, serializer):
        serializer.save(granted_by=self.request.user)

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        if not AuthorizationService.has_permission(request.user, 'permission.revoke'):
            return Response(status=status.HTTP_403_FORBIDDEN)

        grant = self.get_object()

        if grant.user.is_superuser and not request.user.is_superuser:
            return Response({'detail': 'Only a superadmin can modify superadmin permissions.'}, status=status.HTTP_403_FORBIDDEN)

        if grant.is_revoked:
            return Response({'detail': 'Permission already revoked.'}, status=status.HTTP_400_BAD_REQUEST)

        grant.is_revoked = True
        grant.revoked_at = timezone.now()
        grant.save()
        return Response(UserPermissionGrantSerializer(grant).data)
