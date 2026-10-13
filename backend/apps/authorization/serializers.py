from rest_framework import serializers
from .models import Role, Permission, UserRole, UserPermissionGrant, RolePermission
from django.contrib.auth import get_user_model

User = get_user_model()

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = [
            'id', 'name', 'codename', 'resource', 'action', 'description', 'is_active',
            'category', 'ui_label', 'column_index', 'display_order', 'is_preserved_enterprise'
        ]
        read_only_fields = [
            'id', 'name', 'codename', 'resource', 'action', 'description', 'is_active',
            'category', 'ui_label', 'column_index', 'display_order', 'is_preserved_enterprise'
        ]

class RoleSerializer(serializers.ModelSerializer):
    badge = serializers.SerializerMethodField()
    users_count = serializers.SerializerMethodField()
    permissions_count = serializers.SerializerMethodField()
    effective_permissions_count = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    permission_ids = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = [
            'id', 'organization', 'name', 'slug', 'description', 'badge',
            'users_count', 'permissions_count', 'effective_permissions_count',
            'can_delete', 'is_system', 'is_active', 'permission_ids',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'organization', 'slug', 'is_system', 'badge', 'users_count',
            'permissions_count', 'effective_permissions_count', 'can_delete',
            'permission_ids', 'created_at', 'updated_at'
        ]

    def get_badge(self, obj):
        if obj.slug == 'super-admin':
            return 'Full access'
        return None

    def get_users_count(self, obj):
        return obj.user_roles.filter(is_revoked=False).values('user_id').distinct().count()

    def get_permissions_count(self, obj):
        if obj.slug == 'super-admin':
            return Permission.objects.filter(is_active=True, column_index__in=[1, 2, 3]).count()
        return obj.role_permissions.filter(permission__is_active=True, permission__column_index__in=[1, 2, 3]).count()

    def get_effective_permissions_count(self, obj):
        if obj.slug == 'super-admin':
            return Permission.objects.filter(is_active=True).count()
        return obj.role_permissions.filter(permission__is_active=True).count()

    def get_can_delete(self, obj):
        if obj.is_system:
            return False
        return not obj.user_roles.filter(is_revoked=False).exists()

    def get_permission_ids(self, obj):
        if obj.slug == 'super-admin':
            return list(Permission.objects.filter(is_active=True, column_index__in=[1, 2, 3]).values_list('id', flat=True))
        return list(obj.role_permissions.filter(permission__is_active=True).values_list('permission_id', flat=True))

class RolePermissionSerializer(serializers.ModelSerializer):
    permission_codename = serializers.CharField(source='permission.codename', read_only=True)

    class Meta:
        model = RolePermission
        fields = ['id', 'role', 'permission', 'permission_codename', 'created_at']
        read_only_fields = ['created_at']


class UserRoleSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_slug = serializers.CharField(source='role.slug', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = UserRole
        fields = ['id', 'user', 'user_email', 'role', 'role_name', 'role_slug', 'assigned_by', 'assigned_at', 'expires_at', 'is_revoked', 'revoked_at', 'scope', 'branch', 'team']
        read_only_fields = ['assigned_by', 'assigned_at', 'is_revoked', 'revoked_at']

class UserPermissionGrantSerializer(serializers.ModelSerializer):
    permission_codename = serializers.CharField(source='permission.codename', read_only=True)

    class Meta:
        model = UserPermissionGrant
        fields = ['id', 'user', 'permission', 'permission_codename', 'granted_by', 'granted_at', 'expires_at', 'is_revoked', 'revoked_at', 'scope', 'branch', 'team']
        read_only_fields = ['granted_by', 'granted_at', 'is_revoked', 'revoked_at']
