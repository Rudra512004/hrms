from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.utils.dateparse import parse_date
from apps.authorization.permissions import IsNetworkAllowed, require_permission
from apps.authorization.services import AuthorizationService
from django.db.models import Q
from .models import Attendance
from .analytics import ProductivityAnalyticsService
from datetime import timedelta

def timedelta_to_str(td):
    if td is None:
        return "00:00:00"
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

class ProductivityAnalyticsViewSet(viewsets.ViewSet):
    """
    We360 Workforce Intelligence & Productivity Analytics Endpoints.
    """
    permission_classes = [IsAuthenticated, IsNetworkAllowed, require_permission('attendance.view_all')]

    def _get_base_queryset(self, request):
        """
        Builds the base Attendance queryset enforcing RBAC branch/team scope
        and applying user-provided filters.
        """
        user = request.user
        
        # 1. Enforce RBAC
        authorized_branches = AuthorizationService.get_authorized_branches(user, 'attendance.view_all')
        authorized_teams = AuthorizationService.get_authorized_teams(user, 'attendance.view_all')

        qs = Attendance.objects.filter(
            Q(employee__branch__in=authorized_branches) |
            Q(employee__team__in=authorized_teams)
        )

        # 2. Apply explicit filters from query parameters
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if not start_date_str or not end_date_str:
            return None, Response({'detail': 'start_date and end_date are required parameters.'}, status=status.HTTP_400_BAD_REQUEST)

        start_date = parse_date(start_date_str)
        end_date = parse_date(end_date_str)

        if not start_date or not end_date:
            return None, Response({'detail': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        qs = qs.filter(date__range=[start_date, end_date])

        branch_id = request.query_params.get('branch_id')
        if branch_id:
            qs = qs.filter(employee__branch_id=branch_id)

        department_id = request.query_params.get('department_id')
        if department_id:
            qs = qs.filter(employee__department_id=department_id)

        team_id = request.query_params.get('team_id')
        if team_id:
            qs = qs.filter(employee__team_id=team_id)

        employee_id = request.query_params.get('employee_id')
        if employee_id:
            qs = qs.filter(employee_id=employee_id)

        return qs, None

    def _format_durations(self, data):
        """
        Helper to serialize timedelta objects to HH:MM:SS strings.
        """
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, timedelta):
                    data[k] = timedelta_to_str(v)
        elif isinstance(data, list):
            for item in data:
                for k, v in item.items():
                    if isinstance(v, timedelta):
                        item[k] = timedelta_to_str(v)
        return data

    @action(detail=False, methods=['get'])
    def overview(self, request):
        qs, error_response = self._get_base_queryset(request)
        if error_response:
            return error_response

        data = ProductivityAnalyticsService.get_overview_metrics(qs)
        return Response(self._format_durations(data))

    @action(detail=False, methods=['get'])
    def trends(self, request):
        qs, error_response = self._get_base_queryset(request)
        if error_response:
            return error_response

        data = ProductivityAnalyticsService.get_trends(qs)
        return Response(self._format_durations(data))

    @action(detail=False, methods=['get'], url_path='team-breakdown')
    def team_breakdown(self, request):
        qs, error_response = self._get_base_queryset(request)
        if error_response:
            return error_response

        data = ProductivityAnalyticsService.get_team_breakdown(qs)
        return Response(self._format_durations(data))

    @action(detail=False, methods=['get'], url_path='employee-breakdown')
    def employee_breakdown(self, request):
        qs, error_response = self._get_base_queryset(request)
        if error_response:
            return error_response

        data = ProductivityAnalyticsService.get_employee_breakdown(qs)
        return Response(self._format_durations(data))
