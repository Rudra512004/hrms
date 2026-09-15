import os

filepath = 'backend/apps/attendance/views.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix imports
content = content.replace(
    "from .models import Attendance, AttendanceBreak, Holiday, Shift", 
    "from .models import Attendance, AttendanceBreak, Holiday, Shift, EmployeeShiftAssignment"
)
content = content.replace(
    "from .serializers import AttendanceSerializer, HolidaySerializer, ShiftSerializer",
    "from .serializers import AttendanceSerializer, HolidaySerializer, ShiftSerializer, EmployeeShiftAssignmentSerializer"
)

assignment_viewset = '''

class EmployeeShiftAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeShiftAssignmentSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return EmployeeShiftAssignment.objects.all()
        if hasattr(user, 'employee') and user.employee.organization_id:
            return EmployeeShiftAssignment.objects.filter(
                employee__organization_id=user.employee.organization_id
            )
        return EmployeeShiftAssignment.objects.none()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('shift_assignment.view')
        else:
            permission = require_permission('shift_assignment.manage')
        return [IsAuthenticated(), permission()]
'''
content = content + assignment_viewset

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
