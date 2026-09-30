from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import AuditService
from apps.authorization.services import AuthorizationService

from .models import SalaryComponent, SalaryStructure, SalaryStructureComponent
from .serializers import (
    SalaryComponentSerializer,
    SalaryStructureComponentSerializer,
    SalaryStructureSerializer,
)
from .views import _employee_org


class PayrollConfigurationPermissionMixin:
    permission_classes = [IsAuthenticated]

    def _can_manage(self, request):
        return AuthorizationService.has_permission(request.user, 'payroll.manage_compensation')

    def _forbidden(self):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)


class SalaryComponentViewSet(PayrollConfigurationPermissionMixin, viewsets.ModelViewSet):
    serializer_class = SalaryComponentSerializer

    def get_queryset(self):
        org = _employee_org(self.request)
        if not org:
            return SalaryComponent.objects.none()
        return SalaryComponent.objects.filter(organization=org).order_by('kind', 'name')

    def create(self, request, *args, **kwargs):
        if not self._can_manage(request):
            return self._forbidden()
        org = _employee_org(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        component = serializer.save(organization=org)
        AuditService.log('salary_component_created', request.user, 'salary_component', component.id, request=request)
        return Response(self.get_serializer(component).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        if not self._can_manage(request):
            return self._forbidden()
        response = super().update(request, *args, **kwargs)
        AuditService.log('salary_component_updated', request.user, 'salary_component', kwargs['pk'], request=request)
        return response

    def destroy(self, request, *args, **kwargs):
        if not self._can_manage(request):
            return self._forbidden()
        component = self.get_object()
        if component.salarystructurecomponent_set.exists():
            return Response(
                {'detail': 'This component is used by a salary structure. Deactivate it instead.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        component_id = component.id
        component.delete()
        AuditService.log('salary_component_deleted', request.user, 'salary_component', component_id, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SalaryStructureViewSet(PayrollConfigurationPermissionMixin, viewsets.ModelViewSet):
    serializer_class = SalaryStructureSerializer

    def get_queryset(self):
        org = _employee_org(self.request)
        if not org:
            return SalaryStructure.objects.none()
        return SalaryStructure.objects.filter(organization=org).prefetch_related('components__component').order_by('name')

    def create(self, request, *args, **kwargs):
        if not self._can_manage(request):
            return self._forbidden()
        org = _employee_org(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        structure = serializer.save(organization=org)
        AuditService.log('salary_structure_created', request.user, 'salary_structure', structure.id, request=request)
        return Response(self.get_serializer(structure).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        if not self._can_manage(request):
            return self._forbidden()
        response = super().update(request, *args, **kwargs)
        AuditService.log('salary_structure_updated', request.user, 'salary_structure', kwargs['pk'], request=request)
        return response

    def destroy(self, request, *args, **kwargs):
        if not self._can_manage(request):
            return self._forbidden()
        structure = self.get_object()
        structure_id = structure.id
        structure.delete()
        AuditService.log('salary_structure_deleted', request.user, 'salary_structure', structure_id, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='components')
    def set_component(self, request, pk=None):
        if not self._can_manage(request):
            return self._forbidden()
        structure = self.get_object()
        serializer = SalaryStructureComponentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        component = serializer.validated_data['component']
        if component.organization_id != structure.organization_id:
            return Response({'component': 'Choose a component from this organization.'}, status=status.HTTP_400_BAD_REQUEST)
        row, _ = SalaryStructureComponent.objects.update_or_create(
            structure=structure,
            component=component,
            defaults={'amount': serializer.validated_data['amount']},
        )
        AuditService.log('salary_structure_component_set', request.user, 'salary_structure', structure.id, request=request)
        return Response(SalaryStructureComponentSerializer(row).data)

    @action(detail=True, methods=['delete'], url_path=r'components/(?P<component_id>[^/.]+)')
    def remove_component(self, request, pk=None, component_id=None):
        if not self._can_manage(request):
            return self._forbidden()
        structure = self.get_object()
        deleted, _ = SalaryStructureComponent.objects.filter(
            structure=structure, component_id=component_id,
        ).delete()
        if not deleted:
            return Response({'detail': 'Component is not assigned to this structure.'}, status=status.HTTP_404_NOT_FOUND)
        AuditService.log('salary_structure_component_removed', request.user, 'salary_structure', structure.id, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)
