import re
from django.db import transaction
from django.db.models import Q
from .models import Employee, EmployeeIDSequence


def generate_next_employee_code(organization, prefix='EMPBS'):
    """
    Generates the next employee code for a specific organization in the format:
    EMPBS001, EMPBS002, etc. (or specified prefix).

    Enforces tenant isolation by tracking sequence allocation per Organization.
    Acquires an exclusive row-level lock via select_for_update() inside an atomic
    transaction to prevent concurrent allocation race conditions and duplicate codes.
    """
    if organization is None:
        raise ValueError("Organization context is required to generate an employee code.")

    if isinstance(organization, (int, str)):
        from apps.organization.models import Organization
        organization = Organization.objects.get(pk=organization)

    with transaction.atomic():
        seq = EmployeeIDSequence.objects.select_for_update().filter(organization=organization).first()
        if not seq:
            # Resilient adoption of unassigned legacy sequence row if present
            legacy_seq = EmployeeIDSequence.objects.select_for_update().filter(organization__isnull=True).first()
            if legacy_seq:
                legacy_seq.organization = organization
                legacy_seq.save(update_fields=['organization'])
                seq = legacy_seq
            else:
                try:
                    with transaction.atomic():
                        seq = EmployeeIDSequence.objects.create(organization=organization, last_generated=0)
                except Exception:
                    # Concurrently created by a competing worker: acquire the lock on the newly created row
                    seq = EmployeeIDSequence.objects.select_for_update().get(organization=organization)

        max_num = seq.last_generated

        pattern = re.compile(rf'^{re.escape(prefix)}(\d+)$')

        # Load existing codes for this organization OR unassigned legacy employees matching the prefix
        existing_codes = Employee.objects.filter(
            Q(organization=organization) | Q(organization__isnull=True),
            employee_code__startswith=prefix
        ).values_list('employee_code', flat=True)

        for code in existing_codes:
            match = pattern.match(code)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num

        next_num = max_num + 1
        seq.last_generated = next_num
        seq.save(update_fields=['last_generated'])

        return f"{prefix}{next_num:03d}"

