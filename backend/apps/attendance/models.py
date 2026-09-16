from django.db import models
from apps.employees.models import Employee
from django.utils import timezone

class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('half_day', 'Half Day'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(default=timezone.now)
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')

    # Audit fields for location
    check_in_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_in_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_in_accuracy = models.FloatField(null=True, blank=True)

    check_out_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_out_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_out_accuracy = models.FloatField(null=True, blank=True)
    total_break_duration = models.DurationField(null=True, blank=True)
    productive_work_duration = models.DurationField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('employee', 'date')
        ordering = ['-date', '-check_in']

    def __str__(self):
        return f"{self.employee} - {self.date}"

class AttendanceBreak(models.Model):
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='breaks')
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['started_at']

    def __str__(self):
        return f"Break for {self.attendance} starting {self.started_at}"

from apps.organization.models import Organization

class Holiday(models.Model):
    branch = models.ForeignKey('organization.Branch', on_delete=models.CASCADE, related_name='holidays')
    name = models.CharField(max_length=255)
    date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('branch', 'date')
        ordering = ['date']

    def __str__(self):
        return f"{self.name} - {self.date}"

class Shift(models.Model):
    branch = models.ForeignKey('organization.Branch', on_delete=models.CASCADE, related_name='shifts')
    name = models.CharField(max_length=255)
    start_time = models.TimeField()
    end_time = models.TimeField()
    grace_period = models.DurationField(null=True, blank=True, help_text="Allowed late check-in grace period")
    full_day_hours = models.DurationField(null=True, blank=True, help_text="Minimum hours for a full day")
    half_day_hours = models.DurationField(null=True, blank=True, help_text="Minimum hours for a half day")
    work_days = models.CharField(max_length=20, default='0,1,2,3,4', help_text="Comma-separated integers for work days (0=Mon, 6=Sun)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('branch', 'name')
        ordering = ['start_time']

    def __str__(self):
        return f"{self.name} ({self.start_time} - {self.end_time})"


class EmployeeShiftAssignment(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='shift_assignments')
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='assignments')
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-effective_from']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(effective_to__gte=models.F('effective_from')) | models.Q(effective_to__isnull=True),
                name='check_valid_effective_dates'
            )
        ]

    def __str__(self):
        return f"{self.employee} -> {self.shift} ({self.effective_from} to {self.effective_to or 'Open'})"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError

        if self.employee_id and self.shift_id:
            if self.employee.branch_id and self.shift.branch_id:
                if self.employee.branch_id != self.shift.branch_id:
                    raise ValidationError("Employee and Shift must belong to the same branch.")

        # Overlap check
        if self.employee_id and self.effective_from:
            qs = EmployeeShiftAssignment.objects.filter(employee=self.employee)
            if self.pk:
                qs = qs.exclude(pk=self.pk)

            for assignment in qs:
                # If A ends before B starts, no overlap
                if self.effective_to and assignment.effective_from and self.effective_to < assignment.effective_from:
                    continue
                # If B ends before A starts, no overlap
                if assignment.effective_to and self.effective_from and assignment.effective_to < self.effective_from:
                    continue
                # Otherwise they overlap
                raise ValidationError({"effective_from": "Employee cannot have overlapping shift assignments."})
