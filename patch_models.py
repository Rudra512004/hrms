import os

filepath = 'backend/apps/attendance/models.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Add fields to Shift model
shift_fields = '''    grace_period = models.DurationField(null=True, blank=True, help_text="Allowed late check-in grace period")
    full_day_hours = models.DurationField(null=True, blank=True, help_text="Minimum hours for a full day")
    half_day_hours = models.DurationField(null=True, blank=True, help_text="Minimum hours for a half day")
    work_days = models.CharField(max_length=20, default='0,1,2,3,4', help_text="Comma-separated integers for work days (0=Mon, 6=Sun)")'''
content = content.replace('    grace_period = models.DurationField(null=True, blank=True, help_text="Allowed late check-in grace period")', shift_fields)

# Add EmployeeShiftAssignment model
assignment_model = '''

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
                check=models.Q(effective_to__gte=models.F('effective_from')) | models.Q(effective_to__isnull=True),
                name='check_valid_effective_dates'
            )
        ]

    def __str__(self):
        return f"{self.employee} -> {self.shift} ({self.effective_from} to {self.effective_to or 'Open'})"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        
        if self.employee_id and self.shift_id:
            if self.employee.organization_id != self.shift.organization_id:
                raise ValidationError("Employee and Shift must belong to the same organization.")
            
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
'''
content = content + assignment_model

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
