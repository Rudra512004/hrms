from rest_framework import serializers
from .models import OfficeNetwork

class OfficeNetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficeNetwork
        fields = ['id', 'organization', 'name', 'network', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
