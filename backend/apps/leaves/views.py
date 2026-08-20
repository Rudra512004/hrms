from rest_framework import viewsets, status
from apps.audit.services import AuditService
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from apps.authorization.permissions import require_permission
from apps.authorization.services import AuthorizationService
from .models import LeaveType, LeaveBalance, LeaveRequest
from .serializers import LeaveTypeSerializer, LeaveBalanceSerializer, LeaveRequestSerializer, LeaveRequestReviewSerializer

class LeaveTypeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeaveTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # ARCHITECTURAL LIMITATION: Employee model does not have an organization relationship.
        return LeaveType.objects.filter(is_active=True)

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
        if AuthorizationService.has_permission(user, 'leave.view'):
            return LeaveRequest.objects.all()
        if hasattr(user, 'employee'):
            return LeaveRequest.objects.filter(employee=user.employee)
        return LeaveRequest.objects.none()

    def get_permissions(self):
        permissions = [IsAuthenticated()]
        if self.action == 'create':
            permission_class = require_permission('leave.request')
            permissions.append(permission_class())
        return permissions

    def perform_create(self, serializer):
        leave = serializer.save(employee=self.request.user.employee)
        AuditService.log(
            action='leave_request_created',
            actor=self.request.user,
            target_type='leaverequest',
            target_id=leave.id,
            request=self.request
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if not AuthorizationService.has_permission(request.user, 'leave.approve'):
            return Response(status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            leave = self.get_object()
            if leave.employee == getattr(request.user, 'employee', None):
                return Response({"detail": "Cannot approve own request."}, status=status.HTTP_403_FORBIDDEN)
            if leave.status != 'pending':
                return Response({"detail": "Only pending requests can be approved."}, status=status.HTTP_400_BAD_REQUEST)

            serializer = LeaveRequestReviewSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Check balance
            try:
                balance = LeaveBalance.objects.get(employee=leave.employee, leave_type=leave.leave_type)
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

        return Response(LeaveRequestSerializer(leave).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if not AuthorizationService.has_permission(request.user, 'leave.reject'):
            return Response(status=status.HTTP_403_FORBIDDEN)

        leave = self.get_object()
        if leave.status != 'pending':
            return Response({"detail": "Only pending requests can be rejected."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = LeaveRequestReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        leave.status = 'rejected'
        leave.reviewed_by = request.user
        leave.reviewed_at = timezone.now()
        leave.reviewer_comment = serializer.validated_data.get('reviewer_comment', '')
        leave.save()
        return Response(LeaveRequestSerializer(leave).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        leave = self.get_object()
        if leave.employee != getattr(request.user, 'employee', None):
            if not AuthorizationService.has_permission(request.user, 'leave.cancel'):
                return Response(status=status.HTTP_403_FORBIDDEN)

        if leave.status != 'pending':
            return Response({"detail": "Only pending requests can be cancelled."}, status=status.HTTP_400_BAD_REQUEST)

        leave.status = 'cancelled'
        leave.save()
        return Response(LeaveRequestSerializer(leave).data)
