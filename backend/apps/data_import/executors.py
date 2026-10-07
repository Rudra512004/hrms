from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from apps.organization.models import Branch, Department, Designation, WorkingCalendar, WorkingCalendarRule, AttendancePolicy, OfficeNetwork, ThemeMode
from apps.employees.models import Employee, EmployeeStatutoryAndBank
from apps.leaves.models import LeaveType, BranchLeavePolicy, LeaveBalance, LeaveBalanceTransaction, LeaveCycle
from apps.attendance.models import Attendance, AttendanceProductivity, Shift, Holiday, EmployeeShiftAssignment
from apps.payroll.models import CompensationHistory, SalaryStructureComponent, SalaryComponent, SalaryStructure
from apps.authorization.models import UserRole, ScopeChoices
from decimal import Decimal

User = get_user_model()


def execute_employees(parsed_row, organization):
    # 1. User
    email = parsed_row['email']
    user, created_user = User.objects.get_or_create(
        email=email,
        defaults={
            'first_name': parsed_row['first_name'],
            'last_name': parsed_row['last_name'],
            'status': parsed_row['status'],
        }
    )
    if not created_user:
        user.first_name = parsed_row['first_name']
        user.last_name = parsed_row['last_name']
        user.status = parsed_row['status']
        user.save(update_fields=['first_name', 'last_name', 'status'])

    # 2. Employee Profile
    emp, created_emp = Employee.objects.get_or_create(
        employee_code=parsed_row['employee_code'],
        organization=organization,
        defaults={
            'user': user,
            'branch': parsed_row['branch_code'],
            'department': parsed_row['department_code'],
            'designation': parsed_row['designation_code'],
            'employment_type': parsed_row['employment_type'],
            'employment_status': parsed_row['employment_status'],
            'joining_date': parsed_row['date_of_joining'],
        }
    )
    
    # Update employee fields
    emp.personal_email = parsed_row.get('personal_email') or emp.personal_email
    emp.phone_number = parsed_row.get('phone') or emp.phone_number
    emp.alternate_phone = parsed_row.get('alternate_phone') or emp.alternate_phone
    emp.gender = parsed_row.get('gender') or emp.gender
    emp.date_of_birth = parsed_row.get('date_of_birth') or emp.date_of_birth
    emp.marital_status = parsed_row.get('marital_status') or emp.marital_status
    emp.blood_group = parsed_row.get('blood_group') or emp.blood_group
    emp.nationality = parsed_row.get('nationality') or emp.nationality
    emp.branch = parsed_row['branch_code']
    emp.department = parsed_row['department_code']
    emp.designation = parsed_row['designation_code']
    emp.reporting_manager = parsed_row.get('manager_code')
    emp.employment_type = parsed_row['employment_type']
    emp.employment_status = parsed_row['employment_status']
    emp.joining_date = parsed_row['date_of_joining']
    emp.confirmation_date = parsed_row.get('date_of_confirmation') or emp.confirmation_date
    emp.exit_date = parsed_row.get('date_of_exit') or emp.exit_date
    emp.notice_period_days = parsed_row.get('notice_period_days')
    emp.address_line1 = parsed_row.get('address_line1') or emp.address_line1
    emp.address_line2 = parsed_row.get('address_line2') or emp.address_line2
    emp.city = parsed_row.get('city') or emp.city
    emp.state = parsed_row.get('state') or emp.state
    emp.country = parsed_row.get('country') or emp.country
    emp.postal_code = parsed_row.get('postal_code') or emp.postal_code
    emp.emergency_contact_name = parsed_row.get('emergency_contact_name') or emp.emergency_contact_name
    emp.emergency_contact_phone = parsed_row.get('emergency_contact_phone') or emp.emergency_contact_phone
    emp.emergency_contact_relation = parsed_row.get('emergency_contact_relation') or emp.emergency_contact_relation
    emp.notes = parsed_row.get('notes') or emp.notes
    emp.save()

    # 3. Bank and Statutory
    stat, _ = EmployeeStatutoryAndBank.objects.get_or_create(employee=emp)
    stat.bank_name = parsed_row.get('bank_name') or stat.bank_name
    stat.account_name = parsed_row.get('bank_account_name') or stat.account_name
    stat.account_number = parsed_row.get('bank_account_number') or stat.account_number
    stat.ifsc_code = parsed_row.get('bank_ifsc') or stat.ifsc_code
    stat.bank_branch = parsed_row.get('bank_branch') or stat.bank_branch
    stat.pan_number = parsed_row.get('pan_number') or stat.pan_number
    stat.aadhaar_number = parsed_row.get('national_id') or stat.aadhaar_number
    stat.pf_account_number = parsed_row.get('pf_number') or stat.pf_account_number
    stat.esic_number = parsed_row.get('esi_number') or stat.esic_number
    stat.uan_number = parsed_row.get('uan_number') or stat.uan_number
    stat.save()

    # 4. Shift Assignment
    if parsed_row.get('shift_code'):
        EmployeeShiftAssignment.objects.update_or_create(
            employee=emp,
            effective_from=parsed_row['date_of_joining'], # Fallback
            defaults={'shift': parsed_row['shift_code']}
        )

    # 5. Role Assignment
    if parsed_row.get('role'):
        role = parsed_row['role']
        # Prevent assigning "Super Admin" via import for security
        if role.name.lower() == 'super admin':
            from apps.data_import.exceptions import RowValidationError
            raise RowValidationError('role', 'security_violation', "Super Admin privilege cannot be granted via CSV import.")
        
        UserRole.objects.get_or_create(
            user=user,
            role=role,
            scope=ScopeChoices.ORGANIZATION,
            defaults={'is_revoked': False}
        )

    return 'created' if created_emp else 'updated'


