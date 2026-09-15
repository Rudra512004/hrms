import os

filepath = 'backend/apps/attendance/serializers.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix imports
content = content.replace(
    "from .models import Attendance, AttendanceBreak, Holiday, Shift", 
    "from .models import Attendance, AttendanceBreak, Holiday, Shift, EmployeeShiftAssignment"
)

# Update ShiftSerializer
old_shift_meta = "        fields = ['id', 'organization', 'name', 'start_time', 'end_time', 'grace_period', 'is_active', 'created_at', 'updated_at']"
new_shift_meta = "        fields = ['id', 'organization', 'name', 'start_time', 'end_time', 'grace_period', 'full_day_hours', 'half_day_hours', 'work_days', 'is_active', 'created_at', 'updated_at']"
content = content.replace(old_shift_meta, new_shift_meta)

validation_methods = '''
    def validate_work_days(self, value):
        if value:
            days = value.split(',')
            for day in days:
                if not day.strip().isdigit() or int(day.strip()) < 0 or int(day.strip()) > 6:
                    raise serializers.ValidationError("work_days must be a comma-separated list of integers between 0 and 6.")
        return value
'''
content = content + validation_methods

assignment_serializer = '''
class EmployeeShiftAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeShiftAssignment
        fields = ['id', 'employee', 'shift', 'effective_from', 'effective_to', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        employee = attrs.get('employee', getattr(self.instance, 'employee', None))
        shift = attrs.get('shift', getattr(self.instance, 'shift', None))
        
        # Verify cross-tenant
        if employee and shift and employee.organization_id != shift.organization_id:
            raise serializers.ValidationError("Employee and Shift must belong to the same organization.")

        # Ensure we do not allow assigning an employee from another tenant
        request = self.context.get('request')
        if request and hasattr(request.user, 'employee'):
            org_id = request.user.employee.organization_id
            if employee and employee.organization_id != org_id:
                raise serializers.ValidationError("Cannot assign employee from another organization.")
            if shift and shift.organization_id != org_id:
                raise serializers.ValidationError("Cannot assign shift from another organization.")
                
        return attrs
'''
content = content + assignment_serializer

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
