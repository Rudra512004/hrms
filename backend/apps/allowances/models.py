from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.organization.models import Organization, Branch, Department
from apps.employees.models import Employee, Designation, EmploymentStatus
from django.conf import settings

class AllowanceType(models.Model):
    CATEGORY_CHOICES = [
        ('housing', 'Housing'),
        ('travel', 'Travel'),
        ('transport', 'Transport'),
        ('fuel', 'Fuel'),
        ('food', 'Food'),
        ('communication', 'Communication'),
        ('medical', 'Medical'),
        ('education', 'Education'),
        ('wellness', 'Wellness'),
        ('remote_work', 'Remote Work'),
        ('other', 'Other'),
    ]

    CALCULATION_CHOICES = [
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage of Basic'),
        ('per_day', 'Per Day'),
        ('per_trip', 'Per Trip'),
        ('per_claim', 'Per Claim'),
    ]

    FREQUENCY_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('daily', 'Daily'),
        ('per_trip', 'Per Trip'),
        ('on_demand', 'On Demand'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='allowance_types')
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    calculation_type = models.CharField(max_length=20, choices=CALCULATION_CHOICES, default='fixed')
    
    default_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    default_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='monthly')
    
    maximum_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    minimum_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    taxable = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=True)
    
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField(default=timezone.localdate)
    effective_until = models.DateField(null=True, blank=True)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'code')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

class AllowanceEligibility(models.Model):
    # Rule to determine who gets an allowance by default
    allowance_type = models.OneToOneField(AllowanceType, on_delete=models.CASCADE, related_name='eligibility_rule')
    
    branches = models.ManyToManyField(Branch, blank=True)
    departments = models.ManyToManyField(Department, blank=True)
    designations = models.ManyToManyField(Designation, blank=True)
    employment_statuses = models.JSONField(default=list, blank=True, help_text="List of EmploymentStatus strings e.g. ['active', 'probation']")

    def __str__(self):
        return f"Eligibility for {self.allowance_type.name}"

class EmployeeAllowance(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='allowances')
    allowance_type = models.ForeignKey(AllowanceType, on_delete=models.PROTECT, related_name='employee_assignments')
    
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    frequency = models.CharField(max_length=20, choices=AllowanceType.FREQUENCY_CHOICES)
    
    effective_from = models.DateField()
    effective_until = models.DateField(null=True, blank=True)
    
    maximum_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-effective_from']

    def clean(self):
        super().clean()
        if self.employee.organization_id != self.allowance_type.organization_id:
            raise ValidationError("Employee and AllowanceType must belong to the same organization.")
        if self.organization_id != self.allowance_type.organization_id:
            raise ValidationError("Organization mismatch.")
        if self.effective_until and self.effective_from > self.effective_until:
            raise ValidationError({"effective_until": "Effective until date cannot precede effective from date."})
        
        # Check for overlapping active assignments of the same type
        if self.is_active and self.effective_from:
            overlapping = EmployeeAllowance.objects.filter(
                employee=self.employee,
                allowance_type=self.allowance_type,
                is_active=True
            ).exclude(pk=self.pk)
            
            for assignment in overlapping:
                overlap = False
                if assignment.effective_until is None and self.effective_until is None:
                    overlap = True
                elif assignment.effective_until is None:
                    if self.effective_until >= assignment.effective_from:
                        overlap = True
                elif self.effective_until is None:
                    if self.effective_from <= assignment.effective_until:
                        overlap = True
                else:
                    if self.effective_from <= assignment.effective_until and self.effective_until >= assignment.effective_from:
                        overlap = True
                
                if overlap:
                    raise ValidationError("Overlapping active assignments for the same allowance type are not allowed.")

    def __str__(self):
        return f"{self.employee} - {self.allowance_type.name}"

class ReimbursementClaim(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('returned', 'Returned'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='reimbursement_claims')
    allowance_type = models.ForeignKey(AllowanceType, on_delete=models.PROTECT, related_name='claims')
    
    amount_claimed = models.DecimalField(max_digits=12, decimal_places=2)
    amount_approved = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    expense_date = models.DateField()
    description = models.TextField()
    receipt = models.FileField(upload_to='reimbursement_receipts/', null=True, blank=True)
    notes = models.TextField(blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    submitted_at = models.DateTimeField(null=True, blank=True)
    
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_claims')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_comment = models.TextField(blank=True)
    
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    paid_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        if self.employee.organization_id != self.allowance_type.organization_id:
            raise ValidationError("Employee and AllowanceType must belong to the same organization.")
        if self.organization_id != self.employee.organization_id:
            raise ValidationError("Organization mismatch.")
        if self.amount_claimed and self.amount_claimed < 0:
            raise ValidationError({"amount_claimed": "Amount cannot be negative."})
        if self.amount_approved and self.amount_approved < 0:
            raise ValidationError({"amount_approved": "Approved amount cannot be negative."})

    def __str__(self):
        return f"Claim #{self.id} - {self.employee} - {self.allowance_type.name}"
