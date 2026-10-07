"""
Universal CSV Data Import — Template Registry

Single authoritative backend source of truth for all nine locked V1 CSV templates.
Every template definition contains: stable key, display name, exact ordered headers,
schema version, field definitions (type, required, validation, resolver, destination).

DO NOT add, remove, rename, or reorder headers without a version bump.
"""

from collections import OrderedDict


# ── Field type constants ──────────────────────────────────────────────────────
TYPE_STRING = 'string'
TYPE_EMAIL = 'email'
TYPE_DATE = 'date'
TYPE_DATETIME = 'datetime'
TYPE_TIME = 'time'
TYPE_INTEGER = 'integer'
TYPE_DECIMAL = 'decimal'
TYPE_BOOLEAN = 'boolean'
TYPE_DURATION = 'duration'
TYPE_ENUM = 'enum'
TYPE_CSV_LIST = 'csv_list'        # comma-separated list within a cell
TYPE_COMPONENT = 'component'      # dynamic salary component columns

# ── Resolver keys ─────────────────────────────────────────────────────────────
RESOLVE_BRANCH = 'branch_code'
RESOLVE_DEPARTMENT = 'department_code'
RESOLVE_DESIGNATION = 'designation_code'
RESOLVE_SHIFT = 'shift_code'
RESOLVE_EMPLOYEE = 'employee_code'
RESOLVE_LEAVE_TYPE = 'leave_type_code'
RESOLVE_COMPANY = 'company_code'
RESOLVE_MANAGER = 'manager_code'
RESOLVE_ROLE = 'role_name'
RESOLVE_BRANCH_LIST = 'branch_code_list'

# ── Enum value sets ───────────────────────────────────────────────────────────
GENDER_CHOICES = {'male', 'female', 'other'}
MARITAL_STATUS_CHOICES = {'single', 'married', 'divorced', 'widowed'}
BLOOD_GROUP_CHOICES = {'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'}
EMPLOYMENT_TYPE_CHOICES = {'full_time', 'part_time', 'contract'}
EMPLOYMENT_STATUS_CHOICES = {'onboarding', 'active', 'on_notice', 'on_leave', 'inactive', 'exited'}
USER_STATUS_CHOICES = {'active', 'inactive', 'invited'}
ATTENDANCE_STATUS_CHOICES = {'present', 'absent', 'half_day'}
ACCRUAL_CHOICES = {'monthly', 'yearly', 'none'}
ACCRUAL_STARTS_ON_CHOICES = {'joining_date', 'confirmation_date'}
APPLICABLE_GENDER_CHOICES = {'all', 'male', 'female', 'other'}
PAYMENT_MODE_CHOICES = {'BANK_TRANSFER', 'CHEQUE', 'CASH'}
HOLIDAY_TYPE_CHOICES = {'national', 'regional', 'restricted', 'company', 'optional'}
ACTIVE_STATUS_CHOICES = {'active', 'inactive'}


def _field(csv_header, field_type, required=False, destination_model=None,
           destination_field=None, resolver=None, enum_values=None,
           description='', max_length=None, min_value=None):
    """Helper to build a standardised field definition dict."""
    defn = OrderedDict()
    defn['csv_header'] = csv_header
    defn['type'] = field_type
    defn['required'] = required
    defn['destination_model'] = destination_model
    defn['destination_field'] = destination_field
    if resolver:
        defn['resolver'] = resolver
    if enum_values:
        defn['enum_values'] = enum_values
    if max_length:
        defn['max_length'] = max_length
    if min_value is not None:
        defn['min_value'] = min_value
    defn['description'] = description
    return defn


