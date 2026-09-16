from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OfficeNetworkViewSet, OrganizationViewSet, DepartmentViewSet, DesignationViewSet, BranchViewSet, WorkingCalendarViewSet, OrganizationSetupViewSet

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='organization')
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'designations', DesignationViewSet, basename='designation')
router.register(r'office-networks', OfficeNetworkViewSet, basename='office-network')
router.register(r'branches', BranchViewSet, basename='branch')
router.register(r'working-calendars', WorkingCalendarViewSet, basename='working-calendar')
router.register(r'setup', OrganizationSetupViewSet, basename='setup')

urlpatterns = [
    path('', include(router.urls)),
]
