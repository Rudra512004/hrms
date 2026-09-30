from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, AnnouncementViewSet, OrganizationEmailSettingsViewSet, EmailTemplateViewSet, EmailAutomationRuleViewSet, EmailDeliveryViewSet

app_name = 'notifications'

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'announcements', AnnouncementViewSet, basename='announcement')
router.register(r'email-settings', OrganizationEmailSettingsViewSet, basename='email-settings')
router.register(r'email-templates', EmailTemplateViewSet, basename='email-template')
router.register(r'email-rules', EmailAutomationRuleViewSet, basename='email-rule')
router.register(r'email-deliveries', EmailDeliveryViewSet, basename='email-delivery')

urlpatterns = [
    path('', include(router.urls)),
]
