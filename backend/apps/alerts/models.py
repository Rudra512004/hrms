from django.db import models
from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from apps.organization.models import Organization, Branch, Department, Team
from apps.employees.models import Employee

class AlertRule(models.Model):
    ALERT_TYPES = [
        ('excessive_hours', 'Excessive Working Hours'),
        ('long_session', 'Long Continuous Work Session'),
        ('break_reminder', 'Break Reminder'),
        ('excessive_break', 'Excessive Break Duration'),
        ('prolonged_idle', 'Prolonged Idle Time'),
        ('low_active', 'Low Active Time'),
        ('consecutive_days', 'Consecutive Working Days'),
        ('late_start', 'Late Start / Attendance Reminder'),
        ('hydration', 'Hydration Break Alert'),
    ]

    UNIT_CHOICES = [
        ('minutes', 'Minutes'),
        ('percentage', 'Percentage'),
        ('days', 'Days'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='alert_rules')
    
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=True)

    # Configuration using Integer values to distinguish semantics explicitly
    default_value = models.IntegerField(help_text="Default threshold value in specified unit")
    minimum_value = models.IntegerField(null=True, blank=True, help_text="Minimum allowed threshold value")
    maximum_value = models.IntegerField(null=True, blank=True, help_text="Maximum allowed threshold value")
    value_unit = models.CharField(max_length=20, choices=UNIT_CHOICES)

    employee_customization_allowed = models.BooleanField(default=False)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    notification_enabled = models.BooleanField(default=True)

    # Scopes
    applicable_branches = models.ManyToManyField(Branch, blank=True, related_name='alert_rules')
    applicable_departments = models.ManyToManyField(Department, blank=True, related_name='alert_rules')
    applicable_teams = models.ManyToManyField(Team, blank=True, related_name='alert_rules')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.minimum_value is not None and self.maximum_value is not None:
            if self.minimum_value > self.maximum_value:
                raise ValidationError({"minimum_value": "Minimum value cannot be greater than maximum value."})
        
        if self.default_value is not None:
            if self.minimum_value is not None and self.default_value < self.minimum_value:
                raise ValidationError({"default_value": "Default value cannot be less than minimum value."})
            if self.maximum_value is not None and self.default_value > self.maximum_value:
                raise ValidationError({"default_value": "Default value cannot be greater than maximum value."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_alert_type_display()})"


@receiver(m2m_changed, sender=AlertRule.applicable_branches.through)
def validate_alert_rule_branches(sender, instance, action, pk_set, **kwargs):
    if action in ['pre_add', 'post_add'] and pk_set:
        invalid = Branch.objects.filter(id__in=pk_set).exclude(organization=instance.organization)
        if invalid.exists():
            raise ValidationError("All applicable branches must belong to the rule's organization.")

@receiver(m2m_changed, sender=AlertRule.applicable_departments.through)
def validate_alert_rule_departments(sender, instance, action, pk_set, **kwargs):
    if action in ['pre_add', 'post_add'] and pk_set:
        invalid = Department.objects.filter(id__in=pk_set).exclude(branch__organization=instance.organization)
        if invalid.exists():
            raise ValidationError("All applicable departments must belong to the rule's organization.")

@receiver(m2m_changed, sender=AlertRule.applicable_teams.through)
def validate_alert_rule_teams(sender, instance, action, pk_set, **kwargs):
    if action in ['pre_add', 'post_add'] and pk_set:
        invalid = Team.objects.filter(id__in=pk_set).exclude(department__branch__organization=instance.organization)
        if invalid.exists():
            raise ValidationError("All applicable teams must belong to the rule's organization.")


class EmployeeAlertPreference(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='alert_preferences')
    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name='employee_preferences')
    is_enabled = models.BooleanField(default=True)
    custom_value = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('employee', 'rule')

    def clean(self):
        super().clean()
        if self.employee.organization_id != self.rule.organization_id:
            raise ValidationError("Employee must belong to the same organization as the alert rule.")
        
        if not self.rule.employee_customization_allowed:
            if self.custom_value is not None or not self.is_enabled:
                raise ValidationError("Employee customization is not allowed for this rule.")
        
        if self.custom_value is not None:
            if self.rule.minimum_value is not None and self.custom_value < self.rule.minimum_value:
                raise ValidationError({"custom_value": f"Cannot be less than the rule minimum ({self.rule.minimum_value})."})
            if self.rule.maximum_value is not None and self.custom_value > self.rule.maximum_value:
                raise ValidationError({"custom_value": f"Cannot be greater than the rule maximum ({self.rule.maximum_value})."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee.user.get_full_name()} - {self.rule.name}"


class AlertInstance(models.Model):
    STATUS_CHOICES = [
        ('detected', 'Detected'),
        ('notified', 'Notified'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='alert_instances')
    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name='instances')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='detected')
    
    # Deterministic occurrence key (e.g., 'excessive_hours:2026-10-08:emp_1' or 'hydration:2026-10-08:hour_1')
    occurrence_key = models.CharField(max_length=255, help_text="Deterministic key to prevent duplicate alerts")
    
    evaluated_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    reference_date = models.DateField(null=True, blank=True)
    
    metric_value_at_trigger = models.IntegerField(null=True, blank=True)
    notification_reference = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        unique_together = ('rule', 'employee', 'occurrence_key')
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['rule', 'occurrence_key']),
        ]

    def __str__(self):
        return f"{self.rule.name} for {self.employee} ({self.status})"
