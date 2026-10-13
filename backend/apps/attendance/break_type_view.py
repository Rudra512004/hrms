from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from apps.authorization.permissions import require_permission
from apps.authorization.services import AuthorizationService
from apps.audit.services import AuditService
from .models import BreakType
from .serializers import BreakTypeSerializer

class BreakTypeViewSet(viewsets.ModelViewSet):
    serializer_class = BreakTypeSerializer
    def get_permissions(self):
        return [IsAuthenticated(), require_permission('shift.view' if self.action in ['list','retrieve'] else 'shift.manage')()]
    def _get_user_organization(self):
        """Resolve the requesting user's organization.  Never returns a
        cross-tenant fallback — raises PermissionDenied when the
        organization cannot be determined."""
        org = AuthorizationService.get_primary_organization(self.request.user)
        if org is None:
            raise PermissionDenied(
                'Cannot determine organization context for the current user.'
            )
        return org
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self._get_user_organization()
    def get_queryset(self):
        org = self._get_user_organization()
        return BreakType.objects.filter(organization=org)
    def perform_create(self, serializer):
        org = self._get_user_organization()
        item = serializer.save(organization=org)
        AuditService.log(
            'break_type_created', self.request.user, 'break_type', item.id,
            request=self.request, organization=org,
        )
    def perform_update(self, serializer):
        org = self._get_user_organization()
        item = serializer.save()
        AuditService.log(
            'break_type_updated', self.request.user, 'break_type', item.id,
            request=self.request, organization=org,
        )

