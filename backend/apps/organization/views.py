from rest_framework import viewsets
from .models import OfficeNetwork, Organization, Department, Designation, Branch
from .serializers import OfficeNetworkSerializer, OrganizationSerializer, DepartmentSerializer, DesignationSerializer, BranchSerializer
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

class BranchViewSet(viewsets.ModelViewSet):
    serializer_class = BranchSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Branch.objects.all()
        if hasattr(user, 'employee') and user.employee.organization_id:
            return Branch.objects.filter(organization_id=user.employee.organization_id)
        return Branch.objects.none()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('branch.view')
        else:
            permission = require_permission('branch.manage')
        return [IsAuthenticated(), permission()]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        
        if self.request.user.is_superuser and not hasattr(self.request.user, 'employee'):
            org = Organization.objects.first()
        else:
            org = self.request.user.employee.organization

        if not org:
            raise ValidationError({"organization": "User does not belong to an organization."})

        serializer.save(organization=org)
