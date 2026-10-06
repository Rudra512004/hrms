from .framework import BaseCSVImporter
from apps.organization.models import Branch, Department, Designation
import logging

logger = logging.getLogger(__name__)

class BranchImporter(BaseCSVImporter):
    EXPECTED_HEADERS = ['branch_name', 'branch_code', 'address', 'contact_number', 'is_active']

    def process_row(self, row_idx: int, row_data: dict):
        branch_name = row_data.get('branch_name', '').strip()
        branch_code = row_data.get('branch_code', '').strip()
        address = row_data.get('address', '').strip()
        contact_number = row_data.get('contact_number', '').strip()
        is_active_str = row_data.get('is_active', 'true').strip().lower()

        if not branch_name:
            raise ValueError("branch_name is required.")
        if not branch_code:
            raise ValueError("branch_code is required.")

        is_active = is_active_str in ('true', '1', 'yes')

        # Tenant isolation happens naturally since we enforce organization=self.organization
        branch, created = Branch.objects.update_or_create(
            organization=self.organization,
            name=branch_name,
            defaults={
                'address': address,
                'contact_number': contact_number,
                'is_active': is_active
            }
        )

class DepartmentImporter(BaseCSVImporter):
    EXPECTED_HEADERS = ['department_name', 'department_code', 'branch_code', 'description', 'is_active']

    def process_row(self, row_idx: int, row_data: dict):
        dept_name = row_data.get('department_name', '').strip()
        dept_code = row_data.get('department_code', '').strip()
        branch_code = row_data.get('branch_code', '').strip()
        description = row_data.get('description', '').strip()
        is_active_str = row_data.get('is_active', 'true').strip().lower()

        if not dept_name:
            raise ValueError("department_name is required.")
        if not dept_code:
            raise ValueError("department_code is required.")
        if not branch_code:
            raise ValueError("branch_code is required.")

        is_active = is_active_str in ('true', '1', 'yes')

        # Tenant isolation on Branch
        branch = Branch.objects.filter(organization=self.organization, name=branch_code).first()
        if not branch:
            raise ValueError(f"Branch with code '{branch_code}' does not exist in your organization.")

        Department.objects.update_or_create(
            branch=branch,
            name=dept_name,
            defaults={
                'description': description,
                'is_active': is_active
            }
        )

class EmployeeImporter(BaseCSVImporter):
    EXPECTED_HEADERS = [
        'employee_code', 'first_name', 'last_name', 'email'
    ]

    def process_row(self, row_idx: int, row_data: dict):
        from django.contrib.auth import get_user_model
        from apps.employees.models import Employee, EmployeeStatutoryInfo
        User = get_user_model()

        email = row_data.get('email', '').strip()
        first_name = row_data.get('first_name', '').strip()
        last_name = row_data.get('last_name', '').strip()
        employee_code = row_data.get('employee_code', '').strip()
        branch_code = row_data.get('branch_code', '').strip()
        department_code = row_data.get('department_code', '').strip()

        if not email or not first_name or not employee_code:
            raise ValueError("email, first_name, and employee_code are required.")

        branch = None
        if branch_code:
            branch = Branch.objects.filter(organization=self.organization, name=branch_code).first()
            if not branch:
                raise ValueError(f"Branch code '{branch_code}' not found.")

        dept = None
        if department_code:
            dept = Department.objects.filter(branch__organization=self.organization, name=department_code).first()
            if not dept:
                raise ValueError(f"Department code '{department_code}' not found.")

        reporting_manager_code = row_data.get('reporting_manager_code', '').strip()
        manager = None
        if reporting_manager_code:
            manager = Employee.objects.filter(organization=self.organization, employee_code=reporting_manager_code).first()
            if not manager:
                raise ValueError(f"Reporting manager with code '{reporting_manager_code}' not found.")
            if employee_code == reporting_manager_code:
                raise ValueError("Employee cannot report to themselves.")

        # Create or update user
        user, _ = User.objects.update_or_create(
            email=email,
            defaults={'first_name': first_name, 'last_name': last_name}
        )

        employee, _ = Employee.objects.update_or_create(
            employee_code=employee_code,
            organization=self.organization,
            defaults={
                'user': user,
                'branch': branch,
                'department': dept,
                'reporting_manager': manager,
                'personal_email': row_data.get('personal_email', '').strip(),
                'phone_number': row_data.get('phone_number', '').strip(),
                'gender': row_data.get('gender', '').strip(),
                'date_of_birth': row_data.get('date_of_birth', '').strip() or None,
                'marital_status': row_data.get('marital_status', '').strip(),
                'blood_group': row_data.get('blood_group', '').strip(),
                'nationality': row_data.get('nationality', '').strip(),
                'address_line1': row_data.get('address_line1', '').strip(),
                'address_line2': row_data.get('address_line2', '').strip(),
                'city': row_data.get('city', '').strip(),
                'state': row_data.get('state', '').strip(),
                'country': row_data.get('country', '').strip(),
                'postal_code': row_data.get('postal_code', '').strip(),
            }
        )

        EmployeeStatutoryInfo.objects.update_or_create(
            employee=employee,
            defaults={
                'bank_name': row_data.get('bank_name', '').strip(),
                'account_number': row_data.get('account_number', '').strip(),
                'ifsc': row_data.get('ifsc', '').strip(),
                'pan': row_data.get('pan', '').strip(),
            }
        )


