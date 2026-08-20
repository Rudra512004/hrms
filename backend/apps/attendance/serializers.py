from rest_framework import serializers
from .models import Attendance, AttendanceBreak

class AttendanceBreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceBreak
        fields = ['id', 'started_at', 'ended_at']
        read_only_fields = ['id', 'started_at', 'ended_at']

class AttendanceSerializer(serializers.ModelSerializer):
    is_on_break = serializers.SerializerMethodField()
    breaks = AttendanceBreakSerializer(many=True, read_only=True)

    class Meta:
        model = Attendance
        fields = ['id', 'employee', 'date', 'check_in', 'check_out', 'status', 'total_break_duration', 'productive_work_duration', 'is_on_break', 'breaks']
        read_only_fields = ['id', 'employee', 'date', 'check_in', 'check_out', 'status', 'total_break_duration', 'productive_work_duration', 'is_on_break', 'breaks']

    def get_is_on_break(self, obj):
        return obj.breaks.filter(ended_at__isnull=True).exists()
