from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/employees/', include('apps.employees.urls')),
    path('api/v1/organization/', include('apps.organization.urls')),
]
