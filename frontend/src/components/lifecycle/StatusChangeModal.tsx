import React, { useState } from 'react';
import { Modal } from '../Modal';
import {
  employeeManagementService,
  ApiError,
} from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import { Loader2, AlertCircle, AlertTriangle, Power, FileText } from 'lucide-react';

interface StatusChangeModalProps {
  employee: EmployeeProfile;
  onClose: () => void;
  onSuccess: (updated: EmployeeProfile) => void;
}

const STATUS_CHOICES = [
  { value: 'onboarding', label: 'Onboarding' },
  { value: 'active', label: 'Active' },
  { value: 'on_notice', label: 'On Notice' },
  { value: 'on_leave', label: 'On Leave' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'exited', label: 'Exited' },
];

export const StatusChangeModal: React.FC<StatusChangeModalProps> = ({
  employee,
  onClose,
  onSuccess,
}) => {
  const currentStatus = employee.employment_status || employee.status || 'active';
  const isExited = currentStatus === 'exited';

  const [selectedStatus, setSelectedStatus] = useState<string>(currentStatus);
  const [reason, setReason] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (isExited) {
      setErrorMessage(
        'Exited employees cannot be transitioned via regular status update. Please use the explicit Reactivate workflow.'
      );
      return;
    }

    if (selectedStatus === currentStatus) {
      setErrorMessage('Please select a different employment status.');
      return;
    }

    setSubmitting(true);

    try {
      const updated = await employeeManagementService.changeEmploymentStatus(employee.id, {
        employment_status: selectedStatus,
        reason: reason.trim() || undefined,
      });
      onSuccess(updated);
    } catch (err: any) {
      if (err instanceof ApiError || err.status || err.response?.status) {
        const status = err.status || err.response?.status;
        const errorData = err.errorData || {};

        if (status === 403) {
          setErrorMessage(errorData.detail || 'Permission denied: You do not have permission to change employee lifecycle status.');
        } else if (status === 400) {
          setErrorMessage(errorData.detail || errorData.employment_status || 'Invalid status change request.');
        } else if (status === 404) {
          setErrorMessage('Employee not found.');
        } else {
          setErrorMessage(err.message || 'Failed to update status.');
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
      title="Change Employment Status"
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
            className={selectedStatus === 'exited' || selectedStatus === 'inactive' ? 'btn btn-danger' : 'btn btn-primary'}
            onClick={handleSubmit}
            disabled={submitting || isExited}
            data-testid="submit-status-btn"
          >
            {submitting ? (
              <>
                <Loader2 size={16} className="animate-spin" /> Updating...
              </>
            ) : (
              'Save Status'
            )}
          </button>
        </div>
      }
    >
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {isExited && (
          <div style={{
            padding: '12px 14px',
            backgroundColor: 'var(--color-status-danger-bg, #fef2f2)',
            border: '1px solid var(--color-status-danger-border, #fecaca)',
            borderRadius: 'var(--radius-md, 8px)',
            color: 'var(--color-status-danger, #dc2626)',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '8px',
          }}>
            <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong>Action Restricted:</strong> This employee is marked as Exited. Exited employees cannot be transitioned via regular status update. Please use the <strong>Reactivate</strong> action instead.
            </div>
          </div>
        )}

        {selectedStatus === 'exited' && !isExited && (
          <div style={{
            padding: '12px 14px',
            backgroundColor: 'var(--color-status-danger-bg, #fef2f2)',
            border: '1px solid var(--color-status-danger-border, #fecaca)',
            borderRadius: 'var(--radius-md, 8px)',
            color: 'var(--color-status-danger, #dc2626)',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '8px',
          }}>
            <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong>Warning:</strong> Transitioning to Exited will immediately deactivate the employee's system user account.
            </div>
          </div>
        )}

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
            data-testid="status-error-box"
          >
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>{errorMessage}</span>
          </div>
        )}

        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <Power size={14} color="var(--color-text-muted)" /> New Employment Status *
          </label>
          <select
            className="input-field"
            value={selectedStatus}
            onChange={(e) => {
              setSelectedStatus(e.target.value);
              setErrorMessage(null);
            }}
            disabled={submitting || isExited}
            required
            data-testid="status-select"
          >
            {STATUS_CHOICES.map(c => (
              <option key={c.value} value={c.value}>
                {c.label} {c.value === currentStatus ? '(Current)' : ''}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <FileText size={14} color="var(--color-text-muted)" /> Reason (Optional)
          </label>
          <textarea
            className="input-field"
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={submitting || isExited}
            placeholder="Reason for status modification"
            data-testid="status-reason-input"
            style={{ resize: 'vertical' }}
          />
        </div>
      </form>
    </Modal>
  );
};
