from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse

from apps.authorization.services import AuthorizationService
from apps.audit.services import AuditService
from .pdf_service import generate_payslip_pdf

from .models import (
    CompensationHistory,
    PayrollPeriod,
    PayrollRecord,
    Payslip,
    OrganizationBankAccount,
    PaymentRoutingConfiguration,
    DisbursementBatch,
    DisbursementItem,
    FnFPolicyConfiguration,
    FinalSettlement,
    SettlementLine,
)
from .serializers import (
    CompensationHistorySerializer,
    PayrollPeriodSerializer,
    PayrollRecordSerializer,
    PayslipSummarySerializer,
    PayslipDetailSerializer,
    OrganizationBankAccountSerializer,
    PaymentRoutingConfigurationSerializer,
    DisbursementBatchListSerializer,
    DisbursementBatchDetailSerializer,
    PrepareDisbursementBatchSerializer,
    PrepareFnFDisbursementBatchSerializer,
    FnFPolicyConfigurationSerializer,
    FinalSettlementListSerializer,
    FinalSettlementDetailSerializer,
    EmployeeFinalSettlementSerializer,
    EmployeeSettlementLineSerializer,
    FnFPreviewRequestSerializer,
    FnFPrepareRequestSerializer,
    FnFCancelSerializer,
)
from apps.employees.models import Employee
from .services import generate_payroll_for_period, issue_payslips_for_period
from .fnf_service import FnFService, FnFException


def _require(user, codename):
    """Returns None if permitted, else a 403 Response."""
    if not AuthorizationService.has_permission(user, codename):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    return None


