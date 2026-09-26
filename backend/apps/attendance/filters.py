import django_filters
from .models import Attendance, Holiday

class AttendanceFilter(django_filters.FilterSet):
    branch_id = django_filters.NumberFilter(field_name='employee__branch_id')
    team_id = django_filters.NumberFilter(field_name='employee__team_id')
    date = django_filters.DateFilter(field_name='date')

    class Meta:
        model = Attendance
        fields = ['branch_id', 'team_id', 'date']


class HolidayFilter(django_filters.FilterSet):
    branch_id = django_filters.NumberFilter(field_name='branch_id')

    class Meta:
        model = Holiday
        fields = ['branch_id']
