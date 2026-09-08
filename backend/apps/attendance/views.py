from rest_framework import viewsets, status
from apps.audit.services import AuditService
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from apps.authorization.permissions import IsNetworkAllowed, require_permission
from .models import Attendance, AttendanceBreak, Holiday, Shift
from .serializers import AttendanceSerializer, HolidaySerializer, ShiftSerializer

from .utils import calculate_haversine_distance

class AttendanceViewSet(viewsets.GenericViewSet):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]

    def _validate_location(self, request, employee):
        lat = request.data.get('latitude')
        lon = request.data.get('longitude')
        accuracy = request.data.get('accuracy')

        if not employee.branch:
            from apps.authorization.network import NetworkAccessService
            if not NetworkAccessService.is_remote_access_allowed(request, request.user):
                return Response({'detail': 'ATTENDANCE_OUTSIDE_GEOFENCE'}, status=status.HTTP_403_FORBIDDEN)
            return None
            
        if lat is None or lon is None:
            return Response({'detail': 'Location data is required for branch employees.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            lat = float(lat)
            lon = float(lon)
            accuracy = float(accuracy) if accuracy is not None else None
        except ValueError:
            return Response({'detail': 'Invalid location data.'}, status=status.HTTP_400_BAD_REQUEST)
            
        if accuracy is not None and accuracy > 100.0:
            return Response({'detail': 'POOR_GPS_ACCURACY'}, status=status.HTTP_400_BAD_REQUEST)
            
        branch = employee.branch
        if not branch.is_active:
            return Response({'detail': 'Assigned branch is inactive.'}, status=status.HTTP_400_BAD_REQUEST)
            
        if branch.latitude is None or branch.longitude is None:
            # If branch has no coordinates configured, fallback to network check
            from apps.authorization.network import NetworkAccessService
            if not NetworkAccessService.is_remote_access_allowed(request, request.user):
                return Response({'detail': 'ATTENDANCE_OUTSIDE_GEOFENCE'}, status=status.HTTP_403_FORBIDDEN)
            return None
            
        dist = calculate_haversine_distance(lat, lon, branch.latitude, branch.longitude)
        if dist > branch.radius:
            return Response({'detail': 'ATTENDANCE_OUTSIDE_GEOFENCE'}, status=status.HTTP_403_FORBIDDEN)
            
        return {'lat': lat, 'lon': lon, 'acc': accuracy}

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

        loc = self._validate_location(request, employee)
        if isinstance(loc, Response):
            return loc

        with transaction.atomic():
            if Attendance.objects.filter(employee=employee, date=today).exists():
                return Response({'detail': 'Check-in already exists for today.'}, status=status.HTTP_400_BAD_REQUEST)

            attendance = Attendance.objects.create(
                employee=employee,
                date=today,
                check_in=timezone.now(),
                status='present',
                check_in_latitude=loc.get('lat') if loc else None,
                check_in_longitude=loc.get('lon') if loc else None,
                check_in_accuracy=loc.get('acc') if loc else None
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

        loc = self._validate_location(request, employee)
        if isinstance(loc, Response):
            return loc

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
            if loc:
                attendance.check_out_latitude = loc.get('lat')
                attendance.check_out_longitude = loc.get('lon')
                attendance.check_out_accuracy = loc.get('acc')
            
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

        loc = self._validate_location(request, employee)
        if isinstance(loc, Response):
            return loc

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

        loc = self._validate_location(request, employee)
        if isinstance(loc, Response):
            return loc

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

class AttendanceManagementViewSet(viewsets.GenericViewSet):
    serializer_class = AttendanceSerializer
    
    def get_permissions(self):
        return [IsAuthenticated(), IsNetworkAllowed(), require_permission('attendance.view_all')()]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Attendance.objects.all()
        if hasattr(user, 'employee') and user.employee.organization_id:
            return Attendance.objects.filter(employee__organization_id=user.employee.organization_id)
        return Attendance.objects.none()

    def list(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class HolidayViewSet(viewsets.ModelViewSet):
    serializer_class = HolidaySerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Holiday.objects.all()
        if hasattr(user, 'employee') and user.employee.organization_id:
            return Holiday.objects.filter(organization_id=user.employee.organization_id)
        return Holiday.objects.none()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('holiday.view')
        else:
            permission = require_permission('holiday.manage')
        return [IsAuthenticated(), permission()]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        if self.request.user.is_superuser and not hasattr(self.request.user, 'employee'):
            from apps.organization.models import Organization
            org = Organization.objects.first()
        else:
            org = self.request.user.employee.organization
        if not org:
            raise ValidationError({"organization": "User does not belong to an organization."})
        serializer.save(organization=org)

class ShiftViewSet(viewsets.ModelViewSet):
    serializer_class = ShiftSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Shift.objects.all()
        if hasattr(user, 'employee') and user.employee.organization_id:
            return Shift.objects.filter(organization_id=user.employee.organization_id)
        return Shift.objects.none()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('shift.view')
        else:
            permission = require_permission('shift.manage')
        return [IsAuthenticated(), permission()]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        if self.request.user.is_superuser and not hasattr(self.request.user, 'employee'):
            from apps.organization.models import Organization
            org = Organization.objects.first()
        else:
            org = self.request.user.employee.organization
        if not org:
            raise ValidationError({"organization": "User does not belong to an organization."})
        serializer.save(organization=org)
