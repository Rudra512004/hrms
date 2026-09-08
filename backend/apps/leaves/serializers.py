from rest_framework import serializers
from .models import LeaveType, LeaveBalance, LeaveRequest
from django.utils import timezone

class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ['id', 'organization', 'name', 'description', 'annual_allocation', 'is_active']
        read_only_fields = ['organization']

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
        start_date = data.get('start_date', self.instance.start_date if self.instance else None)
        end_date = data.get('end_date', self.instance.end_date if self.instance else None)
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})

        # Overlapping leave validation
        request = self.context.get('request')
        employee = None
        if self.instance:
            employee = self.instance.employee
        elif request and hasattr(request.user, 'employee'):
            employee = request.user.employee
        elif 'employee' in data:
            employee = data['employee']

        if employee and start_date and end_date:
            overlapping = LeaveRequest.objects.filter(
                employee=employee,
                status__in=['pending', 'approved'],
                start_date__lte=end_date,
                end_date__gte=start_date,
            )
            if self.instance and self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            if overlapping.exists():
                raise serializers.ValidationError({"detail": "An overlapping leave request already exists for this date range."})
        return data

class LeaveRequestReviewSerializer(serializers.Serializer):
    reviewer_comment = serializers.CharField(required=False, allow_blank=True)
