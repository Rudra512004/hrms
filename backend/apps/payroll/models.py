from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid
from django.utils import timezone

from apps.employees.models import Employee
from apps.organization.models import Organization
from django.conf import settings


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
    STATUS_LOCKED = 'locked'
    STATUS_PROCESSING = 'processing'
    STATUS_REVIEW = 'review'
    STATUS_FINALIZED = 'finalized'
    STATUS_DISBURSED = 'disbursed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_LOCKED, 'Locked'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_REVIEW, 'Review'),
        (STATUS_FINALIZED, 'Finalized'),
        (STATUS_DISBURSED, 'Disbursed'),
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
    STATUS_FINALIZED = 'finalized'
    STATUS_DISBURSED = 'disbursed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_FINALIZED, 'Finalized'),
        (STATUS_DISBURSED, 'Disbursed'),
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
    tds_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Calculated monthly TDS deduction for this payroll period"
    )
    net_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Equals gross_salary minus deductions (TDS, etc.)"
    )
    tax_calculation_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="Audit snapshot of tax calculation inputs, slabs, deductions, and projected liability"
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
    Contains complete, immutable snapshot information so that historical payslips
    remain reproducible even if live configurations change later.
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
    issued_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_payslips',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ISSUED,
    )

    # --- Verification & Integrity ---
    verification_token = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        editable=False,
    )
    integrity_hash = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="SHA-256 integrity hash of canonicalized snapshot",
    )

    # --- Immutable Snapshot: Organization & Branch ---
    organization_name = models.CharField(max_length=255, blank=True)
    legal_name = models.CharField(max_length=255, blank=True)
    organization_address = models.TextField(blank=True)
    cin = models.CharField(max_length=50, blank=True)
    branch_name = models.CharField(max_length=255, blank=True)
    branch_address = models.TextField(blank=True)

    # --- Immutable Snapshot: Employee ---
    employee_code = models.CharField(max_length=64, blank=True)
    employee_name = models.CharField(max_length=255, blank=True)
    department_name = models.CharField(max_length=150, blank=True)
    designation_name = models.CharField(max_length=150, blank=True)
    joining_date = models.DateField(null=True, blank=True)
    bank_name = models.CharField(max_length=150, blank=True)
    masked_bank_account = models.CharField(max_length=50, blank=True)
    bank_ifsc = models.CharField(max_length=20, blank=True)
    payment_mode = models.CharField(max_length=30, blank=True)
    masked_pan = models.CharField(max_length=20, blank=True)
    uan = models.CharField(max_length=50, blank=True)
    esic_number = models.CharField(max_length=50, blank=True)

    # --- Immutable Snapshot: Period & Attendance ---
    period_year = models.PositiveSmallIntegerField(null=True, blank=True)
    period_month = models.PositiveSmallIntegerField(null=True, blank=True)
    period_start_date = models.DateField(null=True, blank=True)
    period_end_date = models.DateField(null=True, blank=True)
    calendar_days = models.PositiveSmallIntegerField(default=0)
    working_days = models.PositiveSmallIntegerField(default=0)
    present_days = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    half_days = models.PositiveSmallIntegerField(default=0)
    absent_days = models.PositiveSmallIntegerField(default=0)
    leave_days = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    effective_days = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    lop_days = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))

    # --- Immutable Snapshot: Financial Summary ---
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    gross_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    net_pay = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    net_pay_in_words = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = [
            '-payroll_record__period__year',
            '-payroll_record__period__month',
            'payroll_record__employee__employee_code',
        ]
        indexes = [
            models.Index(fields=['payslip_number']),
            models.Index(fields=['status']),
            models.Index(fields=['verification_token']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['verification_token'], name='unique_payslip_verification_token'),
        ]

    def __str__(self):
        return f"{self.payslip_number} — {self.payroll_record.employee.employee_code}"

    def clean(self):
        super().clean()
        if self.pk:
            orig = Payslip.objects.filter(pk=self.pk).values('status', 'gross_earnings', 'net_pay', 'total_deductions', 'integrity_hash').first()
            if orig and orig['status'] == self.STATUS_ISSUED:
                if (
                    self.gross_earnings != orig['gross_earnings']
                    or self.net_pay != orig['net_pay']
                    or self.total_deductions != orig['total_deductions']
                    or self.integrity_hash != orig['integrity_hash']
                ):
                    from django.core.exceptions import ValidationError
                    raise ValidationError("Issued payslip financial records are immutable.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class PayslipLine(models.Model):
    """
    Normalized line items representing earnings, deductions, or employer contributions
    for a specific immutable Payslip snapshot.
    """
    CATEGORY_EARNING = 'earning'
    CATEGORY_DEDUCTION = 'deduction'
    CATEGORY_EMPLOYER_CONTRIBUTION = 'employer_contribution'
    CATEGORY_CHOICES = [
        (CATEGORY_EARNING, 'Earning'),
        (CATEGORY_DEDUCTION, 'Deduction'),
        (CATEGORY_EMPLOYER_CONTRIBUTION, 'Employer Contribution'),
    ]

    payslip = models.ForeignKey(
        Payslip,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    component_code = models.CharField(max_length=32)
    name = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['payslip', 'category']),
        ]

    def __str__(self):
        return f"{self.payslip.payslip_number} - {self.name}: ₹{self.amount}"

    def clean(self):
        super().clean()
        if self.pk and self.payslip.status == Payslip.STATUS_ISSUED:
            from django.core.exceptions import ValidationError
            raise ValidationError("Cannot modify lines of an issued payslip.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


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


class OrganizationBankAccount(models.Model):
    """
    Corporate bank account of an organization (or branch) used as the debit account
    for salary disbursements.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='bank_accounts',
    )
    branch = models.ForeignKey(
        'organization.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_accounts',
        help_text="Optional branch-specific debit account; null applies organization-wide.",
    )
    bank_name = models.CharField(max_length=150)
    account_name = models.CharField(max_length=150)
    account_number = models.CharField(max_length=50)
    ifsc_code = models.CharField(max_length=20)
    is_primary = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_primary', 'bank_name']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'branch'],
                condition=models.Q(is_primary=True, is_active=True),
                name='unique_primary_active_org_bank_account',
            ),
        ]

    def __str__(self):
        last4 = self.account_number[-4:] if len(self.account_number) >= 4 else self.account_number
        return f"{self.organization.name} - {self.bank_name} (••••{last4})"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.account_number:
            self.account_number = self.account_number.strip()
        if self.ifsc_code:
            self.ifsc_code = self.ifsc_code.strip().upper()
        if self.branch_id and self.branch.organization_id != self.organization_id:
            raise ValidationError({'branch': 'Branch must belong to the same organization.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class PaymentRoutingConfiguration(models.Model):
    """
    Organization-scoped, effective-dated configuration for electronic payment routing rules.
    Controls mapping from employee payment mode to generic bank upload modes (NEFT, RTGS, IFT).
    No thresholds or matching rules are hardcoded; all routing behavior is purely configuration-driven.
    """
    PAYMENT_MODE_CHOICES = [
        ('NEFT', 'National Electronic Funds Transfer (NEFT)'),
        ('RTGS', 'Real Time Gross Settlement (RTGS)'),
        ('IFT', 'Internal Fund Transfer (IFT)'),
    ]

    IFT_MATCHING_MODE_NONE = 'none'
    IFT_MATCHING_MODE_EXACT = 'exact_ifsc'
    IFT_MATCHING_MODE_PREFIX = 'ifsc_prefix'
    IFT_MATCHING_CHOICES = [
        (IFT_MATCHING_MODE_NONE, 'None / Disabled'),
        (IFT_MATCHING_MODE_EXACT, 'Exact IFSC Match'),
        (IFT_MATCHING_MODE_PREFIX, 'Configured IFSC Prefix Match'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='payment_routing_configs',
    )
    branch = models.ForeignKey(
        'organization.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_routing_configs',
        help_text="Optional branch-specific override.",
    )
    default_payment_mode = models.CharField(
        max_length=10,
        choices=PAYMENT_MODE_CHOICES,
        default='NEFT',
    )
    rtgs_enabled = models.BooleanField(
        default=False,
        help_text="Whether amounts exceeding rtgs_threshold automatically route via RTGS.",
    )
    rtgs_threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Configured threshold above which payments are routed as RTGS if enabled.",
    )
    ift_enabled = models.BooleanField(
        default=False,
        help_text="Whether IFT routing is enabled for this organization.",
    )
    ift_matching_mode = models.CharField(
        max_length=20,
        choices=IFT_MATCHING_CHOICES,
        default=IFT_MATCHING_MODE_NONE,
        help_text="Configured IFT matching rule (none, exact_ifsc, ifsc_prefix).",
    )
    ift_ifsc_prefix_length = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Configured length of IFSC prefix to match when ift_matching_mode is ifsc_prefix.",
    )
    effective_from = models.DateField(
        help_text="Date from which this configuration becomes active.",
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-effective_from', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'branch', 'effective_from'],
                name='unique_org_branch_effective_routing_config',
            ),
        ]

    def __str__(self):
        return f"{self.organization.name} Routing Config (Effective {self.effective_from})"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.rtgs_enabled:
            if self.rtgs_threshold is None or self.rtgs_threshold <= 0:
                raise ValidationError({'rtgs_threshold': 'A positive RTGS threshold must be specified when RTGS routing is enabled.'})
        if self.ift_enabled:
            if self.ift_matching_mode == self.IFT_MATCHING_MODE_PREFIX:
                if not self.ift_ifsc_prefix_length or not (1 <= self.ift_ifsc_prefix_length <= 11):
                    raise ValidationError({'ift_ifsc_prefix_length': 'Prefix length (between 1 and 11) must be specified for ifsc_prefix matching mode.'})
        if self.branch_id and self.branch.organization_id != self.organization_id:
            raise ValidationError({'branch': 'Branch must belong to the same organization.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class DisbursementBatch(models.Model):
    """
    Offline generic bank disbursement export batch for finalized payroll or FnF settlement.
    Tracks maker-checker workflow (draft/prepared -> approved -> exported) and
    snapshots the routing configuration used.
    """
    BATCH_TYPE_REGULAR = 'regular'
    BATCH_TYPE_FNF = 'fnf'
    BATCH_TYPE_CHOICES = [
        (BATCH_TYPE_REGULAR, 'Regular Payroll'),
        (BATCH_TYPE_FNF, 'Full & Final Settlement'),
    ]

    STATUS_DRAFT = 'draft'
    STATUS_APPROVED = 'approved'
    STATUS_EXPORTED = 'exported'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft / Prepared'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_EXPORTED, 'Exported'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='disbursement_batches',
    )
    batch_type = models.CharField(
        max_length=20,
        choices=BATCH_TYPE_CHOICES,
        default=BATCH_TYPE_REGULAR,
        db_index=True,
    )
    period = models.ForeignKey(
        PayrollPeriod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='disbursement_batches',
    )
    final_settlement = models.ForeignKey(
        'payroll.FinalSettlement',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='disbursement_batches',
    )
    branch = models.ForeignKey(
        'organization.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='disbursement_batches',
    )
    batch_number = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Format: DISB-YYYYMM-ORGCODE-SEQUENCE or DISB-FNF-YYYYMM-ORGCODE-SEQUENCE",
    )
    debit_account = models.ForeignKey(
        OrganizationBankAccount,
        on_delete=models.PROTECT,
        related_name='disbursement_batches',
    )
    debit_account_number = models.CharField(
        max_length=50,
        help_text="Immutable snapshot of the corporate debit account number.",
    )
    value_date = models.DateField(
        help_text="Value date for bank execution (DD-MM-YYYY in export).",
    )
    narration = models.CharField(
        max_length=255,
        help_text="Deterministic payroll/FnF narration (e.g. Salary Oct 2026 or FnF Settlement FNF-001).",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    total_count = models.PositiveIntegerField(default=0)
    routing_config_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="Immutable snapshot of the PaymentRoutingConfiguration used.",
    )

    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_disbursement_batches',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_disbursement_batches',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    exported_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exported_disbursement_batches',
    )
    exported_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'period']),
            models.Index(fields=['organization', 'final_settlement']),
            models.Index(fields=['status']),
            models.Index(fields=['batch_number']),
            models.Index(fields=['batch_type']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(batch_type='regular', period__isnull=False, final_settlement__isnull=True)) |
                    (models.Q(batch_type='fnf', period__isnull=True, final_settlement__isnull=False))
                ),
                name='disbursement_batch_valid_source_by_type',
            ),
            models.UniqueConstraint(
                fields=['organization', 'final_settlement'],
                condition=models.Q(batch_type='fnf') & ~models.Q(status='cancelled'),
                name='unique_active_fnf_disbursement_batch',
            ),
        ]

    def __str__(self):
        if self.period:
            return f"{self.batch_number} — {self.period.year}/{self.period.month:02d} ({self.status})"
        if self.final_settlement:
            return f"{self.batch_number} — FnF {self.final_settlement.settlement_number} ({self.status})"
        return f"{self.batch_number} ({self.status})"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.period and self.organization_id != self.period.organization_id:
            raise ValidationError("DisbursementBatch organization must match period organization.")
        if self.final_settlement and self.organization_id != self.final_settlement.organization_id:
            raise ValidationError("DisbursementBatch organization must match final settlement organization.")
        if self.debit_account and self.organization_id != self.debit_account.organization_id:
            raise ValidationError("DisbursementBatch organization must match debit account organization.")
        if self.pk:
            orig = DisbursementBatch.objects.filter(pk=self.pk).values(
                'status', 'total_amount', 'total_count', 'debit_account_number', 'value_date'
            ).first()
            if orig and orig['status'] in [self.STATUS_APPROVED, self.STATUS_EXPORTED]:
                if (
                    self.total_amount != orig['total_amount']
                    or self.total_count != orig['total_count']
                    or self.debit_account_number != orig['debit_account_number']
                    or self.value_date != orig['value_date']
                ):
                    raise ValidationError("Approved or exported disbursement batches are immutable.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class DisbursementItem(models.Model):
    """
    Immutable payment snapshot line for an individual employee record within a DisbursementBatch.
    Strictly aligns with the columns of Generic_Bank_Salary_Upload_Template - Sheet1.csv:
    Payment_Mode, Debit_Account_Number, Beneficiary_Account_Number, Beneficiary_Name,
    Beneficiary_IFSC, Amount, Value_Date, Narration, Beneficiary_Email, Beneficiary_Mobile.
    """
    batch = models.ForeignKey(
        DisbursementBatch,
        on_delete=models.CASCADE,
        related_name='items',
    )
    payroll_record = models.ForeignKey(
        PayrollRecord,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='disbursement_items',
    )
    final_settlement = models.ForeignKey(
        'payroll.FinalSettlement',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='disbursement_items',
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='disbursement_items',
    )
    payment_mode = models.CharField(max_length=20)
    debit_account_number = models.CharField(max_length=50)
    beneficiary_account_number = models.CharField(max_length=50)
    beneficiary_name = models.CharField(max_length=255)
    beneficiary_ifsc = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    value_date = models.DateField()
    narration = models.CharField(max_length=255)
    beneficiary_email = models.EmailField(max_length=255, blank=True)
    beneficiary_mobile = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ['employee__employee_code', 'id']
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(payroll_record__isnull=False, final_settlement__isnull=True)) |
                    (models.Q(payroll_record__isnull=True, final_settlement__isnull=False))
                ),
                name='disbursement_item_exactly_one_source',
            ),
            models.UniqueConstraint(
                fields=['batch', 'payroll_record'],
                condition=models.Q(payroll_record__isnull=False),
                name='unique_disbursement_item_per_batch_record',
            ),
            models.UniqueConstraint(
                fields=['batch', 'final_settlement'],
                condition=models.Q(final_settlement__isnull=False),
                name='unique_disbursement_item_per_batch_settlement',
            ),
        ]
        indexes = [
            models.Index(fields=['batch', 'payment_mode']),
            models.Index(fields=['final_settlement']),
        ]

    def __str__(self):
        return f"{self.batch.batch_number} - {self.employee.employee_code}: ₹{self.amount} ({self.payment_mode})"

    @property
    def beneficiary_ifsc_code(self):
        return self.beneficiary_ifsc

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.payroll_record and self.final_settlement:
            raise ValidationError("DisbursementItem cannot reference both PayrollRecord and FinalSettlement.")
        if not self.payroll_record and not self.final_settlement:
            raise ValidationError("DisbursementItem must reference either PayrollRecord or FinalSettlement.")
        if self.payroll_record and self.payroll_record.employee != self.employee:
            raise ValidationError("DisbursementItem employee must match PayrollRecord employee.")
        if self.final_settlement and self.final_settlement.employee != self.employee:
            raise ValidationError("DisbursementItem employee must match FinalSettlement employee.")
        if self.batch.organization_id != self.employee.organization_id:
            raise ValidationError("DisbursementItem employee organization must match batch organization.")
        if self.payroll_record and self.batch.period and self.payroll_record.period != self.batch.period:
            raise ValidationError("DisbursementItem PayrollRecord period must match batch period.")
        if self.final_settlement and self.batch.final_settlement and self.final_settlement != self.batch.final_settlement:
            raise ValidationError("DisbursementItem FinalSettlement must match batch FinalSettlement.")
        if self.pk and self.batch.status in [DisbursementBatch.STATUS_APPROVED, DisbursementBatch.STATUS_EXPORTED]:
            orig = DisbursementItem.objects.filter(pk=self.pk).values('amount', 'beneficiary_account_number', 'payment_mode').first()
            if orig and (
                self.amount != orig['amount']
                or self.beneficiary_account_number != orig['beneficiary_account_number']
                or self.payment_mode != orig['payment_mode']
            ):
                raise ValidationError("Cannot modify items of an approved or exported disbursement batch.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class FnFPolicyConfiguration(models.Model):
    """
    Organization-scoped, effective-dated policy configuration for Full & Final Settlement (FnF).
    Avoids hardcoding legal, statutory, notice, leave encashment, and gratuity policies.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='fnf_policy_configs',
    )
    branch = models.ForeignKey(
        'organization.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fnf_policy_configs',
        help_text="Optional branch-specific override.",
    )
    effective_from = models.DateField(
        help_text="Date from which this configuration becomes active.",
    )
    is_active = models.BooleanField(default=True)

    # Leave Encashment Policy
    leave_encashment_enabled = models.BooleanField(default=True)
    leave_encashment_daily_divisor = models.PositiveSmallIntegerField(
        default=30,
        help_text="Divisor used to calculate per-day salary for leave encashment (e.g. 30, 26).",
    )
    leave_encashment_salary_basis = models.CharField(
        max_length=20,
        choices=[('basic', 'Basic Salary'), ('gross', 'Gross Salary')],
        default='basic',
    )
    encashable_leave_types = models.JSONField(
        default=list,
        blank=True,
        help_text="List of eligible leave type codes or names, e.g. ['EL', 'PL', 'Earned Leave'].",
    )

    # Gratuity Policy
    gratuity_enabled = models.BooleanField(default=False)
    gratuity_min_service_years = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=Decimal('5.0'),
        help_text="Minimum service tenure (in years) required for gratuity eligibility.",
    )
    gratuity_wage_days_per_year = models.PositiveSmallIntegerField(
        default=15,
        help_text="Wage days credited per completed year of service (e.g. 15).",
    )
    gratuity_divisor = models.PositiveSmallIntegerField(
        default=26,
        help_text="Divisor per month (e.g. 26).",
    )
    gratuity_max_ceiling = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum statutory ceiling for gratuity (e.g. 2000000.00).",
    )

    # Notice Shortfall Recovery Policy
    notice_recovery_enabled = models.BooleanField(default=True)
    notice_recovery_daily_divisor = models.PositiveSmallIntegerField(
        default=30,
        help_text="Divisor used to calculate per-day salary for notice shortfall recovery.",
    )
    notice_recovery_salary_basis = models.CharField(
        max_length=20,
        choices=[('basic', 'Basic Salary'), ('gross', 'Gross Salary')],
        default='basic',
    )

    # Bonus & Clawback Policies
    bonus_enabled = models.BooleanField(default=False)
    joining_bonus_clawback_enabled = models.BooleanField(default=False)
    clawback_threshold_months = models.PositiveSmallIntegerField(
        default=12,
        help_text="Tenure threshold in months under which joining bonus clawback triggers.",
    )

    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-effective_from', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'branch', 'effective_from'],
                name='unique_org_branch_effective_fnf_config',
            ),
        ]

    def __str__(self):
        return f"{self.organization.name} FnF Policy (Effective {self.effective_from})"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.leave_encashment_daily_divisor <= 0:
            raise ValidationError({'leave_encashment_daily_divisor': 'Divisor must be greater than zero.'})
        if self.notice_recovery_daily_divisor <= 0:
            raise ValidationError({'notice_recovery_daily_divisor': 'Divisor must be greater than zero.'})
        if self.gratuity_divisor <= 0:
            raise ValidationError({'gratuity_divisor': 'Divisor must be greater than zero.'})
        if self.branch_id and self.branch.organization_id != self.organization_id:
            raise ValidationError({'branch': 'Branch must belong to the same organization.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class FinalSettlement(models.Model):
    """
    Normalized Full & Final Settlement (FnF) record for an exiting employee.
    Maintains complete auditability, maker-checker status, and immutable financial snapshots.
    """
    STATUS_DRAFT = 'draft'
    STATUS_REVIEW = 'review'
    STATUS_APPROVED = 'approved'
    STATUS_FINALIZED = 'finalized'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_REVIEW, 'Under Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_FINALIZED, 'Finalized'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='final_settlements',
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='final_settlements',
    )
    resignation_event = models.ForeignKey(
        'employees.EmployeeLifecycleEvent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='final_settlements',
    )
    settlement_number = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Format: FNF-YYYYMM-EMPLOYEE_CODE",
    )
    exit_date = models.DateField(
        help_text="Authoritative last working day",
    )
    resignation_date = models.DateField(
        null=True,
        blank=True,
    )
    settlement_date = models.DateField(
        default=timezone.now,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    total_earnings = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    total_deductions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    total_recoveries = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    net_settlement_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    currency = models.CharField(
        max_length=10,
        default='INR',
    )
    remarks = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)

    # --- Maker-Checker & Timestamps ---
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_final_settlements',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_final_settlements',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    finalized_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finalized_final_settlements',
    )
    finalized_at = models.DateTimeField(null=True, blank=True)

    # --- Immutable Snapshot & Integrity ---
    snapshot_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Immutable financial, employee, attendance, and policy snapshot.",
    )
    integrity_hash = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="Deterministic SHA-256 integrity hash of finalized settlement.",
    )

    class Meta:
        ordering = ['-settlement_date', '-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['settlement_number']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'employee'],
                condition=~models.Q(status='cancelled'),
                name='unique_active_fnf_per_employee',
            ),
        ]

    @property
    def net_payable(self):
        return self.net_settlement_amount

    def __str__(self):
        return f"{self.settlement_number} — {self.employee.employee_code} ({self.status})"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.pk:
            orig = FinalSettlement.objects.filter(pk=self.pk).values(
                'status', 'total_earnings', 'total_deductions', 'total_recoveries',
                'net_settlement_amount', 'integrity_hash', 'exit_date'
            ).first()
            if orig and orig['status'] == FinalSettlement.STATUS_FINALIZED:
                if (
                    self.total_earnings != orig['total_earnings']
                    or self.total_deductions != orig['total_deductions']
                    or self.total_recoveries != orig['total_recoveries']
                    or self.net_settlement_amount != orig['net_settlement_amount']
                    or self.integrity_hash != orig['integrity_hash']
                    or self.exit_date != orig['exit_date']
                ):
                    raise ValidationError("Finalized FnF settlements are strictly immutable.")

    def delete(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        if self.status == self.STATUS_FINALIZED:
            raise ValidationError("Finalized FnF settlements cannot be deleted.")
        return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class SettlementLine(models.Model):
    """
    Normalized line item within a FinalSettlement representing earnings, deductions,
    or recovery items.
    """
    CATEGORY_EARNING = 'earning'
    CATEGORY_DEDUCTION = 'deduction'
    CATEGORY_RECOVERY = 'recovery'
    CATEGORY_CHOICES = [
        (CATEGORY_EARNING, 'Earning'),
        (CATEGORY_DEDUCTION, 'Deduction'),
        (CATEGORY_RECOVERY, 'Recovery'),
    ]

    settlement = models.ForeignKey(
        FinalSettlement,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
    )
    code = models.CharField(
        max_length=64,
        help_text="Canonical code, e.g. SALARY_LWD, LEAVE_ENCASHMENT, GRATUITY, NOTICE_RECOVERY, ASSET_RECOVERY, etc.",
    )
    name = models.CharField(
        max_length=150,
        help_text="Human-readable title",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    calculation_basis = models.TextField(
        blank=True,
        help_text="Human-readable formula or explanation of how the amount was calculated.",
    )
    source_reference = models.CharField(
        max_length=150,
        blank=True,
        help_text="Reference identifier (e.g. Asset tag, Leave type code, etc.).",
    )
    order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['settlement', 'category']),
        ]

    def __str__(self):
        return f"{self.settlement.settlement_number} - {self.name}: ₹{self.amount} ({self.category})"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.pk and self.settlement.status == FinalSettlement.STATUS_FINALIZED:
            raise ValidationError("Cannot modify lines of a finalized FnF settlement.")

    def delete(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        if self.settlement.status == FinalSettlement.STATUS_FINALIZED:
            raise ValidationError("Cannot delete lines of a finalized FnF settlement.")
        return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


# =============================================================================
# TAX DECLARATION & INVESTMENT PROOF FOUNDATION (Phase 6.9A)
# =============================================================================

class FinancialYear(models.Model):
    """
    Authoritative representation of a Financial / Fiscal Year for an organization.
    e.g. 'FY 2024-25' (start_date: 2024-04-01, end_date: 2025-03-31).
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='financial_years',
    )
    name = models.CharField(max_length=32, help_text="e.g. FY 2024-25 or 2024-2025")
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    is_locked = models.BooleanField(
        default=False,
        help_text="Locked financial years prevent new declarations or modifications."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'name')
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError({'end_date': "Financial year end date must be after start date."})


class TaxDeclarationCategory(models.Model):
    """
    Configurable tax deduction / exemption category with effective-dated limits.
    Prevents hardcoding statutory limits into model methods.
    """
    REGIME_OLD = 'OLD'
    REGIME_NEW = 'NEW'
    REGIME_BOTH = 'BOTH'
    REGIME_APPLICABILITY_CHOICES = [
        (REGIME_OLD, 'Old Regime Only'),
        (REGIME_NEW, 'New Regime Only'),
        (REGIME_BOTH, 'Both Regimes'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='tax_declaration_categories',
    )
    code = models.CharField(max_length=32, help_text="e.g. 80C, 80D, 80G, 80CCD_1B, HRA, HOME_LOAN_INTEREST")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    max_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Configurable statutory ceiling (e.g. 150000.00 for 80C). Null indicates no fixed cap."
    )
    regime_applicability = models.CharField(
        max_length=10,
        choices=REGIME_APPLICABILITY_CHOICES,
        default=REGIME_OLD,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'code')
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class TaxDeclaration(models.Model):
    """
    Employee tax regime selection and declaration for a specific financial year.
    Normalized parent record governing Section 80C/80D/HRA investment declaration items.
    """
    REGIME_OLD = 'OLD'
    REGIME_NEW = 'NEW'
    REGIME_CHOICES = [
        (REGIME_OLD, 'Old Tax Regime'),
        (REGIME_NEW, 'New Tax Regime'),
    ]

    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_UNDER_REVIEW = 'under_review'
    STATUS_VERIFIED = 'verified'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_UNDER_REVIEW, 'Under Review'),
        (STATUS_VERIFIED, 'Verified'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='tax_declarations',
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='tax_declarations',
    )
    financial_year = models.ForeignKey(
        FinancialYear,
        on_delete=models.PROTECT,
        related_name='declarations',
    )
    tax_regime = models.CharField(
        max_length=10,
        choices=REGIME_CHOICES,
        default=REGIME_NEW,
        help_text="Elected tax regime for this financial year.",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    total_declared_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    total_verified_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    submission_date = models.DateTimeField(null=True, blank=True)
    verification_date = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_tax_declarations',
    )
    rejection_reason = models.TextField(blank=True)
    snapshot_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Immutable snapshot of approved regime, items, and totals at verification time."
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'employee', 'financial_year')
        ordering = ['-financial_year__start_date', '-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['employee', 'financial_year']),
        ]

    def __str__(self):
        return f"{self.employee.employee_code} - {self.financial_year.name} ({self.tax_regime}) [{self.status}]"

    def update_totals(self):
        """Recompute sum of declared and verified amounts across all child items."""
        from django.db.models import Sum
        sums = self.items.aggregate(
            total_dec=Sum('declared_amount'),
            total_ver=Sum('verified_amount'),
        )
        self.total_declared_amount = sums['total_dec'] or Decimal('0.00')
        self.total_verified_amount = sums['total_ver'] or Decimal('0.00')
        self.save(update_fields=['total_declared_amount', 'total_verified_amount', 'updated_at'])


class InvestmentDeclaration(models.Model):
    """
    Normalized itemized investment declaration entry (e.g. 80C, 80D, HRA rent, Home Loan).
    """
    STATUS_PENDING = 'pending'
    STATUS_VERIFIED = 'verified'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_VERIFIED, 'Verified'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    declaration = models.ForeignKey(
        TaxDeclaration,
        on_delete=models.CASCADE,
        related_name='items',
    )
    category = models.ForeignKey(
        TaxDeclarationCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='declaration_items',
    )
    category_code = models.CharField(
        max_length=32,
        help_text="Denormalized category code e.g. 80C, 80D, HRA",
    )
    description = models.CharField(max_length=255)
    declared_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    verified_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    rejection_reason = models.TextField(blank=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured attributes such as landlord_name, landlord_pan, policy_number, etc.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category_code', 'id']
        indexes = [
            models.Index(fields=['declaration', 'category_code']),
        ]

    def __str__(self):
        return f"{self.declaration.employee.employee_code} - {self.category_code}: ₹{self.declared_amount}"


def tax_proof_upload_path(instance, filename):
    """
    Store files securely under employee_documents/<employee_id>/<uuid>.<ext>
    Reuses existing storage vault conventions.
    """
    import os
    ext = os.path.splitext(filename)[-1].lower()
    new_filename = f"{uuid.uuid4()}{ext}"
    employee_id = instance.declaration_item.declaration.employee_id
    return os.path.join('employee_documents', str(employee_id), new_filename)


class InvestmentProof(models.Model):
    """
    Verification document attached to an investment declaration item.
    Reuses existing EmployeeDocument infrastructure and storage vault.
    """
    STATUS_SUBMITTED = 'submitted'
    STATUS_UNDER_REVIEW = 'under_review'
    STATUS_VERIFIED = 'verified'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_UNDER_REVIEW, 'Under Review'),
        (STATUS_VERIFIED, 'Verified'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    declaration_item = models.ForeignKey(
        InvestmentDeclaration,
        on_delete=models.CASCADE,
        related_name='proofs',
    )
    employee_document = models.ForeignKey(
        'employees.EmployeeDocument',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tax_proofs',
        help_text="Reference to existing vault EmployeeDocument if bridged.",
    )
    file = models.FileField(upload_to=tax_proof_upload_path)
    proof_type = models.CharField(max_length=50, default='DOCUMENT')
    document_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SUBMITTED,
    )
    rejection_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['declaration_item', 'status']),
        ]

    def __str__(self):
        return f"Proof for {self.declaration_item} - {self.document_name} ({self.status})"


# =============================================================================
# TAX RULE CONFIGURATION & PROGRESSIVE TDS ENGINE (Phase 6.9C)
# =============================================================================

class TaxRuleConfiguration(models.Model):
    """
    Versioned, effective-dated tax rule configuration for an organization.
    Governs slabs, standard deductions, Section 87A rebate thresholds, cess, and surcharge
    for a specific Financial Year and Tax Regime (OLD / NEW).
    """
    REGIME_OLD = 'OLD'
    REGIME_NEW = 'NEW'
    REGIME_CHOICES = [
        (REGIME_OLD, 'Old Tax Regime'),
        (REGIME_NEW, 'New Tax Regime'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='tax_rule_configurations',
    )
    financial_year = models.ForeignKey(
        FinancialYear,
        on_delete=models.PROTECT,
        related_name='tax_rule_configurations',
    )
    regime = models.CharField(max_length=10, choices=REGIME_CHOICES)
    version_identifier = models.CharField(
        max_length=64,
        help_text="e.g. FY2024-25-NEW-v1.0 or FY2024-25-OLD-v1.0"
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    standard_deduction = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Standard deduction applicable under this rule version."
    )
    rebate_income_threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Max taxable income eligible for Section 87A rebate."
    )
    max_rebate_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Maximum relief amount under Section 87A rebate."
    )
    cess_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.0000'))],
        help_text="Configured Health & Education cess rate (e.g. 0.0400 for 4%). Must be explicitly specified."
    )
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'financial_year', 'regime', 'version_identifier')
        ordering = ['-effective_from', '-created_at']
        indexes = [
            models.Index(fields=['organization', 'financial_year', 'regime', 'is_active']),
            models.Index(fields=['effective_from', 'effective_to']),
        ]

    def __str__(self):
        return f"{self.financial_year.name} [{self.regime}] - {self.version_identifier} ({self.organization.name})"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.cess_rate is None:
            raise ValidationError({
                'cess_rate': "Cess rate must be explicitly configured."
            })
        if self.financial_year_id and self.organization_id:
            if self.financial_year.organization_id != self.organization_id:
                raise ValidationError({
                    'financial_year': "Financial year does not belong to the same organization."
                })
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({
                'effective_to': "Effective to date cannot be earlier than effective from date."
            })

    def validate_slabs(self):
        """
        Validates completeness, continuity, and sanity of slabs:
        1. Must have at least one slab.
        2. First slab lower_limit must be 0.00.
        3. Subsequent slabs must start exactly where previous slab ends.
        4. Rates must be non-negative and <= 1.0.
        5. Only the final slab may have upper_limit == None.
        """
        from django.core.exceptions import ValidationError
        slabs = list(self.slabs.order_by('slab_order'))
        if not slabs:
            raise ValidationError("Tax rule configuration must define at least one tax slab.")

        for i, slab in enumerate(slabs):
            if slab.rate < Decimal('0.0000') or slab.rate > Decimal('1.0000'):
                raise ValidationError(f"Slab {slab.slab_order} has invalid tax rate {slab.rate}.")
            if i == 0:
                if slab.lower_limit != Decimal('0.00'):
                    raise ValidationError(f"First slab must have lower_limit of 0.00, got {slab.lower_limit}.")
            else:
                prev = slabs[i - 1]
                if prev.upper_limit is None:
                    raise ValidationError(f"Slab {prev.slab_order} is open-ended but followed by slab {slab.slab_order}.")
                if slab.lower_limit != prev.upper_limit:
                    raise ValidationError(
                        f"Discontinuity between slab {prev.slab_order} (upper: {prev.upper_limit}) "
                        f"and slab {slab.slab_order} (lower: {slab.lower_limit})."
                    )

            if slab.upper_limit is not None and slab.upper_limit <= slab.lower_limit:
                raise ValidationError(
                    f"Slab {slab.slab_order} upper_limit ({slab.upper_limit}) must be greater than lower_limit ({slab.lower_limit})."
                )

            if i < len(slabs) - 1 and slab.upper_limit is None:
                raise ValidationError(f"Only the last slab may have an open-ended upper limit.")


class TaxSlab(models.Model):
    """
    Individual income bracket and rate under a TaxRuleConfiguration.
    """
    rule_configuration = models.ForeignKey(
        TaxRuleConfiguration,
        on_delete=models.CASCADE,
        related_name='slabs',
    )
    slab_order = models.PositiveSmallIntegerField()
    lower_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    upper_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Null represents infinity / no upper ceiling."
    )
    rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.0000'))],
        help_text="Tax rate as a decimal fraction (e.g. 0.0500 for 5%)."
    )

    class Meta:
        ordering = ['slab_order']
        unique_together = ('rule_configuration', 'slab_order')

    def __str__(self):
        upper_str = f"₹{self.upper_limit}" if self.upper_limit is not None else "Above"
        return f"Slab {self.slab_order}: ₹{self.lower_limit} - {upper_str} @ {self.rate * 100}%"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.upper_limit is not None and self.upper_limit <= self.lower_limit:
            raise ValidationError({'upper_limit': "Upper limit must be strictly greater than lower limit."})
        if self.rate < Decimal('0.0000') or self.rate > Decimal('1.0000'):
            raise ValidationError({'rate': "Tax rate must be between 0.0000 and 1.0000."})


class TaxSurchargeSlab(models.Model):
    """
    Surcharge tiers applied to high-income earners.
    """
    rule_configuration = models.ForeignKey(
        TaxRuleConfiguration,
        on_delete=models.CASCADE,
        related_name='surcharge_slabs',
    )
    slab_order = models.PositiveSmallIntegerField()
    threshold_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Taxable income threshold above which this surcharge rate applies."
    )
    rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.0000'))],
        help_text="Surcharge rate (e.g. 0.1000 for 10%)."
    )

    class Meta:
        ordering = ['slab_order']
        unique_together = ('rule_configuration', 'slab_order')

    def __str__(self):
        return f"Surcharge {self.slab_order}: Above ₹{self.threshold_amount} @ {self.rate * 100}%"


class TaxRuleDeductionApplicability(models.Model):
    """
    Maps declaration categories (e.g. 80C, 80D, HRA) to a TaxRuleConfiguration,
    defining whether the deduction is allowed under this regime version and any rule-specific caps.
    """
    rule_configuration = models.ForeignKey(
        TaxRuleConfiguration,
        on_delete=models.CASCADE,
        related_name='deduction_rules',
    )
    category_code = models.CharField(
        max_length=32,
        help_text="Matches TaxDeclarationCategory.code (e.g. 80C, 80D, HRA)."
    )
    is_allowed = models.BooleanField(
        default=True,
        help_text="If False, deduction is completely disallowed in this regime version."
    )
    max_deductible_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Ceiling override for this regime. If null, TaxDeclarationCategory.max_limit is used."
    )

    class Meta:
        unique_together = ('rule_configuration', 'category_code')
        ordering = ['category_code']

    def __str__(self):
        status = "Allowed" if self.is_allowed else "Disallowed"
        cap = f" (Cap: ₹{self.max_deductible_limit})" if self.max_deductible_limit else ""
        return f"{self.category_code} in {self.rule_configuration.version_identifier}: {status}{cap}"



