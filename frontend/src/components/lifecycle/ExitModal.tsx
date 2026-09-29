import React, { useState } from 'react';
import { Modal } from '../Modal';
import {
  employeeManagementService,
  type EmployeeExitPayload,
  type EmployeeExitType,
  ApiError,
} from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import { Loader2, AlertCircle, AlertTriangle, UserX, Clock, Calendar, FileText } from 'lucide-react';

interface ExitModalProps {
  employee: EmployeeProfile;
  onClose: () => void;
  onSuccess: (updated: EmployeeProfile) => void;
}

export const ExitModal: React.FC<ExitModalProps> = ({
  employee,
  onClose,
  onSuccess,
}) => {
  const [actionType, setActionType] = useState<'notice' | 'exit'>('exit');
  const [exitType, setExitType] = useState<EmployeeExitType>('resignation');
  const [exitDate, setExitDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [resignationDate, setResignationDate] = useState<string>('');
  const [noticePeriodStart, setNoticePeriodStart] = useState<string>('');
  const [noticePeriodEnd, setNoticePeriodEnd] = useState<string>('');
  const [exitReason, setExitReason] = useState<string>('');

  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setFieldErrors({});

    const errors: Record<string, string> = {};
    if (!exitDate) {
      errors.exit_date = 'Exit date is required.';
    }

    if (noticePeriodStart && noticePeriodEnd && noticePeriodEnd < noticePeriodStart) {
      errors.notice_period_end = 'Notice period end date cannot be before start date.';
    }

    if (resignationDate && exitDate && exitDate < resignationDate) {
      errors.exit_date = 'Exit date cannot be before resignation date.';
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setSubmitting(true);

    const payload: EmployeeExitPayload = {
      exit_type: exitType,
      exit_date: exitDate,
      set_notice_status: actionType === 'notice',
    };

    if (exitReason.trim()) payload.exit_reason = exitReason.trim();
    if (resignationDate) payload.resignation_date = resignationDate;
    if (noticePeriodStart) payload.notice_period_start = noticePeriodStart;
    if (noticePeriodEnd) payload.notice_period_end = noticePeriodEnd;

    try {
      const updated = await employeeManagementService.exitEmployee(employee.id, payload);
      onSuccess(updated);
    } catch (err: any) {
      if (err instanceof ApiError || err.status || err.response?.status) {
        const status = err.status || err.response?.status;
        const errorData = err.errorData || {};

        if (status === 403) {
          setErrorMessage(errorData.detail || 'Permission denied: You do not have permission to manage employee exits.');
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
              setErrorMessage('Please correct the validation errors below.');
            } else {
              setErrorMessage('Validation error occurred.');
            }
          } else {
            setErrorMessage(String(errorData) || 'Invalid exit request.');
          }
        } else if (status === 404) {
          setErrorMessage('Employee not found.');
        } else {
          setErrorMessage(err.message || 'Failed to complete exit workflow.');
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
      title={actionType === 'notice' ? 'Initiate Notice Period' : 'Process Employee Exit'}
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
            className={actionType === 'exit' ? 'btn btn-danger' : 'btn btn-primary'}
            onClick={handleSubmit}
            disabled={submitting}
            data-testid="submit-exit-btn"
          >
            {submitting ? (
              <>
                <Loader2 size={16} className="animate-spin" /> Processing...
              </>
            ) : actionType === 'exit' ? (
              'Confirm Employee Exit'
            ) : (
              'Set On Notice'
            )}
          </button>
        </div>
      }
    >
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Workflow Type Selector Tabs */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '8px',
          padding: '4px',
          backgroundColor: 'var(--color-bg-secondary, #f1f5f9)',
          borderRadius: 'var(--radius-lg, 10px)',
        }}>
          <button
            type="button"
            onClick={() => {
              setActionType('exit');
              setErrorMessage(null);
            }}
            disabled={submitting}
            style={{
              padding: '10px 14px',
              border: 'none',
              borderRadius: 'var(--radius-md, 8px)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              fontSize: '0.85rem',
              fontWeight: 600,
              backgroundColor: actionType === 'exit' ? 'var(--color-bg-card, #ffffff)' : 'transparent',
              color: actionType === 'exit' ? 'var(--color-status-danger, #dc2626)' : 'var(--color-text-muted)',
              boxShadow: actionType === 'exit' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              transition: 'all 0.15s ease',
            }}
            data-testid="tab-exit-final"
          >
            <UserX size={16} /> Final Separation / Exit
          </button>
          <button
            type="button"
            onClick={() => {
              setActionType('notice');
              setErrorMessage(null);
            }}
            disabled={submitting}
            style={{
              padding: '10px 14px',
              border: 'none',
              borderRadius: 'var(--radius-md, 8px)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              fontSize: '0.85rem',
              fontWeight: 600,
              backgroundColor: actionType === 'notice' ? 'var(--color-bg-card, #ffffff)' : 'transparent',
              color: actionType === 'notice' ? 'var(--color-status-warning, #d97706)' : 'var(--color-text-muted)',
              boxShadow: actionType === 'notice' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              transition: 'all 0.15s ease',
            }}
            data-testid="tab-exit-notice"
          >
            <Clock size={16} /> Initiate Notice Period
          </button>
        </div>

        {/* Warning / Informational Callout */}
        {actionType === 'exit' ? (
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
              <strong>Final Separation Warning:</strong> Confirming this exit will mark the employee as{' '}
              <strong>Exited</strong> and immediately deactivate their user account. Exited employees will be excluded from future payroll runs.
            </div>
          </div>
        ) : (
          <div style={{
            padding: '12px 14px',
            backgroundColor: 'var(--color-status-warning-bg, #fffbeb)',
            border: '1px solid var(--color-status-warning-border, #fde68a)',
            borderRadius: 'var(--radius-md, 8px)',
            color: 'var(--color-status-warning, #d97706)',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '8px',
          }}>
            <Clock size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong>Notice Period:</strong> The employee will be transitioned to <strong>On Notice</strong> status. Their system account will remain active throughout their notice period.
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
            data-testid="exit-error-box"
          >
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Exit Type */}
        <div>
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            Exit Type *
          </label>
          <select
            className="input-field"
            value={exitType}
            onChange={(e) => setExitType(e.target.value as EmployeeExitType)}
            disabled={submitting}
            required
            data-testid="exit-type-select"
          >
            <option value="resignation">Resignation</option>
            <option value="termination">Termination</option>
            <option value="end_of_contract">End of Contract</option>
            <option value="retirement">Retirement</option>
            <option value="other">Other</option>
          </select>
        </div>

        {/* Exit Date */}
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <Calendar size={14} color="var(--color-text-muted)" /> Exit Date *
          </label>
          <input
            type="date"
            className="input-field"
            value={exitDate}
            onChange={(e) => {
              setExitDate(e.target.value);
              setFieldErrors(prev => ({ ...prev, exit_date: '' }));
            }}
            disabled={submitting}
            required
            data-testid="exit-date-input"
          />
          {fieldErrors.exit_date && (
            <span style={{ color: 'var(--color-status-danger, #dc2626)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
              {fieldErrors.exit_date}
            </span>
          )}
        </div>

        {/* Resignation Date (Optional) */}
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <Calendar size={14} color="var(--color-text-muted)" /> Resignation Date (Optional)
          </label>
          <input
            type="date"
            className="input-field"
            value={resignationDate}
            onChange={(e) => setResignationDate(e.target.value)}
            disabled={submitting}
            data-testid="exit-resignation-date"
          />
        </div>

        {/* Notice Period Dates */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
              <Calendar size={14} color="var(--color-text-muted)" /> Notice Start
            </label>
            <input
              type="date"
              className="input-field"
              value={noticePeriodStart}
              onChange={(e) => setNoticePeriodStart(e.target.value)}
              disabled={submitting}
              data-testid="exit-notice-start"
            />
          </div>
          <div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
              <Calendar size={14} color="var(--color-text-muted)" /> Notice End
            </label>
            <input
              type="date"
              className="input-field"
              value={noticePeriodEnd}
              onChange={(e) => {
                setNoticePeriodEnd(e.target.value);
                setFieldErrors(prev => ({ ...prev, notice_period_end: '' }));
              }}
              disabled={submitting}
              data-testid="exit-notice-end"
            />
            {fieldErrors.notice_period_end && (
              <span style={{ color: 'var(--color-status-danger, #dc2626)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
                {fieldErrors.notice_period_end}
              </span>
            )}
          </div>
        </div>

        {/* Exit Reason */}
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <FileText size={14} color="var(--color-text-muted)" /> Reason / Notes (Optional)
          </label>
          <textarea
            className="input-field"
            rows={2}
            value={exitReason}
            onChange={(e) => setExitReason(e.target.value)}
            disabled={submitting}
            placeholder="e.g. Higher education, relocation, contract completion"
            data-testid="exit-reason-input"
            style={{ resize: 'vertical' }}
          />
        </div>
      </form>
    </Modal>
  );
};
