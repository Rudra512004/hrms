from django.db import models
from django.conf import settings
from apps.organization.models import Organization

class Notification(models.Model):
    """
    Represents an in-app notification sent to a specific user.
    """
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text="The user receiving the notification"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text="The organization context."
    )
    notification_type = models.CharField(
        max_length=50,
        help_text="Categorization code (e.g., 'LEAVE_APPROVED', 'PAYSLIP_ISSUED')"
    )
    title = models.CharField(
        max_length=255,
        help_text="Short summary of the notification"
    )
    message = models.TextField(
        help_text="Detailed notification content"
    )
    reference_id = models.CharField(
        max_length=150,
        blank=True,
        help_text="Optional identifier of the related object (e.g., LeaveRequest ID). Not a strict foreign key to allow safe deletion of referenced objects."
    )
    is_read = models.BooleanField(
        default=False,
        help_text="Whether the user has viewed this notification"
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read', '-created_at']),
            models.Index(fields=['organization', '-created_at']),
        ]

    def __str__(self):
        return f"To {self.recipient}: {self.title} ({'Read' if self.is_read else 'Unread'})"


class Announcement(models.Model):
    """An organization announcement with optional branch targeting.

    A branch-null announcement is visible to everyone in the organization.
    Publishing is explicit so unfinished drafts never become employee-facing.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='announcements')
    branch = models.ForeignKey('organization.Branch', on_delete=models.CASCADE, null=True, blank=True, related_name='announcements')
    title = models.CharField(max_length=180)
    body = models.TextField(max_length=5000)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [models.Index(fields=['organization', 'is_published', '-published_at'], name='notif_ann_org_pub_idx')]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.branch_id and self.branch.organization_id != self.organization_id:
            raise ValidationError({'branch': 'Branch must belong to the announcement organization.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class OrganizationEmailSettings(models.Model):
    """Organization identity used with the deployment's SMTP provider.

    SMTP credentials deliberately remain deployment secrets rather than being
    stored in the HRMS database.
    """
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='email_settings')
    sender_name = models.CharField(max_length=120, blank=True)
    from_email = models.EmailField(blank=True)
    reply_to_email = models.EmailField(blank=True)
    automation_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class EmailTemplate(models.Model):
    EVENT_CHOICES = [
        ('employee_onboarding', 'Employee onboarding'),
        ('candidate_offer', 'Candidate offer'),
        ('password_reset', 'Password reset'),
        ('announcement_published', 'Announcement published'),
        ('attendance_alert', 'Attendance alert'),
        ('scheduled_report', 'Scheduled report'),
    ]
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='email_templates')
    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES)
    name = models.CharField(max_length=120)
    subject = models.CharField(max_length=255)
    body = models.TextField(max_length=10000)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'event_type', 'name')


class EmailAutomationRule(models.Model):
    EVENT_CHOICES = EmailTemplate.EVENT_CHOICES
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='email_automation_rules')
    name = models.CharField(max_length=120)
    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES)
    recipient_mode = models.CharField(max_length=30, choices=[('event_recipient', 'Event recipient'), ('organization_admins', 'Organization administrators')], default='event_recipient')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'event_type', 'name')


class EmailDelivery(models.Model):
    STATUS_CHOICES = [('sent', 'Sent'), ('failed', 'Failed'), ('suppressed', 'Suppressed')]
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='email_deliveries')
    event_type = models.CharField(max_length=40)
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['organization', 'event_type', '-created_at'], name='email_delivery_org_event_idx')]
