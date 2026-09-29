import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.authorization.models import Permission

User = get_user_model()

PERMISSIONS_DATA = [
    # Leave
    {'codename': 'leave.view', 'resource': 'leave', 'action': 'view', 'name': 'View Leaves'},
    {'codename': 'leave.request', 'resource': 'leave', 'action': 'request', 'name': 'Request Leave'},
    {'codename': 'leave.approve', 'resource': 'leave', 'action': 'approve', 'name': 'Approve Leave'},
    {'codename': 'leave.reject', 'resource': 'leave', 'action': 'reject', 'name': 'Reject Leave'},
    {'codename': 'leave.cancel', 'resource': 'leave', 'action': 'cancel', 'name': 'Cancel Leave'},
    {'codename': 'leave_type.manage', 'resource': 'leave_type', 'action': 'manage', 'name': 'Manage Leave Types'},

    # Employee & Lifecycle
    {'codename': 'employee.view', 'resource': 'employee', 'action': 'view', 'name': 'View Employees'},
    {'codename': 'employee.create', 'resource': 'employee', 'action': 'create', 'name': 'Create Employee'},
    {'codename': 'employee.update', 'resource': 'employee', 'action': 'update', 'name': 'Update Employee'},
    {'codename': 'employee.status', 'resource': 'employee', 'action': 'status', 'name': 'Change Employee Login Status'},
    {'codename': 'employee.manage_status', 'resource': 'employee', 'action': 'manage_status', 'name': 'Manage Employment Status'},
    {'codename': 'employee.view_sensitive', 'resource': 'employee', 'action': 'view_sensitive', 'name': 'View Sensitive Info'},
    {'codename': 'employee.transfer', 'resource': 'employee', 'action': 'transfer', 'name': 'Transfer Employee'},
    {'codename': 'employee.promote', 'resource': 'employee', 'action': 'promote', 'name': 'Promote Employee'},
    {'codename': 'employee.exit', 'resource': 'employee', 'action': 'exit', 'name': 'Exit Employee'},
    {'codename': 'employee.lifecycle.view', 'resource': 'employee', 'action': 'lifecycle_view', 'name': 'View Employee Lifecycle History'},

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
    {'codename': 'organization.update', 'resource': 'organization', 'action': 'update', 'name': 'Update Organizations'},
    {'codename': 'branch.view', 'resource': 'branch', 'action': 'view', 'name': 'View Branches'},
    {'codename': 'branch.manage', 'resource': 'branch', 'action': 'manage', 'name': 'Manage Branches'},
    {'codename': 'department.view', 'resource': 'department', 'action': 'view', 'name': 'View Departments'},
    {'codename': 'department.manage', 'resource': 'department', 'action': 'manage', 'name': 'Manage Departments'},
    {'codename': 'team.view', 'resource': 'team', 'action': 'view', 'name': 'View Teams'},
    {'codename': 'team.manage', 'resource': 'team', 'action': 'manage', 'name': 'Manage Teams'},
    {'codename': 'designation.view', 'resource': 'designation', 'action': 'view', 'name': 'View Designations'},
    {'codename': 'designation.manage', 'resource': 'designation', 'action': 'manage', 'name': 'Manage Designations'},
    {'codename': 'hierarchy.manage', 'resource': 'hierarchy', 'action': 'manage', 'name': 'Manage Reporting Hierarchy'},
    {'codename': 'office_network.view', 'resource': 'office_network', 'action': 'view', 'name': 'View Office Networks'},
    {'codename': 'office_network.create', 'resource': 'office_network', 'action': 'create', 'name': 'Create Office Networks'},
    {'codename': 'office_network.update', 'resource': 'office_network', 'action': 'update', 'name': 'Update Office Networks'},
    {'codename': 'office_network.delete', 'resource': 'office_network', 'action': 'delete', 'name': 'Delete Office Networks'},

    # Payroll
    {'codename': 'payroll.view', 'resource': 'payroll', 'action': 'view', 'name': 'View Payroll'},
    {'codename': 'payroll.generate', 'resource': 'payroll', 'action': 'generate', 'name': 'Generate Payroll'},
    {'codename': 'payroll.approve', 'resource': 'payroll', 'action': 'approve', 'name': 'Approve Payroll'},
    {'codename': 'payroll.view_sensitive', 'resource': 'payroll', 'action': 'view_sensitive', 'name': 'View Sensitive Payroll Data'},
    {'codename': 'payroll.manage_compensation', 'resource': 'payroll', 'action': 'manage_compensation', 'name': 'Manage Compensation'},
    {'codename': 'payroll.view_reports', 'resource': 'payroll', 'action': 'view_reports', 'name': 'View Payroll Reports'},
    {'codename': 'payslip.view', 'resource': 'payslip', 'action': 'view', 'name': 'View Payslips'},
    {'codename': 'payslip.download', 'resource': 'payslip', 'action': 'download', 'name': 'Download Payslips'},

    # Employee Documents
    {'codename': 'employee.document.view', 'resource': 'employee_document', 'action': 'view', 'name': 'View Employee Documents'},
    {'codename': 'employee.document.upload', 'resource': 'employee_document', 'action': 'upload', 'name': 'Upload Employee Documents'},
    {'codename': 'employee.document.delete', 'resource': 'employee_document', 'action': 'delete', 'name': 'Delete Employee Documents'},

    # Assets
    {'codename': 'asset.view', 'resource': 'asset', 'action': 'view', 'name': 'View Assets'},
    {'codename': 'asset.create', 'resource': 'asset', 'action': 'create', 'name': 'Create Assets'},
    {'codename': 'asset.update', 'resource': 'asset', 'action': 'update', 'name': 'Update Assets'},
    {'codename': 'asset.delete', 'resource': 'asset', 'action': 'delete', 'name': 'Delete Assets'},
    {'codename': 'asset.assign', 'resource': 'asset', 'action': 'assign', 'name': 'Assign and Return Assets'},

    # Attendance & Scheduling
    {'codename': 'attendance.view_all', 'resource': 'attendance', 'action': 'view_all', 'name': 'View All Attendance'},
    {'codename': 'holiday.view', 'resource': 'holiday', 'action': 'view', 'name': 'View Holidays'},
    {'codename': 'holiday.manage', 'resource': 'holiday', 'action': 'manage', 'name': 'Manage Holidays'},
    {'codename': 'shift.view', 'resource': 'shift', 'action': 'view', 'name': 'View Shifts'},
    {'codename': 'shift.manage', 'resource': 'shift', 'action': 'manage', 'name': 'Manage Shifts'},
    {'codename': 'shift_assignment.view', 'resource': 'shift_assignment', 'action': 'view', 'name': 'View Shift Assignments'},
    {'codename': 'shift_assignment.manage', 'resource': 'shift_assignment', 'action': 'manage', 'name': 'Manage Shift Assignments'},

    # Candidate & Onboarding
    {'codename': 'candidate.view', 'resource': 'candidate', 'action': 'view', 'name': 'View Candidates'},
    {'codename': 'candidate.create', 'resource': 'candidate', 'action': 'create', 'name': 'Create Candidate'},
    {'codename': 'candidate.update', 'resource': 'candidate', 'action': 'update', 'name': 'Update Candidate'},
    {'codename': 'candidate.manage_status', 'resource': 'candidate', 'action': 'manage_status', 'name': 'Manage Candidate Status'},
    {'codename': 'candidate.onboard', 'resource': 'candidate', 'action': 'onboard', 'name': 'Issue Offer / Start Onboarding'},
    {'codename': 'candidate.verify', 'resource': 'candidate', 'action': 'verify', 'name': 'Verify Candidate Documents'},
    {'codename': 'candidate.convert', 'resource': 'candidate', 'action': 'convert', 'name': 'Convert Candidate to Employee'},

    # Letters
    {'codename': 'letter.view', 'resource': 'letter', 'action': 'view', 'name': 'View Letter Templates'},
    {'codename': 'letter.issue', 'resource': 'letter', 'action': 'issue', 'name': 'Create/Issue Letter Templates'},

    # Audit
    {'codename': 'audit.view', 'resource': 'audit', 'action': 'view', 'name': 'View Audit Logs'},
]


