import os

filepath = 'backend/apps/attendance/urls.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    "from .views import AttendanceViewSet, AttendanceManagementViewSet, HolidayViewSet, ShiftViewSet",
    "from .views import AttendanceViewSet, AttendanceManagementViewSet, HolidayViewSet, ShiftViewSet, EmployeeShiftAssignmentViewSet"
)

content = content.replace(
    "router.register(r'shifts', ShiftViewSet, basename='shift')",
    "router.register(r'shifts', ShiftViewSet, basename='shift')\nrouter.register(r'shift-assignments', EmployeeShiftAssignmentViewSet, basename='shift-assignment')"
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