# ═══════════════════════════════════════════════════════════════════════════════
# 1. EMPLOYEES
# ═══════════════════════════════════════════════════════════════════════════════
EMPLOYEES_FIELDS = [
    _field('employee_code', TYPE_STRING, required=True, destination_model='Employee', destination_field='employee_code', description='Unique employee identifier within organization'),
    _field('first_name', TYPE_STRING, required=True, destination_model='User', destination_field='first_name'),
    _field('last_name', TYPE_STRING, required=True, destination_model='User', destination_field='last_name'),
    _field('email', TYPE_EMAIL, required=True, destination_model='User', destination_field='email', description='Primary login email — must be globally unique'),
    _field('personal_email', TYPE_EMAIL, required=False, destination_model='Employee', destination_field='personal_email'),
    _field('phone', TYPE_STRING, required=False, destination_model='Employee', destination_field='phone_number', max_length=20),
    _field('alternate_phone', TYPE_STRING, required=False, destination_model='Employee', destination_field='alternate_phone', max_length=20),
    _field('gender', TYPE_ENUM, required=False, destination_model='Employee', destination_field='gender', enum_values=GENDER_CHOICES),
    _field('date_of_birth', TYPE_DATE, required=False, destination_model='Employee', destination_field='date_of_birth'),
    _field('marital_status', TYPE_ENUM, required=False, destination_model='Employee', destination_field='marital_status', enum_values=MARITAL_STATUS_CHOICES),
    _field('blood_group', TYPE_STRING, required=False, destination_model='Employee', destination_field='blood_group', max_length=10),
    _field('nationality', TYPE_STRING, required=False, destination_model='Employee', destination_field='nationality', max_length=100),
    _field('company_code', TYPE_STRING, required=False, destination_model='Organization', destination_field='code', resolver=RESOLVE_COMPANY, description='Must match authenticated org or be blank'),
    _field('branch_code', TYPE_STRING, required=True, destination_model='Employee', destination_field='branch', resolver=RESOLVE_BRANCH),
    _field('department_code', TYPE_STRING, required=True, destination_model='Employee', destination_field='department', resolver=RESOLVE_DEPARTMENT),
    _field('designation_code', TYPE_STRING, required=True, destination_model='Employee', destination_field='designation', resolver=RESOLVE_DESIGNATION),
    _field('shift_code', TYPE_STRING, required=False, destination_model='EmployeeShiftAssignment', destination_field='shift', resolver=RESOLVE_SHIFT),
    _field('manager_code', TYPE_STRING, required=False, destination_model='Employee', destination_field='reporting_manager', resolver=RESOLVE_MANAGER),
    _field('employment_type', TYPE_ENUM, required=True, destination_model='Employee', destination_field='employment_type', enum_values=EMPLOYMENT_TYPE_CHOICES),
    _field('employment_status', TYPE_ENUM, required=True, destination_model='Employee', destination_field='employment_status', enum_values=EMPLOYMENT_STATUS_CHOICES),
    _field('date_of_joining', TYPE_DATE, required=True, destination_model='Employee', destination_field='joining_date'),
    _field('date_of_confirmation', TYPE_DATE, required=False, destination_model='Employee', destination_field='confirmation_date'),
    _field('date_of_exit', TYPE_DATE, required=False, destination_model='Employee', destination_field='exit_date'),
    _field('notice_period_days', TYPE_INTEGER, required=False, destination_model='Employee', destination_field='notice_period_days', min_value=0),
    _field('address_line1', TYPE_STRING, required=False, destination_model='Employee', destination_field='address_line1', max_length=255),
    _field('address_line2', TYPE_STRING, required=False, destination_model='Employee', destination_field='address_line2', max_length=255),
    _field('city', TYPE_STRING, required=False, destination_model='Employee', destination_field='city', max_length=100),
    _field('state', TYPE_STRING, required=False, destination_model='Employee', destination_field='state', max_length=100),
    _field('country', TYPE_STRING, required=False, destination_model='Employee', destination_field='country', max_length=100),
    _field('postal_code', TYPE_STRING, required=False, destination_model='Employee', destination_field='postal_code', max_length=20),
    _field('emergency_contact_name', TYPE_STRING, required=False, destination_model='Employee', destination_field='emergency_contact_name', max_length=150),
    _field('emergency_contact_phone', TYPE_STRING, required=False, destination_model='Employee', destination_field='emergency_contact_phone', max_length=20),
    _field('emergency_contact_relation', TYPE_STRING, required=False, destination_model='Employee', destination_field='emergency_contact_relation', max_length=100),
    _field('bank_name', TYPE_STRING, required=False, destination_model='EmployeeStatutoryAndBank', destination_field='bank_name', max_length=150),
    _field('bank_account_name', TYPE_STRING, required=False, destination_model='EmployeeStatutoryAndBank', destination_field='account_name', max_length=150),
    _field('bank_account_number', TYPE_STRING, required=False, destination_model='EmployeeStatutoryAndBank', destination_field='account_number', max_length=50),
    _field('bank_ifsc', TYPE_STRING, required=False, destination_model='EmployeeStatutoryAndBank', destination_field='ifsc_code', max_length=20),
    _field('bank_branch', TYPE_STRING, required=False, destination_model='EmployeeStatutoryAndBank', destination_field='bank_branch', max_length=150),
    _field('pan_number', TYPE_STRING, required=False, destination_model='EmployeeStatutoryAndBank', destination_field='pan_number', max_length=20),
    _field('national_id', TYPE_STRING, required=False, destination_model='EmployeeStatutoryAndBank', destination_field='aadhaar_number', max_length=20),
    _field('pf_number', TYPE_STRING, required=False, destination_model='EmployeeStatutoryAndBank', destination_field='pf_account_number', max_length=50),
    _field('esi_number', TYPE_STRING, required=False, destination_model='EmployeeStatutoryAndBank', destination_field='esic_number', max_length=50),
    _field('uan_number', TYPE_STRING, required=False, destination_model='EmployeeStatutoryAndBank', destination_field='uan_number', max_length=50),
    _field('role', TYPE_STRING, required=False, destination_model='UserRole', destination_field='role', resolver=RESOLVE_ROLE, description='MUST NEVER create Super Admin or elevate to global superuser'),
    _field('status', TYPE_ENUM, required=True, destination_model='User', destination_field='status', enum_values=USER_STATUS_CHOICES),
    _field('notes', TYPE_STRING, required=False, destination_model='Employee', destination_field='notes'),
]

