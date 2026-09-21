import React, { useState, useEffect } from 'react';
import { Modal } from '../Modal';
import { organizationService, type Designation } from '../../services/organization';
import {
  employeeManagementService,
  type EmployeePromotionPayload,
  ApiError,
} from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import { Loader2, AlertCircle, Briefcase, Calendar, DollarSign, FileText, ArrowRight } from 'lucide-react';

interface PromotionModalProps {
  employee: EmployeeProfile;
  onClose: () => void;
  onSuccess: (updated: EmployeeProfile) => void;
}

export const PromotionModal: React.FC<PromotionModalProps> = ({
  employee,
  onClose,
  onSuccess,
}) => {
  const [designations, setDesignations] = useState<Designation[]>([]);
  const [selectedDesignationId, setSelectedDesignationId] = useState<number | ''>('');
  const [effectiveDate, setEffectiveDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [newBasicSalary, setNewBasicSalary] = useState<string>('');
  const [reason, setReason] = useState<string>('');

  const [loadingInitial, setLoadingInitial] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    let isMounted = true;
    const loadDesignations = async () => {
      setLoadingInitial(true);
      try {
        const list = await organizationService.listDesignations().catch(() => []);
        if (isMounted) {
          setDesignations(list || []);
        }
      } finally {
        if (isMounted) setLoadingInitial(false);
      }
    };
    loadDesignations();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setFieldErrors({});

    const errors: Record<string, string> = {};
    if (!selectedDesignationId) {
      errors.designation = 'New designation is required.';
    }
    if (!effectiveDate) {
      errors.effective_date = 'Effective date is required.';
    }
    if (newBasicSalary.trim() !== '') {
      const parsedSalary = parseFloat(newBasicSalary);
      if (isNaN(parsedSalary) || parsedSalary < 0) {
        errors.new_basic_salary = 'Basic salary must be a positive number.';
      }
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setSubmitting(true);

    const payload: EmployeePromotionPayload = {
      designation: Number(selectedDesignationId),
      effective_date: effectiveDate,
    };

    if (newBasicSalary.trim()) {
      payload.new_basic_salary = newBasicSalary.trim();
    }
    if (reason.trim()) {
      payload.reason = reason.trim();
    }

    try {
      const updated = await employeeManagementService.promoteEmployee(employee.id, payload);
      onSuccess(updated);
    } catch (err: any) {
      if (err instanceof ApiError || err.status || err.response?.status) {
        const status = err.status || err.response?.status;
        const errorData = err.errorData || {};

        if (status === 403) {
          setErrorMessage(errorData.detail || 'Permission denied: You do not have permission to promote employees.');
        } else if (status === 400) {
          if (typeof errorData === 'object' && errorData !== null) {
            const nextErrors: Record<string, string> = {};
            const nonFieldMsgs: string[] = [];

            for (const [k, v] of Object.entries(errorData)) {
              const msg = Array.isArray(v) ? v.join(' ') : String(v);
              if (k === 'detail' || k === 'non_field_errors') {
                nonFieldMsgs.push(msg);
              } else {
                nextErrors[k] = msg;
              }
            }

            setFieldErrors(nextErrors);
            if (nonFieldMsgs.length > 0) {
              setErrorMessage(nonFieldMsgs.join(' | '));
            } else if (Object.keys(nextErrors).length > 0) {
              setErrorMessage('Please resolve the validation errors below.');
            } else {
              setErrorMessage('Validation error occurred.');
            }
          } else {
            setErrorMessage(String(errorData) || 'Invalid promotion request.');
          }
        } else if (status === 404) {
          setErrorMessage('Employee or designation not found.');
        } else {
          setErrorMessage(err.message || 'Failed to promote employee.');
        }
      } else {
        setErrorMessage(err?.message || 'Network error occurred. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="Promote Employee"
      onClose={onClose}
      size="md"
      footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', width: '100%' }}>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={onClose}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={submitting || loadingInitial}
            data-testid="submit-promotion-btn"
          >
            {submitting ? (
              <>
                <Loader2 size={16} className="animate-spin" /> Promoting...
              </>
            ) : (
              'Confirm Promotion'
            )}
          </button>
        </div>
      }
    >
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Current Designation Card */}
        <div style={{
          padding: '12px 16px',
          backgroundColor: 'var(--color-bg-secondary, #f1f5f9)',
          borderRadius: 'var(--radius-md, 8px)',
          border: '1px solid var(--color-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div>
            <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--color-text-muted)', fontWeight: 600, display: 'block', marginBottom: '2px' }}>
              Current Designation
            </span>
            <span style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--color-text-main)' }}>
              {employee.designation_name || 'Unassigned'}
            </span>
          </div>
          {selectedDesignationId && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-primary)' }}>
              <ArrowRight size={18} />
              <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                {designations.find(d => d.id === selectedDesignationId)?.name || ''}
              </span>
            </div>
          )}
        </div>

        {errorMessage && (
          <div
            style={{
              padding: '12px 14px',
              backgroundColor: 'var(--color-status-danger-bg, #fef2f2)',
              border: '1px solid var(--color-status-danger-border, #fecaca)',
              borderRadius: 'var(--radius-md, 8px)',
              color: 'var(--color-status-danger, #dc2626)',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '8px',
            }}
            data-testid="promotion-error-box"
          >
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* New Designation Selector */}
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <Briefcase size={14} color="var(--color-text-muted)" /> New Designation *
          </label>
          <select
            className="input-field"
            value={selectedDesignationId}
            onChange={(e) => {
              setSelectedDesignationId(e.target.value ? Number(e.target.value) : '');
              setFieldErrors(prev => ({ ...prev, designation: '' }));
            }}
            disabled={submitting || loadingInitial}
            required
            data-testid="promotion-designation-select"
          >
            <option value="">-- Select New Designation --</option>
            {designations.map(d => (
              <option key={d.id} value={d.id}>
                {d.name} {!d.is_active ? '(Inactive)' : ''}
              </option>
            ))}
          </select>
          {fieldErrors.designation && (
            <span style={{ color: 'var(--color-status-danger, #dc2626)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
              {fieldErrors.designation}
            </span>
          )}
        </div>

        {/* Effective Date */}
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <Calendar size={14} color="var(--color-text-muted)" /> Effective Date *
          </label>
          <input
            type="date"
            className="input-field"
            value={effectiveDate}
            onChange={(e) => {
              setEffectiveDate(e.target.value);
              setFieldErrors(prev => ({ ...prev, effective_date: '' }));
            }}
            disabled={submitting}
            required
            data-testid="promotion-effective-date"
          />
          {fieldErrors.effective_date && (
            <span style={{ color: 'var(--color-status-danger, #dc2626)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
              {fieldErrors.effective_date}
            </span>
          )}
        </div>

        {/* New Basic Salary (Optional) */}
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <DollarSign size={14} color="var(--color-text-muted)" /> New Basic Salary (Optional)
          </label>
          <input
            type="number"
            step="0.01"
            min="0"
            className="input-field"
            placeholder="e.g. 75000.00"
            value={newBasicSalary}
            onChange={(e) => {
              setNewBasicSalary(e.target.value);
              setFieldErrors(prev => ({ ...prev, new_basic_salary: '' }));
            }}
            disabled={submitting}
            data-testid="promotion-salary-input"
          />
          {fieldErrors.new_basic_salary && (
            <span style={{ color: 'var(--color-status-danger, #dc2626)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
              {fieldErrors.new_basic_salary}
            </span>
          )}
          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '4px', display: 'block' }}>
            If specified, this creates a new compensation history record effective on the promotion date.
          </span>
        </div>

        {/* Reason */}
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <FileText size={14} color="var(--color-text-muted)" /> Reason (Optional)
          </label>
          <textarea
            className="input-field"
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={submitting}
            placeholder="e.g. Annual performance appraisal, merit promotion"
            data-testid="promotion-reason"
            style={{ resize: 'vertical' }}
          />
        </div>
      </form>
    </Modal>
  );
};
