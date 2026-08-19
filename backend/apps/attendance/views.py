from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from apps.authorization.permissions import IsNetworkAllowed
from .models import Attendance
from .serializers import AttendanceSerializer

class AttendanceViewSet(viewsets.GenericViewSet):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated, IsNetworkAllowed]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'employee'):
            return Attendance.objects.filter(employee=user.employee)
        return Attendance.objects.none()

    def list(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='check-in')
    def check_in(self, request):
        if not hasattr(request.user, 'employee'):
            return Response({'detail': 'Employee profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        employee = request.user.employee
        today = timezone.now().date()

        if Attendance.objects.filter(employee=employee, date=today).exists():
            return Response({'detail': 'Check-in already exists for today.'}, status=status.HTTP_400_BAD_REQUEST)

        attendance = Attendance.objects.create(
            employee=employee,
            date=today,
            check_in=timezone.now(),
            status='present'
        )

        serializer = self.get_serializer(attendance)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='check-out')
    def check_out(self, request):
        if not hasattr(request.user, 'employee'):
            return Response({'detail': 'Employee profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        employee = request.user.employee
        today = timezone.now().date()

        try:
            attendance = Attendance.objects.get(employee=employee, date=today)
        except Attendance.DoesNotExist:
            return Response({'detail': 'Cannot check out without a check-in.'}, status=status.HTTP_400_BAD_REQUEST)

        if attendance.check_out:
            return Response({'detail': 'Already checked out for today.'}, status=status.HTTP_400_BAD_REQUEST)

        attendance.check_out = timezone.now()
        attendance.save()

        serializer = self.get_serializer(attendance)
        return Response(serializer.data, status=status.HTTP_200_OK)
