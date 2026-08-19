from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RoleViewSet, PermissionViewSet, UserRoleViewSet, UserPermissionGrantViewSet

router = DefaultRouter()
router.register(r'roles', RoleViewSet, basename='roles')
router.register(r'permissions', PermissionViewSet, basename='permissions')
router.register(r'user-roles', UserRoleViewSet, basename='user-roles')
router.register(r'user-permissions', UserPermissionGrantViewSet, basename='user-permissions')

urlpatterns = [
    path('', include(router.urls)),
]
