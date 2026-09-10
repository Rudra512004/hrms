from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import AssetCategory, Asset, AssetAssignment, AssetStatus
from .serializers import (
    AssetCategorySerializer,
    AssetListSerializer,
    AssetDetailSerializer,
    AssetCreateUpdateSerializer,
    AssetAssignSerializer,
    AssetReturnSerializer,
    AssetAssignmentSerializer,
)
from apps.authorization.services import AuthorizationService
from apps.audit.services import AuditService
from apps.notifications.services import NotificationService
from apps.employees.models import Employee, EmploymentStatus


class AssetCategoryViewSet(viewsets.ModelViewSet):
    """
    CRUD for asset categories.
    Protected by dynamic RBAC: asset.view, asset.create, asset.update, asset.delete.
    """
    serializer_class = AssetCategorySerializer

    def _get_org_id(self, user):
        if user.is_superuser:
            return None
        if hasattr(user, 'employee') and user.employee.organization_id:
            return user.employee.organization_id
        return -1

    def get_queryset(self):
        org_id = self._get_org_id(self.request.user)
        if org_id is None:
            return AssetCategory.objects.all().order_by('name')
        if org_id == -1:
            return AssetCategory.objects.none()
        return AssetCategory.objects.filter(organization_id=org_id).order_by('name')

    def list(self, request, *args, **kwargs):
        if not (AuthorizationService.has_permission(request.user, 'asset.view') or request.user.is_superuser):
            return Response({'detail': 'Permission denied: asset.view required.'}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not (AuthorizationService.has_permission(request.user, 'asset.view') or request.user.is_superuser):
            return Response({'detail': 'Permission denied: asset.view required.'}, status=status.HTTP_403_FORBIDDEN)
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not (AuthorizationService.has_permission(request.user, 'asset.create') or request.user.is_superuser):
            return Response({'detail': 'Permission denied: asset.create required.'}, status=status.HTTP_403_FORBIDDEN)

        org_id = self._get_org_id(request.user)
        if org_id is None:
            # Superuser without employee record - fallback to target org from payload if present
            org_id = request.data.get('organization')

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save(organization_id=org_id)
        return Response(self.get_serializer(category).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        if not (AuthorizationService.has_permission(request.user, 'asset.update') or request.user.is_superuser):
            return Response({'detail': 'Permission denied: asset.update required.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not (AuthorizationService.has_permission(request.user, 'asset.delete') or request.user.is_superuser):
            return Response({'detail': 'Permission denied: asset.delete required.'}, status=status.HTTP_403_FORBIDDEN)
        category = self.get_object()
        if category.assets.exists():
            return Response(
                {'detail': 'Cannot delete category that contains existing assets.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class AssetViewSet(viewsets.ModelViewSet):
    """
    Manages physical and digital assets, allocations, and returns.
    """

    def _get_org_id(self, user):
        if user.is_superuser:
            return None
        if hasattr(user, 'employee') and user.employee.organization_id:
            return user.employee.organization_id
        return -1

    def get_queryset(self):
        org_id = self._get_org_id(self.request.user)
        if org_id is None:
            qs = Asset.objects.all()
        elif org_id == -1:
            return Asset.objects.none()
        else:
            qs = Asset.objects.filter(organization_id=org_id)

        # Filters
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category_id=category)

        asset_status = self.request.query_params.get('status')
        if asset_status:
            qs = qs.filter(status=asset_status)

        branch = self.request.query_params.get('branch')
        if branch:
            qs = qs.filter(branch_id=branch)

        employee_id = self.request.query_params.get('employee')
        if employee_id:
            qs = qs.filter(assignments__employee_id=employee_id, assignments__is_active=True)

        search = self.request.query_params.get('search')
        if search:
            search = search.strip()
            qs = qs.filter(
                Q(asset_tag__icontains=search) |
                Q(name__icontains=search) |
                Q(serial_number__icontains=search) |
                Q(model_number__icontains=search)
            )

        return qs.select_related('category', 'branch', 'organization').prefetch_related(
            'assignments__employee__user'
        ).order_by('-created_at')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AssetCreateUpdateSerializer
        if self.action == 'retrieve':
            return AssetDetailSerializer
        return AssetListSerializer

    def list(self, request, *args, **kwargs):
        if not (AuthorizationService.has_permission(request.user, 'asset.view') or request.user.is_superuser):
            return Response({'detail': 'Permission denied: asset.view required.'}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        # Allow retrieve if user has asset.view or is assigned to this asset
        instance = self.get_object()
        is_assigned = (
            hasattr(request.user, 'employee') and
            instance.assignments.filter(employee=request.user.employee, is_active=True).exists()
        )
        if not (is_assigned or AuthorizationService.has_permission(request.user, 'asset.view') or request.user.is_superuser):
            return Response({'detail': 'Permission denied: asset.view required.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        if not (AuthorizationService.has_permission(request.user, 'asset.create') or request.user.is_superuser):
            return Response({'detail': 'Permission denied: asset.create required.'}, status=status.HTTP_403_FORBIDDEN)

        org_id = self._get_org_id(request.user)
        if org_id is None:
            org_id = request.data.get('organization')

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = serializer.save(organization_id=org_id)

        AuditService.log(
            action='asset_created',
            actor=request.user,
            target_type='asset',
            target_id=asset.id,
            metadata={
                'asset_tag': asset.asset_tag,
                'name': asset.name,
                'category_id': asset.category_id,
            },
            request=request,
        )

        return Response(AssetDetailSerializer(asset).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        if not (AuthorizationService.has_permission(request.user, 'asset.update') or request.user.is_superuser):
            return Response({'detail': 'Permission denied: asset.update required.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not (AuthorizationService.has_permission(request.user, 'asset.delete') or request.user.is_superuser):
            return Response({'detail': 'Permission denied: asset.delete required.'}, status=status.HTTP_403_FORBIDDEN)

        asset = self.get_object()
        if asset.status == AssetStatus.ASSIGNED or asset.assignments.filter(is_active=True).exists():
            return Response(
                {'detail': 'Cannot delete an asset that is currently assigned to an employee.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        asset_id = asset.id
        asset_tag = asset.asset_tag
        name = asset.name

        asset.delete()

        AuditService.log(
            action='asset_deleted',
            actor=request.user,
            target_type='asset',
            target_id=asset_id,
            metadata={'asset_tag': asset_tag, 'name': name},
            request=request,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """
        Assign an available asset to an active employee.
        Requires dynamic RBAC permission: asset.assign
        """
        if not (AuthorizationService.has_permission(request.user, 'asset.assign') or request.user.is_superuser):
            return Response({'detail': 'Permission denied: asset.assign required.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = AssetAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.validated_data['employee']

        # Atomic transaction + row lock to guarantee state invariants under concurrency
        with transaction.atomic():
            org_id = self._get_org_id(request.user)
            lock_qs = Asset.objects.select_for_update()
            if org_id is not None:
                if org_id == -1:
                    return Response(status=status.HTTP_404_NOT_FOUND)
                lock_qs = lock_qs.filter(organization_id=org_id)

            try:
                asset = lock_qs.get(pk=pk)
            except Asset.DoesNotExist:
                return Response(status=status.HTTP_404_NOT_FOUND)

            # Check organization alignment
            if asset.organization_id != employee.organization_id:
                return Response(
                    {'detail': 'Cannot assign asset to an employee in a different organization.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check status
            if asset.status != AssetStatus.AVAILABLE:
                return Response(
                    {'detail': f'Asset is not available for assignment (current status: {asset.status}).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check active assignment invariant
            if AssetAssignment.objects.select_for_update().filter(asset_id=asset.id, is_active=True).exists():
                return Response(
                    {'detail': 'Asset already has an active assignment.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create assignment
            assignment = AssetAssignment.objects.create(
                asset=asset,
                employee=employee,
                allocated_at=request.data.get('allocated_at') or timezone.now().date(),
                expected_return_date=serializer.validated_data.get('expected_return_date'),
                condition_at_allocation=serializer.validated_data.get('condition_at_allocation', 'good'),
                allocation_notes=serializer.validated_data.get('allocation_notes', ''),
                assigned_by=request.user,
                is_active=True,
            )

            # Transition asset status
            asset.status = AssetStatus.ASSIGNED
            asset.save(update_fields=['status', 'updated_at'])

            transaction.on_commit(lambda e=employee, a=asset, assign=assignment: NotificationService.create_in_app_notification(
                recipient=e.user,
                organization=e.organization,
                notification_type='ASSET_ASSIGNED',
                title='Asset Assigned',
                message=f'The asset {a.name} ({a.asset_tag}) has been assigned to you.',
                reference_id=str(assign.id)
            ))

            AuditService.log(
                action='asset_assigned',
                actor=request.user,
                target_type='asset',
                target_id=asset.id,
                metadata={
                    'asset_tag': asset.asset_tag,
                    'assignment_id': assignment.id,
                    'employee_id': employee.id,
                    'employee_code': employee.employee_code,
                },
                request=request,
            )

        return Response(AssetAssignmentSerializer(assignment).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='return')
    def return_asset(self, request, pk=None):
        """
        Return an assigned asset from an employee.
        Requires dynamic RBAC permission: asset.assign
        """
        if not (AuthorizationService.has_permission(request.user, 'asset.assign') or request.user.is_superuser):
            return Response({'detail': 'Permission denied: asset.assign required.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = AssetReturnSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        next_status = serializer.validated_data['next_status']
        condition_at_return = serializer.validated_data['condition_at_return']
        return_notes = serializer.validated_data['return_notes']
        return_date = serializer.validated_data['return_date']

        with transaction.atomic():
            org_id = self._get_org_id(request.user)
            lock_qs = Asset.objects.select_for_update()
            if org_id is not None:
                if org_id == -1:
                    return Response(status=status.HTTP_404_NOT_FOUND)
                lock_qs = lock_qs.filter(organization_id=org_id)

            try:
                asset = lock_qs.get(pk=pk)
            except Asset.DoesNotExist:
                return Response(status=status.HTTP_404_NOT_FOUND)

            active_assignment = AssetAssignment.objects.select_for_update().filter(asset_id=asset.id, is_active=True).first()
            if not active_assignment:
                return Response(
                    {'detail': 'Asset does not have an active assignment to return.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Close active assignment
            active_assignment.is_active = False
            active_assignment.returned_at = return_date
            active_assignment.condition_at_return = condition_at_return
            active_assignment.return_notes = return_notes
            active_assignment.save(update_fields=['is_active', 'returned_at', 'condition_at_return', 'return_notes', 'updated_at'])

            # Transition asset status
            asset.status = next_status
            asset.save(update_fields=['status', 'updated_at'])

            transaction.on_commit(lambda emp=active_assignment.employee, a=asset, assign=active_assignment: NotificationService.create_in_app_notification(
                recipient=emp.user,
                organization=emp.organization,
                notification_type='ASSET_RETURNED',
                title='Asset Returned',
                message=f'Your return of asset {a.name} ({a.asset_tag}) has been processed.',
                reference_id=str(assign.id)
            ))

            AuditService.log(
                action='asset_returned',
                actor=request.user,
                target_type='asset',
                target_id=asset.id,
                metadata={
                    'asset_tag': asset.asset_tag,
                    'assignment_id': active_assignment.id,
                    'employee_id': active_assignment.employee_id,
                    'next_status': next_status,
                    'condition_at_return': condition_at_return,
                },
                request=request,
            )

        return Response(AssetDetailSerializer(asset).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='my-assets')
    def my_assets(self, request):
        """
        Employee self-service: View assets currently assigned to the authenticated user.
        No administrative permissions required.
        """
        if not hasattr(request.user, 'employee'):
            return Response([])

        assignments = AssetAssignment.objects.filter(
            employee=request.user.employee,
            is_active=True,
        ).select_related('asset__category', 'asset__branch', 'employee__user')

        serializer = AssetAssignmentSerializer(assignments, many=True)
        return Response(serializer.data)
