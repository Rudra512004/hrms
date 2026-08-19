from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmployeeSelfServiceView, ProvisionEmployeeView, WFHRequestViewSet

router = DefaultRouter()
router.register(r'wfh-requests', WFHRequestViewSet, basename='wfh-request')

urlpatterns = [
    path('me/', EmployeeSelfServiceView.as_view(), name='employee-me'),
    path('', ProvisionEmployeeView.as_view(), name='employee-provision'),
    path('', include(router.urls)),
]
