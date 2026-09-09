from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssetCategoryViewSet, AssetViewSet

router = DefaultRouter()
router.register(r'categories', AssetCategoryViewSet, basename='asset-categories')
router.register(r'', AssetViewSet, basename='assets')

urlpatterns = [
    path('', include(router.urls)),
]
