import re
from .models import Employee, EmployeeIDSequence
from django.db import transaction

def generate_next_employee_code():
    """
    Generates the next employee code in the format EMPBS001, EMPBS002, etc.
    Finds the highest existing number with the EMPBS prefix and increments it.
    """
    with transaction.atomic():
        seq, _ = EmployeeIDSequence.objects.select_for_update().get_or_create(id=1)
        max_num = seq.last_generated

        pattern = re.compile(r'^EMPBS(\d+)$')
        
        # We load all matching codes. Since this is an indexed string field, 
        # and we filter by prefix, it's efficient enough.
        existing_codes = Employee.objects.filter(
            employee_code__startswith='EMPBS'
        ).values_list('employee_code', flat=True)
        
        for code in existing_codes:
            match = pattern.match(code)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
                    
        next_num = max_num + 1
        seq.last_generated = next_num
        seq.save()
        
        return f"EMPBS{next_num:03d}"
