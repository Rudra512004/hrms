from django.http import HttpResponseBadRequest, HttpResponseForbidden
from apps.organization.models import OrganizationMembership, Organization
import logging

logger = logging.getLogger(__name__)

class TenantContextMiddleware:
    """
    Reads the X-Organization-Id header and resolves the tenant context.
    If valid, sets request.organization_context.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization_context = None

        if not request.user.is_authenticated:
            return self.get_response(request)

        # Allow superusers to bypass strict context
        if request.user.is_superuser:
            org_id = request.headers.get('X-Organization-Id')
            if org_id:
                request.organization_context = Organization.objects.filter(id=org_id).first()
            return self.get_response(request)

        org_id = request.headers.get('X-Organization-Id')

        if org_id:
            membership = OrganizationMembership.objects.filter(
                user=request.user,
                organization_id=org_id,
                status='active'
            ).select_related('organization').first()

            if not membership:
                return HttpResponseForbidden("Forbidden: Active membership required for this organization context.")
            
            request.organization_context = membership.organization
        else:
            # Fallback for compatibility: If the user has exactly 1 active membership, use it
            memberships = OrganizationMembership.objects.filter(user=request.user, status='active').select_related('organization')
            count = memberships.count()
            if count == 1:
                request.organization_context = memberships.first().organization
            elif count > 1:
                # User belongs to multiple orgs, they MUST specify which one
                # but we'll let the view logic handle rejecting it via `get_current_organization`
                pass

        return self.get_response(request)
