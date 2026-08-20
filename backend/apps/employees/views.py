from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from apps.authorization.permissions import HasRequiredPermission, IsNetworkAllowed, require_permission
from apps.authorization.services import AuthorizationService
from .models import Employee, WFHRequest
from .serializers import EmployeeSerializer, ProvisionEmployeeSerializer
from apps.notifications.services import NotificationService
from apps.audit.services import AuditService

class EmployeeSelfServiceView(APIView):
    permission_classes = [IsAuthenticated, IsNetworkAllowed]

    def get(self, request, *args, **kwargs):
        try:
            employee = request.user.employee
        except Employee.DoesNotExist:
            return Response({'detail': 'Employee profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = EmployeeSerializer(employee)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        try:
            employee = request.user.employee
        except Employee.DoesNotExist:
            return Response({'detail': 'Employee profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = EmployeeSerializer(employee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        AuditService.log(
            action='employee_updated',
            actor=request.user,
            target_type='employee',
            target_id=employee.id,
            request=request
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

class ProvisionEmployeeView(APIView):
    permission_classes = [HasRequiredPermission, IsNetworkAllowed]
    required_permission = 'employee.create'

    def post(self, request, *args, **kwargs):
        serializer = ProvisionEmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()

        AuditService.log(
            action='employee_created',
            actor=request.user,
            target_type='employee',
            target_id=employee.id,
            request=request
        )

        uid = urlsafe_base64_encode(force_bytes(employee.user.pk))
        token = default_token_generator.make_token(employee.user)

        response_data = {
            'detail': 'Employee provisioned successfully.',
            'employee': EmployeeSerializer(employee).data,
        }

        # Only expose activation secrets in DEBUG mode for local development/testing
        if settings.DEBUG:
            response_data['activation_info'] = {
                'uid': uid,
                'token': token
            }

        email_sent = NotificationService.send_employee_onboarding_email(
            personal_email=employee.personal_email,
            first_name=employee.user.first_name,
            employee_code=employee.employee_code,
            uid=uid,
            token=token
        )
        response_data['onboarding_email_status'] = 'sent' if email_sent else 'failed'

        return Response(response_data, status=status.HTTP_201_CREATED)

class EmployeeManagementViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.action == 'create':
            return ProvisionEmployeeSerializer
        return EmployeeSerializer

    def get_permissions(self):
        permissions = [IsAuthenticated(), IsNetworkAllowed()]
        if self.action in ['list', 'retrieve']:
            permissions.append(require_permission('employee.view')())
        elif self.action == 'create':
            permissions.append(require_permission('employee.create')())
        else:
            permissions.append(require_permission('employee.update')())
        return permissions

    def get_queryset(self):
        # ARCHITECTURAL LIMITATION: Employee model does not have an organization relationship.
        # Returning all employees instead of attempting to scope by organization.
        return Employee.objects.all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()

        AuditService.log(
            action='employee_created',
            actor=request.user,
            target_type='employee',
            target_id=employee.id,
            request=request
        )

        uid = urlsafe_base64_encode(force_bytes(employee.user.pk))
        token = default_token_generator.make_token(employee.user)

        response_data = {
            'detail': 'Employee provisioned successfully.',
            'employee': EmployeeSerializer(employee).data,
        }

        if settings.DEBUG:
            response_data['activation_info'] = {
                'uid': uid,
                'token': token
            }

        email_sent = NotificationService.send_employee_onboarding_email(
            personal_email=employee.personal_email,
            first_name=employee.user.first_name,
            employee_code=employee.employee_code,
            uid=uid,
            token=token
        )
        response_data['onboarding_email_status'] = 'sent' if email_sent else 'failed'

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        if not AuthorizationService.has_permission(request.user, 'employee.status'):
            return Response(status=status.HTTP_403_FORBIDDEN)

        employee = self.get_object()
        user = employee.user

        if user.status == 'active':
            return Response({'detail': 'Employee is already active.'}, status=status.HTTP_400_BAD_REQUEST)

        user.status = 'active'
        user.save()
        AuditService.log(
            action='employee_activated',
            actor=request.user,
            target_type='employee',
            target_id=employee.id,
            request=request
        )
        return Response(EmployeeSerializer(employee).data)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        if not AuthorizationService.has_permission(request.user, 'employee.status'):
            return Response(status=status.HTTP_403_FORBIDDEN)

        employee = self.get_object()
        user = employee.user

        if user == request.user:
            return Response({'detail': 'Cannot deactivate own account.'}, status=status.HTTP_403_FORBIDDEN)

        if user.is_superuser and not request.user.is_superuser:
            return Response({'detail': 'Only superadmin can deactivate a superadmin.'}, status=status.HTTP_403_FORBIDDEN)

        if user.is_superuser:
            active_superadmins = type(user).objects.filter(is_superuser=True, status='active').count()
            if active_superadmins <= 1:
                return Response({'detail': 'Cannot deactivate the last active superadmin.'}, status=status.HTTP_403_FORBIDDEN)

        if user.status == 'inactive':
            return Response({'detail': 'Employee is already deactivated.'}, status=status.HTTP_400_BAD_REQUEST)

        user.status = 'inactive'
        user.save()
        AuditService.log(
            action='employee_deactivated',
            actor=request.user,
            target_type='employee',
            target_id=employee.id,
            request=request
        )
        return Response(EmployeeSerializer(employee).data)

from django.utils import timezone
from .serializers import WFHRequestSerializer, WFHRequestReviewSerializer

class WFHRequestViewSet(viewsets.ModelViewSet):
    serializer_class = WFHRequestSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return WFHRequest.objects.none()
        if AuthorizationService.has_permission(user, 'wfh.view'):
            return WFHRequest.objects.all()
        if hasattr(user, 'employee'):
            return WFHRequest.objects.filter(employee=user.employee)
        return WFHRequest.objects.none()

    def get_permissions(self):
        if self.action == 'create':
            permission = require_permission('wfh.request')
            return [permission()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        wfh = serializer.save(employee=self.request.user.employee)
        AuditService.log(
            action='wfh_request_created',
            actor=self.request.user,
            target_type='wfhrequest',
            target_id=wfh.id,
            request=self.request
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if not AuthorizationService.has_permission(request.user, 'wfh.approve'):
            return Response(status=status.HTTP_403_FORBIDDEN)
        wfh = self.get_object()
        if wfh.employee == getattr(request.user, 'employee', None):
            return Response({"detail": "Cannot approve own request."}, status=status.HTTP_403_FORBIDDEN)
        if wfh.status != 'pending':
            return Response({"detail": "Only pending requests can be approved."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = WFHRequestReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wfh.status = 'approved'
        wfh.reviewed_by = request.user
        wfh.reviewed_at = timezone.now()
        wfh.reviewer_comment = serializer.validated_data.get('reviewer_comment', '')
        wfh.save()
        AuditService.log(
            action=f'wfh_request_{wfh.status}',
            actor=request.user,
            target_type='wfhrequest',
            target_id=wfh.id,
            request=request
        )
        return Response(WFHRequestSerializer(wfh).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if not AuthorizationService.has_permission(request.user, 'wfh.reject'):
            return Response(status=status.HTTP_403_FORBIDDEN)
        wfh = self.get_object()
        if wfh.status != 'pending':
            return Response({"detail": "Only pending requests can be rejected."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = WFHRequestReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wfh.status = 'rejected'
        wfh.reviewed_by = request.user
        wfh.reviewed_at = timezone.now()
        wfh.reviewer_comment = serializer.validated_data.get('reviewer_comment', '')
        wfh.save()
        AuditService.log(
            action=f'wfh_request_{wfh.status}',
            actor=request.user,
            target_type='wfhrequest',
            target_id=wfh.id,
            request=request
        )
        return Response(WFHRequestSerializer(wfh).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        wfh = self.get_object()
        if wfh.employee != getattr(request.user, 'employee', None):
            if not AuthorizationService.has_permission(request.user, 'wfh.cancel'):
                return Response(status=status.HTTP_403_FORBIDDEN)
        if wfh.status != 'pending':
            return Response({"detail": "Only pending requests can be cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        wfh.status = 'cancelled'
        wfh.save()
        AuditService.log(
            action=f'wfh_request_{wfh.status}',
            actor=request.user,
            target_type='wfhrequest',
            target_id=wfh.id,
            request=request
        )
        return Response(WFHRequestSerializer(wfh).data)