# ═══════════════════════════════════════════════════════════════════════════════
# 2. BRANCHES
# ═══════════════════════════════════════════════════════════════════════════════
BRANCHES_FIELDS = [
    _field('code', TYPE_STRING, required=True, destination_model='Branch', destination_field='code', description='Unique branch code within organization'),
    _field('name', TYPE_STRING, required=True, destination_model='Branch', destination_field='name'),
    _field('email', TYPE_EMAIL, required=False, destination_model='Branch', destination_field='email'),
    _field('phone', TYPE_STRING, required=False, destination_model='Branch', destination_field='phone', max_length=20),
    _field('address_line1', TYPE_STRING, required=False, destination_model='Branch', destination_field='address_line1', max_length=255),
    _field('address_line2', TYPE_STRING, required=False, destination_model='Branch', destination_field='address_line2', max_length=255),
    _field('city', TYPE_STRING, required=False, destination_model='Branch', destination_field='city', max_length=100),
    _field('state', TYPE_STRING, required=False, destination_model='Branch', destination_field='state', max_length=100),
    _field('country', TYPE_STRING, required=False, destination_model='Branch', destination_field='country', max_length=100),
    _field('postal_code', TYPE_STRING, required=False, destination_model='Branch', destination_field='postal_code', max_length=20),
    _field('latitude', TYPE_DECIMAL, required=False, destination_model='Branch', destination_field='latitude'),
    _field('longitude', TYPE_DECIMAL, required=False, destination_model='Branch', destination_field='longitude'),
    _field('geofence_radius_metres', TYPE_DECIMAL, required=False, destination_model='Branch', destination_field='radius', min_value=100.0),
    _field('timezone', TYPE_STRING, required=True, destination_model='Branch', destination_field='timezone', max_length=50),
    _field('work_start_time', TYPE_TIME, required=True, destination_model='Shift', destination_field='start_time', description='Creates a default shift for the branch'),
    _field('work_end_time', TYPE_TIME, required=True, destination_model='Shift', destination_field='end_time'),
    _field('working_days', TYPE_STRING, required=True, destination_model='WorkingCalendar', destination_field='work_days', description='Comma-separated day names or integers'),
    _field('saturday_offs', TYPE_STRING, required=False, destination_model='WorkingCalendarRule', destination_field='occurrence', description='e.g. 2nd,4th'),
    _field('is_head_office', TYPE_BOOLEAN, required=False, destination_model='Branch', destination_field='is_head_office'),
    _field('status', TYPE_ENUM, required=True, destination_model='Branch', destination_field='is_active', enum_values=ACTIVE_STATUS_CHOICES),
]

