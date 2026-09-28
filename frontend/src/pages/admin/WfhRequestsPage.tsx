import React, { useState, useEffect } from 'react';
import { wfhService, type WfhRequest } from '../../services/wfh';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { Check, X, Ban, AlertCircle, Loader2, Plus } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { Modal } from '../../components/Modal';
import { AlertBanner } from '../../components/AlertBanner';


const styles = {
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 'var(--spacing-lg)',
  },
  title: {
    margin: 0,
    fontSize: '1.25rem',
    color: 'var(--color-text-main)',
  },
  actionBtn: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: '4px 8px',
    color: 'var(--color-text-main)',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: '8px',
    borderRadius: 'var(--radius-sm)',
    fontSize: '0.85rem',
    fontWeight: 500,
  },
  btnApprove: {
    backgroundColor: 'rgba(40, 199, 111, 0.1)',
    color: 'var(--color-status-success)',
  },
  btnReject: {
    backgroundColor: 'rgba(234, 84, 85, 0.1)',
    color: 'var(--color-status-danger)',
  },
  btnCancel: {
    backgroundColor: 'rgba(168, 170, 174, 0.1)',
    color: 'var(--color-text-muted)',
  },
  modalOverlay: {
    position: 'fixed' as const,
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  modalContent: {
    backgroundColor: 'var(--color-bg-card)',
    padding: 'var(--spacing-xl)',
    borderRadius: 'var(--radius-lg)',
    width: '100%',
    maxWidth: '450px',
    boxShadow: 'var(--shadow-lg)',
  },
  formGroup: {
    marginBottom: 'var(--spacing-md)',
  },
  label: {
    display: 'block',
    marginBottom: '8px',
    fontWeight: 500,
    fontSize: '0.9rem',
  },
  input: {
    width: '100%',
    padding: '10px 12px',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-md)',
    backgroundColor: 'var(--color-bg-body)',
    color: 'var(--color-text-main)',
    fontSize: '0.95rem',
  },
  modalActions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
    marginTop: 'var(--spacing-xl)',
  },
  cancelBtn: {
    backgroundColor: 'transparent',
    color: 'var(--color-text-main)',
    border: '1px solid var(--color-border)',
    padding: '8px 16px',
    borderRadius: 'var(--radius-md)',
    cursor: 'pointer',
  },
  confirmBtn: {
    backgroundColor: 'var(--color-primary)',
    color: '#fff',
    border: 'none',
    padding: '8px 16px',
    borderRadius: 'var(--radius-md)',
    cursor: 'pointer',
    fontWeight: 500,
  },
  errorBox: {
    backgroundColor: 'rgba(234, 84, 85, 0.1)',
    color: 'var(--color-status-danger)',
    padding: '12px',
    borderRadius: 'var(--radius-md)',
    marginBottom: '16px',
    fontSize: '0.9rem',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  }
};

