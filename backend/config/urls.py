from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

from django.db import connection
from django.db.utils import OperationalError

def health_check(request):
    try:
        connection.ensure_connection()
        return JsonResponse({'status': 'ok', 'service': 'beyondsure-hrms', 'database': 'ok'})
    except OperationalError:
        return JsonResponse({'status': 'error', 'service': 'beyondsure-hrms', 'database': 'unavailable'}, status=503)

urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('api/v1/health/', health_check, name='api-health-check'),
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/employees/', include('apps.employees.urls')),
    path('api/v1/organization/', include('apps.organization.urls')),
    path('api/v1/attendance/', include('apps.attendance.urls')),
    path('api/v1/leaves/', include('apps.leaves.urls')),
    path('api/v1/', include('apps.audit.urls')),
    path('api/v1/authorization/', include('apps.authorization.urls')),
    path('api/v1/payroll/', include('apps.payroll.urls')),
    path('api/v1/assets/', include('apps.assets.urls')),
    path('api/v1/', include('apps.notifications.urls')),
    path('api/v1/dashboard/', include('apps.dashboard.urls')),
    path('api/v1/candidates/', include('apps.candidates.urls')),
    path('api/v1/allowances/', include('apps.allowances.urls')),
]
