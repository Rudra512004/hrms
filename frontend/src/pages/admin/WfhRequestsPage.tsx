import React, { useState, useEffect } from 'react';
import { wfhService, type WfhRequest } from '../../services/wfh';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { Check, X, Ban, AlertCircle, Loader2 } from 'lucide-react';
import { authService } from '../../services/auth';

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
  const [requests, setRequests] = useState<WfhRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [modalState, setModalState] = useState<{ isOpen: boolean, type: 'approve' | 'reject', request: WfhRequest | null }>({ isOpen: false, type: 'approve', request: null });
  const [comment, setComment] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    authService.getCurrentUser().then(u => {

      if (u?.isStaff) {
        loadRequests();
      } else {
        setError("You do not have permission to view all WFH requests.");
        setLoading(false);
      }
    }).catch(() => {
      setError("Authentication error.");
      setLoading(false);
    });
  }, []);

  const loadRequests = async () => {
    setLoading(true);
    try {
      const data = await wfhService.getAll();
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
    { key: 'employee', title: 'Employee ID' },
    { 
      key: 'start_at', 
      title: 'Start Date',
      render: (r: WfhRequest) => new Date(r.start_at).toLocaleDateString()
    },
    { 
      key: 'end_at', 
      title: 'End Date',
      render: (r: WfhRequest) => new Date(r.end_at).toLocaleDateString()
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
            <button 
              style={{...styles.actionBtn, ...styles.btnApprove}} 
              onClick={() => { setModalState({ isOpen: true, type: 'approve', request: r }); setComment(''); }}
            >
              <Check size={14} style={{ marginRight: '4px' }} /> Approve
            </button>
            <button 
              style={{...styles.actionBtn, ...styles.btnReject}} 
              onClick={() => { setModalState({ isOpen: true, type: 'reject', request: r }); setComment(''); }}
            >
              <X size={14} style={{ marginRight: '4px' }} /> Reject
            </button>
            <button 
              style={{...styles.actionBtn, ...styles.btnCancel}} 
              onClick={() => handleCancel(r)}
            >
              <Ban size={14} style={{ marginRight: '4px' }} /> Cancel
            </button>
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
      </div>

      <Card>
        <Table data={requests} columns={columns} keyExtractor={(r) => r.id} />
      </Card>

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
