from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RoleViewSet, PermissionViewSet, UserRoleViewSet, UserPermissionGrantViewSet, CurrentUserPermissionsView, RolePermissionViewSet

router = DefaultRouter()
router.register(r'roles', RoleViewSet, basename='roles')
router.register(r'permissions', PermissionViewSet, basename='permissions')
router.register(r'user-roles', UserRoleViewSet, basename='user-roles')
router.register(r'user-permissions', UserPermissionGrantViewSet, basename='user-permissions')
router.register(r'role-permissions', RolePermissionViewSet, basename='role-permissions')

urlpatterns = [
    path('me/', CurrentUserPermissionsView.as_view(), name='auth-me'),
    path('', include(router.urls)),
]
