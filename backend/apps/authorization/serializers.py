from rest_framework import serializers
from .models import Role, Permission, UserRole, UserPermissionGrant
from django.contrib.auth import get_user_model

User = get_user_model()

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename', 'resource', 'action', 'description', 'is_active']
        read_only_fields = ['id', 'name', 'codename', 'resource', 'action', 'description', 'is_active']

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'organization', 'name', 'description', 'is_active']
        read_only_fields = ['organization']

class UserRoleSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True)

    class Meta:
        model = UserRole
        fields = ['id', 'user', 'role', 'role_name', 'assigned_by', 'assigned_at', 'expires_at', 'is_revoked', 'revoked_at']
        read_only_fields = ['assigned_by', 'assigned_at', 'is_revoked', 'revoked_at']

class UserPermissionGrantSerializer(serializers.ModelSerializer):
    permission_codename = serializers.CharField(source='permission.codename', read_only=True)

    class Meta:
        model = UserPermissionGrant
        fields = ['id', 'user', 'permission', 'permission_codename', 'granted_by', 'granted_at', 'expires_at', 'is_revoked', 'revoked_at']
        read_only_fields = ['granted_by', 'granted_at', 'is_revoked', 'revoked_at']
