from rest_framework import viewsets
from .models import OfficeNetwork
from .serializers import OfficeNetworkSerializer
from apps.authorization.permissions import require_permission

class OfficeNetworkViewSet(viewsets.ModelViewSet):
    queryset = OfficeNetwork.objects.all()
    serializer_class = OfficeNetworkSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('office_network.view')
        elif self.action == 'create':
            permission = require_permission('office_network.create')
        elif self.action in ['update', 'partial_update']:
            permission = require_permission('office_network.update')
        elif self.action == 'destroy':
            permission = require_permission('office_network.delete')
        else:
            permission = require_permission('office_network.view')
        return [permission()]
