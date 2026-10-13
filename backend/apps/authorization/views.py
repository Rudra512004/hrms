from rest_framework import viewsets, status
from apps.audit.services import AuditService
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError
from apps.organization.models import Organization
from .models import Role, Permission, UserRole, UserPermissionGrant, RolePermission, ScopeChoices
from .serializers import RoleSerializer, PermissionSerializer, UserRoleSerializer, UserPermissionGrantSerializer, RolePermissionSerializer
from apps.authorization.permissions import require_permission, require_any_permission
from apps.authorization.services import AuthorizationService
from django.contrib.auth import get_user_model
from rest_framework.views import APIView

User = get_user_model()


def _get_user_organization(user):
    """Resolve a tenant-admin's role-scoped organization without granting global access."""
    return AuthorizationService.get_primary_organization(user)

class CurrentUserPermissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        perms = AuthorizationService.get_effective_permissions(user)
            
        roles = Role.objects.filter(
            user_roles__user=user,
            user_roles__is_revoked=False,
            is_active=True
        ).values_list('name', flat=True)

        # Determine whether this user has a linked employee profile.
        # Super Admin accounts do NOT have employee profiles and must NOT
        # access employee self-service endpoints (attendance, leaves, payslips).
        has_employee = hasattr(user, 'employee') and user.employee is not None
        employee_code = user.employee.employee_code if (has_employee and hasattr(user, 'employee') and user.employee) else None
        registration = getattr(user, 'tenant_owner_registration', None)

        return Response({
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_superuser': user.is_superuser,
                'has_employee_profile': has_employee,
                'employee_code': employee_code,
                'can_create_organization': bool(registration and registration.can_launch_organization),
            },
            'roles': list(roles),
            'permissions': list(perms)
        })

