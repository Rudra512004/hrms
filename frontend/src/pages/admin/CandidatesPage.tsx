import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UserPlus, Search, Filter, Eye,
  AlertCircle, Loader2, FileText,
  RefreshCw,
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import {
  candidateService,
  type CandidateListItem,
  type CandidateStatus,
  type CreateCandidatePayload,
} from '../../services/candidates';

// ── Status helpers ──────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<CandidateStatus, { label: string; color: string; bg: string }> = {
  created:    { label: 'Created',         color: 'var(--color-text-muted)',           bg: 'var(--color-bg-body)' },
  offered:    { label: 'Offer Sent',      color: '#3b82f6',                           bg: '#eff6ff' },
  onboarding: { label: 'Onboarding',      color: '#f59e0b',                           bg: '#fffbeb' },
  submitted:  { label: 'Submitted',       color: '#8b5cf6',                           bg: '#f5f3ff' },
  verifying:  { label: 'Verifying',       color: '#0ea5e9',                           bg: '#f0f9ff' },
  approved:   { label: 'Approved',        color: 'var(--color-beyondsure-green)',      bg: '#f0fdf4' },
  converted:  { label: 'Converted',       color: 'var(--color-beyondsure-green)',      bg: '#dcfce7' },
  rejected:   { label: 'Rejected',        color: '#ef4444',                           bg: '#fef2f2' },
};

function StatusBadge({ status, display }: { status: CandidateStatus; display: string }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.created;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '3px 10px', borderRadius: '99px', fontSize: '0.75rem', fontWeight: 600,
      color: cfg.color, background: cfg.bg,
    }}>
      {display}
    </span>
  );
}

// ── Create Candidate Modal ──────────────────────────────────────────────────

interface CreateModalProps {
  onClose: () => void;
  onCreated: (c: CandidateListItem) => void;
}

