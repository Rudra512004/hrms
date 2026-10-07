import csv
from django.http import HttpResponse
from rest_framework import viewsets, views, status, parsers
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.authorization.permissions import require_permission
from apps.authorization.services import AuthorizationService
from apps.data_import.models import ImportJob, ImportJobError
from apps.data_import.registry import TEMPLATE_REGISTRY, generate_csv_content
from apps.data_import.serializers import (
    TemplateSerializer, ImportJobSerializer, 
    ImportJobUploadSerializer, ImportJobErrorSerializer
)
from apps.data_import.engine import ImportEngine
from apps.data_import.exceptions import ImportValidationError

class TemplateViewSet(viewsets.ViewSet):
    """
    Read-only viewset for discovering and downloading CSV templates.
    """
    permission_classes = [IsAuthenticated, require_permission('data_import.view')]

    def list(self, request):
        templates = list(TEMPLATE_REGISTRY.values())
        serializer = TemplateSerializer(templates, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        template = TEMPLATE_REGISTRY.get(pk)
        if not template:
            return Response({'error': 'Template not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = TemplateSerializer(template)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        template = TEMPLATE_REGISTRY.get(pk)
        if not template:
            return Response({'error': 'Template not found'}, status=status.HTTP_404_NOT_FOUND)
        
        content = generate_csv_content(pk)
        response = HttpResponse(content, content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="{template["filename"]}"'
        return response


class ImportJobViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing the import lifecycle (Upload -> Preview -> Execute).
    """
    serializer_class = ImportJobSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_permissions(self):
        if self.action in ['execute', 'create']:
            return [IsAuthenticated(), require_permission('data_import.execute')()]
        return [IsAuthenticated(), require_permission('data_import.view')()]

    def get_queryset(self):
        tenant = AuthorizationService.get_primary_organization(self.request.user)
        if not tenant:
            return ImportJob.objects.none()
        return ImportJob.objects.filter(organization=tenant).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = ImportJobUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        file_obj = request.data['file']
        
        tenant = AuthorizationService.get_primary_organization(request.user)
        if not tenant:
            return Response({'error': 'Organization context is missing'}, status=status.HTTP_400_BAD_REQUEST)

        job = ImportJob.objects.create(
            organization=tenant,
            created_by=request.user,
            template_key=serializer.validated_data['template_key'],
            file=file_obj,
            original_filename=file_obj.name,
            status='pending'
        )
        
        return Response(ImportJobSerializer(job).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """Phase 1: Validates the file structure and generates preview data."""
        job = self.get_object()
        if job.status != 'pending':
            return Response({'error': f'Job is in {job.status} state, not pending.'}, status=status.HTTP_400_BAD_REQUEST)
            
        engine = ImportEngine(job)
        try:
            engine.validate_and_preview()
            job.refresh_from_db()
            return Response(ImportJobSerializer(job).data)
        except ImportValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': 'An internal error occurred during validation.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Phase 2: Executes the import job, committing valid rows to the database."""
        job = self.get_object()
        if job.status != 'validated':
            return Response({'error': f'Job must be validated before execution.'}, status=status.HTTP_400_BAD_REQUEST)
            
        engine = ImportEngine(job)
        try:
            engine.execute()
            job.refresh_from_db()
            return Response(ImportJobSerializer(job).data)
        except Exception as e:
            return Response({'error': 'An internal error occurred during execution.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def errors(self, request, pk=None):
        job = self.get_object()
        errors = job.errors.all()
        serializer = ImportJobErrorSerializer(errors, many=True)
        return Response(serializer.data)
