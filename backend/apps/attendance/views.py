from rest_framework import viewsets, status
from apps.audit.services import AuditService
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.db.models import Q
from datetime import timedelta
from apps.authorization.permissions import IsNetworkAllowed, require_permission
from .models import Attendance, AttendanceBreak, Holiday, Shift
from .serializers import AttendanceSerializer, HolidaySerializer, ShiftSerializer

from .utils import calculate_haversine_distance

class AttendanceViewSet(viewsets.GenericViewSet):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]

    def _validate_location(self, request, employee):
        from apps.authorization.network import NetworkAccessService

        if getattr(request.user, 'is_superuser', False):
            return None # Superusers bypass location restrictions

        # Determine Attendance Policy
        # Using getattr to safely handle case where branch lacks a policy (fallback to strict defaults)
        branch = employee.branch
        policy = getattr(branch, 'attendance_policy', None)

        is_gps_enabled = policy.is_office_gps_enabled if policy else True
        is_ip_enabled = policy.is_office_ip_enabled if policy else False
        is_wfh_enabled = policy.is_wfh_enabled if policy else False
        wfh_bypasses = policy.wfh_bypasses_office_restrictions if policy else False

        # 1. WFH Bypass
        if is_wfh_enabled and wfh_bypasses and NetworkAccessService.is_wfh_active(employee):
            return None # Bypass office restrictions

        # Extract GPS data if provided
        lat = request.data.get('latitude')
        lon = request.data.get('longitude')
        accuracy = request.data.get('accuracy')

        try:
            if lat is not None and lon is not None:
                lat = float(lat)
                lon = float(lon)
            if accuracy is not None:
                accuracy = float(accuracy)
        except ValueError:
            return Response({'detail': 'Invalid location data.'}, status=status.HTTP_400_BAD_REQUEST)

        if accuracy is not None and accuracy > 100.0:
            return Response({'detail': 'POOR_GPS_ACCURACY'}, status=status.HTTP_400_BAD_REQUEST)

        branch = employee.branch

        # 2. IP Enforcement
        if is_ip_enabled:
            ip = NetworkAccessService.get_client_ip(request)
            if not NetworkAccessService.is_office_network_allowed(ip, employee.organization):
                return Response({'detail': 'ATTENDANCE_OUTSIDE_OFFICE_NETWORK'}, status=status.HTTP_403_FORBIDDEN)

        # 3. GPS Enforcement
        if is_gps_enabled:
            if not branch:
                return Response({'detail': 'ATTENDANCE_OUTSIDE_GEOFENCE'}, status=status.HTTP_403_FORBIDDEN)
            if branch.latitude is None or branch.longitude is None:
                return Response({'detail': 'ATTENDANCE_OUTSIDE_GEOFENCE'}, status=status.HTTP_403_FORBIDDEN)
            if not branch.is_active:
                return Response({'detail': 'Assigned branch is inactive.'}, status=status.HTTP_400_BAD_REQUEST)
            if lat is None or lon is None:
                return Response({'detail': 'Location data is required for branch employees.'}, status=status.HTTP_400_BAD_REQUEST)

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
        if getattr(employee, 'employment_status', None) == 'exited':
            return Response({'detail': 'Exited employees cannot record attendance.'}, status=status.HTTP_400_BAD_REQUEST)

        today = timezone.now().date()

        loc = self._validate_location(request, employee)
        if isinstance(loc, Response):
            return loc

        from .services import AttendanceCalculationService
        shift = AttendanceCalculationService.resolve_scheduled_shift(employee, today)
        check_in_time = timezone.now()
        is_late = AttendanceCalculationService.is_late_check_in(shift, check_in_time, target_date=today)

        try:
            with transaction.atomic():
                if Attendance.objects.filter(employee=employee, date=today).exists():
                    return Response({'detail': 'Check-in already exists for today.'}, status=status.HTTP_400_BAD_REQUEST)

                attendance = Attendance.objects.create(
                    employee=employee,
                    date=today,
                    check_in=check_in_time,
                    status='present',
                    is_late=is_late,
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
        except IntegrityError:
            return Response({'detail': 'Check-in already exists for today.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(attendance)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='check-out')
    def check_out(self, request):
        if not hasattr(request.user, 'employee'):
            return Response({'detail': 'Employee profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        employee = request.user.employee
        if getattr(employee, 'employment_status', None) == 'exited':
            return Response({'detail': 'Exited employees cannot record attendance.'}, status=status.HTTP_400_BAD_REQUEST)

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
            attendance.productive_work_duration = max(timedelta(0), productive)

            from .services import AttendanceCalculationService
            attendance.status = AttendanceCalculationService.determine_attendance_status(attendance)

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

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from apps.common.pagination import StandardResultsSetPagination
from .filters import AttendanceFilter, HolidayFilter

class AttendanceManagementViewSet(viewsets.GenericViewSet):
    serializer_class = AttendanceSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = AttendanceFilter
    ordering_fields = ['date', 'check_in']
    ordering = ['-date', '-check_in']

    def get_permissions(self):
        return [IsAuthenticated(), IsNetworkAllowed(), require_permission('attendance.view_all')()]

    def get_queryset(self):
        user = self.request.user
        qs = Attendance.objects.all()
        if user.is_superuser:
            pass
        elif hasattr(user, 'employee') and user.employee:
            from apps.authorization.services import AuthorizationService
            authorized_branches = AuthorizationService.get_authorized_branches(user, 'attendance.view_all')
            authorized_teams = AuthorizationService.get_authorized_teams(user, 'attendance.view_all')

            qs = qs.filter(
                Q(employee__branch__in=authorized_branches) |
                Q(employee__team__in=authorized_teams)
            )
        else:
            return Attendance.objects.none()

        branch_id = self.request.query_params.get('branch_id')
        if branch_id:
            qs = qs.filter(employee__branch_id=branch_id)

        team_id = self.request.query_params.get('team_id')
        if team_id:
            qs = qs.filter(employee__team_id=team_id)

        date_param = self.request.query_params.get('date')
        if date_param:
            qs = qs.filter(date=date_param)

        return qs.select_related('employee__user', 'employee__branch', 'employee__department', 'employee__team').prefetch_related('breaks').distinct()

    def list(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class HolidayViewSet(viewsets.ModelViewSet):
    serializer_class = HolidaySerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = HolidayFilter
    search_fields = ['name']
    ordering_fields = ['date']
    ordering = ['date']

    def get_queryset(self):
        user = self.request.user
        qs = Holiday.objects.all()
        if user.is_superuser:
            pass
        elif hasattr(user, 'employee') and user.employee:
            from apps.authorization.services import AuthorizationService
            perm = 'holiday.view' if self.action in ['list', 'retrieve'] else 'holiday.manage'
            authorized_branches = AuthorizationService.get_authorized_branches(user, perm)
            qs = qs.filter(branch__in=authorized_branches)
        else:
            return Holiday.objects.none()

        branch_id = self.request.query_params.get('branch_id')
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        return qs

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('holiday.view')
        else:
            permission = require_permission('holiday.manage')
        return [IsAuthenticated(), permission()]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        branch = serializer.validated_data.get('branch')
        if not branch:
            raise ValidationError({"branch": "Branch is required."})
        user = self.request.user
        if not user.is_superuser:
            if hasattr(user, 'employee') and user.employee and branch.organization_id != user.employee.organization_id:
                raise ValidationError({"branch": "Cannot create holiday for another organization."})
            from apps.authorization.services import AuthorizationService
            if not AuthorizationService.has_permission(user, 'holiday.manage', branch.id):
                raise ValidationError({"branch": "You do not have permission to manage holidays for this branch."})
        serializer.save()

    def perform_update(self, serializer):
        from rest_framework.exceptions import ValidationError
        instance = serializer.instance
        user = self.request.user
        if not user.is_superuser:
            from apps.authorization.services import AuthorizationService
            if not AuthorizationService.has_permission(user, 'holiday.manage', instance.branch_id):
                raise ValidationError({"branch": "You do not have permission to manage holidays for this branch."})
            target_branch = serializer.validated_data.get('branch')
            if target_branch and target_branch != instance.branch:
                if hasattr(user, 'employee') and user.employee and target_branch.organization_id != user.employee.organization_id:
                    raise ValidationError({"branch": "Cannot move holiday to another organization."})
                if not AuthorizationService.has_permission(user, 'holiday.manage', target_branch.id):
                    raise ValidationError({"branch": "You do not have permission to manage holidays for the target branch."})
        serializer.save()

    def perform_destroy(self, instance):
        from rest_framework.exceptions import ValidationError
        user = self.request.user
        if not user.is_superuser:
            from apps.authorization.services import AuthorizationService
            if not AuthorizationService.has_permission(user, 'holiday.manage', instance.branch_id):
                raise ValidationError({"branch": "You do not have permission to delete holidays for this branch."})
        instance.delete()

class ShiftViewSet(viewsets.ModelViewSet):
    serializer_class = ShiftSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Shift.objects.all()
        if user.is_superuser:
            pass
        elif hasattr(user, 'employee') and user.employee:
            from apps.authorization.services import AuthorizationService
            perm = 'shift.view' if self.action in ['list', 'retrieve'] else 'shift.manage'
            authorized_branches = AuthorizationService.get_authorized_branches(user, perm)
            qs = qs.filter(branch__in=authorized_branches)
        else:
            return Shift.objects.none()

        branch_id = self.request.query_params.get('branch_id')
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        return qs

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission = require_permission('shift.view')
        else:
            permission = require_permission('shift.manage')
        return [IsAuthenticated(), permission()]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        branch = serializer.validated_data.get('branch')
        if not branch:
            raise ValidationError({"branch": "Branch is required."})
        user = self.request.user
        if not user.is_superuser:
            if hasattr(user, 'employee') and user.employee and branch.organization_id != user.employee.organization_id:
                raise ValidationError({"branch": "Cannot create shift for another organization."})
            from apps.authorization.services import AuthorizationService
            if not AuthorizationService.has_permission(user, 'shift.manage', branch.id):
                raise ValidationError({"branch": "You do not have permission to manage shifts for this branch."})
        serializer.save()

    def perform_update(self, serializer):
        from rest_framework.exceptions import ValidationError
        instance = serializer.instance
        user = self.request.user
        if not user.is_superuser:
            from apps.authorization.services import AuthorizationService
            if not AuthorizationService.has_permission(user, 'shift.manage', instance.branch_id):
                raise ValidationError({"branch": "You do not have permission to manage shifts for this branch."})
            target_branch = serializer.validated_data.get('branch')
            if target_branch and target_branch != instance.branch:
                if hasattr(user, 'employee') and user.employee and target_branch.organization_id != user.employee.organization_id:
                    raise ValidationError({"branch": "Cannot move shift to another organization."})
                if not AuthorizationService.has_permission(user, 'shift.manage', target_branch.id):
                    raise ValidationError({"branch": "You do not have permission to manage shifts for the target branch."})
        serializer.save()

    def perform_destroy(self, instance):
        from rest_framework.exceptions import ValidationError
        user = self.request.user
        if not user.is_superuser:
            from apps.authorization.services import AuthorizationService
            if not AuthorizationService.has_permission(user, 'shift.manage', instance.branch_id):
                raise ValidationError({"branch": "You do not have permission to delete shifts for this branch."})
        instance.delete()
