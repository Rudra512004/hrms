from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from apps.authorization.permissions import HasRequiredPermission
from .models import Employee
from .serializers import EmployeeSerializer, ProvisionEmployeeSerializer

class EmployeeSelfServiceView(APIView):
    permission_classes = [IsAuthenticated]

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
        return Response(serializer.data, status=status.HTTP_200_OK)

class ProvisionEmployeeView(APIView):
    permission_classes = [HasRequiredPermission]
    required_permission = 'employee.create'

    def post(self, request, *args, **kwargs):
        serializer = ProvisionEmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()

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

        return Response(response_data, status=status.HTTP_201_CREATED)

from rest_framework import viewsets
from rest_framework.decorators import action
from django.utils import timezone
from .models import WFHRequest
from .serializers import WFHRequestSerializer, WFHRequestReviewSerializer
from apps.authorization.permissions import require_permission
from apps.authorization.services import AuthorizationService

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
        serializer.save(employee=self.request.user.employee)

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
        return Response(WFHRequestSerializer(wfh).data)
