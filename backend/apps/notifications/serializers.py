from rest_framework import serializers
from .models import Notification, Announcement

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


