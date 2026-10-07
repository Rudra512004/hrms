import io
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.template import Template, Context
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from .models import DocumentCategory, DocumentTemplate, TemplateVersion, IssuedDocument, TemplateType
from .serializers import (
    DocumentCategorySerializer, DocumentTemplateListSerializer,
    DocumentTemplateDetailSerializer, TemplateVersionSerializer,
    IssuedDocumentSerializer, GenerateDocumentSerializer
)
from apps.authorization.services import AuthorizationService
from apps.employees.models import Employee
from apps.candidates.models import Candidate
from apps.authorization.permissions import require_permission
from xhtml2pdf import pisa

class DocumentCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentCategorySerializer
    permission_classes = [require_permission('document.manage_templates')]

    def get_queryset(self):
        org = AuthorizationService.get_primary_organization(self.request.user)
        if not org:
            return DocumentCategory.objects.none()
        return DocumentCategory.objects.filter(organization=org)

    def perform_create(self, serializer):
        org = AuthorizationService.get_primary_organization(self.request.user)
        serializer.save(organization=org)

class DocumentTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [require_permission('document.manage_templates')]

    def get_serializer_class(self):
        if self.action in ['list']:
            return DocumentTemplateListSerializer
        return DocumentTemplateDetailSerializer

    def get_queryset(self):
        org = AuthorizationService.get_primary_organization(self.request.user)
        if not org:
            return DocumentTemplate.objects.none()
        return DocumentTemplate.objects.filter(organization=org)

    def perform_create(self, serializer):
        org = AuthorizationService.get_primary_organization(self.request.user)
        serializer.save(organization=org, created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def add_version(self, request, pk=None):
        template = self.get_object()
        latest = template.versions.first()
        new_version_number = (latest.version_number + 1) if latest else 1
        
        serializer = TemplateVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        is_published = serializer.validated_data.get('is_published', False)
        if is_published:
            template.versions.all().update(is_published=False)
        serializer.save(template=template, version_number=new_version_number, created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def activate_version(self, request, pk=None):
        template = self.get_object()
        version_id = request.data.get('version_id')
        if not version_id:
            return Response({'detail': 'version_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        version = get_object_or_404(template.versions, id=version_id)
        template.versions.all().update(is_published=False)
        version.is_published = True
        version.save()
        return Response(TemplateVersionSerializer(version).data)

    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        template = self.get_object()
        version_id = request.data.get('version_id')
        context_data = request.data.get('context_data', {})

        if version_id:
            version = get_object_or_404(template.versions, id=version_id)
        else:
            version = template.versions.filter(is_published=True).first()
            if not version:
                return Response({'detail': 'No active version available.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            django_template = Template(version.body)
            rendered_html = django_template.render(Context(context_data))
        except Exception as e:
            return Response({'detail': f'Template rendering error: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'html': rendered_html})

from rest_framework.permissions import IsAuthenticated

class IssuedDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = IssuedDocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = AuthorizationService.get_primary_organization(self.request.user)
        if not org:
            return IssuedDocument.objects.none()
            
        qs = IssuedDocument.objects.filter(organization=org)
        
        # Self-service filtering
        if not AuthorizationService.has_permission(self.request.user, 'document.view_all'):
            if hasattr(self.request.user, 'employee'):
                qs = qs.filter(employee=self.request.user.employee)
            elif hasattr(self.request.user, 'candidate'):
                qs = qs.filter(candidate=self.request.user.candidate)
            else:
                qs = IssuedDocument.objects.none()
                
        return qs

    @action(detail=False, methods=['post'])
    def generate(self, request):
        if not AuthorizationService.has_permission(request.user, 'document.issue'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = GenerateDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        org = AuthorizationService.get_primary_organization(request.user)
        
        template = get_object_or_404(DocumentTemplate, id=serializer.validated_data['template_id'], organization=org)
        version = template.versions.filter(is_published=True).first()
        if not version:
            return Response({'detail': 'Template has no published version.'}, status=status.HTTP_400_BAD_REQUEST)

        emp_id = serializer.validated_data.get('employee_id')
        cand_id = serializer.validated_data.get('candidate_id')
        
        employee = None
        candidate = None
        
        if emp_id:
            employee = get_object_or_404(Employee, id=emp_id, organization=org)
        elif cand_id:
            candidate = get_object_or_404(Candidate, id=cand_id, organization=org)
        else:
            return Response({'detail': 'Either employee_id or candidate_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        context_data = serializer.validated_data.get('context_data', {})
        if employee:
            context_data['employee'] = {
                'first_name': employee.user.first_name if (employee.user) else '',
                'last_name': employee.user.last_name if (employee.user) else '',
                'email': employee.user.email if (employee.user) else '',
                'code': employee.employee_code,
            }
            if employee.designation:
                context_data['employee']['designation'] = employee.designation.name
        elif candidate:
            context_data['candidate'] = {
                'first_name': candidate.first_name,
                'last_name': candidate.last_name,
                'email': candidate.email,
                'full_name': candidate.get_full_name(),
            }
            if candidate.applied_designation:
                context_data['candidate']['designation'] = candidate.applied_designation.name

        try:
            django_template = Template(version.body)
            rendered_html = django_template.render(Context(context_data))
        except Exception as e:
            return Response({'detail': f'Template rendering error: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        doc_title_name = ''
        if employee:
            doc_title_name = employee.user.get_full_name() if (employee.user) else employee.employee_code
        elif candidate:
            doc_title_name = candidate.get_full_name()

        doc = IssuedDocument(
            organization=org,
            employee=employee,
            candidate=candidate,
            template_version=version,
            document_type=template.template_type,
            title=f"{template.name} - {doc_title_name}".strip(" -"),
            issued_by=request.user
        )

        if template.template_type == TemplateType.PDF:
            pdf_file = io.BytesIO()
            pisa_status = pisa.CreatePDF(io.StringIO(rendered_html), dest=pdf_file)
            if pisa_status.err:
                return Response({'detail': 'PDF Generation failed.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            file_name = f"{template.name.replace(' ', '_')}_{employee.id if employee else candidate.id}.pdf"
            doc.file_attachment.save(file_name, ContentFile(pdf_file.getvalue()), save=False)
        else:
            doc.body_snapshot = rendered_html

        doc.save()
        return Response(IssuedDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)
