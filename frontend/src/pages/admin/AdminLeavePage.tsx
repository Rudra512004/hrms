import { useState, useEffect } from 'react';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { leaveService, type LeaveRequest } from '../../services/leaves';
import { AlertCircle, FileCheck2, Loader2, Check, X } from 'lucide-react';
import { authService, type User } from '../../services/auth';

const styles = {
  container: {
    padding: 'var(--spacing-xl)',
    maxWidth: '1200px',
    margin: '0 auto',
    width: '100%'
  },
  header: {
    marginBottom: 'var(--spacing-xl)'
  },
  title: {
    fontSize: '24px',
    fontWeight: 600,
    color: 'var(--color-text-main)',
    marginBottom: 'var(--spacing-xs)'
  },
  subtitle: {
    color: 'var(--color-text-muted)',
    fontSize: '14px'
  },
  alert: (type: 'error' | 'success') => ({
    padding: 'var(--spacing-md)',
    backgroundColor: type === 'error' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(34, 197, 94, 0.1)',
    color: type === 'error' ? 'var(--color-danger)' : 'var(--color-success)',
    borderRadius: '4px',
    marginBottom: 'var(--spacing-lg)',
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-sm)',
    border: `1px solid ${type === 'error' ? 'var(--color-danger)' : 'var(--color-success)'}`
  }),
  button: (variant: 'success' | 'danger' | 'secondary' = 'secondary') => ({
    padding: '6px 12px',
    backgroundColor: variant === 'success' ? 'var(--color-success)' : variant === 'danger' ? 'var(--color-danger)' : 'var(--color-bg-body)',
    color: variant === 'secondary' ? 'var(--color-text-main)' : 'white',
    border: variant === 'secondary' ? '1px solid var(--color-border)' : 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontWeight: 500,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '4px',
    fontSize: '13px',
    transition: 'opacity 0.2s',
  }),
  modal: {
    position: 'fixed' as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    padding: 'var(--spacing-xl)'
  },
  modalContent: {
    backgroundColor: 'var(--color-bg-card)',
    padding: 'var(--spacing-xl)',
    borderRadius: '8px',
    width: '100%',
    maxWidth: '500px',
    boxShadow: 'var(--shadow-lg)'
  },
  input: {
    width: '100%',
    padding: 'var(--spacing-sm)',
    border: '1px solid var(--color-border)',
    borderRadius: '4px',
    backgroundColor: 'var(--color-bg-input)',
    color: 'var(--color-text-main)',
    fontFamily: 'inherit',
    fontSize: '14px',
    marginBottom: 'var(--spacing-lg)'
  }
};

