from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError
from .models import OfficeNetwork, Organization, Department, Designation, Branch, Team, WorkingCalendar
from .services import OrganizationReadinessService
from .serializers import OfficeNetworkSerializer, OrganizationSerializer, DepartmentSerializer, DesignationSerializer, BranchSerializer, WorkingCalendarSerializer, OrganizationSetupSerializer, TeamSerializer, AttendancePolicySerializer
from apps.authorization.permissions import require_permission, IsNetworkAllowed
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from apps.audit.services import AuditService


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
    from apps.authorization.services import AuthorizationService
    return AuthorizationService.get_primary_organization(user)


class OrganizationConfigurationAuditMixin:
    """Adds a privacy-safe audit event for organization configuration changes."""
    audit_resource = ''

    def _audit_organization(self, instance):
        if isinstance(instance, Organization):
            return instance
        if hasattr(instance, 'organization_id'):
            return instance.organization
        if hasattr(instance, 'branch_id'):
            return instance.branch.organization
        if hasattr(instance, 'department_id'):
            return instance.department.branch.organization
        return None

    def _audit(self, action, instance, metadata=None):
        AuditService.log(
            action=action,
            actor=self.request.user,
            target_type=self.audit_resource,
            target_id=instance.pk,
            metadata=metadata or {},
            request=self.request,
            organization=self._audit_organization(instance),
        )

    def perform_update(self, serializer):
        changed_fields = sorted(serializer.validated_data.keys())
        instance = serializer.save()
        self._audit(f'{self.audit_resource}_updated', instance, {'fields': changed_fields})

    def perform_destroy(self, instance):
        self._audit(f'{self.audit_resource}_deleted', instance)
        instance.delete()


class OrganizationSetupViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSetupSerializer
    from apps.authorization.permissions import IsSuperAdmin
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    queryset = Organization.objects.all()

    def perform_create(self, serializer):
        organization = serializer.save()
        AuditService.log(
            action='organization_launched',
            actor=self.request.user,
            target_type='organization',
            target_id=organization.pk,
            # Deliberately avoid address, network, and policy details in audit metadata.
            metadata={'branch_count': organization.branches.count()},
            request=self.request,
            organization=organization,
        )


