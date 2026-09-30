from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from apps.authorization.permissions import require_permission
from apps.audit.services import AuditService
from .models import BreakType
from .serializers import BreakTypeSerializer

class BreakTypeViewSet(viewsets.ModelViewSet):
    serializer_class = BreakTypeSerializer
    def get_permissions(self):
        return [IsAuthenticated(), require_permission('shift.view' if self.action in ['list','retrieve'] else 'shift.manage')()]
    def get_queryset(self):
        u=self.request.user
        if u.is_superuser:return BreakType.objects.all()
        e=getattr(u,'employee',None)
        return BreakType.objects.filter(organization=e.organization) if e and e.organization_id else BreakType.objects.none()
    def perform_create(self,serializer):
        e=getattr(self.request.user,'employee',None); org=e.organization if e else None
        if self.request.user.is_superuser: org=serializer.validated_data.get('organization')
        item=serializer.save(organization=org); AuditService.log('break_type_created',self.request.user,'break_type',item.id,request=self.request,organization=org)
