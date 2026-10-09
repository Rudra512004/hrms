from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.db.models import Q
import mimetypes

from apps.payroll.models import (
    FinancialYear,
    TaxDeclarationCategory,
    TaxDeclaration,
    InvestmentDeclaration,
    InvestmentProof,
)
from apps.payroll.serializers_tax import (
    FinancialYearSerializer,
    TaxDeclarationCategorySerializer,
    TaxDeclarationSummarySerializer,
    TaxDeclarationDetailSerializer,
    TaxDeclarationCreateSerializer,
    TaxDeclarationUpdateSerializer,
    InvestmentItemCreateSerializer,
    InvestmentItemUpdateSerializer,
    InvestmentDeclarationSerializer,
    InvestmentProofSerializer,
    TaxDeclarationVerificationSerializer,
    TaxDeclarationRejectSerializer,
    TaxProofRejectSerializer,
)
from apps.payroll.services_tax import TaxDeclarationService, TaxDeclarationException
from apps.authorization.services import AuthorizationService
from apps.audit.services import AuditService


def _get_user_org(request):
    user = request.user
    if hasattr(user, 'employee') and user.employee and user.employee.organization_id:
        return user.employee.organization
    return AuthorizationService.get_primary_organization(user)


def _is_reviewer(user) -> bool:
    return AuthorizationService.has_permission(user, 'payroll.tax_review') or \
           AuthorizationService.has_permission(user, 'payroll.tax_view')


