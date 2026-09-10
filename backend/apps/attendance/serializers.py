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
        fields = ['id', 'employee', 'employee_name', 'employee_code', 'date', 'check_in', 'check_out', 'status', 'total_break_duration', 'productive_work_duration', 'is_on_break', 'breaks']
        read_only_fields = ['id', 'employee', 'employee_name', 'employee_code', 'date', 'check_in', 'check_out', 'status', 'total_break_duration', 'productive_work_duration', 'is_on_break', 'breaks']

    def get_is_on_break(self, obj):
        return obj.breaks.filter(ended_at__isnull=True).exists()

    def get_employee_name(self, obj):
        return f"{obj.employee.user.first_name} {obj.employee.user.last_name}".strip() or obj.employee.user.email

class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ['id', 'organization', 'name', 'date', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']

class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = ['id', 'organization', 'name', 'start_time', 'end_time', 'grace_period', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']
