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
