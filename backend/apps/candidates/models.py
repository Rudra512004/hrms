"""
Candidate domain models.

Covers the workflow:
  HR creates Candidate → Offer → Onboarding Portal → Doc Upload →
  HR Verification → HR Approval → Convert to Employee

Candidate and Employee are SEPARATE identity entities.
Conversion is atomic and idempotent.
"""

import os
import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


# ---------------------------------------------------------------------------
# File storage helpers
# ---------------------------------------------------------------------------

def candidate_document_upload_path(instance, filename):
    """Store candidate docs at media/candidate_documents/<candidate_id>/<uuid>.<ext>"""
    ext = os.path.splitext(filename)[-1].lower()
    new_filename = f"{uuid.uuid4()}{ext}"
    return os.path.join('candidate_documents', str(instance.candidate_id), new_filename)


def letter_content_upload_path(instance, filename):
    """Store letter files at media/letters/<letter_type>/<uuid>.<ext>"""
    ext = os.path.splitext(filename)[-1].lower()
    new_filename = f"{uuid.uuid4()}{ext}"
    return os.path.join('letters', str(instance.letter_type), new_filename)


# ---------------------------------------------------------------------------
# Status choices — minimum required by the agreed workflow
# ---------------------------------------------------------------------------

class CandidateStatus(models.TextChoices):
    CREATED    = 'created',    'Created'        # HR created record
    OFFERED    = 'offered',    'Offer Sent'     # Offer letter generated & portal access given
    ONBOARDING = 'onboarding', 'Onboarding'     # Candidate actively submitting docs
    SUBMITTED  = 'submitted',  'Submitted'      # Candidate marked onboarding complete
    VERIFYING  = 'verifying',  'Under Verification'  # HR is reviewing docs
    APPROVED   = 'approved',   'Approved'       # HR approved, pending conversion
    CONVERTED  = 'converted',  'Converted to Employee'  # Employee record created
    REJECTED   = 'rejected',   'Rejected'       # HR rejected onboarding


# Valid forward-only status transitions
CANDIDATE_TRANSITIONS = {
    CandidateStatus.CREATED:    {CandidateStatus.OFFERED, CandidateStatus.REJECTED},
    CandidateStatus.OFFERED:    {CandidateStatus.ONBOARDING, CandidateStatus.REJECTED},
    CandidateStatus.ONBOARDING: {CandidateStatus.SUBMITTED, CandidateStatus.REJECTED},
    CandidateStatus.SUBMITTED:  {CandidateStatus.VERIFYING, CandidateStatus.ONBOARDING, CandidateStatus.REJECTED},
    CandidateStatus.VERIFYING:  {CandidateStatus.APPROVED, CandidateStatus.ONBOARDING, CandidateStatus.REJECTED},
    CandidateStatus.APPROVED:   {CandidateStatus.CONVERTED},
    CandidateStatus.CONVERTED:  set(),   # terminal
    CandidateStatus.REJECTED:   set(),   # terminal
}


class CandidateDocumentStatus(models.TextChoices):
    PENDING  = 'pending',  'Pending'
    VERIFIED = 'verified', 'Verified'
    REJECTED = 'rejected', 'Rejected'


class LetterType(models.TextChoices):
    OFFER       = 'offer',       'Offer Letter'
    APPOINTMENT = 'appointment', 'Appointment Letter'


# ---------------------------------------------------------------------------
# LetterTemplate — HR-managed wording/template (versioned snapshot on issue)
# ---------------------------------------------------------------------------

class LetterTemplate(models.Model):
    """
    HR-authored template for a letter type.

    Changes to wording apply to NEW letters only.
    Issued letters snapshot the content at issue time.
    """
    organization = models.ForeignKey(
        'organization.Organization',
        on_delete=models.CASCADE,
        related_name='letter_templates',
    )
    letter_type = models.CharField(max_length=30, choices=LetterType.choices)
    version     = models.PositiveIntegerField(default=1)
    subject     = models.CharField(max_length=255)
    body        = models.TextField(help_text="Template body. Supports {{candidate_name}}, {{designation}}, {{joining_date}}, {{organization}} placeholders.")
    is_active   = models.BooleanField(default=True)
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        # One active template per letter type per organization
        unique_together = ('organization', 'letter_type', 'version')
        ordering = ['-version']

    def __str__(self):
        return f"{self.get_letter_type_display()} v{self.version} ({self.organization.name})"


# ---------------------------------------------------------------------------
# Candidate — the core entity
# ---------------------------------------------------------------------------

