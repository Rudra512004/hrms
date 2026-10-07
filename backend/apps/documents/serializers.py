from rest_framework import serializers
from .models import DocumentCategory, DocumentTemplate, TemplateVersion, IssuedDocument

class DocumentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentCategory
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')

class TemplateVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateVersion
        fields = '__all__'
        read_only_fields = ('template', 'created_at', 'created_by')

class DocumentTemplateListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    active_version = serializers.SerializerMethodField()

    class Meta:
        model = DocumentTemplate
        fields = ('id', 'name', 'template_type', 'category', 'category_name', 'is_active', 'active_version', 'created_at', 'updated_at')

    def get_active_version(self, obj):
        latest = obj.versions.filter(is_published=True).first()
        return latest.version_number if latest else None

class DocumentTemplateDetailSerializer(serializers.ModelSerializer):
    versions = TemplateVersionSerializer(many=True, read_only=True)
    
    class Meta:
        model = DocumentTemplate
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at', 'created_by')

class IssuedDocumentSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    candidate_name = serializers.SerializerMethodField()
    
    class Meta:
        model = IssuedDocument
        fields = '__all__'
        read_only_fields = ('organization', 'issued_at', 'issued_by')

    def get_employee_name(self, obj):
        return obj.employee.user.get_full_name() if obj.employee and obj.employee.user else None

    def get_candidate_name(self, obj):
        return obj.candidate.get_full_name() if obj.candidate else None

class GenerateDocumentSerializer(serializers.Serializer):
    template_id = serializers.IntegerField()
    employee_id = serializers.IntegerField(required=False, allow_null=True)
    candidate_id = serializers.IntegerField(required=False, allow_null=True)
    # Extra variables to inject into the template rendering dynamically
    context_data = serializers.JSONField(required=False, default=dict)
