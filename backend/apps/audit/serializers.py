from rest_framework import serializers
from .models import AuditLog

class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source='actor.email', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = ['id', 'actor', 'actor_email', 'action', 'target_type', 'target_id', 'timestamp', 'metadata', 'ip_address']
        read_only_fields = fields
