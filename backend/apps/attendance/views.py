from rest_framework import viewsets, status
from apps.audit.services import AuditService
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from apps.authorization.permissions import IsNetworkAllowed
from .models import Attendance, AttendanceBreak
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

        with transaction.atomic():
            if Attendance.objects.filter(employee=employee, date=today).exists():
                return Response({'detail': 'Check-in already exists for today.'}, status=status.HTTP_400_BAD_REQUEST)

            attendance = Attendance.objects.create(
                employee=employee,
                date=today,
                check_in=timezone.now(),
                status='present'
            )
            AuditService.log(
                action='check-in',
                actor=request.user,
                target_type='attendance',
                target_id=attendance.id,
                request=request
            )

        serializer = self.get_serializer(attendance)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='check-out')
    def check_out(self, request):
        if not hasattr(request.user, 'employee'):
            return Response({'detail': 'Employee profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        employee = request.user.employee
        today = timezone.now().date()

        with transaction.atomic():
            try:
                attendance = Attendance.objects.select_for_update().get(employee=employee, date=today)
            except Attendance.DoesNotExist:
                return Response({'detail': 'Cannot check out without a check-in.'}, status=status.HTTP_400_BAD_REQUEST)

            if attendance.check_out:
                return Response({'detail': 'Already checked out for today.'}, status=status.HTTP_400_BAD_REQUEST)

            if attendance.breaks.filter(ended_at__isnull=True).exists():
                return Response({'detail': 'End the active break before checking out.'}, status=status.HTTP_400_BAD_REQUEST)

            now = timezone.now()
            attendance.check_out = now
            
            # Calculate total break duration
            total_break = timedelta(0)
            for b in attendance.breaks.all():
                if b.ended_at:
                    total_break += (b.ended_at - b.started_at)
            
            attendance.total_break_duration = total_break
            productive = (now - attendance.check_in) - total_break
            attendance.productive_work_duration = productive

            attendance.save()

            AuditService.log(
                action='check-out',
                actor=request.user,
                target_type='attendance',
                target_id=attendance.id,
                request=request
            )

        serializer = self.get_serializer(attendance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='start-break')
    def start_break(self, request):
        if not hasattr(request.user, 'employee'):
            return Response({'detail': 'Employee profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        employee = request.user.employee
        today = timezone.now().date()

        with transaction.atomic():
            try:
                attendance = Attendance.objects.select_for_update().get(employee=employee, date=today)
            except Attendance.DoesNotExist:
                return Response({'detail': 'Cannot start a break without checking in.'}, status=status.HTTP_400_BAD_REQUEST)

            if attendance.check_out:
                return Response({'detail': 'Cannot start a break after checking out.'}, status=status.HTTP_400_BAD_REQUEST)

            if attendance.breaks.filter(ended_at__isnull=True).exists():
                return Response({'detail': 'Already on a break.'}, status=status.HTTP_400_BAD_REQUEST)

            b = AttendanceBreak.objects.create(
                attendance=attendance,
                started_at=timezone.now()
            )
            
            AuditService.log(
                action='break_started',
                actor=request.user,
                target_type='attendance',
                target_id=attendance.id,
                request=request
            )

        serializer = self.get_serializer(attendance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='end-break')
    def end_break(self, request):
        if not hasattr(request.user, 'employee'):
            return Response({'detail': 'Employee profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        employee = request.user.employee
        today = timezone.now().date()

        with transaction.atomic():
            try:
                attendance = Attendance.objects.select_for_update().get(employee=employee, date=today)
            except Attendance.DoesNotExist:
                return Response({'detail': 'No active attendance found.'}, status=status.HTTP_400_BAD_REQUEST)

            active_breaks = attendance.breaks.filter(ended_at__isnull=True)
            if not active_breaks.exists():
                return Response({'detail': 'No active break to end.'}, status=status.HTTP_400_BAD_REQUEST)

            active_break = active_breaks.first()
            active_break.ended_at = timezone.now()
            active_break.save()

            AuditService.log(
                action='break_ended',
                actor=request.user,
                target_type='attendance',
                target_id=attendance.id,
                request=request
            )

        serializer = self.get_serializer(attendance)
        return Response(serializer.data, status=status.HTTP_200_OK)
