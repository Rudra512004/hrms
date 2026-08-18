from django.contrib import admin
from .models import Role, Permission, UserRole, RolePermission, UserPermissionGrant

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('codename', 'name', 'resource', 'action', 'is_active')
    search_fields = ('codename', 'name', 'resource')
    list_filter = ('is_active', 'resource', 'action')

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'is_active')
    search_fields = ('name', 'organization__name')
    list_filter = ('is_active', 'organization')

@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ('role', 'permission', 'created_at')
    search_fields = ('role__name', 'permission__codename')

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'assigned_by', 'is_revoked', 'expires_at')
    search_fields = ('user__email', 'role__name')
    list_filter = ('is_revoked',)

@admin.register(UserPermissionGrant)
class UserPermissionGrantAdmin(admin.ModelAdmin):
    list_display = ('user', 'permission', 'granted_by', 'is_revoked', 'expires_at')
    search_fields = ('user__email', 'permission__codename')
    list_filter = ('is_revoked',)
