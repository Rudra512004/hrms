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
        overview_data = DashboardAggregationService.get_dashboard_overview(request.user)
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

        trends_data = DashboardTrendsService.get_trends(request.user, window)
        return Response(trends_data, status=status.HTTP_200_OK)

