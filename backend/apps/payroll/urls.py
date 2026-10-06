from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CompensationHistoryViewSet,
    PayrollRunViewSet,
    PayrollRecordViewSet,
    PayslipViewSet,
)
from .views_reporting import PayrollReportingViewSet
from .salary_configuration_views import SalaryComponentViewSet, SalaryStructureViewSet

router = DefaultRouter()
router.register(r'compensation', CompensationHistoryViewSet, basename='compensation')
router.register(r'periods', PayrollRunViewSet, basename='payroll-period')
router.register(r'records', PayrollRecordViewSet, basename='payroll-record')
router.register(r'payslips', PayslipViewSet, basename='payslip')
router.register(r'reports', PayrollReportingViewSet, basename='payroll-reports')
router.register(r'salary-components', SalaryComponentViewSet, basename='salary-component')
router.register(r'salary-structures', SalaryStructureViewSet, basename='salary-structure')



urlpatterns = [
    path('', include(router.urls)),
]
