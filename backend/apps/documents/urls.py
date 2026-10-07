from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DocumentCategoryViewSet, DocumentTemplateViewSet, IssuedDocumentViewSet

router = DefaultRouter()
router.register(r'categories', DocumentCategoryViewSet, basename='document-category')
router.register(r'templates', DocumentTemplateViewSet, basename='document-template')
router.register(r'issued', IssuedDocumentViewSet, basename='issued-document')

urlpatterns = [
    path('', include(router.urls)),
]
