"""
Serializers for the Candidate + Onboarding + Letter workflow.
"""

import os
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Candidate, CandidateStatus, CandidateDocument,
    CandidateDocumentStatus, IssuedLetter, LetterTemplate, LetterType,
    CandidateOnboardingNote, ALLOWED_CANDIDATE_DOC_EXTENSIONS, MAX_CANDIDATE_DOC_SIZE,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# LetterTemplate
# ---------------------------------------------------------------------------

class LetterTemplateSerializer(serializers.ModelSerializer):
    letter_type_display = serializers.CharField(source='get_letter_type_display', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)

    class Meta:
        model = LetterTemplate
        fields = (
            'id', 'organization', 'letter_type', 'letter_type_display',
            'version', 'subject', 'body', 'is_active',
            'created_by', 'created_by_email', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'version', 'created_by', 'created_by_email', 'created_at', 'updated_at')


class LetterTemplateWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LetterTemplate
        fields = ('id', 'letter_type', 'subject', 'body', 'is_active')
        read_only_fields = ('id',)


# ---------------------------------------------------------------------------
# IssuedLetter
# ---------------------------------------------------------------------------

class IssuedLetterSerializer(serializers.ModelSerializer):
    letter_type_display = serializers.CharField(source='get_letter_type_display', read_only=True)
    issued_by_email     = serializers.CharField(source='issued_by.email', read_only=True)
    candidate_name      = serializers.CharField(source='candidate.get_full_name', read_only=True)

    class Meta:
        model = IssuedLetter
        fields = (
            'id', 'candidate', 'candidate_name',
            'letter_type', 'letter_type_display',
            'template', 'template_version',
            'subject_snapshot', 'body_snapshot',
            'issued_by', 'issued_by_email', 'issued_at',
        )
        read_only_fields = fields


# ---------------------------------------------------------------------------
# CandidateDocument
# ---------------------------------------------------------------------------

class CandidateDocumentSerializer(serializers.ModelSerializer):
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    uploaded_by_email = serializers.CharField(source='uploaded_by.email', read_only=True)
    reviewed_by_email = serializers.CharField(source='reviewed_by.email', read_only=True)

    class Meta:
        model = CandidateDocument
        fields = (
            'id', 'candidate', 'document_type', 'document_type_display',
            'document_name', 'file_size', 'mime_type', 'description',
            'status', 'status_display', 'rejection_reason',
            'uploaded_at', 'uploaded_by', 'uploaded_by_email',
            'reviewed_at', 'reviewed_by', 'reviewed_by_email',
        )
        read_only_fields = fields


class CandidateDocumentUploadSerializer(serializers.Serializer):
    """Write serializer for document upload during onboarding."""
    document_type = serializers.ChoiceField(
        choices=[
            ('identity', 'Identity Proof'),
            ('address', 'Address Proof'),
            ('education', 'Education Certificate'),
            ('employment', 'Previous Employment Proof'),
            ('other', 'Other'),
        ],
        default='other',
    )
    document_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    description   = serializers.CharField(required=False, allow_blank=True, default='')
    file          = serializers.FileField()

    def validate_file(self, file):
        if file.size > MAX_CANDIDATE_DOC_SIZE:
            raise serializers.ValidationError(
                f"File size {file.size} bytes exceeds the 5 MB maximum."
            )
        ext = os.path.splitext(file.name)[-1].lower()
        if ext not in ALLOWED_CANDIDATE_DOC_EXTENSIONS:
            raise serializers.ValidationError(
                f"File type '{ext}' is not allowed. "
                f"Accepted: {', '.join(sorted(ALLOWED_CANDIDATE_DOC_EXTENSIONS))}."
            )
        return file

    def validate_document_name(self, value):
        if value:
            value = value.replace('..', '').replace('/', '').replace('\\', '').strip()
        return value

    def create(self, validated_data):
        candidate = self.context['candidate']
        request   = self.context.get('request')
        file      = validated_data['file']
        doc_name  = validated_data.get('document_name') or os.path.basename(file.name)
        doc_name  = doc_name.replace('..', '').replace('/', '').replace('\\', '').strip()

        return CandidateDocument.objects.create(
            candidate=candidate,
            document_type=validated_data.get('document_type', 'other'),
            document_name=doc_name,
            file=file,
            file_size=file.size,
            mime_type=getattr(file, 'content_type', ''),
            description=validated_data.get('description', ''),
            uploaded_by=request.user if request else None,
        )


