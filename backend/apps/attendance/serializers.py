from rest_framework import serializers
from .models import Attendance, AttendanceBreak, Holiday, Shift

class AttendanceBreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceBreak
        fields = ['id', 'started_at', 'ended_at']
        read_only_fields = ['id', 'started_at', 'ended_at']

class AttendanceSerializer(serializers.ModelSerializer):
    is_on_break = serializers.SerializerMethodField()
    breaks = AttendanceBreakSerializer(many=True, read_only=True)
    employee_name = serializers.SerializerMethodField()
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)

    class Meta:
        model = Attendance
        fields = ['id', 'employee', 'employee_name', 'employee_code', 'date', 'check_in', 'check_out', 'status', 'is_late', 'total_break_duration', 'productive_work_duration', 'is_on_break', 'breaks']
        read_only_fields = ['id', 'employee', 'employee_name', 'employee_code', 'date', 'check_in', 'check_out', 'status', 'is_late', 'total_break_duration', 'productive_work_duration', 'is_on_break', 'breaks']

    def get_is_on_break(self, obj):
        return obj.breaks.filter(ended_at__isnull=True).exists()

    def get_employee_name(self, obj):
        if not obj.employee or not obj.employee.user:
            return None
        return f"{obj.employee.user.first_name} {obj.employee.user.last_name}".strip()

class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ['id', 'branch', 'name', 'date', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = ['id', 'branch', 'name', 'start_time', 'end_time', 'grace_period', 'full_day_hours', 'half_day_hours', 'work_days', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_work_days(self, value):
        if value:
            days = value.split(',')
            seen = set()
            for day in days:
                day_stripped = day.strip()
                if not day_stripped.isdigit() or int(day_stripped) < 0 or int(day_stripped) > 6:
                    raise serializers.ValidationError("work_days must be a comma-separated list of integers between 0 and 6.")
                if day_stripped in seen:
                    raise serializers.ValidationError("work_days cannot contain duplicate days.")
                seen.add(day_stripped)
        return value

    def validate(self, attrs):
        branch = attrs.get('branch', getattr(self.instance, 'branch', None))
        is_active = attrs.get('is_active', getattr(self.instance, 'is_active', True) if self.instance else True)

        if is_active and branch:
            active_shifts = Shift.objects.filter(branch=branch, is_active=True)
            if self.instance and self.instance.pk:
                active_shifts = active_shifts.exclude(pk=self.instance.pk)
            if active_shifts.exists():
                raise serializers.ValidationError(
                    "An active shift is already configured for this branch. Deactivate the existing shift before activating a new one."
                )
        return attrs
