from django.db import models
from apps.employees.models import Employee
from apps.organization.models import Organization

class LeaveType(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='leave_types')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('organization', 'name')

    def __str__(self):
        return f"{self.name} - {self.organization.name}"

class BranchLeavePolicy(models.Model):
    PRORATION_ROUNDING_CHOICES = [
        ('nearest_half', 'Nearest 0.5'),
        ('floor', 'Floor'),
        ('ceiling', 'Ceiling'),
    ]

    branch = models.ForeignKey('organization.Branch', on_delete=models.CASCADE, related_name='leave_policies')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='branch_policies')

    monthly_allocation = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    proration_enabled = models.BooleanField(default=True)
    proration_rounding = models.CharField(max_length=20, choices=PRORATION_ROUNDING_CHOICES, default='nearest_half')

    carry_forward_enabled = models.BooleanField(default=False)
    carry_forward_limit = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    carry_forward_expiry_months = models.PositiveIntegerField(null=True, blank=True)

    negative_balance_allowed = models.BooleanField(default=False)
    half_day_allowed = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=True)
    requires_supporting_document = models.BooleanField(default=False)
    advance_notice_days = models.PositiveIntegerField(default=0)
    cancellation_allowed = models.BooleanField(default=True)

    class Meta:
        unique_together = ('branch', 'leave_type')

    def clean(self):
        super().clean()
        if self.branch_id and self.leave_type_id:
            if self.branch.organization_id != self.leave_type.organization_id:
                from django.core.exceptions import ValidationError
                raise ValidationError("Branch and LeaveType must belong to the same organization.")

    def __str__(self):
        return f"{self.leave_type.name} Policy for {self.branch.name}"

class LeaveCycle(models.Model):
    branch = models.ForeignKey('organization.Branch', on_delete=models.CASCADE, related_name='leave_cycles')
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({'end_date': 'End date cannot be before start date.'})

        if self.is_active and self.branch_id and self.start_date and self.end_date:
            overlapping = LeaveCycle.objects.filter(
                branch=self.branch,
                is_active=True,
                start_date__lte=self.end_date,
                end_date__gte=self.start_date
            ).exclude(pk=self.pk)
            if overlapping.exists():
                raise ValidationError("Overlapping active cycle exists for this branch.")

    def __str__(self):
        return f"{self.name} - {self.branch.name if self.branch_id else 'None'}"


class LeaveBalance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_balances')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='balances')
    branch = models.ForeignKey('organization.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    leave_cycle = models.ForeignKey(LeaveCycle, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    allocated = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    used = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    carried_forward = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    adjustment = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    class Meta:
        unique_together = ('employee', 'leave_type', 'leave_cycle')

    @property
    def remaining(self):
        return self.allocated + self.carried_forward + self.adjustment - self.used

    def clean(self):
        super().clean()
        if self.pk is None:
            # New operational balance
            from django.core.exceptions import ValidationError
            if not self.branch_id or not self.leave_cycle_id:
                raise ValidationError("Operational LeaveBalance must have branch and leave_cycle assigned.")

    def __str__(self):
        return f"{self.employee} - {self.leave_type.name}: {self.remaining} left"

class LeaveBalanceTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('legacy_conversion_allocated', 'Legacy Conversion Allocated'),
        ('legacy_conversion_used', 'Legacy Conversion Used'),
        ('allocation', 'Allocation'),
        ('monthly_accrual', 'Monthly Accrual'),
        ('proration', 'Proration'),
        ('carry_forward', 'Carry Forward'),
        ('usage', 'Usage (Leave Approved)'),
        ('refund', 'Refund (Leave Cancelled)'),
        ('manual_adjustment', 'Manual Adjustment'),
        ('carry_forward_expiry', 'Carry Forward Expiry'),
        ('exit_forfeiture', 'Exit Forfeiture'),
        ('branch_transfer_adjustment', 'Branch Transfer Adjustment'),
    ]

    balance = models.ForeignKey(LeaveBalance, on_delete=models.CASCADE, related_name='transactions')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_transactions')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    leave_cycle = models.ForeignKey(LeaveCycle, on_delete=models.SET_NULL, null=True, blank=True)
    leave_request = models.ForeignKey('LeaveRequest', on_delete=models.SET_NULL, null=True, blank=True)
    actor = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)

    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    effective_date = models.DateField(null=True, blank=True)
    reference = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} of {self.amount} for {self.employee.employee_code}"


class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    HALF_DAY_PERIOD_CHOICES = [
        ('first_half', 'First Half'),
        ('second_half', 'Second Half'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name='requests')
    start_date = models.DateField()
    end_date = models.DateField()

    is_half_day = models.BooleanField(default=False)
    half_day_period = models.CharField(max_length=20, choices=HALF_DAY_PERIOD_CHOICES, null=True, blank=True)
    supporting_document = models.FileField(upload_to='leave_documents/', null=True, blank=True)

    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    reviewed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_leaves')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee} - {self.leave_type.name} ({self.start_date} to {self.end_date})"

    @property
    def duration_days(self):
        branch = getattr(self.employee, 'branch', None)
        if not branch:
            return None

        from apps.organization.services import WorkingCalendarService
        from decimal import Decimal
        days = WorkingCalendarService.count_working_days(branch, self.start_date, self.end_date)
        if days == 0:
            return Decimal('0.0')
        if self.is_half_day:
            return Decimal(str(days)) - Decimal('0.5')
        return Decimal(str(days))

