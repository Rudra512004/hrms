from rest_framework import viewsets, status
from apps.audit.services import AuditService
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError
from apps.organization.models import Organization
from .models import Role, Permission, UserRole, UserPermissionGrant, RolePermission
from .serializers import RoleSerializer, PermissionSerializer, UserRoleSerializer, UserPermissionGrantSerializer, RolePermissionSerializer
from apps.authorization.permissions import require_permission
from apps.authorization.services import AuthorizationService
from django.contrib.auth import get_user_model
from rest_framework.views import APIView

User = get_user_model()

class CurrentUserPermissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        if user.is_superuser:
            perms = set(Permission.objects.filter(is_active=True).values_list('codename', flat=True))
        else:
            perms = AuthorizationService.get_effective_permissions(user)
            
        roles = Role.objects.filter(
            user_roles__user=user,
            user_roles__is_revoked=False,
            is_active=True
        ).values_list('name', flat=True)

        return Response({
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_superuser': user.is_superuser,
            },
            'roles': list(roles),
            'permissions': list(perms)
        })

class RoleViewSet(viewsets.ModelViewSet):
    serializer_class = RoleSerializer

    def get_permissions(self):
        permissions = [IsAuthenticated()]
        if self.action in ['list', 'retrieve']:
            permissions.append(require_permission('role.view')())
        else:
            permissions.append(require_permission('role.assign')())
        return permissions

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            qs = Role.objects.all()
            org_id = self.request.query_params.get('organization')
            if org_id:
                qs = qs.filter(organization_id=org_id)
            return qs
        if hasattr(user, 'employee') and user.employee.organization_id:
            return Role.objects.filter(organization=user.employee.organization)
        return Role.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser:
            org_id = self.request.data.get('organization')
            if org_id:
                try:
                    org = Organization.objects.get(id=org_id)
                except Organization.DoesNotExist:
                    raise ValidationError({'organization': 'Specified organization does not exist.'})
            elif hasattr(user, 'employee') and user.employee.organization_id:
                org = user.employee.organization
            else:
                org = Organization.objects.first()
        else:
            if hasattr(user, 'employee') and user.employee.organization_id:
                org = user.employee.organization
            else:
                raise ValidationError({'organization': 'User does not belong to an organization.'})

        try:
            serializer.save(organization=org)
        except IntegrityError:
            raise ValidationError({'name': 'A role with this name already exists in this organization.'})


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated]
    queryset = Permission.objects.all()

    def get_permissions(self):
        permissions = [IsAuthenticated()]
        if self.action != 'my_permissions':
            permissions.append(require_permission('permission.view')())
        return permissions

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
        user = self.request.user
        if user.is_superuser:
            qs = UserRole.objects.filter(is_revoked=False)
            org_id = self.request.query_params.get('organization')
            if org_id:
                qs = qs.filter(role__organization_id=org_id)
            return qs
        if hasattr(user, 'employee') and user.employee.organization_id:
            org = user.employee.organization
            return UserRole.objects.filter(is_revoked=False, role__organization=org)
        return UserRole.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        role = serializer.validated_data.get('role')
        target_user = serializer.validated_data.get('user')

        if not user.is_superuser:
            if not hasattr(user, 'employee') or not user.employee.organization_id:
                raise ValidationError({'detail': 'User does not belong to an organization.'})

            user_org = user.employee.organization
            if role.organization_id != user_org.id:
                raise ValidationError({'role': 'Role does not belong to your organization.'})

            if not hasattr(target_user, 'employee') or target_user.employee.organization_id != user_org.id:
                raise ValidationError({'user': 'Target user does not belong to your organization.'})
        else:
            if hasattr(target_user, 'employee') and target_user.employee.organization_id:
                if role.organization_id != target_user.employee.organization_id:
                    raise ValidationError({'detail': 'Role organization must match target user organization.'})

        user_role = serializer.save(assigned_by=self.request.user)
        AuditService.log(
            action='role_assigned',
            actor=self.request.user,
            target_type='user',
            target_id=user_role.user.id,
            metadata={'role_id': user_role.role.id, 'role_name': user_role.role.name},
            request=self.request
        )

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
        AuditService.log(
            action='role_revoked',
            actor=request.user,
            target_type='user',
            target_id=user_role.user.id,
            metadata={'role_id': user_role.role.id, 'role_name': user_role.role.name},
            request=request
        )
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
        user = self.request.user
        if user.is_superuser:
            qs = UserPermissionGrant.objects.filter(is_revoked=False)
            org_id = self.request.query_params.get('organization')
            if org_id:
                qs = qs.filter(user__employee__organization_id=org_id)
            return qs
        if hasattr(user, 'employee') and user.employee.organization_id:
            org = user.employee.organization
            return UserPermissionGrant.objects.filter(
                is_revoked=False,
                user__employee__organization=org
            )
        return UserPermissionGrant.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        target_user = serializer.validated_data.get('user')

        if not user.is_superuser:
            if not hasattr(user, 'employee') or not user.employee.organization_id:
                raise ValidationError({'detail': 'User does not belong to an organization.'})

            user_org = user.employee.organization
            if not hasattr(target_user, 'employee') or target_user.employee.organization_id != user_org.id:
                raise ValidationError({'user': 'Target user does not belong to your organization.'})

        user_permission = serializer.save(granted_by=self.request.user)
        AuditService.log(
            action='permission_granted',
            actor=self.request.user,
            target_type='user',
            target_id=user_permission.user.id,
            metadata={'permission_id': user_permission.permission.id, 'codename': user_permission.permission.codename},
            request=self.request
        )

    def perform_update(self, serializer):
        user = self.request.user
        target_user = serializer.validated_data.get('user')

        if target_user and not user.is_superuser:
            if not hasattr(user, 'employee') or not user.employee.organization_id:
                raise ValidationError({'detail': 'User does not belong to an organization.'})

            user_org = user.employee.organization
            if not hasattr(target_user, 'employee') or target_user.employee.organization_id != user_org.id:
                raise ValidationError({'user': 'Target user does not belong to your organization.'})

        serializer.save()

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
        AuditService.log(
            action='permission_revoked',
            actor=request.user,
            target_type='user',
            target_id=grant.user.id,
            metadata={'permission_id': grant.permission.id, 'codename': grant.permission.codename},
            request=request
        )
        return Response(UserPermissionGrantSerializer(grant).data)

