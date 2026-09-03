from django.core.management.base import BaseCommand
from apps.authorization.models import Permission, Role, RolePermission
from apps.leaves.models import LeaveType
from apps.organization.models import Organization
from django.db import transaction

class Command(BaseCommand):
    help = 'Seed deterministic base data for HRMS development'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        # 1. Ensure a default organization exists
        org, _ = Organization.objects.get_or_create(
            name='Default Org',
            defaults={'status': 'active'}
        )
        self.stdout.write(self.style.SUCCESS(f'Organization: {org.name}'))

        # 2. Permissions
        permissions_data = [
            # Leave
            {'codename': 'leave.view', 'resource': 'leave', 'action': 'view', 'name': 'View Leaves'},
            {'codename': 'leave.request', 'resource': 'leave', 'action': 'request', 'name': 'Request Leave'},
            {'codename': 'leave.approve', 'resource': 'leave', 'action': 'approve', 'name': 'Approve Leave'},
            {'codename': 'leave.reject', 'resource': 'leave', 'action': 'reject', 'name': 'Reject Leave'},
            {'codename': 'leave.cancel', 'resource': 'leave', 'action': 'cancel', 'name': 'Cancel Leave'},
            {'codename': 'leave_type.manage', 'resource': 'leave_type', 'action': 'manage', 'name': 'Manage Leave Types'},
            
            # Employee
            {'codename': 'employee.view', 'resource': 'employee', 'action': 'view', 'name': 'View Employees'},
            {'codename': 'employee.create', 'resource': 'employee', 'action': 'create', 'name': 'Create Employee'},
            {'codename': 'employee.update', 'resource': 'employee', 'action': 'update', 'name': 'Update Employee'},
            {'codename': 'employee.status', 'resource': 'employee', 'action': 'status', 'name': 'Change Employee Status'},
            
            # WFH
            {'codename': 'wfh.view', 'resource': 'wfh', 'action': 'view', 'name': 'View WFH Requests'},
            {'codename': 'wfh.request', 'resource': 'wfh', 'action': 'request', 'name': 'Request WFH'},
            {'codename': 'wfh.approve', 'resource': 'wfh', 'action': 'approve', 'name': 'Approve WFH'},
            {'codename': 'wfh.reject', 'resource': 'wfh', 'action': 'reject', 'name': 'Reject WFH'},
            {'codename': 'wfh.cancel', 'resource': 'wfh', 'action': 'cancel', 'name': 'Cancel WFH'},
            
            # Roles/Permissions
            {'codename': 'role.view', 'resource': 'role', 'action': 'view', 'name': 'View Roles'},
            {'codename': 'role.assign', 'resource': 'role', 'action': 'assign', 'name': 'Assign Roles'},
            {'codename': 'role.revoke', 'resource': 'role', 'action': 'revoke', 'name': 'Revoke Roles'},
            {'codename': 'permission.view', 'resource': 'permission', 'action': 'view', 'name': 'View Permissions'},
            {'codename': 'permission.assign', 'resource': 'permission', 'action': 'assign', 'name': 'Assign Permissions'},
            {'codename': 'permission.revoke', 'resource': 'permission', 'action': 'revoke', 'name': 'Revoke Permissions'},

            # Organization
            {'codename': 'organization.view', 'resource': 'organization', 'action': 'view', 'name': 'View Organizations'},
            {'codename': 'organization.manage', 'resource': 'organization', 'action': 'manage', 'name': 'Manage Organizations'},
            {'codename': 'department.view', 'resource': 'department', 'action': 'view', 'name': 'View Departments'},
            {'codename': 'department.manage', 'resource': 'department', 'action': 'manage', 'name': 'Manage Departments'},
            {'codename': 'designation.view', 'resource': 'designation', 'action': 'view', 'name': 'View Designations'},
            {'codename': 'designation.manage', 'resource': 'designation', 'action': 'manage', 'name': 'Manage Designations'},
            {'codename': 'hierarchy.manage', 'resource': 'hierarchy', 'action': 'manage', 'name': 'Manage Reporting Hierarchy'},
        ]

        for p_data in permissions_data:
            Permission.objects.update_or_create(
                codename=p_data['codename'],
                defaults={
                    'name': p_data['name'],
                    'resource': p_data['resource'],
                    'action': p_data['action'],
                }
            )
        self.stdout.write(self.style.SUCCESS(f'Seeded {len(permissions_data)} permissions'))

        # 3. Roles
        employee_role, _ = Role.objects.get_or_create(organization=org, name='Employee', defaults={'description': 'Standard employee'})
        hr_role, _ = Role.objects.get_or_create(organization=org, name='HR', defaults={'description': 'HR Administrator'})
        manager_role, _ = Role.objects.get_or_create(organization=org, name='Manager', defaults={'description': 'Team Manager'})

        # Assign permissions to Roles
        emp_perms = [
            'leave.view', 'leave.request', 'leave.cancel', 'wfh.view', 'wfh.request', 'wfh.cancel',
            'organization.view', 'department.view', 'designation.view'
        ]
        for codename in emp_perms:
            p = Permission.objects.get(codename=codename)
            RolePermission.objects.get_or_create(role=employee_role, permission=p)

        for p in Permission.objects.all():
            RolePermission.objects.get_or_create(role=hr_role, permission=p)

        mgr_perms = emp_perms + ['leave.approve', 'leave.reject', 'wfh.approve', 'wfh.reject', 'employee.view']
        for codename in mgr_perms:
            p = Permission.objects.get(codename=codename)
            RolePermission.objects.get_or_create(role=manager_role, permission=p)

        self.stdout.write(self.style.SUCCESS('Seeded Roles and RolePermissions'))

        # 4. Leave Types
        leave_types = [
            {'name': 'Annual Leave', 'description': 'Standard paid time off', 'annual_allocation': 20},
            {'name': 'Sick Leave', 'description': 'Medical leave', 'annual_allocation': 10},
            {'name': 'Unpaid Leave', 'description': 'Leave without pay', 'annual_allocation': 30},
        ]
        
        for lt_data in leave_types:
            LeaveType.objects.update_or_create(
                name=lt_data['name'],
                organization=org,
                defaults={
                    'description': lt_data['description'],
                    'annual_allocation': lt_data['annual_allocation'],
                    'is_active': True
                }
            )
        self.stdout.write(self.style.SUCCESS(f'Seeded {len(leave_types)} Leave Types'))