class Command(BaseCommand):
    help = 'Idempotently bootstrap initial Super Admin and required RBAC permissions for Render demo'

    def handle(self, *args, **options):
        # 1. Populate canonical system permissions
        seeded_count = 0
        for p_data in PERMISSIONS_DATA:
            _, created = Permission.objects.update_or_create(
                codename=p_data['codename'],
                defaults={
                    'name': p_data['name'],
                    'resource': p_data['resource'],
                    'action': p_data['action'],
                    'is_active': True,
                }
            )
            if created:
                seeded_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'RBAC Permissions populated: {len(PERMISSIONS_DATA)} available ({seeded_count} newly created).'
        ))

        # 2. Resolve Super Admin credentials from environment
        email = os.environ.get('DEMO_SUPERADMIN_EMAIL', '').strip()
        password = os.environ.get('DEMO_SUPERADMIN_PASSWORD', '').strip()

        if not email:
            self.stdout.write(self.style.WARNING(
                'DEMO_SUPERADMIN_EMAIL environment variable not set. Skipping Super Admin creation.'
            ))
            return

        normalized_email = User.objects.normalize_email(email)
        user = User.objects.filter(email__iexact=normalized_email).first()

        if user:
            # Idempotent: Update existing user to active superuser without resetting existing password
            updated = False
            if not user.is_superuser:
                user.is_superuser = True
                updated = True
            if not user.is_staff:
                user.is_staff = True
                updated = True
            if user.status != 'active':
                user.status = 'active'
                updated = True

            # If user has no usable password and password was provided, set it
            if not user.has_usable_password() and password:
                user.set_password(password)
                updated = True

            if updated:
                user.save()
                self.stdout.write(self.style.SUCCESS(
                    f'Super Admin account ({normalized_email}) verified and updated to active superuser.'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'Super Admin account ({normalized_email}) already exists and is active.'
                ))
        else:
            if not password:
                self.stdout.write(self.style.ERROR(
                    'DEMO_SUPERADMIN_PASSWORD must be provided to create the initial Super Admin account.'
                ))
                return

            user = User.objects.create_superuser(
                email=normalized_email,
                password=password,
                first_name='Super',
                last_name='Admin'
            )
            self.stdout.write(self.style.SUCCESS(
                f'Super Admin account ({normalized_email}) created successfully as a headless administrator.'
            ))

        # Explicit safety check: Ensure Super Admin does NOT have an Employee record
        if hasattr(user, 'employee') and user.employee:
            self.stdout.write(self.style.WARNING(
                'Warning: Super Admin unexpectedly has an Employee profile attached.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                'Confirmed: Super Admin remains a headless administrator with NO Employee profile.'
            ))
