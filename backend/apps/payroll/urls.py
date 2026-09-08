from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CompensationHistoryViewSet,
    PayrollPeriodViewSet,
    PayrollRecordViewSet,
    PayslipViewSet,
)

router = DefaultRouter()
router.register(r'compensation', CompensationHistoryViewSet, basename='compensation')
router.register(r'periods', PayrollPeriodViewSet, basename='payroll-period')
router.register(r'records', PayrollRecordViewSet, basename='payroll-record')
router.register(r'payslips', PayslipViewSet, basename='payslip')


urlpatterns = [
    path('', include(router.urls)),
]