def execute_branches(parsed_row, organization):
    branch, created = Branch.objects.get_or_create(
        code=parsed_row['code'],
        organization=organization,
        defaults={
            'name': parsed_row['name'],
            'timezone': parsed_row['timezone'],
        }
    )
    
    branch.name = parsed_row['name']
    branch.email = parsed_row.get('email') or branch.email
    branch.phone = parsed_row.get('phone') or branch.phone
    branch.address_line1 = parsed_row.get('address_line1') or branch.address_line1
    branch.address_line2 = parsed_row.get('address_line2') or branch.address_line2
    branch.city = parsed_row.get('city') or branch.city
    branch.state = parsed_row.get('state') or branch.state
    branch.country = parsed_row.get('country') or branch.country
    branch.postal_code = parsed_row.get('postal_code') or branch.postal_code
    branch.latitude = parsed_row.get('latitude') or branch.latitude
    branch.longitude = parsed_row.get('longitude') or branch.longitude
    branch.radius = parsed_row.get('geofence_radius_metres') or branch.radius
    branch.timezone = parsed_row['timezone']
    
    if parsed_row.get('is_head_office') is not None:
        branch.is_head_office = parsed_row['is_head_office']
    branch.is_active = (parsed_row['status'] == 'active')
    branch.save()

    # Create Default Shift
    Shift.objects.get_or_create(
        branch=branch,
        name='Standard Shift',
        defaults={
            'code': 'STD',
            'start_time': parsed_row['work_start_time'],
            'end_time': parsed_row['work_end_time'],
            'work_days': parsed_row['working_days']
        }
    )

    # Calendar configuration is auto-created via signals, we just update it
    calendar, _ = WorkingCalendar.objects.get_or_create(branch=branch)
    calendar.work_days = parsed_row['working_days']
    calendar.save()

    if parsed_row.get('saturday_offs'):
        offs = parsed_row['saturday_offs']
        for occurrence_str in offs:
            try:
                occ = int(''.join(filter(str.isdigit, occurrence_str)))
                WorkingCalendarRule.objects.get_or_create(
                    working_calendar=calendar,
                    weekday=5, # Saturday
                    occurrence=occ,
                    defaults={'is_working': False}
                )
            except ValueError:
                continue

    return 'created' if created else 'updated'


def execute_departments(parsed_row, organization):
    dept, created = Department.objects.get_or_create(
        code=parsed_row['code'],
        branch=parsed_row['branch_code'],
        defaults={
            'name': parsed_row['name']
        }
    )
    dept.name = parsed_row['name']
    dept.description = parsed_row.get('description') or dept.description
    dept.is_active = (parsed_row['status'] == 'active')
    dept.save()
    return 'created' if created else 'updated'


def execute_designations(parsed_row, organization):
    desig, created = Designation.objects.get_or_create(
        code=parsed_row['code'],
        organization=organization,
        defaults={
            'name': parsed_row['name']
        }
    )
    desig.name = parsed_row['name']
    desig.level = parsed_row.get('level') or desig.level
    desig.description = parsed_row.get('description') or desig.description
    desig.is_active = (parsed_row['status'] == 'active')
    desig.save()
    return 'created' if created else 'updated'