class FinancialYearViewSet(viewsets.ModelViewSet):
    """
    CRUD and query endpoint for organization Financial Years.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = FinancialYearSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        org = _get_user_org(self.request)
        if not org:
            return FinancialYear.objects.none()
        return FinancialYear.objects.filter(organization=org)

    def perform_create(self, serializer):
        org = _get_user_org(self.request)
        if not org:
            raise PermissionError("No organization context found.")
        if not AuthorizationService.has_permission(self.request.user, 'payroll.tax_review'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only authorized tax administrators can configure financial years.")
        serializer.save(organization=org)


class TaxDeclarationCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only catalog of configurable tax categories (80C, 80D, HRA, etc.).
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TaxDeclarationCategorySerializer

    def get_queryset(self):
        org = _get_user_org(self.request)
        if not org:
            return TaxDeclarationCategory.objects.none()
        return TaxDeclarationCategory.objects.filter(organization=org, is_active=True)


class TaxDeclarationViewSet(viewsets.ModelViewSet):
    """
    Comprehensive employee tax declaration and reviewer workflow endpoint.
    - GET /my/: Current employee's tax declarations.
    - POST /: Create draft declaration.
    - GET /{id}/: Detailed declaration with items and proofs (owner or reviewer).
    - PATCH /{id}/: Update regime/notes on draft declaration.
    - POST /{id}/submit/: Submit declaration for review.
    - POST /{id}/items/: Add investment item.
    - PATCH/DELETE /{id}/items/{item_id}/: Update or delete investment item.
    - POST /{id}/items/{item_id}/proofs/: Upload proof attachment.
    - GET /{id}/items/{item_id}/proofs/{proof_id}/download/: Secure binary proof download.
    - POST /{id}/start-review/: (Reviewer) Transition to under_review.
    - POST /{id}/verify/: (Reviewer) Verify declaration.
    - POST /{id}/reject/: (Reviewer) Reject declaration with reason.
    """
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TaxDeclarationDetailSerializer
        return TaxDeclarationSummarySerializer

    def get_queryset(self):
        org = _get_user_org(self.request)
        if not org:
            return TaxDeclaration.objects.none()

        base_qs = TaxDeclaration.objects.filter(
            organization=org
        ).select_related(
            'employee', 'employee__user', 'financial_year', 'verified_by'
        ).prefetch_related(
            'items', 'items__proofs'
        )

        user = self.request.user
        # If user is a designated reviewer, allow org-wide query with filters
        if _is_reviewer(user) and self.action != 'my':
            emp_id = self.request.query_params.get('employee')
            if emp_id:
                base_qs = base_qs.filter(employee_id=emp_id)
            fy_id = self.request.query_params.get('financial_year')
            if fy_id:
                base_qs = base_qs.filter(financial_year_id=fy_id)
            stat = self.request.query_params.get('status')
            if stat:
                base_qs = base_qs.filter(status=stat)
            return base_qs

        # Otherwise, strictly scope to employee's own declarations
        if hasattr(user, 'employee') and user.employee:
            return base_qs.filter(employee=user.employee)

        return TaxDeclaration.objects.none()

    @action(detail=False, methods=['get'], url_path='my')
    def my(self, request):
        """Returns the authenticated employee's tax declarations."""
        if not hasattr(request.user, 'employee') or not request.user.employee:
            return Response(
                {'detail': 'An active employee profile is required to access tax declarations.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        qs = self.get_queryset().filter(employee=request.user.employee)
        fy_param = request.query_params.get('financial_year')
        if fy_param:
            if fy_param.isdigit():
                qs = qs.filter(financial_year_id=int(fy_param))
            else:
                qs = qs.filter(financial_year__name__iexact=fy_param.strip())

        serializer = TaxDeclarationSummarySerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        """Employee creates a new draft tax declaration for a financial year."""
        if not hasattr(request.user, 'employee') or not request.user.employee:
            return Response(
                {'detail': 'An active employee profile is required to create a tax declaration.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = TaxDeclarationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        org = _get_user_org(request)
        fy = None
        if data.get('financial_year_id'):
            fy = get_object_or_404(FinancialYear, id=data['financial_year_id'], organization=org)
        elif data.get('financial_year_name'):
            fy = get_object_or_404(FinancialYear, name__iexact=data['financial_year_name'].strip(), organization=org)

        try:
            declaration = TaxDeclarationService.create_declaration(
                employee=request.user.employee,
                financial_year=fy,
                tax_regime=data.get('tax_regime', TaxDeclaration.REGIME_NEW),
                notes=data.get('notes', ''),
                requesting_user=request.user,
            )
        except TaxDeclarationException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            TaxDeclarationDetailSerializer(declaration).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, pk=None):
        """Update draft declaration fields (tax regime, notes)."""
        declaration = self.get_object()

        # Enforce owner authorization
        emp = getattr(request.user, 'employee', None)
        if not emp or declaration.employee_id != emp.id:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = TaxDeclarationUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            updated = TaxDeclarationService.update_declaration(
                declaration=declaration,
                tax_regime=data.get('tax_regime'),
                notes=data.get('notes'),
                requesting_user=request.user,
            )
        except TaxDeclarationException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TaxDeclarationDetailSerializer(updated).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        """Employee submits declaration for review."""
        declaration = self.get_object()

        # Enforce owner authorization
        emp = getattr(request.user, 'employee', None)
        if not emp or declaration.employee_id != emp.id:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            submitted = TaxDeclarationService.submit_declaration(
                declaration=declaration,
                requesting_user=request.user,
            )
        except TaxDeclarationException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TaxDeclarationDetailSerializer(submitted).data, status=status.HTTP_200_OK)

    # =========================================================================
    # ITEM MANAGEMENT ACTIONS
    # =========================================================================

    @action(detail=True, methods=['post'], url_path='items')
    def add_item(self, request, pk=None):
        """Add an investment item to the draft declaration."""
        declaration = self.get_object()

        emp = getattr(request.user, 'employee', None)
        if not emp or declaration.employee_id != emp.id:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = InvestmentItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            item = TaxDeclarationService.add_item(
                declaration=declaration,
                category_code=data['category_code'],
                description=data['description'],
                declared_amount=data['declared_amount'],
                metadata=data.get('metadata'),
                requesting_user=request.user,
            )
        except TaxDeclarationException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        return Response(InvestmentDeclarationSerializer(item).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], url_path='items/(?P<item_id>[^/.]+)')
    def update_item(self, request, pk=None, item_id=None):
        """Update an investment item in a draft declaration."""
        declaration = self.get_object()

        emp = getattr(request.user, 'employee', None)
        if not emp or declaration.employee_id != emp.id:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        item = get_object_or_404(InvestmentDeclaration, id=item_id, declaration=declaration)

        serializer = InvestmentItemUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            updated = TaxDeclarationService.update_item(
                item=item,
                description=data.get('description'),
                declared_amount=data.get('declared_amount'),
                metadata=data.get('metadata'),
                requesting_user=request.user,
            )
        except TaxDeclarationException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        return Response(InvestmentDeclarationSerializer(updated).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['delete'], url_path='items/(?P<item_id>[^/.]+)/delete')
    def delete_item(self, request, pk=None, item_id=None):
        """Delete an investment item from a draft declaration."""
        declaration = self.get_object()

        emp = getattr(request.user, 'employee', None)
        if not emp or declaration.employee_id != emp.id:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        item = get_object_or_404(InvestmentDeclaration, id=item_id, declaration=declaration)

        try:
            TaxDeclarationService.delete_item(item=item, requesting_user=request.user)
        except TaxDeclarationException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)

    # =========================================================================
    # PROOF ATTACHMENT ACTIONS
    # =========================================================================

    @action(detail=True, methods=['post'], url_path='items/(?P<item_id>[^/.]+)/proofs')
    def upload_proof(self, request, pk=None, item_id=None):
        """Upload a proof file attached to an investment item."""
        declaration = self.get_object()

        emp = getattr(request.user, 'employee', None)
        if not emp or declaration.employee_id != emp.id:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        item = get_object_or_404(InvestmentDeclaration, id=item_id, declaration=declaration)

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'detail': 'No file uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

        proof_type = request.data.get('proof_type', 'DOCUMENT')
        doc_name = request.data.get('document_name', uploaded_file.name)

        try:
            proof = TaxDeclarationService.upload_proof(
                item=item,
                uploaded_file=uploaded_file,
                proof_type=proof_type,
                document_name=doc_name,
                requesting_user=request.user,
            )
        except TaxDeclarationException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        return Response(InvestmentProofSerializer(proof).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='items/(?P<item_id>[^/.]+)/proofs/(?P<proof_id>[^/.]+)/download')
    def download_proof(self, request, pk=None, item_id=None, proof_id=None):
        """Securely stream proof file. Enforces owner or reviewer authorization."""
        declaration = self.get_object()
        item = get_object_or_404(InvestmentDeclaration, id=item_id, declaration=declaration)
        proof = get_object_or_404(InvestmentProof, id=proof_id, declaration_item=item)

        user = request.user
        emp = getattr(user, 'employee', None)
        is_owner = (emp is not None and declaration.employee_id == emp.id)
        has_reviewer_perm = _is_reviewer(user)

        if not (is_owner or has_reviewer_perm):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        if not proof.file:
            return Response({'detail': 'File not found on storage.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            file_handle = proof.file.open('rb')
            content = file_handle.read()
            file_handle.close()
        except Exception:
            return Response({'detail': 'Unable to read file from storage.'}, status=status.HTTP_404_NOT_FOUND)

        mime = proof.mime_type or mimetypes.guess_type(proof.document_name)[0] or 'application/octet-stream'
        response = HttpResponse(content, content_type=mime)
        response['Content-Disposition'] = f'attachment; filename="{proof.document_name}"'
        return response

    # =========================================================================
    # REVIEWER / ADMINISTRATIVE ACTIONS
    # =========================================================================

    @action(detail=True, methods=['post'], url_path='start-review')
    def start_review(self, request, pk=None):
        """(Reviewer) Mark declaration as under review."""
        if not AuthorizationService.has_permission(request.user, 'payroll.tax_review'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        declaration = self.get_object()
        try:
            reviewed = TaxDeclarationService.start_review(declaration, reviewer_user=request.user)
        except TaxDeclarationException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TaxDeclarationDetailSerializer(reviewed).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='verify')
    def verify(self, request, pk=None):
        """(Reviewer) Verify declaration and snapshot verified inputs."""
        if not AuthorizationService.has_permission(request.user, 'payroll.tax_review'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        declaration = self.get_object()
        serializer = TaxDeclarationVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            verified = TaxDeclarationService.verify_declaration(
                declaration=declaration,
                reviewer_user=request.user,
                item_verifications=data.get('item_verifications'),
                notes=data.get('notes', ''),
            )
        except TaxDeclarationException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TaxDeclarationDetailSerializer(verified).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        """(Reviewer) Reject declaration with reason."""
        if not AuthorizationService.has_permission(request.user, 'payroll.tax_review'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        declaration = self.get_object()
        serializer = TaxDeclarationRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            rejected = TaxDeclarationService.reject_declaration(
                declaration=declaration,
                reviewer_user=request.user,
                rejection_reason=serializer.validated_data['rejection_reason'],
            )
        except TaxDeclarationException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TaxDeclarationDetailSerializer(rejected).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='items/(?P<item_id>[^/.]+)/proofs/(?P<proof_id>[^/.]+)/verify')
    def verify_proof(self, request, pk=None, item_id=None, proof_id=None):
        """(Reviewer) Verify individual proof document."""
        if not AuthorizationService.has_permission(request.user, 'payroll.tax_review'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        declaration = self.get_object()
        item = get_object_or_404(InvestmentDeclaration, id=item_id, declaration=declaration)
        proof = get_object_or_404(InvestmentProof, id=proof_id, declaration_item=item)

        try:
            verified_proof = TaxDeclarationService.verify_proof(proof=proof, reviewer_user=request.user)
        except TaxDeclarationException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        return Response(InvestmentProofSerializer(verified_proof).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='items/(?P<item_id>[^/.]+)/proofs/(?P<proof_id>[^/.]+)/reject')
    def reject_proof(self, request, pk=None, item_id=None, proof_id=None):
        """(Reviewer) Reject individual proof document with reason."""
        if not AuthorizationService.has_permission(request.user, 'payroll.tax_review'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        declaration = self.get_object()
        item = get_object_or_404(InvestmentDeclaration, id=item_id, declaration=declaration)
        proof = get_object_or_404(InvestmentProof, id=proof_id, declaration_item=item)

        serializer = TaxProofRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            rejected_proof = TaxDeclarationService.reject_proof(
                proof=proof,
                rejection_reason=serializer.validated_data['rejection_reason'],
                reviewer_user=request.user,
            )
        except TaxDeclarationException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        return Response(InvestmentProofSerializer(rejected_proof).data, status=status.HTTP_200_OK)


# =============================================================================
# TAX RULE & PROGRESSIVE TDS VIEWS (Phase 6.9C)
# =============================================================================

class TaxRuleConfigurationViewSet(viewsets.ModelViewSet):
    """
    CRUD and query endpoint for versioned organization tax rule configurations.
    """
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        from apps.payroll.serializers_tax import TaxRuleConfigurationSerializer
        return TaxRuleConfigurationSerializer

    def get_queryset(self):
        org = _get_user_org(self.request)
        if not org:
            return TaxRuleConfiguration.objects.none()
        return TaxRuleConfiguration.objects.filter(
            organization=org
        ).prefetch_related('slabs', 'surcharge_slabs', 'deduction_rules')

    def perform_create(self, serializer):
        org = _get_user_org(self.request)
        if not org:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("No organization context found.")
        if not AuthorizationService.has_permission(self.request.user, 'payroll.tax_configure'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Permission payroll.tax_configure is required to create tax rules.")
        instance = serializer.save(organization=org)
        AuditService.log(
            action='TAX_RULE_CONFIG_CREATED',
            actor=self.request.user,
            target_type='TaxRuleConfiguration',
            target_id=instance.id,
            organization=org,
            metadata={'version_identifier': instance.version_identifier, 'regime': instance.regime}
        )

    def perform_update(self, serializer):
        if not AuthorizationService.has_permission(self.request.user, 'payroll.tax_configure'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Permission payroll.tax_configure is required to update tax rules.")
        instance = serializer.save()
        AuditService.log(
            action='TAX_RULE_CONFIG_UPDATED',
            actor=self.request.user,
            target_type='TaxRuleConfiguration',
            target_id=instance.id,
            organization=instance.organization,
            metadata={'version_identifier': instance.version_identifier, 'is_active': instance.is_active}
        )


class TaxCalculationPreviewView(viewsets.GenericViewSet):
    """
    Service endpoint for tax projection & monthly TDS calculation preview.
    Does not mutate or persist payroll records (idempotent preview).
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='preview')
    def preview(self, request):
        from apps.payroll.serializers_tax import TaxCalculationPreviewRequestSerializer
        from apps.payroll.tax_calculator import TaxCalculationService, TaxCalculationException
        from apps.employees.models import Employee
        from apps.payroll.models import PayrollPeriod

        serializer = TaxCalculationPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        org = _get_user_org(request)
        if not org:
            return Response({'detail': 'No organization context.'}, status=status.HTTP_403_FORBIDDEN)

        if not (
            AuthorizationService.has_permission(request.user, 'payroll.tax_calculate') or
            AuthorizationService.has_permission(request.user, 'payroll.tax_view')
        ):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        emp_id = serializer.validated_data['employee_id']
        period_id = serializer.validated_data['period_id']
        current_gross = serializer.validated_data.get('current_gross')

        employee = get_object_or_404(Employee, id=emp_id, organization=org)
        period = get_object_or_404(PayrollPeriod, id=period_id, organization=org)

        try:
            result = TaxCalculationService.calculate_monthly_tds(
                employee=employee,
                period=period,
                current_gross=current_gross,
                preview=True,
            )
        except TaxCalculationException as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)