# ═══════════════════════════════════════════════════════════════════════════════
# 3. DEPARTMENTS
# ═══════════════════════════════════════════════════════════════════════════════
DEPARTMENTS_FIELDS = [
    _field('code', TYPE_STRING, required=True, destination_model='Department', destination_field='code', description='Unique department code within branch'),
    _field('name', TYPE_STRING, required=True, destination_model='Department', destination_field='name'),
    _field('branch_code', TYPE_STRING, required=True, destination_model='Department', destination_field='branch', resolver=RESOLVE_BRANCH),
    _field('description', TYPE_STRING, required=False, destination_model='Department', destination_field='description'),
    _field('status', TYPE_ENUM, required=True, destination_model='Department', destination_field='is_active', enum_values=ACTIVE_STATUS_CHOICES),
]

# ═══════════════════════════════════════════════════════════════════════════════
# 4. DESIGNATIONS
# ═══════════════════════════════════════════════════════════════════════════════
DESIGNATIONS_FIELDS = [
    _field('code', TYPE_STRING, required=True, destination_model='Designation', destination_field='code', description='Unique designation code within organization'),
    _field('name', TYPE_STRING, required=True, destination_model='Designation', destination_field='name'),
    _field('level', TYPE_INTEGER, required=False, destination_model='Designation', destination_field='level', min_value=0),
    _field('description', TYPE_STRING, required=False, destination_model='Designation', destination_field='description'),
    _field('status', TYPE_ENUM, required=True, destination_model='Designation', destination_field='is_active', enum_values=ACTIVE_STATUS_CHOICES),
]

