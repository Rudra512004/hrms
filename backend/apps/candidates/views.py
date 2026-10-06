"""
Candidate + Onboarding + Letter API views.

Two surface areas:
  1. HR/Admin: Full candidate management (requires candidate.* permissions).
  2. Candidate portal: Restricted self-service (identified via user.candidate FK).

Security invariants:
  - Candidate users cannot access any HR/employee/admin endpoints.
  - HR cannot access another org's candidates.
  - Document access is always candidate-scoped.
  - Conversion is atomic and idempotent.
"""

import mimetypes
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.http import FileResponse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import AuditService
from apps.authorization.permissions import require_permission
from apps.authorization.services import AuthorizationService
from apps.common.pagination import StandardResultsSetPagination
from apps.notifications.services import NotificationService

from .models import (
    Candidate, CandidateDocument, CandidateDocumentStatus,
    CandidateOnboardingNote, CandidateStatus, IssuedLetter,
    LetterTemplate, LetterType, CANDIDATE_TRANSITIONS,
)
from .serializers import (
    CandidateCreateSerializer, CandidateDocumentSerializer,
    CandidateDocumentUploadSerializer, CandidateListSerializer,
    CandidateOnboardingNoteSerializer, CandidateOnboardingProfileSerializer,
    CandidateSerializer, CandidateUpdateSerializer,
    IssuedLetterSerializer, LetterTemplateSerializer, LetterTemplateWriteSerializer,
)

User = get_user_model()


def _get_candidate_org(request):
    """Return the org context for the requesting HR user."""
    user = request.user
    if user.is_superuser:
        org_id = request.query_params.get('organization_id') or request.data.get('organization')
        if org_id:
            from apps.organization.models import Organization
            try:
                return Organization.objects.get(id=org_id)
            except Organization.DoesNotExist:
                return None
        return None
    emp = getattr(user, 'employee', None)
    return emp.organization if emp else None


# ---------------------------------------------------------------------------
# HR Candidate Management
# ---------------------------------------------------------------------------

class CandidateViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for HR/Admin. Permission-gated at every action.
    Superusers must pass ?organization_id= for queryset scoping.
    """
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return CandidateListSerializer
        if self.action == 'create':
            return CandidateCreateSerializer
        if self.action in ['update', 'partial_update']:
            return CandidateUpdateSerializer
        return CandidateSerializer

    def get_permissions(self):
        perms = [IsAuthenticated()]
        if self.action in ['list', 'retrieve']:
            perms.append(require_permission('candidate.view')())
        elif self.action == 'create':
            perms.append(require_permission('candidate.create')())
        elif self.action in ['update', 'partial_update']:
            perms.append(require_permission('candidate.update')())
        else:
            # action-level permissions checked inside the action
            pass
        return perms

    def get_queryset(self):
        user = self.request.user
        qs = Candidate.objects.select_related(
            'organization', 'applied_designation', 'created_by', 'user', 'employee'
        ).prefetch_related('documents', 'issued_letters')

        if user.is_superuser:
            org_id = self.request.query_params.get('organization_id')
            if org_id:
                qs = qs.filter(organization_id=org_id)
        elif hasattr(user, 'employee') and user.employee.organization_id:
            qs = qs.filter(organization=user.employee.organization)
        else:
            return Candidate.objects.none()

        # Filtering
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        search = self.request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            )
        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        from apps.organization.models import Organization
        user = self.request.user
        org = _get_candidate_org(self.request)
        if not org:
            if user.is_superuser:
                org_id = self.request.data.get('organization')
                if org_id:
                    try:
                        org = Organization.objects.get(id=org_id)
                    except Organization.DoesNotExist:
                        from rest_framework.exceptions import ValidationError
                        raise ValidationError({'organization': 'Organization not found.'})
            if not org:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'organization': 'Organization context is required.'})

        # Pass org to serializer validator
        serializer.context['organization'] = org
        # Re-run validate with org context
        serializer.is_valid(raise_exception=True)

        candidate = serializer.save(organization=org, created_by=user)
        AuditService.log(
            action='candidate_created',
            actor=user,
            target_type='candidate',
            target_id=candidate.id,
            metadata={'name': candidate.get_full_name(), 'email': candidate.email},
            request=self.request,
            organization=org,
        )

    @action(detail=True, methods=['post'], url_path='issue-offer')
    def issue_offer(self, request, pk=None):
        """
        HR issues the offer letter and provisions a candidate onboarding account.

        Steps:
        1. Validate candidate is in CREATED status.
        2. Find/render the active Offer Letter template for this org.
        3. Create candidate User account (invited state).
        4. Generate activation link for the candidate onboarding portal.
        5. Send email via NotificationService.
        6. Save IssuedLetter snapshot.
        7. Transition candidate → OFFERED.
        """
        if not AuthorizationService.has_permission(request.user, 'candidate.onboard'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        candidate = self.get_object()

        if candidate.status != CandidateStatus.CREATED:
            return Response(
                {'detail': f"Cannot issue offer from status '{candidate.status}'. Expected 'created'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch active offer template
        template = LetterTemplate.objects.filter(
            organization=candidate.organization,
            letter_type=LetterType.OFFER,
            is_active=True,
        ).order_by('-version').first()

        if not template:
            return Response(
                {'detail': 'No active Offer Letter template found for this organization. Please create one first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Provision candidate user account if not already existing
            if not candidate.user_id:
                if User.objects.filter(email=candidate.email).exists():
                    return Response(
                        {'detail': f"A user account already exists for email '{candidate.email}'."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                candidate_user = User.objects.create_user(
                    email=candidate.email,
                    first_name=candidate.first_name,
                    last_name=candidate.last_name,
                )
                # Mark as invited (default in UserManager)
                candidate.user = candidate_user

            # Render template with available context
            context = {
                'candidate_name': candidate.get_full_name(),
                'designation': candidate.applied_designation.name if candidate.applied_designation else '',
                'joining_date': str(candidate.proposed_joining_date or ''),
                'organization': candidate.organization.name,
            }
            rendered_body = template.body
            for key, value in context.items():
                rendered_body = rendered_body.replace(f'{{{{{key}}}}}', value)

            # Snapshot the letter
            issued_letter = IssuedLetter.objects.create(
                candidate=candidate,
                letter_type=LetterType.OFFER,
                template=template,
                template_version=template.version,
                subject_snapshot=template.subject,
                body_snapshot=rendered_body,
                issued_by=request.user,
            )

            # Transition candidate status
            candidate.transition_to(CandidateStatus.OFFERED)
            candidate.save()

        # Generate activation link for onboarding portal
        uid   = urlsafe_base64_encode(force_bytes(candidate.user.pk))
        token = default_token_generator.make_token(candidate.user)
        frontend_url = __import__('django.conf', fromlist=['settings']).settings.FRONTEND_URL
        onboarding_link = f"{frontend_url}/onboarding/activate?uid={uid}&token={token}"

        email_sent = NotificationService.send_candidate_offer_email(
            candidate_email=candidate.email,
            candidate_name=candidate.get_full_name(),
            organization_name=candidate.organization.name,
            offer_letter_body=rendered_body,
            onboarding_link=onboarding_link,
        )

        AuditService.log(
            action='candidate_offer_issued',
            actor=request.user,
            target_type='candidate',
            target_id=candidate.id,
            metadata={'template_version': template.version, 'email_sent': email_sent},
            request=request,
            organization=candidate.organization,
        )

        return Response({
            'detail': 'Offer letter issued successfully.',
            'candidate': CandidateSerializer(candidate, context={'request': request}).data,
            'issued_letter': IssuedLetterSerializer(issued_letter).data,
            'onboarding_email_status': 'sent' if email_sent else 'failed',
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='start-onboarding')
    def start_onboarding(self, request, pk=None):
        """HR manually transitions candidate from OFFERED → ONBOARDING (if needed)."""
        if not AuthorizationService.has_permission(request.user, 'candidate.onboard'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        candidate = self.get_object()
        try:
            candidate.transition_to(CandidateStatus.ONBOARDING)
            candidate.save()
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(CandidateSerializer(candidate, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='verify-documents')
    def verify_documents(self, request, pk=None):
        """HR moves candidate to VERIFYING state."""
        if not AuthorizationService.has_permission(request.user, 'candidate.verify'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        candidate = self.get_object()
        try:
            candidate.transition_to(CandidateStatus.VERIFYING)
            candidate.save()
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        AuditService.log(
            action='candidate_verification_started',
            actor=request.user, target_type='candidate', target_id=candidate.id,
            request=request, organization=candidate.organization,
        )
        return Response(CandidateSerializer(candidate, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        """HR approves the candidate for conversion."""
        if not AuthorizationService.has_permission(request.user, 'candidate.verify'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        candidate = self.get_object()
        try:
            candidate.transition_to(CandidateStatus.APPROVED)
            candidate.save()
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        AuditService.log(
            action='candidate_approved',
            actor=request.user, target_type='candidate', target_id=candidate.id,
            request=request, organization=candidate.organization,
        )
        return Response(CandidateSerializer(candidate, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        """HR rejects the candidate (terminal state)."""
        if not AuthorizationService.has_permission(request.user, 'candidate.manage_status'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        candidate = self.get_object()
        reason = request.data.get('reason', '')
        try:
            candidate.transition_to(CandidateStatus.REJECTED)
            if reason:
                candidate.notes = (candidate.notes + f"\n\nRejection reason: {reason}").strip()
            candidate.save()
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        AuditService.log(
            action='candidate_rejected',
            actor=request.user, target_type='candidate', target_id=candidate.id,
            metadata={'reason': reason},
            request=request, organization=candidate.organization,
        )
        return Response(CandidateSerializer(candidate, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='convert-to-employee')
    def convert_to_employee(self, request, pk=None):
        """
        Atomically converts an approved Candidate to an Employee.

        Idempotency: if candidate.employee is already set → return 409.
        Uses the existing ProvisionEmployee pattern but bypasses the HTTP layer.
        """
        if not AuthorizationService.has_permission(request.user, 'candidate.convert'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        candidate = self.get_object()

        # Idempotency guard
        if candidate.employee_id:
            return Response(
                {'detail': 'Candidate has already been converted to an employee.', 'employee_id': candidate.employee_id},
                status=status.HTTP_409_CONFLICT,
            )

        if candidate.status != CandidateStatus.APPROVED:
            return Response(
                {'detail': f"Candidate must be in 'approved' state to convert. Current: '{candidate.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not candidate.user_id:
            return Response(
                {'detail': 'Candidate does not have an onboarding user account. Issue the offer first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.employees.models import Employee, EmploymentStatus
        from apps.employees.utils import generate_next_employee_code

        with transaction.atomic():
            # Lock candidate row to prevent duplicate conversion
            candidate = Candidate.objects.select_for_update().get(pk=candidate.pk)

            if candidate.employee_id:
                return Response(
                    {'detail': 'Candidate has already been converted (concurrent request).'},
                    status=status.HTTP_409_CONFLICT,
                )

            employee_code = generate_next_employee_code()

            # Activate the candidate user account
            candidate.user.status = 'active'
            candidate.user.save(update_fields=['status'])

            # Create employee record, copying candidate profile
            employee = Employee.objects.create(
                user=candidate.user,
                organization=candidate.organization,
                branch=None,         # HR finalizes later
                department=None,
                team=None,
                designation=candidate.applied_designation,
                employee_code=employee_code,
                personal_email=candidate.email,
                phone_number=candidate.phone_number,
                address=candidate.address,
                address_line1=candidate.address,
                employment_status=EmploymentStatus.ONBOARDING,
                joining_date=candidate.proposed_joining_date,
            )

            # Traceability link
            candidate.employee = employee
            candidate.transition_to(CandidateStatus.CONVERTED)
            candidate.save()

        # Issue Appointment Letter
        appt_template = LetterTemplate.objects.filter(
            organization=candidate.organization,
            letter_type=LetterType.APPOINTMENT,
            is_active=True,
        ).order_by('-version').first()

        if appt_template:
            context = {
                'candidate_name': candidate.get_full_name(),
                'designation': candidate.applied_designation.name if candidate.applied_designation else '',
                'joining_date': str(candidate.proposed_joining_date or ''),
                'organization': candidate.organization.name,
                'employee_code': employee.employee_code,
            }
            rendered_body = appt_template.body
            for key, value in context.items():
                rendered_body = rendered_body.replace(f'{{{{{key}}}}}', value)

            IssuedLetter.objects.create(
                candidate=candidate,
                letter_type=LetterType.APPOINTMENT,
                template=appt_template,
                template_version=appt_template.version,
                subject_snapshot=appt_template.subject,
                body_snapshot=rendered_body,
                issued_by=request.user,
            )

            AuditService.log(
                action='appointment_letter_issued',
                actor=request.user, target_type='candidate', target_id=candidate.id,
                metadata={'employee_code': employee.employee_code},
                request=request, organization=candidate.organization,
            )

        AuditService.log(
            action='candidate_converted_to_employee',
            actor=request.user,
            target_type='candidate',
            target_id=candidate.id,
            metadata={
                'employee_id': employee.id,
                'employee_code': employee.employee_code,
            },
            request=request,
            organization=candidate.organization,
        )

        return Response({
            'detail': 'Candidate successfully converted to employee.',
            'candidate': CandidateSerializer(candidate, context={'request': request}).data,
            'employee_id': employee.id,
            'employee_code': employee.employee_code,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='add-note')
    def add_note(self, request, pk=None):
        """HR adds an internal onboarding note."""
        if not AuthorizationService.has_permission(request.user, 'candidate.view'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        candidate = self.get_object()
        serializer = CandidateOnboardingNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.save(candidate=candidate, author=request.user)
        return Response(CandidateOnboardingNoteSerializer(note).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Candidate Document Management (HR side)
# ---------------------------------------------------------------------------

class HRCandidateDocumentView(APIView):
    """HR can list, verify, or reject a candidate's documents."""
    permission_classes = [IsAuthenticated]

    def _get_candidate(self, candidate_id, user):
        try:
            candidate = Candidate.objects.get(pk=candidate_id)
        except Candidate.DoesNotExist:
            return None, Response({'detail': 'Candidate not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not user.is_superuser:
            emp = getattr(user, 'employee', None)
            if not emp or emp.organization_id != candidate.organization_id:
                return None, Response({'detail': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)
        return candidate, None

    def get(self, request, candidate_id):
        if not AuthorizationService.has_permission(request.user, 'candidate.view'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        candidate, err = self._get_candidate(candidate_id, request.user)
        if err:
            return err
        docs = candidate.documents.all()
        return Response(CandidateDocumentSerializer(docs, many=True).data)


class HRCandidateDocumentVerifyView(APIView):
    """HR verifies or rejects a specific candidate document."""
    permission_classes = [IsAuthenticated]

    def post(self, request, candidate_id, document_id):
        if not AuthorizationService.has_permission(request.user, 'candidate.verify'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            doc = CandidateDocument.objects.select_related('candidate__organization').get(
                pk=document_id, candidate_id=candidate_id
            )
        except CandidateDocument.DoesNotExist:
            return Response({'detail': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Tenant check
        if not request.user.is_superuser:
            emp = getattr(request.user, 'employee', None)
            if not emp or emp.organization_id != doc.candidate.organization_id:
                return Response({'detail': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

        decision = request.data.get('decision')  # 'verified' or 'rejected'
        if decision not in ('verified', 'rejected'):
            return Response({'detail': "'decision' must be 'verified' or 'rejected'."}, status=status.HTTP_400_BAD_REQUEST)

        doc.status = CandidateDocumentStatus.VERIFIED if decision == 'verified' else CandidateDocumentStatus.REJECTED
        doc.rejection_reason = request.data.get('rejection_reason', '') if decision == 'rejected' else ''
        doc.reviewed_by = request.user
        doc.reviewed_at = timezone.now()
        doc.save()

        AuditService.log(
            action=f'candidate_document_{decision}',
            actor=request.user,
            target_type='candidate_document',
            target_id=doc.id,
            metadata={'document_name': doc.document_name, 'candidate_id': candidate_id},
            request=request,
            organization=doc.candidate.organization,
        )
        return Response(CandidateDocumentSerializer(doc).data)


# ---------------------------------------------------------------------------
# Letter Template Management (HR)
# ---------------------------------------------------------------------------

class LetterTemplateViewSet(viewsets.ModelViewSet):
    """HR manages letter templates (Offer, Appointment)."""
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return LetterTemplateWriteSerializer
        return LetterTemplateSerializer

    def get_permissions(self):
        perms = [IsAuthenticated()]
        if self.action in ['list', 'retrieve']:
            perms.append(require_permission('letter.view')())
        else:
            perms.append(require_permission('letter.issue')())
        return perms

    def get_queryset(self):
        user = self.request.user
        qs = LetterTemplate.objects.select_related('organization', 'created_by')
        if user.is_superuser:
            org_id = self.request.query_params.get('organization_id')
            if org_id:
                qs = qs.filter(organization_id=org_id)
        elif hasattr(user, 'employee') and user.employee.organization_id:
            qs = qs.filter(organization=user.employee.organization)
        else:
            return LetterTemplate.objects.none()

        lt = self.request.query_params.get('letter_type')
        if lt:
            qs = qs.filter(letter_type=lt)
        return qs.order_by('-version')

    def perform_create(self, serializer):
        from apps.organization.models import Organization
        from rest_framework.exceptions import ValidationError

        user = self.request.user
        org = _get_candidate_org(self.request)
        if not org:
            if user.is_superuser:
                org_id = self.request.data.get('organization')
                if org_id:
                    try:
                        org = Organization.objects.get(id=org_id)
                    except Organization.DoesNotExist:
                        raise ValidationError({'organization': 'Organization not found.'})
            if not org:
                raise ValidationError({'organization': 'Organization context is required.'})

        letter_type = serializer.validated_data['letter_type']

        # Auto-increment version
        last_version = LetterTemplate.objects.filter(
            organization=org, letter_type=letter_type
        ).order_by('-version').values_list('version', flat=True).first()
        new_version = (last_version or 0) + 1

        # Deactivate previous active template for this type
        LetterTemplate.objects.filter(
            organization=org, letter_type=letter_type, is_active=True
        ).update(is_active=False)

        template = serializer.save(
            organization=org,
            version=new_version,
            created_by=user,
            is_active=True,
        )

        AuditService.log(
            action='letter_template_created',
            actor=user, target_type='letter_template', target_id=template.id,
            metadata={'letter_type': letter_type, 'version': new_version},
            request=self.request, organization=org,
        )


# ---------------------------------------------------------------------------
# Candidate Portal (Restricted self-service)
# ---------------------------------------------------------------------------

class IsCandidateUser(IsAuthenticated):
    """Grants access only to users linked to a Candidate record."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, 'candidate') and request.user.candidate is not None


class CandidatePortalMeView(APIView):
    """
    Candidate's own profile view.
    Only the candidate themselves can access this — identified by user.candidate FK.
    """
    permission_classes = [IsCandidateUser]

    def get(self, request):
        candidate = request.user.candidate
        return Response(CandidateOnboardingProfileSerializer(candidate).data)

    def patch(self, request):
        candidate = request.user.candidate
        if candidate.status not in (CandidateStatus.ONBOARDING, CandidateStatus.OFFERED):
            return Response(
                {'detail': 'Profile can only be updated during the onboarding stage.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = CandidateOnboardingProfileSerializer(candidate, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CandidatePortalDocumentsView(APIView):
    """
    Candidate uploads their own documents during onboarding.
    Only accessible to the specific candidate (not HR, not other candidates).
    """
    permission_classes = [IsCandidateUser]

    def get(self, request):
        docs = request.user.candidate.documents.all()
        return Response(CandidateDocumentSerializer(docs, many=True).data)

    def post(self, request):
        candidate = request.user.candidate
        if candidate.status not in (CandidateStatus.ONBOARDING, CandidateStatus.OFFERED, CandidateStatus.SUBMITTED):
            return Response(
                {'detail': 'Documents can only be uploaded during the onboarding stage.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = CandidateDocumentUploadSerializer(
            data=request.data,
            context={'candidate': candidate, 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        doc = serializer.save()
        AuditService.log(
            action='candidate_document_uploaded',
            actor=request.user, target_type='candidate_document', target_id=doc.id,
            metadata={'document_name': doc.document_name, 'candidate_id': candidate.id},
            request=request, organization=candidate.organization,
        )
        return Response(CandidateDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


class CandidatePortalDocumentDetailView(APIView):
    """Candidate can delete their own pending documents."""
    permission_classes = [IsCandidateUser]

    def delete(self, request, document_id):
        candidate = request.user.candidate
        try:
            doc = CandidateDocument.objects.get(pk=document_id, candidate=candidate)
        except CandidateDocument.DoesNotExist:
            return Response({'detail': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)

        if doc.status != CandidateDocumentStatus.PENDING:
            return Response(
                {'detail': 'Only pending documents can be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        doc.file.delete(save=False)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CandidatePortalSubmitView(APIView):
    """Candidate submits their onboarding for HR review."""
    permission_classes = [IsCandidateUser]

    def post(self, request):
        candidate = request.user.candidate
        try:
            candidate.transition_to(CandidateStatus.SUBMITTED)
            candidate.save()
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        AuditService.log(
            action='candidate_onboarding_submitted',
            actor=request.user, target_type='candidate', target_id=candidate.id,
            request=request, organization=candidate.organization,
        )
        return Response({
            'detail': 'Onboarding submitted successfully. HR will review your submission.',
            'status': candidate.status,
        })


class CandidatePortalLettersView(APIView):
    """Candidate can view letters issued to them (Offer, Appointment)."""
    permission_classes = [IsCandidateUser]

    def get(self, request):
        letters = request.user.candidate.issued_letters.all()
        return Response(IssuedLetterSerializer(letters, many=True).data)


class CandidatePortalActivateView(APIView):
    """
    Public endpoint — activates candidate account from onboarding email link.
    Uses same token mechanism as employee activation.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        from django.utils.http import urlsafe_base64_decode
        from django.utils.encoding import force_str

        uid   = request.data.get('uid', '')
        token = request.data.get('token', '')
        password = request.data.get('password', '')

        if not all([uid, token, password]):
            return Response({'detail': 'uid, token, and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user_pk = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_pk)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'Invalid activation link.'}, status=status.HTTP_400_BAD_REQUEST)

        # Must be a candidate user
        if not hasattr(user, 'candidate'):
            return Response({'detail': 'Invalid activation link.'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'detail': 'Activation link is invalid or has expired.'}, status=status.HTTP_400_BAD_REQUEST)

        if len(password) < 8:
            return Response({'detail': 'Password must be at least 8 characters.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(password)
        user.status = 'active'
        user.save()

        # Transition to ONBOARDING if still OFFERED
        candidate = user.candidate
        if candidate.status == CandidateStatus.OFFERED:
            candidate.status = CandidateStatus.ONBOARDING
            candidate.save(update_fields=['status'])

        AuditService.log(
            action='candidate_account_activated',
            actor=user, target_type='candidate', target_id=candidate.id,
            request=request, organization=candidate.organization,
        )
        return Response({'detail': 'Account activated successfully. You can now log in to the onboarding portal.'})
