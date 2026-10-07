import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.organization.models import Organization
from apps.authorization.services import AuthorizationService
from apps.authorization.models import Role, UserRole, Permission, RolePermission, ScopeChoices

User = get_user_model()

def test_isolation():
    org_a, _ = Organization.objects.get_or_create(name='Org A')
    org_b, _ = Organization.objects.get_or_create(name='Org B')

    admin_a, _ = User.objects.get_or_create(email='admin_a@test.com', defaults={'is_superuser': True, 'status': 'active'})
    admin_b, _ = User.objects.get_or_create(email='admin_b@test.com', defaults={'is_superuser': True, 'status': 'active'})
    
    # Assign admin_a to org_a
    role_a, _ = Role.objects.get_or_create(organization=org_a, name='Owner A', is_active=True)
    UserRole.objects.get_or_create(user=admin_a, role=role_a, scope=ScopeChoices.ORGANIZATION)

    # Assign admin_b to org_b
    role_b, _ = Role.objects.get_or_create(organization=org_b, name='Owner B', is_active=True)
    UserRole.objects.get_or_create(user=admin_b, role=role_b, scope=ScopeChoices.ORGANIZATION)

    org_for_a = AuthorizationService.get_primary_organization(admin_a)
    org_for_b = AuthorizationService.get_primary_organization(admin_b)
    
    print(f'Admin A Organization: {org_for_a.name}')
    print(f'Admin B Organization: {org_for_b.name}')
    
    # Check if admin_a can access org_b (should be false, as get_primary_organization only returns org_a)
    if org_for_a.id == org_b.id:
        print('FAILURE: Admin A has access to Org B')
    else:
        print('SUCCESS: Admin A is isolated to Org A')

    if org_for_b.id == org_a.id:
        print('FAILURE: Admin B has access to Org A')
    else:
        print('SUCCESS: Admin B is isolated to Org B')

test_isolation()
