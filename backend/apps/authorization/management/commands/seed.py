from django.core.management.base import BaseCommand
from apps.authorization.models import Permission, Role, RolePermission, UserRole
from apps.leaves.models import LeaveType
from apps.organization.models import Organization
from apps.employees.models import Employee
from apps.payroll.models import CompensationHistory
from apps.attendance.models import Attendance
from apps.leaves.models import LeaveRequest
from django.contrib.auth import get_user_model
from django.db import transaction
from decimal import Decimal
from datetime import date, timedelta

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
            {'codename': 'employee.status', 'resource': 'employee', 'action': 'status', 'name': 'Change Employee Login Status'},
            {'codename': 'employee.manage_status', 'resource': 'employee', 'action': 'manage_status', 'name': 'Manage Employment Status'},
            {'codename': 'employee.view_sensitive', 'resource': 'employee', 'action': 'view_sensitive', 'name': 'View Sensitive Info'},
            
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

            # Payroll
            {'codename': 'payroll.view', 'resource': 'payroll', 'action': 'view', 'name': 'View Payroll'},
            {'codename': 'payroll.generate', 'resource': 'payroll', 'action': 'generate', 'name': 'Generate Payroll'},
            {'codename': 'payroll.approve', 'resource': 'payroll', 'action': 'approve', 'name': 'Approve Payroll'},
            {'codename': 'payroll.view_sensitive', 'resource': 'payroll', 'action': 'view_sensitive', 'name': 'View Sensitive Payroll Data'},
            {'codename': 'payroll.manage_compensation', 'resource': 'payroll', 'action': 'manage_compensation', 'name': 'Manage Compensation'},
            {'codename': 'payroll.view_reports', 'resource': 'payroll', 'action': 'view_reports', 'name': 'View Payroll Reports'},
            {'codename': 'payslip.view', 'resource': 'payslip', 'action': 'view', 'name': 'View Payslips'},
            {'codename': 'payslip.download', 'resource': 'payslip', 'action': 'download', 'name': 'Download Payslips'},
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

        mgr_perms = emp_perms + ['leave.approve', 'leave.reject', 'wfh.approve', 'wfh.reject', 'employee.view', 'employee.view_sensitive']
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

        # 5. Demo Users
        User = get_user_model()
        demo_users = [
            {'email': 'hr@demo.local', 'first_name': 'HR', 'last_name': 'Demo', 'role': hr_role, 'code': 'DEMO-HR'},
            {'email': 'manager@demo.local', 'first_name': 'Manager', 'last_name': 'Demo', 'role': manager_role, 'code': 'DEMO-MGR'},
            {'email': 'employee@demo.local', 'first_name': 'Employee', 'last_name': 'Demo', 'role': employee_role, 'code': 'DEMO-EMP'},
            {'email': 'noperm@demo.local', 'first_name': 'NoPerm', 'last_name': 'Demo', 'role': None, 'code': 'DEMO-NONE'},
        ]
        
        for data in demo_users:
            user, created = User.objects.get_or_create(email=data['email'], defaults={
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'status': 'active'
            })
            if created or not user.has_usable_password():
                user.set_password('DevPass123!')
                user.status = 'active'
                user.save()
                
            if data['role']:
                UserRole.objects.get_or_create(user=user, role=data['role'])
                
            emp, _ = Employee.objects.get_or_create(user=user, defaults={
                'employee_code': data['code'],
                'organization': org,
                'personal_email': data['email'].replace('@demo.local', '@personal.local'),
                'employment_status': 'active'
            })
            # Ensure compensation is configured
            CompensationHistory.objects.get_or_create(
                employee=emp,
                effective_from=date(2026, 1, 1),
                defaults={
                    'basic_salary': Decimal('60000.00') if data['code'] != 'DEMO-NONE' else Decimal('45000.00'),
                    'created_by': user,
                }
            )

        # 6. Ensure Superuser is linked to an Employee record in the primary organization
        superuser = User.objects.filter(is_superuser=True).first()
        if superuser and not hasattr(superuser, 'employee'):
            admin_emp = Employee.objects.create(
                user=superuser,
                employee_code='ADMIN-001',
                organization=org,
                personal_email=superuser.email,
                employment_status='active',
            )
            CompensationHistory.objects.get_or_create(
                employee=admin_emp,
                effective_from=date(2026, 1, 1),
                defaults={
                    'basic_salary': Decimal('100000.00'),
                    'created_by': superuser,
                }
            )

        # 7. Seed sample attendance for active employees for the current month
        today = date.today()
        month_start = date(today.year, today.month, 1)
        active_employees = Employee.objects.filter(organization=org, employment_status='active')
        for emp in active_employees:
            curr = month_start
            while curr <= today:
                if curr.weekday() < 5:  # Mon-Fri
                    Attendance.objects.get_or_create(
                        employee=emp,
                        date=curr,
                        defaults={'status': 'present'}
                    )
                curr += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f'Seeded {len(demo_users)} Demo Users with password "DevPass123!", compensation, and attendance.'))
