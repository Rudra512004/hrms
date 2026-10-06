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
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    salary_structure = models.ForeignKey('SalaryStructure', on_delete=models.SET_NULL, null=True, blank=True, related_name='compensation_history')
    basic_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
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

    def __str__(self):
        return (
            f"{self.employee.employee_code} — "
            f"₹{self.basic_salary} from {self.effective_from}"
        )

class StatutoryRule(models.Model):
    """
    Versioned, effective-dated statutory rules.
    Global rules have organization=None. Tenant overrides have organization set.
    """
    RULE_TYPE_CHOICES = [
        ('PF', 'Provident Fund'),
        ('ESI', 'Employee State Insurance'),
        ('PT', 'Professional Tax'),
        ('TDS', 'Tax Deducted at Source'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True)
    rule_type = models.CharField(max_length=10, choices=RULE_TYPE_CHOICES)
    state = models.CharField(max_length=50, null=True, blank=True, help_text="Required for PT")
    
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    employee_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="e.g. 12.00 for PF")
    employer_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="e.g. 13.00 for PF (12 + 1 EDLI/Admin)")
    
    applicable_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="e.g. 15000 for PF, 21000 for ESI")
    
    rule_metadata = models.JSONField(default=dict, blank=True, help_text="For complex structures like PT slabs")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-effective_from']

    def __str__(self):
        org = self.organization.name if self.organization else 'Global'
        return f"{self.rule_type} ({org}) - {self.effective_from}"

class PayrollRun(models.Model):
    """
    One payroll run per organization per calendar month.
    Transitions: draft → approved (locked; no re-generation).
    """
    STATUS_DRAFT = 'draft'
    STATUS_APPROVED = 'approved'
    STATUS_FINALIZED = 'finalized'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_FINALIZED, 'Finalized'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='payroll_periods',
    )
    run_type = models.CharField(max_length=50, default='REGULAR')
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
    calculation_version = models.CharField(max_length=20, default='v1')

    class Meta:
        unique_together = ('organization', 'year', 'month', 'run_type')
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
    STATUS_FINALIZED = 'finalized'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_FINALIZED, 'Finalized'),
    ]

    period = models.ForeignKey(
        PayrollRun,
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
    lop_dates = models.JSONField(
        default=list, 
        blank=True, 
        help_text="List of YYYY-MM-DD strings where employee was marked absent/LOP"
    )

    # --- Salary snapshot (from CompensationHistory at generation time) ---
    basic_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Monthly basic salary as of period start"
    )

    # --- Computed amounts ---
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    employer_contributions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

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
    KIND=[
        ('earning', 'Earning'),
        ('deduction', 'Deduction'),
        ('employer_contribution', 'Employer Contribution'),
        ('tax', 'Tax')
    ]
    organization=models.ForeignKey(Organization,on_delete=models.CASCADE,related_name='salary_components')
    name=models.CharField(max_length=120); code=models.CharField(max_length=32); kind=models.CharField(max_length=30,choices=KIND)
    is_taxable=models.BooleanField(default=False); is_active=models.BooleanField(default=True)
    class Meta: unique_together=('organization','code')

class SalaryStructure(models.Model):
    organization=models.ForeignKey(Organization,on_delete=models.CASCADE,related_name='salary_structures')
    name=models.CharField(max_length=120); is_active=models.BooleanField(default=True)
    class Meta: unique_together=('organization','name')

class SalaryStructureComponent(models.Model):
    structure=models.ForeignKey(SalaryStructure,on_delete=models.CASCADE,related_name='components')
    component=models.ForeignKey(SalaryComponent,on_delete=models.PROTECT)
    CALC_CHOICES = [('FIXED_AMOUNT', 'Fixed Amount'), ('PERCENTAGE_OF_BASIC', 'Percentage of Basic')]
    calculation_type = models.CharField(max_length=50, choices=CALC_CHOICES, default='FIXED_AMOUNT')
    amount=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    class Meta: unique_together=('structure','component')


class PayrollAdjustment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_PROCESSED = 'processed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_PROCESSED, 'Processed')
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payroll_adjustments')
    component = models.ForeignKey(SalaryComponent, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    period_year = models.PositiveSmallIntegerField()
    period_month = models.PositiveSmallIntegerField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class PayrollLineItem(models.Model):
    CATEGORY_CHOICES = [
        ('EARNING', 'Earning'),
        ('DEDUCTION', 'Deduction'),
        ('EMPLOYER_CONTRIBUTION', 'Employer Contribution'),
        ('TAX', 'Tax'),
    ]
    payroll_record = models.ForeignKey(PayrollRecord, on_delete=models.CASCADE, related_name='line_items')
    component = models.ForeignKey(SalaryComponent, null=True, blank=True, on_delete=models.PROTECT)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_backfilled = models.BooleanField(default=False)
    
    # --- Lineage & Evidence ---
    calculation_type = models.CharField(max_length=50, null=True, blank=True)
    calculation_base = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    rate = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    calculation_metadata = models.JSONField(default=dict, blank=True)
    
    source_adjustment = models.ForeignKey(PayrollAdjustment, null=True, blank=True, on_delete=models.PROTECT)
    source_structure_component = models.ForeignKey(SalaryStructureComponent, null=True, blank=True, on_delete=models.PROTECT)
