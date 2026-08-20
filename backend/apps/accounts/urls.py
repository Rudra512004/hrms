from django.urls import path
from .views import LoginView, LogoutView, MeView, ActivateView, PasswordResetRequestView, PasswordResetConfirmView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
    path('activate/', ActivateView.as_view(), name='activate'),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]
