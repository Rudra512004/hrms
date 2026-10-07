from django.db.models import Sum, Avg, Count, F, QuerySet
from datetime import timedelta
from typing import Dict, Any, List

class ProductivityAnalyticsService:
    """
    We360 Workforce Intelligence & Productivity Analytics Service.
    Aggregates productivity data over date ranges and organizational scopes.
    Uses efficient Django ORM aggregations to avoid loading full datasets into memory.
    """

    @staticmethod
    def get_overview_metrics(base_qs: QuerySet) -> Dict[str, Any]:
        """
        Calculates aggregate productivity metrics for a given pre-filtered Attendance queryset.
        """
        aggregations = base_qs.aggregate(
            attendance_count=Count('id'),
            total_online_duration=Sum('productivity__online_duration'),
            total_active_duration=Sum('productivity__active_duration'),
            total_idle_duration=Sum('productivity__idle_duration'),
            total_productive_duration=Sum('productivity__productive_duration'),
            total_unproductive_duration=Sum('productivity__unproductive_duration'),
            total_neutral_duration=Sum('productivity__neutral_duration'),
            total_break_duration=Sum('total_break_duration'),
            average_active_percent=Avg('productivity__active_percent'),
            total_mouse_clicks=Sum('productivity__mouse_clicks'),
            total_key_presses=Sum('productivity__key_presses'),
        )

        return {
            'attendance_count': aggregations['attendance_count'] or 0,
            'total_online_duration': aggregations['total_online_duration'] or timedelta(0),
            'total_active_duration': aggregations['total_active_duration'] or timedelta(0),
            'total_idle_duration': aggregations['total_idle_duration'] or timedelta(0),
            'total_productive_duration': aggregations['total_productive_duration'] or timedelta(0),
            'total_unproductive_duration': aggregations['total_unproductive_duration'] or timedelta(0),
            'total_neutral_duration': aggregations['total_neutral_duration'] or timedelta(0),
            'total_break_duration': aggregations['total_break_duration'] or timedelta(0),
            'average_active_percent': float(aggregations['average_active_percent']) if aggregations['average_active_percent'] is not None else 0.0,
            'total_mouse_clicks': aggregations['total_mouse_clicks'] or 0,
            'total_key_presses': aggregations['total_key_presses'] or 0,
        }

    @staticmethod
    def get_trends(base_qs: QuerySet) -> List[Dict[str, Any]]:
        """
        Calculates daily trends for productivity metrics.
        """
        daily_aggregations = base_qs.values('date').annotate(
            attendance_count=Count('id'),
            total_online_duration=Sum('productivity__online_duration'),
            total_active_duration=Sum('productivity__active_duration'),
            total_idle_duration=Sum('productivity__idle_duration'),
            total_productive_duration=Sum('productivity__productive_duration'),
            average_active_percent=Avg('productivity__active_percent'),
            total_break_duration=Sum('total_break_duration')
        ).order_by('date')

        results = []
        for agg in daily_aggregations:
            results.append({
                'date': agg['date'],
                'attendance_count': agg['attendance_count'],
                'total_online_duration': agg['total_online_duration'] or timedelta(0),
                'total_active_duration': agg['total_active_duration'] or timedelta(0),
                'total_idle_duration': agg['total_idle_duration'] or timedelta(0),
                'total_productive_duration': agg['total_productive_duration'] or timedelta(0),
                'total_break_duration': agg['total_break_duration'] or timedelta(0),
                'average_active_percent': float(agg['average_active_percent']) if agg['average_active_percent'] is not None else 0.0,
            })
        return results

    @staticmethod
    def get_team_breakdown(base_qs: QuerySet) -> List[Dict[str, Any]]:
        """
        Groups metrics by team to provide a team-level comparison breakdown.
        """
        team_aggregations = base_qs.filter(employee__team__isnull=False).values(
            'employee__team_id', 'employee__team__name'
        ).annotate(
            attendance_count=Count('id'),
            total_active_duration=Sum('productivity__active_duration'),
            total_idle_duration=Sum('productivity__idle_duration'),
            total_productive_duration=Sum('productivity__productive_duration'),
            average_active_percent=Avg('productivity__active_percent'),
        ).order_by('employee__team__name')

        results = []
        for agg in team_aggregations:
            results.append({
                'team_id': agg['employee__team_id'],
                'team_name': agg['employee__team__name'],
                'attendance_count': agg['attendance_count'],
                'total_active_duration': agg['total_active_duration'] or timedelta(0),
                'total_idle_duration': agg['total_idle_duration'] or timedelta(0),
                'total_productive_duration': agg['total_productive_duration'] or timedelta(0),
                'average_active_percent': float(agg['average_active_percent']) if agg['average_active_percent'] is not None else 0.0,
            })
        return results

    @staticmethod
    def get_employee_breakdown(base_qs: QuerySet) -> List[Dict[str, Any]]:
        """
        Groups metrics by employee for a detailed breakdown.
        """
        employee_aggregations = base_qs.values(
            'employee_id', 
            'employee__user__first_name', 
            'employee__user__last_name'
        ).annotate(
            attendance_count=Count('id'),
            total_online_duration=Sum('productivity__online_duration'),
            total_active_duration=Sum('productivity__active_duration'),
            total_idle_duration=Sum('productivity__idle_duration'),
            total_productive_duration=Sum('productivity__productive_duration'),
            total_unproductive_duration=Sum('productivity__unproductive_duration'),
            average_active_percent=Avg('productivity__active_percent'),
        ).order_by('employee__user__first_name', 'employee__user__last_name')

        results = []
        for agg in employee_aggregations:
            first_name = agg.get('employee__user__first_name') or ''
            last_name = agg.get('employee__user__last_name') or ''
            full_name = f"{first_name} {last_name}".strip()
            
            results.append({
                'employee_id': agg['employee_id'],
                'employee_name': full_name,
                'attendance_count': agg['attendance_count'],
                'total_online_duration': agg['total_online_duration'] or timedelta(0),
                'total_active_duration': agg['total_active_duration'] or timedelta(0),
                'total_idle_duration': agg['total_idle_duration'] or timedelta(0),
                'total_productive_duration': agg['total_productive_duration'] or timedelta(0),
                'total_unproductive_duration': agg['total_unproductive_duration'] or timedelta(0),
                'average_active_percent': float(agg['average_active_percent']) if agg['average_active_percent'] is not None else 0.0,
            })
        return results
