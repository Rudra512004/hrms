from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OfficeNetworkViewSet

router = DefaultRouter()
router.register(r'office-networks', OfficeNetworkViewSet, basename='office-network')

urlpatterns = [
    path('', include(router.urls)),
]
