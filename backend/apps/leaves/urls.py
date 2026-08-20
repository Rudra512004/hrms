from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LeaveTypeViewSet, LeaveBalanceViewSet, LeaveRequestViewSet, AdminLeaveTypeViewSet

router = DefaultRouter()
router.register(r'types', LeaveTypeViewSet, basename='leave-types')
router.register(r'admin/types', AdminLeaveTypeViewSet, basename='admin-leave-types')
router.register(r'balances', LeaveBalanceViewSet, basename='leave-balances')
router.register(r'requests', LeaveRequestViewSet, basename='leave-requests')

urlpatterns = [
    path('', include(router.urls)),
]