class Candidate(models.Model):
    """
    A candidate exists independently of Employee.
    Employee creation happens ONLY at the controlled conversion step.
    """
    organization = models.ForeignKey(
        'organization.Organization',
        on_delete=models.CASCADE,
        related_name='candidates',
    )
    # The candidate's onboarding user account (set when offer is issued)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='candidate',
        help_text="Auth account created for the candidate onboarding portal"
    )
    # Traceability: set atomically during conversion
    employee = models.OneToOneField(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='candidate_record',
        help_text="Populated after conversion. Establishes candidate→employee traceability."
    )

    # Basic profile
    first_name       = models.CharField(max_length=150)
    last_name        = models.CharField(max_length=150)
    email            = models.EmailField(help_text="Candidate's personal/contact email")
    phone_number     = models.CharField(max_length=20, blank=True)
    address          = models.TextField(blank=True)

    # Role being offered
    applied_designation = models.ForeignKey(
        'organization.Designation',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='candidates',
    )
    proposed_joining_date = models.DateField(null=True, blank=True)
    notes                 = models.TextField(blank=True)

    # Workflow state
    status = models.CharField(
        max_length=20,
        choices=CandidateStatus.choices,
        default=CandidateStatus.CREATED,
        db_index=True,
    )

    # HR tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='candidates_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['email', 'organization']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def transition_to(self, new_status):
        """Validate and apply a status transition."""
        allowed = CANDIDATE_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValidationError(
                f"Cannot transition from '{self.status}' to '{new_status}'. "
                f"Allowed: {', '.join(allowed) or 'none (terminal state)'}."
            )
        self.status = new_status

    @property
    def is_converted(self):
        return self.status == CandidateStatus.CONVERTED and self.employee_id is not None


# ---------------------------------------------------------------------------
# IssuedLetter — snapshot at issue time (historical preservation)
# ---------------------------------------------------------------------------

class IssuedLetter(models.Model):
    """
    A historical snapshot of a letter issued to a candidate/employee.

    The body_snapshot preserves the exact wording at issue time.
    Future template changes do NOT affect this record.
    """
    candidate       = models.ForeignKey(
        Candidate, on_delete=models.CASCADE,
        related_name='issued_letters',
    )
    letter_type     = models.CharField(max_length=30, choices=LetterType.choices)
    template        = models.ForeignKey(
        LetterTemplate, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='issued_letters',
        help_text="Template used at issue time (for reference only)"
    )
    template_version = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Snapshot of template version number at issue time"
    )
    subject_snapshot = models.CharField(max_length=255)
    body_snapshot    = models.TextField(help_text="Rendered/final letter body at issue time")
    issued_by        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='issued_letters',
    )
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        return f"{self.get_letter_type_display()} – {self.candidate.get_full_name()} ({self.issued_at.date()})"


# ---------------------------------------------------------------------------
# CandidateDocument — uploaded by candidate during onboarding
# ---------------------------------------------------------------------------

ALLOWED_CANDIDATE_DOC_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.doc', '.docx'}
MAX_CANDIDATE_DOC_SIZE = 5 * 1024 * 1024  # 5 MB


class CandidateDocument(models.Model):
    """Documents uploaded by the candidate during the onboarding portal stage."""
    candidate     = models.ForeignKey(
        Candidate, on_delete=models.CASCADE,
        related_name='documents',
    )
    document_type = models.CharField(
        max_length=50,
        choices=[
            ('identity',   'Identity Proof'),
            ('address',    'Address Proof'),
            ('education',  'Education Certificate'),
            ('employment', 'Previous Employment Proof'),
            ('other',      'Other'),
        ],
        default='other',
    )
    document_name = models.CharField(max_length=255)
    file          = models.FileField(upload_to=candidate_document_upload_path)
    file_size     = models.PositiveIntegerField(help_text="File size in bytes")
    mime_type     = models.CharField(max_length=100, blank=True)
    description   = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=CandidateDocumentStatus.choices,
        default=CandidateDocumentStatus.PENDING,
    )
    rejection_reason = models.TextField(blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='candidate_documents_uploaded',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='candidate_documents_reviewed',
    )

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.candidate} – {self.document_name} ({self.document_type})"


# ---------------------------------------------------------------------------
# CandidateOnboardingNote — HR internal notes during review
# ---------------------------------------------------------------------------

class CandidateOnboardingNote(models.Model):
    candidate  = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='onboarding_notes')
    author     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    note       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Note on {self.candidate} by {self.author}"
