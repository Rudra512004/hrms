from rest_framework import serializers
from .models import Notification, Announcement, OrganizationEmailSettings, EmailTemplate, EmailAutomationRule, EmailDelivery

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id',
            'notification_type',
            'title',
            'message',
            'reference_id',
            'is_read',
            'created_at'
        ]
        read_only_fields = fields  # All fields are read-only to the client


class AnnouncementSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ['id', 'organization', 'branch', 'branch_name', 'title', 'body', 'is_published', 'published_at', 'expires_at', 'created_by_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'published_at', 'created_by_name', 'created_at', 'updated_at']
        extra_kwargs = {'organization': {'required': False}}

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return 'System'
        return f'{obj.created_by.first_name} {obj.created_by.last_name}'.strip() or obj.created_by.email


class OrganizationEmailSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationEmailSettings
        fields = ['id', 'organization', 'sender_name', 'from_email', 'reply_to_email', 'automation_enabled', 'updated_at']
        read_only_fields = ['id', 'organization', 'updated_at']


class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = ['id', 'organization', 'event_type', 'name', 'subject', 'body', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']


class EmailAutomationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailAutomationRule
        fields = ['id', 'organization', 'name', 'event_type', 'recipient_mode', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']


class EmailDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailDelivery
        fields = ['id', 'event_type', 'recipient_email', 'subject', 'status', 'error_message', 'created_at']
        read_only_fields = fields
