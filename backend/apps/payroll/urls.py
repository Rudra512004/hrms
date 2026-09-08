from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CompensationHistoryViewSet,
    PayrollPeriodViewSet,
    PayrollRecordViewSet,
    PayslipViewSet,
)
from .views_reporting import PayrollReportingViewSet

router = DefaultRouter()
router.register(r'compensation', CompensationHistoryViewSet, basename='compensation')
router.register(r'periods', PayrollPeriodViewSet, basename='payroll-period')
router.register(r'records', PayrollRecordViewSet, basename='payroll-record')
router.register(r'payslips', PayslipViewSet, basename='payslip')
router.register(r'reports', PayrollReportingViewSet, basename='payroll-reports')



urlpatterns = [
    path('', include(router.urls)),
]
