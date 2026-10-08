from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

from apps.employees.models import Employee
from apps.organization.models import Organization


class CompensationHistory(models.Model):
    """
    Immutable salary records. A new entry is created every time salary changes.
    The active record is the one where effective_to is null.
    Historical records are never modified or deleted.
    """
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='compensation_history',
    )
    salary_structure = models.ForeignKey(
        'SalaryStructure',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='employee_assignments',
        help_text="The salary structure governing this employee's compensation."
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    basic_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    ctc_annual = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True, blank=True,
    )
    currency = models.CharField(max_length=10, default='INR')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-effective_from']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(effective_to__gte=models.F('effective_from')) | models.Q(effective_to__isnull=True),
                name='compensation_history_effective_dates_valid'
            )
        ]

    def __str__(self):
        return (
            f"{self.employee.employee_code} — "
            f"₹{self.basic_salary} from {self.effective_from}"
        )


class PayrollPeriod(models.Model):
    """
    One payroll run per organization per calendar month.
    Transitions: draft → approved (locked; no re-generation).
    """
    STATUS_DRAFT = 'draft'
    STATUS_APPROVED = 'approved'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_APPROVED, 'Approved'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='payroll_periods',
    )
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()   # 1–12
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_payroll_periods',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'year', 'month')
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.organization.name} — {self.year}/{self.month:02d}"


class PayrollRecord(models.Model):
    """
    One computed payroll line per employee per period.
    All monetary values use Decimal. Fields are snapshots at generation time.
    Historical records are never modified after approval.
    """
    STATUS_DRAFT = 'draft'
    STATUS_APPROVED = 'approved'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_APPROVED, 'Approved'),
    ]

    period = models.ForeignKey(
        PayrollPeriod,
        on_delete=models.CASCADE,
        related_name='records',
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='payroll_records',
    )

    # --- Working-day breakdown (computed at generation time, never recomputed) ---
    working_days = models.PositiveSmallIntegerField(
        help_text="Total scheduled working days in the period (excl. weekends & holidays)"
    )
    present_days = models.PositiveSmallIntegerField(
        help_text="Days with Attendance status=present"
    )
    half_days = models.PositiveSmallIntegerField(
        default=0,
        help_text="Days with Attendance status=half_day (counted as 0.5)"
    )
    absent_days = models.PositiveSmallIntegerField(
        help_text="working_days - present_days - half_days - leave_days"
    )
    leave_days = models.PositiveSmallIntegerField(
        help_text="Approved leave days overlapping the period (already weekday/holiday excluded)"
    )
    effective_days = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        help_text="present + (half_days * 0.5) + leave_days — paid days"
    )

    # --- Salary snapshot (from CompensationHistory at generation time) ---
    basic_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Monthly basic salary as of period start"
    )

    # --- Computed amounts ---
    gross_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="basic_salary × (effective_days / working_days)"
    )
    net_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Equals gross_salary (no statutory deductions in current scope)"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('period', 'employee')
        ordering = ['employee__employee_code']

    @property
    def lop_days(self) -> Decimal:
        """
        Unpaid absence days: working_days - effective_days.
        Capped at 0.0 minimum.
        """
        return max(Decimal('0.0'), Decimal(self.working_days) - self.effective_days)

    @property
    def lop_amount(self) -> Decimal:
        """
        Loss of pay deduction amount: max(0, basic_salary - net_salary).
        """
        return max(Decimal('0.00'), self.basic_salary - self.net_salary)

    def __str__(self):
        return (
            f"{self.employee.employee_code} — "
            f"{self.period.year}/{self.period.month:02d} — ₹{self.net_salary}"
        )


class Payslip(models.Model):
    """
    Issued receipt/reference for an approved PayrollRecord.
    References the authoritative PayrollRecord snapshot without duplicating calculation fields.
    """
    STATUS_ISSUED = 'issued'
    STATUS_REVOKED = 'revoked'
    STATUS_CHOICES = [
        (STATUS_ISSUED, 'Issued'),
        (STATUS_REVOKED, 'Revoked'),
    ]

    payroll_record = models.OneToOneField(
        PayrollRecord,
        on_delete=models.PROTECT,
        related_name='payslip',
    )
    payslip_number = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Format: PAY-YYYYMM-EMPLOYEE_CODE",
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ISSUED,
    )

    class Meta:
        ordering = [
            '-payroll_record__period__year',
            '-payroll_record__period__month',
            'payroll_record__employee__employee_code',
        ]
        indexes = [
            models.Index(fields=['payslip_number']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.payslip_number} — {self.payroll_record.employee.employee_code}"

class SalaryComponent(models.Model):
    KIND_CHOICES = [
        ('earning', 'Earning'),
        ('deduction', 'Employee Deduction'),
        ('employer_contribution', 'Employer Contribution'),
        ('informational', 'Informational / Non-Payable'),
    ]

    CALCULATION_CHOICES = [
        ('flat', 'Flat Amount'),
        ('percentage', 'Percentage'),
        ('formula', 'Formula'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='salary_components')
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=32)
    kind = models.CharField(max_length=25, choices=KIND_CHOICES)
    
    # Calculation Logic
    calculation_type = models.CharField(max_length=20, choices=CALCULATION_CHOICES, default='flat')
    formula_expression = models.CharField(
        max_length=500, 
        blank=True, 
        help_text="e.g. 5000 for flat, 40% of BASIC, or a formula like (BASIC * 0.4)"
    )

    # Flags
    is_taxable = models.BooleanField(default=False)
    is_prorated = models.BooleanField(default=True, help_text="Does this component scale with attendance?")
    is_epf_applicable = models.BooleanField(default=False)
    is_esic_applicable = models.BooleanField(default=False)
    is_pt_applicable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta: 
        unique_together = ('organization', 'code')

    def __str__(self):
        return f"{self.name} ({self.code})"

class SalaryStructure(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='salary_structures')
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta: 
        unique_together = ('organization', 'name')

    def __str__(self):
        return f"{self.name} - {self.organization.name}"

class SalaryStructureComponent(models.Model):
    structure = models.ForeignKey(SalaryStructure, on_delete=models.CASCADE, related_name='components')
    component = models.ForeignKey(SalaryComponent, on_delete=models.PROTECT)
    
    # Ordering within the structure, useful for evaluating formula dependencies
    order = models.PositiveIntegerField(default=0)

    # Optional overrides. If blank/null, falls back to the component's defaults.
    override_calculation_type = models.CharField(max_length=20, choices=SalaryComponent.CALCULATION_CHOICES, null=True, blank=True)
    override_formula_expression = models.CharField(max_length=500, blank=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Legacy/Fallback fixed amount if needed.")
    
    class Meta: 
        unique_together = ('structure', 'component')
        ordering = ['order']

    def __str__(self):
        return f"{self.structure.name} -> {self.component.code}"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.component.organization_id != self.structure.organization_id:
            raise ValidationError("Component must belong to the same organization as the Salary Structure.")