def _employee_org(request):
    """Return the organization of the requesting user's employee profile or fallback for superadmin."""
    from apps.authorization.services import AuthorizationService
    return AuthorizationService.get_primary_organization(request.user)


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
        if not org:
            return Response({'detail': 'Organization not found.'}, status=status.HTTP_400_BAD_REQUEST)
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
        if not org:
            return Response({'detail': 'User does not belong to an organization.'}, status=status.HTTP_400_BAD_REQUEST)

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

        if period.status != PayrollPeriod.STATUS_DRAFT:
            return Response(
                {'detail': 'Can only generate payroll for a draft period.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.payroll.workflow_service import PayrollWorkflowService, PayrollWorkflowException
        try:
            # Emulate the lock step for backward compatibility with frontend
            period.status = PayrollPeriod.STATUS_LOCKED
            period.save(update_fields=['status'])
            
            PayrollWorkflowService.process_period(period, request.user)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        records_count = period.records.count()
        response_data = {'detail': f'Generated {records_count} payroll record(s).'}

        today = timezone.localdate()
        if period.end_date > today:
            response_data['warning'] = (
                f'Payroll was generated before the period ends ({period.end_date}). '
                'Attendance data may be incomplete, resulting in zero or understated pay. '
                'Re-generate payroll after the period closes and attendance is finalised.'
            )

        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        err = _require(request.user, 'payroll.approve')
        if err:
            return err

        period = self.get_object()

        if period.status == PayrollPeriod.STATUS_FINALIZED:
            return Response({'detail': 'Period is already finalized.'}, status=status.HTTP_400_BAD_REQUEST)
            
        if period.status != PayrollPeriod.STATUS_REVIEW:
            return Response({'detail': 'Period must be generated (in review) before finalizing.'}, status=status.HTTP_400_BAD_REQUEST)

        if period.end_date >= timezone.now().date():
            return Response(
                {'detail': 'Cannot finalize an ongoing or future payroll period. The period end date has not passed.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from apps.payroll.workflow_service import PayrollWorkflowService, PayrollWorkflowException
        try:
            PayrollWorkflowService.finalize_period(period, request.user)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.get_serializer(period).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def disburse(self, request, pk=None):
        err = _require(request.user, 'payroll.approve') # Using approve permission for disburse
        if err:
            return err

        period = self.get_object()

        from apps.payroll.workflow_service import PayrollWorkflowService, PayrollWorkflowException
        try:
            PayrollWorkflowService.disburse_period(period, request.user)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.get_serializer(period).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='issue-payslips')
    def issue_payslips(self, request, pk=None):
        err = _require(request.user, 'payroll.approve')
        if err:
            err = _require(request.user, 'payroll.generate')
            if err:
                return err

        period = self.get_object()
        if period.status != PayrollPeriod.STATUS_FINALIZED:
            return Response(
                {'detail': 'Cannot issue payslips for an unfinalized period.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            payslips = issue_payslips_for_period(period, requesting_user=request.user)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'detail': f'Successfully issued {len(payslips)} payslip(s).',
                'count': len(payslips),
                'period_id': period.id,
            },
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='prepare-disbursement')
    def prepare_disbursement(self, request, pk=None):
        err = _require(request.user, 'payroll.disburse_prepare')
        if err:
            err = _require(request.user, 'payroll.disburse')
            if err:
                return err

        period = self.get_object()
        value_date = request.data.get('value_date')
        if not value_date:
            return Response({'detail': 'value_date is required (YYYY-MM-DD).'}, status=status.HTTP_400_BAD_REQUEST)

        narration = request.data.get('narration')
        debit_account_id = request.data.get('debit_account_id')
        debit_account = None
        if debit_account_id:
            debit_account = OrganizationBankAccount.objects.filter(
                id=debit_account_id, organization=period.organization
            ).first()
            if not debit_account:
                return Response({'detail': 'Debit account not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        from apps.payroll.disbursement_service import DisbursementService, DisbursementException
        try:
            batch = DisbursementService.prepare_disbursement_batch(
                period=period,
                user=request.user,
                value_date=value_date,
                narration=narration,
                debit_account=debit_account,
            )
        except DisbursementException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DisbursementBatchDetailSerializer(batch).data, status=status.HTTP_201_CREATED)





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


class PayslipViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ReadOnly endpoint for issued Payslips.
    - /my/: Returns the authenticated employee's own issued payslips.
    - /{id}/: Retrieves payslip detail (owner or authorized admin only).
    - /: Admin listing (requires payslip.view or payroll.view, scoped to user's org).
    """
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PayslipDetailSerializer
        return PayslipSummarySerializer

    def get_queryset(self):
        user = self.request.user
        org = _employee_org(self.request)
        if org is None:
            return Payslip.objects.none()

        base_qs = Payslip.objects.filter(
            payroll_record__period__organization=org,
            payroll_record__status=PayrollRecord.STATUS_FINALIZED,
            payroll_record__period__status=PayrollPeriod.STATUS_FINALIZED,
        ).select_related(
            'payroll_record',
            'payroll_record__period',
            'payroll_record__employee',
            'payroll_record__employee__user',
            'payroll_record__employee__department',
            'payroll_record__employee__designation',
        ).prefetch_related('lines')

        if self.action == 'my':
            if hasattr(user, 'employee') and user.employee:
                return base_qs.filter(payroll_record__employee=user.employee)
            return base_qs.filter(payroll_record__employee__user=user)

        if self.action in ['retrieve', 'pdf']:
            if (
                AuthorizationService.has_permission(user, 'payslip.view')
                or AuthorizationService.has_permission(user, 'payroll.view')
                or AuthorizationService.has_permission(user, 'payslip.download')
            ):
                return base_qs
            if hasattr(user, 'employee'):
                return base_qs.filter(payroll_record__employee=user.employee)
            return Payslip.objects.none()

        # For list (/), requires payslip.view or payroll.view
        if not (
            AuthorizationService.has_permission(user, 'payslip.view')
            or AuthorizationService.has_permission(user, 'payroll.view')
        ):
            return Payslip.objects.none()

        period_id = self.request.query_params.get('period')
        if period_id:
            base_qs = base_qs.filter(payroll_record__period_id=period_id)
        emp_id = self.request.query_params.get('employee')
        if emp_id:
            base_qs = base_qs.filter(payroll_record__employee_id=emp_id)

        return base_qs

    def list(self, request, *args, **kwargs):
        if not (
            AuthorizationService.has_permission(request.user, 'payslip.view')
            or AuthorizationService.has_permission(request.user, 'payroll.view')
        ):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='my')
    def my(self, request):
        """Returns the authenticated employee's issued payslips."""
        qs = self.get_queryset()
        serializer = PayslipSummarySerializer(qs, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        """Download server-side rendered PDF of the payslip."""
        payslip = self.get_object()
        user = request.user
        is_owner = False
        if hasattr(user, 'employee') and user.employee:
            is_owner = (user.employee.id == payslip.payroll_record.employee_id)

        has_admin_perm = (
            AuthorizationService.has_permission(user, 'payslip.download')
            or AuthorizationService.has_permission(user, 'payslip.view')
            or AuthorizationService.has_permission(user, 'payroll.view')
        )

        if not (is_owner or has_admin_perm):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        pdf_bytes = generate_payslip_pdf(payslip)

        AuditService.log(
            action='PAYSLIP_PDF_DOWNLOADED',
            actor=user,
            target_type='Payslip',
            target_id=payslip.id,
            organization=payslip.payroll_record.period.organization,
            request=request,
        )

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"Payslip_{payslip.payslip_number}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=False, methods=['post'], url_path='issue')
    def issue(self, request):
        """Administrative action to issue payslips for a finalized period."""
        err = _require(request.user, 'payroll.approve')
        if err:
            err = _require(request.user, 'payroll.generate')
            if err:
                return err

        period_id = request.data.get('period_id')
        if not period_id:
            return Response({'detail': 'period_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        org = _employee_org(request)
        period = PayrollPeriod.objects.filter(id=period_id, organization=org).first()
        if not period:
            return Response({'detail': 'Payroll period not found.'}, status=status.HTTP_404_NOT_FOUND)

        if period.status != PayrollPeriod.STATUS_FINALIZED:
            return Response({'detail': 'Cannot issue payslips for an unfinalized period.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payslips = issue_payslips_for_period(period, requesting_user=request.user)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'detail': f'Successfully issued {len(payslips)} payslip(s).',
                'count': len(payslips),
                'period_id': period.id,
            },
            status=status.HTTP_200_OK
        )


class PayslipVerificationView(APIView):
    """
    Public unauthenticated endpoint to verify payslip authenticity via cryptographic token.
    Exposes only safe, non-sensitive verification metadata (no salary/PAN/bank info).
    """
    permission_classes = [AllowAny]

    def get(self, request, token):
        payslip = Payslip.objects.filter(verification_token=token).select_related(
            'payroll_record', 'payroll_record__period', 'payroll_record__period__organization',
            'payroll_record__employee', 'payroll_record__employee__user'
        ).first()

        if not payslip or payslip.status != Payslip.STATUS_ISSUED:
            return Response(
                {
                    'valid': False,
                    'detail': 'Invalid or revoked verification token.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        emp = payslip.payroll_record.employee
        u = emp.user
        emp_name = payslip.employee_name or (f"{u.first_name} {u.last_name}".strip() or u.email)
        emp_code = payslip.employee_code or emp.employee_code
        org_name = payslip.organization_name or payslip.payroll_record.period.organization.name
        period_str = f"{payslip.period_year or payslip.payroll_record.period.year}/{payslip.period_month or payslip.payroll_record.period.month:02d}"

        return Response(
            {
                'valid': True,
                'payslip_number': payslip.payslip_number,
                'organization_name': org_name,
                'employee_name': emp_name,
                'employee_code': emp_code,
                'period': period_str,
                'issued_at': payslip.issued_at.isoformat() if payslip.issued_at else None,
                'status': payslip.status,
            },
            status=status.HTTP_200_OK
        )


class OrganizationBankAccountViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationBankAccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = _employee_org(self.request)
        if not org:
            return OrganizationBankAccount.objects.none()
        return OrganizationBankAccount.objects.filter(organization=org)

    def perform_create(self, serializer):
        org = _employee_org(self.request)
        serializer.save(organization=org)

    def list(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.view')
        if err:
            err = _require(request.user, 'payroll.disburse')
            if err:
                return err
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.view')
        if err:
            err = _require(request.user, 'payroll.disburse')
            if err:
                return err
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.disburse_configure')
        if err:
            return err
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.disburse_configure')
        if err:
            return err
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.disburse_configure')
        if err:
            return err
        return super().destroy(request, *args, **kwargs)


class PaymentRoutingConfigurationViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentRoutingConfigurationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = _employee_org(self.request)
        if not org:
            return PaymentRoutingConfiguration.objects.none()
        return PaymentRoutingConfiguration.objects.filter(organization=org)

    def perform_create(self, serializer):
        org = _employee_org(self.request)
        instance = serializer.save(organization=org, created_by=self.request.user)
        AuditService.log(
            action="DISBURSEMENT_ROUTING_CONFIG_CREATED",
            actor=self.request.user,
            target_type="PaymentRoutingConfiguration",
            target_id=str(instance.id),
            organization=org,
            metadata={
                'default_payment_mode': instance.default_payment_mode,
                'rtgs_enabled': instance.rtgs_enabled,
                'rtgs_threshold': str(instance.rtgs_threshold),
                'ift_enabled': instance.ift_enabled,
                'effective_from': instance.effective_from.isoformat() if instance.effective_from else None,
            }
        )

    def perform_update(self, serializer):
        instance = serializer.save(updated_by=self.request.user)
        AuditService.log(
            action="DISBURSEMENT_ROUTING_CONFIG_UPDATED",
            actor=self.request.user,
            target_type="PaymentRoutingConfiguration",
            target_id=str(instance.id),
            organization=instance.organization,
            metadata={
                'default_payment_mode': instance.default_payment_mode,
                'rtgs_enabled': instance.rtgs_enabled,
                'rtgs_threshold': str(instance.rtgs_threshold),
                'ift_enabled': instance.ift_enabled,
                'effective_from': instance.effective_from.isoformat() if instance.effective_from else None,
            }
        )

    def list(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.view')
        if err:
            err = _require(request.user, 'payroll.disburse')
            if err:
                return err
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.view')
        if err:
            err = _require(request.user, 'payroll.disburse')
            if err:
                return err
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.disburse_configure')
        if err:
            return err
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.disburse_configure')
        if err:
            return err
        return super().update(request, *args, **kwargs)


class DisbursementBatchViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DisbursementBatchDetailSerializer
        return DisbursementBatchListSerializer

    def get_queryset(self):
        org = _employee_org(self.request)
        if not org:
            return DisbursementBatch.objects.none()
        qs = DisbursementBatch.objects.filter(organization=org).select_related(
            'period', 'final_settlement', 'debit_account', 'created_by', 'approved_by', 'exported_by'
        )
        batch_type = self.request.query_params.get('batch_type')
        if batch_type:
            qs = qs.filter(batch_type=batch_type)
        period_id = self.request.query_params.get('period')
        if period_id:
            qs = qs.filter(period_id=period_id)
        settlement_id = self.request.query_params.get('final_settlement')
        if settlement_id:
            qs = qs.filter(final_settlement_id=settlement_id)
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def list(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.view')
        if err:
            err = _require(request.user, 'payroll.disburse')
            if err:
                return err
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        err = _require(request.user, 'payroll.view')
        if err:
            err = _require(request.user, 'payroll.disburse')
            if err:
                return err
        return super().retrieve(request, *args, **kwargs)

    @action(detail=False, methods=['post'], url_path='prepare')
    def prepare(self, request):
        err = _require(request.user, 'payroll.disburse_prepare')
        if err:
            err = _require(request.user, 'payroll.disburse')
            if err:
                return err

        serializer = PrepareDisbursementBatchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        org = _employee_org(request)
        if not org:
            return Response({'detail': 'No organization context.'}, status=status.HTTP_403_FORBIDDEN)

        debit_account = None
        if data.get('debit_account_id'):
            debit_account = OrganizationBankAccount.objects.filter(
                id=data['debit_account_id'], organization=org
            ).first()
            if not debit_account:
                return Response({'detail': 'Specified debit account not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        from apps.payroll.disbursement_service import DisbursementService, DisbursementException

        if data.get('period_id'):
            period = PayrollPeriod.objects.filter(id=data['period_id'], organization=org).first()
            if not period:
                return Response({'detail': 'Payroll period not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

            branch = None
            if data.get('branch_id'):
                from apps.organization.models import Branch
                branch = Branch.objects.filter(id=data['branch_id'], organization=org).first()

            try:
                batch = DisbursementService.prepare_disbursement_batch(
                    period=period,
                    user=request.user,
                    value_date=data['value_date'],
                    narration=data.get('narration'),
                    debit_account=debit_account,
                    branch=branch,
                )
            except DisbursementException as exc:
                return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as exc:
                return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            return Response(DisbursementBatchDetailSerializer(batch).data, status=status.HTTP_201_CREATED)

        elif data.get('final_settlement_id'):
            settlement = FinalSettlement.objects.filter(id=data['final_settlement_id'], organization=org).first()
            if not settlement:
                return Response({'detail': 'Final settlement not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

            try:
                batch = DisbursementService.prepare_fnf_disbursement_batch(
                    settlement=settlement,
                    user=request.user,
                    value_date=data['value_date'],
                    narration=data.get('narration'),
                    debit_account=debit_account,
                )
            except DisbursementException as exc:
                return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as exc:
                return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            return Response(DisbursementBatchDetailSerializer(batch).data, status=status.HTTP_201_CREATED)

        return Response({'detail': 'Invalid source.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='prepare-fnf')
    def prepare_fnf(self, request):
        err = _require(request.user, 'payroll.disburse_prepare')
        if err:
            err = _require(request.user, 'payroll.disburse')
            if err:
                return err

        serializer = PrepareFnFDisbursementBatchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        org = _employee_org(request)
        if not org:
            return Response({'detail': 'No organization context.'}, status=status.HTTP_403_FORBIDDEN)

        settlement = FinalSettlement.objects.filter(id=data['final_settlement_id'], organization=org).first()
        if not settlement:
            return Response({'detail': 'Final settlement not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        debit_account = None
        if data.get('debit_account_id'):
            debit_account = OrganizationBankAccount.objects.filter(
                id=data['debit_account_id'], organization=org
            ).first()
            if not debit_account:
                return Response({'detail': 'Specified debit account not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        from apps.payroll.disbursement_service import DisbursementService, DisbursementException
        try:
            batch = DisbursementService.prepare_fnf_disbursement_batch(
                settlement=settlement,
                user=request.user,
                value_date=data['value_date'],
                narration=data.get('narration'),
                debit_account=debit_account,
            )
        except DisbursementException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DisbursementBatchDetailSerializer(batch).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        err = _require(request.user, 'payroll.disburse_approve')
        if err:
            return err

        batch = self.get_object()
        from apps.payroll.disbursement_service import DisbursementService, DisbursementException
        try:
            approved_batch = DisbursementService.approve_disbursement_batch(batch, request.user)
        except DisbursementException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DisbursementBatchDetailSerializer(approved_batch).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='export-csv')
    def export_csv(self, request, pk=None):
        err = _require(request.user, 'payroll.disburse_export')
        if err:
            return err

        batch = self.get_object()
        from apps.payroll.disbursement_service import DisbursementService, DisbursementException
        try:
            csv_content = DisbursementService.export_disbursement_csv(batch, request.user)
        except DisbursementException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        filename = f"{batch.batch_number}.csv"
        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        err = _require(request.user, 'payroll.disburse_approve')
        if err:
            return err

        batch = self.get_object()
        reason = request.data.get('reason', '')
        from apps.payroll.disbursement_service import DisbursementService, DisbursementException
        try:
            cancelled_batch = DisbursementService.cancel_disbursement_batch(batch, request.user, reason=reason)
        except DisbursementException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DisbursementBatchDetailSerializer(cancelled_batch).data, status=status.HTTP_200_OK)


def _has_any_perm(user, *codenames):
    return any(AuthorizationService.has_permission(user, c) for c in codenames)


class FinalSettlementViewSet(viewsets.ModelViewSet):
    """
    CRUD and workflow management for Full & Final Settlement (FnF).
    Endpoints:
    - GET /: list settlements for requesting organization
    - POST /: prepare DRAFT settlement
    - POST /preview/: preview settlement calculations without persisting
    - GET /<id>/: retrieve settlement detail with normalized lines
    - POST /<id>/approve/: approve draft settlement (enforces maker-checker)
    - POST /<id>/finalize/: finalize approved settlement (locks immutable state)
    - POST /<id>/cancel/: cancel draft settlement
    """
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'list':
            return FinalSettlementListSerializer
        return FinalSettlementDetailSerializer

    def get_queryset(self):
        org = _employee_org(self.request)
        if not org:
            return FinalSettlement.objects.none()
        qs = FinalSettlement.objects.filter(
            organization=org
        ).select_related(
            'employee', 'employee__user', 'employee__branch', 'employee__department',
            'created_by', 'approved_by', 'finalized_by'
        ).prefetch_related('lines')

        emp_id = self.request.query_params.get('employee')
        if emp_id:
            qs = qs.filter(employee_id=emp_id)
        stat = self.request.query_params.get('status')
        if stat:
            qs = qs.filter(status=stat)
        return qs

    def list(self, request, *args, **kwargs):
        if not _has_any_perm(request.user, 'payroll.fnf_view', 'payroll.view', 'payroll.view_sensitive'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not _has_any_perm(request.user, 'payroll.fnf_view', 'payroll.view', 'payroll.view_sensitive'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return super().retrieve(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='my')
    def my(self, request):
        """
        Employee self-service: Returns the authenticated employee's own finalized
        Full & Final Settlement records.

        Security requirements:
        - Authenticated employee access only.
        - Derives employee identity strictly from request.user (no user-supplied employee ID).
        - Organization isolation strictly enforced (organization=employee.organization).
        - Only FINALIZED settlements are exposed (draft/review/approved/cancelled excluded).
        - Exposes strictly employee-safe fields via EmployeeFinalSettlementSerializer.
        - Excludes maker/checker workflow internals, audit metadata, admin remarks,
          and sensitive banking/identity numbers.
        """
        user = request.user
        employee = getattr(user, 'employee', None)
        if not employee:
            employee = Employee.objects.filter(user=user).first()
        if not employee:
            return Response([], status=status.HTTP_200_OK)

        qs = FinalSettlement.objects.filter(
            organization=employee.organization,
            employee=employee,
            status=FinalSettlement.STATUS_FINALIZED,
        ).prefetch_related('lines', 'disbursement_batches').order_by('-settlement_date', '-created_at')

        serializer = EmployeeFinalSettlementSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path=r'my/(?P<settlement_id>\d+)')
    def my_detail(self, request, settlement_id=None):
        """
        Employee self-service: Returns detail of the authenticated employee's own
        finalized Full & Final Settlement record.

        Security requirements:
        - Authenticated employee access only.
        - Strict IDOR prevention: If settlement does not belong to the authenticated
          employee, does not belong to their organization, or is not in FINALIZED state,
          returns 404 NOT FOUND (never returns 403 or leaks settlement existence).
        - Exposes strictly employee-safe fields via EmployeeFinalSettlementSerializer.
        """
        user = request.user
        employee = getattr(user, 'employee', None)
        if not employee:
            employee = Employee.objects.filter(user=user).first()
        if not employee:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        settlement = FinalSettlement.objects.filter(
            id=settlement_id,
            organization=employee.organization,
            employee=employee,
            status=FinalSettlement.STATUS_FINALIZED,
        ).prefetch_related('lines', 'disbursement_batches').first()

        if not settlement:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = EmployeeFinalSettlementSerializer(settlement)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='preview')
    def preview(self, request):
        if not _has_any_perm(request.user, 'payroll.fnf_prepare', 'payroll.generate'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = FnFPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = FnFService.preview(
                employee_id=serializer.validated_data['employee_id'],
                requesting_user=request.user,
                exit_date=serializer.validated_data.get('exit_date'),
                settlement_date=serializer.validated_data.get('settlement_date'),
                asset_recoveries=serializer.validated_data.get('asset_recoveries'),
                loan_recoveries=serializer.validated_data.get('loan_recoveries'),
                bonus_amount=serializer.validated_data.get('bonus_amount'),
                bonus_remarks=serializer.validated_data.get('bonus_remarks', ''),
                joining_bonus_clawback=serializer.validated_data.get('joining_bonus_clawback'),
                tds_amount=serializer.validated_data.get('tds_amount'),
                remarks=serializer.validated_data.get('remarks', ''),
            )
        except FnFException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        if not _has_any_perm(request.user, 'payroll.fnf_prepare', 'payroll.generate'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = FnFPrepareRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            settlement = FnFService.prepare(
                employee_id=serializer.validated_data['employee_id'],
                requesting_user=request.user,
                exit_date=serializer.validated_data.get('exit_date'),
                settlement_date=serializer.validated_data.get('settlement_date'),
                asset_recoveries=serializer.validated_data.get('asset_recoveries'),
                loan_recoveries=serializer.validated_data.get('loan_recoveries'),
                bonus_amount=serializer.validated_data.get('bonus_amount'),
                bonus_remarks=serializer.validated_data.get('bonus_remarks', ''),
                joining_bonus_clawback=serializer.validated_data.get('joining_bonus_clawback'),
                tds_amount=serializer.validated_data.get('tds_amount'),
                remarks=serializer.validated_data.get('remarks', ''),
            )
        except FnFException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(FinalSettlementDetailSerializer(settlement).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        if not _has_any_perm(request.user, 'payroll.fnf_approve', 'payroll.approve'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        settlement = self.get_object()
        try:
            approved = FnFService.approve(settlement, request.user)
        except FnFException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(FinalSettlementDetailSerializer(approved).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='finalize')
    def finalize(self, request, pk=None):
        if not _has_any_perm(request.user, 'payroll.fnf_finalize', 'payroll.approve'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        settlement = self.get_object()
        try:
            finalized = FnFService.finalize(settlement, request.user)
        except FnFException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(FinalSettlementDetailSerializer(finalized).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        if not _has_any_perm(request.user, 'payroll.fnf_prepare', 'payroll.generate'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        settlement = self.get_object()
        reason = request.data.get('reason', '')
        try:
            cancelled = FnFService.cancel(settlement, request.user, reason=reason)
        except FnFException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(FinalSettlementDetailSerializer(cancelled).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='prepare-disbursement')
    def prepare_disbursement(self, request, pk=None):
        if not _has_any_perm(request.user, 'payroll.disburse_prepare', 'payroll.disburse'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        settlement = self.get_object()
        value_date = request.data.get('value_date')
        narration = request.data.get('narration')
        debit_account_id = request.data.get('debit_account_id')

        debit_account = None
        if debit_account_id:
            org = _employee_org(request)
            debit_account = OrganizationBankAccount.objects.filter(
                id=debit_account_id, organization=org
            ).first()
            if not debit_account:
                return Response({'detail': 'Specified debit account not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        from apps.payroll.disbursement_service import DisbursementService, DisbursementException
        try:
            batch = DisbursementService.prepare_fnf_disbursement_batch(
                settlement=settlement,
                user=request.user,
                value_date=value_date,
                narration=narration,
                debit_account=debit_account,
            )
        except DisbursementException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DisbursementBatchDetailSerializer(batch).data, status=status.HTTP_201_CREATED)


class FnFPolicyConfigurationViewSet(viewsets.ModelViewSet):
    """
    CRUD for effective-dated Full & Final settlement policy configurations.
    """
    serializer_class = FnFPolicyConfigurationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = _employee_org(self.request)
        if not org:
            return FnFPolicyConfiguration.objects.none()
        return FnFPolicyConfiguration.objects.filter(organization=org).select_related('branch', 'created_by')

    def list(self, request, *args, **kwargs):
        if not _has_any_perm(request.user, 'payroll.fnf_view', 'payroll.view', 'payroll.disburse_configure'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not _has_any_perm(request.user, 'payroll.fnf_view', 'payroll.view', 'payroll.disburse_configure'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not _has_any_perm(request.user, 'payroll.fnf_prepare', 'payroll.disburse_configure', 'payroll.manage_compensation'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        org = _employee_org(request)
        if not org:
            return Response({'detail': 'Organization context required.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(organization=org, created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        if not _has_any_perm(request.user, 'payroll.fnf_prepare', 'payroll.disburse_configure', 'payroll.manage_compensation'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not _has_any_perm(request.user, 'payroll.fnf_prepare', 'payroll.disburse_configure', 'payroll.manage_compensation'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


