from rest_framework import viewsets, status, permissions
from apps.audit.services import AuditService
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from apps.authorization.permissions import require_permission
from apps.audit.services import AuditService
from apps.authorization.services import AuthorizationService
from apps.notifications.services import NotificationService
from apps.organization.models import Organization
from .models import LeaveType, LeaveBalance, LeaveRequest
from .serializers import LeaveTypeSerializer, LeaveBalanceSerializer, LeaveRequestSerializer, LeaveRequestReviewSerializer

class LeaveTypeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeaveTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'employee') and user.employee.organization_id:
            return LeaveType.objects.filter(is_active=True, organization_id=user.employee.organization_id)
        return LeaveType.objects.none()

class AdminLeaveTypeViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveTypeSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return LeaveType.objects.all()
        if hasattr(user, 'employee') and user.employee.organization_id:
            return LeaveType.objects.filter(organization_id=user.employee.organization_id)
        return LeaveType.objects.none()

    def get_permissions(self):
        permission_class = require_permission('leave_type.manage')
        return [permissions.IsAuthenticated(), permission_class()]

    def perform_create(self, serializer):
        from django.db import IntegrityError
        from rest_framework.exceptions import ValidationError

        org_id = self.request.data.get('organization')
        if self.request.user.is_superuser and not hasattr(self.request.user, 'employee'):
            if org_id:
                try:
                    from apps.organization.models import Organization
                    org = Organization.objects.get(id=org_id)
                except (Organization.DoesNotExist, ValueError):
                    raise ValidationError({"organization": "Specified organization does not exist."})
            else:
                org = None
        else:
            emp = getattr(self.request.user, 'employee', None)
            org = emp.organization if emp else None
            if org_id and org and str(org.id) != str(org_id):
                raise ValidationError({"organization": "Cannot create resources for another organization."})

        if not org:
            raise ValidationError({"organization": "Organization context is required."})

        try:
            leave_type = serializer.save(organization=org)
            AuditService.log(
                action='leave_type_created',
                actor=self.request.user,
                target_type='leavetype',
                target_id=leave_type.id,
                request=self.request
            )
        except IntegrityError:
            raise ValidationError({"name": "A leave type with this name already exists."})

    def perform_update(self, serializer):
        from django.db import IntegrityError
        from rest_framework.exceptions import ValidationError

        try:
            leave_type = serializer.save()
            AuditService.log(
                action='leave_type_updated',
                actor=self.request.user,
                target_type='leavetype',
                target_id=leave_type.id,
                request=self.request
            )
        except IntegrityError:
            raise ValidationError({"name": "A leave type with this name already exists."})

    def destroy(self, request, *args, **kwargs):
        leave_type = self.get_object()

        # Safe deletion: check for requests or USED balances
        if leave_type.requests.exists() or leave_type.balances.filter(used__gt=0).exists():
            return Response(
                {"detail": "Cannot delete leave type that is in use by requests or has consumed balances."},
                status=status.HTTP_409_CONFLICT
            )

        leave_type_id = leave_type.id
        leave_type.delete()

        AuditService.log(
            action='leave_type_deleted',
            actor=request.user,
            target_type='leavetype',
            target_id=leave_type_id,
            request=request
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

class LeaveBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeaveBalanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'employee'):
            return LeaveBalance.objects.filter(employee=user.employee)
        return LeaveBalance.objects.none()

class LeaveRequestViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveRequestSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return LeaveRequest.objects.none()

        qs = LeaveRequest.objects.all()
        if AuthorizationService.has_permission(user, 'leave.view'):
            if user.is_superuser:
                pass
            elif hasattr(user, 'employee'):
                authorized_branches = AuthorizationService.get_authorized_branches(user, 'leave.view')
                qs = qs.filter(employee__branch__in=authorized_branches)
            else:
                qs = LeaveRequest.objects.none()
        elif hasattr(user, 'employee'):
            qs = qs.filter(employee=user.employee)
        else:
            return LeaveRequest.objects.none()

        branch_id = self.request.query_params.get('branch_id')
        if branch_id:
            qs = qs.filter(employee__branch_id=branch_id)
        return qs

    def get_permissions(self):
        permissions = [IsAuthenticated()]
        if self.action == 'create':
            permission_class = require_permission('leave.request')
            permissions.append(permission_class())
        return permissions

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        employee = getattr(self.request.user, 'employee', None)
        if not employee:
            raise ValidationError({"detail": "Employee profile not found."})

        if getattr(employee, 'employment_status', None) == 'exited':
            raise ValidationError({"detail": "Exited employees cannot request leave."})

        leave = serializer.save(employee=employee)
        AuditService.log(
            action='leave_request_created',
            actor=self.request.user,
            target_type='leaverequest',
            target_id=leave.id,
            request=self.request
        )

    def perform_update(self, serializer):
        from rest_framework.exceptions import ValidationError, PermissionDenied
        instance = self.get_object()
        if instance.status != 'pending':
            raise ValidationError({"detail": "Only pending requests can be modified."})
        if not self.request.user.is_superuser and instance.employee != getattr(self.request.user, 'employee', None):
            raise PermissionDenied("You can only modify your own leave requests.")
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        from rest_framework.exceptions import ValidationError, PermissionDenied
        if instance.status != 'pending':
            raise ValidationError({"detail": f"Cannot delete a leave request with status '{instance.status}'. Only pending requests can be deleted."})
        if not self.request.user.is_superuser and instance.employee != getattr(self.request.user, 'employee', None):
            raise PermissionDenied("You can only delete your own leave requests.")
        super().perform_destroy(instance)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if not AuthorizationService.has_permission(request.user, 'leave.approve'):
            return Response(status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            leave = LeaveRequest.objects.select_for_update().get(pk=self.get_object().pk)
            if not request.user.is_superuser:
                if not hasattr(request.user, 'employee'):
                    return Response(status=status.HTTP_403_FORBIDDEN)
                authorized_branches = AuthorizationService.get_authorized_branches(request.user, 'leave.approve')
                if leave.employee.branch not in authorized_branches:
                    return Response(status=status.HTTP_403_FORBIDDEN)

            if leave.employee == getattr(request.user, 'employee', None):
                return Response({"detail": "Cannot approve own request."}, status=status.HTTP_403_FORBIDDEN)
            if leave.status != 'pending':
                return Response({"detail": "Only pending requests can be approved."}, status=status.HTTP_400_BAD_REQUEST)

            # Defensive check against overlapping approved leaves
            overlap = LeaveRequest.objects.filter(
                employee=leave.employee,
                status='approved',
                start_date__lte=leave.end_date,
                end_date__gte=leave.start_date,
            ).exclude(pk=leave.pk).exists()
            if overlap:
                return Response(
                    {"detail": "Cannot approve: an overlapping approved leave already exists for this employee."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer = LeaveRequestReviewSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Check balance
            try:
                balance = LeaveBalance.objects.select_for_update().get(employee=leave.employee, leave_type=leave.leave_type)
            except LeaveBalance.DoesNotExist:
                return Response({"detail": "Leave balance record not found."}, status=status.HTTP_400_BAD_REQUEST)

            if balance.remaining < leave.duration_days:
                return Response({"detail": "Insufficient leave balance."}, status=status.HTTP_400_BAD_REQUEST)

            # Update balance
            balance.used += leave.duration_days
            balance.save()

            leave.status = 'approved'
            leave.reviewed_by = request.user
            leave.reviewed_at = timezone.now()
            leave.reviewer_comment = serializer.validated_data.get('reviewer_comment', '')
            leave.save()

            transaction.on_commit(lambda l=leave: NotificationService.create_in_app_notification(
                recipient=l.employee.user,
                organization=l.employee.organization,
                notification_type='LEAVE_APPROVED',
                title='Leave Approved',
                message=f'Your {l.leave_type.name} request from {l.start_date} to {l.end_date} has been approved.',
                reference_id=str(l.id)
            ))

        AuditService.log(
            action='leave_request_approved',
            actor=request.user,
            target_type='leaverequest',
            target_id=leave.id,
            request=request
        )
        return Response(LeaveRequestSerializer(leave).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if not AuthorizationService.has_permission(request.user, 'leave.reject'):
            return Response(status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            leave = LeaveRequest.objects.select_for_update().get(pk=self.get_object().pk)
            if not request.user.is_superuser:
                if not hasattr(request.user, 'employee'):
                    return Response(status=status.HTTP_403_FORBIDDEN)
                authorized_branches = AuthorizationService.get_authorized_branches(request.user, 'leave.reject')
                if leave.employee.branch not in authorized_branches:
                    return Response(status=status.HTTP_403_FORBIDDEN)

            if leave.status != 'pending':
                return Response({"detail": "Only pending requests can be rejected."}, status=status.HTTP_400_BAD_REQUEST)

            serializer = LeaveRequestReviewSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            leave.status = 'rejected'
            leave.reviewed_by = request.user
            leave.reviewed_at = timezone.now()
            leave.reviewer_comment = serializer.validated_data.get('reviewer_comment', '')
            leave.save()

            transaction.on_commit(lambda l=leave: NotificationService.create_in_app_notification(
                recipient=l.employee.user,
                organization=l.employee.organization,
                notification_type='LEAVE_REJECTED',
                title='Leave Rejected',
                message=f'Your {l.leave_type.name} request from {l.start_date} to {l.end_date} has been rejected.',
                reference_id=str(l.id)
            ))

        AuditService.log(
            action='leave_request_rejected',
            actor=request.user,
            target_type='leaverequest',
            target_id=leave.id,
            request=request
        )
        return Response(LeaveRequestSerializer(leave).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        with transaction.atomic():
            leave = LeaveRequest.objects.select_for_update().get(pk=self.get_object().pk)
            if not request.user.is_superuser:
                if not hasattr(request.user, 'employee'):
                    return Response(status=status.HTTP_403_FORBIDDEN)
                if leave.employee != request.user.employee:
                    authorized_branches = AuthorizationService.get_authorized_branches(request.user, 'leave.cancel')
                    if leave.employee.branch not in authorized_branches:
                        return Response(status=status.HTTP_403_FORBIDDEN)

            if leave.employee != getattr(request.user, 'employee', None):
                if not AuthorizationService.has_permission(request.user, 'leave.cancel'):
                    return Response(status=status.HTTP_403_FORBIDDEN)

            if leave.status != 'pending':
                return Response({"detail": "Only pending requests can be cancelled."}, status=status.HTTP_400_BAD_REQUEST)

            leave.status = 'cancelled'
            leave.save()

            if leave.employee.user != request.user:
                transaction.on_commit(lambda l=leave: NotificationService.create_in_app_notification(
                    recipient=l.employee.user,
                    organization=l.employee.organization,
                    notification_type='LEAVE_CANCELLED',
                    title='Leave Cancelled',
                    message=f'Your {l.leave_type.name} request from {l.start_date} to {l.end_date} has been cancelled by an administrator.',
                    reference_id=str(l.id)
                ))

        AuditService.log(
            action='leave_request_cancelled',
            actor=request.user,
            target_type='leaverequest',
            target_id=leave.id,
            request=request
        )
        return Response(LeaveRequestSerializer(leave).data)
