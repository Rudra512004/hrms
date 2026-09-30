from datetime import date
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.authorization.permissions import require_permission
from apps.authorization.services import AuthorizationService
from .models import Attendance
from .utils import calculate_haversine_distance

class LocationAlertView(APIView):
    """Read-only geo-fence exception queue based on recorded attendance data."""
    def get_permissions(self):
        return [IsAuthenticated(), require_permission('attendance.view_all')()]
    def get(self, request):
        try: target_date=date.fromisoformat(request.query_params.get('date', str(date.today())))
        except ValueError: return Response({'detail':'date must be YYYY-MM-DD.'},status=400)
        user=request.user
        records=Attendance.objects.filter(date=target_date,check_in_latitude__isnull=False,check_in_longitude__isnull=False).select_related('employee__user','employee__branch')
        if not user.is_superuser:
            records=records.filter(employee__branch__in=AuthorizationService.get_authorized_branches(user,'attendance.view_all'))
        alerts=[]
        for record in records:
            branch=record.employee.branch
            if not branch or branch.latitude is None or branch.longitude is None: continue
            distance=round(calculate_haversine_distance(record.check_in_latitude,record.check_in_longitude,branch.latitude,branch.longitude))
            if distance>branch.radius:
                alerts.append({'attendance_id':record.id,'employee_id':record.employee_id,'employee_name':f'{record.employee.user.first_name} {record.employee.user.last_name}'.strip() or record.employee.user.email,'branch_name':branch.name,'distance_meters':distance,'allowed_radius_meters':branch.radius,'check_in':record.check_in})
        return Response({'date':str(target_date),'count':len(alerts),'results':alerts})
