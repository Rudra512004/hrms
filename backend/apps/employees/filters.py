import django_filters
from .models import Employee

class EmployeeFilter(django_filters.FilterSet):
    branch_id = django_filters.NumberFilter(field_name='branch_id')
    status = django_filters.CharFilter(field_name='user__status')

    class Meta:
        model = Employee
        fields = ['branch_id', 'status']
