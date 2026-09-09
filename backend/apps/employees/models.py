# pyrefly: ignore [missing-import]
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.organization.models import Organization, Department, Designation

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
    designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, related_name='employees', null=True, blank=True)
    reporting_manager = models.ForeignKey('self', on_delete=models.SET_NULL, related_name='direct_reports', null=True, blank=True)
    employee_code = models.CharField(max_length=50, unique=True, help_text="Assigned HRMS/Employee ID")
    personal_email = models.EmailField(unique=True, null=True, blank=True, help_text="Employee's personal email for onboarding")
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)

    employment_status = models.CharField(max_length=20, choices=EmploymentStatus.choices, default=EmploymentStatus.ONBOARDING)
    joining_date = models.DateField(null=True, blank=True)
    exit_date = models.DateField(null=True, blank=True)
    resignation_date = models.DateField(null=True, blank=True)
    exit_reason = models.TextField(blank=True)
    notice_period_start = models.DateField(null=True, blank=True)
    notice_period_end = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee_code} - {self.user.email}"

    def clean(self):
        super().clean()
        if self.organization_id:
            if self.branch_id and self.branch.organization_id != self.organization_id:
                raise ValidationError({'branch': 'Branch must belong to the same organization.'})
            if self.department_id and self.department.organization_id != self.organization_id:
                raise ValidationError({'department': 'Department must belong to the same organization.'})
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