class RoleViewSet(viewsets.ModelViewSet):
    serializer_class = RoleSerializer

    def get_permissions(self):
        permissions = [IsAuthenticated()]
        if self.action in ['list', 'retrieve']:
            permissions.append(require_any_permission('role.view', 'role.manage')())
        else:
            permissions.append(require_any_permission('role.manage', 'role.assign')())
        return permissions

    def get_queryset(self):
        user = self.request.user
        organization = _get_user_organization(user)
        if organization:
            return Role.objects.filter(organization=organization)
        return Role.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        org = _get_user_organization(user)
        if not org:
            raise ValidationError({'organization': 'User does not belong to an organization.'})

        name = serializer.validated_data.get('name', '').strip()
        if not name:
            raise ValidationError({'name': 'Role name is required.'})

        from django.utils.text import slugify
        candidate_slug = slugify(name)
        if candidate_slug in ['super-admin', 'organization-owner-super-admin'] or name.lower() in ['super admin', 'organization owner (super admin)']:
            raise ValidationError({'name': 'Cannot create a role with reserved system name or slug.'})

        base_slug = candidate_slug or 'role'
        slug = base_slug
        counter = 1
        while Role.objects.filter(organization=org, slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        try:
            role = serializer.save(organization=org, slug=slug, is_system=False)
            AuditService.log(
                action='role_created',
                actor=self.request.user,
                target_type='role',
                target_id=role.id,
                metadata={'role_name': role.name, 'slug': role.slug},
                request=self.request
            )
        except IntegrityError:
            raise ValidationError({'name': 'A role with this name already exists in this organization.'})

    def perform_update(self, serializer):
        role = serializer.instance
        new_name = serializer.validated_data.get('name')

        if role.is_system:
            if new_name is not None and new_name.strip() != role.name:
                raise ValidationError({'detail': 'System role name and identity cannot be modified.'})
        else:
            if new_name is not None:
                from django.utils.text import slugify
                candidate_slug = slugify(new_name)
                if candidate_slug in ['super-admin', 'organization-owner-super-admin'] or new_name.strip().lower() in ['super admin', 'organization owner (super admin)']:
                    raise ValidationError({'name': 'Cannot rename role to a reserved system name.'})

        updated_role = serializer.save()
        AuditService.log(
            action='role_updated',
            actor=self.request.user,
            target_type='role',
            target_id=updated_role.id,
            metadata={'role_name': updated_role.name, 'slug': updated_role.slug},
            request=self.request
        )

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system:
            return Response({'detail': 'System roles cannot be deleted.'}, status=status.HTTP_400_BAD_REQUEST)
        if role.user_roles.filter(is_revoked=False).exists():
            return Response({'detail': 'Cannot delete role with active user assignments.'}, status=status.HTTP_400_BAD_REQUEST)

        role_id = role.id
        role_name = role.name
        role_slug = role.slug

        role.delete()

        AuditService.log(
            action='role_deleted',
            actor=request.user,
            target_type='role',
            target_id=role_id,
            metadata={'role_name': role_name, 'slug': role_slug},
            request=request
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['put'])
    def permissions(self, request, pk=None):
        role = self.get_object()
        if role.slug == 'super-admin':
            return Response(
                {'detail': 'Super Admin permissions cannot be narrowed. Super Admin automatically holds all system permissions.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        permission_ids = request.data.get('permission_ids', None)
        if permission_ids is None or not isinstance(permission_ids, list):
            return Response(
                {'detail': 'permission_ids must be a list of permission IDs.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            permission_ids = [int(pid) for pid in permission_ids]
        except (ValueError, TypeError):
            return Response(
                {'detail': 'permission_ids must contain valid integer IDs.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        existing_perms = {p.id: p for p in Permission.objects.filter(id__in=permission_ids)}
        unknown_ids = [pid for pid in permission_ids if pid not in existing_perms]
        if unknown_ids:
            return Response(
                {'detail': f'Unknown permission IDs: {unknown_ids}', 'invalid_ids': unknown_ids},
                status=status.HTTP_400_BAD_REQUEST
            )

        inactive_ids = [pid for pid in permission_ids if not existing_perms[pid].is_active]
        if inactive_ids:
            return Response(
                {'detail': f'Inactive permissions cannot be assigned: {inactive_ids}', 'inactive_ids': inactive_ids},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_super = AuthorizationService.is_super_admin(request.user)
        if not is_super:
            enterprise_ids = [pid for pid in permission_ids if existing_perms[pid].is_preserved_enterprise]
            if enterprise_ids:
                return Response(
                    {'detail': 'Only Super Admins can assign preserved enterprise permissions.', 'enterprise_ids': enterprise_ids},
                    status=status.HTTP_403_FORBIDDEN
                )

        from django.db import transaction
        with transaction.atomic():
            RolePermission.objects.filter(role=role).delete()
            to_create = [RolePermission(role=role, permission_id=pid) for pid in set(permission_ids)]
            RolePermission.objects.bulk_create(to_create)

        AuditService.log(
            action='role_permissions_updated',
            actor=request.user,
            target_type='role',
            target_id=role.id,
            metadata={
                'role_name': role.name,
                'permissions_count': len(set(permission_ids)),
                'permission_ids': list(set(permission_ids)),
            },
            request=request
        )

        return Response({
            'role_id': role.id,
            'role_name': role.name,
            'permissions_count': role.role_permissions.filter(permission__is_active=True, permission__column_index__in=[1, 2, 3]).count(),
            'effective_permissions_count': role.role_permissions.filter(permission__is_active=True).count(),
            'updated_at': timezone.now().isoformat()
        })


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated]
    queryset = Permission.objects.all()
    format_kwarg = None

    def perform_content_negotiation(self, request, force=False):
        renderers = self.get_renderers()
        conneg = self.get_content_negotiator()
        try:
            return conneg.select_renderer(request, renderers, self.format_kwarg)
        except Exception:
            return (renderers[0], renderers[0].media_type)

    def get_permissions(self):
        permissions = [IsAuthenticated()]
        if self.action != 'my_permissions':
            permissions.append(require_any_permission('permission.view', 'role.view', 'role.manage')())
        return permissions

    def list(self, request, *args, **kwargs):
        user = request.user
        org = _get_user_organization(user)
        if not org:
            return Response({'detail': 'User does not belong to an organization.'}, status=status.HTTP_400_BAD_REQUEST)

        format_type = request.query_params.get('format', '').lower()
        include_preserved = request.query_params.get('include_preserved', 'false').lower() == 'true'

        base_qs = Permission.objects.filter(is_active=True)
        if not include_preserved:
            base_qs = base_qs.filter(column_index__in=[1, 2, 3])

        if format_type == 'flat':
            serializer = PermissionSerializer(base_qs.order_by('column_index', 'display_order', 'id'), many=True)
            return Response(serializer.data)

        ui_perms = Permission.objects.filter(is_active=True, column_index__in=[1, 2, 3]).order_by('column_index', 'display_order', 'id')
        total_visible = ui_perms.count()

        columns_data = {'1': [], '2': [], '3': []}

        for col_idx in [1, 2, 3]:
            col_perms = [p for p in ui_perms if p.column_index == col_idx]
            categories_map = {}
            for p in col_perms:
                cat_name = p.category or 'General'
                if cat_name not in categories_map:
                    categories_map[cat_name] = []
                categories_map[cat_name].append({
                    'id': p.id,
                    'codename': p.codename,
                    'label': p.ui_label or p.name,
                    'name': p.name,
                    'description': p.description,
                    'column': p.column_index,
                    'category': p.category,
                })
            columns_data[str(col_idx)] = [
                {'category': cat, 'actions': actions}
                for cat, actions in categories_map.items()
            ]

        response_data = {
            'total_visible_count': total_visible,
            'columns': columns_data,
        }
        if include_preserved:
            preserved_perms = Permission.objects.filter(is_active=True, is_preserved_enterprise=True).order_by('id')
            response_data['preserved_enterprise'] = [
                {
                    'id': p.id,
                    'codename': p.codename,
                    'label': p.ui_label or p.name,
                    'name': p.name,
                    'description': p.description,
                    'category': p.category,
                }
                for p in preserved_perms
            ]

        return Response(response_data)

    @action(detail=False, methods=['get'])
    def my_permissions(self, request):
        perms = AuthorizationService.get_effective_permissions(request.user)
        return Response(list(perms))


class UserRoleViewSet(viewsets.ModelViewSet):
    serializer_class = UserRoleSerializer

    def get_permissions(self):
        permissions = [IsAuthenticated()]
        if self.action in ['list', 'retrieve']:
            permissions.append(require_any_permission('role.view', 'role.manage')())
        elif self.action in ['destroy', 'revoke']:
            permissions.append(require_any_permission('role.revoke', 'role.assign', 'role.manage')())
        else:
            permissions.append(require_any_permission('role.assign', 'role.manage')())
        return permissions

    def get_queryset(self):
        user = self.request.user
        org = _get_user_organization(user)
        if not org:
            return UserRole.objects.none()
        qs = UserRole.objects.filter(role__organization=org)
        if self.action == 'list':
            include_revoked = self.request.query_params.get('include_revoked', 'false').lower() == 'true'
            if not include_revoked:
                qs = qs.filter(is_revoked=False)
        user_id = self.request.query_params.get('user')
        if user_id:
            qs = qs.filter(user_id=user_id)
        role_id = self.request.query_params.get('role')
        if role_id:
            qs = qs.filter(role_id=role_id)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        role = serializer.validated_data.get('role')
        target_user = serializer.validated_data.get('user')

        user_org = _get_user_organization(user)
        if not user_org:
            raise ValidationError({'detail': 'User does not belong to an organization.'})
        if role.organization_id != user_org.id:
            raise ValidationError({'role': 'Role does not belong to your organization.'})

        if hasattr(target_user, 'employee') and target_user.employee and target_user.employee.organization_id != user_org.id:
            raise ValidationError({'user': 'Target user does not belong to your organization.'})

        other_org_roles = UserRole.objects.filter(user=target_user).exclude(role__organization=user_org)
        if other_org_roles.exists() and not UserRole.objects.filter(user=target_user, role__organization=user_org).exists():
            raise ValidationError({'user': 'Target user belongs to another organization.'})

        # Anti-privilege escalation: only Super Admin can assign the Super Admin role
        if role.slug == 'super-admin':
            if not AuthorizationService.is_super_admin(user):
                raise ValidationError({'role': 'Only Super Admins can assign the Super Admin role.'})

        # Prevent Privilege Escalation on scope
        scope = serializer.validated_data.get('scope', ScopeChoices.ORGANIZATION)
        branch = serializer.validated_data.get('branch')
        team = serializer.validated_data.get('team')

        if scope == ScopeChoices.ORGANIZATION:
            if not AuthorizationService.has_permission(user, 'role.assign', branch_id=None, team_id=None, global_only=True):
                raise ValidationError({'scope': 'You do not have permission to grant organization-wide roles.'})
        elif scope == ScopeChoices.BRANCH:
            if not AuthorizationService.has_permission(user, 'role.assign', branch_id=branch.id if branch else None, team_id=None):
                raise ValidationError({'scope': 'You do not have permission to grant roles for this branch.'})
        elif scope == ScopeChoices.TEAM:
            if not AuthorizationService.has_permission(user, 'role.assign', branch_id=None, team_id=team.id if team else None):
                raise ValidationError({'scope': 'You do not have permission to grant roles for this team.'})

        # Duplicate assignment check
        if UserRole.objects.filter(user=target_user, role=role, scope=scope, branch=branch, team=team, is_revoked=False).exists():
            raise ValidationError({'detail': 'User already has this role assigned with the same scope.'})

        user_role = serializer.save(assigned_by=self.request.user, is_revoked=False)
        AuditService.log(
            action='role_assigned',
            actor=self.request.user,
            target_type='user',
            target_id=user_role.user.id,
            metadata={
                'role_id': user_role.role.id,
                'role_name': user_role.role.name,
                'role_slug': user_role.role.slug,
                'scope': user_role.scope,
                'branch_id': user_role.branch_id,
                'team_id': user_role.team_id,
            },
            request=self.request
        )

    def perform_update(self, serializer):
        user = self.request.user
        target_user = serializer.validated_data.get('user', serializer.instance.user)
        role = serializer.validated_data.get('role', serializer.instance.role)

        user_org = _get_user_organization(user)
        if not user_org:
            raise ValidationError({'detail': 'User does not belong to an organization.'})
        if not hasattr(target_user, 'employee') or target_user.employee.organization_id != user_org.id:
            raise ValidationError({'user': 'Target user does not belong to your organization.'})

        # Prevent Privilege Escalation
        scope = serializer.validated_data.get('scope', serializer.instance.scope)
        branch = serializer.validated_data.get('branch', serializer.instance.branch)
        team = serializer.validated_data.get('team', serializer.instance.team)

        if scope == ScopeChoices.ORGANIZATION:
            if not AuthorizationService.has_permission(user, 'role.assign', branch_id=None, team_id=None, global_only=True):
                raise ValidationError({'scope': 'You do not have permission to grant organization-wide roles.'})
        elif scope == ScopeChoices.BRANCH:
            if not AuthorizationService.has_permission(user, 'role.assign', branch_id=branch.id if branch else None, team_id=None):
                raise ValidationError({'scope': 'You do not have permission to grant roles for this branch.'})
        elif scope == ScopeChoices.TEAM:
            if not AuthorizationService.has_permission(user, 'role.assign', branch_id=None, team_id=team.id if team else None):
                raise ValidationError({'scope': 'You do not have permission to grant roles for this team.'})

        serializer.save()

    def _revoke_user_role(self, request, user_role):
        user = request.user
        user_org = _get_user_organization(user)
        if not user_org or user_role.role.organization_id != user_org.id:
            raise ValidationError({'detail': 'Cannot revoke role from another organization.'})

        if user_role.role.slug == 'super-admin':
            if not AuthorizationService.is_super_admin(user):
                return Response({'detail': 'Only Super Admins can revoke the Super Admin role.'}, status=status.HTTP_403_FORBIDDEN)

        if user_role.is_revoked:
            return Response({'detail': 'Role already revoked.'}, status=status.HTTP_400_BAD_REQUEST)

        user_role.is_revoked = True
        user_role.revoked_at = timezone.now()
        user_role.save()

        AuditService.log(
            action='role_revoked',
            actor=user,
            target_type='user',
            target_id=user_role.user.id,
            metadata={
                'role_id': user_role.role.id,
                'role_name': user_role.role.name,
                'role_slug': user_role.role.slug,
            },
            request=request
        )
        return None

    def destroy(self, request, *args, **kwargs):
        user_role = self.get_object()
        err_response = self._revoke_user_role(request, user_role)
        if err_response:
            return err_response
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        user_role = self.get_object()
        err_response = self._revoke_user_role(request, user_role)
        if err_response:
            return err_response
        return Response(UserRoleSerializer(user_role).data, status=status.HTTP_200_OK)

class UserPermissionGrantViewSet(viewsets.ModelViewSet):
    serializer_class = UserPermissionGrantSerializer

    def get_permissions(self):
        permissions = [IsAuthenticated()]
        if self.action in ['list', 'retrieve']:
            permissions.append(require_any_permission('permission.view', 'role.view', 'role.manage')())
        elif self.action in ['destroy', 'revoke']:
            permissions.append(require_any_permission('permission.revoke', 'role.manage')())
        else:
            permissions.append(require_any_permission('permission.assign', 'role.manage')())
        return permissions

    def get_queryset(self):
        user = self.request.user
        org = _get_user_organization(user)
        if org:
            return UserPermissionGrant.objects.filter(
                is_revoked=False,
                user__employee__organization=org
            )
        return UserPermissionGrant.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        target_user = serializer.validated_data.get('user')

        user_org = _get_user_organization(user)
        if not user_org:
            raise ValidationError({'detail': 'User does not belong to an organization.'})
        if not hasattr(target_user, 'employee') or target_user.employee.organization_id != user_org.id:
            raise ValidationError({'user': 'Target user does not belong to your organization.'})
            
        # Prevent Privilege Escalation
        scope = serializer.validated_data.get('scope', ScopeChoices.ORGANIZATION)
        branch = serializer.validated_data.get('branch')
        team = serializer.validated_data.get('team')
        
        if scope == ScopeChoices.ORGANIZATION:
            if not AuthorizationService.has_permission(user, 'permission.assign', branch_id=None, team_id=None, global_only=True):
                raise ValidationError({'scope': 'You do not have permission to grant organization-wide permissions.'})
        elif scope == ScopeChoices.BRANCH:
            if not AuthorizationService.has_permission(user, 'permission.assign', branch_id=branch.id if branch else None, team_id=None):
                raise ValidationError({'scope': 'You do not have permission to grant permissions for this branch.'})
        elif scope == ScopeChoices.TEAM:
            if not AuthorizationService.has_permission(user, 'permission.assign', branch_id=None, team_id=team.id if team else None):
                raise ValidationError({'scope': 'You do not have permission to grant permissions for this team.'})

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

        if target_user:
            user_org = _get_user_organization(user)
            if not user_org:
                raise ValidationError({'detail': 'User does not belong to an organization.'})
            if not hasattr(target_user, 'employee') or target_user.employee.organization_id != user_org.id:
                raise ValidationError({'user': 'Target user does not belong to your organization.'})

            # Prevent Privilege Escalation
            scope = serializer.validated_data.get('scope', serializer.instance.scope)
            branch = serializer.validated_data.get('branch', serializer.instance.branch)
            team = serializer.validated_data.get('team', serializer.instance.team)
            
            if scope == ScopeChoices.ORGANIZATION:
                if not AuthorizationService.has_permission(user, 'permission.assign', branch_id=None, team_id=None):
                    raise ValidationError({'scope': 'You do not have permission to grant organization-wide permissions.'})
            elif scope == ScopeChoices.BRANCH:
                if not AuthorizationService.has_permission(user, 'permission.assign', branch_id=branch.id if branch else None, team_id=None):
                    raise ValidationError({'scope': 'You do not have permission to grant permissions for this branch.'})
            elif scope == ScopeChoices.TEAM:
                if not AuthorizationService.has_permission(user, 'permission.assign', branch_id=None, team_id=team.id if team else None):
                    raise ValidationError({'scope': 'You do not have permission to grant permissions for this team.'})

        serializer.save()

    def destroy(self, request, *args, **kwargs):
        grant = self.get_object()
        perm_id = grant.permission.id
        codename = grant.permission.codename
        target_user_id = grant.user.id

        grant.delete()

        AuditService.log(
            action='permission_revoked',
            actor=request.user,
            target_type='user',
            target_id=target_user_id,
            metadata={'permission_id': perm_id, 'codename': codename},
            request=request
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        if not AuthorizationService.has_permission(request.user, 'permission.revoke'):
            return Response(status=status.HTTP_403_FORBIDDEN)

        grant = self.get_object()

        # Removed superadmin restriction

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
            permissions.append(require_any_permission('role.view', 'role.manage')())
        elif self.action in ['destroy', 'revoke']:
            permissions.append(require_any_permission('permission.revoke', 'role.manage')())
        else:
            permissions.append(require_any_permission('permission.assign', 'role.manage')())
        return permissions

    def get_queryset(self):
        user = self.request.user
        if _get_user_organization(user):
            queryset = RolePermission.objects.filter(role__organization=_get_user_organization(user))
        else:
            return RolePermission.objects.none()

        role_id = self.request.query_params.get('role', None)
        if role_id is not None:
            queryset = queryset.filter(role_id=role_id)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        role = serializer.validated_data.get('role')
        user_org = _get_user_organization(user)
        if not user_org:
            raise ValidationError({'detail': 'User does not belong to an organization.'})
        if role.organization_id != user_org.id:
            raise ValidationError({'role': 'Role does not belong to your organization.'})
        if role.slug == 'super-admin':
            raise ValidationError({'role': 'Super Admin permissions are dynamically resolved and cannot be manually assigned.'})

        grant = serializer.save()
        AuditService.log(
            action='role_permission_granted',
            actor=self.request.user,
            target_type='role',
            target_id=grant.role.id,
            metadata={'permission_id': grant.permission.id, 'codename': grant.permission.codename},
            request=self.request
        )

    def destroy(self, request, *args, **kwargs):
        grant = self.get_object()
        if grant.role.slug == 'super-admin':
            return Response({'detail': 'Super Admin permissions cannot be modified.'}, status=status.HTTP_400_BAD_REQUEST)
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
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        if not AuthorizationService.has_permission(request.user, 'permission.revoke'):
            return Response(status=status.HTTP_403_FORBIDDEN)
        
        grant = self.get_object()
        if grant.role.slug == 'super-admin':
            return Response({'detail': 'Super Admin permissions cannot be modified.'}, status=status.HTTP_400_BAD_REQUEST)
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

