# pyrefly: ignore [missing-import]
import os
import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.organization.models import Organization, Department, Designation


def employee_document_upload_path(instance, filename):
    """
    Store documents at:
      media/private/employee_documents/<employee_id>/<uuid>.<ext>
    Using a UUID-based filename prevents both directory traversal and name collisions.
    The original filename is stored in the `document_name` field.
    """
    ext = os.path.splitext(filename)[-1].lower()
    new_filename = f"{uuid.uuid4()}{ext}"
    return os.path.join('employee_documents', str(instance.employee_id), new_filename)


class DocumentType(models.TextChoices):
    IDENTITY = 'identity', 'Identity'
    ADDRESS = 'address', 'Address Proof'
    EDUCATION = 'education', 'Education'
    EMPLOYMENT = 'employment', 'Employment'
    CONTRACT = 'contract', 'Contract'
    OTHER = 'other', 'Other'


class DocumentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    VERIFIED = 'verified', 'Verified'
    REJECTED = 'rejected', 'Rejected'

class EmploymentStatus(models.TextChoices):
    ONBOARDING = 'onboarding', 'Onboarding'
    ACTIVE = 'active', 'Active'
    ON_NOTICE = 'on_notice', 'On Notice'
    ON_LEAVE = 'on_leave', 'On Leave'
    INACTIVE = 'inactive', 'Inactive'
    EXITED = 'exited', 'Exited'

