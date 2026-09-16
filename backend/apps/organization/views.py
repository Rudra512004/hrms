from rest_framework import viewsets, status
from rest_framework.response import Response
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError
from .models import OfficeNetwork, Organization, Department, Designation, Branch, Team
from .serializers import OfficeNetworkSerializer, OrganizationSerializer, DepartmentSerializer, DesignationSerializer, BranchSerializer, WorkingCalendarSerializer, OrganizationSetupSerializer, TeamSerializer
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

        from apps.authorization.services import AuthorizationService
        authorized_branches = AuthorizationService.get_authorized_branches(user, 'organization.update')
        return WorkingCalendar.objects.filter(branch__in=authorized_branches)

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, 'is_superuser', False):
            pass
        else:
            # Creation is typically via signals, but if explicit, we would need a branch_id.
            # Usually handled automatically or via BranchViewSet.
            pass

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
            branch_id = self.request.query_params.get('branch')
            if branch_id:
                qs = qs.filter(branch_id=branch_id)
            return qs

        from apps.authorization.services import AuthorizationService
        
        # Determine accessible branches via authorization service
        permission = 'department.view' if self.action in ['list', 'retrieve'] else 'department.manage'
        authorized_branches = AuthorizationService.get_authorized_branches(user, permission)
        
        qs = Department.objects.filter(branch__in=authorized_branches)
        branch_id = self.request.query_params.get('branch')
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        return qs

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('department.view')
        else:
            permission = require_permission('department.manage')
        return [IsAuthenticated(), permission()]

    def perform_create(self, serializer):
        user = self.request.user
        branch_id = self.request.data.get('branch')
        if not branch_id:
            raise ValidationError({"branch": "Branch ID is required."})

        try:
            branch = Branch.objects.get(id=branch_id)
        except Branch.DoesNotExist:
            raise ValidationError({"branch": "Specified branch does not exist."})

        from apps.authorization.services import AuthorizationService
        if not user.is_superuser:
            authorized_branches = AuthorizationService.get_authorized_branches(user, 'department.manage')
            if branch not in authorized_branches:
                raise ValidationError({"branch": "You do not have permission to create a department in this branch."})

        try:
            serializer.save(branch=branch)
        except IntegrityError:
            raise ValidationError({"name": "A department with this name already exists in this branch."})

class TeamViewSet(viewsets.ModelViewSet):
    serializer_class = TeamSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            qs = Team.objects.all()
            dept_id = self.request.query_params.get('department')
            if dept_id:
                qs = qs.filter(department_id=dept_id)
            return qs
        from apps.authorization.services import AuthorizationService
        permission = 'team.view' if self.action in ['list', 'retrieve'] else 'team.manage'
        authorized_branches = AuthorizationService.get_authorized_branches(user, permission)
        
        qs = Team.objects.filter(department__branch__in=authorized_branches)
        dept_id = self.request.query_params.get('department')
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        return qs

    def destroy(self, request, *args, **kwargs):
        team = self.get_object()
        active_employees = team.employees.exclude(employment_status__in=['inactive', 'exited'])
        if active_employees.exists():
            return Response(
                {"detail": "Cannot delete team while active employees are assigned to it."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('team.view')
        else:
            permission = require_permission('team.manage')
        return [IsAuthenticated(), permission()]

    def perform_create(self, serializer):
        user = self.request.user
        dept_id = self.request.data.get('department')
        if not dept_id:
            raise ValidationError({"department": "Department ID is required."})

        try:
            dept = Department.objects.get(id=dept_id)
        except Department.DoesNotExist:
            raise ValidationError({"department": "Specified department does not exist."})

        from apps.authorization.services import AuthorizationService
        if not user.is_superuser:
            authorized_branches = AuthorizationService.get_authorized_branches(user, 'team.manage')
            if dept.branch not in authorized_branches:
                raise ValidationError({"department": "You do not have permission to create a team in this department's branch."})

        try:
            serializer.save(department=dept)
        except IntegrityError:
            raise ValidationError({"name": "A team with this name already exists in this department."})


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
            branch_id = self.request.query_params.get('branch')
            if branch_id:
                qs = qs.filter(branch_id=branch_id)
            return qs

        from apps.authorization.services import AuthorizationService
        if self.action in ['list', 'retrieve']:
            authorized_branches = AuthorizationService.get_authorized_branches(user, 'office_network.view')
        else:
            authorized_branches = AuthorizationService.get_authorized_branches(user, 'office_network.manage')

        return OfficeNetwork.objects.filter(branch__in=authorized_branches)

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
        branch_id = self.request.data.get('branch')

        if not branch_id:
            raise ValidationError({"branch": "Branch ID is required."})

        try:
            branch = Branch.objects.get(id=branch_id)
        except Branch.DoesNotExist:
            raise ValidationError({"branch": "Specified branch does not exist."})

        if not user.is_superuser:
            from apps.authorization.services import AuthorizationService
            authorized_branches = AuthorizationService.get_authorized_branches(user, 'office_network.create')
            if branch not in authorized_branches:
                raise ValidationError({"branch": "Cannot create resources for a branch you do not have permission for."})

        try:
            serializer.save(branch=branch)
        except IntegrityError:
            raise ValidationError({"network": "This network is already configured for this branch."})


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
