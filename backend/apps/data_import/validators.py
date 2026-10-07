import csv
import io
from apps.data_import.exceptions import ImportValidationError, RowValidationError
from apps.data_import.registry import get_template, TYPE_COMPONENT, RESOLVE_BRANCH, RESOLVE_DEPARTMENT, RESOLVE_DESIGNATION, RESOLVE_SHIFT, RESOLVE_EMPLOYEE, RESOLVE_LEAVE_TYPE, RESOLVE_COMPANY, RESOLVE_MANAGER, RESOLVE_ROLE, RESOLVE_BRANCH_LIST
from apps.data_import.parsers import parse_field_value
from apps.data_import import resolvers

def validate_csv_structure(file_obj, template_key):
    """
    Validates that the uploaded file matches the template headers exactly.
    Returns (headers, list of rows)
    """
    template = get_template(template_key)
    if not template:
        raise ImportValidationError(f"Unknown template: {template_key}")

    expected_headers = template['headers']
    
    # Check file size (e.g. 5MB max)
    file_obj.seek(0, io.SEEK_END)
    size = file_obj.tell()
    if size > 5 * 1024 * 1024:
        raise ImportValidationError("File too large. Maximum size is 5MB.")
    file_obj.seek(0)
    
    try:
        raw_content = file_obj.read()
        if isinstance(raw_content, bytes):
            content = raw_content.decode('utf-8-sig')
        else:
            content = raw_content
    except UnicodeDecodeError:
        raise ImportValidationError("File must be UTF-8 encoded.")

    reader = csv.reader(io.StringIO(content))
    try:
        headers = next(reader)
    except StopIteration:
        raise ImportValidationError("The uploaded file is empty.")

    # Strip BOM and whitespace from headers
    headers = [h.strip() for h in headers]

    # Validate headers. Note: dynamic component headers are prefix-matched
    for i, expected in enumerate(expected_headers):
        if expected.startswith('component:'):
            # As long as there are components in the CSV, we accept them. 
            # We don't strictly require exact positional match for dynamic columns 
            # but we will extract whatever headers start with 'component:'
            pass
        else:
            if i >= len(headers) or headers[i] != expected:
                raise ImportValidationError(
                    f"Header mismatch at column {i+1}. "
                    f"Expected '{expected}', found '{headers[i] if i < len(headers) else 'EOF'}'."
                )

    rows = list(reader)
    if len(rows) > 5000:
        raise ImportValidationError("Too many rows. Maximum is 5000 rows per import.")

    return headers, rows

def parse_and_resolve_row(row_num, row_data, headers, template_key, organization):
    """
    Takes a list of raw string values and maps them into a dictionary of python objects.
    """
    template = get_template(template_key)
    fields = template['fields']
    
    parsed = {}
    
    # First pass: Parse native types (no relationships)
    for i, field_def in enumerate(fields):
        header = field_def['csv_header']
        
        # Handle dynamic component columns
        if header.startswith('component:'):
            if 'components' not in parsed:
                parsed['components'] = {}
            # Find all headers in the actual CSV that start with component:
            for j, actual_header in enumerate(headers):
                if actual_header.startswith('component:'):
                    comp_code = actual_header.split(':', 1)[1]
                    val = row_data[j] if j < len(row_data) else None
                    if val and str(val).strip():
                        parsed['components'][comp_code] = parse_field_value(field_def, val)
            continue
            
        value_str = row_data[i] if i < len(row_data) else None
        parsed[header] = parse_field_value(field_def, value_str)

    # Second pass: Resolve relationships (tenant-safe)
    for field_def in fields:
        header = field_def['csv_header']
        if header.startswith('component:'):
            continue
            
        resolver_name = field_def.get('resolver')
        if not resolver_name or parsed[header] is None:
            continue
            
        val = parsed[header]
        
        try:
            if resolver_name == RESOLVE_COMPANY:
                parsed[header] = resolvers.resolve_company(val, organization, row_num)
            elif resolver_name == RESOLVE_BRANCH:
                parsed[header] = resolvers.resolve_branch(val, organization, row_num)
            elif resolver_name == RESOLVE_DEPARTMENT:
                # Department needs the resolved branch from this same row
                branch_obj = parsed.get('branch_code')
                if not branch_obj:
                    raise RowValidationError(header, 'missing_dependency', "Cannot resolve department without a valid branch in this row.")
                parsed[header] = resolvers.resolve_department_with_branch(val, branch_obj, row_num)
            elif resolver_name == RESOLVE_DESIGNATION:
                parsed[header] = resolvers.resolve_designation(val, organization, row_num)
            elif resolver_name == RESOLVE_SHIFT:
                branch_obj = parsed.get('branch_code')
                if not branch_obj:
                    # In employees template, branch_code is present. If it's another template, we need to handle it.
                    raise RowValidationError(header, 'missing_dependency', "Cannot resolve shift without a valid branch in this row.")
                parsed[header] = resolvers.resolve_shift(val, branch_obj, row_num)
            elif resolver_name == RESOLVE_EMPLOYEE:
                parsed[header] = resolvers.resolve_employee(val, organization, row_num, header)
            elif resolver_name == RESOLVE_MANAGER:
                parsed[header] = resolvers.resolve_employee(val, organization, row_num, header)
            elif resolver_name == RESOLVE_LEAVE_TYPE:
                parsed[header] = resolvers.resolve_leave_type(val, organization, row_num)
            elif resolver_name == RESOLVE_ROLE:
                parsed[header] = resolvers.resolve_role(val, organization, row_num)
            elif resolver_name == RESOLVE_BRANCH_LIST:
                parsed[header] = resolvers.resolve_branch_list(val, organization, row_num)
        except resolvers.RowValidationError:
            raise
        except Exception as e:
            raise RowValidationError(header, 'resolution_error', str(e))
            
    return parsed
