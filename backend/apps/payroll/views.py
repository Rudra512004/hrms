from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone

from apps.authorization.services import AuthorizationService
from apps.audit.services import AuditService

from .models import CompensationHistory, PayrollPeriod, PayrollRecord
from .serializers import (
    CompensationHistorySerializer,
    PayrollPeriodSerializer,
    PayrollRecordSerializer,
)
from .services import generate_payroll_for_period


def _require(user, codename):
    """Returns None if permitted, else a 403 Response."""
    if not AuthorizationService.has_permission(user, codename):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    return None


def _employee_org(request):
    """Return the organization of the requesting user's employee profile."""
    try:
        return request.user.employee.organization
    except Exception:
        return None


class CompensationHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only listing of salary history per employee.
    Creation is handled via dedicated POST to avoid accidental overwrites.
    """
    serializer_class = CompensationHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = _employee_org(self.request)
        if org is None:
            return CompensationHistory.objects.none()
        qs = CompensationHistory.objects.filter(
            employee__organization=org
        ).select_related('employee', 'created_by')

        emp_id = self.request.query_params.get('employee')
        if emp_id:
            qs = qs.filter(employee_id=emp_id)
        return qs

    def list(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.view_sensitive')
        if err:
            return err
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.view_sensitive')
        if err:
            return err
        return super().retrieve(request, *args, **kwargs)

    @action(detail=False, methods=['post'], url_path='set')
    def set_compensation(self, request):
        """Create or update salary. Closes the current open record first."""
        err = _require(request.user, 'payroll.manage_compensation')
        if err:
            return err

        from apps.employees.models import Employee
        org = _employee_org(request)
        employee_id = request.data.get('employee')

        try:
            employee = Employee.objects.get(id=employee_id, organization=org)
        except Employee.DoesNotExist:
            return Response({'detail': 'Employee not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CompensationHistorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        effective_from = serializer.validated_data['effective_from']

        with transaction.atomic():
            # Close any open record that started before the new effective_from
            CompensationHistory.objects.filter(
                employee=employee,
                effective_to__isnull=True,
                effective_from__lt=effective_from,
            ).update(effective_to=effective_from)

            record = CompensationHistory.objects.create(
                employee=employee,
                effective_from=effective_from,
                effective_to=serializer.validated_data.get('effective_to'),
                basic_salary=serializer.validated_data['basic_salary'],
                created_by=request.user,
            )

        AuditService.log(
            action='compensation_set',
            actor=request.user,
            target_type='compensation_history',
            target_id=record.id,
            request=request,
        )
        return Response(CompensationHistorySerializer(record).data, status=status.HTTP_201_CREATED)


class PayrollPeriodViewSet(viewsets.ModelViewSet):
    serializer_class = PayrollPeriodSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']  # No PATCH/DELETE

    def get_queryset(self):
        org = _employee_org(self.request)
        if org is None:
            return PayrollPeriod.objects.none()
        return PayrollPeriod.objects.filter(organization=org).select_related(
            'organization', 'approved_by'
        )

    def list(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.view')
        if err:
            return err
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.view')
        if err:
            return err
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.generate')
        if err:
            return err

        org = _employee_org(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Pre-flight uniqueness check to avoid an unhandled IntegrityError
        if PayrollPeriod.objects.filter(
            organization=org,
            year=serializer.validated_data['year'],
            month=serializer.validated_data['month'],
        ).exists():
            return Response(
                {'detail': 'A payroll period for this organization/year/month already exists.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            period = serializer.save(organization=org)

        AuditService.log(
            action='payroll_period_created',
            actor=request.user,
            target_type='payroll_period',
            target_id=period.id,
            request=request,
        )
        return Response(self.get_serializer(period).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        err = _require(request.user, 'payroll.generate')
        if err:
            return err

        period = self.get_object()

        if period.status == PayrollPeriod.STATUS_APPROVED:
            return Response(
                {'detail': 'Cannot re-generate an approved payroll period.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                records = generate_payroll_for_period(period, requesting_user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        AuditService.log(
            action='payroll_generated',
            actor=request.user,
            target_type='payroll_period',
            target_id=period.id,
            request=request,
        )
        return Response(
            {'detail': f'Generated {len(records)} payroll record(s).'},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        err = _require(request.user, 'payroll.approve')
        if err:
            return err

        period = self.get_object()

        if period.status == PayrollPeriod.STATUS_APPROVED:
            return Response({'detail': 'Period is already approved.'}, status=status.HTTP_400_BAD_REQUEST)

        if not period.records.exists():
            return Response({'detail': 'Generate payroll before approving.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            period.status = PayrollPeriod.STATUS_APPROVED
            period.approved_by = request.user
            period.approved_at = timezone.now()
            period.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

            # Lock all draft records
            period.records.filter(status=PayrollRecord.STATUS_DRAFT).update(
                status=PayrollRecord.STATUS_APPROVED
            )

        AuditService.log(
            action='payroll_approved',
            actor=request.user,
            target_type='payroll_period',
            target_id=period.id,
            request=request,
        )
        return Response(self.get_serializer(period).data, status=status.HTTP_200_OK)


class PayrollRecordViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PayrollRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = _employee_org(self.request)
        if org is None:
            return PayrollRecord.objects.none()
        qs = PayrollRecord.objects.filter(
            period__organization=org
        ).select_related('period', 'employee', 'employee__user')

        period_id = self.request.query_params.get('period')
        if period_id:
            qs = qs.filter(period_id=period_id)

        emp_id = self.request.query_params.get('employee')
        if emp_id:
            qs = qs.filter(employee_id=emp_id)

        return qs

    def list(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.view')
        if err:
            return err
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.view')
        if err:
            return err
        return super().retrieve(request, *args, **kwargs)
