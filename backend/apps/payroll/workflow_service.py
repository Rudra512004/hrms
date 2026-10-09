from django.db import transaction
from django.utils import timezone
from typing import Dict, List, Any
import logging

from apps.payroll.models import PayrollPeriod, PayrollRecord
from apps.employees.models import Employee, EmploymentStatus
from apps.audit.services import AuditService

logger = logging.getLogger(__name__)

class PayrollWorkflowException(Exception):
    pass

class PayrollWorkflowService:
    """
    Manages the lifecycle of a PayrollPeriod:
    DRAFT -> LOCKED -> PROCESSING -> REVIEW -> FINALIZED -> DISBURSED
    """
    
    @staticmethod
    @transaction.atomic
    def lock_period(period: PayrollPeriod, user) -> Dict[str, Any]:
        """
        Transition DRAFT -> LOCKED.
        Runs reconciliation. If blockers exist, raises exception.
        """
        if period.status != PayrollPeriod.STATUS_DRAFT:
            raise PayrollWorkflowException(f"Cannot lock period in state {period.status}")
            
        recon_result = PayrollWorkflowService.reconcile_period(period)
        if not recon_result['can_lock']:
            raise PayrollWorkflowException("Cannot lock due to unresolved blockers.")
            
        period.status = PayrollPeriod.STATUS_LOCKED
        period.save(update_fields=['status', 'updated_at'])
        
        AuditService.log(
            action="PAYROLL_LOCKED",
            actor=user,
            target_type="PayrollPeriod",
            target_id=period.id,
            organization=period.organization
        )
        
        return recon_result
        
    @staticmethod
    def reconcile_period(period: PayrollPeriod) -> Dict[str, Any]:
        """
        Step 1: Lock & Reconcile.
        Detects blockers and warnings.
        """
        blockers = []
        warnings = []
        
        employees = Employee.objects.filter(
            organization=period.organization,
            employment_status__in=[EmploymentStatus.ACTIVE, EmploymentStatus.ON_NOTICE]
        )
        # Include those who exited during the period
        from django.db.models import Q
        employees = employees.filter(
            Q(exit_date__isnull=True) | Q(exit_date__gte=period.start_date)
        ).select_related('branch')

        # Check configurations at the organization level
        from apps.payroll.models import EPFConfiguration, ESICConfiguration, PTConfiguration, LWFConfiguration
        
        has_epf = EPFConfiguration.objects.filter(
            organization=period.organization,
            effective_from__lte=period.end_date
        ).exists()
        
        has_esic = ESICConfiguration.objects.filter(
            organization=period.organization,
            effective_from__lte=period.end_date
        ).exists()

        if not has_epf:
            blockers.append({
                'employee': None,
                'category': 'configuration',
                'code': 'MISSING_EPF_CONFIG',
                'message': 'No valid EPF configuration found for this period.',
                'severity': 'BLOCKER'
            })
            
        if not has_esic:
            blockers.append({
                'employee': None,
                'category': 'configuration',
                'code': 'MISSING_ESIC_CONFIG',
                'message': 'No valid ESIC configuration found for this period.',
                'severity': 'BLOCKER'
            })
        
        for emp in employees:
            # Check Salary Assignment
            comp_records = emp.compensation_history.filter(
                effective_from__lte=period.end_date
            ).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=period.start_date)
            )
            
            if not comp_records.exists():
                blockers.append({
                    'employee': emp.employee_code,
                    'category': 'salary_assignment',
                    'code': 'MISSING_SALARY_ASSIGNMENT',
                    'message': f'Employee {emp.employee_code} has no active salary assignment for this period.',
                    'severity': 'BLOCKER'
                })
                
            # Pending attendance/leave (Checking logically)
            from apps.leaves.models import LeaveRequest
            pending_leaves = LeaveRequest.objects.filter(
                employee=emp, 
                status='pending',
                start_date__lte=period.end_date,
                end_date__gte=period.start_date
            ).exists()
            
            if pending_leaves:
                blockers.append({
                    'employee': emp.employee_code,
                    'category': 'leave',
                    'code': 'PENDING_LEAVE',
                    'message': f'Employee {emp.employee_code} has pending leave requests.',
                    'severity': 'BLOCKER'
                })
                
            # Bank Details
            if not hasattr(emp, 'statutory_and_bank') or not emp.statutory_and_bank.bank_account_number:
                warnings.append({
                    'employee': emp.employee_code,
                    'category': 'bank_details',
                    'code': 'MISSING_BANK_ACCOUNT',
                    'message': f'Employee {emp.employee_code} is missing bank account details.',
                    'severity': 'WARNING'
                })

            # New Joiners / Exits
            if emp.joining_date and period.start_date <= emp.joining_date <= period.end_date:
                warnings.append({
                    'employee': emp.employee_code,
                    'category': 'lifecycle',
                    'code': 'NEW_JOINER',
                    'message': f'Employee {emp.employee_code} joined during this period.',
                    'severity': 'WARNING'
                })
                
            if emp.exit_date and period.start_date <= emp.exit_date <= period.end_date:
                warnings.append({
                    'employee': emp.employee_code,
                    'category': 'lifecycle',
                    'code': 'EXIT_EMPLOYEE',
                    'message': f'Employee {emp.employee_code} exited during this period.',
                    'severity': 'WARNING'
                })
                
        return {
            'can_lock': len(blockers) == 0,
            'blockers': blockers,
            'warnings': warnings,
            'employee_count': employees.count(),
            'eligible_employee_count': employees.count() - len(set([b['employee'] for b in blockers]))
        }

    @staticmethod
    def process_period(period: PayrollPeriod, user) -> None:
        """
        Transition LOCKED -> PROCESSING -> REVIEW.
        """
        if period.status != PayrollPeriod.STATUS_LOCKED:
            raise PayrollWorkflowException(f"Cannot process period in state {period.status}")
            
        with transaction.atomic():
            period.status = PayrollPeriod.STATUS_PROCESSING
            period.save(update_fields=['status', 'updated_at'])
            
            from apps.payroll.services import generate_payroll_for_period
            
            try:
                generate_payroll_for_period(period, requesting_user=user)
                
                period.status = PayrollPeriod.STATUS_REVIEW
                period.generated_at = timezone.now()
                period.save(update_fields=['status', 'generated_at', 'updated_at'])
                
                AuditService.log(
                    action="PAYROLL_PROCESSED",
                    actor=user,
                    target_type="PayrollPeriod",
                    target_id=period.id,
                    organization=period.organization
                )
            except Exception as e:
                # Fallback to LOCKED if processing failed
                period.status = PayrollPeriod.STATUS_LOCKED
                period.save(update_fields=['status'])
                logger.error(f"Payroll processing failed: {str(e)}")
                raise PayrollWorkflowException(f"Payroll processing failed: {str(e)}")

    @staticmethod
    def run_variance_audit(period: PayrollPeriod) -> Dict[str, Any]:
        """
        Step 3: Variance Audit & Approve.
        Compares with previous finalized payroll.
        """
        if period.status != PayrollPeriod.STATUS_REVIEW:
            raise PayrollWorkflowException("Variance audit is only available in REVIEW state.")
            
        anomalies = []
        
        records = period.records.all().select_related('employee')
        for record in records:
            # Check Zero Pay
            if record.net_salary == 0:
                anomalies.append({
                    'employee': record.employee.employee_code,
                    'category': 'variance',
                    'code': 'ZERO_PAY',
                    'message': f'Employee {record.employee.employee_code} has zero net pay.',
                    'severity': 'WARNING'
                })
                
            # Previous comparison
            prev_record = PayrollRecord.objects.filter(
                employee=record.employee,
                period__status__in=[PayrollPeriod.STATUS_FINALIZED, PayrollPeriod.STATUS_DISBURSED],
                period__start_date__lt=period.start_date
            ).order_by('-period__start_date').first()
            
            if prev_record:
                if prev_record.net_salary > 0:
                    net_variance = abs(record.net_salary - prev_record.net_salary)
                    percentage = (net_variance / prev_record.net_salary) * 100
                    
                    if percentage > 15: # Configurable threshold, defaulting to 15% here temporarily
                        anomalies.append({
                            'employee': record.employee.employee_code,
                            'category': 'variance',
                            'code': 'HIGH_VARIANCE',
                            'message': f'Employee {record.employee.employee_code} has {percentage:.2f}% net pay variance.',
                            'severity': 'WARNING'
                        })
                        
        return {
            'anomalies': anomalies
        }
        
    @staticmethod
    @transaction.atomic
    def finalize_period(period: PayrollPeriod, user) -> None:
        """
        Transition REVIEW -> FINALIZED.
        """
        if period.status != PayrollPeriod.STATUS_REVIEW:
            raise PayrollWorkflowException(f"Cannot finalize period in state {period.status}")
            

        period.status = PayrollPeriod.STATUS_FINALIZED
        period.approved_at = timezone.now()
        period.approved_by = user
        period.save(update_fields=['status', 'approved_at', 'approved_by', 'updated_at'])
        
        period.records.update(status=PayrollRecord.STATUS_FINALIZED)
        
        AuditService.log(
            action="PAYROLL_FINALIZED",
            actor=user,
            target_type="PayrollPeriod",
            target_id=period.id,
            organization=period.organization
        )

    @staticmethod
    @transaction.atomic
    def disburse_period(period: PayrollPeriod, user) -> None:
        """
        Transition FINALIZED -> DISBURSED.
        """
        if period.status != PayrollPeriod.STATUS_FINALIZED:
            raise PayrollWorkflowException(f"Cannot disburse period in state {period.status}")
            
        period.status = PayrollPeriod.STATUS_DISBURSED
        period.save(update_fields=['status', 'updated_at'])
        
        # Payslip generation/publication belongs to a later Phase 6.x implementation.
        
        AuditService.log(
            action="PAYROLL_DISBURSED",
            actor=user,
            target_type="PayrollPeriod",
            target_id=period.id,
            organization=period.organization
        )
