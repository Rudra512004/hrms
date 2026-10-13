import os
import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

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

def organization_logo_upload_path(instance, filename):
    """
    Store tenant logos securely under:
      organization_logos/<org_id>/<uuid>.<ext>
    """
    ext = os.path.splitext(filename)[-1].lower()
    new_filename = f"{uuid.uuid4()}{ext}"
    org_id = instance.organization_id if instance.organization_id else 'common'
    return os.path.join('organization_logos', str(org_id), new_filename)


class ThemeMode(models.TextChoices):
    LIGHT = 'light', 'Light'
    DARK = 'dark', 'Dark'


class BrandingMode(models.TextChoices):
    DEFAULT = 'default', 'Default Theme'
    CUSTOM = 'custom', 'Custom Theme'


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

    # Phase 3F — Branding Mode & live theming
    branding_mode = models.CharField(
        max_length=20,
        choices=BrandingMode.choices,
        default=BrandingMode.DEFAULT,
        help_text="Active theming mode: 'default' (platform tokens + logo) or 'custom' (brand palette).",
    )
    selected_palette = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Identifier of the selected palette suggestion (e.g. 'vibrant', 'professional', 'deep').",
    )
    palette_suggestions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of generated color palette suggestion dictionaries.",
    )
    manual_overrides = models.JSONField(
        default=dict,
        blank=True,
        help_text="Manual color overrides dictionary (e.g. {'primary_color': '#166534'}).",
    )

    # Branding assets (stored as URLs or local media files)
    logo_file = models.FileField(
        upload_to=organization_logo_upload_path,
        null=True,
        blank=True,
        help_text="Uploaded logo file stored in tenant media directory.",
    )
    logo_url = models.CharField(max_length=1024, blank=True, default='')
    favicon_url = models.CharField(max_length=1024, blank=True, default='')
    login_banner_url = models.CharField(max_length=1024, blank=True, default='')
    watermark_url = models.CharField(max_length=1024, blank=True, default='')
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


class OnboardingStatus(models.TextChoices):
    NOT_STARTED = 'not_started', 'Not Started'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    ABANDONED = 'abandoned', 'Abandoned'


def validate_onboarding_metadata(value):
    """
    Validates that metadata is a JSON object and contains no sensitive credentials,
    tokens, passwords, or attempts to override trusted tenant/authorization identifiers.
    """
    if not isinstance(value, dict):
        raise ValidationError("Onboarding metadata must be a JSON object (dictionary).")

    forbidden_exact = {
        'password', 'secret', 'token', 'access_token', 'refresh_token',
        'auth_token', 'credentials', 'api_key', 'private_key',
        'organization_id', 'org_id', 'owner_id', 'user_id',
        'is_superuser', 'is_staff', 'roles', 'permissions',
        'role', 'permission', 'is_active',
    }

    forbidden_substrings = {'password', 'token', 'secret', 'cred'}

    def check_dict(d, path=""):
        for k, v in d.items():
            k_lower = str(k).lower().strip()
            current_path = f"{path}.{k}" if path else str(k)

            if k_lower in forbidden_exact:
                raise ValidationError(
                    f"Metadata key '{current_path}' is forbidden. Sensitive credentials and "
                    f"trusted identity/role fields cannot be stored in onboarding metadata."
                )

            if any(sub in k_lower for sub in forbidden_substrings):
                raise ValidationError(
                    f"Metadata key '{current_path}' contains sensitive term and is forbidden."
                )

            if isinstance(v, str):
                v_lower = v.lower()
                if v_lower.startswith('pbkdf2_') or v_lower.startswith('argon2') or v_lower.startswith('bcrypt'):
                    raise ValidationError(f"Metadata field '{current_path}' contains hashed credential data.")
                if v.startswith('eyJ') and len(v) > 60 and '.' in v:
                    raise ValidationError(f"Metadata field '{current_path}' appears to contain a JWT token.")
            elif isinstance(v, dict):
                check_dict(v, current_path)
            elif isinstance(v, list):
                for idx, item in enumerate(v):
                    if isinstance(item, dict):
                        check_dict(item, f"{current_path}[{idx}]")

    check_dict(value)


