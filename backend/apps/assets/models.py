from django.db import models
from django.conf import settings
from django.utils import timezone

from apps.organization.models import Organization, Branch
from apps.employees.models import Employee


class AssetCategory(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='asset_categories'
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Asset Categories'
        unique_together = [('organization', 'name'), ('organization', 'code')]
        indexes = [
            models.Index(fields=['organization', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class AssetStatus(models.TextChoices):
    AVAILABLE = 'available', 'Available'
    ASSIGNED = 'assigned', 'Assigned'
    UNDER_MAINTENANCE = 'under_maintenance', 'Under Maintenance'
    RETIRED = 'retired', 'Retired'
    LOST = 'lost', 'Lost'


class Asset(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='assets'
    )
    category = models.ForeignKey(
        AssetCategory, on_delete=models.PROTECT, related_name='assets'
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='assets'
    )
    asset_tag = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=200)
    serial_number = models.CharField(max_length=150, blank=True, default='')
    model_number = models.CharField(max_length=150, blank=True, default='')
    status = models.CharField(
        max_length=30,
        choices=AssetStatus.choices,
        default=AssetStatus.AVAILABLE,
        db_index=True,
    )
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    warranty_expiry = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('organization', 'asset_tag')]
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['organization', 'category']),
        ]

    def __str__(self):
        return f"{self.name} [{self.asset_tag}]"


class AssetAssignment(models.Model):
    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name='assignments'
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='asset_assignments'
    )
    allocated_at = models.DateField(default=timezone.now)
    expected_return_date = models.DateField(null=True, blank=True)
    returned_at = models.DateField(null=True, blank=True)
    condition_at_allocation = models.CharField(max_length=50, default='good')
    condition_at_return = models.CharField(max_length=50, blank=True, default='')
    allocation_notes = models.TextField(blank=True, default='')
    return_notes = models.TextField(blank=True, default='')
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['asset', 'is_active']),
            models.Index(fields=['employee', 'is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['asset'],
                condition=models.Q(is_active=True),
                name='unique_active_asset_assignment',
            )
        ]

    def __str__(self):
        return f"{self.asset.asset_tag} -> {self.employee.employee_code} (Active: {self.is_active})"
