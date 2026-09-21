import mimetypes
from django.http import FileResponse
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from apps.authorization.permissions import HasRequiredPermission, IsNetworkAllowed, require_permission
from apps.authorization.services import AuthorizationService
from apps.audit.services import AuditService
from apps.notifications.services import NotificationService
from .models import Employee, EmploymentStatus, EmployeeLifecycleEvent, WFHRequest, EmployeeDocument
from .serializers import (
    EmployeeSerializer,
    ProvisionEmployeeSerializer,
    EmployeeLifecycleEventSerializer,
    EmployeeTransferSerializer,
    EmployeePromotionSerializer,
    EmployeeExitSerializer,
    EmployeeDocumentSerializer,
    EmployeeDocumentUploadSerializer,
    EmployeeSelfServiceSerializer,
)


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

        serializer = EmployeeSelfServiceSerializer(employee, data=request.data, partial=True)
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
        serializer = ProvisionEmployeeSerializer(data=request.data, context={'request': request})
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
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

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
        elif self.action in [
            'activate', 'deactivate', 'change_employment_status',
            'transfer', 'promote', 'exit', 'reactivate', 'lifecycle_history'
        ]:
            # Action-specific RBAC permissions are enforced in their respective action handlers
            pass
        else:
            permissions.append(require_permission('employee.update')())
        return permissions

    def get_queryset(self):
        user = self.request.user
        qs = Employee.objects.all()
        if user.is_superuser:
            pass
        elif hasattr(user, 'employee'):
            from django.db.models import Q
            authorized_branches = AuthorizationService.get_authorized_branches(user, 'employee.view')
            authorized_teams = AuthorizationService.get_authorized_teams(user, 'employee.view')
            if AuthorizationService.has_permission(user, 'employee.view', branch_id=None, global_only=True):
                qs = qs.filter(
                    Q(branch__in=authorized_branches) |
                    Q(branch__isnull=True, organization=user.employee.organization) |
                    Q(team__in=authorized_teams)
                )
            else:
                qs = qs.filter(Q(branch__in=authorized_branches) | Q(team__in=authorized_teams))
        else:
            return Employee.objects.none()

        branch_id = self.request.query_params.get('branch_id')
        if branch_id:
            qs = qs.filter(branch_id=branch_id)

        return qs

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
        return Response(EmployeeSerializer(employee, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def change_employment_status(self, request, pk=None):
        if not (AuthorizationService.has_permission(request.user, 'employee.manage_status') or request.user.is_superuser):
            return Response(status=status.HTTP_403_FORBIDDEN)

        employee = self.get_object()
        new_status = request.data.get('employment_status')

        if new_status not in [choice[0] for choice in EmploymentStatus.choices]:
            return Response({'detail': 'Invalid employment status.'}, status=status.HTTP_400_BAD_REQUEST)

        old_status = employee.employment_status
        if old_status == EmploymentStatus.EXITED and new_status != EmploymentStatus.EXITED:
            return Response(
                {'detail': 'Exited employee cannot be transitioned via regular status update. Use explicit reactivate workflow.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            if new_status == EmploymentStatus.EXITED:
                user = employee.user
                user.status = 'inactive'
                user.save()
                if not employee.exit_date:
                    employee.exit_date = timezone.now().date()

            employee.employment_status = new_status
            employee.save()

            EmployeeLifecycleEvent.objects.create(
                employee=employee,
                event_type='status_change',
                from_status=old_status,
                to_status=new_status,
                effective_date=timezone.now().date(),
                reason=request.data.get('reason', ''),
                created_by=request.user
            )

            AuditService.log(
                action='employee_employment_status_changed',
                actor=request.user,
                target_type='employee',
                target_id=employee.id,
                metadata={
                    'from_status': old_status,
                    'to_status': new_status,
                },
                request=request
            )

        return Response(EmployeeSerializer(employee, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def transfer(self, request, pk=None):
        if not (
            AuthorizationService.has_permission(request.user, 'employee.transfer') or
            request.user.is_superuser
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        employee = self.get_object()
        if employee.employment_status == EmploymentStatus.EXITED:
            return Response({'detail': 'Cannot transfer an exited employee.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = EmployeeTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        team = serializer.validated_data.get('team')
        dept = serializer.validated_data.get('department')
        branch = serializer.validated_data.get('branch')
        effective_date = serializer.validated_data['effective_date']
        reason = serializer.validated_data.get('reason', '')

        if dept and dept.branch.organization_id != employee.organization_id:
            return Response({'department': 'Department must belong to the same organization.'}, status=status.HTTP_400_BAD_REQUEST)
        if branch and branch.organization_id != employee.organization_id:
            return Response({'branch': 'Branch must belong to the same organization.'}, status=status.HTTP_400_BAD_REQUEST)

        # DESTINATION AUTHORIZATION
        if not request.user.is_superuser:
            has_access = False
            # Check which permission they are using
            if AuthorizationService.has_permission(request.user, 'employee.transfer', branch_id=None, global_only=True):
                has_access = True
            else:
                authorized_branches = AuthorizationService.get_authorized_branches(request.user, 'employee.transfer')
                authorized_teams = AuthorizationService.get_authorized_teams(request.user, 'employee.transfer')

                if branch and branch in authorized_branches:
                    has_access = True
                elif team and team in authorized_teams:
                    has_access = True

            if not has_access:
                return Response({'detail': 'You do not have permission to transfer employees into this organizational unit.'}, status=status.HTTP_403_FORBIDDEN)

        # Restore original consistency checks
        final_team = team if 'team' in serializer.validated_data else employee.team
        final_dept = dept if 'department' in serializer.validated_data else employee.department
        final_branch = branch if 'branch' in serializer.validated_data else employee.branch

        if final_team and final_dept and final_team.department_id != final_dept.id:
            return Response({'team': 'Team must match the employee\'s final department.'}, status=status.HTTP_400_BAD_REQUEST)
        if final_dept and final_branch and final_dept.branch_id != final_branch.id:
            return Response({'department': 'Department must match the employee\'s final branch.'}, status=status.HTTP_400_BAD_REQUEST)

        old_team = employee.team
        old_dept = employee.department
        old_branch = employee.branch

        with transaction.atomic():
            if 'team' in serializer.validated_data:
                employee.team = team
            if 'department' in serializer.validated_data:
                employee.department = dept
            if 'branch' in serializer.validated_data:
                employee.branch = branch
            employee.save()

            EmployeeLifecycleEvent.objects.create(
                employee=employee,
                event_type='transfer',
                from_status=employee.employment_status,
                to_status=employee.employment_status,
                from_department=old_dept,
                to_department=employee.department,
                from_branch=old_branch,
                to_branch=employee.branch,
                effective_date=effective_date,
                reason=reason,
                created_by=request.user
            )

            transaction.on_commit(lambda emp=employee, new_dept=employee.department, new_branch=employee.branch: NotificationService.create_in_app_notification(
                recipient=emp.user,
                organization=emp.organization,
                notification_type='EMPLOYEE_TRANSFER',
                title='Transfer Initiated',
                message=f'You have been transferred to {new_dept.name if new_dept else "a new department"} at {new_branch.name if new_branch else "a new branch"}.',
                reference_id=str(emp.id)
            ))

            AuditService.log(
                action='employee_transferred',
                actor=request.user,
                target_type='employee',
                target_id=employee.id,
                metadata={
                    'from_dept': old_dept.name if old_dept else None,
                    'to_dept': employee.department.name if employee.department else None,
                    'from_branch': old_branch.name if old_branch else None,
                    'to_branch': employee.branch.name if employee.branch else None,
                    'effective_date': str(effective_date),
                },
                request=request
            )

        return Response(EmployeeSerializer(employee, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def promote(self, request, pk=None):
        if not (
            AuthorizationService.has_permission(request.user, 'employee.promote') or
            request.user.is_superuser
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        employee = self.get_object()
        if employee.employment_status == EmploymentStatus.EXITED:
            return Response({'detail': 'Cannot promote an exited employee.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = EmployeePromotionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        designation = serializer.validated_data['designation']
        effective_date = serializer.validated_data['effective_date']
        reason = serializer.validated_data.get('reason', '')
        new_basic_salary = serializer.validated_data.get('new_basic_salary')

        if designation.organization_id != employee.organization_id:
            return Response({'designation': 'Designation must belong to the same organization.'}, status=status.HTTP_400_BAD_REQUEST)

        old_desig = employee.designation

        with transaction.atomic():
            employee.designation = designation
            employee.save()

            if new_basic_salary is not None:
                from apps.payroll.models import CompensationHistory
                CompensationHistory.objects.filter(
                    employee=employee,
                    effective_to__isnull=True,
                    effective_from__lt=effective_date,
                ).update(effective_to=effective_date)

                CompensationHistory.objects.create(
                    employee=employee,
                    effective_from=effective_date,
                    basic_salary=new_basic_salary,
                    created_by=request.user
                )

            EmployeeLifecycleEvent.objects.create(
                employee=employee,
                event_type='promotion',
                from_status=employee.employment_status,
                to_status=employee.employment_status,
                from_designation=old_desig,
                to_designation=employee.designation,
                effective_date=effective_date,
                reason=reason,
                created_by=request.user
            )

            transaction.on_commit(lambda emp=employee, new_desig=employee.designation: NotificationService.create_in_app_notification(
                recipient=emp.user,
                organization=emp.organization,
                notification_type='EMPLOYEE_PROMOTION',
                title='Promotion',
                message=f'You have been promoted to {new_desig.name}.',
                reference_id=str(emp.id)
            ))

            AuditService.log(
                action='employee_promoted',
                actor=request.user,
                target_type='employee',
                target_id=employee.id,
                metadata={
                    'from_designation': old_desig.name if old_desig else None,
                    'to_designation': designation.name,
                    'new_salary': str(new_basic_salary) if new_basic_salary is not None else None,
                    'effective_date': str(effective_date),
                },
                request=request
            )

        return Response(EmployeeSerializer(employee, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def exit(self, request, pk=None):
        if not (
            AuthorizationService.has_permission(request.user, 'employee.exit') or
            AuthorizationService.has_permission(request.user, 'employee.manage_status') or
            request.user.is_superuser
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        employee = self.get_object()
        if employee.employment_status == EmploymentStatus.EXITED:
            return Response({'detail': 'Employee is already exited.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = EmployeeExitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        exit_type = serializer.validated_data['exit_type']
        exit_date = serializer.validated_data['exit_date']
        exit_reason = serializer.validated_data.get('exit_reason', '')
        resignation_date = serializer.validated_data.get('resignation_date')
        notice_start = serializer.validated_data.get('notice_period_start')
        notice_end = serializer.validated_data.get('notice_period_end')
        set_notice_status = serializer.validated_data.get('set_notice_status', False)

        old_status = employee.employment_status

        with transaction.atomic():
            if set_notice_status:
                employee.employment_status = EmploymentStatus.ON_NOTICE
                employee.resignation_date = resignation_date or timezone.now().date()
                employee.notice_period_start = notice_start or timezone.now().date()
                employee.notice_period_end = notice_end or exit_date
                employee.exit_date = exit_date
                employee.exit_reason = exit_reason
                employee.save()

                EmployeeLifecycleEvent.objects.create(
                    employee=employee,
                    event_type='resignation',
                    from_status=old_status,
                    to_status=EmploymentStatus.ON_NOTICE,
                    effective_date=employee.notice_period_start,
                    reason=exit_reason,
                    created_by=request.user
                )

                AuditService.log(
                    action='employee_resigned',
                    actor=request.user,
                    target_type='employee',
                    target_id=employee.id,
                    metadata={
                        'resignation_date': str(employee.resignation_date),
                        'exit_date': str(exit_date),
                        'exit_reason': exit_reason,
                    },
                    request=request
                )
            else:
                employee.employment_status = EmploymentStatus.EXITED
                employee.exit_date = exit_date
                employee.exit_reason = exit_reason
                if resignation_date:
                    employee.resignation_date = resignation_date
                if notice_start:
                    employee.notice_period_start = notice_start
                if notice_end:
                    employee.notice_period_end = notice_end
                employee.save()

                user = employee.user
                user.status = 'inactive'
                user.save()

                EmployeeLifecycleEvent.objects.create(
                    employee=employee,
                    event_type='exit',
                    from_status=old_status,
                    to_status=EmploymentStatus.EXITED,
                    effective_date=exit_date,
                    reason=exit_reason,
                    created_by=request.user
                )

                AuditService.log(
                    action='employee_exited',
                    actor=request.user,
                    target_type='employee',
                    target_id=employee.id,
                    metadata={
                        'exit_type': exit_type,
                        'exit_date': str(exit_date),
                        'exit_reason': exit_reason,
                    },
                    request=request
                )

        return Response(EmployeeSerializer(employee, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        if not (AuthorizationService.has_permission(request.user, 'employee.manage_status') or request.user.is_superuser):
            return Response(status=status.HTTP_403_FORBIDDEN)

        employee = self.get_object()
        if employee.employment_status != EmploymentStatus.EXITED:
            return Response({'detail': 'Only exited employees can be reactivated.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            old_status = employee.employment_status
            employee.employment_status = EmploymentStatus.ACTIVE
            employee.exit_date = None
            employee.exit_reason = ''
            employee.resignation_date = None
            employee.notice_period_start = None
            employee.notice_period_end = None
            employee.save()

            user = employee.user
            user.status = 'active'
            user.save()

            EmployeeLifecycleEvent.objects.create(
                employee=employee,
                event_type='reactivation',
                from_status=old_status,
                to_status=EmploymentStatus.ACTIVE,
                effective_date=timezone.now().date(),
                reason=request.data.get('reason', 'Reactivated via explicit workflow'),
                created_by=request.user
            )

            AuditService.log(
                action='employee_reactivated',
                actor=request.user,
                target_type='employee',
                target_id=employee.id,
                request=request
            )

        return Response(EmployeeSerializer(employee, context={'request': request}).data)

    @action(detail=True, methods=['get'])
    def lifecycle_history(self, request, pk=None):
        if not (
            AuthorizationService.has_permission(request.user, 'employee.lifecycle.view') or
            AuthorizationService.has_permission(request.user, 'employee.view') or
            request.user.is_superuser
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        employee = self.get_object()
        events = employee.lifecycle_events.all().select_related(
            'from_department', 'to_department',
            'from_branch', 'to_branch',
            'from_designation', 'to_designation',
            'created_by'
        )
        serializer = EmployeeLifecycleEventSerializer(events, many=True)
        return Response(serializer.data)

from .serializers import WFHRequestSerializer, WFHRequestReviewSerializer

class WFHRequestViewSet(viewsets.ModelViewSet):
    serializer_class = WFHRequestSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return WFHRequest.objects.none()
        if user.is_superuser:
            qs = WFHRequest.objects.all()
            org_id = self.request.query_params.get('organization')
            if org_id:
                qs = qs.filter(employee__organization_id=org_id)
            return qs
        if AuthorizationService.has_permission(user, 'wfh.view'):
            emp = getattr(user, 'employee', None)
            if emp and emp.organization_id:
                return WFHRequest.objects.filter(employee__organization=emp.organization)
            return WFHRequest.objects.none()
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


class EmployeeDocumentViewSet(viewsets.GenericViewSet):
    """
    Manages employee document uploads.

    All file downloads are served through backend-authenticated endpoints.
    No public MEDIA_URL exposure.
    Organization isolation (IDOR protection) is enforced in get_queryset().
    """

    def get_queryset(self):
        user = self.request.user
        qs = EmployeeDocument.objects.all()

        if user.is_superuser:
            pass
        elif hasattr(user, 'employee'):
            from django.db.models import Q
            authorized_branches = AuthorizationService.get_authorized_branches(user, 'employee.document.view')
            authorized_teams = AuthorizationService.get_authorized_teams(user, 'employee.document.view')
            if AuthorizationService.has_permission(user, 'employee.document.view', branch_id=None, global_only=True):
                qs = qs.filter(
                    Q(employee=user.employee) |
                    Q(employee__branch__in=authorized_branches) |
                    Q(employee__branch__isnull=True, employee__organization=user.employee.organization) |
                    Q(employee__team__in=authorized_teams)
                )
            else:
                qs = qs.filter(Q(employee=user.employee) | Q(employee__branch__in=authorized_branches) | Q(employee__team__in=authorized_teams))
        else:
            return EmployeeDocument.objects.none()

        employee_id = self.request.query_params.get('employee')
        if employee_id:
            qs = qs.filter(employee_id=employee_id)

        return qs.select_related('employee', 'uploaded_by')

    def list(self, request):
        """List documents. Requires employee.document.view permission."""
        if not (
            AuthorizationService.has_permission(request.user, 'employee.document.view') or
            request.user.is_superuser
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        queryset = self.get_queryset()
        serializer = EmployeeDocumentSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Retrieve document metadata. Returns 404 for cross-org (IDOR protection)."""
        try:
            doc = self.get_queryset().get(pk=pk)
        except EmployeeDocument.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Employees may view their own documents
        is_own = (
            hasattr(request.user, 'employee') and
            doc.employee_id == request.user.employee.id
        )
        if not is_own and not (
            AuthorizationService.has_permission(request.user, 'employee.document.view') or
            request.user.is_superuser
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = EmployeeDocumentSerializer(doc)
        return Response(serializer.data)

    def create(self, request):
        """Upload a document. Requires employee.document.upload permission."""
        if not (
            AuthorizationService.has_permission(request.user, 'employee.document.upload') or
            request.user.is_superuser
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = EmployeeDocumentUploadSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        # Branch isolation: ensure the target employee belongs to an authorized branch
        target_employee = serializer.validated_data['employee']

        if not request.user.is_superuser:
            if not hasattr(request.user, 'employee'):
                return Response(status=status.HTTP_403_FORBIDDEN)

            authorized_branches = AuthorizationService.get_authorized_branches(request.user, 'employee.document.upload')

            can_upload = False
            if target_employee.branch in authorized_branches:
                can_upload = True
            elif target_employee.branch is None and target_employee.organization == request.user.employee.organization:
                if AuthorizationService.has_permission(request.user, 'employee.document.upload', branch_id=None):
                    can_upload = True

            if not can_upload:
                return Response(
                    {'detail': 'Cannot upload documents for an employee in this branch.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        document = serializer.save()

        AuditService.log(
            action='employee_document_uploaded',
            actor=request.user,
            target_type='employeedocument',
            target_id=document.id,
            metadata={
                'employee_id': target_employee.id,
                'document_name': document.document_name,
                'document_type': document.document_type,
                'file_size': document.file_size,
            },
            request=request
        )

        return Response(EmployeeDocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        """Delete a document (db record + file). Requires employee.document.delete."""
        if not (
            AuthorizationService.has_permission(request.user, 'employee.document.delete') or
            request.user.is_superuser
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            doc = self.get_queryset().get(pk=pk)
        except EmployeeDocument.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        doc_id = doc.id
        doc_name = doc.document_name
        emp_id = doc.employee_id

        # Delete the physical file from storage
        if doc.file and doc.file.name:
            try:
                doc.file.delete(save=False)
            except Exception:
                pass  # Log but don't block db cleanup

        doc.delete()

        AuditService.log(
            action='employee_document_deleted',
            actor=request.user,
            target_type='employeedocument',
            target_id=doc_id,
            metadata={
                'employee_id': emp_id,
                'document_name': doc_name,
            },
            request=request
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Serve file as attachment. Auth + RBAC required."""
        try:
            doc = self.get_queryset().get(pk=pk)
        except EmployeeDocument.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        is_own = (
            hasattr(request.user, 'employee') and
            doc.employee_id == request.user.employee.id
        )
        if not is_own and not (
            AuthorizationService.has_permission(request.user, 'employee.document.view') or
            request.user.is_superuser
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            file_handle = doc.file.open('rb')
        except (FileNotFoundError, OSError):
            return Response({'detail': 'File not found on storage.'}, status=status.HTTP_404_NOT_FOUND)

        content_type = doc.mime_type or mimetypes.guess_type(doc.file.name)[0] or 'application/octet-stream'
        response = FileResponse(file_handle, content_type=content_type, as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{doc.document_name}"'

        AuditService.log(
            action='employee_document_downloaded',
            actor=request.user,
            target_type='employeedocument',
            target_id=doc.id,
            metadata={'employee_id': doc.employee_id, 'document_name': doc.document_name},
            request=request
        )

        return response

    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """Serve file inline for browser preview. Auth + RBAC required."""
        try:
            doc = self.get_queryset().get(pk=pk)
        except EmployeeDocument.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        is_own = (
            hasattr(request.user, 'employee') and
            doc.employee_id == request.user.employee.id
        )
        if not is_own and not (
            AuthorizationService.has_permission(request.user, 'employee.document.view') or
            request.user.is_superuser
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            file_handle = doc.file.open('rb')
        except (FileNotFoundError, OSError):
            return Response({'detail': 'File not found on storage.'}, status=status.HTTP_404_NOT_FOUND)

        content_type = doc.mime_type or mimetypes.guess_type(doc.file.name)[0] or 'application/octet-stream'
        response = FileResponse(file_handle, content_type=content_type, as_attachment=False)
        response['Content-Disposition'] = f'inline; filename="{doc.document_name}"'

        return response