class OrganizationOnboarding(models.Model):
    """
    Durable state machine tracking organization first-time setup and onboarding wizard progress.
    Ensures exactly one onboarding record per tenant organization, protects tenant ownership,
    and isolates incomplete organizations from operational usage.
    """
    STAGE_MIN = 1
    STAGE_MAX = 7

    STAGE_NAMES = {
        1: 'Organization Details',
        2: 'Initial Branch',
        3: 'Organizational Structure',
        4: 'Working Calendar and Holidays',
        5: 'Shift and Attendance Configuration',
        6: 'Initial Administrator and RBAC',
        7: 'Review and Complete',
    }

    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name='onboarding',
        help_text='Organization undergoing or having completed onboarding',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='organization_onboardings',
        help_text='User initiating and responsible for the onboarding process',
    )
    status = models.CharField(
        max_length=20,
        choices=OnboardingStatus.choices,
        default=OnboardingStatus.NOT_STARTED,
        db_index=True,
    )
    current_stage = models.PositiveSmallIntegerField(
        default=STAGE_MIN,
        validators=[MinValueValidator(STAGE_MIN), MaxValueValidator(STAGE_MAX)],
        help_text='Current active stage (1 to 7)',
    )
    completed_stages = models.JSONField(
        default=list,
        blank=True,
        help_text='List of completed stage numbers (1 to 7)',
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        validators=[validate_onboarding_metadata],
        help_text='Non-sensitive workflow metadata and step drafts',
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when onboarding was successfully completed',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organization_onboarding'
        verbose_name = 'Organization Onboarding'
        verbose_name_plural = 'Organization Onboardings'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=OnboardingStatus.values),
                name='org_onboarding_valid_status',
            ),
            models.CheckConstraint(
                condition=models.Q(current_stage__gte=1, current_stage__lte=7),
                name='org_onboarding_valid_current_stage',
            ),
        ]

    def __str__(self):
        return f"Onboarding: {self.organization.name} [{self.get_status_display()}] (Stage {self.current_stage}/7)"

    @property
    def is_complete(self):
        return self.status == OnboardingStatus.COMPLETED

    @property
    def is_in_progress(self):
        return self.status == OnboardingStatus.IN_PROGRESS

    def clean(self):
        super().clean()

        if self.status not in OnboardingStatus.values:
            raise ValidationError({'status': f"Invalid status '{self.status}'. Must be one of {OnboardingStatus.values}."})

        if not (self.STAGE_MIN <= self.current_stage <= self.STAGE_MAX):
            raise ValidationError({'current_stage': f"Stage must be between {self.STAGE_MIN} and {self.STAGE_MAX}."})

        if not isinstance(self.completed_stages, list):
            raise ValidationError({'completed_stages': "completed_stages must be a list of stage numbers."})

        for stage in self.completed_stages:
            if not isinstance(stage, int) or not (self.STAGE_MIN <= stage <= self.STAGE_MAX):
                raise ValidationError({
                    'completed_stages': f"Invalid stage number '{stage}'. Must be an integer between {self.STAGE_MIN} and {self.STAGE_MAX}."
                })

        # Deduplicate and sort completed_stages
        self.completed_stages = sorted(list(set(self.completed_stages)))

        # Metadata validation
        if self.metadata:
            validate_onboarding_metadata(self.metadata)

        # Status consistency checks
        if self.status == OnboardingStatus.COMPLETED:
            required_stages = list(range(self.STAGE_MIN, self.STAGE_MAX + 1))
            missing = set(required_stages) - set(self.completed_stages)
            if missing:
                raise ValidationError({
                    'status': f"Cannot mark onboarding completed with missing stages: {sorted(list(missing))}."
                })
            if not self.completed_at:
                self.completed_at = timezone.now()
        elif self.status == OnboardingStatus.NOT_STARTED:
            if self.completed_stages:
                raise ValidationError({
                    'status': "An onboarding in 'not_started' status cannot have completed stages."
                })

        # Tenant owner consistency check
        if self.owner_id and hasattr(self.organization, 'owner_registration'):
            reg = getattr(self.organization, 'owner_registration', None)
            if reg and reg.user_id and reg.user_id != self.owner_id:
                raise ValidationError({
                    'owner': "Onboarding owner must match the registered tenant owner user."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def mark_stage_complete(self, stage_number):
        """Marks a single stage complete and advances current_stage if appropriate."""
        if not (self.STAGE_MIN <= stage_number <= self.STAGE_MAX):
            raise ValueError(f"Stage number must be between {self.STAGE_MIN} and {self.STAGE_MAX}.")

        stages = set(self.completed_stages or [])
        stages.add(stage_number)
        self.completed_stages = sorted(list(stages))

        if self.status == OnboardingStatus.NOT_STARTED:
            self.status = OnboardingStatus.IN_PROGRESS

        if self.current_stage <= stage_number and stage_number < self.STAGE_MAX:
            self.current_stage = stage_number + 1

        self.save()

    def mark_completed(self):
        """Marks all stages complete and transitions status to COMPLETED."""
        self.completed_stages = list(range(self.STAGE_MIN, self.STAGE_MAX + 1))
        self.current_stage = self.STAGE_MAX
        self.status = OnboardingStatus.COMPLETED
        if not self.completed_at:
            self.completed_at = timezone.now()
        self.save()

    def update_metadata(self, new_data):
        """Safely updates metadata with validation."""
        if not isinstance(new_data, dict):
            raise ValueError("Metadata update must be a dictionary.")
        validate_onboarding_metadata(new_data)
        updated = dict(self.metadata or {})
        updated.update(new_data)
        self.metadata = updated
        self.save(update_fields=['metadata', 'updated_at'])



class InvitationStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    ACCEPTED = 'accepted', 'Accepted'
    EXPIRED = 'expired', 'Expired'
    REVOKED = 'revoked', 'Revoked'


class EmailDeliveryStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    SENT = 'sent', 'Sent'
    FAILED = 'failed', 'Failed'


class OrganizationInvitation(models.Model):
    """
    Cryptographically secure, single-use invitation for administrative or scoped
    role assignment within a tenant organization.
    
    Product Uniqueness Rule:
    For Phase 3E Stage 6 onboarding and initial-administrator governance, exactly one
    active PENDING invitation per (organization, role) is permitted at any given time.
    Creating a new invitation or rotating an administrator in Stage 6 requires explicitly
    revoking or replacing the prior pending invitation, ensuring that only one authoritative
    unaccepted token exists in circulation.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='invitations',
        help_text='Tenant organization to which the invitee is being invited.',
    )
    email = models.EmailField(
        db_index=True,
        help_text='Normalized lowercase email of the intended administrator.',
    )
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.ForeignKey(
        'authorization.Role',
        on_delete=models.CASCADE,
        related_name='invitations',
        help_text='Organization-scoped role to grant upon acceptance.',
    )
    token_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text='SHA-256 hash of the single-use invitation token. Raw token is never stored.',
    )
    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        db_index=True,
    )
    email_delivery_status = models.CharField(
        max_length=20,
        choices=EmailDeliveryStatus.choices,
        default=EmailDeliveryStatus.PENDING,
        db_index=True,
        help_text='Separate status tracking actual SMTP delivery outcome.',
    )
    email_delivery_error = models.TextField(
        blank=True,
        default='',
        help_text='Diagnostic details if email delivery failed.',
    )
    email_sent_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_organization_invitations',
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accepted_organization_invitations',
    )
    expires_at = models.DateTimeField(
        help_text='Timestamp after which the invitation token is no longer valid.',
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    resend_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organization_invitation'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'email', 'status']),
            models.Index(fields=['token_hash']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=InvitationStatus.values),
                name='org_invitation_valid_status',
            ),
            models.CheckConstraint(
                condition=models.Q(email_delivery_status__in=EmailDeliveryStatus.values),
                name='org_invitation_valid_delivery_status',
            ),
            models.UniqueConstraint(
                fields=['organization', 'role'],
                condition=models.Q(status=InvitationStatus.PENDING),
                name='unique_pending_org_role_invitation',
            ),
        ]

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()

        if self.status not in InvitationStatus.values:
            raise ValidationError({'status': f"Invalid status '{self.status}'. Must be one of {InvitationStatus.values}."})

        if self.email_delivery_status not in EmailDeliveryStatus.values:
            raise ValidationError({'email_delivery_status': f"Invalid email delivery status '{self.email_delivery_status}'."})

        if not self.expires_at:
            raise ValidationError({'expires_at': "expires_at timestamp is required."})

        if self.role_id and self.organization_id and self.role.organization_id != self.organization_id:
            raise ValidationError({'role': 'Invited role must belong to the invitation organization.'})

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invitation for {self.email} [{self.role.name} in {self.organization.name}] ({self.status})"


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

