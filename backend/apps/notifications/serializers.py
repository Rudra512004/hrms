from rest_framework import serializers
from .models import Notification

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
