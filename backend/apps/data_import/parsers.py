import re
import datetime
from decimal import Decimal, InvalidOperation
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from apps.data_import.exceptions import RowValidationError
from apps.data_import.registry import (
    TYPE_STRING, TYPE_EMAIL, TYPE_DATE, TYPE_DATETIME, TYPE_TIME,
    TYPE_INTEGER, TYPE_DECIMAL, TYPE_BOOLEAN, TYPE_DURATION,
    TYPE_ENUM, TYPE_CSV_LIST, TYPE_COMPONENT
)

def parse_date(value_str):
    formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d']
    for fmt in formats:
        try:
            return datetime.datetime.strptime(value_str, fmt).date()
        except ValueError:
            continue
    raise ValueError("Invalid date format. Use YYYY-MM-DD or DD/MM/YYYY.")

def parse_datetime(value_str):
    # Try ISO first
    try:
        from django.utils.dateparse import parse_datetime as django_parse_datetime
        dt = django_parse_datetime(value_str)
        if dt is not None:
            return dt
    except Exception:
        pass

    formats = [
        '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M',
        '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M',
        '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M'
    ]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(value_str, fmt)
        except ValueError:
            continue
    raise ValueError("Invalid datetime format.")

def parse_time(value_str):
    formats = ['%H:%M:%S', '%H:%M']
    for fmt in formats:
        try:
            return datetime.datetime.strptime(value_str, fmt).time()
        except ValueError:
            continue
    raise ValueError("Invalid time format. Use HH:MM or HH:MM:SS.")

def parse_duration(value_str):
    # Expects HH:MM:SS
    parts = value_str.split(':')
    try:
        if len(parts) == 3:
            h, m, s = map(int, parts)
            return datetime.timedelta(hours=h, minutes=m, seconds=s)
        elif len(parts) == 2:
            h, m = map(int, parts)
            return datetime.timedelta(hours=h, minutes=m)
    except ValueError:
        pass
    raise ValueError("Invalid duration. Use HH:MM:SS or HH:MM.")

def parse_boolean(value_str):
    lower = value_str.lower()
    if lower in ('true', '1', 'yes', 'y'):
        return True
    if lower in ('false', '0', 'no', 'n'):
        return False
    raise ValueError("Invalid boolean. Use true/false or yes/no.")

def parse_field_value(field_def, value_str):
    """
    Parse a raw string value according to the field definition type.
    Raises RowValidationError on failure.
    """
    if value_str is None:
        value_str = ''
    value_str = str(value_str).strip()

    if not value_str:
        if field_def.get('required'):
            raise RowValidationError(field_def['csv_header'], 'required', 'This field is required.')
        return None

    field_type = field_def['type']
    header = field_def['csv_header']

    try:
        if field_type == TYPE_STRING:
            max_len = field_def.get('max_length')
            if max_len and len(value_str) > max_len:
                raise RowValidationError(header, 'max_length', f'Maximum length is {max_len} characters.')
            return value_str
            
        elif field_type == TYPE_EMAIL:
            lower_email = value_str.lower()
            validate_email(lower_email)
            return lower_email

        elif field_type == TYPE_DATE:
            return parse_date(value_str)

        elif field_type == TYPE_DATETIME:
            return parse_datetime(value_str)

        elif field_type == TYPE_TIME:
            return parse_time(value_str)

        elif field_type == TYPE_INTEGER:
            val = int(value_str)
            min_val = field_def.get('min_value')
            if min_val is not None and val < min_val:
                raise RowValidationError(header, 'min_value', f'Value must be >= {min_val}.')
            return val

        elif field_type == TYPE_DECIMAL or field_type == TYPE_COMPONENT:
            val = Decimal(value_str)
            min_val = field_def.get('min_value')
            if min_val is not None and val < Decimal(str(min_val)):
                raise RowValidationError(header, 'min_value', f'Value must be >= {min_val}.')
            return val

        elif field_type == TYPE_BOOLEAN:
            return parse_boolean(value_str)

        elif field_type == TYPE_DURATION:
            return parse_duration(value_str)

        elif field_type == TYPE_ENUM:
            allowed = field_def.get('enum_values', set())
            allowed_lower = {v.lower() for v in allowed}
            lower_val = value_str.lower()
            if lower_val not in allowed_lower:
                raise RowValidationError(header, 'invalid_enum', f'Value must be one of: {", ".join(allowed)}.')
            
            # Return the correct case from the original allowed set
            for v in allowed:
                if v.lower() == lower_val:
                    return v
            return value_str

        elif field_type == TYPE_CSV_LIST:
            return [v.strip() for v in value_str.split(',') if v.strip()]

        else:
            return value_str

    except ValidationError as e:
        raise RowValidationError(header, 'validation_error', e.message if hasattr(e, 'message') else str(e))
    except ValueError as e:
        raise RowValidationError(header, 'invalid_type', str(e))
    except InvalidOperation:
        raise RowValidationError(header, 'invalid_type', 'Invalid decimal format.')
    except RowValidationError:
        raise
    except Exception as e:
        raise RowValidationError(header, 'unknown_error', str(e))
