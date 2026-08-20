import React, { useState, useEffect } from 'react';
import { Card } from '../components/Card';
import { Table } from '../components/Table';
import { StatusBadge } from '../components/StatusBadge';
import { leaveService, type LeaveType, type LeaveBalance, type LeaveRequest } from '../services/leaves';
import { AlertCircle, Calendar, PlusCircle, Loader2 } from 'lucide-react';

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
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: 'var(--spacing-lg)',
    marginBottom: 'var(--spacing-xl)'
  },
  button: () => ({
    // Kept for backward compatibility just in case, but overridden by className in JSX
  }),
  formGroup: {
    marginBottom: 'var(--spacing-md)'
  },
  label: {
    display: 'block',
    marginBottom: 'var(--spacing-xs)',
    color: 'var(--color-text-main)',
    fontWeight: 500,
    fontSize: '14px'
  },
  input: {},
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
  })
};

export function LeavePage() {
  const [types, setTypes] = useState<LeaveType[]>([]);
  const [balances, setBalances] = useState<LeaveBalance[]>([]);
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const activeTypes = types.filter(t => t.is_active);

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [formType, setFormType] = useState('');
  const [formStart, setFormStart] = useState('');
  const [formEnd, setFormEnd] = useState('');
  const [formReason, setFormReason] = useState('');
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [t, b, r] = await Promise.all([
        leaveService.getLeaveTypes(),
        leaveService.getBalances(),
        leaveService.getRequests()
      ]);
      setTypes(t);
      setBalances(b);
      setRequests(r);
    } catch {
      setError("Failed to load leave data. Please try again later.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formType || !formStart || !formEnd || !formReason) {
      setFormError("All fields are required.");
      return;
    }
    try {
      setFormSubmitting(true);
      setFormError(null);
      await leaveService.createRequest({
        leave_type: parseInt(formType),
        start_date: formStart,
        end_date: formEnd,
        reason: formReason
      });
      setShowForm(false);
      setFormType('');
      setFormStart('');
      setFormEnd('');
      setFormReason('');
      await loadData();
    } catch (err: any) {
      const msgs = err.errorData ? Object.values(err.errorData).flat().join(" ") : "Failed to create request.";
      setFormError(msgs);
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleCancel = async (id: number) => {
    if (!confirm("Are you sure you want to cancel this request?")) return;
    try {
      await leaveService.cancelRequest(id);
      await loadData();
    } catch {
      alert("Failed to cancel request.");
    }
  };

  const columns = [
    { key: 'leave_type_name', title: 'Leave Type' },
    { key: 'start_date', title: 'Start Date' },
    { key: 'end_date', title: 'End Date' },
    { key: 'reason', title: 'Reason' },
    {
      key: 'status',
      title: 'Status',
      render: (r: LeaveRequest) => <StatusBadge status={r.status} />
    },
    {
      key: 'reviewer_comment',
      title: 'Comments',
      render: (r: LeaveRequest) => <span style={{ fontSize: '13px', color: 'var(--color-text-muted)' }}>{r.reviewer_comment || '-'}</span>
    },
    {
      key: 'actions',
      title: 'Actions',
      render: (r: LeaveRequest) => r.status === 'pending' ? (
        <button
          onClick={() => handleCancel(r.id)}
          className="btn btn-danger"
          style={{ padding: '4px 8px', fontSize: '12px' }}
        >
          Cancel
        </button>
      ) : null
    }
  ];

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: '300px' }}>
        <Loader2 size={32} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1 style={styles.title}>Leave Management</h1>
            <p style={styles.subtitle}>View your balances and manage leave requests.</p>
          </div>
          <button
            className="btn btn-primary"
            onClick={() => setShowForm(!showForm)}
          >
            <PlusCircle size={18} />
            {showForm ? 'Cancel Request' : 'New Leave Request'}
          </button>
        </div>
      </div>

      {error && (
        <div style={styles.alert('error')}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      {showForm && (
        <Card>
          <div style={{ padding: 'var(--spacing-lg)' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: 'var(--spacing-lg)', color: 'var(--color-text-main)' }}>Create Leave Request</h2>

            {formError && (
              <div style={styles.alert('error')}>
                <AlertCircle size={18} />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleCreateRequest}>
              <div style={styles.grid}>
                <div style={styles.formGroup}>
                  <label style={styles.label}>Leave Type</label>
                  {activeTypes.length === 0 ? (
                    <div style={{ padding: '10px 14px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-md)', color: 'var(--color-text-muted)', fontSize: '14px', boxShadow: 'var(--shadow-inset)' }}>
                      No leave types are currently configured. Please contact HR.
                    </div>
                  ) : (
                    <select
                      className="input-neumorphic"
                      value={formType}
                      onChange={e => setFormType(e.target.value)}
                      required
                    >
                      <option value="">Select a leave type</option>
                      {activeTypes.map(t => (
                        <option key={t.id} value={t.id}>{t.name} (Allocated: {t.annual_allocation})</option>
                      ))}
                    </select>
                  )}
                </div>

                <div style={styles.formGroup}>
                  <label style={styles.label}>Start Date</label>
                  <input
                    type="date"
                    className="input-neumorphic"
                    value={formStart}
                    onChange={e => setFormStart(e.target.value)}
                    required
                  />
                </div>

                <div style={styles.formGroup}>
                  <label style={styles.label}>End Date</label>
                  <input
                    type="date"
                    className="input-neumorphic"
                    value={formEnd}
                    onChange={e => setFormEnd(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>Reason</label>
                <textarea
                  className="input-neumorphic"
                  style={{ minHeight: '100px', resize: 'vertical' }}
                  value={formReason}
                  onChange={e => setFormReason(e.target.value)}
                  placeholder="Provide a reason for your leave request..."
                  required
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--spacing-md)', marginTop: 'var(--spacing-lg)' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={formSubmitting || activeTypes.length === 0}>
                  {formSubmitting ? <Loader2 size={18} className="animate-spin" /> : 'Submit Request'}
                </button>
              </div>
            </form>
          </div>
        </Card>
      )}

      {!showForm && (
        <>
          <div style={{ marginBottom: 'var(--spacing-xl)' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: 'var(--spacing-lg)', color: 'var(--color-text-main)' }}>Your Balances</h2>
            <div style={styles.grid}>
              {balances.map(b => (
                <Card key={b.id}>
                  <div style={{ padding: 'var(--spacing-lg)' }}>
                    <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--color-text-main)', marginBottom: 'var(--spacing-md)' }}>
                      {b.leave_type_name}
                    </h3>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--spacing-xs)' }}>
                      <span style={{ color: 'var(--color-text-muted)', fontSize: '14px' }}>Allocated</span>
                      <span style={{ fontWeight: 500, color: 'var(--color-text-main)' }}>{b.allocated} days</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--spacing-xs)' }}>
                      <span style={{ color: 'var(--color-text-muted)', fontSize: '14px' }}>Used</span>
                      <span style={{ fontWeight: 500, color: 'var(--color-text-main)' }}>{b.used} days</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 'var(--spacing-sm)', paddingTop: 'var(--spacing-sm)', borderTop: '1px solid var(--color-border)' }}>
                      <span style={{ fontWeight: 600, color: 'var(--color-text-main)' }}>Remaining</span>
                      <span style={{ fontWeight: 600, color: 'var(--color-primary)' }}>{b.remaining} days</span>
                    </div>
                  </div>
                </Card>
              ))}
              {balances.length === 0 && (
                <p style={{ color: 'var(--color-text-muted)', gridColumn: '1 / -1' }}>No leave balances available.</p>
              )}
            </div>
          </div>

          <Card>
            <div style={{ padding: 'var(--spacing-lg)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)', marginBottom: 'var(--spacing-lg)' }}>
                <Calendar size={20} style={{ color: 'var(--color-primary)' }} />
                <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-text-main)' }}>Request History</h2>
              </div>
              <Table
                columns={columns}
                data={requests}
                keyExtractor={(r) => r.id.toString()}
              />
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
