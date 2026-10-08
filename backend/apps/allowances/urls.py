from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AllowanceTypeViewSet, EmployeeAllowanceViewSet, ReimbursementClaimViewSet

app_name = 'allowances'

router = DefaultRouter()
router.register(r'types', AllowanceTypeViewSet, basename='allowancetype')
router.register(r'assignments', EmployeeAllowanceViewSet, basename='employeeallowance')
router.register(r'claims', ReimbursementClaimViewSet, basename='reimbursementclaim')

urlpatterns = [
    path('', include(router.urls)),
]
