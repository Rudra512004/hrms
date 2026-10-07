from decimal import Decimal
from typing import List, Dict, Any

from .models import PayrollRun, PayrollRecord

class PayrollValidationIssue:
    SEVERITY_INFO = 'INFO'
    SEVERITY_WARNING = 'WARNING'
    SEVERITY_BLOCKING = 'BLOCKING'

    def __init__(self, run_id: int, employee_id: int, code: str, severity: str, message: str, evidence: Dict[str, Any] = None):
        self.run_id = run_id
        self.employee_id = employee_id
        self.code = code
        self.severity = severity
        self.message = message
        self.evidence = evidence or {}

    def as_dict(self):
        return {
            'run_id': self.run_id,
            'employee_id': self.employee_id,
            'code': self.code,
            'severity': self.severity,
            'message': self.message,
            'evidence': self.evidence,
        }

class PayrollValidator:
    def __init__(self, run: PayrollRun):
        self.run = run
        self.issues = []

    def validate(self) -> List[PayrollValidationIssue]:
        self.issues = []
        records = self.run.records.select_related('employee').prefetch_related('line_items')
        
        for record in records:
            self._validate_record(record)
            
        return self.issues

    def _validate_record(self, record: PayrollRecord):
        # A. Completeness
        legacy_lines = [li for li in record.line_items.all() if li.calculation_type == 'LEGACY_RECONSTRUCTED']
        if legacy_lines:
            self.issues.append(PayrollValidationIssue(
                run_id=self.run.id,
                employee_id=record.employee_id,
                code='MISSING_SALARY_STRUCTURE',
                severity=PayrollValidationIssue.SEVERITY_WARNING,
                message=f"Employee has no active salary structure. Using legacy gross fallback.",
                evidence={'legacy_gross': str(record.basic_salary)}
            ))

        if record.working_days > 0 and record.present_days == 0 and record.leave_days == 0 and record.absent_days == record.working_days:
            self.issues.append(PayrollValidationIssue(
                run_id=self.run.id,
                employee_id=record.employee_id,
                code='MISSING_ATTENDANCE',
                severity=PayrollValidationIssue.SEVERITY_WARNING,
                message=f"Employee has no attendance or leave records for the entire period.",
                evidence={'working_days': record.working_days}
            ))
            
        # B. Attendance / LOP
        if record.lop_days > Decimal('5.0'):
            self.issues.append(PayrollValidationIssue(
                run_id=self.run.id,
                employee_id=record.employee_id,
                code='ABNORMAL_LOP',
                severity=PayrollValidationIssue.SEVERITY_WARNING,
                message=f"High Loss of Pay ({record.lop_days} days).",
                evidence={'lop_days': str(record.lop_days)}
            ))
            
        if record.net_salary < Decimal('0'):
            self.issues.append(PayrollValidationIssue(
                run_id=self.run.id,
                employee_id=record.employee_id,
                code='NEGATIVE_NET_PAY',
                severity=PayrollValidationIssue.SEVERITY_BLOCKING,
                message=f"Net salary cannot be negative.",
                evidence={'net_salary': str(record.net_salary)}
            ))
            
        # C. Integrity
        if not record.line_items.all() and record.gross_salary > Decimal('0'):
            self.issues.append(PayrollValidationIssue(
                run_id=self.run.id,
                employee_id=record.employee_id,
                code='MISSING_LINE_ITEMS',
                severity=PayrollValidationIssue.SEVERITY_BLOCKING,
                message=f"Payroll record has no line items but has gross salary.",
                evidence={'gross_salary': str(record.gross_salary)}
            ))
