import React, { useState } from 'react';
import { Modal } from '../Modal';
import {
  employeeManagementService,
  ApiError,
} from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import { Loader2, AlertCircle, CheckCircle, FileText } from 'lucide-react';

interface ReactivateModalProps {
  employee: EmployeeProfile;
  onClose: () => void;
  onSuccess: (updated: EmployeeProfile) => void;
}

export const ReactivateModal: React.FC<ReactivateModalProps> = ({
  employee,
  onClose,
  onSuccess,
}) => {
  const [reason, setReason] = useState<string>('Reactivated via explicit workflow');
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSubmitting(true);

    try {
      const updated = await employeeManagementService.reactivateEmployee(employee.id, {
        reason: reason.trim() || undefined,
      });
      onSuccess(updated);
    } catch (err: any) {
      if (err instanceof ApiError || err.status || err.response?.status) {
        const status = err.status || err.response?.status;
        const errorData = err.errorData || {};

        if (status === 403) {
          setErrorMessage(errorData.detail || 'Permission denied: You do not have permission to reactivate employees.');
        } else if (status === 400) {
          setErrorMessage(errorData.detail || 'Only exited employees can be reactivated.');
        } else if (status === 404) {
          setErrorMessage('Employee not found.');
        } else {
          setErrorMessage(err.message || 'Failed to reactivate employee.');
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
      title="Reactivate Exited Employee"
      onClose={onClose}
      size="sm"
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
            disabled={submitting}
            data-testid="submit-reactivate-btn"
          >
            {submitting ? (
              <>
                <Loader2 size={16} className="animate-spin" /> Reactivating...
              </>
            ) : (
              'Confirm Reactivation'
            )}
          </button>
        </div>
      }
    >
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{
          padding: '12px 14px',
          backgroundColor: 'var(--color-status-success-bg, #ecfdf5)',
          border: '1px solid var(--color-status-success-border, #a7f3d0)',
          borderRadius: 'var(--radius-md, 8px)',
          color: 'var(--color-status-success, #059669)',
          fontSize: '0.85rem',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '8px',
        }}>
          <CheckCircle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <strong>Employee Reactivation:</strong> This workflow will restore the employee's status to{' '}
            <strong>Active</strong>, re-enable their system user account, and clear any historical exit or resignation dates.
          </div>
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
            data-testid="reactivate-error-box"
          >
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>{errorMessage}</span>
          </div>
        )}

        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <FileText size={14} color="var(--color-text-muted)" /> Reactivation Reason / Notes
          </label>
          <textarea
            className="input-field"
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={submitting}
            placeholder="Reason for rehire or reactivation"
            data-testid="reactivate-reason-input"
            style={{ resize: 'vertical' }}
          />
        </div>
      </form>
    </Modal>
  );
};
