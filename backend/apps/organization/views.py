from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError
from .models import OfficeNetwork, Organization, Department, Designation, Branch, Team, WorkingCalendar
from .services import OrganizationReadinessService, OrganizationOnboardingService
from .serializers import (
    OfficeNetworkSerializer, OrganizationSerializer, DepartmentSerializer,
    DesignationSerializer, BranchSerializer, WorkingCalendarSerializer,
    OrganizationSetupSerializer, TeamSerializer, AttendancePolicySerializer,
    TenantBrandingAndConfigSerializer, OnboardingStage1Serializer,
    OnboardingStage2Serializer, OnboardingStage3Serializer,
    OnboardingStage4Serializer, OnboardingStage5Serializer,
    OnboardingStage6Serializer, OnboardingDraftSerializer,
    OrganizationOnboardingSerializer, OrganizationInvitationSerializer,
    OrganizationInvitationAcceptSerializer,
)
from apps.authorization.permissions import require_permission, IsNetworkAllowed
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
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
        with transaction.atomic():
            organization = serializer.save()
            from apps.authorization.models import Permission, Role, RolePermission, ScopeChoices, UserRole
            
            # Super Admins are headless. To manage this organization, they need an explicit role within it.
            owner_role = Role.objects.create(
                organization=organization,
                name='Organization Owner (Super Admin)',
                description='Full administrative access within this organization only.',
            )
            RolePermission.objects.bulk_create([
                RolePermission(role=owner_role, permission=permission)
                for permission in Permission.objects.filter(is_active=True)
            ])
            UserRole.objects.create(
                user=self.request.user,
                role=owner_role,
                assigned_by=self.request.user,
                scope=ScopeChoices.ORGANIZATION,
            )
            
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

        from apps.authorization.services import AuthorizationService
        authorized_branches = AuthorizationService.get_authorized_branches(user, 'organization.update')
        return WorkingCalendar.objects.filter(branch__in=authorized_branches)

    def perform_create(self, serializer):
        pass

