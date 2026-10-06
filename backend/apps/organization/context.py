from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.employees.models import Employee

def get_current_organization(request):
    """
    Safely retrieves the active organization context for the current request.
    This acts as a compatibility layer and migration tool.
    
    If the context was successfully resolved by TenantContextMiddleware, it is returned.
    If not, it falls back to the legacy `request.user.employee.organization` behavior temporarily,
    but emits a warning (or will eventually be strictly removed).
    
    Raises exceptions if the context cannot be resolved.
    """
    if hasattr(request, 'organization_context') and request.organization_context:
        return request.organization_context
        
    # Legacy fallback for transition phase
    if hasattr(request.user, 'employee'):
        try:
            return request.user.employee.organization
        except AttributeError:
            pass
        
    # If the middleware could not resolve it and there's no legacy employee fallback:
    if not request.headers.get('X-Organization-Id'):
        raise ValidationError("Missing X-Organization-Id header. Tenant context could not be determined.")
    
    raise PermissionDenied("You do not have an active membership for the requested organization.")

def get_current_employee(request):
    """
    Retrieves the Employee profile for the current user in the current active organization context.
    Raises an error if the user has no Employee profile in this specific organization.
    """
    org = get_current_organization(request)
    
    # Correct multi-tenant lookup: find the employee profile in this specific org
    if hasattr(request.user, 'employee'):
        try:
            if request.user.employee.organization_id == org.id:
                return request.user.employee
        except AttributeError:
            pass
            
    emp = Employee.objects.filter(user=request.user, organization=org).first()
    if not emp:
        raise PermissionDenied("You do not have an active employee profile in this organization.")
    return emp
