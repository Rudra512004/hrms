from rest_framework import serializers
from .models import Attendance

class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = ['id', 'employee', 'date', 'check_in', 'check_out', 'status']
        read_only_fields = ['id', 'employee', 'date', 'check_in', 'check_out', 'status']
