import os
from django.conf import settings
from rest_framework import serializers
from apps.data_import.models import ImportJob, ImportJobError
from apps.data_import.registry import TEMPLATE_REGISTRY

ALLOWED_IMPORT_EXTENSIONS = {'.csv', '.txt'}
BLOCKED_IMPORT_EXTENSIONS = {
    '.exe', '.dll', '.so', '.bin', '.sh', '.bat', '.cmd', '.ps1',
    '.py', '.js', '.ts', '.html', '.htm', '.php', '.phtml',
    '.jar', '.war', '.vbs', '.msi', '.com', '.scr',
}

class TemplateFieldSerializer(serializers.Serializer):
    csv_header = serializers.CharField()
    type = serializers.CharField()
    required = serializers.BooleanField()
    description = serializers.CharField(allow_blank=True)

class TemplateSerializer(serializers.Serializer):
    key = serializers.CharField()
    display_name = serializers.CharField()
    filename = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    version = serializers.CharField()
    headers = serializers.ListField(child=serializers.CharField())
    fields = TemplateFieldSerializer(many=True)

class ImportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportJob
        fields = [
            'id', 'template_key', 'status', 'original_filename', 
            'total_rows', 'valid_rows', 'created_count', 'updated_count', 
            'skipped_count', 'error_count', 'started_at', 'completed_at', 
            'created_at', 'preview_data'
        ]
        read_only_fields = fields

class ImportJobUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportJob
        fields = ['template_key', 'file']

    def validate_template_key(self, value):
        if value not in TEMPLATE_REGISTRY:
            raise serializers.ValidationError("Invalid template key.")
        return value

    def validate_file(self, file):
        # 1. Size check
        max_size = getattr(settings, 'MAX_IMPORT_FILE_SIZE', 10 * 1024 * 1024)
        if file.size > max_size:
            raise serializers.ValidationError(
                f"File size exceeds the maximum allowed limit of {max_size // (1024 * 1024)} MB."
            )

        # 2. Extension check
        ext = os.path.splitext(file.name)[-1].lower()
        if ext in BLOCKED_IMPORT_EXTENSIONS or ext not in ALLOWED_IMPORT_EXTENSIONS:
            raise serializers.ValidationError(
                f"File type '{ext}' is not allowed for CSV import. Please upload a .csv file."
            )

        return file

class ImportJobErrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportJobError
        fields = ['row_number', 'field', 'error_type', 'message', 'row_data']
