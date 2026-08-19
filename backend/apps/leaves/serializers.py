from rest_framework import serializers
from .models import LeaveType, LeaveBalance, LeaveRequest
from django.utils import timezone

class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ['id', 'organization', 'name', 'description', 'annual_allocation', 'is_active']

class LeaveBalanceSerializer(serializers.ModelSerializer):
    remaining = serializers.IntegerField(read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)

    class Meta:
        model = LeaveBalance
        fields = ['id', 'employee', 'leave_type', 'leave_type_name', 'allocated', 'used', 'remaining']
        read_only_fields = ['employee', 'allocated', 'used']

class LeaveRequestSerializer(serializers.ModelSerializer):
    duration_days = serializers.IntegerField(read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'employee', 'leave_type', 'leave_type_name', 'start_date', 'end_date', 'reason',
            'status', 'reviewed_by', 'reviewed_at', 'reviewer_comment', 'created_at', 'updated_at', 'duration_days'
        ]
        read_only_fields = ['employee', 'status', 'reviewed_by', 'reviewed_at', 'reviewer_comment']

    def validate(self, data):
        if data['end_date'] < data['start_date']:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})
        return data

class LeaveRequestReviewSerializer(serializers.Serializer):
    reviewer_comment = serializers.CharField(required=False, allow_blank=True)
