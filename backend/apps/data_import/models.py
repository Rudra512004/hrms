import uuid
from django.db import models
from django.conf import settings
from apps.organization.models import Organization


def import_file_upload_path(instance, filename):
    """Store uploaded CSV files at: media/private/data_import/<org_id>/<uuid>.csv"""
    import os
    ext = os.path.splitext(filename)[-1].lower()
    new_filename = f"{uuid.uuid4()}{ext}"
    return os.path.join('data_import', str(instance.organization_id), new_filename)


class ImportJob(models.Model):
    """
    Tracks the lifecycle of a single CSV import operation.
    Status transitions: pending → validating → validated → executing → completed / failed
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('validating', 'Validating'),
        ('validated', 'Validated'),
        ('executing', 'Executing'),
        ('completed', 'Completed'),
        ('completed_with_errors', 'Completed With Errors'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='import_jobs'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='import_jobs'
    )
    template_key = models.CharField(max_length=50, db_index=True)
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default='pending'
    )
    file = models.FileField(upload_to=import_file_upload_path)
    original_filename = models.CharField(max_length=255)

    # Stats populated during validation/execution
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)

    # Preview data (JSON): list of first N parsed rows for user confirmation
    preview_data = models.JSONField(default=list, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Import {self.template_key} — {self.status} ({self.id})"


class ImportJobError(models.Model):
    """
    Per-row error record for a failed/partially-failed import.
    Used to generate the downloadable error report CSV.
    """
    job = models.ForeignKey(
        ImportJob, on_delete=models.CASCADE, related_name='errors'
    )
    row_number = models.PositiveIntegerField(help_text="1-indexed CSV row number (excluding header)")
    field = models.CharField(max_length=100, blank=True, help_text="CSV column that caused the error")
    error_type = models.CharField(max_length=50, help_text="e.g. required, invalid_type, duplicate, cross_tenant")
    message = models.TextField()
    row_data = models.JSONField(default=dict, blank=True, help_text="Sanitized copy of the row for context")

    class Meta:
        ordering = ['row_number', 'field']

    def __str__(self):
        return f"Row {self.row_number}: {self.field} — {self.error_type}"
