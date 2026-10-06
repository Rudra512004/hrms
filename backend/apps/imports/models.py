from django.db import models
from django.conf import settings
from apps.organization.models import Organization

class ImportStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    DRY_RUN = 'dry_run', 'Dry Run'

class DataImport(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='imports')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    import_type = models.CharField(max_length=50) # 'employee', 'branch', etc.
    file = models.FileField(upload_to='imports/')
    status = models.CharField(max_length=20, choices=ImportStatus.choices, default=ImportStatus.PENDING)
    total_rows = models.IntegerField(default=0)
    successful_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    error_log = models.JSONField(default=dict, blank=True) # {row_number: ['error msg']}
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.import_type} import by {self.uploaded_by} on {self.created_at}'
