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
