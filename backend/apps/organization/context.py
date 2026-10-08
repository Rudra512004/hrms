from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.employees.models import Employee

def get_current_organization(request):
    """
    Safely retrieves the active organization context for the current request.
    Raises exceptions if the context cannot be resolved.
    """
    if hasattr(request, 'organization_context') and request.organization_context:
        return request.organization_context
        
    org_id = request.headers.get('X-Organization-Id')
    if org_id:
        from apps.organization.models import OrganizationMembership
        membership = OrganizationMembership.objects.filter(
            user=request.user,
            organization_id=org_id,
            status='active'
        ).select_related('organization').first()
        if membership:
            return membership.organization
        raise PermissionDenied("You do not have an active membership for the requested organization.")

    if hasattr(request, 'user') and request.user and request.user.is_authenticated:
        from apps.organization.models import OrganizationMembership
        memberships = OrganizationMembership.objects.filter(user=request.user, status='active').select_related('organization')
        count = memberships.count()
        if count == 1:
            return memberships.first().organization
        else:
            print(f"DEBUG: memberships.count() is {count} for user {request.user}")

    print(f"DEBUG: Failing context resolution. Org ID: {org_id}, User: {getattr(request, 'user', None)}")
    raise ValidationError("Missing X-Organization-Id header. Tenant context could not be determined.")

def get_current_employee(request):
    """
    Retrieves the Employee profile for the current user in the current active organization context.
    Raises an error if the user has no Employee profile in this specific organization.
    """
    org = get_current_organization(request)
            
    emp = Employee.objects.filter(user=request.user, organization=org).first()
    if not emp:
        raise PermissionDenied("You do not have an active employee profile in this organization.")
    return emp
