from django.contrib import admin
from .models import Candidate, CandidateDocument, CandidateOnboardingNote, IssuedLetter, LetterTemplate


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'organization', 'status', 'created_at')
    list_filter  = ('status', 'organization')
    search_fields = ('first_name', 'last_name', 'email')
    readonly_fields = ('employee', 'user', 'created_at', 'updated_at')


@admin.register(CandidateDocument)
class CandidateDocumentAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'document_type', 'document_name', 'status', 'uploaded_at')
    list_filter  = ('status', 'document_type')


@admin.register(LetterTemplate)
class LetterTemplateAdmin(admin.ModelAdmin):
    list_display = ('organization', 'letter_type', 'version', 'is_active', 'created_at')
    list_filter  = ('letter_type', 'is_active', 'organization')


@admin.register(IssuedLetter)
class IssuedLetterAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'letter_type', 'template_version', 'issued_by', 'issued_at')
    list_filter  = ('letter_type',)


@admin.register(CandidateOnboardingNote)
class CandidateOnboardingNoteAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'author', 'created_at')
