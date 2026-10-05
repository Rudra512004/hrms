import React, { useState, useEffect } from 'react';
import {
  UserCheck,
  Plus,
  Calendar,
  Loader2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Trash2,
  Power,
  RefreshCw,
  X,
  Send,
} from 'lucide-react';
import { Card } from '../components/Card';
import {
  approvalDelegationService,
  type ApprovalDelegation,
  type CreateDelegationPayload,
} from '../services/approvalDelegation';
import { useAuth } from '../contexts/AuthContext';

const DELEGATE_TYPES = [
  { id: 'leave', label: 'Leave Requests' },
  { id: 'wfh', label: 'WFH Requests' },
  { id: 'attendance', label: 'Attendance & Regularization' },
  { id: 'timesheet', label: 'Timesheet Approvals' },
];

export const ApprovalDelegationPage: React.FC = () => {
  const { user } = useAuth();

  const [delegations, setDelegations] = useState<ApprovalDelegation[]>([]);
  const [employees, setEmployees] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [actionInProgressId, setActionInProgressId] = useState<number | null>(null);

  const [form, setForm] = useState({
    delegate: '',
    valid_from: new Date().toISOString().split('T')[0],
    valid_until: '',
    delegate_types: ['leave', 'wfh'] as string[],
  });

  const fetchDelegations = () => {
    setLoading(true);
    setError(null);
    approvalDelegationService
      .list()
      .then((data) => {
        setDelegations(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        console.error('Failed to load approval delegations:', err);
        setError('Unable to load approval delegations.');
      })
      .finally(() => {
        setLoading(false);
      });
  };

  // Load employees for delegate dropdown (filtered to active colleagues)
  useEffect(() => {
    fetchDelegations();

    const token = localStorage.getItem('auth_token');
    fetch('/api/v1/employees/?page_size=100', {
      headers: token ? { Authorization: `Token ${token}` } : {},
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        const list = Array.isArray(data) ? data : data.results || [];
        // Filter out current user from potential delegates
        const filtered = list.filter((emp: any) => String(emp.user_id) !== String(user?.id));
        setEmployees(filtered);
        if (filtered.length > 0 && !form.delegate) {
          setForm((prev) => ({ ...prev, delegate: String(filtered[0].user_id) }));
        }
      })
      .catch((err) => {
        console.error('Could not load employees for delegate selection:', err);
      });
  }, [user?.id]);

  const handleToggleType = (typeId: string) => {
    setForm((prev) => {
      const exists = prev.delegate_types.includes(typeId);
      const updated = exists
        ? prev.delegate_types.filter((t) => t !== typeId)
        : [...prev.delegate_types, typeId];
      return { ...prev, delegate_types: updated };
    });
  };

  const handleCreateDelegation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.delegate) {
      setError('Please select a delegate colleague.');
      return;
    }
    if (form.delegate_types.length === 0) {
      setError('Please select at least one approval type to delegate.');
      return;
    }
    if (form.valid_until && form.valid_from > form.valid_until) {
      setError('Valid Until date must be on or after Valid From date.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const payload: CreateDelegationPayload = {
        delegate: Number(form.delegate),
        valid_from: form.valid_from,
        valid_until: form.valid_until || null,
        delegate_types: form.delegate_types,
        is_active: true,
      };

      await approvalDelegationService.create(payload);
      setIsModalOpen(false);
      setForm({
        delegate: employees[0]?.user_id ? String(employees[0].user_id) : '',
        valid_from: new Date().toISOString().split('T')[0],
        valid_until: '',
        delegate_types: ['leave', 'wfh'],
      });
      fetchDelegations();
    } catch (err: any) {
      console.error('Failed to create delegation:', err);
      setError(err?.message || 'Failed to create approval delegation.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (del: ApprovalDelegation) => {
    setActionInProgressId(del.id);
    setError(null);
    try {
      const updated = await approvalDelegationService.update(del.id, {
        is_active: !del.is_active,
      });
      setDelegations((prev) => prev.map((d) => (d.id === del.id ? updated : d)));
    } catch (err: any) {
      console.error('Failed to update delegation status:', err);
      setError(err?.message || 'Failed to update delegation.');
    } finally {
      setActionInProgressId(null);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this approval delegation?')) return;
    setActionInProgressId(id);
    setError(null);
    try {
      await approvalDelegationService.delete(id);
      setDelegations((prev) => prev.filter((d) => d.id !== id));
    } catch (err: any) {
      console.error('Failed to delete delegation:', err);
      setError(err?.message || 'Failed to delete delegation.');
    } finally {
      setActionInProgressId(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      {/* Header bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <h1
            style={{
              margin: 0,
              fontSize: 'var(--font-size-2xl)',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <UserCheck size={26} color="var(--color-primary)" />
            Approval Delegation
          </h1>
          <p className="text-muted" style={{ margin: '4px 0 0 0' }}>
            Temporarily transfer your managerial approval duties (Leaves, WFH, Timesheets) to a designated colleague.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary" onClick={fetchDelegations} type="button">
            <RefreshCw size={15} />
          </button>
          <button className="btn btn-primary" onClick={() => setIsModalOpen(true)} type="button">
            <Plus size={18} /> New Delegation
          </button>
        </div>
      </div>

      {error && (
        <Card>
          <div
            style={{
              padding: 14,
              color: 'var(--color-status-danger)',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        </Card>
      )}

      {/* Delegation Content */}
      {loading ? (
        <Card>
          <div style={{ padding: 48, textAlign: 'center' }}>
            <Loader2 size={32} className="animate-spin" color="var(--color-primary)" />
            <p className="text-muted" style={{ marginTop: 12 }}>
              Loading delegations...
            </p>
          </div>
        </Card>
      ) : delegations.length === 0 ? (
        <Card>
          <div style={{ padding: '48px 24px', textAlign: 'center' }}>
            <UserCheck size={42} color="var(--color-text-muted)" style={{ margin: '0 auto 12px' }} />
            <h3 style={{ margin: 0 }}>No Active Delegations</h3>
            <p className="text-muted" style={{ maxWidth: 440, margin: '8px auto 16px' }}>
              You have not assigned any approval delegations. When stepping away for vacation or leave, assign a peer to prevent approval bottlenecks.
            </p>
            <button
              className="btn btn-primary"
              onClick={() => setIsModalOpen(true)}
              type="button"
            >
              <Plus size={16} /> Create Delegation
            </button>
          </div>
        </Card>
      ) : (
        <div style={{ display: 'grid', gap: 'var(--spacing-md)' }}>
          {delegations.map((del) => {
            const isSelfDelegated = String(del.delegator) === String(user?.id);
            const isProcessing = actionInProgressId === del.id;

            return (
              <Card key={del.id}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    flexWrap: 'wrap',
                    gap: 16,
                  }}
                >
                  <div style={{ display: 'flex', gap: 14, minWidth: 0, flex: 1 }}>
                    <div
                      style={{
                        width: 42,
                        height: 42,
                        borderRadius: '10px',
                        background: del.is_active
                          ? 'var(--color-primary-light, rgba(2, 132, 199, 0.1))'
                          : 'var(--color-bg-subtle, #f1f5f9)',
                        color: del.is_active ? 'var(--color-primary, #0284c7)' : 'var(--color-text-muted)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        marginTop: 2,
                      }}
                    >
                      <UserCheck size={22} />
                    </div>

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <strong style={{ fontSize: '1.05rem', color: 'var(--color-text-main)' }}>
                          Delegate: {del.delegate_name}
                        </strong>

                        <span
                          style={{
                            fontSize: '0.75rem',
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: '6px',
                            background: del.is_active
                              ? 'rgba(5, 150, 105, 0.12)'
                              : 'rgba(100, 116, 139, 0.12)',
                            color: del.is_active ? '#059669' : '#64748b',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                          }}
                        >
                          {del.is_active ? (
                            <>
                              <CheckCircle2 size={12} /> Active
                            </>
                          ) : (
                            <>
                              <XCircle size={12} /> Inactive / Revoked
                            </>
                          )}
                        </span>

                        {!isSelfDelegated && (
                          <span
                            style={{
                              fontSize: '0.75rem',
                              padding: '2px 8px',
                              borderRadius: '6px',
                              background: 'var(--color-bg-subtle, #f1f5f9)',
                              color: 'var(--color-text-muted)',
                            }}
                          >
                            Granted by: {del.delegator_name}
                          </span>
                        )}
                      </div>

                      {/* Period info */}
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          fontSize: '0.86rem',
                          color: 'var(--color-text-sub)',
                          margin: '6px 0 10px',
                        }}
                      >
                        <Calendar size={14} color="var(--color-text-muted)" />
                        <span>
                          Valid: <strong>{del.valid_from}</strong> to{' '}
                          <strong>{del.valid_until || 'Indefinite'}</strong>
                        </span>
                      </div>

                      {/* Delegation Types */}
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {del.delegate_types.map((type) => (
                          <span
                            key={type}
                            style={{
                              fontSize: '0.75rem',
                              fontWeight: 600,
                              padding: '3px 9px',
                              borderRadius: '6px',
                              background: 'var(--color-bg-subtle, #f1f5f9)',
                              color: 'var(--color-text-main, #334155)',
                              border: '1px solid var(--color-border-subtle, #e2e8f0)',
                              textTransform: 'capitalize',
                            }}
                          >
                            {type}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                    <button
                      type="button"
                      className={`btn ${del.is_active ? 'btn-secondary' : 'btn-primary'}`}
                      disabled={isProcessing}
                      onClick={() => handleToggleActive(del)}
                      style={{ fontSize: '0.82rem', display: 'inline-flex', alignItems: 'center', gap: 6 }}
                    >
                      {isProcessing ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <Power size={14} />
                      )}
                      {del.is_active ? 'Deactivate' : 'Reactivate'}
                    </button>

                    <button
                      type="button"
                      className="btn btn-secondary"
                      disabled={isProcessing}
                      onClick={() => handleDelete(del.id)}
                      style={{
                        padding: '8px 10px',
                        color: 'var(--color-status-danger, #ef4444)',
                      }}
                      title="Delete delegation"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create Delegation Modal */}
      {isModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'grid',
            placeItems: 'center',
            zIndex: 1000,
            padding: 16,
          }}
        >
          <Card style={{ width: 'min(540px, 100%)', maxHeight: '90vh', overflowY: 'auto' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 16,
              }}
            >
              <h2 style={{ margin: 0, fontSize: '1.25rem' }}>Create Approval Delegation</h2>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateDelegation} style={{ display: 'grid', gap: 14 }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 4 }}>
                  Select Delegate Colleague
                </label>
                {employees.length > 0 ? (
                  <select
                    className="input-neumorphic"
                    value={form.delegate}
                    onChange={(e) => setForm({ ...form, delegate: e.target.value })}
                    required
                    style={{ width: '100%', height: 38 }}
                  >
                    {employees.map((emp) => (
                      <option key={emp.id} value={emp.user_id}>
                        {emp.first_name} {emp.last_name} ({emp.employee_code}) ·{' '}
                        {emp.designation_name || emp.department_name || emp.email}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="number"
                    className="input-neumorphic"
                    placeholder="Enter delegate user ID"
                    value={form.delegate}
                    onChange={(e) => setForm({ ...form, delegate: e.target.value })}
                    required
                    style={{ width: '100%' }}
                  />
                )}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 4 }}>
                    Valid From
                  </label>
                  <input
                    type="date"
                    className="input-neumorphic"
                    required
                    value={form.valid_from}
                    onChange={(e) => setForm({ ...form, valid_from: e.target.value })}
                    style={{ width: '100%', height: 38 }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 4 }}>
                    Valid Until (Optional)
                  </label>
                  <input
                    type="date"
                    className="input-neumorphic"
                    value={form.valid_until}
                    onChange={(e) => setForm({ ...form, valid_until: e.target.value })}
                    style={{ width: '100%', height: 38 }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 8 }}>
                  Delegated Approval Capabilities
                </label>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: 8,
                  }}
                >
                  {DELEGATE_TYPES.map((type) => {
                    const isChecked = form.delegate_types.includes(type.id);
                    return (
                      <label
                        key={type.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          padding: '8px 12px',
                          borderRadius: '8px',
                          border: `1px solid ${
                            isChecked ? 'var(--color-primary)' : 'var(--color-border)'
                          }`,
                          background: isChecked
                            ? 'var(--color-primary-light, rgba(2, 132, 199, 0.08))'
                            : 'transparent',
                          cursor: 'pointer',
                          fontSize: '0.85rem',
                          fontWeight: isChecked ? 600 : 400,
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => handleToggleType(type.id)}
                        />
                        <span>{type.label}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsModalOpen(false)}
                  disabled={submitting}
                >
                  Cancel
                </button>
                <button className="btn btn-primary" disabled={submitting}>
                  {submitting ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Send size={16} />
                  )}
                  Save Delegation
                </button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
};
