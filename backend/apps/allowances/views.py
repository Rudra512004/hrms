from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError

from apps.authorization.permissions import require_permission, IsNetworkAllowed
from apps.authorization.services import AuthorizationService
from apps.organization.context import get_current_employee, get_current_organization
from apps.audit.services import AuditService
from apps.notifications.services import NotificationService

from .models import AllowanceType, EmployeeAllowance, ReimbursementClaim
from .serializers import (
    AllowanceTypeSerializer,
    EmployeeAllowanceSerializer,
    ReimbursementClaimSerializer,
    ReimbursementReviewSerializer
)

class AllowanceTypeViewSet(viewsets.ModelViewSet):
    serializer_class = AllowanceTypeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'code']
    filterset_fields = ['is_active', 'category']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('allowance.view')
        else:
            permission = require_permission('allowance.manage')
        return [permissions.IsAuthenticated(), permission()]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            org_id = self.request.query_params.get('organization_id')
            if org_id:
                return AllowanceType.objects.filter(organization_id=org_id)
            return AllowanceType.objects.all()

        org = get_current_organization(self.request)
        if org:
            return AllowanceType.objects.filter(organization=org)
        return AllowanceType.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser:
            org_id = self.request.data.get('organization')
            if not org_id:
                raise ValidationError({"organization": "Organization is required for superuser."})
            from apps.organization.models import Organization
            try:
                org = Organization.objects.get(id=org_id)
            except Organization.DoesNotExist:
                raise ValidationError({"organization": "Invalid organization."})
        else:
            org = get_current_organization(self.request)
            if not org:
                raise ValidationError("Organization context is required.")
        
        try:
            allowance_type = serializer.save(organization=org, created_by=user)
            AuditService.log(
                action='allowance_type_created',
                actor=user,
                target_type='allowancetype',
                target_id=allowance_type.id,
                request=self.request
            )
        except IntegrityError:
            raise ValidationError({"code": "Allowance Type with this code already exists."})

    def perform_update(self, serializer):
        try:
            allowance_type = serializer.save()
            AuditService.log(
                action='allowance_type_updated',
                actor=self.request.user,
                target_type='allowancetype',
                target_id=allowance_type.id,
                request=self.request
            )
        except IntegrityError:
            raise ValidationError({"code": "Allowance Type with this code already exists."})

class EmployeeAllowanceViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeAllowanceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'allowance_type', 'is_active']

    def get_permissions(self):
        if self.action == 'my_allowances':
            return [permissions.IsAuthenticated()]
        elif self.action in ['list', 'retrieve']:
            permission = require_permission('allowance.view')
        else:
            permission = require_permission('allowance.assign')
        return [permissions.IsAuthenticated(), permission()]

    def get_queryset(self):
        user = self.request.user
        qs = EmployeeAllowance.objects.select_related('employee', 'allowance_type')

        if user.is_superuser:
            org_id = self.request.query_params.get('organization_id')
            if org_id:
                return qs.filter(organization_id=org_id)
            return qs

        org = get_current_organization(self.request)
        if not org:
            return EmployeeAllowance.objects.none()

        qs = qs.filter(organization=org)
        
        # Determine accessible branches via authorization service
        authorized_branches = AuthorizationService.get_authorized_branches(user, 'allowance.view')
        authorized_teams = AuthorizationService.get_authorized_teams(user, 'allowance.view')

        if AuthorizationService.has_permission(self.request, 'allowance.view', branch_id=None, global_only=True):
            pass # Org level access
        else:
            from django.db.models import Q
            qs = qs.filter(Q(employee__branch__in=authorized_branches) | Q(employee__team__in=authorized_teams))
        
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        employee_id = self.request.data.get('employee')
        
        from apps.employees.models import Employee
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            raise ValidationError({"employee": "Employee not found."})

        if not user.is_superuser:
            authorized_branches = AuthorizationService.get_authorized_branches(user, 'allowance.assign')
            if employee.branch not in authorized_branches and not AuthorizationService.has_permission(user, 'allowance.assign', global_only=True):
                raise ValidationError({"employee": "Not authorized to assign allowance to this employee."})
            org = get_current_organization(self.request)
            if employee.organization_id != org.id:
                raise ValidationError("Organization mismatch.")

        assignment = serializer.save(organization=employee.organization, assigned_by=user)
        AuditService.log(
            action='employee_allowance_assigned',
            actor=user,
            target_type='employeeallowance',
            target_id=assignment.id,
            request=self.request
        )

    def perform_update(self, serializer):
        assignment = serializer.save()
        AuditService.log(
            action='employee_allowance_updated',
            actor=self.request.user,
            target_type='employeeallowance',
            target_id=assignment.id,
            request=self.request
        )

    @action(detail=False, methods=['get'])
    def my_allowances(self, request):
        employee = get_current_employee(request)
        if not employee:
            return Response([])
        
        qs = EmployeeAllowance.objects.filter(employee=employee, is_active=True).select_related('allowance_type')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

class ReimbursementClaimViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'payment_status', 'allowance_type', 'employee']
    search_fields = ['description']

    def get_serializer_class(self):
        if self.action in ['approve', 'reject', 'return_claim']:
            return ReimbursementReviewSerializer
        return ReimbursementClaimSerializer

    def get_permissions(self):
        permissions_list = [permissions.IsAuthenticated(), IsNetworkAllowed()]
        if self.action in ['create', 'my_claims', 'submit']:
            pass
        elif self.action in ['approve', 'reject', 'return_claim', 'queue']:
            permissions_list.append(require_permission('reimbursement.approve')())
        elif self.action == 'pay':
            permissions_list.append(require_permission('reimbursement.pay')())
        else:
            permissions_list.append(require_permission('reimbursement.view')())
        return permissions_list

    def get_queryset(self):
        user = self.request.user
        qs = ReimbursementClaim.objects.select_related('employee', 'allowance_type', 'reviewer')

        if user.is_superuser:
            org_id = self.request.query_params.get('organization_id')
            if org_id:
                return qs.filter(organization_id=org_id)
            return qs

        org = get_current_organization(self.request)
        if not org:
            return ReimbursementClaim.objects.none()

        qs = qs.filter(organization=org)
        
        # If accessing regular list/retrieve, restrict to authorized scope
        if self.action not in ['my_claims']:
            authorized_branches = AuthorizationService.get_authorized_branches(user, 'reimbursement.view')
            authorized_teams = AuthorizationService.get_authorized_teams(user, 'reimbursement.view')
            if AuthorizationService.has_permission(self.request, 'reimbursement.view', branch_id=None, global_only=True):
                pass
            else:
                from django.db.models import Q
                qs = qs.filter(Q(employee__branch__in=authorized_branches) | Q(employee__team__in=authorized_teams))
        
        return qs

    def perform_create(self, serializer):
        employee = get_current_employee(self.request)
        if not employee:
            raise ValidationError("Must be an employee to create a claim.")

        status_val = self.request.data.get('status', 'draft')
        if status_val not in ['draft', 'submitted']:
            raise ValidationError({"status": "Initial status must be draft or submitted."})

        claim = serializer.save(
            organization=employee.organization,
            employee=employee,
            status=status_val,
            submitted_at=timezone.now() if status_val == 'submitted' else None
        )
        
        AuditService.log(
            action=f'reimbursement_claim_{status_val}',
            actor=self.request.user,
            target_type='reimbursementclaim',
            target_id=claim.id,
            request=self.request
        )

    def perform_update(self, serializer):
        claim = self.get_object()
        if claim.status not in ['draft', 'returned']:
            raise ValidationError("Can only update draft or returned claims.")
        
        status_val = self.request.data.get('status')
        if status_val and status_val not in ['draft', 'submitted', 'cancelled']:
            raise ValidationError("Invalid status transition.")
            
        updated_claim = serializer.save(
            submitted_at=timezone.now() if status_val == 'submitted' else claim.submitted_at
        )
        AuditService.log(
            action='reimbursement_claim_updated',
            actor=self.request.user,
            target_type='reimbursementclaim',
            target_id=updated_claim.id,
            request=self.request
        )

    @action(detail=False, methods=['get'])
    def my_claims(self, request):
        employee = get_current_employee(request)
        if not employee:
            return Response([])
        qs = ReimbursementClaim.objects.filter(employee=employee).select_related('allowance_type', 'reviewer')
        qs = self.filter_queryset(qs)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def queue(self, request):
        qs = self.get_queryset().filter(status='submitted')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def _review_claim(self, claim, status_val, data):
        if claim.status not in ['submitted', 'under_review']:
            raise ValidationError("Claim is not in a reviewable state.")
        
        if claim.employee.user_id == self.request.user.id:
            raise ValidationError("Cannot review your own claim.")

        serializer = self.get_serializer(claim, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        reviewed_claim = serializer.save(
            status=status_val,
            reviewer=self.request.user,
            reviewed_at=timezone.now()
        )
        
        AuditService.log(
            action=f'reimbursement_claim_{status_val}',
            actor=self.request.user,
            target_type='reimbursementclaim',
            target_id=reviewed_claim.id,
            request=self.request
        )
        return reviewed_claim

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        claim = self.get_object()
        data = request.data.copy()
        data['status'] = 'approved'
        if 'amount_approved' not in data:
            data['amount_approved'] = claim.amount_claimed
        
        claim = self._review_claim(claim, 'approved', data)
        return Response(ReimbursementClaimSerializer(claim).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        claim = self.get_object()
        data = request.data.copy()
        data['status'] = 'rejected'
        claim = self._review_claim(claim, 'rejected', data)
        return Response(ReimbursementClaimSerializer(claim).data)

    @action(detail=True, methods=['post'])
    def return_claim(self, request, pk=None):
        claim = self.get_object()
        data = request.data.copy()
        data['status'] = 'returned'
        claim = self._review_claim(claim, 'returned', data)
        return Response(ReimbursementClaimSerializer(claim).data)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        claim = self.get_object()
        if claim.status != 'approved':
            raise ValidationError("Only approved claims can be marked as paid.")
        if claim.payment_status == 'paid':
            raise ValidationError("Claim is already paid.")
        
        claim.payment_status = 'paid'
        claim.paid_at = timezone.now()
        claim.save(update_fields=['payment_status', 'paid_at'])
        
        AuditService.log(
            action='reimbursement_claim_paid',
            actor=request.user,
            target_type='reimbursementclaim',
            target_id=claim.id,
            request=request
        )
        return Response(ReimbursementClaimSerializer(claim).data)
