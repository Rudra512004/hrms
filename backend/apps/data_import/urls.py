from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.data_import.views import TemplateViewSet, ImportJobViewSet

router = DefaultRouter()
router.register(r'templates', TemplateViewSet, basename='data-import-templates')
router.register(r'jobs', ImportJobViewSet, basename='data-import-jobs')

urlpatterns = [
    path('', include(router.urls)),
]
