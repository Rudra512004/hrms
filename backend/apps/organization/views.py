from rest_framework import viewsets
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError
from .models import OfficeNetwork, Organization, Department, Designation, Branch
from .serializers import OfficeNetworkSerializer, OrganizationSerializer, DepartmentSerializer, DesignationSerializer, BranchSerializer, WorkingCalendarSerializer, OrganizationSetupSerializer
from apps.authorization.permissions import require_permission, IsNetworkAllowed
from rest_framework.permissions import IsAuthenticated


def _get_request_user_org(request):
    """
    Resolve the organization of the requesting user.
    Checks:
    1. Employee profile organization
    2. Active user role organization
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return None
    if hasattr(user, 'employee') and user.employee and user.employee.organization_id:
        return user.employee.organization
    user_role = user.user_roles.filter(
        is_revoked=False, role__organization__isnull=False
    ).select_related('role__organization').first()
    if user_role and user_role.role.organization:
        return user_role.role.organization
    return None


class OrganizationSetupViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSetupSerializer
    from apps.authorization.permissions import IsSuperAdmin
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    queryset = Organization.objects.all()

class WorkingCalendarViewSet(viewsets.ModelViewSet):
    serializer_class = WorkingCalendarSerializer
    permission_classes = [IsAuthenticated, IsNetworkAllowed, require_permission('organization.update')]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'is_superuser', False):
            return WorkingCalendar.objects.all()
        employee = getattr(user, 'employee', None)
        if employee:
            return WorkingCalendar.objects.filter(organization=employee.organization)
        return WorkingCalendar.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, 'is_superuser', False):
            # Admin can create for any org, handled by serializer?
            # Actually we usually don't allow explicit creation since it's OneToOne and auto-created.
            pass
        employee = getattr(user, 'employee', None)
        if employee:
            serializer.save(organization=employee.organization)

class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Organization.objects.all()
        org = _get_request_user_org(self.request)
        if org:
            return Organization.objects.filter(id=org.id)
        return Organization.objects.none()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('organization.view')
        else:
            permission = require_permission('organization.manage')
        return [IsAuthenticated(), permission()]


class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            qs = Department.objects.all()
            org_id = self.request.query_params.get('organization')
            if org_id:
                qs = qs.filter(organization_id=org_id)
            return qs
        org = _get_request_user_org(self.request)
        if org:
            return Department.objects.filter(organization_id=org.id)
        return Department.objects.none()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('department.view')
        else:
            permission = require_permission('department.manage')
        return [IsAuthenticated(), permission()]

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser:
            org_id = self.request.data.get('organization')
            if org_id:
                try:
                    org = Organization.objects.get(id=org_id)
                except Organization.DoesNotExist:
                    raise ValidationError({"organization": "Specified organization does not exist."})
            else:
                org = _get_request_user_org(self.request) or Organization.objects.first()
        else:
            org = _get_request_user_org(self.request)
            if not org:
                raise ValidationError({"organization": "User does not belong to an organization."})
            req_org_id = self.request.data.get('organization')
            if req_org_id:
                try:
                    if int(req_org_id) != org.id:
                        raise ValidationError({"organization": "Cannot create resources for another organization."})
                except (ValueError, TypeError):
                    raise ValidationError({"organization": "Invalid organization ID."})

        try:
            serializer.save(organization=org)
        except IntegrityError:
            raise ValidationError({"name": "A department with this name already exists in this organization."})


class DesignationViewSet(viewsets.ModelViewSet):
    serializer_class = DesignationSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            qs = Designation.objects.all()
            org_id = self.request.query_params.get('organization')
            if org_id:
                qs = qs.filter(organization_id=org_id)
            return qs
        org = _get_request_user_org(self.request)
        if org:
            return Designation.objects.filter(organization_id=org.id)
        return Designation.objects.none()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('designation.view')
        else:
            permission = require_permission('designation.manage')
        return [IsAuthenticated(), permission()]

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser:
            org_id = self.request.data.get('organization')
            if org_id:
                try:
                    org = Organization.objects.get(id=org_id)
                except Organization.DoesNotExist:
                    raise ValidationError({"organization": "Specified organization does not exist."})
            else:
                org = _get_request_user_org(self.request) or Organization.objects.first()
        else:
            org = _get_request_user_org(self.request)
            if not org:
                raise ValidationError({"organization": "User does not belong to an organization."})
            req_org_id = self.request.data.get('organization')
            if req_org_id:
                try:
                    if int(req_org_id) != org.id:
                        raise ValidationError({"organization": "Cannot create resources for another organization."})
                except (ValueError, TypeError):
                    raise ValidationError({"organization": "Invalid organization ID."})

        try:
            serializer.save(organization=org)
        except IntegrityError:
            raise ValidationError({"name": "A designation with this name already exists in this organization."})


class OfficeNetworkViewSet(viewsets.ModelViewSet):
    serializer_class = OfficeNetworkSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            qs = OfficeNetwork.objects.all()
            org_id = self.request.query_params.get('organization')
            if org_id:
                qs = qs.filter(organization_id=org_id)
            return qs
        org = _get_request_user_org(self.request)
        if org:
            return OfficeNetwork.objects.filter(organization_id=org.id)
        return OfficeNetwork.objects.none()

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

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser:
            org_id = self.request.data.get('organization')
            if org_id:
                try:
                    org = Organization.objects.get(id=org_id)
                except Organization.DoesNotExist:
                    raise ValidationError({"organization": "Specified organization does not exist."})
            else:
                org = _get_request_user_org(self.request) or Organization.objects.first()
        else:
            org = _get_request_user_org(self.request)
            if not org:
                raise ValidationError({"organization": "User does not belong to an organization."})
            req_org_id = self.request.data.get('organization')
            if req_org_id:
                try:
                    if int(req_org_id) != org.id:
                        raise ValidationError({"organization": "Cannot create resources for another organization."})
                except (ValueError, TypeError):
                    raise ValidationError({"organization": "Invalid organization ID."})

        try:
            serializer.save(organization=org)
        except IntegrityError:
            raise ValidationError({"network": "This network is already configured for this organization."})


class BranchViewSet(viewsets.ModelViewSet):
    serializer_class = BranchSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            qs = Branch.objects.all()
            org_id = self.request.query_params.get('organization')
            if org_id:
                qs = qs.filter(organization_id=org_id)
            return qs
        org = _get_request_user_org(self.request)
        if org:
            return Branch.objects.filter(organization_id=org.id)
        return Branch.objects.none()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('branch.view')
        else:
            permission = require_permission('branch.manage')
        return [IsAuthenticated(), permission()]

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser:
            org_id = self.request.data.get('organization')
            if org_id:
                try:
                    org = Organization.objects.get(id=org_id)
                except Organization.DoesNotExist:
                    raise ValidationError({"organization": "Specified organization does not exist."})
            else:
                org = _get_request_user_org(self.request) or Organization.objects.first()
        else:
            org = _get_request_user_org(self.request)
            if not org:
                raise ValidationError({"organization": "User does not belong to an organization."})
            req_org_id = self.request.data.get('organization')
            if req_org_id:
                try:
                    if int(req_org_id) != org.id:
                        raise ValidationError({"organization": "Cannot create resources for another organization."})
                except (ValueError, TypeError):
                    raise ValidationError({"organization": "Invalid organization ID."})

        try:
            serializer.save(organization=org)
        except IntegrityError:
            raise ValidationError({"name": "A branch with this name already exists in this organization."})