function CreateCandidateModal({ onClose, onCreated }: CreateModalProps) {
  const [form, setForm] = useState<CreateCandidatePayload>({
    first_name: '', last_name: '', email: '',
    phone_number: '', address: '', notes: '',
    proposed_joining_date: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      const payload: CreateCandidatePayload = {
        ...form,
        proposed_joining_date: form.proposed_joining_date || null,
      };
      const created = await candidateService.createCandidate(payload);
      // Convert to list item shape
      onCreated({
        id: created.id,
        first_name: created.first_name,
        last_name: created.last_name,
        email: created.email,
        phone_number: created.phone_number,
        applied_designation: created.applied_designation,
        designation_name: created.designation_name,
        proposed_joining_date: created.proposed_joining_date,
        status: created.status,
        status_display: created.status_display,
        document_count: 0,
        created_at: created.created_at,
      });
    } catch (err: any) {
      setError(err.message || 'Failed to create candidate.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000, padding: '16px',
    }}>
      <div style={{
        background: 'var(--color-bg-card)', borderRadius: '12px',
        width: '100%', maxWidth: '540px', padding: '28px',
        boxShadow: 'var(--shadow-lg)', maxHeight: '90vh', overflowY: 'auto',
      }}>
        <h2 style={{ margin: '0 0 20px', fontSize: '1.1rem', color: 'var(--color-text-main)' }}>
          Add New Candidate
        </h2>

        {error && (
          <div style={{
            display: 'flex', gap: '8px', alignItems: 'flex-start',
            background: '#fef2f2', border: '1px solid #fecaca',
            borderRadius: '8px', padding: '12px', marginBottom: '16px',
            color: '#ef4444', fontSize: '0.875rem',
          }}>
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '1px' }} />
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
            {([
              { name: 'first_name', label: 'First Name', required: true },
              { name: 'last_name',  label: 'Last Name',  required: true },
            ] as any[]).map(f => (
              <div key={f.name}>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                  {f.label} {f.required && <span style={{ color: '#ef4444' }}>*</span>}
                </label>
                <input
                  name={f.name}
                  value={(form as any)[f.name]}
                  onChange={handleChange}
                  required={f.required}
                  style={{
                    width: '100%', padding: '9px 12px', border: '1px solid var(--color-border)',
                    borderRadius: '8px', background: 'var(--color-bg-body)',
                    color: 'var(--color-text-main)', fontSize: '0.9rem', boxSizing: 'border-box',
                  }}
                />
              </div>
            ))}
          </div>

          {([
            { name: 'email', label: 'Email Address', type: 'email', required: true },
            { name: 'phone_number', label: 'Phone Number', type: 'tel' },
            { name: 'proposed_joining_date', label: 'Proposed Joining Date', type: 'date' },
          ] as any[]).map(f => (
            <div key={f.name} style={{ marginTop: '14px' }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                {f.label} {f.required && <span style={{ color: '#ef4444' }}>*</span>}
              </label>
              <input
                type={f.type || 'text'}
                name={f.name}
                value={(form as any)[f.name]}
                onChange={handleChange}
                required={f.required}
                style={{
                  width: '100%', padding: '9px 12px', border: '1px solid var(--color-border)',
                  borderRadius: '8px', background: 'var(--color-bg-body)',
                  color: 'var(--color-text-main)', fontSize: '0.9rem', boxSizing: 'border-box',
                }}
              />
            </div>
          ))}

          <div style={{ marginTop: '14px' }}>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
              Notes
            </label>
            <textarea
              name="notes"
              value={form.notes}
              onChange={handleChange}
              rows={3}
              style={{
                width: '100%', padding: '9px 12px', border: '1px solid var(--color-border)',
                borderRadius: '8px', background: 'var(--color-bg-body)',
                color: 'var(--color-text-main)', fontSize: '0.9rem',
                resize: 'vertical', boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '24px' }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '9px 18px', border: '1px solid var(--color-border)',
                borderRadius: '8px', background: 'none',
                color: 'var(--color-text-main)', cursor: 'pointer', fontWeight: 500,
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              style={{
                padding: '9px 18px', border: 'none', borderRadius: '8px',
                background: 'var(--color-primary)', color: '#fff',
                cursor: saving ? 'not-allowed' : 'pointer', fontWeight: 600,
                opacity: saving ? 0.7 : 1, display: 'flex', alignItems: 'center', gap: '6px',
              }}
            >
              {saving && <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />}
              {saving ? 'Creating…' : 'Create Candidate'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main Candidates Page ────────────────────────────────────────────────────

export const CandidatesPage: React.FC = () => {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();

  const [candidates, setCandidates] = useState<CandidateListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);

  const PAGE_SIZE = 20;

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await candidateService.listCandidates({
        search: search || undefined,
        status: statusFilter || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setCandidates(res.results);
      setTotal(res.count);
    } catch (err: any) {
      setError(err.message || 'Failed to load candidates.');
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, page]);

  useEffect(() => { load(); }, [load]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const statusOptions: { value: string; label: string }[] = [
    { value: '', label: 'All Statuses' },
    { value: 'created',    label: 'Created' },
    { value: 'offered',    label: 'Offer Sent' },
    { value: 'onboarding', label: 'Onboarding' },
    { value: 'submitted',  label: 'Submitted' },
    { value: 'verifying',  label: 'Verifying' },
    { value: 'approved',   label: 'Approved' },
    { value: 'converted',  label: 'Converted' },
    { value: 'rejected',   label: 'Rejected' },
  ];

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
            Candidates
          </h1>
          <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>
            Manage the candidate onboarding workflow
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button
            onClick={load}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '8px 14px', border: '1px solid var(--color-border)',
              borderRadius: '8px', background: 'var(--color-bg-card)',
              color: 'var(--color-text-muted)', cursor: 'pointer', fontWeight: 500, fontSize: '0.875rem',
            }}
          >
            <RefreshCw size={14} />
            Refresh
          </button>
          {hasPermission('letter.view') && (
            <button
              onClick={() => navigate('/admin/candidates/templates')}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '8px 14px', border: '1px solid var(--color-border)',
                borderRadius: '8px', background: 'var(--color-bg-card)',
                color: 'var(--color-text-main)', cursor: 'pointer', fontWeight: 500, fontSize: '0.875rem',
              }}
            >
              <FileText size={14} />
              Letter Templates
            </button>
          )}
          {hasPermission('candidate.create') && (
            <button
              id="add-candidate-btn"
              onClick={() => setShowCreate(true)}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '8px 16px', border: 'none',
                borderRadius: '8px', background: 'var(--color-primary)',
                color: '#fff', cursor: 'pointer', fontWeight: 600, fontSize: '0.875rem',
              }}
            >
              <UserPlus size={15} />
              Add Candidate
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div style={{
        background: 'var(--color-bg-card)', borderRadius: '10px',
        padding: '14px 16px', marginBottom: '16px',
        display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center',
        border: '1px solid var(--color-border)',
      }}>
        <div style={{ position: 'relative', flex: '1', minWidth: '200px' }}>
          <Search size={15} style={{
            position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)',
            color: 'var(--color-text-muted)',
          }} />
          <input
            type="text"
            placeholder="Search by name or email…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            style={{
              width: '100%', padding: '8px 12px 8px 34px',
              border: '1px solid var(--color-border)', borderRadius: '8px',
              background: 'var(--color-bg-body)', color: 'var(--color-text-main)',
              fontSize: '0.875rem', boxSizing: 'border-box',
            }}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Filter size={14} style={{ color: 'var(--color-text-muted)' }} />
          <select
            value={statusFilter}
            onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
            style={{
              padding: '8px 12px', border: '1px solid var(--color-border)',
              borderRadius: '8px', background: 'var(--color-bg-body)',
              color: 'var(--color-text-main)', fontSize: '0.875rem',
            }}
          >
            {statusOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <span style={{ marginLeft: 'auto', color: 'var(--color-text-muted)', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>
          {total} candidate{total !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Table */}
      <div style={{
        background: 'var(--color-bg-card)', borderRadius: '10px',
        border: '1px solid var(--color-border)', overflow: 'hidden',
      }}>
        {error ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#ef4444' }}>
            <AlertCircle size={32} style={{ marginBottom: '8px' }} />
            <p>{error}</p>
          </div>
        ) : loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
            <Loader2 size={28} style={{ animation: 'spin 1s linear infinite', marginBottom: '8px' }} />
            <p style={{ margin: 0 }}>Loading candidates…</p>
          </div>
        ) : candidates.length === 0 ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
            <UserPlus size={36} style={{ opacity: 0.3, marginBottom: '12px' }} />
            <p style={{ margin: 0, fontWeight: 500 }}>No candidates found</p>
            <p style={{ margin: '4px 0 0', fontSize: '0.85rem' }}>
              {hasPermission('candidate.create') ? 'Click "Add Candidate" to get started.' : ''}
            </p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg-body)' }}>
                {['Name', 'Email', 'Designation', 'Joining Date', 'Status', 'Docs', 'Actions'].map(h => (
                  <th key={h} style={{
                    padding: '12px 16px', textAlign: 'left',
                    fontSize: '0.78rem', fontWeight: 700, letterSpacing: '0.04em',
                    color: 'var(--color-text-muted)', textTransform: 'uppercase',
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {candidates.map((c, i) => (
                <tr
                  key={c.id}
                  style={{
                    borderBottom: i < candidates.length - 1 ? '1px solid var(--color-border)' : 'none',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-bg-body)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <td style={{ padding: '13px 16px' }}>
                    <span style={{ fontWeight: 600, color: 'var(--color-text-main)', fontSize: '0.9rem' }}>
                      {c.first_name} {c.last_name}
                    </span>
                  </td>
                  <td style={{ padding: '13px 16px', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                    {c.email}
                  </td>
                  <td style={{ padding: '13px 16px', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                    {c.designation_name || '—'}
                  </td>
                  <td style={{ padding: '13px 16px', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                    {c.proposed_joining_date || '—'}
                  </td>
                  <td style={{ padding: '13px 16px' }}>
                    <StatusBadge status={c.status} display={c.status_display} />
                  </td>
                  <td style={{ padding: '13px 16px', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                    {c.document_count}
                  </td>
                  <td style={{ padding: '13px 16px' }}>
                    <button
                      onClick={() => navigate(`/admin/candidates/${c.id}`)}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: '4px',
                        padding: '6px 12px', border: '1px solid var(--color-border)',
                        borderRadius: '6px', background: 'none',
                        color: 'var(--color-primary)', cursor: 'pointer',
                        fontSize: '0.8rem', fontWeight: 500,
                      }}
                    >
                      <Eye size={12} /> View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{
            padding: '14px 16px', display: 'flex', justifyContent: 'space-between',
            alignItems: 'center', borderTop: '1px solid var(--color-border)',
          }}>
            <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
              Page {page} of {totalPages}
            </span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                style={{
                  padding: '6px 12px', border: '1px solid var(--color-border)',
                  borderRadius: '6px', background: 'none',
                  color: page === 1 ? 'var(--color-text-muted)' : 'var(--color-text-main)',
                  cursor: page === 1 ? 'not-allowed' : 'pointer', fontSize: '0.85rem',
                }}
              >
                Previous
              </button>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                style={{
                  padding: '6px 12px', border: '1px solid var(--color-border)',
                  borderRadius: '6px', background: 'none',
                  color: page === totalPages ? 'var(--color-text-muted)' : 'var(--color-text-main)',
                  cursor: page === totalPages ? 'not-allowed' : 'pointer', fontSize: '0.85rem',
                }}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {showCreate && (
        <CreateCandidateModal
          onClose={() => setShowCreate(false)}
          onCreated={c => {
            setCandidates(prev => [c, ...prev]);
            setShowCreate(false);
          }}
        />
      )}
    </div>
  );
};
