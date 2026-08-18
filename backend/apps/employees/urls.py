from django.urls import path
from .views import EmployeeSelfServiceView, ProvisionEmployeeView

urlpatterns = [
    path('me/', EmployeeSelfServiceView.as_view(), name='employee-me'),
    path('', ProvisionEmployeeView.as_view(), name='employee-provision'),
]
