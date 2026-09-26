import django_filters
from .models import LeaveRequest

class LeaveRequestFilter(django_filters.FilterSet):
    organization_id = django_filters.NumberFilter(field_name='employee__organization_id')
    branch_id = django_filters.NumberFilter(field_name='employee__branch_id')
    employee_id = django_filters.NumberFilter(field_name='employee_id')
    status = django_filters.CharFilter(field_name='status')
    start_date = django_filters.DateFilter(field_name='start_date', lookup_expr='gte')
    end_date = django_filters.DateFilter(field_name='end_date', lookup_expr='lte')

    class Meta:
        model = LeaveRequest
        fields = ['organization_id', 'branch_id', 'employee_id', 'status', 'start_date', 'end_date']
