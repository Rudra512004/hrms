from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import AlertRule, EmployeeAlertPreference, AlertInstance
from .serializers import AlertRuleSerializer, EmployeeAlertPreferenceSerializer, AlertInstanceSerializer
from apps.authorization.services import AuthorizationService
from apps.employees.models import Employee

class AlertRuleViewSet(viewsets.ModelViewSet):
    serializer_class = AlertRuleSerializer
    
    def get_queryset(self):
        user = self.request.user
        org = AuthorizationService.get_primary_organization(user)
        if not org:
            return AlertRule.objects.none()
        return AlertRule.objects.filter(organization=org)

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method in permissions.SAFE_METHODS:
            if not AuthorizationService.has_permission(request.user, 'work_health_alert.view_rules', global_only=True):
                self.permission_denied(request, message="Missing work_health_alert.view_rules permission")
        else:
            if not AuthorizationService.has_permission(request.user, 'work_health_alert.manage_rules', global_only=True):
                self.permission_denied(request, message="Missing work_health_alert.manage_rules permission")

    def perform_create(self, serializer):
        org = AuthorizationService.get_primary_organization(self.request.user)
        serializer.save(organization=org)

class EmployeeAlertPreferenceViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeAlertPreferenceSerializer
    
    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, 'employee'):
            return EmployeeAlertPreference.objects.none()
        return EmployeeAlertPreference.objects.filter(employee=user.employee)

    def check_permissions(self, request):
        super().check_permissions(request)
        # Any employee can view/manage their OWN preferences
        if not hasattr(request.user, 'employee'):
            self.permission_denied(request, message="Must be an employee to manage preferences.")

    def perform_create(self, serializer):
        serializer.save(employee=self.request.user.employee)

class AlertInstanceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AlertInstanceSerializer
    
    def get_queryset(self):
        user = self.request.user
        org = AuthorizationService.get_primary_organization(user)
        if not org:
            return AlertInstance.objects.none()

        # Employee viewing their own alerts
        if 'own' in self.request.query_params:
            if hasattr(user, 'employee'):
                return AlertInstance.objects.filter(employee=user.employee).select_related('rule', 'employee__user')
            return AlertInstance.objects.none()

        # Manager viewing team alerts
        if not AuthorizationService.has_permission(user, 'work_health_alert.view'):
            return AlertInstance.objects.none()

        authorized_teams = AuthorizationService.get_authorized_teams(user, 'work_health_alert.view')
        authorized_branches = AuthorizationService.get_authorized_branches(user, 'work_health_alert.view')
        
        from django.db.models import Q
        q = Q()
        if authorized_teams.exists():
            q |= Q(employee__team__in=authorized_teams)
        if authorized_branches.exists():
            q |= Q(employee__branch__in=authorized_branches)
            
        return AlertInstance.objects.filter(Q(rule__organization=org) & q).select_related('rule', 'employee__user')

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        instance = self.get_object()
        
        # Verify access context. Either employee acknowledging own, or manager acknowledging team's
        user = request.user
        can_ack = False
        
        if hasattr(user, 'employee') and instance.employee_id == user.employee.id:
            can_ack = True
        elif AuthorizationService.has_permission(user, 'work_health_alert.manage'):
            auth_teams = AuthorizationService.get_authorized_teams(user, 'work_health_alert.manage')
            auth_branches = AuthorizationService.get_authorized_branches(user, 'work_health_alert.manage')
            if instance.employee.team_id in auth_teams.values_list('id', flat=True) or \
               instance.employee.branch_id in auth_branches.values_list('id', flat=True):
                can_ack = True
                
        if not can_ack:
            self.permission_denied(request, message="You do not have permission to acknowledge this alert.")

        if instance.status != 'acknowledged':
            instance.status = 'acknowledged'
            instance.acknowledged_at = timezone.now()
            instance.save(update_fields=['status', 'acknowledged_at'])
            
        return Response(self.get_serializer(instance).data)
