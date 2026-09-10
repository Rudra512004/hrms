from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AttendanceViewSet, AttendanceManagementViewSet, HolidayViewSet, ShiftViewSet

router = DefaultRouter()
router.register(r'management', AttendanceManagementViewSet, basename='attendance-management')
router.register(r'holidays', HolidayViewSet, basename='holiday')
router.register(r'shifts', ShiftViewSet, basename='shift')
router.register(r'', AttendanceViewSet, basename='attendance')

urlpatterns = [
    path('', include(router.urls)),
]
