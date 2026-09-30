from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AttendanceViewSet, AttendanceManagementViewSet, HolidayViewSet, ShiftViewSet
from .break_type_view import BreakTypeViewSet
from .location_alerts import LocationAlertView
from .timesheet_views import TimesheetPolicyViewSet,ProjectViewSet,TimesheetViewSet

router = DefaultRouter()
router.register(r'management', AttendanceManagementViewSet, basename='attendance-management')
router.register(r'holidays', HolidayViewSet, basename='holiday')
router.register(r'shifts', ShiftViewSet, basename='shift')
router.register(r'break-types', BreakTypeViewSet, basename='break-type')
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'timesheets', TimesheetViewSet, basename='timesheet')
router.register(r'timesheet-policy', TimesheetPolicyViewSet, basename='timesheet-policy')
router.register(r'', AttendanceViewSet, basename='attendance')

urlpatterns = [
    path('location-alerts/', LocationAlertView.as_view(), name='location-alerts'),
    path('', include(router.urls)),
]
