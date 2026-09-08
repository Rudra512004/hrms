"""
Views for Payroll Reporting & Reconciliation.

Enforces:
- Organization isolation
- Dynamic RBAC (payroll.view_reports / payroll.view)
- Sensitive salary protection (payroll.view_sensitive)
- IDOR prevention on period, branch, and department IDs
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.authorization.services import AuthorizationService
from apps.organization.models import Branch, Department
from .models import PayrollPeriod
from .services_reporting import (
    get_period_summary,
    get_reconciliation_records,
    get_organization_breakdown,
    get_payroll_exceptions,
)
from .serializers_reporting import (
    PeriodSummaryResponseSerializer,
    ReconciliationRecordSerializer,
    OrganizationBreakdownResponseSerializer,
    PayrollExceptionItemSerializer,
)


def _employee_org(request):
    try:
        return request.user.employee.organization
    except Exception:
        return None


def _check_reports_permission(user):
    """Returns True if user has report viewing capability."""
    return (
        AuthorizationService.has_permission(user, 'payroll.view_reports')
        or AuthorizationService.has_permission(user, 'payroll.view')
    )


class PayrollReportingViewSet(viewsets.ViewSet):
    """
    Administrative reporting and reconciliation endpoints.
    Endpoints:
    - /period-summary/
    - /reconciliation/
    - /organization-breakdown/
    - /exceptions/
    """
    permission_classes = [IsAuthenticated]

    def _resolve_period_and_org(self, request):
        """
        Validates the organization and resolves the requested PayrollPeriod.
        Returns (period, org, error_response).
        """
        org = _employee_org(request)
        if org is None:
            return None, None, Response({'detail': 'Organization not found.'}, status=status.HTTP_403_FORBIDDEN)

        if not _check_reports_permission(request.user):
            return None, None, Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        period_id = request.query_params.get('period')
        if period_id:
            period = PayrollPeriod.objects.filter(id=period_id, organization=org).first()
            if period is None:
                return None, None, Response({'detail': 'Payroll period not found.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            period = PayrollPeriod.objects.filter(organization=org).order_by('-year', '-month').first()
            if period is None:
                return None, None, Response({'detail': 'No payroll periods found.'}, status=status.HTTP_404_NOT_FOUND)

        return period, org, None

    @action(detail=False, methods=['get'], url_path='period-summary')
    def period_summary(self, request):
        period, org, err = self._resolve_period_and_org(request)
        if err:
            return err

        has_sensitive = AuthorizationService.has_permission(request.user, 'payroll.view_sensitive')
        data = get_period_summary(period, has_sensitive_perm=has_sensitive)
        serializer = PeriodSummaryResponseSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='reconciliation')
    def reconciliation(self, request):
        period, org, err = self._resolve_period_and_org(request)
        if err:
            return err

        branch_id = request.query_params.get('branch')
        if branch_id:
            if not Branch.objects.filter(id=branch_id, organization=org).exists():
                return Response({'detail': 'Branch not found.'}, status=status.HTTP_404_NOT_FOUND)

        department_id = request.query_params.get('department')
        if department_id:
            if not Department.objects.filter(id=department_id, organization=org).exists():
                return Response({'detail': 'Department not found.'}, status=status.HTTP_404_NOT_FOUND)

        search = request.query_params.get('search')
        has_sensitive = AuthorizationService.has_permission(request.user, 'payroll.view_sensitive')

        records = get_reconciliation_records(
            period=period,
            branch_id=branch_id,
            department_id=department_id,
            search=search,
            has_sensitive_perm=has_sensitive,
        )

        serializer = ReconciliationRecordSerializer(records, many=True)
        return Response({
            'period_id': period.id,
            'count': len(records),
            'records': serializer.data,
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='organization-breakdown')
    def organization_breakdown(self, request):
        period, org, err = self._resolve_period_and_org(request)
        if err:
            return err

        has_sensitive = AuthorizationService.has_permission(request.user, 'payroll.view_sensitive')
        data = get_organization_breakdown(period, has_sensitive_perm=has_sensitive)
        serializer = OrganizationBreakdownResponseSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='exceptions')
    def exceptions(self, request):
        period, org, err = self._resolve_period_and_org(request)
        if err:
            return err

        exceptions_list = get_payroll_exceptions(period)
        serializer = PayrollExceptionItemSerializer(exceptions_list, many=True)
        return Response({
            'period_id': period.id,
            'total_exceptions': len(exceptions_list),
            'exceptions': serializer.data,
        }, status=status.HTTP_200_OK)
