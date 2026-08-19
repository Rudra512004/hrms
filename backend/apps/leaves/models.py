from django.db import models
from apps.employees.models import Employee
from apps.organization.models import Organization

class LeaveType(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='leave_types')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    annual_allocation = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('organization', 'name')

    def __str__(self):
        return f"{self.name} - {self.organization.name}"

class LeaveBalance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_balances')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='balances')
    allocated = models.PositiveIntegerField(default=0)
    used = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('employee', 'leave_type')

    @property
    def remaining(self):
        return self.allocated - self.used

    def __str__(self):
        return f"{self.employee} - {self.leave_type.name}: {self.remaining} left"

class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name='requests')
    start_date = models.DateField()
    end_date = models.DateField()
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
        return (self.end_date - self.start_date).days + 1
