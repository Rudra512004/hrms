from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class DocumentCategory(models.Model):
    organization = models.ForeignKey('organization.Organization', on_delete=models.CASCADE, related_name='document_categories')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'name')
        ordering = ['name']
        verbose_name_plural = "Document Categories"
        
    def __str__(self):
        return f"{self.name} ({self.organization.name})"

class TemplateType(models.TextChoices):
    EMAIL = 'email', _('Email Template')
    PDF = 'pdf', _('PDF Document')

class DocumentTemplate(models.Model):
    organization = models.ForeignKey('organization.Organization', on_delete=models.CASCADE, related_name='document_templates')
    category = models.ForeignKey(DocumentCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='templates')
    name = models.CharField(max_length=255)
    template_type = models.CharField(max_length=20, choices=TemplateType.choices)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_document_templates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('organization', 'name', 'template_type')
        ordering = ['-updated_at']
        
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"
        
class TemplateVersion(models.Model):
    template = models.ForeignKey(DocumentTemplate, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    subject = models.CharField(max_length=255, blank=True, help_text="Email subject or PDF title")
    body = models.TextField(help_text="HTML body with Django template variables e.g. {{ employee.first_name }}")
    is_published = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_template_versions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('template', 'version_number')
        ordering = ['-version_number']

    def __str__(self):
        return f"{self.template.name} v{self.version_number}"

def issued_document_path(instance, filename):
    import uuid
    ext = filename.split('.')[-1]
    return f"vault/{instance.organization.id}/{uuid.uuid4().hex}.{ext}"

class IssuedDocument(models.Model):
    organization = models.ForeignKey('organization.Organization', on_delete=models.CASCADE, related_name='issued_documents')
    employee = models.ForeignKey('employees.Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='issued_documents')
    candidate = models.ForeignKey('candidates.Candidate', on_delete=models.SET_NULL, null=True, blank=True, related_name='issued_documents')
    
    template_version = models.ForeignKey(TemplateVersion, on_delete=models.SET_NULL, null=True, blank=True, related_name='issued_documents')
    
    document_type = models.CharField(max_length=20, choices=TemplateType.choices)
    title = models.CharField(max_length=255)
    
    # For Emails or HTML Snapshots
    body_snapshot = models.TextField(blank=True, help_text="Rendered HTML at issue time")
    
    # For PDFs
    file_attachment = models.FileField(upload_to=issued_document_path, null=True, blank=True)
    
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='issued_documents')
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        return f"{self.title} - {self.employee or self.candidate}"

    def clean(self):
        if not self.employee and not self.candidate:
            raise ValidationError("Issued document must belong to either an employee or a candidate.")