class Employee(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='employee')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='employees', null=True, blank=True)
    branch = models.ForeignKey('organization.Branch', on_delete=models.SET_NULL, related_name='employees', null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, related_name='employees', null=True, blank=True)
    team = models.ForeignKey('organization.Team', on_delete=models.SET_NULL, related_name='employees', null=True, blank=True)
    designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, related_name='employees', null=True, blank=True)
    reporting_manager = models.ForeignKey('self', on_delete=models.SET_NULL, related_name='direct_reports', null=True, blank=True)
    employee_code = models.CharField(max_length=50, help_text="Assigned HRMS/Employee ID")
    personal_email = models.EmailField(unique=True, null=True, blank=True, help_text="Employee's personal email for onboarding")
    phone_number = models.CharField(max_length=20, blank=True)
    alternate_phone = models.CharField(max_length=20, blank=True)
    
    gender = models.CharField(max_length=20, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    marital_status = models.CharField(max_length=20, choices=[('single', 'Single'), ('married', 'Married'), ('divorced', 'Divorced'), ('widowed', 'Widowed')], blank=True)
    blood_group = models.CharField(max_length=10, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    
    address = models.TextField(blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    emergency_contact_relation = models.CharField(max_length=100, blank=True)

    employment_type = models.CharField(max_length=20, choices=[('full_time', 'Full Time'), ('part_time', 'Part Time'), ('contract', 'Contract')], default='full_time')
    employment_status = models.CharField(max_length=20, choices=EmploymentStatus.choices, default=EmploymentStatus.ONBOARDING)
    joining_date = models.DateField(null=True, blank=True)
    confirmation_date = models.DateField(null=True, blank=True)
    exit_date = models.DateField(null=True, blank=True)
    resignation_date = models.DateField(null=True, blank=True)
    exit_reason = models.TextField(blank=True)
    notice_period_days = models.IntegerField(null=True, blank=True)
    notice_period_start = models.DateField(null=True, blank=True)
    notice_period_end = models.DateField(null=True, blank=True)

    custom_fields_data = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'employee_code')

    def __str__(self):
        return f"{self.employee_code} - {self.user.email}"

    def clean(self):
        super().clean()
        if self.organization_id:
            if self.branch_id and self.branch.organization_id != self.organization_id:
                raise ValidationError({'branch': 'Branch must belong to the same organization.'})
            if self.department_id and self.department.branch.organization_id != self.organization_id:
                raise ValidationError({'department': 'Department must belong to the same organization.'})
            if self.branch_id and self.department_id and self.department.branch_id != self.branch_id:
                raise ValidationError({'department': 'Department must belong to the same branch as the employee.'})
            if self.team_id and self.team.department_id != self.department_id:
                raise ValidationError({'team': 'Team must belong to the same department as the employee.'})
            if self.team_id and not self.team.is_active and self.employment_status not in [EmploymentStatus.INACTIVE, EmploymentStatus.EXITED]:
                raise ValidationError({'team': 'Cannot assign an inactive team to an active employee.'})
            if self.designation_id and self.designation.organization_id != self.organization_id:
                raise ValidationError({'designation': 'Designation must belong to the same organization.'})
        else:
            if self.branch_id or self.department_id or self.designation_id:
                raise ValidationError('Cannot assign branch, department, or designation without an organization.')

        if self.reporting_manager_id:
            if self.reporting_manager_id == self.id:
                raise ValidationError({'reporting_manager': 'Employee cannot report to themselves.'})
            if self.reporting_manager.organization_id != self.organization_id:
                raise ValidationError({'reporting_manager': 'Reporting manager must belong to the same organization.'})

        if self.joining_date and self.exit_date and self.exit_date < self.joining_date:
            raise ValidationError({'exit_date': 'Exit date cannot be before joining date.'})

        if self.notice_period_start and self.notice_period_end and self.notice_period_end < self.notice_period_start:
            raise ValidationError({'notice_period_end': 'Notice period end date cannot be before start date.'})

        if self.resignation_date and self.exit_date and self.exit_date < self.resignation_date:
            raise ValidationError({'exit_date': 'Exit date cannot be before resignation date.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class WFHRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='wfh_requests')
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_comment = models.TextField(blank=True)

    def clean(self):
        super().clean()
        if self.start_at and self.end_at and self.start_at >= self.end_at:
            raise ValidationError({'end_at': 'End date must be after start date.'})

    def __str__(self):
        return f"WFH: {self.employee.employee_code} ({self.start_at} - {self.end_at})"

class EmployeeIDSequence(models.Model):
    last_generated = models.IntegerField(default=0)

class EmployeeLifecycleEvent(models.Model):
    EVENT_TYPES = [
        ('status_change', 'Status Change'),
        ('transfer', 'Transfer'),
        ('promotion', 'Promotion'),
        ('resignation', 'Resignation'),
        ('exit', 'Exit'),
        ('reactivation', 'Reactivation'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='lifecycle_events')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    from_status = models.CharField(max_length=50, blank=True)
    to_status = models.CharField(max_length=50, blank=True)
    from_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    to_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    from_branch = models.ForeignKey('organization.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    to_branch = models.ForeignKey('organization.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    from_designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    to_designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    effective_date = models.DateField()
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.employee_code} - {self.get_event_type_display()} on {self.effective_date}"


class EmployeeDocument(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(
        max_length=50, choices=DocumentType.choices, default=DocumentType.OTHER
    )
    document_name = models.CharField(max_length=255, help_text="Human-readable document label")
    file = models.FileField(upload_to=employee_document_upload_path)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    mime_type = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=DocumentStatus.choices, default=DocumentStatus.PENDING
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+'
    )

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.employee.employee_code} — {self.document_name} ({self.document_type})"

class ReviewCycle(models.Model):
    organization=models.ForeignKey(Organization,on_delete=models.CASCADE,related_name='review_cycles')
    name=models.CharField(max_length=150); start_date=models.DateField(); end_date=models.DateField(); is_active=models.BooleanField(default=True)
    class Meta: unique_together=('organization','name')
    def clean(self):
        if self.start_date and self.end_date and self.end_date<self.start_date: raise ValidationError({'end_date':'End date cannot precede start date.'})

class PerformanceReview(models.Model):
    STATUS=[('draft','Draft'),('submitted','Submitted'),('acknowledged','Acknowledged')]
    cycle=models.ForeignKey(ReviewCycle,on_delete=models.PROTECT,related_name='reviews')
    employee=models.ForeignKey(Employee,on_delete=models.CASCADE,related_name='performance_reviews')
    reviewer=models.ForeignKey(Employee,on_delete=models.SET_NULL,null=True,related_name='reviews_authored')
    rating=models.PositiveSmallIntegerField(null=True,blank=True); summary=models.TextField(blank=True); status=models.CharField(max_length=16,choices=STATUS,default='draft'); submitted_at=models.DateTimeField(null=True,blank=True)
    class Meta: unique_together=('cycle','employee')
    def clean(self):
        if self.rating is not None and not 1<=self.rating<=5:raise ValidationError({'rating':'Rating must be between 1 and 5.'})
        if self.reviewer_id and self.reviewer.organization_id!=self.employee.organization_id:raise ValidationError({'reviewer':'Reviewer must be in the same organization.'})

class EmployeeStatutoryAndBank(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='statutory_and_bank')
    
    # Statutory
    pan_number = models.CharField(max_length=20, blank=True)
    aadhaar_number = models.CharField(max_length=20, blank=True) # Masked in API
    passport_number = models.CharField(max_length=50, blank=True)
    passport_expiry = models.DateField(null=True, blank=True)
    driving_license_number = models.CharField(max_length=50, blank=True)
    
    uan_number = models.CharField(max_length=50, blank=True)
    pf_account_number = models.CharField(max_length=50, blank=True)
    eps_number = models.CharField(max_length=50, blank=True)
    esic_number = models.CharField(max_length=50, blank=True)
    
    is_pt_applicable = models.BooleanField(default=False)
    is_lwf_applicable = models.BooleanField(default=False)
    
    # Bank
    bank_name = models.CharField(max_length=150, blank=True)
    account_name = models.CharField(max_length=150, blank=True)
    bank_branch = models.CharField(max_length=150, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    
    PAYMENT_MODES = [('BANK_TRANSFER', 'Bank Transfer'), ('CHEQUE', 'Cheque'), ('CASH', 'Cash')]
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default='BANK_TRANSFER')
    
    TAX_REGIMES = [('OLD', 'Old Regime'), ('NEW', 'New Regime')]
    tax_regime = models.CharField(max_length=10, choices=TAX_REGIMES, default='NEW')

class EmployeeDependent(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='dependents')
    full_name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=100)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    
    is_emergency_contact = models.BooleanField(default=False)
    is_insurance_dependent = models.BooleanField(default=False)
    
    pf_nominee_share = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gratuity_nominee_share = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    esic_nominee_share = models.DecimalField(max_digits=5, decimal_places=2, default=0)

class EmployeeEducation(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='education_records')
    degree = models.CharField(max_length=150)
    specialization = models.CharField(max_length=150, blank=True)
    institution = models.CharField(max_length=150)
    completion_year = models.IntegerField(null=True, blank=True)
    grade_or_cgpa = models.CharField(max_length=50, blank=True)

def employee_prior_experience_upload_path(instance, filename):
    ext = os.path.splitext(filename)[-1].lower()
    new_filename = f"{uuid.uuid4()}{ext}"
    return os.path.join('employee_prior_experience', str(instance.employee_id), new_filename)

class EmployeePriorExperience(models.Model):
    BGV_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('VERIFIED', 'Verified'),
        ('DISCREPANCY', 'Discrepancy'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='prior_experiences')
    employer_name = models.CharField(max_length=150)
    designation = models.CharField(max_length=150)
    start_date = models.DateField()
    end_date = models.DateField()
    last_drawn_ctc = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reason_for_leaving = models.TextField(blank=True)
    
    bgv_status = models.CharField(max_length=20, choices=BGV_STATUS_CHOICES, default='PENDING')
    
    relieving_letter = models.FileField(upload_to=employee_prior_experience_upload_path, null=True, blank=True)
    experience_letter = models.FileField(upload_to=employee_prior_experience_upload_path, null=True, blank=True)

class ApprovalDelegation(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    delegator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='delegations_given')
    delegate = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='delegations_received')
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    delegate_types = models.JSONField(default=list, help_text="e.g. ['leave', 'wfh', 'attendance', 'timesheet']")
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

def letter_request_upload_path(instance, filename):
    ext = os.path.splitext(filename)[-1].lower()
    return f"letter_requests/{instance.employee_id}/{uuid.uuid4()}{ext}"

class LetterRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('ISSUED', 'Issued'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='letter_requests')
    letter_type = models.CharField(max_length=50) # e.g. BONAFIDE, ADDRESS_PROOF
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    issued_document = models.FileField(upload_to=letter_request_upload_path, null=True, blank=True)
    
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_letter_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

