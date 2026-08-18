from django.urls import path
from .views import LoginView, LogoutView, MeView, ActivateView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
    path('activate/', ActivateView.as_view(), name='activate'),
]
