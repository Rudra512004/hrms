"""
URLs for dashboard app.
"""
from django.urls import path
from .views import DashboardOverviewView, DashboardTrendsView, DashboardCelebrationsView

app_name = 'dashboard'

urlpatterns = [
    path('overview/', DashboardOverviewView.as_view(), name='dashboard-overview'),
    path('trends/', DashboardTrendsView.as_view(), name='dashboard-trends'),
    path('celebrations/', DashboardCelebrationsView.as_view(), name='dashboard-celebrations'),
]