def execute_leave_types(parsed_row, organization):
    leave_type, created = LeaveType.objects.get_or_create(
        code=parsed_row['code'],
        organization=organization,
        defaults={
            'name': parsed_row['name'],
            'accrual_frequency': parsed_row['accrual'],
        }
    )
    leave_type.name = parsed_row['name']
    leave_type.accrual_frequency = parsed_row['accrual']
    leave_type.color_code = parsed_row.get('color') or leave_type.color_code
    leave_type.description = parsed_row.get('description') or leave_type.description
    leave_type.is_active = (parsed_row['status'] == 'active')
    leave_type.save()

    # Apply to all branches in org by default, or just create base policies
    branches = Branch.objects.filter(organization=organization)
    for branch in branches:
        policy, _ = BranchLeavePolicy.objects.get_or_create(
            branch=branch,
            leave_type=leave_type
        )
        if parsed_row.get('days_per_month') is not None:
            policy.monthly_allocation = parsed_row['days_per_month']
        if parsed_row.get('probation_days_per_month') is not None:
            policy.probation_monthly_allocation = parsed_row['probation_days_per_month']
        
        if parsed_row.get('accrue_in_advance') is not None:
            policy.accrue_in_advance = parsed_row['accrue_in_advance']
        if parsed_row.get('accrual_starts_on') is not None:
            policy.accrual_starts_on = parsed_row['accrual_starts_on']
            
        policy.is_paid = parsed_row['is_paid']
        
        if parsed_row.get('requires_approval') is not None:
            policy.requires_approval = parsed_row['requires_approval']
        if parsed_row.get('allow_half_day') is not None:
            policy.half_day_allowed = parsed_row['allow_half_day']
        if parsed_row.get('carry_forward') is not None:
            policy.carry_forward_enabled = parsed_row['carry_forward']
        if parsed_row.get('max_carry_forward_days') is not None:
            policy.carry_forward_limit = parsed_row['max_carry_forward_days']
        if parsed_row.get('max_consecutive_days') is not None:
            policy.max_consecutive_days = parsed_row['max_consecutive_days']
        if parsed_row.get('min_notice_days') is not None:
            policy.advance_notice_days = parsed_row['min_notice_days']
        if parsed_row.get('applicable_gender') is not None:
            policy.applicable_gender = parsed_row['applicable_gender']
        if parsed_row.get('applicable_after_months') is not None:
            policy.applicable_after_months = parsed_row['applicable_after_months']
        if parsed_row.get('requires_attachment') is not None:
            policy.requires_supporting_document = parsed_row['requires_attachment']
            
        policy.save()

    return 'created' if created else 'updated'


def execute_holidays(parsed_row, organization):
    created_any = False
    branches = parsed_row['branches']
    
    for branch in branches:
        holiday, created = Holiday.objects.get_or_create(
            branch=branch,
            date=parsed_row['date'],
            defaults={
                'name': parsed_row['name']
            }
        )
        if created:
            created_any = True
        
        holiday.name = parsed_row['name']
        if parsed_row.get('type'):
            holiday.holiday_type = parsed_row['type']
        if parsed_row.get('description'):
            holiday.description = parsed_row['description']
        if parsed_row.get('is_recurring') is not None:
            holiday.is_recurring = parsed_row['is_recurring']
        holiday.save()
        
    return 'created' if created_any else 'updated'


def execute_attendance(parsed_row, organization):
    emp = parsed_row['employee_code']
    att, created = Attendance.objects.get_or_create(
        employee=emp,
        date=parsed_row['date'],
        defaults={
            'status': parsed_row['status']
        }
    )
    
    att.status = parsed_row['status']
    att.check_in = parsed_row.get('check_in') or att.check_in
    att.check_out = parsed_row.get('check_out') or att.check_out
    
    if parsed_row.get('productive_duration') is not None:
        att.productive_work_duration = parsed_row['productive_duration']
        
    att.save()

    # Productivity metrics if provided
    has_prod = any(parsed_row.get(k) is not None for k in [
        'online_duration', 'active_duration', 'idle_duration', 
        'unproductive_duration', 'neutral_duration', 'active_percent',
        'mouse_clicks', 'key_presses'
    ])
    
    if has_prod:
        prod, _ = AttendanceProductivity.objects.get_or_create(attendance=att)
        for field in ['online_duration', 'active_duration', 'idle_duration', 
                      'unproductive_duration', 'neutral_duration', 'active_percent',
                      'mouse_clicks', 'key_presses']:
            if parsed_row.get(field) is not None:
                setattr(prod, field, parsed_row[field])
        prod.save()

    return 'created' if created else 'updated'