# ═══════════════════════════════════════════════════════════════════════════════
# 5. LEAVE TYPES
# ═══════════════════════════════════════════════════════════════════════════════
LEAVE_TYPES_FIELDS = [
    _field('code', TYPE_STRING, required=True, destination_model='LeaveType', destination_field='code', description='Unique leave type code within organization'),
    _field('name', TYPE_STRING, required=True, destination_model='LeaveType', destination_field='name'),
    _field('days_per_year', TYPE_DECIMAL, required=True, description='Total annual entitlement — used for validation only'),
    _field('accrual', TYPE_ENUM, required=True, destination_model='LeaveType', destination_field='accrual_frequency', enum_values=ACCRUAL_CHOICES),
    _field('days_per_month', TYPE_DECIMAL, required=False, destination_model='BranchLeavePolicy', destination_field='monthly_allocation'),
    _field('probation_days_per_month', TYPE_DECIMAL, required=False, destination_model='BranchLeavePolicy', destination_field='probation_monthly_allocation'),
    _field('accrue_in_advance', TYPE_BOOLEAN, required=False, destination_model='BranchLeavePolicy', destination_field='accrue_in_advance'),
    _field('accrual_starts_on', TYPE_ENUM, required=False, destination_model='BranchLeavePolicy', destination_field='accrual_starts_on', enum_values=ACCRUAL_STARTS_ON_CHOICES),
    _field('is_paid', TYPE_BOOLEAN, required=True, destination_model='BranchLeavePolicy', destination_field='is_paid'),
    _field('requires_approval', TYPE_BOOLEAN, required=False, destination_model='BranchLeavePolicy', destination_field='requires_approval'),
    _field('allow_half_day', TYPE_BOOLEAN, required=False, destination_model='BranchLeavePolicy', destination_field='half_day_allowed'),
    _field('carry_forward', TYPE_BOOLEAN, required=False, destination_model='BranchLeavePolicy', destination_field='carry_forward_enabled'),
    _field('max_carry_forward_days', TYPE_DECIMAL, required=False, destination_model='BranchLeavePolicy', destination_field='carry_forward_limit'),
    _field('max_consecutive_days', TYPE_INTEGER, required=False, destination_model='BranchLeavePolicy', destination_field='max_consecutive_days'),
    _field('min_notice_days', TYPE_INTEGER, required=False, destination_model='BranchLeavePolicy', destination_field='advance_notice_days', min_value=0),
    _field('applicable_gender', TYPE_ENUM, required=False, destination_model='BranchLeavePolicy', destination_field='applicable_gender', enum_values=APPLICABLE_GENDER_CHOICES),
    _field('applicable_after_months', TYPE_INTEGER, required=False, destination_model='BranchLeavePolicy', destination_field='applicable_after_months', min_value=0),
    _field('requires_attachment', TYPE_BOOLEAN, required=False, destination_model='BranchLeavePolicy', destination_field='requires_supporting_document'),
    _field('color', TYPE_STRING, required=False, destination_model='LeaveType', destination_field='color_code', max_length=20),
    _field('description', TYPE_STRING, required=False, destination_model='LeaveType', destination_field='description'),
    _field('status', TYPE_ENUM, required=True, destination_model='LeaveType', destination_field='is_active', enum_values=ACTIVE_STATUS_CHOICES),
]

# ═══════════════════════════════════════════════════════════════════════════════
# 6. HOLIDAYS
# ═══════════════════════════════════════════════════════════════════════════════
HOLIDAYS_FIELDS = [
    _field('name', TYPE_STRING, required=True, destination_model='Holiday', destination_field='name'),
    _field('date', TYPE_DATE, required=True, destination_model='Holiday', destination_field='date'),
    _field('type', TYPE_ENUM, required=False, destination_model='Holiday', destination_field='holiday_type', enum_values=HOLIDAY_TYPE_CHOICES),
    _field('branches', TYPE_CSV_LIST, required=True, destination_model='Holiday', destination_field='branch', resolver=RESOLVE_BRANCH_LIST, description='Comma-separated branch codes'),
    _field('description', TYPE_STRING, required=False, destination_model='Holiday', destination_field='description'),
    _field('is_recurring', TYPE_BOOLEAN, required=False, destination_model='Holiday', destination_field='is_recurring'),
]

# ═══════════════════════════════════════════════════════════════════════════════
# 7. ATTENDANCE
# ═══════════════════════════════════════════════════════════════════════════════
ATTENDANCE_FIELDS = [
    _field('employee_code', TYPE_STRING, required=True, destination_model='Attendance', destination_field='employee', resolver=RESOLVE_EMPLOYEE),
    _field('date', TYPE_DATE, required=True, destination_model='Attendance', destination_field='date'),
    _field('check_in', TYPE_DATETIME, required=False, destination_model='Attendance', destination_field='check_in'),
    _field('check_out', TYPE_DATETIME, required=False, destination_model='Attendance', destination_field='check_out'),
    _field('status', TYPE_ENUM, required=True, destination_model='Attendance', destination_field='status', enum_values=ATTENDANCE_STATUS_CHOICES),
    _field('remarks', TYPE_STRING, required=False, destination_model='Attendance', destination_field='remarks'),
    _field('online_duration', TYPE_DURATION, required=False, destination_model='AttendanceProductivity', destination_field='online_duration'),
    _field('active_duration', TYPE_DURATION, required=False, destination_model='AttendanceProductivity', destination_field='active_duration'),
    _field('idle_duration', TYPE_DURATION, required=False, destination_model='AttendanceProductivity', destination_field='idle_duration'),
    _field('productive_duration', TYPE_DURATION, required=False, destination_model='AttendanceProductivity', destination_field='productive_duration'),
    _field('unproductive_duration', TYPE_DURATION, required=False, destination_model='AttendanceProductivity', destination_field='unproductive_duration'),
    _field('neutral_duration', TYPE_DURATION, required=False, destination_model='AttendanceProductivity', destination_field='neutral_duration'),
    _field('active_percent', TYPE_DECIMAL, required=False, destination_model='AttendanceProductivity', destination_field='active_percent'),
    _field('mouse_clicks', TYPE_INTEGER, required=False, destination_model='AttendanceProductivity', destination_field='mouse_clicks', min_value=0),
    _field('key_presses', TYPE_INTEGER, required=False, destination_model='AttendanceProductivity', destination_field='key_presses', min_value=0),
]

