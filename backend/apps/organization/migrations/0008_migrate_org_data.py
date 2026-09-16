from django.db import migrations

def migrate_data(apps, schema_editor):
    Organization = apps.get_model('organization', 'Organization')
    Branch = apps.get_model('organization', 'Branch')
    WorkingCalendar = apps.get_model('organization', 'WorkingCalendar')
    AttendancePolicy = apps.get_model('organization', 'AttendancePolicy')
    OfficeNetwork = apps.get_model('organization', 'OfficeNetwork')
    
    Holiday = apps.get_model('attendance', 'Holiday')
    Shift = apps.get_model('attendance', 'Shift')
    EmployeeShiftAssignment = apps.get_model('attendance', 'EmployeeShiftAssignment')
    
    Employee = apps.get_model('employees', 'Employee')

    # 1. Validate that all employees assigned to a shift have a branch
    assignments = EmployeeShiftAssignment.objects.all().select_related('employee')
    employees_without_branch = []
    for assignment in assignments:
        if not assignment.employee.branch_id:
            employees_without_branch.append(assignment.employee.id)
    
    if employees_without_branch:
        raise ValueError(
            f"Migration failed: The following employees have shift assignments but no branch assigned: "
            f"{set(employees_without_branch)}. Please assign branches to these employees before migrating."
        )

    # 2. Migrate configurations and create branch-specific shifts/holidays
    orgs = Organization.objects.all()
    for org in orgs:
        # Get org configs
        org_working_calendar = WorkingCalendar.objects.filter(organization=org).first()
        org_attendance_policy = AttendancePolicy.objects.filter(organization=org).first()
        org_office_networks = OfficeNetwork.objects.filter(organization=org)
        org_holidays = Holiday.objects.filter(organization=org)
        org_shifts = Shift.objects.filter(organization=org)

        branches = Branch.objects.filter(organization=org)
        for branch in branches:
            # Create WorkingCalendar
            if org_working_calendar:
                WorkingCalendar.objects.create(
                    branch=branch,
                    work_days=org_working_calendar.work_days
                )
            
            # Create AttendancePolicy
            if org_attendance_policy:
                AttendancePolicy.objects.create(
                    branch=branch,
                    is_office_gps_enabled=org_attendance_policy.is_office_gps_enabled,
                    is_office_ip_enabled=org_attendance_policy.is_office_ip_enabled,
                    is_wfh_enabled=org_attendance_policy.is_wfh_enabled,
                    wfh_bypasses_office_restrictions=org_attendance_policy.wfh_bypasses_office_restrictions
                )
            
            # Create OfficeNetworks
            for network in org_office_networks:
                OfficeNetwork.objects.create(
                    branch=branch,
                    name=network.name,
                    network=network.network,
                    description=network.description,
                    is_active=network.is_active
                )
            
            # Create Holidays
            for holiday in org_holidays:
                Holiday.objects.create(
                    branch=branch,
                    name=holiday.name,
                    date=holiday.date,
                    is_active=holiday.is_active
                )
            
            # Create Shifts and map old to new
            shift_mapping = {}
            for shift in org_shifts:
                new_shift = Shift.objects.create(
                    branch=branch,
                    name=shift.name,
                    start_time=shift.start_time,
                    end_time=shift.end_time,
                    grace_period=shift.grace_period,
                    full_day_hours=shift.full_day_hours,
                    half_day_hours=shift.half_day_hours,
                    work_days=shift.work_days,
                    is_active=shift.is_active
                )
                shift_mapping[shift.id] = new_shift.id
            
            # Update EmployeeShiftAssignments for this branch
            branch_assignments = EmployeeShiftAssignment.objects.filter(employee__branch=branch)
            for assignment in branch_assignments:
                if assignment.shift_id in shift_mapping:
                    assignment.shift_id = shift_mapping[assignment.shift_id]
                    assignment.save(update_fields=['shift_id'])

    # 3. Update UserRole and UserPermissionGrant scope and branch
    UserRole = apps.get_model('authorization', 'UserRole')
    UserPermissionGrant = apps.get_model('authorization', 'UserPermissionGrant')
    
    # We will default to ORGANIZATION scope, which is already the default and requires branch=None
    # If a role needs to be branch specific, it can be updated manually later.
    # The clean method will enforce organization -> branch_id is None.


def reverse_migrate_data(apps, schema_editor):
    # This migration is one-way conceptually, but we can delete the branch-specific configs 
    # to reverse it, relying on the old_... fields still existing.
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0007_attendancepolicy_branch_officenetwork_branch_and_more'),
        ('attendance', '0007_alter_holiday_unique_together_and_more'),
        ('authorization', '0002_userpermissiongrant_branch_userpermissiongrant_scope_and_more'),
        ('employees', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_data, reverse_migrate_data),
    ]
