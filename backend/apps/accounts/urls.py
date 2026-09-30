from django.urls import path
from .views import (
    LoginView, LogoutView, MeView, ActivateView,
    PasswordResetRequestView, PasswordResetConfirmView, ChangePasswordView, TenantOwnerRegistrationView
)

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('register/', TenantOwnerRegistrationView.as_view(), name='tenant-owner-register'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
    path('activate/', ActivateView.as_view(), name='activate'),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-change/', ChangePasswordView.as_view(), name='password_change'),
]