export const WfhRequestsPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const [requests, setRequests] = useState<WfhRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'approved' | 'rejected' | 'cancelled'>('all');

  const [modalState, setModalState] = useState<{ isOpen: boolean, type: 'approve' | 'reject', request: WfhRequest | null }>({ isOpen: false, type: 'approve', request: null });
  const [comment, setComment] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  // New WFH request state
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [newStartAt, setNewStartAt] = useState('');
  const [newEndAt, setNewEndAt] = useState('');
  const [newReason, setNewReason] = useState('');
  const [newSubmitting, setNewSubmitting] = useState(false);
  const [newError, setNewError] = useState<string | null>(null);

  useEffect(() => {
    loadRequests('all');
  }, []);

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStartAt || !newEndAt || !newReason.trim()) {
      setNewError('All fields are required.');
      return;
    }
    const start = new Date(newStartAt);
    const end = new Date(newEndAt);
    if (end <= start) {
      setNewError('End date/time must be strictly after start date/time.');
      return;
    }

    try {
      setNewSubmitting(true);
      setNewError(null);
      await wfhService.create({
        start_at: start.toISOString(),
        end_at: end.toISOString(),
        reason: newReason.trim(),
      });
      setIsNewModalOpen(false);
      setNewStartAt('');
      setNewEndAt('');
      setNewReason('');
      await loadRequests();
    } catch (err: any) {
      const msgs = err.errorData
        ? Object.values(err.errorData).flat().join(' ')
        : 'Failed to submit WFH request.';
      setNewError(msgs);
    } finally {
      setNewSubmitting(false);
    }
  };

  const loadRequests = async (status = statusFilter) => {
    setLoading(true);
    try {
      const data = await wfhService.getAll({ status: status === 'all' ? undefined : status });
      setRequests(data);
      setError(null);
    } catch (err: any) {
      if (err.response?.status === 403) {
        setError("403 Forbidden: You do not have permission.");
      } else {
        setError("Failed to load WFH requests.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async () => {
    if (!modalState.request) return;
    setActionLoading(true);
    try {
      if (modalState.type === 'approve') {
        await wfhService.approve(modalState.request.id, comment);
      } else {
        await wfhService.reject(modalState.request.id, comment);
      }
      setModalState({ isOpen: false, type: 'approve', request: null });
      setComment('');
      loadRequests();
    } catch (err: any) {
      alert(err.errorData?.detail || "An error occurred.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async (req: WfhRequest) => {
    if (!window.confirm("Are you sure you want to cancel this request?")) return;
    try {
      await wfhService.cancel(req.id);
      loadRequests();
    } catch (err: any) {
      alert(err.errorData?.detail || "An error occurred.");
    }
  };

  const columns = [
    {
      key: 'employee',
      title: 'Employee',
      render: (r: WfhRequest) => (
        <div>
          <div style={{ fontWeight: 500 }}>{r.employee_name || `Employee #${r.employee}`}</div>
          {r.employee_code && (
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{r.employee_code}</div>
          )}
        </div>
      ),
    },
    {
      key: 'start_at',
      title: 'Start',
      render: (r: WfhRequest) => new Date(r.start_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }),
    },
    {
      key: 'end_at',
      title: 'End',
      render: (r: WfhRequest) => new Date(r.end_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }),
    },
    { key: 'reason', title: 'Reason' },
    {
      key: 'status',
      title: 'Status',
      render: (r: WfhRequest) => <StatusBadge status={r.status as any} />
    },
    {
      key: 'actions',
      title: 'Actions',
      render: (r: WfhRequest) => {
        if (r.status !== 'pending') return <span style={{ color: 'var(--color-text-muted)' }}>-</span>;

        return (
          <div>
            {hasPermission('wfh.approve') && (
              <button
                style={{...styles.actionBtn, ...styles.btnApprove}}
                onClick={() => { setModalState({ isOpen: true, type: 'approve', request: r }); setComment(''); }}
              >
                <Check size={14} style={{ marginRight: '4px' }} /> Approve
              </button>
            )}
            {hasPermission('wfh.reject') && (
              <button
                style={{...styles.actionBtn, ...styles.btnReject}}
                onClick={() => { setModalState({ isOpen: true, type: 'reject', request: r }); setComment(''); }}
              >
                <X size={14} style={{ marginRight: '4px' }} /> Reject
              </button>
            )}
            {hasPermission('wfh.cancel') && (
              <button
                style={{...styles.actionBtn, ...styles.btnCancel}}
                onClick={() => handleCancel(r)}
              >
                <Ban size={14} style={{ marginRight: '4px' }} /> Cancel
              </button>
            )}
          </div>
        );
      }
    }
  ];

  if (loading && requests.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  if (error && requests.length === 0) {
    return (
      <Card>
        <div style={styles.errorBox}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      </Card>
    );
  }

  return (
    <div>
      <div style={styles.header}>
        <h1 style={styles.title}>WFH Requests</h1>
        {hasPermission('wfh.request') && (
          <button
            className="btn btn-primary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}
            onClick={() => {
              setNewStartAt('');
              setNewEndAt('');
              setNewReason('');
              setNewError(null);
              setIsNewModalOpen(true);
            }}
          >
            <Plus size={16} />
            <span>New WFH Request</span>
          </button>
        )}
      </div>

      <div style={{ display: 'flex', gap: '8px', marginBottom: 'var(--spacing-md)' }}>
        {(['all', 'pending', 'approved', 'rejected', 'cancelled'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            className={`btn ${statusFilter === tab ? 'btn-primary' : 'btn-secondary'}`}
            style={{ textTransform: 'capitalize', fontSize: '0.85rem', padding: '6px 14px' }}
            onClick={() => {
              setStatusFilter(tab);
              loadRequests(tab);
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      <Card>
        <Table data={requests} columns={columns} keyExtractor={(r) => r.id} />
      </Card>

      {isNewModalOpen && (
        <Modal
          onClose={() => setIsNewModalOpen(false)}
          title="New WFH Request"
          footer={
            <>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setIsNewModalOpen(false)}
              >
                Cancel
              </button>
              <button
                type="submit"
                form="wfh-request-form"
                className="btn btn-primary"
                disabled={newSubmitting}
              >
                {newSubmitting ? <Loader2 size={16} className="animate-spin" /> : null}
                Submit Request
              </button>
            </>
          }
        >
          {newError && (
            <AlertBanner type="error" message={newError} style={{ marginBottom: 'var(--spacing-md)' }} />
          )}

          <form id="wfh-request-form" onSubmit={handleCreateSubmit}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="wfh-start">Start Date &amp; Time</label>
                <input
                  id="wfh-start"
                  type="datetime-local"
                  className="form-control"
                  value={newStartAt}
                  onChange={(e) => setNewStartAt(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="wfh-end">End Date &amp; Time</label>
                <input
                  id="wfh-end"
                  type="datetime-local"
                  className="form-control"
                  value={newEndAt}
                  onChange={(e) => setNewEndAt(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="wfh-reason">Reason</label>
                <textarea
                  id="wfh-reason"
                  className="form-control"
                  rows={3}
                  value={newReason}
                  onChange={(e) => setNewReason(e.target.value)}
                  placeholder="Provide a reason for working from home..."
                  required
                />
              </div>
            </div>
          </form>
        </Modal>
      )}

      {modalState.isOpen && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <h2 style={{ marginTop: 0 }}>
              {modalState.type === 'approve' ? 'Approve Request' : 'Reject Request'}
            </h2>

            <div style={styles.formGroup}>
              <label style={styles.label}>Reviewer Comment (Optional)</label>
              <textarea
                style={{ ...styles.input, minHeight: '80px', resize: 'vertical' }}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Add an optional comment..."
              />
            </div>

            <div style={styles.modalActions}>
              <button style={styles.cancelBtn} onClick={() => setModalState({ isOpen: false, type: 'approve', request: null })}>
                Cancel
              </button>
              <button
                style={{
                  ...styles.confirmBtn,
                  backgroundColor: modalState.type === 'approve' ? 'var(--color-status-success)' : 'var(--color-status-danger)'
                }}
                onClick={handleAction}
                disabled={actionLoading}
              >
                {actionLoading ? <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }}/> : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
