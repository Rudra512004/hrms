from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAuthenticated
from .models import AuditLog
from .serializers import AuditLogSerializer
from apps.authorization.permissions import IsNetworkAllowed, require_permission
from apps.authorization.services import AuthorizationService

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.all()

    def get_permissions(self):
        return [IsAuthenticated(), IsNetworkAllowed(), require_permission('audit.view')()]

    def get_queryset(self):
        queryset = super().get_queryset()
        
        actor = self.request.query_params.get('actor')
        if actor:
            queryset = queryset.filter(actor__email=actor)
            
        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)
            
        target = self.request.query_params.get('target')
        if target:
            queryset = queryset.filter(target_id=target)
            
        return queryset
