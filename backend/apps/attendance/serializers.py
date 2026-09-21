from rest_framework import serializers
from .models import Attendance, AttendanceBreak, Holiday, Shift, EmployeeShiftAssignment

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
        return f"{obj.employee.user.first_name} {obj.employee.user.last_name}".strip() or obj.employee.user.email

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

class EmployeeShiftAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeShiftAssignment
        fields = ['id', 'employee', 'shift', 'effective_from', 'effective_to', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        employee = attrs.get('employee', getattr(self.instance, 'employee', None))
        shift = attrs.get('shift', getattr(self.instance, 'shift', None))

        # Verify cross-tenant
        if employee and shift and employee.branch_id and shift.branch_id and employee.branch_id != shift.branch_id:
            raise serializers.ValidationError({"employee": "Employee and Shift must belong to the same branch."})

        # Ensure we do not allow assigning an employee from another tenant or unauthorized branch
        request = self.context.get('request')
        if request and not getattr(request.user, 'is_superuser', False) and hasattr(request.user, 'employee') and request.user.employee:
            from apps.authorization.services import AuthorizationService
            user_org_id = request.user.employee.organization_id
            if employee and employee.organization_id != user_org_id:
                raise serializers.ValidationError({"employee": "Cannot assign employee from another organization."})
            if shift and shift.branch.organization_id != user_org_id:
                raise serializers.ValidationError({"shift": "Cannot assign shift from another organization."})
            if employee and not AuthorizationService.has_permission(request.user, 'shift_assignment.manage', employee.branch_id):
                raise serializers.ValidationError({"employee": "You do not have permission to assign shifts in this branch."})

        effective_from = attrs.get('effective_from', getattr(self.instance, 'effective_from', None))
        effective_to = attrs.get('effective_to', getattr(self.instance, 'effective_to', None))

        if effective_to and effective_from and effective_to < effective_from:
            raise serializers.ValidationError({"effective_to": "effective_to cannot be earlier than effective_from."})

        # Model clean for overlap validation
        instance = EmployeeShiftAssignment(**attrs)
        if self.instance:
            instance.pk = self.instance.pk
            if 'employee' not in attrs:
                instance.employee = self.instance.employee
            if 'shift' not in attrs:
                instance.shift = self.instance.shift
            if 'effective_from' not in attrs:
                instance.effective_from = self.instance.effective_from

        try:
            instance.clean()
        except serializers.ValidationError as e:
            raise e
        except Exception as e:
            # Django ValidationError
            from django.core.exceptions import ValidationError as DjangoValidationError
            if isinstance(e, DjangoValidationError):
                raise serializers.ValidationError(e.message_dict if hasattr(e, 'message_dict') else list(e.messages))
            raise e

        return attrs
