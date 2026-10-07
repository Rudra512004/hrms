from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class Organization(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=50, unique=True, null=True, blank=True, help_text="Tenant unique code")
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

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.work_days is not None:
            if not self.work_days.strip():
                raise ValidationError({'work_days': 'work_days cannot be empty.'})
            for d in self.work_days.split(','):
                d_str = d.strip()
                if not d_str.isdigit() or int(d_str) < 0 or int(d_str) > 6:
                    raise ValidationError({'work_days': f"Invalid work day '{d_str}'. Must be integers between 0 and 6."})

    def get_work_days_list(self):
        from .exceptions import WorkingCalendarConfigurationError
        if not self.work_days or not self.work_days.strip():
            raise WorkingCalendarConfigurationError(f"Working calendar for branch {self.branch_id} has unconfigured work days.")
        days = []
        for d in self.work_days.split(','):
            d_str = d.strip()
            if not d_str.isdigit() or int(d_str) < 0 or int(d_str) > 6:
                raise WorkingCalendarConfigurationError(f"Invalid work day '{d_str}' in working calendar for branch {self.branch_id}.")
            days.append(int(d_str))
        if not days:
            raise WorkingCalendarConfigurationError(f"Working calendar for branch {self.branch_id} has no valid work days.")
        return days

    def get_recurring_rules_dict(self):
        """Returns {(weekday, occurrence): is_working} for all configured recurring rules."""
        return {(r.weekday, r.occurrence): r.is_working for r in self.recurring_rules.all()}

    def is_working_day(self, target_date):
        """
        Determines whether target_date is a working day based on:
        1. Specific recurring rule for (weekday, occurrence)
        2. Base calendar work_days
        Does NOT check holidays; holiday precedence is evaluated in WorkingCalendarService.
        """
        weekday = target_date.weekday()
        occurrence = (target_date.day - 1) // 7 + 1
        rule = self.recurring_rules.filter(weekday=weekday, occurrence=occurrence).first()
        if rule is not None:
            return rule.is_working
        return weekday in self.get_work_days_list()


class WorkingCalendarRule(models.Model):
    working_calendar = models.ForeignKey(
        WorkingCalendar,
        on_delete=models.CASCADE,
        related_name='recurring_rules'
    )
    weekday = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        help_text='0=Monday, 6=Sunday'
    )
    occurrence = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='1=1st, 2=2nd, 3=3rd, 4=4th, 5=5th occurrence in the month'
    )
    is_working = models.BooleanField(
        default=False,
        help_text='Whether this occurrence is a working day (True) or non-working day (False)'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('working_calendar', 'weekday', 'occurrence')
        ordering = ['weekday', 'occurrence']

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.weekday is not None and (self.weekday < 0 or self.weekday > 6):
            raise ValidationError({'weekday': 'Weekday must be an integer between 0 (Monday) and 6 (Sunday).'})
        if self.occurrence is not None and (self.occurrence < 1 or self.occurrence > 5):
            raise ValidationError({'occurrence': 'Occurrence must be an integer between 1 and 5.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        wk = weekdays[self.weekday] if 0 <= self.weekday <= 6 else str(self.weekday)
        status = 'Working' if self.is_working else 'Non-working'
        return f"{self.working_calendar.branch.name} - {self.occurrence} {wk}: {status}"


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
    code = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('branch', 'name'), ('branch', 'code')]

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
    code = models.CharField(max_length=50, null=True, blank=True)
    level = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('organization', 'name'), ('organization', 'code')]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

class Branch(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    address = models.TextField(blank=True) # Legacy
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    timezone = models.CharField(max_length=50, default='UTC')
    is_head_office = models.BooleanField(default=False)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    radius = models.FloatField(default=100.0, help_text="Radius in meters", validators=[MinValueValidator(100.0)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('organization', 'name'), ('organization', 'code')]

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

class ThemeMode(models.TextChoices):
    LIGHT = 'light', 'Light'
    DARK = 'dark', 'Dark'


class TenantBrandingAndConfig(models.Model):
    """
    Tenant-specific branding, theming, and custom-field configuration.
    One record per Organization, auto-provisioned on Organization creation.
    All fields are optional so the system works with empty/default values.
    """
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name='branding',
        primary_key=True,
    )

    # Branding assets (stored as URLs; upload handled via separate media endpoints)
    logo_url = models.URLField(max_length=1024, blank=True, default='')
    favicon_url = models.URLField(max_length=1024, blank=True, default='')
    login_banner_url = models.URLField(max_length=1024, blank=True, default='')
    watermark_url = models.URLField(max_length=1024, blank=True, default='')
    watermark_opacity = models.DecimalField(
        max_digits=3, decimal_places=2,
        default='0.08',
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text='0.00 – 1.00 (transparent to fully opaque)',
    )

    # Color palette (stored as hex strings, e.g. "#4F46E5")
    primary_color = models.CharField(max_length=20, blank=True, default='')
    secondary_color = models.CharField(max_length=20, blank=True, default='')
    accent_color = models.CharField(max_length=20, blank=True, default='')
    sidebar_bg_color = models.CharField(max_length=20, blank=True, default='')

    # Typography and locale
    default_theme_mode = models.CharField(
        max_length=10,
        choices=ThemeMode.choices,
        default=ThemeMode.LIGHT,
    )
    font_family = models.CharField(max_length=100, blank=True, default='')
    currency_code = models.CharField(max_length=10, blank=True, default='INR')
    date_format = models.CharField(
        max_length=30, blank=True, default='DD/MM/YYYY',
        help_text='e.g. DD/MM/YYYY, MM-DD-YYYY, YYYY-MM-DD',
    )

    # Module enablement — JSONField list of module keys enabled for this tenant
    # e.g. ["attendance", "leaves", "payroll", "assets", "candidates", "wellness"]
    enabled_modules_json = models.JSONField(
        default=list,
        blank=True,
        help_text='List of enabled module keys for this tenant',
    )

    # Custom fields schema — enables Zoho-style per-module custom fields
    # Schema format: [{"key": "employee_vehicle_number", "label": "Vehicle Number",
    #                   "type": "text", "required": false, "module": "employee"}]
    custom_fields_schema = models.JSONField(
        default=list,
        blank=True,
        help_text='Custom field definitions for this tenant',
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tenant Branding & Config'
        verbose_name_plural = 'Tenant Branding & Configs'

    def __str__(self):
        return f'Branding: {self.organization.name}'


from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Branch)
def auto_provision_branch_configs(sender, instance, created, **kwargs):
    if created:
        AttendancePolicy.objects.get_or_create(branch=instance)
        WorkingCalendar.objects.get_or_create(branch=instance)


@receiver(post_save, sender=Organization)
def auto_provision_tenant_branding(sender, instance, created, **kwargs):
    """Auto-create an empty TenantBrandingAndConfig row whenever a new Organization is saved."""
    if created:
        TenantBrandingAndConfig.objects.get_or_create(organization=instance)
