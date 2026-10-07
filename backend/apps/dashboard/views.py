"""
Dashboard views for HRMS Dashboard V2.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .services import DashboardAggregationService, DashboardTrendsService


class DashboardOverviewView(APIView):
    """
    Consolidated Dashboard V2 Overview endpoint.
    GET /api/v1/dashboard/overview/

    Authenticates user and returns dynamically gated sections:
    - 'personal': Caller's personal attendance, balances, pending requests, holidays.
    - 'team': Direct reports attendance and approvals queue (if user has direct reports).
    - 'organization': Org-wide workforce, attendance pulse, and approval counts (if user has permissions).

    Returns None for any section where caller lacks context or permissions.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        branch_id = request.query_params.get("branch_id")
        overview_data = DashboardAggregationService.get_dashboard_overview(request.user, branch_id)
        return Response(overview_data, status=status.HTTP_200_OK)


class DashboardTrendsView(APIView):
    """
    Historical Analytics Trends endpoint.
    GET /api/v1/dashboard/trends/?window=7d|6m

    Query params:
    - window: '7d' (7-day attendance trend) or '6m' (6-month workforce trend).
    Rejects unsupported window values with HTTP 400.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        window = request.query_params.get('window')
        if not window or window not in ('7d', '6m'):
            return Response(
                {'detail': "Invalid window. Supported values are '7d' and '6m'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        branch_id = request.query_params.get("branch_id")
        trends_data = DashboardTrendsService.get_trends(request.user, window, branch_id)
        return Response(trends_data, status=status.HTTP_200_OK)


class DashboardCelebrationsView(APIView):
    """
    Celebrations endpoint.
    GET /api/v1/dashboard/celebrations/
    
    Returns birthdays, work anniversaries, and new joinees within the current month/week.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from apps.authorization.services import AuthorizationService
        org = AuthorizationService.get_primary_organization(request.user)
        if not org:
            return Response([], status=status.HTTP_200_OK)
            
        from apps.employees.models import Employee
        from django.utils import timezone
        import datetime
        
        today = timezone.now().date()
        thirty_days_ago = today - datetime.timedelta(days=30)
        thirty_days_ahead = today + datetime.timedelta(days=30)
        
        employees = Employee.objects.filter(
            organization=org,
            employment_status__in=['active', 'probation', 'onboarding']
        ).select_related('user')
        
        birthdays = []
        anniversaries = []
        joinees = []
        
        for emp in employees:
            if hasattr(emp, 'dependents'):
                # Check for employee's own birthday (if logged as dependent 'Self')
                # Or just list dependents' birthdays if you want, but usually it's employee's birthday.
                pass
                
            # New Joinees (joined within last 30 days or joining within 30 days)
            if emp.joining_date:
                if thirty_days_ago <= emp.joining_date <= thirty_days_ahead:
                    joinees.append({
                        'id': emp.id,
                        'name': f"{emp.user.first_name} {emp.user.last_name}".strip(),
                        'date': str(emp.joining_date),
                        'type': 'new_joinee'
                    })
                    
                # Work Anniversaries
                years = today.year - emp.joining_date.year
                if years > 0 and (today.month, today.day) <= (emp.joining_date.month, emp.joining_date.day) and datetime.date(today.year, emp.joining_date.month, emp.joining_date.day) <= thirty_days_ahead:
                    anniversaries.append({
                        'id': emp.id,
                        'name': f"{emp.user.first_name} {emp.user.last_name}".strip(),
                        'date': str(datetime.date(today.year, emp.joining_date.month, emp.joining_date.day)),
                        'years': years,
                        'type': 'anniversary'
                    })
                    
        # Birthdays from EmployeeDependent (assuming 'Self' is used or we just list all employee dependents)
        from apps.employees.models import EmployeeDependent
        deps = EmployeeDependent.objects.filter(employee__in=employees, dob__isnull=False)
        for dep in deps:
            if (today.month, today.day) <= (dep.dob.month, dep.dob.day) and datetime.date(today.year, dep.dob.month, dep.dob.day) <= thirty_days_ahead:
                name_prefix = f"{dep.employee.user.first_name}'s " if dep.relationship.lower() != 'self' else ""
                birthdays.append({
                    'id': dep.employee.id,
                    'name': f"{name_prefix}{dep.full_name}".strip(),
                    'date': str(datetime.date(today.year, dep.dob.month, dep.dob.day)),
                    'type': 'birthday'
                })

        celebrations = joinees + anniversaries + birthdays
        celebrations.sort(key=lambda x: x['date'])
        
        return Response(celebrations, status=status.HTTP_200_OK)

