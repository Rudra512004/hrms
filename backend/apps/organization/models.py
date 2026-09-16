from django.db import models

class Organization(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    name = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class WorkingCalendar(models.Model):
    branch = models.OneToOneField('organization.Branch', on_delete=models.CASCADE, related_name='working_calendar')
    work_days = models.CharField(
        max_length=50,
        default='0,1,2,3,4',
        help_text='Comma separated integers (0=Monday, 6=Sunday)'
    )

    def __str__(self):
        return f"{self.branch.name} Calendar"

    def get_work_days_list(self):
        try:
            return [int(d.strip()) for d in self.work_days.split(',') if d.strip().isdigit()]
        except (ValueError, AttributeError):
            return [0, 1, 2, 3, 4]

import ipaddress
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator

def validate_network(value):
    try:
        ipaddress.ip_network(value, strict=False)
    except ValueError:
        raise ValidationError("Invalid CIDR network")

class OfficeNetwork(models.Model):
    branch = models.ForeignKey('organization.Branch', on_delete=models.CASCADE, related_name='office_networks')
    name = models.CharField(max_length=255)
    network = models.CharField(max_length=45, validators=[validate_network], help_text="e.g., 203.0.113.0/24")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('branch', 'network')

    def __str__(self):
        return f"{self.name} ({self.network})"

class Department(models.Model):
    branch = models.ForeignKey('organization.Branch', on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('branch', 'name')

    def __str__(self):
        return f"{self.name} ({self.branch.name})"

class Team(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    manager = models.ForeignKey('employees.Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_teams')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('department', 'name')

    def clean(self):
        super().clean()
        if self.manager:
            if self.manager.branch_id != self.department.branch_id:
                raise ValidationError({'manager': 'Manager must belong to the same branch as the team.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.department.name})"

class Designation(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='designations')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'name')

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

class Branch(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    radius = models.FloatField(default=100.0, help_text="Radius in meters", validators=[MinValueValidator(100.0)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'name')

    def clean(self):
        super().clean()
        if self.radius < 100.0:
            raise ValidationError({'radius': 'Branch radius must be at least 100 meters.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

class AttendancePolicy(models.Model):
    branch = models.OneToOneField('organization.Branch', on_delete=models.CASCADE, related_name='attendance_policy')
    is_office_gps_enabled = models.BooleanField(default=True)
    is_office_ip_enabled = models.BooleanField(default=False)
    is_wfh_enabled = models.BooleanField(default=False)
    wfh_bypasses_office_restrictions = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Attendance Policy ({self.branch.name})"

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Branch)
def auto_provision_branch_configs(sender, instance, created, **kwargs):
    if created:
        AttendancePolicy.objects.get_or_create(branch=instance)
        WorkingCalendar.objects.get_or_create(branch=instance)
