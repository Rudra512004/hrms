from rest_framework import viewsets
from .models import OfficeNetwork, Organization, Department, Designation
from .serializers import OfficeNetworkSerializer, OrganizationSerializer, DepartmentSerializer, DesignationSerializer
from apps.authorization.permissions import require_permission, IsNetworkAllowed
from rest_framework.permissions import IsAuthenticated

class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('organization.view')
        else:
            permission = require_permission('organization.manage')
        return [IsAuthenticated(), permission()]

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('department.view')
        else:
            permission = require_permission('department.manage')
        return [IsAuthenticated(), permission()]

class DesignationViewSet(viewsets.ModelViewSet):
    queryset = Designation.objects.all()
    serializer_class = DesignationSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('designation.view')
        else:
            permission = require_permission('designation.manage')
        return [IsAuthenticated(), permission()]

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
        return [IsAuthenticated(), permission()]
