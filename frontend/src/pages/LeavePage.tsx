import React, { useState, useEffect } from 'react';
import { Card } from '../components/Card';
import { Table } from '../components/Table';
import { StatusBadge } from '../components/StatusBadge';
import { PageHeader } from '../components/PageHeader';
import { Modal } from '../components/Modal';
import { AlertBanner } from '../components/AlertBanner';
import { leaveService, type LeaveType, type LeaveBalance, type LeaveRequest } from '../services/leaves';
import { Calendar, PlusCircle, Loader2, CalendarDays } from 'lucide-react';
import { EmptyState } from '../components/EmptyState';

export function LeavePage() {
  const [types, setTypes] = useState<LeaveType[]>([]);
  const [balances, setBalances] = useState<LeaveBalance[]>([]);
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const activeTypes = types.filter((t) => t.is_active);

  // Form state
  const [showModal, setShowModal] = useState(false);
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
        leaveService.getRequests(),
      ]);
      setTypes(t);
      setBalances(b);
      setRequests(r);
    } catch {
      setError('Failed to load leave data. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const openModal = () => {
    setFormType('');
    setFormStart('');
    setFormEnd('');
    setFormReason('');
    setFormError(null);
    setShowModal(true);
  };

  const handleCreateRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formType || !formStart || !formEnd || !formReason) {
      setFormError('All fields are required.');
      return;
    }
    try {
      setFormSubmitting(true);
      setFormError(null);
      await leaveService.createRequest({
        leave_type: parseInt(formType),
        start_date: formStart,
        end_date: formEnd,
        reason: formReason,
      });
      setShowModal(false);
      await loadData();
    } catch (err: any) {
      const msgs = err.errorData
        ? Object.values(err.errorData).flat().join(' ')
        : 'Failed to create request.';
      setFormError(msgs);
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleCancel = async (id: number) => {
    if (!confirm('Are you sure you want to cancel this request?')) return;
    try {
      await leaveService.cancelRequest(id);
      await loadData();
    } catch {
      alert('Failed to cancel request.');
    }
  };

  const columns = [
    { key: 'leave_type_name', title: 'Type' },
    {
      key: 'start_date',
      title: 'Start',
      render: (r: LeaveRequest) => (
        <span style={{ whiteSpace: 'nowrap' }}>{r.start_date}</span>
      ),
    },
    {
      key: 'end_date',
      title: 'End',
      render: (r: LeaveRequest) => (
        <span style={{ whiteSpace: 'nowrap' }}>{r.end_date}</span>
      ),
    },
    {
      key: 'reason',
      title: 'Reason',
      render: (r: LeaveRequest) => (
        <span
          style={{
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
            maxWidth: 280,
          }}
        >
          {r.reason}
        </span>
      ),
    },
    {
      key: 'status',
      title: 'Status',
      render: (r: LeaveRequest) => <StatusBadge status={r.status} />,
    },
    {
      key: 'reviewer_comment',
      title: 'Note',
      render: (r: LeaveRequest) => (
        <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
          {r.reviewer_comment || '—'}
        </span>
      ),
    },
    {
      key: 'actions',
      title: '',
      render: (r: LeaveRequest) =>
        r.status === 'pending' ? (
          <button
            onClick={() => handleCancel(r.id)}
            className="btn btn-sm btn-secondary"
            style={{ color: 'var(--color-status-danger)', borderColor: 'var(--color-status-danger-border)' }}
          >
            Cancel
          </button>
        ) : null,
    },
  ];

  if (loading) {
    return (
      <div className="loading-center">
        <Loader2 size={28} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
        <span>Loading leave data…</span>
      </div>
    );
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      <PageHeader
        title="My Leave"
        subtitle="Manage your leave balances and requests."
        actions={
          <button className="btn btn-primary" onClick={openModal} type="button">
            <PlusCircle size={16} />
            New Request
          </button>
        }
      />

      {error && <AlertBanner type="error" message={error} />}

      {/* Balances */}
      <div>
        <h2
          style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 600,
            marginBottom: 'var(--spacing-md)',
            color: 'var(--color-text-main)',
          }}
        >
          Leave Balances
        </h2>
        {balances.length === 0 ? (
          <Card>
            <EmptyState
              icon={Calendar}
              title="No balances"
              description="You don't have any active leave balances configured."
            />
          </Card>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
              gap: 'var(--spacing-md)',
            }}
          >
            {balances.map((b) => {
              const pct = b.allocated > 0 ? Math.round(((b.allocated - b.remaining) / b.allocated) * 100) : 0;
              return (
                <div
                  key={b.id}
                  className="card"
                  style={{
                    padding: 'var(--spacing-md)',
                    borderTop: '3px solid var(--color-primary)',
                    boxShadow: 'var(--shadow-sm)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: 'var(--spacing-md)' }}>
                    <div
                      style={{
                        width: 38,
                        height: 38,
                        borderRadius: 'var(--radius-md)',
                        backgroundColor: 'var(--color-primary-light)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Calendar size={18} color="var(--color-primary)" />
                    </div>
                    <div>
                      <span style={{ fontWeight: 600, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-main)', display: 'block' }}>
                        {b.leave_type_name}
                      </span>
                      <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                        Annual Allowance
                      </span>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div
                    style={{
                      height: 7,
                      backgroundColor: 'var(--color-border)',
                      borderRadius: 'var(--radius-full)',
                      marginBottom: '10px',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${pct}%`,
                        background: pct > 80 ? 'var(--color-status-danger)' : 'linear-gradient(90deg, var(--color-primary) 0%, var(--color-secondary) 100%)',
                        borderRadius: 'var(--radius-full)',
                        transition: 'width 0.4s ease',
                      }}
                    />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                    <span>Used: <b style={{ color: 'var(--color-text-main)' }}>{b.used}</b></span>
                    <span>
                      Remaining:{' '}
                      <b style={{ color: 'var(--color-primary)', fontWeight: 700 }}>{b.remaining}</b> / {b.allocated} days
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Request History */}
      <Card
        title="Request History"
        noPadding
      >
        <Table
          columns={columns}
          data={requests}
          keyExtractor={(r) => r.id.toString()}
          emptyIcon={CalendarDays}
          emptyTitle="No leave requests"
          emptyDescription="You haven't submitted any leave requests yet."
        />
      </Card>

      {/* Request Modal */}
      {showModal && (
        <Modal
          title="New Leave Request"
          onClose={() => setShowModal(false)}
          footer={
            <>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowModal(false)}
              >
                Cancel
              </button>
              <button
                type="submit"
                form="leave-request-form"
                className="btn btn-primary"
                disabled={formSubmitting || activeTypes.length === 0}
              >
                {formSubmitting ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : null}
                Submit Request
              </button>
            </>
          }
        >
          {formError && (
            <AlertBanner type="error" message={formError} style={{ marginBottom: 'var(--spacing-md)' }} />
          )}

          <form id="leave-request-form" onSubmit={handleCreateRequest}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="leave-type">Leave Type</label>
                {activeTypes.length === 0 ? (
                  <AlertBanner type="warning" message="No active leave types are configured. Contact HR." />
                ) : (
                  <select
                    id="leave-type"
                    className="input-field"
                    value={formType}
                    onChange={(e) => setFormType(e.target.value)}
                    required
                  >
                    <option value="">Select a leave type</option>
                    {activeTypes.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name} (Annual: {t.annual_allocation} days)
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-md)' }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="leave-start">Start Date</label>
                  <input
                    id="leave-start"
                    type="date"
                    className="input-field"
                    value={formStart}
                    onChange={(e) => setFormStart(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="leave-end">End Date</label>
                  <input
                    id="leave-end"
                    type="date"
                    className="input-field"
                    value={formEnd}
                    min={formStart}
                    onChange={(e) => setFormEnd(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="leave-reason">Reason</label>
                <textarea
                  id="leave-reason"
                  className="input-field"
                  style={{ minHeight: 100 }}
                  value={formReason}
                  onChange={(e) => setFormReason(e.target.value)}
                  placeholder="Provide a reason for your leave request…"
                  required
                />
              </div>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