class OrganizationViewSet(OrganizationConfigurationAuditMixin, viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    audit_resource = 'organization'

    def get_queryset(self):
        org = _get_request_user_org(self.request)
        if org:
            return Organization.objects.filter(id=org.id)
        return Organization.objects.none()

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'readiness', 'org_chart']:
            permission = require_permission('organization.view')
        elif self.action in ['branding', 'branding_logo']:
            if self.request.method in ['GET', 'HEAD']:
                permission = require_permission('organization.view')
            else:
                permission = require_permission('branding.manage')
        else:
            permission = require_permission('organization.manage')
        return [IsAuthenticated(), permission()]

    def perform_create(self, serializer):
        # Organizations are tenant boundaries. Client accounts can only
        # create their one tenant through the verified self-setup flow.
        raise ValidationError({'detail': 'Use the verified organization launch flow to create a tenant.'})
        organization = serializer.save()
        self._audit('organization_created', organization)

    @action(detail=True, methods=['get'])
    def readiness(self, request, pk=None):
        organization = self.get_object()
        return Response(OrganizationReadinessService.assess(organization))

    @action(detail=True, methods=['get', 'patch'])
    def branding(self, request, pk=None):
        """
        Manage Tenant Branding and Theme Configuration.
        Auto-creates the config record if it somehow doesn't exist.
        """
        organization = self.get_object()
        from .models import TenantBrandingAndConfig
        branding_config, _ = TenantBrandingAndConfig.objects.get_or_create(
            organization=organization
        )

        if request.method == 'GET':
            serializer = TenantBrandingAndConfigSerializer(branding_config)
            return Response(serializer.data)

        # PATCH
        serializer = TenantBrandingAndConfigSerializer(
            branding_config, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        updated_config = serializer.save()
        self._audit('tenant_branding_updated', organization, {'fields': list(request.data.keys())})
        return Response(serializer.data)

    @action(detail=True, methods=['post', 'delete'], url_path='branding/logo')
    def branding_logo(self, request, pk=None):
        """
        Upload, replace, or remove organization logo file.
        On upload, validates image integrity, extracts dominant colors,
        and generates coordinated color palettes.
        """
        organization = self.get_object()
        from .models import TenantBrandingAndConfig
        from .branding_service import OrganizationBrandingService
        from PIL import Image

        branding_config, _ = TenantBrandingAndConfig.objects.get_or_create(
            organization=organization
        )

        if request.method == 'DELETE':
            if branding_config.logo_file:
                branding_config.logo_file.delete(save=False)
            branding_config.logo_file = None
            branding_config.logo_url = ''
            branding_config.save(update_fields=['logo_file', 'logo_url', 'updated_at'])
            self._audit('organization_logo_removed', organization)
            return Response(TenantBrandingAndConfigSerializer(branding_config).data, status=status.HTTP_200_OK)

        # POST upload
        upload_file = request.FILES.get('file') or request.FILES.get('logo')
        if not upload_file:
            raise ValidationError({'file': ['No logo image file was provided in the upload request.']})

        # Size check (2MB max)
        if upload_file.size > 2 * 1024 * 1024:
            raise ValidationError({'file': ['Logo file size must not exceed 2 MB.']})

        # Content validation via Pillow
        try:
            img = Image.open(upload_file)
            img.verify()
            upload_file.seek(0)
            img = Image.open(upload_file)
        except Exception:
            raise ValidationError({'file': ['Uploaded file is not a valid or readable image.']})

        if img.format.upper() not in ['PNG', 'JPEG', 'JPG', 'WEBP']:
            raise ValidationError({'file': [f"Unsupported image format '{img.format}'. Allowed: PNG, JPEG, WEBP."]})

        if img.width > 2048 or img.height > 2048:
            raise ValidationError({'file': ['Logo dimensions must not exceed 2048x2048 pixels.']})

        if img.width < 16 or img.height < 16:
            raise ValidationError({'file': ['Logo dimensions must be at least 16x16 pixels.']})

        # Replace existing logo file safely
        if branding_config.logo_file:
            branding_config.logo_file.delete(save=False)

        branding_config.logo_file = upload_file
        branding_config.save()
        branding_config.refresh_from_db()

        # Build absolute URL
        if branding_config.logo_file:
            branding_config.logo_url = request.build_absolute_uri(branding_config.logo_file.url)

        # Extract dominant colors and generate palette suggestions
        upload_file.seek(0)
        dominant_colors = OrganizationBrandingService.extract_dominant_colors(upload_file)
        palettes = OrganizationBrandingService.generate_coordinated_palettes(dominant_colors[0])
        branding_config.palette_suggestions = palettes

        # If custom mode is active and no colors have been set yet, initialize with the first palette.
        # Otherwise, preserve existing theme colors and manual overrides (do not silently replace active theme).
        if branding_config.branding_mode == 'custom' and not branding_config.primary_color:
            branding_config.selected_palette = palettes[0]['id']
            branding_config.primary_color = palettes[0]['primary_color']
            branding_config.secondary_color = palettes[0]['secondary_color']
            branding_config.accent_color = palettes[0]['accent_color']
            branding_config.sidebar_bg_color = palettes[0]['sidebar_bg_color']

        branding_config.save(update_fields=[
            'logo_url', 'palette_suggestions', 'selected_palette',
            'primary_color', 'secondary_color', 'accent_color', 'sidebar_bg_color', 'updated_at'
        ])

        self._audit('organization_logo_uploaded', organization, {'logo_url': branding_config.logo_url})
        return Response(TenantBrandingAndConfigSerializer(branding_config).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='org-chart')
    def org_chart(self, request, pk=None):
        organization = self.get_object()
        from apps.employees.models import Employee
        # Fetch all active employees
        employees = Employee.objects.filter(
            organization=organization,
            employment_status__in=['onboarding', 'active', 'probation', 'notice_period']
        ).select_related('designation', 'department')

        # Build hierarchical representation
        nodes = {}
        for emp in employees:
            nodes[emp.id] = {
                'id': emp.id,
                'name': f"{emp.user.first_name} {emp.user.last_name}".strip() or emp.user.email,
                'email': emp.user.email,
                'designation': emp.designation.name if emp.designation else None,
                'department': emp.department.name if emp.department else None,
                'headcount': 0, # To be computed
                'reporting_manager_id': emp.reporting_manager_id,
                'children': []
            }

        # Link children and compute direct headcount
        roots = []
        for emp_id, node in nodes.items():
            manager_id = node['reporting_manager_id']
            if manager_id and manager_id in nodes:
                nodes[manager_id]['children'].append(node)
                nodes[manager_id]['headcount'] += 1
            else:
                roots.append(node)
                
        # Recursive compute total headcount (subtree size)
        def compute_total_headcount(node):
            total = len(node['children'])
            for child in node['children']:
                total += compute_total_headcount(child)
            node['total_headcount'] = total
            return total

        for root in roots:
            compute_total_headcount(root)

        return Response(roots)



class DepartmentViewSet(OrganizationConfigurationAuditMixin, viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer
    audit_resource = 'department'

    def get_queryset(self):
        user = self.request.user

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


# =============================================================================
# Organization Setup Wizard Views (Phase 3C)
# =============================================================================

class OrganizationWizardBaseView(APIView):
    permission_classes = [IsAuthenticated]

    def get_onboarding(self, request):
        org_id = request.query_params.get('org_id')
        if org_id is None and request.data and isinstance(request.data, dict):
            org_id = request.data.get('organization_id') or request.data.get('org_id')

        onb = OrganizationOnboardingService.resolve_onboarding(request.user, org_id=org_id)
        if not onb:
            raise ValidationError({'detail': 'No active onboarding session found for this user.'})
        return onb


class OrganizationWizardStartView(APIView):
    """
    POST /api/v1/organization/wizard/start/
    Initialize onboarding session and execute Stage 1 (Organization Details).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = OnboardingStage1Serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        onboarding, org = OrganizationOnboardingService.execute_stage_1(
            user=request.user,
            validated_data=serializer.validated_data,
            request=request,
        )

        return Response({
            'onboarding_id': onboarding.id,
            'organization_id': org.id,
            'name': org.name,
            'code': org.code,
            'current_stage': onboarding.current_stage,
            'completed_stages': onboarding.completed_stages,
            'status': onboarding.status,
        }, status=status.HTTP_201_CREATED)


class OrganizationWizardStatusView(OrganizationWizardBaseView):
    """
    GET /api/v1/organization/wizard/status/
    Query current onboarding state, stage progress, and readiness summary.
    """
    def get(self, request, *args, **kwargs):
        onboarding = self.get_onboarding(request)
        return Response(OrganizationOnboardingService.get_status(onboarding), status=status.HTTP_200_OK)


class OrganizationWizardStageView(OrganizationWizardBaseView):
    """
    POST /api/v1/organization/wizard/stage/<int:stage_number>/
    Atomic submission and validation for discrete wizard stages.
    """
    def post(self, request, stage_number, *args, **kwargs):
        if stage_number < 1 or stage_number > 7:
            raise ValidationError({'stage': 'Stage number must be between 1 and 7.'})

        if stage_number == 1:
            serializer = OnboardingStage1Serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            onboarding, org = OrganizationOnboardingService.execute_stage_1(
                user=request.user, validated_data=serializer.validated_data, request=request
            )
            return Response(OrganizationOnboardingService.get_status(onboarding), status=status.HTTP_200_OK)

        onboarding = self.get_onboarding(request)

        if stage_number == 2:
            serializer = OnboardingStage2Serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            onboarding, branch = OrganizationOnboardingService.execute_stage_2(
                onboarding, request.user, serializer.validated_data, request=request
            )
        elif stage_number == 3:
            serializer = OnboardingStage3Serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            onboarding, depts, desigs = OrganizationOnboardingService.execute_stage_3(
                onboarding, request.user, serializer.validated_data, request=request
            )
        elif stage_number == 4:
            serializer = OnboardingStage4Serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            onboarding, wc = OrganizationOnboardingService.execute_stage_4(
                onboarding, request.user, serializer.validated_data, request=request
            )
        elif stage_number == 5:
            serializer = OnboardingStage5Serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            onboarding, shift = OrganizationOnboardingService.execute_stage_5(
                onboarding, request.user, serializer.validated_data, request=request
            )
        elif stage_number == 6:
            serializer = OnboardingStage6Serializer(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            onboarding, result = OrganizationOnboardingService.execute_stage_6(
                onboarding, request.user, serializer.validated_data, request=request
            )
        elif stage_number == 7:
            onboarding, readiness = OrganizationOnboardingService.execute_stage_7(
                onboarding, request.user, request=request
            )

        return Response(OrganizationOnboardingService.get_status(onboarding), status=status.HTTP_200_OK)


class OrganizationWizardStage2View(OrganizationWizardStageView):
    def post(self, request, *args, **kwargs):
        return super().post(request, 2, *args, **kwargs)


class OrganizationWizardStage3View(OrganizationWizardStageView):
    def post(self, request, *args, **kwargs):
        return super().post(request, 3, *args, **kwargs)


class OrganizationWizardStage4View(OrganizationWizardStageView):
    def post(self, request, *args, **kwargs):
        return super().post(request, 4, *args, **kwargs)


class OrganizationWizardStage5View(OrganizationWizardStageView):
    def post(self, request, *args, **kwargs):
        return super().post(request, 5, *args, **kwargs)


class OrganizationWizardStage6View(OrganizationWizardStageView):
    def post(self, request, *args, **kwargs):
        return super().post(request, 6, *args, **kwargs)


class OrganizationWizardCompleteView(OrganizationWizardBaseView):
    """
    POST /api/v1/organization/wizard/complete/
    Finalizes wizard setup, marks onboarding complete, activates organization, and returns readiness report.
    """
    def post(self, request, *args, **kwargs):
        onboarding = self.get_onboarding(request)
        onboarding, readiness = OrganizationOnboardingService.execute_stage_7(
            onboarding, request.user, request=request
        )
        return Response({
            'status': onboarding.status,
            'organization_id': onboarding.organization.id,
            'completed_at': onboarding.completed_at,
            'readiness_score': readiness.get('score', 0),
            'redirect_url': '/dashboard',
        }, status=status.HTTP_200_OK)


class OrganizationWizardDraftView(OrganizationWizardBaseView):
    """
    POST /api/v1/organization/wizard/draft/
    Saves non-sensitive draft metadata for a wizard step.
    """
    def post(self, request, *args, **kwargs):
        serializer = OnboardingDraftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        onboarding = self.get_onboarding(request)
        stage = serializer.validated_data['stage']
        data = serializer.validated_data['data']

        onboarding = OrganizationOnboardingService.save_draft(
            onboarding, request.user, stage, data, request=request
        )
        return Response({
            'detail': 'Draft saved successfully.',
            'stage': stage,
            'current_stage': onboarding.current_stage,
        }, status=status.HTTP_200_OK)


class OrganizationWizardReadinessView(OrganizationWizardBaseView):
    """
    GET /api/v1/organization/wizard/readiness/
    Retrieves the complete diagnostic readiness assessment.
    """
    def get(self, request, *args, **kwargs):
        onboarding = self.get_onboarding(request)
        return Response(OrganizationReadinessService.assess(onboarding.organization), status=status.HTTP_200_OK)


class OrganizationInvitationThrottle(AnonRateThrottle):
    rate = '15/minute'


class OrganizationInvitationAcceptThrottle(AnonRateThrottle):
    rate = '5/minute'


class OrganizationWizardStage6ResendView(OrganizationWizardBaseView):
    """
    POST /api/v1/organization/wizard/stage-6/resend/
    Resends an active pending administrator invitation and rotates the token.
    """
    throttle_classes = [UserRateThrottle]

    def post(self, request, *args, **kwargs):
        onboarding = self.get_onboarding(request)
        invitation = OrganizationOnboardingService.resend_stage_6_invitation(
            onboarding, request.user, request=request
        )
        return Response({
            'detail': 'Invitation resent successfully.',
            'invitation_id': invitation.id,
            'email': invitation.email,
            'status': invitation.status,
            'email_delivery_status': invitation.email_delivery_status,
            'resend_count': invitation.resend_count,
            'expires_at': invitation.expires_at.isoformat(),
        }, status=status.HTTP_200_OK)


class OrganizationWizardStage6RevokeView(OrganizationWizardBaseView):
    """
    POST /api/v1/organization/wizard/stage-6/revoke/
    Revokes an active pending administrator invitation.
    """
    throttle_classes = [UserRateThrottle]

    def post(self, request, *args, **kwargs):
        onboarding = self.get_onboarding(request)
        invitation = OrganizationOnboardingService.revoke_stage_6_invitation(
            onboarding, request.user, request=request
        )
        return Response({
            'detail': 'Invitation revoked successfully.',
            'invitation_id': invitation.id,
            'status': invitation.status,
        }, status=status.HTTP_200_OK)


class OrganizationInvitationVerifyView(APIView):
    """
    GET /api/v1/organization/invitations/verify/?token=<raw_token>
    Public rate-throttled endpoint validating an invitation token.
    Does NOT disclose whether arbitrary accounts exist.
    """
    permission_classes = [AllowAny]
    throttle_classes = [OrganizationInvitationThrottle]

    def get(self, request, *args, **kwargs):
        token = request.query_params.get('token')
        invitation = OrganizationOnboardingService.verify_invitation_token(token)
        return Response({
            'valid': True,
            'organization_name': invitation.organization.name,
            'organization_code': invitation.organization.code,
            'email': invitation.email,
            'first_name': invitation.first_name,
            'last_name': invitation.last_name,
            'expires_at': invitation.expires_at.isoformat(),
        }, status=status.HTTP_200_OK)


class OrganizationInvitationAcceptView(APIView):
    """
    POST /api/v1/organization/invitations/accept/
    Atomically accepts an invitation and provisions the organization Super Admin role.
    Active existing accounts must be pre-authenticated through canonical login.
    Invited or new accounts must provide a password meeting complexity standards.
    Zero DRF authentication tokens are returned from this view.
    """
    permission_classes = [AllowAny]
    throttle_classes = [OrganizationInvitationAcceptThrottle]

    def post(self, request, *args, **kwargs):
        serializer = OrganizationInvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']
        password = serializer.validated_data.get('password')
        first_name = serializer.validated_data.get('first_name', '')
        last_name = serializer.validated_data.get('last_name', '')

        invitation, target_user = OrganizationOnboardingService.accept_invitation(
            raw_token=token,
            authenticated_user=request.user if request.user.is_authenticated else None,
            password=password,
            first_name=first_name,
            last_name=last_name,
            request=request,
        )

        return Response({
            'detail': 'Invitation accepted successfully. Organization Super Admin role provisioned.',
            'organization_id': invitation.organization.id,
            'organization_name': invitation.organization.name,
            'role': invitation.role.slug,
            'status': invitation.status,
        }, status=status.HTTP_200_OK)


