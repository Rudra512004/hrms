from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OfficeNetworkViewSet, OrganizationViewSet, DepartmentViewSet, DesignationViewSet

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='organization')
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'designations', DesignationViewSet, basename='designation')
router.register(r'office-networks', OfficeNetworkViewSet, basename='office-network')

urlpatterns = [
    path('', include(router.urls)),
]