def execute_salary_structures(parsed_row, organization):
    emp = parsed_row['employee_code']
    
    history, created = CompensationHistory.objects.get_or_create(
        employee=emp,
        effective_from=parsed_row['effective_from'],
        defaults={
            'basic_salary': parsed_row['basic_salary'],
            'ctc_annual': parsed_row['ctc_annual'],
            'currency': parsed_row['currency'],
        }
    )
    
    history.basic_salary = parsed_row['basic_salary']
    history.ctc_annual = parsed_row['ctc_annual']
    history.currency = parsed_row['currency']
    history.notes = parsed_row.get('notes') or history.notes
    history.save()

    if parsed_row.get('payment_mode'):
        stat, _ = EmployeeStatutoryAndBank.objects.get_or_create(employee=emp)
        stat.payment_mode = parsed_row['payment_mode']
        stat.save()

    # Process components
    if 'components' in parsed_row:
        # Create a default active structure if none exists for the organization
        struct, _ = SalaryStructure.objects.get_or_create(
            organization=organization,
            name="Standard Structure",
            defaults={'is_active': True}
        )
        
        for comp_code, amount in parsed_row['components'].items():
            if amount is not None:
                comp, _ = SalaryComponent.objects.get_or_create(
                    organization=organization,
                    code=comp_code.upper(),
                    defaults={
                        'name': comp_code.replace('_', ' ').title(),
                        'kind': 'earning' if float(amount) >= 0 else 'deduction'
                    }
                )
                SalaryStructureComponent.objects.update_or_create(
                    structure=struct,
                    component=comp,
                    defaults={'amount': abs(amount)}
                )

    return 'created' if created else 'updated'


def execute_leave_balances(parsed_row, organization):
    emp = parsed_row['employee_code']
    
    # 1. Ensure cycle exists
    cycle_year = parsed_row['year']
    from datetime import date
    cycle, _ = LeaveCycle.objects.get_or_create(
        branch=emp.branch,
        name=str(cycle_year),
        defaults={
            'start_date': date(cycle_year, 1, 1),
            'end_date': date(cycle_year, 12, 31)
        }
    )
    
    # 2. Get/Create Balance
    balance, created = LeaveBalance.objects.get_or_create(
        employee=emp,
        leave_type=parsed_row['leave_type_code'],
        leave_cycle=cycle,
        defaults={
            'branch': emp.branch
        }
    )
    
    # 3. Process transactions
    tx_map = {
        'allocated_days': ('legacy_conversion_allocated', 'allocated'),
        'carried_forward_days': ('legacy_conversion_carry_forward', 'carried_forward'),
        'used_days': ('legacy_conversion_used', 'used'),
        'encashed_days': ('legacy_conversion_encashed', 'encashed'),
    }
    
    made_changes = False
    
    for field, (tx_type, bal_field) in tx_map.items():
        val = parsed_row.get(field)
        if val is not None and val > 0:
            # Check if this tx already exists to prevent duplicate imports
            exists = LeaveBalanceTransaction.objects.filter(
                balance=balance, transaction_type=tx_type
            ).exists()
            
            if not exists:
                LeaveBalanceTransaction.objects.create(
                    balance=balance,
                    employee=emp,
                    leave_type=parsed_row['leave_type_code'],
                    leave_cycle=cycle,
                    transaction_type=tx_type,
                    amount=val,
                    reference=parsed_row.get('notes') or f'Imported {tx_type}'
                )
                # Update balance aggregate
                current = getattr(balance, bal_field)
                setattr(balance, bal_field, current + val)
                made_changes = True

    if made_changes:
        balance.save()
        
    return 'created' if created else 'updated'


EXECUTOR_MAP = {
    'employees': execute_employees,
    'branches': execute_branches,
    'departments': execute_departments,
    'designations': execute_designations,
    'leave_types': execute_leave_types,
    'holidays': execute_holidays,
    'attendance': execute_attendance,
    'salary_structures': execute_salary_structures,
    'leave_balances': execute_leave_balances,
}
