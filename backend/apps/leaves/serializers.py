from rest_framework import serializers
from .models import LeaveType, LeaveBalance, LeaveRequest, BranchLeavePolicy
from apps.organization.services import WorkingCalendarService
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ['id', 'organization', 'name', 'description', 'is_active']
        read_only_fields = ['organization']

class LeaveBalanceSerializer(serializers.ModelSerializer):
    remaining = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True, default=None)
    employee_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = LeaveBalance
        fields = ['id', 'employee', 'employee_name', 'employee_code', 'leave_type', 'leave_type_name', 'branch', 'leave_cycle', 'allocated', 'used', 'carried_forward', 'adjustment', 'remaining']
        read_only_fields = ['employee', 'allocated', 'used', 'carried_forward', 'adjustment']

    def get_employee_name(self, obj):
        if not obj.employee or not obj.employee.user:
            return None
        return f"{obj.employee.user.first_name} {obj.employee.user.last_name}".strip()


class LeaveRequestSerializer(serializers.ModelSerializer):
    duration_days = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True, allow_null=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    employee_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'employee', 'employee_code', 'employee_name',
            'leave_type', 'leave_type_name', 'start_date', 'end_date', 'reason',
            'is_half_day', 'half_day_period', 'supporting_document',
            'status', 'reviewed_by', 'reviewed_at', 'reviewer_comment', 'created_at', 'updated_at', 'duration_days'
        ]
        read_only_fields = ['employee', 'status', 'reviewed_by', 'reviewed_at', 'reviewer_comment']

    def get_employee_name(self, obj):
        if obj.employee and getattr(obj.employee, 'user', None):
            u = obj.employee.user
            if hasattr(u, 'get_full_name'):
                return u.get_full_name()
            full_name = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
            return full_name if full_name else getattr(u, 'email', str(obj.employee.id))
        return None

    def validate(self, data):
        start_date = data.get('start_date', self.instance.start_date if self.instance else None)
        end_date = data.get('end_date', self.instance.end_date if self.instance else None)
        leave_type = data.get('leave_type', self.instance.leave_type if self.instance else None)
        is_half_day = data.get('is_half_day', self.instance.is_half_day if self.instance else False)
        half_day_period = data.get('half_day_period', self.instance.half_day_period if self.instance else None)
        supporting_doc = data.get('supporting_document', self.instance.supporting_document if self.instance else None)

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})

        request = self.context.get('request')
        employee = None
        if self.instance:
            employee = self.instance.employee
        elif request:
            try:
                from apps.organization.context import get_current_employee
                employee = get_current_employee(request)
            except Exception:
                employee = None
        elif 'employee' in data:
            employee = data['employee']

        if not employee:
            raise serializers.ValidationError({"detail": "Employee identity is required."})

        if leave_type:
            if not leave_type.is_active:
                raise serializers.ValidationError({"leave_type": "Leave type must be active."})
            if leave_type.organization_id != employee.organization_id:
                raise serializers.ValidationError({"leave_type": "Leave type must belong to the employee's organization."})

            branch = getattr(employee, 'branch', None)
            if not branch:
                raise serializers.ValidationError({"detail": "Employee must be assigned to a branch."})

            policy = BranchLeavePolicy.objects.filter(branch=branch, leave_type=leave_type).first()
            if not policy:
                raise serializers.ValidationError({"leave_type": "No leave policy found for this branch and leave type."})

            if is_half_day and not policy.half_day_allowed:
                raise serializers.ValidationError({"is_half_day": "Half-day leaves are not allowed for this leave type."})

            if is_half_day and not half_day_period:
                raise serializers.ValidationError({"half_day_period": "Half-day period is required when requesting a half-day."})

            if not is_half_day and half_day_period:
                raise serializers.ValidationError({"half_day_period": "Half-day period must not be supplied for full-day leaves."})

            if policy.requires_supporting_document and not supporting_doc:
                raise serializers.ValidationError({"supporting_document": "Supporting document is required for this leave type."})

            if policy.advance_notice_days > 0 and start_date:
                today = timezone.localdate()
                if start_date < today + timedelta(days=policy.advance_notice_days):
                    raise serializers.ValidationError({"start_date": f"This leave type requires at least {policy.advance_notice_days} days of advance notice."})

            if start_date and end_date:
                working_days = WorkingCalendarService.count_working_days(branch, start_date, end_date)
                if working_days == 0:
                    raise serializers.ValidationError({"detail": "Requested date range contains zero working days."})

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
