from django.db import models
from django.conf import settings
from apps.organization.models import Organization

class Permission(models.Model):
    name = models.CharField(max_length=255)
    codename = models.CharField(max_length=255, unique=True, help_text="e.g., employee.view")
    resource = models.CharField(max_length=100, help_text="e.g., employee")
    action = models.CharField(max_length=100, help_text="e.g., view, create")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('resource', 'action')

    def __str__(self):
        return self.codename

class Role(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='roles')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'name')

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='role_permissions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('role', 'permission')

    def __str__(self):
        return f"{self.role.name} -> {self.permission.codename}"

class ScopeChoices(models.TextChoices):
    ORGANIZATION = 'organization', 'Organization'
    BRANCH = 'branch', 'Branch'
    TEAM = 'team', 'Team'

class UserRole(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    assigned_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    scope = models.CharField(max_length=20, choices=ScopeChoices.choices, default=ScopeChoices.ORGANIZATION)
    branch = models.ForeignKey('organization.Branch', on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    team = models.ForeignKey('organization.Team', on_delete=models.CASCADE, null=True, blank=True, related_name='+')

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError

        if self.scope == ScopeChoices.ORGANIZATION and (self.branch_id is not None or self.team_id is not None):
            raise ValidationError({'scope': 'Branch and Team must be null when scope is organization.'})

        if self.scope == ScopeChoices.BRANCH:
            if self.branch_id is None:
                raise ValidationError({'branch': 'Branch must be set when scope is branch.'})
            if self.team_id is not None:
                raise ValidationError({'team': 'Team must be null when scope is branch.'})

        if self.scope == ScopeChoices.TEAM:
            if self.team_id is None:
                raise ValidationError({'team': 'Team must be set when scope is team.'})

            # If both branch and team are provided, ensure they align structurally
            if self.branch_id is not None and self.team.department.branch_id != self.branch_id:
                raise ValidationError({'team': 'Team must belong to the specified branch.'})

            # Verify team organization matches role organization
            if hasattr(self, 'role') and getattr(self.role, 'organization_id', None):
                if self.team.department.branch.organization_id != self.role.organization_id:
                    raise ValidationError({'team': 'Team must belong to the same organization as the role.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} - {self.role.name}"

class UserPermissionGrant(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='direct_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='direct_grants')
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    scope = models.CharField(max_length=20, choices=ScopeChoices.choices, default=ScopeChoices.ORGANIZATION)
    branch = models.ForeignKey('organization.Branch', on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    team = models.ForeignKey('organization.Team', on_delete=models.CASCADE, null=True, blank=True, related_name='+')

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError

        if self.scope == ScopeChoices.ORGANIZATION and (self.branch_id is not None or self.team_id is not None):
            raise ValidationError({'scope': 'Branch and Team must be null when scope is organization.'})

        if self.scope == ScopeChoices.BRANCH:
            if self.branch_id is None:
                raise ValidationError({'branch': 'Branch must be set when scope is branch.'})
            if self.team_id is not None:
                raise ValidationError({'team': 'Team must be null when scope is branch.'})

        if self.scope == ScopeChoices.TEAM:
            if self.team_id is None:
                raise ValidationError({'team': 'Team must be set when scope is team.'})

            if self.branch_id is not None and self.team.department.branch_id != self.branch_id:
                raise ValidationError({'team': 'Team must belong to the specified branch.'})

            # Verify team organization matches target user's organization
            if hasattr(self, 'user') and hasattr(self.user, 'employee') and getattr(self.user.employee, 'organization_id', None):
                if self.team.department.branch.organization_id != self.user.employee.organization_id:
                    raise ValidationError({'team': 'Team must belong to the target user\'s organization.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} - {self.permission.codename}"