# ═══════════════════════════════════════════════════════════════════════════════
# 8. SALARY STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════
SALARY_STRUCTURES_FIELDS = [
    _field('employee_code', TYPE_STRING, required=True, destination_model='CompensationHistory', destination_field='employee', resolver=RESOLVE_EMPLOYEE),
    _field('effective_from', TYPE_DATE, required=True, destination_model='CompensationHistory', destination_field='effective_from'),
    _field('ctc_annual', TYPE_DECIMAL, required=True, destination_model='CompensationHistory', destination_field='ctc_annual'),
    _field('basic_salary', TYPE_DECIMAL, required=True, destination_model='CompensationHistory', destination_field='basic_salary', min_value=0),
    _field('currency', TYPE_STRING, required=True, destination_model='CompensationHistory', destination_field='currency', max_length=10),
    _field('payment_mode', TYPE_ENUM, required=False, destination_model='EmployeeStatutoryAndBank', destination_field='payment_mode', enum_values=PAYMENT_MODE_CHOICES),
    _field('notes', TYPE_STRING, required=False, destination_model='CompensationHistory', destination_field='notes'),
    # component:* columns are dynamic — handled by the engine at parse time
    _field('component:basic', TYPE_DECIMAL, required=False, destination_model='SalaryStructureComponent', destination_field='amount'),
    _field('component:hra', TYPE_DECIMAL, required=False, destination_model='SalaryStructureComponent', destination_field='amount'),
    _field('component:conv', TYPE_DECIMAL, required=False, destination_model='SalaryStructureComponent', destination_field='amount'),
    _field('component:med', TYPE_DECIMAL, required=False, destination_model='SalaryStructureComponent', destination_field='amount'),
    _field('component:spl', TYPE_DECIMAL, required=False, destination_model='SalaryStructureComponent', destination_field='amount'),
    _field('component:pf', TYPE_DECIMAL, required=False, destination_model='SalaryStructureComponent', destination_field='amount'),
    _field('component:pt', TYPE_DECIMAL, required=False, destination_model='SalaryStructureComponent', destination_field='amount'),
    _field('component:tds', TYPE_DECIMAL, required=False, destination_model='SalaryStructureComponent', destination_field='amount'),
]

# ═══════════════════════════════════════════════════════════════════════════════
# 9. LEAVE BALANCES
# ═══════════════════════════════════════════════════════════════════════════════
LEAVE_BALANCES_FIELDS = [
    _field('employee_code', TYPE_STRING, required=True, destination_model='LeaveBalance', destination_field='employee', resolver=RESOLVE_EMPLOYEE),
    _field('leave_type_code', TYPE_STRING, required=True, destination_model='LeaveBalance', destination_field='leave_type', resolver=RESOLVE_LEAVE_TYPE),
    _field('year', TYPE_INTEGER, required=True, destination_model='LeaveBalance', destination_field='leave_cycle', description='Calendar year — resolves to LeaveCycle'),
    _field('allocated_days', TYPE_DECIMAL, required=True, destination_model='LeaveBalanceTransaction', destination_field='amount', description='Creates legacy_conversion_allocated transaction'),
    _field('carried_forward_days', TYPE_DECIMAL, required=False, destination_model='LeaveBalanceTransaction', destination_field='amount', description='Creates legacy_conversion_carry_forward transaction'),
    _field('used_days', TYPE_DECIMAL, required=False, destination_model='LeaveBalanceTransaction', destination_field='amount', description='Creates legacy_conversion_used transaction'),
    _field('encashed_days', TYPE_DECIMAL, required=False, destination_model='LeaveBalanceTransaction', destination_field='amount', description='Creates legacy_conversion_encashed transaction'),
    _field('notes', TYPE_STRING, required=False, destination_model='LeaveBalanceTransaction', destination_field='reference'),
]


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATE REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

