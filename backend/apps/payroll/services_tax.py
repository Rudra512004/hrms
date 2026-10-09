from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from typing import Optional, Dict, Any, List
import logging

from apps.payroll.models import (
    FinancialYear,
    TaxDeclarationCategory,
    TaxDeclaration,
    InvestmentDeclaration,
    InvestmentProof,
)
from apps.employees.models import Employee, EmployeeDocument, DocumentType, DocumentStatus
from apps.audit.services import AuditService

logger = logging.getLogger(__name__)


class TaxDeclarationException(Exception):
    def __init__(self, message: str, code: str = 'TAX_DECLARATION_ERROR'):
        super().__init__(message)
        self.message = message
        self.code = code


class TaxDeclarationService:
    """
    Authoritative service governing employee tax declarations, investment items,
    proof uploads, reviewer workflows, and downstream calculation inputs.
    """

    @staticmethod
    @transaction.atomic
    def create_declaration(
        employee: Employee,
        financial_year: FinancialYear,
        tax_regime: str = TaxDeclaration.REGIME_NEW,
        notes: str = '',
        requesting_user=None,
    ) -> TaxDeclaration:
        """Create a new draft tax declaration for an employee and financial year."""
        if financial_year.is_locked:
            raise TaxDeclarationException(
                f"Financial year '{financial_year.name}' is locked for new declarations.",
                code='FINANCIAL_YEAR_LOCKED',
            )

        if not financial_year.is_active:
            raise TaxDeclarationException(
                f"Financial year '{financial_year.name}' is inactive.",
                code='FINANCIAL_YEAR_INACTIVE',
            )

        if financial_year.organization_id != employee.organization_id:
            raise TaxDeclarationException(
                "Financial year does not belong to the employee's organization.",
                code='CROSS_ORGANIZATION_FORBIDDEN',
            )

        if TaxDeclaration.objects.filter(
            organization=employee.organization,
            employee=employee,
            financial_year=financial_year,
        ).exists():
            raise TaxDeclarationException(
                f"A tax declaration already exists for {employee.employee_code} in {financial_year.name}.",
                code='DUPLICATE_DECLARATION',
            )

        if tax_regime not in [TaxDeclaration.REGIME_OLD, TaxDeclaration.REGIME_NEW]:
            raise TaxDeclarationException(
                f"Invalid tax regime '{tax_regime}'. Must be 'OLD' or 'NEW'.",
                code='INVALID_TAX_REGIME',
            )

        declaration = TaxDeclaration.objects.create(
            organization=employee.organization,
            employee=employee,
            financial_year=financial_year,
            tax_regime=tax_regime,
            notes=notes,
            status=TaxDeclaration.STATUS_DRAFT,
            total_declared_amount=Decimal('0.00'),
            total_verified_amount=Decimal('0.00'),
        )

        AuditService.log(
            action='TAX_DECLARATION_CREATED',
            actor=requesting_user,
            target_type='TaxDeclaration',
            target_id=declaration.id,
            organization=employee.organization,
            metadata={
                'employee_code': employee.employee_code,
                'financial_year': financial_year.name,
                'tax_regime': tax_regime,
            },
        )

        return declaration

    @staticmethod
    @transaction.atomic
    def update_declaration(
        declaration: TaxDeclaration,
        tax_regime: Optional[str] = None,
        notes: Optional[str] = None,
        requesting_user=None,
    ) -> TaxDeclaration:
        """Update draft declaration fields (regime, notes)."""
        if declaration.status not in [TaxDeclaration.STATUS_DRAFT, TaxDeclaration.STATUS_REJECTED]:
            raise TaxDeclarationException(
                f"Cannot modify declaration in state '{declaration.status}'. Only DRAFT or REJECTED declarations may be edited.",
                code='IMMUTABLE_DECLARATION_STATE',
            )

        if declaration.financial_year.is_locked:
            raise TaxDeclarationException(
                "Cannot modify declaration in a locked financial year.",
                code='FINANCIAL_YEAR_LOCKED',
            )

        update_fields = ['updated_at']

        if tax_regime is not None:
            if tax_regime not in [TaxDeclaration.REGIME_OLD, TaxDeclaration.REGIME_NEW]:
                raise TaxDeclarationException(
                    f"Invalid tax regime '{tax_regime}'.",
                    code='INVALID_TAX_REGIME',
                )
            old_regime = declaration.tax_regime
            declaration.tax_regime = tax_regime
            update_fields.append('tax_regime')

            AuditService.log(
                action='TAX_REGIME_CHANGED',
                actor=requesting_user,
                target_type='TaxDeclaration',
                target_id=declaration.id,
                organization=declaration.organization,
                metadata={
                    'previous_regime': old_regime,
                    'new_regime': tax_regime,
                    'financial_year': declaration.financial_year.name,
                },
            )

        if notes is not None:
            declaration.notes = notes
            update_fields.append('notes')

        declaration.save(update_fields=update_fields)
        return declaration

    @staticmethod
    @transaction.atomic
    def add_item(
        declaration: TaxDeclaration,
        category_code: str,
        description: str,
        declared_amount: Decimal,
        metadata: Optional[Dict[str, Any]] = None,
        requesting_user=None,
    ) -> InvestmentDeclaration:
        """Add an itemized investment entry to a draft declaration."""
        if declaration.status not in [TaxDeclaration.STATUS_DRAFT, TaxDeclaration.STATUS_REJECTED]:
            raise TaxDeclarationException(
                f"Cannot add items to declaration in state '{declaration.status}'.",
                code='IMMUTABLE_DECLARATION_STATE',
            )

        if declared_amount <= Decimal('0.00'):
            raise TaxDeclarationException(
                "Declared amount must be greater than zero.",
                code='INVALID_AMOUNT',
            )

        # Lookup category configuration if configured
        category = TaxDeclarationCategory.objects.filter(
            organization=declaration.organization,
            code__iexact=category_code.strip(),
            is_active=True,
        ).first()

        item = InvestmentDeclaration.objects.create(
            declaration=declaration,
            category=category,
            category_code=category.code if category else category_code.strip().upper(),
            description=description.strip(),
            declared_amount=declared_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            metadata=metadata or {},
            status=InvestmentDeclaration.STATUS_PENDING,
        )

        declaration.update_totals()

        AuditService.log(
            action='TAX_INVESTMENT_ITEM_ADDED',
            actor=requesting_user,
            target_type='InvestmentDeclaration',
            target_id=item.id,
            organization=declaration.organization,
            metadata={
                'declaration_id': declaration.id,
                'category_code': item.category_code,
                'declared_amount': str(item.declared_amount),
            },
        )

        return item

    @staticmethod
    @transaction.atomic
    def update_item(
        item: InvestmentDeclaration,
        description: Optional[str] = None,
        declared_amount: Optional[Decimal] = None,
        metadata: Optional[Dict[str, Any]] = None,
        requesting_user=None,
    ) -> InvestmentDeclaration:
        """Update an itemized investment entry."""
        declaration = item.declaration
        if declaration.status not in [TaxDeclaration.STATUS_DRAFT, TaxDeclaration.STATUS_REJECTED]:
            raise TaxDeclarationException(
                f"Cannot update items in declaration with status '{declaration.status}'.",
                code='IMMUTABLE_DECLARATION_STATE',
            )

        update_fields = ['updated_at']

        if description is not None:
            item.description = description.strip()
            update_fields.append('description')

        if declared_amount is not None:
            if declared_amount <= Decimal('0.00'):
                raise TaxDeclarationException(
                    "Declared amount must be greater than zero.",
                    code='INVALID_AMOUNT',
                )
            item.declared_amount = declared_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            update_fields.append('declared_amount')

        if metadata is not None:
            item.metadata = metadata
            update_fields.append('metadata')

        item.save(update_fields=update_fields)
        declaration.update_totals()

        AuditService.log(
            action='TAX_INVESTMENT_ITEM_UPDATED',
            actor=requesting_user,
            target_type='InvestmentDeclaration',
            target_id=item.id,
            organization=declaration.organization,
            metadata={
                'category_code': item.category_code,
                'declared_amount': str(item.declared_amount),
            },
        )

        return item

    @staticmethod
    @transaction.atomic
    def delete_item(item: InvestmentDeclaration, requesting_user=None) -> None:
        """Delete an investment item from a draft declaration."""
        declaration = item.declaration
        if declaration.status not in [TaxDeclaration.STATUS_DRAFT, TaxDeclaration.STATUS_REJECTED]:
            raise TaxDeclarationException(
                f"Cannot delete items from declaration in status '{declaration.status}'.",
                code='IMMUTABLE_DECLARATION_STATE',
            )

        item_id = item.id
        category_code = item.category_code
        item.delete()
        declaration.update_totals()

        AuditService.log(
            action='TAX_INVESTMENT_ITEM_DELETED',
            actor=requesting_user,
            target_type='InvestmentDeclaration',
            target_id=item_id,
            organization=declaration.organization,
            metadata={'category_code': category_code},
        )

    @staticmethod
    @transaction.atomic
    def upload_proof(
        item: InvestmentDeclaration,
        uploaded_file,
        proof_type: str = 'DOCUMENT',
        document_name: Optional[str] = None,
        requesting_user=None,
    ) -> InvestmentProof:
        """
        Upload proof document attached to an investment declaration item.
        Reuses EmployeeDocument infrastructure for storage vault integration.
        """
        declaration = item.declaration
        employee = declaration.employee

        doc_name = document_name or getattr(uploaded_file, 'name', 'Tax_Proof')

        # Create/bridge EmployeeDocument record
        emp_doc = None
        try:
            emp_doc = EmployeeDocument.objects.create(
                employee=employee,
                document_type=DocumentType.OTHER,
                document_name=f"Tax Proof: {doc_name}",
                file=uploaded_file,
                file_size=getattr(uploaded_file, 'size', 0) or 0,
                mime_type=getattr(uploaded_file, 'content_type', '') or '',
                description=f"Tax Proof for {item.category_code} in {declaration.financial_year.name}",
                status=DocumentStatus.PENDING,
                uploaded_by=requesting_user,
            )
        except Exception as e:
            logger.warning(f"Could not bridge to EmployeeDocument: {e}")

        proof = InvestmentProof.objects.create(
            declaration_item=item,
            employee_document=emp_doc,
            file=emp_doc.file if emp_doc else uploaded_file,
            proof_type=proof_type,
            document_name=doc_name,
            file_size=getattr(uploaded_file, 'size', 0) or 0,
            mime_type=getattr(uploaded_file, 'content_type', '') or '',
            status=InvestmentProof.STATUS_SUBMITTED,
        )

        AuditService.log(
            action='TAX_PROOF_SUBMITTED',
            actor=requesting_user,
            target_type='InvestmentProof',
            target_id=proof.id,
            organization=declaration.organization,
            metadata={
                'item_id': item.id,
                'category_code': item.category_code,
                'document_name': proof.document_name,
            },
        )

        return proof

    @staticmethod
    @transaction.atomic
    def submit_declaration(declaration: TaxDeclaration, requesting_user=None) -> TaxDeclaration:
        """Submit draft declaration for administrative review."""
        if declaration.status not in [TaxDeclaration.STATUS_DRAFT, TaxDeclaration.STATUS_REJECTED]:
            raise TaxDeclarationException(
                f"Cannot submit declaration with status '{declaration.status}'. Must be DRAFT or REJECTED.",
                code='INVALID_STATUS_TRANSITION',
            )

        declaration.update_totals()
        declaration.status = TaxDeclaration.STATUS_SUBMITTED
        declaration.submission_date = timezone.now()
        declaration.rejection_reason = ''
        declaration.save(update_fields=['status', 'submission_date', 'rejection_reason', 'updated_at'])

        AuditService.log(
            action='TAX_DECLARATION_SUBMITTED',
            actor=requesting_user,
            target_type='TaxDeclaration',
            target_id=declaration.id,
            organization=declaration.organization,
            metadata={
                'employee_code': declaration.employee.employee_code,
                'financial_year': declaration.financial_year.name,
                'regime': declaration.tax_regime,
                'total_declared': str(declaration.total_declared_amount),
            },
        )

        return declaration

    @staticmethod
    @transaction.atomic
    def start_review(declaration: TaxDeclaration, reviewer_user=None) -> TaxDeclaration:
        """Transition declaration from SUBMITTED to UNDER_REVIEW."""
        if declaration.status != TaxDeclaration.STATUS_SUBMITTED:
            raise TaxDeclarationException(
                f"Cannot start review on declaration with status '{declaration.status}'. Expected SUBMITTED.",
                code='INVALID_STATUS_TRANSITION',
            )

        declaration.status = TaxDeclaration.STATUS_UNDER_REVIEW
        declaration.save(update_fields=['status', 'updated_at'])

        AuditService.log(
            action='TAX_DECLARATION_UNDER_REVIEW',
            actor=reviewer_user,
            target_type='TaxDeclaration',
            target_id=declaration.id,
            organization=declaration.organization,
        )

        return declaration

    @staticmethod
    @transaction.atomic
    def verify_declaration(
        declaration: TaxDeclaration,
        reviewer_user,
        item_verifications: Optional[List[Dict[str, Any]]] = None,
        notes: str = '',
    ) -> TaxDeclaration:
        """
        Verify submitted declaration. Creates immutable verification snapshot
        and marks declaration as authoritative input for downstream payroll tax calculations.
        """
        if declaration.status not in [TaxDeclaration.STATUS_SUBMITTED, TaxDeclaration.STATUS_UNDER_REVIEW]:
            raise TaxDeclarationException(
                f"Cannot verify declaration with status '{declaration.status}'. Expected SUBMITTED or UNDER_REVIEW.",
                code='INVALID_STATUS_TRANSITION',
            )

        # Apply item-level verified amounts if provided
        if item_verifications:
            item_map = {item.id: item for item in declaration.items.all()}
            for iv in item_verifications:
                item_id = iv.get('id')
                ver_amt = iv.get('verified_amount')
                rej_reason = iv.get('rejection_reason', '')
                if item_id in item_map:
                    it = item_map[item_id]
                    if ver_amt is not None:
                        it.verified_amount = Decimal(str(ver_amt)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                        it.status = InvestmentDeclaration.STATUS_VERIFIED
                    elif iv.get('rejected', False):
                        it.verified_amount = Decimal('0.00')
                        it.status = InvestmentDeclaration.STATUS_REJECTED
                        it.rejection_reason = rej_reason
                    it.save(update_fields=['verified_amount', 'status', 'rejection_reason', 'updated_at'])
        else:
            # Default all pending items to verified_amount = declared_amount
            for item in declaration.items.all():
                if item.verified_amount is None:
                    item.verified_amount = item.declared_amount
                    item.status = InvestmentDeclaration.STATUS_VERIFIED
                    item.save(update_fields=['verified_amount', 'status', 'updated_at'])

        declaration.update_totals()

        # Build immutable snapshot of approved regime and verified totals
        items_snapshot = []
        for it in declaration.items.all():
            items_snapshot.append({
                'id': it.id,
                'category_code': it.category_code,
                'description': it.description,
                'declared_amount': str(it.declared_amount),
                'verified_amount': str(it.verified_amount or '0.00'),
                'status': it.status,
                'metadata': it.metadata,
            })

        declaration.snapshot_data = {
            'verified_at': timezone.now().isoformat(),
            'verified_by_email': reviewer_user.email if reviewer_user else None,
            'tax_regime': declaration.tax_regime,
            'total_declared_amount': str(declaration.total_declared_amount),
            'total_verified_amount': str(declaration.total_verified_amount),
            'items': items_snapshot,
            'verification_notes': notes,
        }

        declaration.status = TaxDeclaration.STATUS_VERIFIED
        declaration.verification_date = timezone.now()
        declaration.verified_by = reviewer_user
        declaration.save(update_fields=[
            'status', 'verification_date', 'verified_by', 'snapshot_data', 'updated_at'
        ])

        AuditService.log(
            action='TAX_DECLARATION_VERIFIED',
            actor=reviewer_user,
            target_type='TaxDeclaration',
            target_id=declaration.id,
            organization=declaration.organization,
            metadata={
                'regime': declaration.tax_regime,
                'total_verified': str(declaration.total_verified_amount),
            },
        )

        return declaration

    @staticmethod
    @transaction.atomic
    def reject_declaration(
        declaration: TaxDeclaration,
        reviewer_user,
        rejection_reason: str,
    ) -> TaxDeclaration:
        """Reject declaration with required reason, allowing employee revision."""
        if declaration.status not in [TaxDeclaration.STATUS_SUBMITTED, TaxDeclaration.STATUS_UNDER_REVIEW]:
            raise TaxDeclarationException(
                f"Cannot reject declaration in state '{declaration.status}'.",
                code='INVALID_STATUS_TRANSITION',
            )

        if not rejection_reason or not rejection_reason.strip():
            raise TaxDeclarationException(
                "A rejection reason is required.",
                code='REJECTION_REASON_REQUIRED',
            )

        declaration.status = TaxDeclaration.STATUS_REJECTED
        declaration.rejection_reason = rejection_reason.strip()
        declaration.save(update_fields=['status', 'rejection_reason', 'updated_at'])

        AuditService.log(
            action='TAX_DECLARATION_REJECTED',
            actor=reviewer_user,
            target_type='TaxDeclaration',
            target_id=declaration.id,
            organization=declaration.organization,
            metadata={'rejection_reason': declaration.rejection_reason},
        )

        return declaration

    @staticmethod
    @transaction.atomic
    def verify_proof(proof: InvestmentProof, reviewer_user=None) -> InvestmentProof:
        """Verify an individual investment proof document."""
        proof.status = InvestmentProof.STATUS_VERIFIED
        proof.reviewed_by = reviewer_user
        proof.reviewed_at = timezone.now()
        proof.rejection_reason = ''
        proof.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_reason', 'updated_at'])

        if proof.employee_document:
            proof.employee_document.status = DocumentStatus.VERIFIED
            proof.employee_document.save(update_fields=['status'])

        AuditService.log(
            action='TAX_PROOF_VERIFIED',
            actor=reviewer_user,
            target_type='InvestmentProof',
            target_id=proof.id,
            organization=proof.declaration_item.declaration.organization,
        )

        return proof

    @staticmethod
    @transaction.atomic
    def reject_proof(
        proof: InvestmentProof,
        rejection_reason: str,
        reviewer_user=None,
    ) -> InvestmentProof:
        """Reject an individual investment proof document with reason."""
        if not rejection_reason or not rejection_reason.strip():
            raise TaxDeclarationException(
                "A rejection reason is required to reject proof.",
                code='REJECTION_REASON_REQUIRED',
            )

        proof.status = InvestmentProof.STATUS_REJECTED
        proof.rejection_reason = rejection_reason.strip()
        proof.reviewed_by = reviewer_user
        proof.reviewed_at = timezone.now()
        proof.save(update_fields=['status', 'rejection_reason', 'reviewed_by', 'reviewed_at', 'updated_at'])

        if proof.employee_document:
            proof.employee_document.status = DocumentStatus.REJECTED
            proof.employee_document.save(update_fields=['status'])

        AuditService.log(
            action='TAX_PROOF_REJECTED',
            actor=reviewer_user,
            target_type='InvestmentProof',
            target_id=proof.id,
            organization=proof.declaration_item.declaration.organization,
            metadata={'rejection_reason': rejection_reason},
        )

        return proof

    # =========================================================================
    # DOWNSTREAM TAX SERVICE INTEGRATION BOUNDARY (Part 9)
    # =========================================================================

    @staticmethod
    def get_verified_declaration_inputs(employee: Employee, financial_year: FinancialYear) -> Dict[str, Any]:
        """
        Authoritative export boundary for downstream tax calculation services.
        Extracts verified declaration inputs for an employee for a financial year.
        If no verified declaration exists, defaults safely to New Tax Regime with zero deductions.
        """
        declaration = TaxDeclaration.objects.filter(
            employee=employee,
            financial_year=financial_year,
            status=TaxDeclaration.STATUS_VERIFIED,
        ).prefetch_related('items').first()

        if not declaration:
            return {
                'has_verified_declaration': False,
                'tax_regime': TaxDeclaration.REGIME_NEW,
                'declaration_id': None,
                'total_declared_deductions': Decimal('0.00'),
                'total_verified_deductions': Decimal('0.00'),
                'categories': {},
                'verified_items': [],
            }

        categories: Dict[str, Decimal] = {}
        items_list = []

        for item in declaration.items.all():
            cat = item.category_code
            v_amt = item.verified_amount or Decimal('0.00')
            categories[cat] = categories.get(cat, Decimal('0.00')) + v_amt
            items_list.append({
                'category_code': cat,
                'description': item.description,
                'declared_amount': item.declared_amount,
                'verified_amount': v_amt,
                'status': item.status,
                'metadata': item.metadata,
            })

        return {
            'has_verified_declaration': True,
            'tax_regime': declaration.tax_regime,
            'declaration_id': declaration.id,
            'total_declared_deductions': declaration.total_declared_amount,
            'total_verified_deductions': declaration.total_verified_amount,
            'categories': categories,
            'verified_items': items_list,
        }