class RolePermissionViewSet(viewsets.ModelViewSet):
    serializer_class = RolePermissionSerializer

    def get_permissions(self):
        permissions = [IsAuthenticated()]
        if self.action in ['list', 'retrieve']:
            permissions.append(require_permission('role.view')())
        else:
            permissions.append(require_permission('permission.assign')())
        return permissions

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            queryset = RolePermission.objects.all()
        elif hasattr(user, 'employee') and user.employee.organization_id:
            queryset = RolePermission.objects.filter(role__organization_id=user.employee.organization_id)
        else:
            return RolePermission.objects.none()

        role_id = self.request.query_params.get('role', None)
        if role_id is not None:
            queryset = queryset.filter(role_id=role_id)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        role = serializer.validated_data.get('role')
        if not user.is_superuser:
            if not hasattr(user, 'employee') or not user.employee.organization_id:
                raise ValidationError({'detail': 'User does not belong to an organization.'})
            if role.organization_id != user.employee.organization_id:
                raise ValidationError({'role': 'Role does not belong to your organization.'})

        grant = serializer.save()
        AuditService.log(
            action='role_permission_granted',
            actor=self.request.user,
            target_type='role',
            target_id=grant.role.id,
            metadata={'permission_id': grant.permission.id, 'codename': grant.permission.codename},
            request=self.request
        )

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        if not AuthorizationService.has_permission(request.user, 'permission.revoke'):
            return Response(status=status.HTTP_403_FORBIDDEN)
        
        grant = self.get_object()
        role_id = grant.role.id
        perm_id = grant.permission.id
        perm_codename = grant.permission.codename
        
        grant.delete()
        
        AuditService.log(
            action='role_permission_revoked',
            actor=request.user,
            target_type='role',
            target_id=role_id,
            metadata={'permission_id': perm_id, 'codename': perm_codename},
            request=request
        )
        return Response({'detail': 'Permission revoked from role'})