# ---------------------------------------------------------------------------
# CandidateOnboardingNote
# ---------------------------------------------------------------------------

class CandidateOnboardingNoteSerializer(serializers.ModelSerializer):
    author_email = serializers.CharField(source='author.email', read_only=True)

    class Meta:
        model = CandidateOnboardingNote
        fields = ('id', 'candidate', 'author', 'author_email', 'note', 'created_at')
        read_only_fields = ('id', 'candidate', 'author', 'author_email', 'created_at')


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------

class CandidateSerializer(serializers.ModelSerializer):
    """Full read representation for HR."""
    status_display      = serializers.CharField(source='get_status_display', read_only=True)
    designation_name    = serializers.CharField(source='applied_designation.name', read_only=True)
    organization_name   = serializers.CharField(source='organization.name', read_only=True)
    created_by_email    = serializers.CharField(source='created_by.email', read_only=True)
    employee_id_display = serializers.SerializerMethodField()
    document_count      = serializers.SerializerMethodField()
    documents           = CandidateDocumentSerializer(many=True, read_only=True)
    issued_letters      = IssuedLetterSerializer(many=True, read_only=True)

    class Meta:
        model = Candidate
        fields = (
            'id', 'organization', 'organization_name',
            'first_name', 'last_name', 'email', 'phone_number', 'address',
            'applied_designation', 'designation_name',
            'proposed_joining_date', 'notes',
            'status', 'status_display',
            'user', 'employee', 'employee_id_display',
            'created_by', 'created_by_email',
            'document_count', 'documents', 'issued_letters',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'organization', 'organization_name', 'status', 'status_display',
            'user', 'employee', 'employee_id_display',
            'created_by', 'created_by_email',
            'document_count', 'documents', 'issued_letters',
            'created_at', 'updated_at',
        )

    def get_employee_id_display(self, obj):
        if obj.employee_id:
            return obj.employee.employee_code
        return None

    def get_document_count(self, obj):
        return obj.documents.count()


class CandidateCreateSerializer(serializers.ModelSerializer):
    """Write serializer for HR creating a new candidate."""
    class Meta:
        model = Candidate
        fields = (
            'first_name', 'last_name', 'email', 'phone_number', 'address',
            'applied_designation', 'proposed_joining_date', 'notes',
        )

    def validate_email(self, value):
        value = value.strip().lower()
        org = self.context.get('organization')
        if org and Candidate.objects.filter(email__iexact=value, organization=org).exclude(
            status__in=[CandidateStatus.REJECTED, CandidateStatus.CONVERTED]
        ).exists():
            raise serializers.ValidationError(
                "An active candidate with this email already exists in this organization."
            )
        return value


class CandidateUpdateSerializer(serializers.ModelSerializer):
    """Write serializer for HR updating candidate basic info (before offer issued)."""
    class Meta:
        model = Candidate
        fields = (
            'first_name', 'last_name', 'phone_number', 'address',
            'applied_designation', 'proposed_joining_date', 'notes',
        )


class CandidateOnboardingProfileSerializer(serializers.ModelSerializer):
    """
    Limited serializer for candidate self-service.
    Candidate can update their own contact / personal details,
    but cannot modify email, status, organization, or notes.
    """
    class Meta:
        model = Candidate
        fields = (
            'id', 'first_name', 'last_name', 'email', 'phone_number', 'address',
            'applied_designation', 'proposed_joining_date',
            'status', 'organization',
        )
        read_only_fields = ('id', 'email', 'status', 'organization', 'applied_designation', 'proposed_joining_date')


class CandidateListSerializer(serializers.ModelSerializer):
    """Compact list serializer for HR candidate list."""
    status_display   = serializers.CharField(source='get_status_display', read_only=True)
    designation_name = serializers.CharField(source='applied_designation.name', read_only=True)
    document_count   = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = (
            'id', 'first_name', 'last_name', 'email', 'phone_number',
            'applied_designation', 'designation_name',
            'proposed_joining_date', 'status', 'status_display',
            'document_count', 'created_at',
        )

    def get_document_count(self, obj):
        return obj.documents.count()
