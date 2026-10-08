from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AlertRuleViewSet, EmployeeAlertPreferenceViewSet, AlertInstanceViewSet

router = DefaultRouter()
router.register(r'rules', AlertRuleViewSet, basename='alertrule')
router.register(r'preferences', EmployeeAlertPreferenceViewSet, basename='alertpreference')
router.register(r'instances', AlertInstanceViewSet, basename='alertinstance')

urlpatterns = [
    path('', include(router.urls)),
]
