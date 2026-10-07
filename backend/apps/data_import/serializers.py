from rest_framework import serializers
from apps.data_import.models import ImportJob, ImportJobError
from apps.data_import.registry import TEMPLATE_REGISTRY

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

class ImportJobErrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportJobError
        fields = ['row_number', 'field', 'error_type', 'message', 'row_data']