# ---------------------------------------------------------------------------
# Designation Importer
# ---------------------------------------------------------------------------

class DesignationImporter(BaseCSVImporter):
    """
    Maps: designation_name, description, is_active
    Tenant boundary: organization=self.organization
    unique_together: (organization, name) → update_or_create
    """
    EXPECTED_HEADERS = ['designation_name']

    def process_row(self, row_idx: int, row_data: dict):
        name = row_data.get('designation_name', '').strip()
        description = row_data.get('description', '').strip()
        is_active_str = row_data.get('is_active', 'true').strip().lower()

        if not name:
            raise ValueError("designation_name is required.")

        is_active = is_active_str in ('true', '1', 'yes')

        Designation.objects.update_or_create(
            organization=self.organization,
            name=name,
            defaults={
                'description': description,
                'is_active': is_active,
            }
        )


# ---------------------------------------------------------------------------
# Holiday Importer
# ---------------------------------------------------------------------------

class HolidayImporter(BaseCSVImporter):
    """
    Maps: branch_code, holiday_name, date, is_active
    Holiday model is branch-scoped.
    unique_together: (branch, date) → update name on duplicate date.
    Productivity fields in the template are not part of this model.
    """
    EXPECTED_HEADERS = ['branch_code', 'holiday_name', 'date']

    def process_row(self, row_idx: int, row_data: dict):
        from apps.attendance.models import Holiday
        import datetime

        branch_code = row_data.get('branch_code', '').strip()
        holiday_name = row_data.get('holiday_name', '').strip()
        date_str = row_data.get('date', '').strip()
        is_active_str = row_data.get('is_active', 'true').strip().lower()

        if not branch_code:
            raise ValueError("branch_code is required.")
        if not holiday_name:
            raise ValueError("holiday_name is required.")
        if not date_str:
            raise ValueError("date is required.")

        # Tenant-isolated branch lookup
        branch = Branch.objects.filter(organization=self.organization, name=branch_code).first()
        if not branch:
            raise ValueError(f"Branch '{branch_code}' not found in your organization.")

        try:
            date_value = datetime.date.fromisoformat(date_str)
        except ValueError:
            raise ValueError(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD.")

        is_active = is_active_str in ('true', '1', 'yes')

        Holiday.objects.update_or_create(
            branch=branch,
            date=date_value,
            defaults={
                'name': holiday_name,
                'is_active': is_active,
            }
        )


# ---------------------------------------------------------------------------
# Leave Type Importer
# ---------------------------------------------------------------------------

class LeaveTypeImporter(BaseCSVImporter):
    """
    Maps CSV fields to LeaveType + optional BranchLeavePolicy.

    SUPPORTED fields:
      name, description, is_active
      branch_code → BranchLeavePolicy (optional)
      monthly_allocation / days_per_month → BranchLeavePolicy.monthly_allocation
      carry_forward_enabled, carry_forward_limit / max_carry_forward_days,
      carry_forward_expiry_months, half_day_allowed, is_paid,
      requires_supporting_document / requires_attachment,
      advance_notice_days / min_notice_days,
      cancellation_allowed, negative_balance_allowed, proration_enabled,
      proration_rounding

    UNSUPPORTED (no model field — reported, not silently dropped):
      code, days_per_year, accrual, probation_days_per_month,
      accrue_in_advance, accrual_starts_on, applicable_gender,
      applicable_after_months, max_consecutive_days, color
    """
    UNSUPPORTED_FIELDS = [
        'code', 'days_per_year', 'accrual', 'probation_days_per_month',
        'accrue_in_advance', 'accrual_starts_on', 'applicable_gender',
        'applicable_after_months', 'max_consecutive_days', 'color',
    ]

    EXPECTED_HEADERS = ['name']

    def process_row(self, row_idx: int, row_data: dict):
        from apps.leaves.models import LeaveType, BranchLeavePolicy

        name = row_data.get('name', '').strip()
        if not name:
            raise ValueError("name is required.")

        description = row_data.get('description', '').strip()
        is_active_str = row_data.get('is_active', 'true').strip().lower()
        is_active = is_active_str in ('true', '1', 'yes')

        # Warn about unsupported fields (non-fatal — logged, not blocking)
        for field in self.UNSUPPORTED_FIELDS:
            val = row_data.get(field, '').strip()
            if val:
                logger.warning(
                    f"Row {row_idx}: CSV field '{field}' has no mapping in the HRMS LeaveType model "
                    f"and will not be imported. Value: '{val}'."
                )

        leave_type, _ = LeaveType.objects.update_or_create(
            organization=self.organization,
            name=name,
            defaults={
                'description': description,
                'is_active': is_active,
            }
        )

        # Optional branch-level policy
        branch_code = row_data.get('branch_code', '').strip()
        if branch_code:
            branch = Branch.objects.filter(organization=self.organization, name=branch_code).first()
            if not branch:
                raise ValueError(f"Branch '{branch_code}' not found in your organization.")

            def _decimal_or_none(key):
                val = row_data.get(key, '').strip()
                if not val:
                    return None
                try:
                    from decimal import Decimal
                    return Decimal(val)
                except Exception:
                    raise ValueError(f"Invalid decimal value for '{key}': '{val}'.")

            def _int_or_none(key):
                val = row_data.get(key, '').strip()
                if not val:
                    return None
                try:
                    return int(val)
                except Exception:
                    raise ValueError(f"Invalid integer value for '{key}': '{val}'.")

            def _bool(key, default='true'):
                return row_data.get(key, default).strip().lower() in ('true', '1', 'yes')

            # days_per_month is a CSV alias for monthly_allocation
            monthly_allocation = (
                _decimal_or_none('monthly_allocation')
                or _decimal_or_none('days_per_month')
                or 0
            )
            carry_forward_limit = (
                _decimal_or_none('carry_forward_limit')
                or _decimal_or_none('max_carry_forward_days')
            )
            advance_notice_days = (
                _int_or_none('advance_notice_days')
                or _int_or_none('min_notice_days')
                or 0
            )
            requires_doc = (
                _bool('requires_supporting_document', 'false')
                or _bool('requires_attachment', 'false')
            )

            proration_rounding = row_data.get('proration_rounding', 'nearest_half').strip()
            valid_roundings = ('nearest_half', 'floor', 'ceiling')
            if proration_rounding not in valid_roundings:
                raise ValueError(
                    f"Invalid proration_rounding '{proration_rounding}'. "
                    f"Must be one of: {', '.join(valid_roundings)}."
                )

            BranchLeavePolicy.objects.update_or_create(
                branch=branch,
                leave_type=leave_type,
                defaults={
                    'monthly_allocation': monthly_allocation,
                    'proration_enabled': _bool('proration_enabled'),
                    'proration_rounding': proration_rounding,
                    'carry_forward_enabled': _bool('carry_forward_enabled', 'false'),
                    'carry_forward_limit': carry_forward_limit,
                    'carry_forward_expiry_months': _int_or_none('carry_forward_expiry_months'),
                    'negative_balance_allowed': _bool('negative_balance_allowed', 'false'),
                    'half_day_allowed': _bool('half_day_allowed', 'false'),
                    'is_paid': _bool('is_paid'),
                    'requires_supporting_document': requires_doc,
                    'advance_notice_days': advance_notice_days,
                    'cancellation_allowed': _bool('cancellation_allowed'),
                }
            )


# ---------------------------------------------------------------------------
# Leave Balance Importer
# ---------------------------------------------------------------------------

class LeaveBalanceImporter(BaseCSVImporter):
    """
    Maps: employee_code, leave_type_name, branch_code, year,
          allocated_days, carried_forward_days, used_days

    UNSUPPORTED: encashed_days — no encashment field on LeaveBalance model.
    ARCHITECTURAL CONSTRAINT: LeaveBalance.clean() requires branch + leave_cycle
      for new records. We resolve leave_cycle from (branch, year) — the first
      active LeaveCycle whose date range falls within the given year.
      If no cycle exists, the row fails with an explicit error.
    Tenant isolation: employee and leave_type must belong to self.organization.
    """
    EXPECTED_HEADERS = ['employee_code', 'leave_type_name', 'branch_code', 'year', 'allocated_days']

    def process_row(self, row_idx: int, row_data: dict):
        from decimal import Decimal
        from apps.employees.models import Employee
        from apps.leaves.models import LeaveType, LeaveBalance, LeaveCycle

        employee_code = row_data.get('employee_code', '').strip()
        leave_type_name = row_data.get('leave_type_name', '').strip()
        branch_code = row_data.get('branch_code', '').strip()
        year_str = row_data.get('year', '').strip()

        if not employee_code:
            raise ValueError("employee_code is required.")
        if not leave_type_name:
            raise ValueError("leave_type_name is required.")
        if not branch_code:
            raise ValueError("branch_code is required.")
        if not year_str:
            raise ValueError("year is required.")

        # Warn about unsupported fields
        encashed = row_data.get('encashed_days', '').strip()
        if encashed:
            logger.warning(
                f"Row {row_idx}: CSV field 'encashed_days' has no mapping in the HRMS "
                f"LeaveBalance model and will not be imported. Value: '{encashed}'."
            )

        # Validate year
        try:
            year = int(year_str)
        except ValueError:
            raise ValueError(f"Invalid year '{year_str}'. Must be an integer.")

        def _decimal(key):
            val = row_data.get(key, '0').strip() or '0'
            try:
                d = Decimal(val)
                if d < 0:
                    raise ValueError(f"'{key}' must be non-negative.")
                return d
            except Exception as e:
                raise ValueError(f"Invalid decimal value for '{key}': '{val}'. {e}")

        allocated = _decimal('allocated_days')
        carried_forward = _decimal('carried_forward_days')
        used = _decimal('used_days')

        # Tenant-isolated lookups
        employee = Employee.objects.filter(
            organization=self.organization,
            employee_code=employee_code
        ).first()
        if not employee:
            raise ValueError(f"Employee '{employee_code}' not found in your organization.")

        leave_type = LeaveType.objects.filter(
            organization=self.organization,
            name=leave_type_name
        ).first()
        if not leave_type:
            raise ValueError(f"LeaveType '{leave_type_name}' not found in your organization.")

        branch = Branch.objects.filter(
            organization=self.organization,
            name=branch_code
        ).first()
        if not branch:
            raise ValueError(f"Branch '{branch_code}' not found in your organization.")

        # Resolve leave_cycle: first active cycle for the branch within the given year
        leave_cycle = LeaveCycle.objects.filter(
            branch=branch,
            is_active=True,
            start_date__year__lte=year,
            end_date__year__gte=year,
        ).first()
        if not leave_cycle:
            raise ValueError(
                f"No active LeaveCycle found for branch '{branch_code}' covering year {year}. "
                f"Create the leave cycle before importing balances."
            )

        LeaveBalance.objects.update_or_create(
            employee=employee,
            leave_type=leave_type,
            leave_cycle=leave_cycle,
            defaults={
                'branch': branch,
                'allocated': allocated,
                'carried_forward': carried_forward,
                'used': used,
                'adjustment': Decimal('0'),
            }
        )


# ---------------------------------------------------------------------------
# Salary Structure Importer
# ---------------------------------------------------------------------------

class SalaryStructureImporter(BaseCSVImporter):
    """
    Maps: structure_name, employee_code, effective_date, basic_salary,
          component:<code> columns (dynamic).

    Dynamic column parsing: any CSV column prefixed with 'component:' is
    treated as a SalaryStructureComponent. The component code must exist
    as a SalaryComponent in the organization — the importer never auto-creates
    components, preventing silent data corruption.

    UNSUPPORTED (no model field): payment_mode, currency, ctc
    """
    EXPECTED_HEADERS = ['structure_name']

    UNSUPPORTED_FIELDS = ['payment_mode', 'currency', 'ctc']

    def process_row(self, row_idx: int, row_data: dict):
        from decimal import Decimal
        import datetime
        from apps.payroll.models import (
            SalaryStructure, SalaryComponent, SalaryStructureComponent,
            CompensationHistory,
        )
        from apps.employees.models import Employee

        structure_name = row_data.get('structure_name', '').strip()
        if not structure_name:
            raise ValueError("structure_name is required.")

        # Warn about unsupported fields
        for field in self.UNSUPPORTED_FIELDS:
            val = row_data.get(field, '').strip()
            if val:
                logger.warning(
                    f"Row {row_idx}: CSV field '{field}' has no mapping in the HRMS payroll "
                    f"model and will not be imported. Value: '{val}'."
                )

        # Create or get the salary structure (org-scoped)
        structure, _ = SalaryStructure.objects.get_or_create(
            organization=self.organization,
            name=structure_name,
            defaults={'is_active': True},
        )

        # Process dynamic component:* columns
        for key, value in row_data.items():
            if not key.startswith('component:'):
                continue
            component_code = key.split(':', 1)[1].strip()
            if not value or not value.strip():
                continue
            try:
                amount = Decimal(value.strip())
            except Exception:
                raise ValueError(f"Invalid amount for component '{component_code}': '{value}'.")
            if amount < 0:
                raise ValueError(f"Component '{component_code}' amount must be non-negative.")

            # Component must exist in org — do not auto-create
            component = SalaryComponent.objects.filter(
                organization=self.organization,
                code=component_code,
                is_active=True,
            ).first()
            if not component:
                raise ValueError(
                    f"SalaryComponent with code '{component_code}' not found in your organization. "
                    f"Create the component before importing."
                )

            SalaryStructureComponent.objects.update_or_create(
                structure=structure,
                component=component,
                defaults={'amount': amount},
            )

        # Optional: link employee + effective date → CompensationHistory
        employee_code = row_data.get('employee_code', '').strip()
        if employee_code:
            employee = Employee.objects.filter(
                organization=self.organization,
                employee_code=employee_code,
            ).first()
            if not employee:
                raise ValueError(f"Employee '{employee_code}' not found in your organization.")

            basic_salary_str = row_data.get('basic_salary', '').strip()
            if not basic_salary_str:
                raise ValueError(
                    f"basic_salary is required when employee_code is provided (row {row_idx})."
                )
            try:
                basic_salary = Decimal(basic_salary_str)
                if basic_salary < 0:
                    raise ValueError("basic_salary must be non-negative.")
            except Exception as e:
                raise ValueError(f"Invalid basic_salary '{basic_salary_str}': {e}")

            effective_date_str = row_data.get('effective_date', '').strip()
            if not effective_date_str:
                raise ValueError(
                    f"effective_date is required when employee_code is provided (row {row_idx})."
                )
            try:
                effective_date = datetime.date.fromisoformat(effective_date_str)
            except ValueError:
                raise ValueError(
                    f"Invalid effective_date '{effective_date_str}'. Expected YYYY-MM-DD."
                )

            # Close existing open record, then create new
            CompensationHistory.objects.filter(
                employee=employee,
                effective_to__isnull=True,
            ).update(effective_to=effective_date)

            CompensationHistory.objects.get_or_create(
                employee=employee,
                effective_from=effective_date,
                defaults={
                    'basic_salary': basic_salary,
                    'created_by': self.user,
                }
            )


# ---------------------------------------------------------------------------
# Attendance Importer
# ---------------------------------------------------------------------------

class AttendanceImporter(BaseCSVImporter):
    """
    Maps: employee_code, date, check_in, check_out, status

    UNSUPPORTED (no model field — explicitly logged, not silently dropped):
      remarks, online_duration, active_duration, idle_duration,
      productive_duration, unproductive_duration, neutral_duration,
      active_percent, mouse_clicks, key_presses

    Duplicate handling: unique_together (employee, date) → update_or_create.
    Status must be one of: present, absent, half_day.
    check_in / check_out: ISO 8601 datetime or blank.
    """
    EXPECTED_HEADERS = ['employee_code', 'date', 'status']

    UNSUPPORTED_FIELDS = [
        'remarks', 'online_duration', 'active_duration', 'idle_duration',
        'productive_duration', 'unproductive_duration', 'neutral_duration',
        'active_percent', 'mouse_clicks', 'key_presses',
    ]

    VALID_STATUSES = ('present', 'absent', 'half_day')

    def process_row(self, row_idx: int, row_data: dict):
        import datetime
        from django.utils import timezone as tz
        from apps.attendance.models import Attendance
        from apps.employees.models import Employee

        employee_code = row_data.get('employee_code', '').strip()
        date_str = row_data.get('date', '').strip()
        status = row_data.get('status', '').strip().lower()

        if not employee_code:
            raise ValueError("employee_code is required.")
        if not date_str:
            raise ValueError("date is required.")
        if not status:
            raise ValueError("status is required.")
        if status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {', '.join(self.VALID_STATUSES)}."
            )

        # Log unsupported fields (non-fatal)
        for field in self.UNSUPPORTED_FIELDS:
            val = row_data.get(field, '').strip()
            if val:
                logger.info(
                    f"Row {row_idx}: CSV field '{field}' is not supported by the HRMS "
                    f"Attendance model and will be ignored. Value: '{val}'."
                )

        # Tenant-isolated employee lookup
        employee = Employee.objects.filter(
            organization=self.organization,
            employee_code=employee_code,
        ).first()
        if not employee:
            raise ValueError(f"Employee '{employee_code}' not found in your organization.")

        try:
            date_value = datetime.date.fromisoformat(date_str)
        except ValueError:
            raise ValueError(f"Invalid date '{date_str}'. Expected YYYY-MM-DD.")

        def _parse_datetime(key):
            val = row_data.get(key, '').strip()
            if not val:
                return None
            try:
                dt = datetime.datetime.fromisoformat(val)
                if tz.is_naive(dt):
                    dt = tz.make_aware(dt)
                return dt
            except Exception:
                raise ValueError(f"Invalid datetime for '{key}': '{val}'. Expected ISO 8601.")

        check_in = _parse_datetime('check_in')
        check_out = _parse_datetime('check_out')

        if check_in and check_out and check_out < check_in:
            raise ValueError("check_out cannot be before check_in.")

        Attendance.objects.update_or_create(
            employee=employee,
            date=date_value,
            defaults={
                'check_in': check_in,
                'check_out': check_out,
                'status': status,
            }
        )
