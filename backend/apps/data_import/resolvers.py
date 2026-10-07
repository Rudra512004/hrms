from apps.data_import.exceptions import RowValidationError
from apps.organization.models import Branch, Department, Designation
from apps.employees.models import Employee
from apps.leaves.models import LeaveType
from apps.attendance.models import Shift
from apps.authorization.models import Role

class CrossTenantReferenceError(Exception):
    pass

class DependencyNotFoundError(Exception):
    pass

def resolve_branch(code, organization, row_num):
    if not code:
        return None
    try:
        branch = Branch.objects.get(code=code, organization=organization)
        return branch
    except Branch.DoesNotExist:
        raise RowValidationError('branch_code', 'not_found', f"Branch with code '{code}' does not exist in your organization.")

def resolve_department(code, organization, row_num):
    if not code:
        return None
    try:
        # Note: Department code is unique per branch, so looking up just by code + org is tricky.
        # But wait, the schema states department code is unique per branch.
        # If we only have dept code, we need branch_code.
        # Actually, in the Employee template, we import branch_code AND department_code.
        pass
    except Exception as e:
        pass
    return None

def resolve_department_with_branch(dept_code, branch, row_num):
    if not dept_code or not branch:
        return None
    try:
        dept = Department.objects.get(code=dept_code, branch=branch)
        return dept
    except Department.DoesNotExist:
        raise RowValidationError('department_code', 'not_found', f"Department with code '{dept_code}' does not exist in branch '{branch.code}'.")

def resolve_designation(code, organization, row_num):
    if not code:
        return None
    try:
        desig = Designation.objects.get(code=code, organization=organization)
        return desig
    except Designation.DoesNotExist:
        raise RowValidationError('designation_code', 'not_found', f"Designation with code '{code}' does not exist in your organization.")

def resolve_shift(code, branch, row_num):
    if not code:
        return None
    if not branch:
        raise RowValidationError('shift_code', 'missing_dependency', "Cannot resolve shift without a valid branch.")
    try:
        shift = Shift.objects.get(code=code, branch=branch)
        return shift
    except Shift.DoesNotExist:
        raise RowValidationError('shift_code', 'not_found', f"Shift with code '{code}' does not exist in branch '{branch.code}'.")

def resolve_employee(code, organization, row_num, field_name='employee_code'):
    if not code:
        return None
    try:
        emp = Employee.objects.get(employee_code=code, organization=organization)
        return emp
    except Employee.DoesNotExist:
        raise RowValidationError(field_name, 'not_found', f"Employee with code '{code}' does not exist in your organization.")

def resolve_leave_type(code, organization, row_num):
    if not code:
        return None
    try:
        leave_type = LeaveType.objects.get(code=code, organization=organization)
        return leave_type
    except LeaveType.DoesNotExist:
        raise RowValidationError('leave_type_code', 'not_found', f"Leave type with code '{code}' does not exist in your organization.")

def resolve_role(name, organization, row_num):
    if not name:
        return None
    try:
        role = Role.objects.get(name=name, organization=organization)
        return role
    except Role.DoesNotExist:
        raise RowValidationError('role', 'not_found', f"Role with name '{name}' does not exist in your organization.")

def resolve_branch_list(codes, organization, row_num):
    if not codes:
        return []
    branches = list(Branch.objects.filter(code__in=codes, organization=organization))
    found_codes = {b.code for b in branches}
    missing_codes = set(codes) - found_codes
    if missing_codes:
        raise RowValidationError('branches', 'not_found', f"Branches not found in your organization: {', '.join(missing_codes)}")
    return branches

def resolve_company(code, organization, row_num):
    if not code:
        return organization
    if code != organization.code:
        raise RowValidationError('company_code', 'cross_tenant', "You cannot import data for a different organization.")
    return organization
