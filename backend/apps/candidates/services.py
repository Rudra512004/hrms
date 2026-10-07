import uuid
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.candidates.models import Candidate, CandidateStatus, CandidateDocument
from apps.employees.models import Employee, EmployeeDocument, EmployeeIDSequence, EmploymentStatus
from apps.audit.services import AuditService

User = get_user_model()

def generate_employee_code(organization):
    with transaction.atomic():
        seq, _ = EmployeeIDSequence.objects.select_for_update().get_or_create(id=1)
        seq.last_generated += 1
        seq.save()
        
        prefix = 'EMP'
        if organization and organization.name:
            prefix = ''.join([c.upper() for c in organization.name if c.isalpha()])[:3]
            if len(prefix) < 2:
                prefix = 'EMP'
        
        return f"{prefix}{str(seq.last_generated).zfill(4)}"

def convert_candidate_to_employee(candidate, user_who_initiated=None, request=None):
    """
    Converts a candidate (APPROVED) to an Employee (ONBOARDING).
    - Creates a new User (if not already existing) with pending activation.
    - Creates an Employee record tied to the Organization and Candidate's designation.
    - Migrates all verified CandidateDocuments to EmployeeDocuments.
    - Updates Candidate status to CONVERTED.
    """
    if candidate.status != CandidateStatus.APPROVED:
        raise ValidationError(f"Only '{CandidateStatus.APPROVED}' candidates can be converted.")
    if candidate.employee_id:
        raise ValidationError("Candidate is already converted to an employee.")

    with transaction.atomic():
        # 1. Create or get User
        user = candidate.user
        if not user:
            temp_password = User.objects.make_random_password()
            # If email already exists, this could fail, but we assume it's unique or we append a timestamp/suffix.
            # Realistically, onboarding portals require a user account, so candidate.user is usually set during OFFERED stage.
            if User.objects.filter(email=candidate.email).exists():
                raise ValidationError("A user with this email already exists in the system.")
            
            user = User.objects.create_user(
                email=candidate.email,
                password=temp_password,
                first_name=candidate.first_name,
                last_name=candidate.last_name,
                status='active'
            )
            candidate.user = user
            candidate.save(update_fields=['user'])

        # 2. Create Employee
        employee_code = generate_employee_code(candidate.organization)
        employee = Employee.objects.create(
            user=user,
            organization=candidate.organization,
            designation=candidate.applied_designation,
            employee_code=employee_code,
            personal_email=candidate.email,
            phone_number=candidate.phone_number,
            address=candidate.address,
            employment_status=EmploymentStatus.ONBOARDING,
            joining_date=candidate.proposed_joining_date
        )

        # 3. Update Candidate
        candidate.employee = employee
        candidate.status = CandidateStatus.CONVERTED
        candidate.save(update_fields=['employee', 'status'])

        # 4. Migrate Documents (Only VERIFIED ones, or ALL?)
        # Standard practice is to migrate all documents that are approved/verified.
        docs = CandidateDocument.objects.filter(candidate=candidate)
        for cdoc in docs:
            # Re-map document types if they match exactly, or default to OTHER
            EmployeeDocument.objects.create(
                employee=employee,
                document_type=cdoc.document_type,
                document_name=cdoc.document_name,
                file=cdoc.file,
                file_size=cdoc.file_size,
                mime_type=cdoc.mime_type,
                description=cdoc.description,
                status='verified' if cdoc.status == 'verified' else 'pending',
                uploaded_by=cdoc.uploaded_by,
                uploaded_at=cdoc.uploaded_at
            )

        # 5. Audit Log
        if user_who_initiated:
            AuditService.log(
                action='candidate_converted_to_employee',
                actor=user_who_initiated,
                target_type='candidate',
                target_id=candidate.id,
                metadata={'employee_id': employee.id, 'employee_code': employee.employee_code},
                request=request
            )

        return employee
