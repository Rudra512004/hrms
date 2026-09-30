from rest_framework import serializers
from .models import Attendance, AttendanceBreak, Holiday, Shift, BreakType, TimesheetPolicy, Project, Timesheet, TimeEntry

class AttendanceBreakSerializer(serializers.ModelSerializer):
    break_type_name = serializers.CharField(source='break_type.name', read_only=True)
    class Meta:
        model = AttendanceBreak
        fields = ['id', 'break_type', 'break_type_name', 'started_at', 'ended_at']
        read_only_fields = ['id', 'break_type', 'break_type_name', 'started_at', 'ended_at']

class BreakTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BreakType
        fields = ['id', 'organization', 'name', 'max_duration_minutes', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'organization': {'required': False}}

class TimesheetPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model=TimesheetPolicy; fields=['id','organization','cadence','requires_manager_approval','lock_on_submit','manager_can_reopen','updated_at']; read_only_fields=['id','organization','updated_at']

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model=Project; fields=['id','organization','name','code','is_active']; read_only_fields=['id','organization']

class TimeEntrySerializer(serializers.ModelSerializer):
    project_name=serializers.CharField(source='project.name',read_only=True)
    class Meta:
        model=TimeEntry; fields=['id','timesheet','project','project_name','work_date','minutes','note']; read_only_fields=['id','timesheet']

class TimesheetSerializer(serializers.ModelSerializer):
    employee_name=serializers.SerializerMethodField(); entries=TimeEntrySerializer(many=True,read_only=True)
    class Meta:
        model=Timesheet; fields=['id','employee','employee_name','period_start','period_end','status','submitted_at','reviewed_at','reviewer_comment','entries']; read_only_fields=['id','employee','employee_name','status','submitted_at','reviewed_at','reviewer_comment','entries']
    def get_employee_name(self,obj): return f'{obj.employee.user.first_name} {obj.employee.user.last_name}'.strip() or obj.employee.user.email

class AttendanceSerializer(serializers.ModelSerializer):
    is_on_break = serializers.SerializerMethodField()
    breaks = AttendanceBreakSerializer(many=True, read_only=True)
    employee_name = serializers.SerializerMethodField()
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    distance_from_branch = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = ['id', 'employee', 'employee_name', 'employee_code', 'date', 'check_in', 'check_out', 'status', 'is_late', 'total_break_duration', 'productive_work_duration', 'is_on_break', 'breaks', 'distance_from_branch']
        read_only_fields = ['id', 'employee', 'employee_name', 'employee_code', 'date', 'check_in', 'check_out', 'status', 'is_late', 'total_break_duration', 'productive_work_duration', 'is_on_break', 'breaks', 'distance_from_branch']

    def get_is_on_break(self, obj):
        return obj.breaks.filter(ended_at__isnull=True).exists()

    def get_employee_name(self, obj):
        if not obj.employee or not obj.employee.user:
            return None
        return f"{obj.employee.user.first_name} {obj.employee.user.last_name}".strip()

    def get_distance_from_branch(self, obj):
        if obj.check_in_latitude and obj.check_in_longitude and obj.employee.branch and obj.employee.branch.latitude and obj.employee.branch.longitude:
            from .utils import calculate_haversine_distance
            return round(calculate_haversine_distance(
                obj.check_in_latitude, obj.check_in_longitude,
                obj.employee.branch.latitude, obj.employee.branch.longitude
            ))
        return None

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