export function AdminLeavePage() {
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDenied, setIsDenied] = useState(false);
  
  // Review Modal State
  const [reviewModal, setReviewModal] = useState<{ isOpen: boolean; request: LeaveRequest | null; action: 'approve' | 'reject' | null }>({
    isOpen: false,
    request: null,
    action: null
  });
  const [reviewComment, setReviewComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [user, setUser] = useState<User | null>(null);

  const loadRequests = async () => {
    try {
      setLoading(true);
      setError(null);
      setIsDenied(false);
      const [u, data] = await Promise.all([
        authService.getCurrentUser(),
        leaveService.getRequests()
      ]);
      setUser(u);
      setRequests(data);
    } catch (err: any) {
      if (err.response?.status === 403) {
        setIsDenied(true);
      } else {
        setError("Failed to load leave requests.");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRequests();
  }, []);

  const openReviewModal = (request: LeaveRequest, action: 'approve' | 'reject') => {
    setReviewModal({ isOpen: true, request, action });
    setReviewComment('');
  };

  const handleReviewSubmit = async () => {
    if (!reviewModal.request || !reviewModal.action) return;
    
    try {
      setIsSubmitting(true);
      setError(null);
      if (reviewModal.action === 'approve') {
        await leaveService.approveRequest(reviewModal.request.id, reviewComment);
      } else {
        await leaveService.rejectRequest(reviewModal.request.id, reviewComment);
      }
      setReviewModal({ isOpen: false, request: null, action: null });
      await loadRequests();
    } catch (err: any) {
      setReviewModal({ isOpen: false, request: null, action: null });
      const msgs = err.errorData ? Object.values(err.errorData).flat().join(" ") : `Failed to ${reviewModal.action} request.`;
      setError(msgs);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isDenied) {
    return (
      <div style={styles.container}>
        <div style={{ textAlign: 'center', padding: '40px 20px' }}>
          <AlertCircle size={48} style={{ color: 'var(--color-danger)', margin: '0 auto 16px' }} />
          <h2 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--color-text-main)', marginBottom: '8px' }}>Access Denied</h2>
          <p style={{ color: 'var(--color-text-muted)' }}>You do not have permission to view or manage leave requests.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: '300px' }}>
        <Loader2 size={32} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
      </div>
    );
  }

  const columns = [
    { key: 'id', title: 'ID', render: (r: LeaveRequest) => `#${r.id}` },
    { key: 'employee', title: 'Employee ID' }, // In a real app we'd resolve employee name, but we only have ID here
    { key: 'leave_type_name', title: 'Leave Type' },
    { key: 'start_date', title: 'Start' },
    { key: 'end_date', title: 'End' },
    { key: 'duration_days', title: 'Days' },
    { 
      key: 'status', 
      title: 'Status',
      render: (r: LeaveRequest) => <StatusBadge status={r.status} />
    },
    {
      key: 'actions',
      title: 'Actions',
      render: (r: LeaveRequest) => {
        const isSelf = user?.id === r.employee.toString(); // Employee cannot approve own request
        return r.status === 'pending' ? (
          <div style={{ display: 'flex', gap: '8px' }}>
            <button 
              onClick={() => openReviewModal(r, 'approve')}
              style={{...styles.button('success'), opacity: isSelf ? 0.5 : 1}}
              disabled={isSelf}
              title={isSelf ? "Cannot approve your own request" : "Approve Request"}
            >
              <Check size={14} /> Approve
            </button>
            <button 
              onClick={() => openReviewModal(r, 'reject')}
              style={styles.button('danger')}
            >
              <X size={14} /> Reject
            </button>
          </div>
        ) : <span style={{ fontSize: '13px', color: 'var(--color-text-muted)' }}>{r.reviewer_comment || '-'}</span>;
      }
    }
  ];

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Leave Management</h1>
        <p style={styles.subtitle}>Review and manage employee leave requests.</p>
      </div>

      {error && (
        <div style={styles.alert('error')}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      <Card>
        <div style={{ padding: 'var(--spacing-lg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)', marginBottom: 'var(--spacing-lg)' }}>
            <FileCheck2 size={20} style={{ color: 'var(--color-primary)' }} />
            <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-text-main)' }}>All Leave Requests</h2>
          </div>
          <Table 
            columns={columns}
            data={requests}
            keyExtractor={(r) => r.id.toString()}
          />
        </div>
      </Card>

      {reviewModal.isOpen && (
        <div style={styles.modal}>
          <div style={styles.modalContent}>
            <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-text-main)', marginBottom: '16px' }}>
              {reviewModal.action === 'approve' ? 'Approve' : 'Reject'} Leave Request
            </h2>
            <p style={{ color: 'var(--color-text-muted)', marginBottom: '16px', fontSize: '14px' }}>
              You are about to {reviewModal.action} request #{reviewModal.request?.id}. You may provide an optional comment.
            </p>
            
            <label style={{ display: 'block', marginBottom: '8px', color: 'var(--color-text-main)', fontSize: '14px', fontWeight: 500 }}>
              Reviewer Comment (Optional)
            </label>
            <textarea
              style={{...styles.input, minHeight: '80px', resize: 'vertical'}}
              value={reviewComment}
              onChange={e => setReviewComment(e.target.value)}
              placeholder="Enter your comment here..."
            />

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button 
                style={styles.button('secondary')} 
                onClick={() => setReviewModal({ isOpen: false, request: null, action: null })}
                disabled={isSubmitting}
              >
                Cancel
              </button>
              <button 
                style={reviewModal.action === 'approve' ? styles.button('success') : styles.button('danger')} 
                onClick={handleReviewSubmit}
                disabled={isSubmitting}
              >
                {isSubmitting ? <Loader2 size={14} className="animate-spin" /> : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
