import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hrms.settings')
django.setup()

from apps.authorization.services import AuthorizationService
from django.contrib.auth import get_user_model
from apps.authorization.models import Permission, Role, UserRole, RolePermission
from apps.organization.models import Organization

User = get_user_model()
org = Organization.objects.create(name='org_debug')
u = User.objects.create(email='debug@debug.com', is_active=True)
r = Role.objects.create(organization=org, name='hr_debug', is_active=True)
p, _ = Permission.objects.get_or_create(codename='employee.manage_statutory', defaults={'name': 't', 'resource': 'r', 'action': 'a', 'is_active': True})
RolePermission.objects.create(role=r, permission=p)
ur = UserRole.objects.create(user=u, role=r, scope='organization')

print('Perms:', AuthorizationService.get_effective_permissions(u))
print('Has Perm:', AuthorizationService.has_permission(u, 'employee.manage_statutory'))
