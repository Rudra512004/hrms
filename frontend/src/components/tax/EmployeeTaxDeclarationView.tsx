import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  FileText,
  Upload,
  Plus,
  Trash2,
  Edit2,
  Download,
  AlertCircle,
  CheckCircle2,
  Clock,
  Lock,
  Send,
  Loader2,
  FileCheck,
  AlertTriangle,
  Info,
} from 'lucide-react';
import { Card } from '../Card';
import { Modal } from '../Modal';
import { StatusBadge } from '../StatusBadge';
import { EmptyState } from '../EmptyState';
import {
  payrollService,
  formatCurrency,
  extractApiError,
  type FinancialYear,
  type TaxDeclarationCategory,
  type TaxDeclarationDetail,
  type InvestmentDeclaration,
  type InvestmentProof,
} from '../../services/payroll';

export const EmployeeTaxDeclarationView: React.FC = () => {
  // Financial Years & Categories
  const [financialYears, setFinancialYears] = useState<FinancialYear[]>([]);
  const [selectedFyId, setSelectedFyId] = useState<number | null>(null);
  const [categories, setCategories] = useState<TaxDeclarationCategory[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);

  // Declaration State
  const [declaration, setDeclaration] = useState<TaxDeclarationDetail | null>(null);
  const [loadingDeclaration, setLoadingDeclaration] = useState(false);
  const [declarationError, setDeclarationError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Modals State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [showAddItemModal, setShowAddItemModal] = useState(false);
  const [editingItem, setEditingItem] = useState<InvestmentDeclaration | null>(null);
  const [uploadProofItem, setUploadProofItem] = useState<InvestmentDeclaration | null>(null);
  const [deletingItemId, setDeletingItemId] = useState<number | null>(null);

  // Form States
  const [newRegime, setNewRegime] = useState<'OLD' | 'NEW'>('NEW');
  const [newNotes, setNewNotes] = useState('');
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Add/Edit Item Form State
  const [itemCategoryCode, setItemCategoryCode] = useState('');
  const [itemDescription, setItemDescription] = useState('');
  const [itemDeclaredAmount, setItemDeclaredAmount] = useState('');
  const [itemFormSubmitting, setItemFormSubmitting] = useState(false);
  const [itemFormError, setItemFormError] = useState<string | null>(null);

  // Upload Proof Form State
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [proofDocName, setProofDocName] = useState('');
  const [proofType, setProofType] = useState('DOCUMENT');
  const [uploadSubmitting, setUploadSubmitting] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Action Loading
  const [actionInProgress, setActionInProgress] = useState(false);
  const [downloadingProofId, setDownloadingProofId] = useState<number | null>(null);

  // Selected Financial Year object
  const selectedFy = useMemo(() => {
    return financialYears.find((fy) => fy.id === selectedFyId) || null;
  }, [financialYears, selectedFyId]);

  // Is declaration editable by employee
  const isEditable = useMemo(() => {
    if (!declaration) return false;
    if (declaration.financial_year_locked) return false;
    if (selectedFy?.is_locked) return false;
    return declaration.status === 'draft' || declaration.status === 'rejected';
  }, [declaration, selectedFy]);

  // ─── 1. Load Financial Years and Categories ─────────────────────────────────
  const fetchInitialData = useCallback(async () => {
    setInitialLoading(true);
    setDeclarationError(null);
    try {
      const [fys, cats] = await Promise.all([
        payrollService.getFinancialYears(),
        payrollService.getTaxCategories(),
      ]);
      setFinancialYears(fys);
      setCategories(cats);

      if (fys.length > 0) {
        // Pick active FY or first FY
        const activeFy = fys.find((f) => f.is_active) || fys[0];
        setSelectedFyId(activeFy.id);
      }
    } catch (err) {
      setDeclarationError(extractApiError(err));
    } finally {
      setInitialLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  // ─── 2. Fetch Declaration for Selected Financial Year ───────────────────────
  const fetchDeclarationForFy = useCallback(async (fyId: number) => {
    setLoadingDeclaration(true);
    setDeclarationError(null);
    setActionSuccess(null);
    try {
      const summaries = await payrollService.getMyTaxDeclarations(fyId);
      if (summaries && summaries.length > 0) {
        // Load authoritative detail with items & proofs
        const detail = await payrollService.getTaxDeclarationDetail(summaries[0].id);
        setDeclaration(detail);
      } else {
        setDeclaration(null);
      }
    } catch (err: any) {
      setDeclaration(null);
      setDeclarationError(extractApiError(err));
    } finally {
      setLoadingDeclaration(false);
    }
  }, []);

  useEffect(() => {
    if (selectedFyId) {
      fetchDeclarationForFy(selectedFyId);
    }
  }, [selectedFyId, fetchDeclarationForFy]);

  // ─── 3. Create Draft Declaration ────────────────────────────────────────────
  const handleOpenCreateModal = () => {
    setNewRegime('NEW');
    setNewNotes('');
    setCreateError(null);
    setShowCreateModal(true);
  };

  const handleCreateDeclaration = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFyId) return;
    setCreateSubmitting(true);
    setCreateError(null);
    try {
      const created = await payrollService.createTaxDeclaration({
        financial_year_id: selectedFyId,
        tax_regime: newRegime,
        notes: newNotes.trim(),
      });
      setDeclaration(created);
      setShowCreateModal(false);
      setActionSuccess('Draft tax declaration successfully created.');
    } catch (err) {
      setCreateError(extractApiError(err));
    } finally {
      setCreateSubmitting(false);
    }
  };

  // ─── 4. Update Regime on Draft Declaration ──────────────────────────────────
  const handleRegimeChange = async (targetRegime: 'OLD' | 'NEW') => {
    if (!declaration || !isEditable) return;
    setActionInProgress(true);
    setDeclarationError(null);
    try {
      const updated = await payrollService.updateTaxDeclaration(declaration.id, {
        tax_regime: targetRegime,
      });
      setDeclaration(updated);
      setActionSuccess(`Tax regime updated to ${targetRegime}.`);
    } catch (err) {
      setDeclarationError(extractApiError(err));
    } finally {
      setActionInProgress(false);
    }
  };

  // ─── 5. Add / Edit Investment Item ──────────────────────────────────────────
  const handleOpenAddItem = () => {
    if (categories.length > 0) {
      setItemCategoryCode(categories[0].code);
    } else {
      setItemCategoryCode('');
    }
    setItemDescription('');
    setItemDeclaredAmount('');
    setItemFormError(null);
    setShowAddItemModal(true);
  };

  const handleOpenEditItem = (item: InvestmentDeclaration) => {
    setEditingItem(item);
    setItemDescription(item.description);
    setItemDeclaredAmount(item.declared_amount);
    setItemFormError(null);
  };

  const handleSaveItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!declaration) return;
    setItemFormSubmitting(true);
    setItemFormError(null);

    const amountNum = parseFloat(itemDeclaredAmount);
    if (isNaN(amountNum) || amountNum <= 0) {
      setItemFormError('Please enter a valid declared amount greater than 0.');
      setItemFormSubmitting(false);
      return;
    }

    try {
      if (editingItem) {
        await payrollService.updateInvestmentItem(declaration.id, editingItem.id, {
          description: itemDescription.trim(),
          declared_amount: itemDeclaredAmount,
        });
        setActionSuccess('Investment item updated.');
        setEditingItem(null);
      } else {
        if (!itemCategoryCode) {
          setItemFormError('Please select an investment category.');
          setItemFormSubmitting(false);
          return;
        }
        await payrollService.addInvestmentItem(declaration.id, {
          category_code: itemCategoryCode,
          description: itemDescription.trim(),
          declared_amount: itemDeclaredAmount,
        });
        setActionSuccess('Investment item added.');
        setShowAddItemModal(false);
      }
      // Refresh authoritative declaration detail
      const refreshed = await payrollService.getTaxDeclarationDetail(declaration.id);
      setDeclaration(refreshed);
    } catch (err) {
      setItemFormError(extractApiError(err));
    } finally {
      setItemFormSubmitting(false);
    }
  };

  // ─── 6. Delete Investment Item ──────────────────────────────────────────────
  const handleDeleteItem = async (itemId: number) => {
    if (!declaration || !isEditable) return;
    setDeletingItemId(itemId);
    setActionInProgress(true);
    setDeclarationError(null);
    try {
      await payrollService.deleteInvestmentItem(declaration.id, itemId);
      setActionSuccess('Investment item deleted.');
      const refreshed = await payrollService.getTaxDeclarationDetail(declaration.id);
      setDeclaration(refreshed);
    } catch (err) {
      setDeclarationError(extractApiError(err));
    } finally {
      setDeletingItemId(null);
      setActionInProgress(false);
    }
  };

  // ─── 7. Upload Proof ────────────────────────────────────────────────────────
  const handleOpenUploadProof = (item: InvestmentDeclaration) => {
    setUploadProofItem(item);
    setProofFile(null);
    setProofDocName('');
    setProofType('DOCUMENT');
    setUploadError(null);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setProofFile(file);
      if (!proofDocName) {
        setProofDocName(file.name);
      }
    }
  };

  const handleUploadProofSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!declaration || !uploadProofItem) return;
    if (!proofFile) {
      setUploadError('Please select a proof file to upload.');
      return;
    }

    setUploadSubmitting(true);
    setUploadError(null);

    try {
      const formData = new FormData();
      formData.append('file', proofFile);
      formData.append('document_name', proofDocName.trim() || proofFile.name);
      formData.append('proof_type', proofType);

      await payrollService.uploadInvestmentProof(declaration.id, uploadProofItem.id, formData);
      setActionSuccess('Proof document uploaded successfully.');
      setUploadProofItem(null);

      // Refresh authoritative declaration detail
      const refreshed = await payrollService.getTaxDeclarationDetail(declaration.id);
      setDeclaration(refreshed);
    } catch (err) {
      setUploadError(extractApiError(err));
    } finally {
      setUploadSubmitting(false);
    }
  };

  // ─── 8. Download Proof ──────────────────────────────────────────────────────
  const handleDownloadProof = async (itemId: number, proof: InvestmentProof) => {
    if (!declaration) return;
    setDownloadingProofId(proof.id);
    setDeclarationError(null);
    try {
      const { blob, filename } = await payrollService.downloadInvestmentProof(
        declaration.id,
        itemId,
        proof.id
      );
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename || proof.document_name);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setDeclarationError(extractApiError(err));
    } finally {
      setDownloadingProofId(null);
    }
  };

  // ─── 9. Submit Declaration ──────────────────────────────────────────────────
  const handleSubmitDeclaration = async () => {
    if (!declaration) return;
    setActionInProgress(true);
    setDeclarationError(null);
    try {
      const submitted = await payrollService.submitTaxDeclaration(declaration.id);
      setDeclaration(submitted);
      setShowSubmitModal(false);
      setActionSuccess('Your tax declaration has been submitted for review.');
    } catch (err) {
      setDeclarationError(extractApiError(err));
    } finally {
      setActionInProgress(false);
    }
  };

  // Category helper
  const getCategoryDetails = (code: string) => {
    return categories.find((c) => c.code.toUpperCase() === code.toUpperCase());
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
      {/* ─── Financial Year & Header Controls ─────────────────────────────── */}
      <Card noPadding>
        <div
          style={{
            padding: '16px 20px',
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <label
              htmlFor="tax-fy-select"
              style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--color-text-main)' }}
            >
              Financial Year:
            </label>
            <select
              id="tax-fy-select"
              value={selectedFyId || ''}
              onChange={(e) => setSelectedFyId(Number(e.target.value))}
              disabled={initialLoading || financialYears.length === 0}
              style={{
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-border)',
                background: 'var(--color-bg-body)',
                color: 'var(--color-text-main)',
                fontSize: '0.9rem',
                minWidth: '220px',
              }}
            >
              {financialYears.map((fy) => (
                <option key={fy.id} value={fy.id}>
                  {fy.name} {fy.is_locked ? '(Locked)' : ''} {fy.is_active ? '(Active)' : ''}
                </option>
              ))}
            </select>

            {selectedFy && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '0.8rem',
                  color: 'var(--color-text-muted)',
                }}
              >
                <span>Period: {selectedFy.start_date} to {selectedFy.end_date}</span>
                {selectedFy.is_locked && (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      color: 'var(--color-status-danger)',
                      fontWeight: 600,
                    }}
                  >
                    <Lock size={13} /> Locked
                  </span>
                )}
                {selectedFy.is_active && (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      color: 'var(--color-status-success)',
                      fontWeight: 600,
                    }}
                  >
                    <CheckCircle2 size={13} /> Current Active FY
                  </span>
                )}
              </div>
            )}
          </div>

          <div>
            {!declaration && !loadingDeclaration && selectedFy && !selectedFy.is_locked && (
              <button
                className="btn btn-primary"
                onClick={handleOpenCreateModal}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              >
                <Plus size={16} /> Start Tax Declaration
              </button>
            )}
            {declaration && isEditable && (
              <button
                className="btn btn-primary"
                onClick={() => setShowSubmitModal(true)}
                disabled={actionInProgress}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              >
                <Send size={15} />
                {declaration.status === 'rejected' ? 'Resubmit Declaration' : 'Submit Declaration'}
              </button>
            )}
          </div>
        </div>
      </Card>

      {/* Action Success Banner */}
      {actionSuccess && (
        <div
          role="status"
          style={{
            padding: '12px 16px',
            backgroundColor: 'rgba(34, 197, 94, 0.1)',
            border: '1px solid var(--color-status-success)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--color-status-success)',
            fontSize: '0.875rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircle2 size={16} />
            <span>{actionSuccess}</span>
          </div>
          <button
            className="btn btn-ghost"
            style={{ padding: '2px 6px', fontSize: '0.75rem', color: 'inherit' }}
            onClick={() => setActionSuccess(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Declaration Error Banner */}
      {declarationError && (
        <div
          role="alert"
          style={{
            padding: '12px 16px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid var(--color-status-danger)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--color-status-danger)',
            fontSize: '0.875rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertCircle size={16} />
            <span>{declarationError}</span>
          </div>
          <button
            className="btn btn-ghost"
            style={{ padding: '2px 6px', fontSize: '0.75rem', color: 'inherit' }}
            onClick={() => setDeclarationError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* ─── Loading State ─────────────────────────────────────────────────── */}
      {(initialLoading || loadingDeclaration) && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--spacing-2xl)' }}>
          <Loader2 className="animate-spin" size={32} color="var(--color-primary)" />
        </div>
      )}

      {/* ─── Empty State (No declaration exists) ──────────────────────────── */}
      {!initialLoading && !loadingDeclaration && !declaration && selectedFy && (
        <Card noPadding>
          <div style={{ padding: '40px 20px', textAlign: 'center' }}>
            {selectedFy.is_locked ? (
              <EmptyState
                title={`Declarations Locked for ${selectedFy.name}`}
                description="This financial year is locked by payroll administrators. Tax declaration submissions are no longer accepted for this period."
                icon={Lock}
              />
            ) : (
              <div>
                <EmptyState
                  title={`No Tax Declaration for ${selectedFy.name}`}
                  description="You have not created an investment declaration for this financial year yet. Create a draft declaration to declare eligible investments and select your tax regime."
                  icon={FileText}
                />
                <div style={{ marginTop: '20px' }}>
                  <button className="btn btn-primary" onClick={handleOpenCreateModal}>
                    <Plus size={16} style={{ marginRight: '6px' }} /> Create Tax Declaration
                  </button>
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* ─── Active Declaration Details ────────────────────────────────────── */}
      {!initialLoading && !loadingDeclaration && declaration && (
        <>
          {/* Status & Lifecycle Alert Banners */}
          {declaration.status === 'draft' && (
            <div
              style={{
                padding: '14px 18px',
                backgroundColor: 'rgba(234, 179, 8, 0.1)',
                border: '1px solid var(--color-status-warning)',
                borderRadius: 'var(--radius-sm)',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
              }}
            >
              <Info size={20} color="var(--color-status-warning)" />
              <div style={{ fontSize: '0.875rem', color: 'var(--color-text-main)' }}>
                <strong>Draft Declaration:</strong> You can edit your tax regime, add or modify investment items, and attach proof documents. Once finalized, click <strong>Submit Declaration</strong> to send for review.
              </div>
            </div>
          )}

          {declaration.status === 'submitted' && (
            <div
              style={{
                padding: '14px 18px',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                border: '1px solid var(--color-primary)',
                borderRadius: 'var(--radius-sm)',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
              }}
            >
              <Clock size={20} color="var(--color-primary)" />
              <div style={{ fontSize: '0.875rem', color: 'var(--color-text-main)' }}>
                <strong>Submitted & Awaiting Review:</strong> Your declaration was submitted on{' '}
                {declaration.submission_date || 'date recorded'} and is locked for verification. Editing and proof uploads are disabled while pending review.
              </div>
            </div>
          )}

          {declaration.status === 'under_review' && (
            <div
              style={{
                padding: '14px 18px',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                border: '1px solid var(--color-primary)',
                borderRadius: 'var(--radius-sm)',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
              }}
            >
              <Loader2 size={20} color="var(--color-primary)" className="animate-spin" />
              <div style={{ fontSize: '0.875rem', color: 'var(--color-text-main)' }}>
                <strong>Under Review:</strong> Your declaration is currently undergoing review by the finance and payroll operations team. This declaration is strictly read-only.
              </div>
            </div>
          )}

          {declaration.status === 'verified' && (
            <div
              style={{
                padding: '14px 18px',
                backgroundColor: 'rgba(34, 197, 94, 0.1)',
                border: '1px solid var(--color-status-success)',
                borderRadius: 'var(--radius-sm)',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
              }}
            >
              <CheckCircle2 size={20} color="var(--color-status-success)" />
              <div style={{ fontSize: '0.875rem', color: 'var(--color-text-main)' }}>
                <strong>Declaration Verified:</strong> Verified
                {declaration.verification_date ? ` on ${declaration.verification_date}` : ''}
                {declaration.verified_by_email ? ` by ${declaration.verified_by_email}` : ''}.
                Total verified amount: <strong>{formatCurrency(declaration.total_verified_amount)}</strong>.
              </div>
            </div>
          )}

          {declaration.status === 'rejected' && (
            <div
              style={{
                padding: '14px 18px',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid var(--color-status-danger)',
                borderRadius: 'var(--radius-sm)',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
              }}
            >
              <AlertTriangle size={20} color="var(--color-status-danger)" style={{ marginTop: '2px', flexShrink: 0 }} />
              <div style={{ fontSize: '0.875rem', color: 'var(--color-text-main)' }}>
                <strong style={{ color: 'var(--color-status-danger)' }}>Declaration Returned / Rejected:</strong>
                <p style={{ margin: '4px 0 8px 0', color: 'var(--color-status-danger)', fontWeight: 500 }}>
                  Reason: {declaration.rejection_reason || 'No specific rejection reason provided.'}
                </p>
                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                  You can update your declared items, attach corrected proofs, and click <strong>Resubmit Declaration</strong>.
                </div>
              </div>
            </div>
          )}

          {/* Declaration Overview Cards */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: 'var(--spacing-md)',
            }}
          >
            {/* Regime Card */}
            <Card title="Elected Tax Regime" noPadding>
              <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>Tax Regime:</span>
                  <StatusBadge
                    status={declaration.tax_regime === 'NEW' ? 'approved' : 'info'}
                    label={`${declaration.tax_regime} REGIME`}
                  />
                </div>

                {isEditable ? (
                  <div style={{ marginTop: '4px' }}>
                    <label
                      htmlFor="select-tax-regime"
                      style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}
                    >
                      Change Regime:
                    </label>
                    <select
                      id="select-tax-regime"
                      value={declaration.tax_regime}
                      onChange={(e) => handleRegimeChange(e.target.value as 'OLD' | 'NEW')}
                      disabled={actionInProgress}
                      style={{
                        width: '100%',
                        padding: '6px 10px',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--color-border)',
                        background: 'var(--color-bg-body)',
                        color: 'var(--color-text-main)',
                        fontSize: '0.85rem',
                      }}
                    >
                      <option value="NEW">New Tax Regime (Section 115BAC)</option>
                      <option value="OLD">Old Tax Regime</option>
                    </select>
                  </div>
                ) : (
                  <p style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', margin: 0 }}>
                    {declaration.tax_regime === 'NEW'
                      ? 'New Tax Regime (Section 115BAC) selected.'
                      : 'Old Tax Regime selected.'}
                  </p>
                )}
              </div>
            </Card>

            {/* Status Card */}
            <Card title="Declaration Status" noPadding>
              <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>Status:</span>
                  <StatusBadge
                    status={
                      declaration.status === 'verified'
                        ? 'approved'
                        : declaration.status === 'rejected'
                        ? 'rejected'
                        : declaration.status === 'draft'
                        ? 'draft'
                        : 'pending'
                    }
                    label={declaration.status.replace('_', ' ').toUpperCase()}
                  />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Financial Year:</span>
                  <span style={{ fontWeight: 600 }}>{declaration.financial_year_name}</span>
                </div>
                {declaration.submission_date && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                    <span style={{ color: 'var(--color-text-muted)' }}>Submitted On:</span>
                    <span>{declaration.submission_date}</span>
                  </div>
                )}
              </div>
            </Card>

            {/* Total Declared vs Verified */}
            <Card title="Declaration Amounts" noPadding>
              <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Total Declared:</span>
                  <span style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--color-text-main)' }}>
                    {formatCurrency(declaration.total_declared_amount)}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Total Verified:</span>
                  <span
                    style={{
                      fontWeight: 700,
                      fontSize: '1rem',
                      color:
                        parseFloat(declaration.total_verified_amount) > 0
                          ? 'var(--color-status-success)'
                          : 'var(--color-text-muted)',
                    }}
                  >
                    {formatCurrency(declaration.total_verified_amount)}
                  </span>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                  Total Items: {declaration.items?.length || 0}
                </div>
              </div>
            </Card>
          </div>

          {/* ─── Investment Declaration Items Table ─────────────────────────── */}
          <Card
            title="Declared Investment Items & Supporting Proofs"
            actions={
              isEditable ? (
                <button
                  className="btn btn-outline"
                  onClick={handleOpenAddItem}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}
                >
                  <Plus size={14} /> Add Investment Item
                </button>
              ) : undefined
            }
            noPadding
          >
            {(!declaration.items || declaration.items.length === 0) ? (
              <div style={{ padding: '40px 20px', textAlign: 'center' }}>
                <EmptyState
                  title="No Investment Items Declared"
                  description="You have not declared any investment or deduction items for this financial year yet."
                  icon={FileText}
                />
                {isEditable && (
                  <div style={{ marginTop: '16px' }}>
                    <button className="btn btn-primary" onClick={handleOpenAddItem}>
                      <Plus size={15} style={{ marginRight: '6px' }} /> Add Investment Item
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--color-border)', textAlign: 'left' }}>
                      <th style={{ padding: '12px 16px', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                        Category
                      </th>
                      <th style={{ padding: '12px 16px', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                        Description
                      </th>
                      <th style={{ padding: '12px 16px', fontSize: '0.8rem', color: 'var(--color-text-muted)', textAlign: 'right' }}>
                        Declared Amount
                      </th>
                      <th style={{ padding: '12px 16px', fontSize: '0.8rem', color: 'var(--color-text-muted)', textAlign: 'right' }}>
                        Verified Amount
                      </th>
                      <th style={{ padding: '12px 16px', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                        Status
                      </th>
                      <th style={{ padding: '12px 16px', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                        Proofs Attached
                      </th>
                      {isEditable && (
                        <th style={{ padding: '12px 16px', fontSize: '0.8rem', color: 'var(--color-text-muted)', textAlign: 'right' }}>
                          Actions
                        </th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {declaration.items.map((item) => {
                      const catInfo = getCategoryDetails(item.category_code);
                      return (
                        <React.Fragment key={item.id}>
                          <tr
                            style={{
                              borderBottom: '1px solid var(--color-border)',
                              verticalAlign: 'top',
                            }}
                          >
                            <td style={{ padding: '12px 16px', fontSize: '0.875rem' }}>
                              <div style={{ fontWeight: 600, color: 'var(--color-text-main)' }}>
                                {item.category_code}
                              </div>
                              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                                {catInfo?.name || item.category_code}
                              </div>
                              {catInfo?.max_limit && (
                                <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                                  Configured limit: {formatCurrency(catInfo.max_limit)}
                                </div>
                              )}
                            </td>
                            <td style={{ padding: '12px 16px', fontSize: '0.875rem' }}>
                              <div>{item.description}</div>
                              {item.rejection_reason && (
                                <div
                                  style={{
                                    fontSize: '0.75rem',
                                    color: 'var(--color-status-danger)',
                                    marginTop: '4px',
                                  }}
                                >
                                  <strong>Rejected:</strong> {item.rejection_reason}
                                </div>
                              )}
                            </td>
                            <td style={{ padding: '12px 16px', fontSize: '0.875rem', textAlign: 'right', fontWeight: 600 }}>
                              {formatCurrency(item.declared_amount)}
                            </td>
                            <td style={{ padding: '12px 16px', fontSize: '0.875rem', textAlign: 'right' }}>
                              {item.status === 'verified' ? (
                                <span style={{ fontWeight: 600, color: 'var(--color-status-success)' }}>
                                  {formatCurrency(item.verified_amount)}
                                </span>
                              ) : (
                                <span style={{ color: 'var(--color-text-muted)' }}>—</span>
                              )}
                            </td>
                            <td style={{ padding: '12px 16px', fontSize: '0.875rem' }}>
                              <StatusBadge
                                status={
                                  item.status === 'verified'
                                    ? 'approved'
                                    : item.status === 'rejected'
                                    ? 'rejected'
                                    : 'pending'
                                }
                                label={item.status.toUpperCase()}
                              />
                            </td>
                            <td style={{ padding: '12px 16px', fontSize: '0.875rem' }}>
                              {item.proofs && item.proofs.length > 0 ? (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                  {item.proofs.map((proof) => (
                                    <div
                                      key={proof.id}
                                      style={{
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: '6px',
                                        padding: '4px 8px',
                                        borderRadius: 'var(--radius-sm)',
                                        border: '1px solid var(--color-border)',
                                        backgroundColor: 'var(--color-bg-body)',
                                        fontSize: '0.75rem',
                                        maxWidth: '280px',
                                      }}
                                    >
                                      <FileCheck size={14} style={{ flexShrink: 0 }} />
                                      <span
                                        style={{
                                          overflow: 'hidden',
                                          textOverflow: 'ellipsis',
                                          whiteSpace: 'nowrap',
                                          flex: 1,
                                        }}
                                        title={proof.document_name}
                                      >
                                        {proof.document_name}
                                      </span>
                                      <StatusBadge
                                        status={
                                          proof.status === 'verified'
                                            ? 'approved'
                                            : proof.status === 'rejected'
                                            ? 'rejected'
                                            : 'pending'
                                        }
                                        label={proof.status}
                                      />
                                      <button
                                        type="button"
                                        className="btn btn-ghost"
                                        style={{ padding: '2px 4px', fontSize: '0.7rem' }}
                                        onClick={() => handleDownloadProof(item.id, proof)}
                                        disabled={downloadingProofId === proof.id}
                                        title="Download Proof"
                                        aria-label={`Download proof ${proof.document_name}`}
                                      >
                                        {downloadingProofId === proof.id ? (
                                          <Loader2 size={12} className="animate-spin" />
                                        ) : (
                                          <Download size={12} />
                                        )}
                                      </button>
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                                  No proofs attached
                                </span>
                              )}
                            </td>
                            {isEditable && (
                              <td style={{ padding: '12px 16px', fontSize: '0.875rem', textAlign: 'right' }}>
                                <div style={{ display: 'inline-flex', gap: '6px' }}>
                                  <button
                                    type="button"
                                    className="btn btn-ghost"
                                    style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                                    onClick={() => handleOpenUploadProof(item)}
                                    title="Upload Proof"
                                    aria-label={`Upload proof for ${item.category_code}`}
                                  >
                                    <Upload size={14} style={{ marginRight: '4px' }} /> Upload
                                  </button>
                                  <button
                                    type="button"
                                    className="btn btn-ghost"
                                    style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                                    onClick={() => handleOpenEditItem(item)}
                                    title="Edit Item"
                                    aria-label={`Edit item ${item.category_code}`}
                                  >
                                    <Edit2 size={14} />
                                  </button>
                                  <button
                                    type="button"
                                    className="btn btn-ghost"
                                    style={{ padding: '4px 8px', fontSize: '0.75rem', color: 'var(--color-status-danger)' }}
                                    onClick={() => handleDeleteItem(item.id)}
                                    disabled={actionInProgress || deletingItemId === item.id}
                                    title="Delete Item"
                                    aria-label={`Delete item ${item.category_code}`}
                                  >
                                    {deletingItemId === item.id ? (
                                      <Loader2 size={14} className="animate-spin" />
                                    ) : (
                                      <Trash2 size={14} />
                                    )}
                                  </button>

                                </div>
                              </td>
                            )}
                          </tr>
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}

      {/* ─── MODAL 1: CREATE DRAFT DECLARATION ────────────────────────────── */}
      {showCreateModal && selectedFy && (
        <Modal
          title={`Start Tax Declaration — ${selectedFy.name}`}
          onClose={() => setShowCreateModal(false)}
          size="md"
        >
          <form onSubmit={handleCreateDeclaration}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', padding: '8px 0' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '4px' }}>
                  Financial Year
                </label>
                <input
                  type="text"
                  value={`${selectedFy.name} (${selectedFy.start_date} to ${selectedFy.end_date})`}
                  disabled
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-bg-body)',
                    color: 'var(--color-text-muted)',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
                  Select Tax Regime <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                </label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-sm)',
                      border: newRegime === 'NEW' ? '1px solid var(--color-primary)' : '1px solid var(--color-border)',
                      backgroundColor: newRegime === 'NEW' ? 'rgba(59, 130, 246, 0.05)' : 'transparent',
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="radio"
                      name="taxRegime"
                      value="NEW"
                      checked={newRegime === 'NEW'}
                      onChange={() => setNewRegime('NEW')}
                    />
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>New Tax Regime (Section 115BAC)</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                        Default statutory regime. Applicable slab rates determined server-side.
                      </div>
                    </div>
                  </label>

                  <label
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-sm)',
                      border: newRegime === 'OLD' ? '1px solid var(--color-primary)' : '1px solid var(--color-border)',
                      backgroundColor: newRegime === 'OLD' ? 'rgba(59, 130, 246, 0.05)' : 'transparent',
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="radio"
                      name="taxRegime"
                      value="OLD"
                      checked={newRegime === 'OLD'}
                      onChange={() => setNewRegime('OLD')}
                    />
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>Old Tax Regime</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                        Traditional statutory regime supporting Chapter VI-A deductions and allowances.
                      </div>
                    </div>
                  </label>
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '4px' }}>
                  Notes / Declaration Remarks (Optional)
                </label>
                <textarea
                  value={newNotes}
                  onChange={(e) => setNewNotes(e.target.value)}
                  placeholder="Optional comments regarding your declaration"
                  rows={2}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-bg-body)',
                    color: 'var(--color-text-main)',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              {createError && (
                <div style={{ color: 'var(--color-status-danger)', fontSize: '0.85rem', display: 'flex', gap: '6px' }}>
                  <AlertCircle size={15} style={{ flexShrink: 0, marginTop: '2px' }} />
                  <span>{createError}</span>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => setShowCreateModal(false)}
                  disabled={createSubmitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={createSubmitting}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                >
                  {createSubmitting ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                  Create Draft Declaration
                </button>
              </div>
            </div>
          </form>
        </Modal>
      )}

      {/* ─── MODAL 2: ADD / EDIT INVESTMENT ITEM ─────────────────────────── */}
      {(showAddItemModal || editingItem) && (
        <Modal
          title={editingItem ? `Edit Investment Item (${editingItem.category_code})` : 'Add Investment Declaration Item'}
          onClose={() => {
            setShowAddItemModal(false);
            setEditingItem(null);
          }}
          size="md"
        >
          <form onSubmit={handleSaveItem}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', padding: '8px 0' }}>
              {!editingItem && (
                <div>
                  <label
                    htmlFor="item-category-select"
                    style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '4px' }}
                  >
                    Category <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                  </label>
                  <select
                    id="item-category-select"
                    value={itemCategoryCode}
                    onChange={(e) => setItemCategoryCode(e.target.value)}
                    required
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--color-border)',
                      background: 'var(--color-bg-body)',
                      color: 'var(--color-text-main)',
                      fontSize: '0.875rem',
                      boxSizing: 'border-box',
                    }}
                  >
                    {categories.map((cat) => (
                      <option key={cat.id} value={cat.code}>
                        {cat.code} — {cat.name}{' '}
                        {cat.max_limit ? `(Configured Limit: ${formatCurrency(cat.max_limit)})` : ''}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label
                  htmlFor="item-description-input"
                  style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '4px' }}
                >
                  Description <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                </label>
                <input
                  id="item-description-input"
                  type="text"
                  value={itemDescription}
                  onChange={(e) => setItemDescription(e.target.value)}
                  placeholder="e.g. Life Insurance Policy Premium or PPF Deposit"
                  required
                  maxLength={255}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-bg-body)',
                    color: 'var(--color-text-main)',
                    fontSize: '0.875rem',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div>
                <label
                  htmlFor="item-amount-input"
                  style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '4px' }}
                >
                  Declared Amount (₹) <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                </label>
                <input
                  id="item-amount-input"
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={itemDeclaredAmount}
                  onChange={(e) => setItemDeclaredAmount(e.target.value)}
                  placeholder="e.g. 50000.00"
                  required
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-bg-body)',
                    color: 'var(--color-text-main)',
                    fontSize: '0.875rem',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              {itemFormError && (
                <div style={{ color: 'var(--color-status-danger)', fontSize: '0.85rem', display: 'flex', gap: '6px' }}>
                  <AlertCircle size={15} style={{ flexShrink: 0, marginTop: '2px' }} />
                  <span>{itemFormError}</span>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => {
                    setShowAddItemModal(false);
                    setEditingItem(null);
                  }}
                  disabled={itemFormSubmitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={itemFormSubmitting}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                >
                  {itemFormSubmitting && <Loader2 size={15} className="animate-spin" />}
                  {editingItem ? 'Save Changes' : 'Add Item'}
                </button>
              </div>
            </div>
          </form>
        </Modal>
      )}

      {/* ─── MODAL 3: UPLOAD PROOF ────────────────────────────────────────── */}
      {uploadProofItem && (
        <Modal
          title={`Upload Proof Document (${uploadProofItem.category_code})`}
          onClose={() => setUploadProofItem(null)}
          size="md"
        >
          <form onSubmit={handleUploadProofSubmit}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', padding: '8px 0' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '4px' }}>
                  Attaching Proof For
                </label>
                <div
                  style={{
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'var(--color-bg-body)',
                    border: '1px solid var(--color-border)',
                    fontSize: '0.85rem',
                  }}
                >
                  <strong>{uploadProofItem.category_code}:</strong> {uploadProofItem.description} (
                  {formatCurrency(uploadProofItem.declared_amount)})
                </div>
              </div>

              <div>
                <label
                  htmlFor="proof-file-input"
                  style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '4px' }}
                >
                  Supporting Document File <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                </label>
                <input
                  id="proof-file-input"
                  type="file"
                  required
                  accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
                  onChange={handleFileChange}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-bg-body)',
                    color: 'var(--color-text-main)',
                    fontSize: '0.85rem',
                    boxSizing: 'border-box',
                  }}
                />
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                  Supported formats: PDF, JPG, PNG, DOCX (Max 10MB)
                </div>
              </div>

              <div>
                <label
                  htmlFor="proof-name-input"
                  style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '4px' }}
                >
                  Document Name / Label
                </label>
                <input
                  id="proof-name-input"
                  type="text"
                  value={proofDocName}
                  onChange={(e) => setProofDocName(e.target.value)}
                  placeholder="e.g. LIC_Premium_Receipt_2025.pdf"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-bg-body)',
                    color: 'var(--color-text-main)',
                    fontSize: '0.85rem',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div>
                <label
                  htmlFor="proof-type-select"
                  style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '4px' }}
                >
                  Proof Type
                </label>
                <select
                  id="proof-type-select"
                  value={proofType}
                  onChange={(e) => setProofType(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-bg-body)',
                    color: 'var(--color-text-main)',
                    fontSize: '0.85rem',
                    boxSizing: 'border-box',
                  }}
                >
                  <option value="DOCUMENT">Standard Document</option>
                  <option value="RECEIPT">Payment Receipt</option>
                  <option value="STATEMENT">Bank / Financial Statement</option>
                  <option value="CERTIFICATE">Certificate / Policy Document</option>
                  <option value="OTHER">Other Proof</option>
                </select>
              </div>

              {uploadError && (
                <div style={{ color: 'var(--color-status-danger)', fontSize: '0.85rem', display: 'flex', gap: '6px' }}>
                  <AlertCircle size={15} style={{ flexShrink: 0, marginTop: '2px' }} />
                  <span>{uploadError}</span>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => setUploadProofItem(null)}
                  disabled={uploadSubmitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={uploadSubmitting || !proofFile}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                >
                  {uploadSubmitting ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}
                  Upload Proof
                </button>
              </div>
            </div>
          </form>
        </Modal>
      )}

      {/* ─── MODAL 4: CONFIRM SUBMISSION ─────────────────────────────────── */}
      {showSubmitModal && declaration && (
        <Modal
          title={`Submit Tax Declaration — ${declaration.financial_year_name}`}
          onClose={() => setShowSubmitModal(false)}
          size="md"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '8px 0' }}>
            <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--color-text-main)' }}>
              Are you sure you want to submit your tax declaration for review?
            </p>

            <div
              style={{
                backgroundColor: 'var(--color-bg-body)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-sm)',
                padding: '14px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                fontSize: '0.85rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>Financial Year:</span>
                <span style={{ fontWeight: 600 }}>{declaration.financial_year_name}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>Selected Tax Regime:</span>
                <span style={{ fontWeight: 600 }}>{declaration.tax_regime} REGIME</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>Investment Items:</span>
                <span style={{ fontWeight: 600 }}>{declaration.items?.length || 0}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>Total Declared Amount:</span>
                <span style={{ fontWeight: 700, color: 'var(--color-text-main)' }}>
                  {formatCurrency(declaration.total_declared_amount)}
                </span>
              </div>
            </div>

            <div
              style={{
                fontSize: '0.8rem',
                color: 'var(--color-text-muted)',
                lineHeight: 1.4,
                backgroundColor: 'rgba(234, 179, 8, 0.08)',
                padding: '10px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-status-warning)',
              }}
            >
              <strong>Important Notice:</strong> Once submitted, this declaration and attached proof files will become locked. You will not be able to modify investment items or regime selections unless returned by Finance. Verification and final tax impact are computed server-side by the payroll engine.
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '6px' }}>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setShowSubmitModal(false)}
                disabled={actionInProgress}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleSubmitDeclaration}
                disabled={actionInProgress}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              >
                {actionInProgress ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
                Confirm & Submit Declaration
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