class TenantOrganizationSetupView(APIView):
    """Launch exactly one organization for a verified, self-service owner."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        registration = getattr(request.user, 'tenant_owner_registration', None)
        if not registration or not registration.can_launch_organization:
            raise ValidationError({'detail': 'This verified account cannot create another organization.'})

        serializer = OrganizationSetupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            organization = serializer.save()
            from apps.authorization.models import Permission, Role, RolePermission, ScopeChoices, UserRole
            owner_role = Role.objects.create(
                organization=organization,
                name='Organization Owner',
                description='Full administrative access within this organization only.',
            )
            RolePermission.objects.bulk_create([
                RolePermission(role=owner_role, permission=permission)
                for permission in Permission.objects.filter(is_active=True)
            ])
            UserRole.objects.create(
                user=request.user,
                role=owner_role,
                assigned_by=request.user,
                scope=ScopeChoices.ORGANIZATION,
            )
            registration.organization = organization
            registration.save(update_fields=['organization'])

        AuditService.log(
            action='tenant_organization_launched', actor=request.user, target_type='organization',
            target_id=organization.pk, metadata={'branch_count': organization.branches.count()},
            request=request, organization=organization,
        )
        return Response(OrganizationSerializer(organization).data, status=status.HTTP_201_CREATED)

class WorkingCalendarViewSet(OrganizationConfigurationAuditMixin, viewsets.ModelViewSet):
    serializer_class = WorkingCalendarSerializer
    audit_resource = 'working_calendar'
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

class OrganizationViewSet(OrganizationConfigurationAuditMixin, viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    audit_resource = 'organization'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Organization.objects.all()
        org = _get_request_user_org(self.request)
        if org:
            return Organization.objects.filter(id=org.id)
        return Organization.objects.none()

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'readiness']:
            permission = require_permission('organization.view')
        else:
            permission = require_permission('organization.manage')
        return [IsAuthenticated(), permission()]

    def perform_create(self, serializer):
        if not self.request.user.is_superuser:
            # Organizations are tenant boundaries. Client accounts can only
            # create their one tenant through the verified self-setup flow.
            raise ValidationError({'detail': 'Use the verified organization launch flow to create a tenant.'})
        organization = serializer.save()
        self._audit('organization_created', organization)

    @action(detail=True, methods=['get'])
    def readiness(self, request, pk=None):
        organization = self.get_object()
        return Response(OrganizationReadinessService.assess(organization))


class DepartmentViewSet(OrganizationConfigurationAuditMixin, viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer
    audit_resource = 'department'

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
            department = serializer.save(branch=branch)
            self._audit('department_created', department)
        except IntegrityError:
            raise ValidationError({"name": "A department with this name already exists in this branch."})

class TeamViewSet(OrganizationConfigurationAuditMixin, viewsets.ModelViewSet):
    serializer_class = TeamSerializer
    audit_resource = 'team'

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
        qs = AuthorizationService.get_authorized_teams(user, permission)
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
            team = serializer.save(department=dept)
            self._audit('team_created', team)
        except IntegrityError:
            raise ValidationError({"name": "A team with this name already exists in this department."})


class DesignationViewSet(OrganizationConfigurationAuditMixin, viewsets.ModelViewSet):
    serializer_class = DesignationSerializer
    audit_resource = 'designation'

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
                org = _get_request_user_org(self.request)
                if not org:
                    raise ValidationError({"organization": "Organization context is required."})
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
            designation = serializer.save(organization=org)
            self._audit('designation_created', designation)
        except IntegrityError:
            raise ValidationError({"name": "A designation with this name already exists in this organization."})


class OfficeNetworkViewSet(OrganizationConfigurationAuditMixin, viewsets.ModelViewSet):
    serializer_class = OfficeNetworkSerializer
    audit_resource = 'office_network'

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
            network = serializer.save(branch=branch)
            self._audit('office_network_created', network)
        except IntegrityError:
            raise ValidationError({"network": "This network is already configured for this branch."})


class BranchViewSet(OrganizationConfigurationAuditMixin, viewsets.ModelViewSet):
    serializer_class = BranchSerializer
    audit_resource = 'branch'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            qs = Branch.objects.all()
            org_id = self.request.query_params.get('organization')
            if org_id:
                qs = qs.filter(organization_id=org_id)
            return qs

        from apps.authorization.services import AuthorizationService
        is_read = self.action in ['list', 'retrieve'] or (self.action == 'attendance_policy' and getattr(self.request, 'method', None) == 'GET')
        permission = 'branch.view' if is_read else 'branch.manage'
        qs = AuthorizationService.get_authorized_branches(user, permission)
        org_id = self.request.query_params.get('organization')
        if org_id:
            qs = qs.filter(organization_id=org_id)
        return qs

    def get_permissions(self):
        is_read = self.action in ['list', 'retrieve'] or (self.action == 'attendance_policy' and getattr(self.request, 'method', None) == 'GET')
        if is_read:
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
                org = _get_request_user_org(self.request)
                if not org:
                    raise ValidationError({"organization": "Organization context is required."})
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
            branch = serializer.save(organization=org)
            self._audit('branch_created', branch)
        except IntegrityError:
            raise ValidationError({"name": "A branch with this name already exists in this organization."})

    @action(detail=True, methods=['get', 'put', 'patch'], url_path='attendance-policy')
    def attendance_policy(self, request, pk=None):
        branch = self.get_object()
        from .models import AttendancePolicy
        policy, _ = AttendancePolicy.objects.get_or_create(branch=branch)

        if request.method == 'GET':
            serializer = AttendancePolicySerializer(policy)
            return Response(serializer.data)

        # Write actions require branch.manage on this branch
        user = request.user
        if not user.is_superuser:
            from apps.authorization.services import AuthorizationService
            if not AuthorizationService.has_permission(user, 'branch.manage', branch.id):
                return Response(
                    {'detail': 'You do not have permission to manage attendance policy for this branch.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        serializer = AttendancePolicySerializer(policy, data=request.data, partial=(request.method == 'PATCH'))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        AuditService.log(
            action='attendance_policy_updated',
            actor=request.user,
            target_type='attendance_policy',
            target_id=policy.pk,
            metadata={'fields': sorted(serializer.validated_data.keys()), 'branch_id': branch.pk},
            request=request,
            organization=branch.organization,
        )
        return Response(serializer.data)