TEMPLATE_REGISTRY = OrderedDict()

def _register(key, display_name, filename, fields, identity_fields, description=''):
    """Register a template in the global registry."""
    headers = [f['csv_header'] for f in fields]
    TEMPLATE_REGISTRY[key] = {
        'key': key,
        'display_name': display_name,
        'filename': filename,
        'version': 'v1',
        'description': description,
        'headers': headers,
        'fields': fields,
        'identity_fields': identity_fields,
    }


_register(
    key='employees',
    display_name='Employees',
    filename='hrms-employees-template.csv',
    fields=EMPLOYEES_FIELDS,
    identity_fields=['employee_code'],
    description='Import employees with full profile, bank, statutory, and role data',
)

_register(
    key='branches',
    display_name='Branches',
    filename='hrms-branches-template.csv',
    fields=BRANCHES_FIELDS,
    identity_fields=['code'],
    description='Import branches with address, timezone, shift, and calendar configuration',
)

_register(
    key='departments',
    display_name='Departments',
    filename='hrms-departments-template.csv',
    fields=DEPARTMENTS_FIELDS,
    identity_fields=['code', 'branch_code'],
    description='Import departments scoped to branches',
)

_register(
    key='designations',
    display_name='Designations',
    filename='hrms-designations-template.csv',
    fields=DESIGNATIONS_FIELDS,
    identity_fields=['code'],
    description='Import designation levels within the organization',
)

_register(
    key='leave_types',
    display_name='Leave Types',
    filename='hrms-leave-types-template.csv',
    fields=LEAVE_TYPES_FIELDS,
    identity_fields=['code'],
    description='Import leave types with accrual and policy configuration',
)

_register(
    key='holidays',
    display_name='Holidays',
    filename='hrms-holidays-template.csv',
    fields=HOLIDAYS_FIELDS,
    identity_fields=['name', 'date'],
    description='Import holidays for one or more branches',
)

_register(
    key='attendance',
    display_name='Attendance',
    filename='hrms-attendance-template.csv',
    fields=ATTENDANCE_FIELDS,
    identity_fields=['employee_code', 'date'],
    description='Import attendance records with optional productivity metrics',
)

_register(
    key='salary_structures',
    display_name='Salary Structures',
    filename='hrms-salary-structures-template.csv',
    fields=SALARY_STRUCTURES_FIELDS,
    identity_fields=['employee_code', 'effective_from'],
    description='Import compensation history with salary component breakdown',
)

_register(
    key='leave_balances',
    display_name='Leave Balances',
    filename='hrms-leave-balances-template.csv',
    fields=LEAVE_BALANCES_FIELDS,
    identity_fields=['employee_code', 'leave_type_code', 'year'],
    description='Import legacy leave balances with ledger transactions',
)


def get_template(key):
    """Return template definition by key or None."""
    return TEMPLATE_REGISTRY.get(key)


def get_template_headers(key):
    """Return the exact ordered header list for a template."""
    tmpl = get_template(key)
    return tmpl['headers'] if tmpl else None


def get_all_template_keys():
    """Return list of all registered template keys."""
    return list(TEMPLATE_REGISTRY.keys())


def generate_csv_content(key):
    """Generate an empty CSV template with only the header row."""
    headers = get_template_headers(key)
    if not headers:
        return None
    return ','.join(headers) + '\n'
