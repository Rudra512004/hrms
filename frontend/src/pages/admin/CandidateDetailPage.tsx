import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Send, CheckCircle, XCircle, UserCheck, FileText,
  AlertCircle, Loader2, ChevronDown, ChevronUp,
  Clock
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import {
  candidateService,
  type Candidate,
  type CandidateStatus,
} from '../../services/candidates';

// ── Helpers ─────────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<CandidateStatus, string> = {
  created: '#94a3b8', offered: '#3b82f6', onboarding: '#f59e0b',
  submitted: '#8b5cf6', verifying: '#0ea5e9',
  approved: 'var(--color-beyondsure-green)', converted: 'var(--color-beyondsure-green)',
  rejected: '#ef4444',
};

function StatusBadge({ status, display }: { status: CandidateStatus; display: string }) {
  return (
    <span style={{
      display: 'inline-block', padding: '4px 12px',
      borderRadius: '99px', fontSize: '0.8rem', fontWeight: 700,
      color: '#fff', background: STATUS_COLOR[status] || '#94a3b8',
    }}>
      {display}
    </span>
  );
}

function DocumentStatusBadge({ status }: { status: string }) {
  const colors: Record<string, { bg: string; color: string }> = {
    pending:  { bg: '#fffbeb', color: '#f59e0b' },
    verified: { bg: '#f0fdf4', color: 'var(--color-beyondsure-green)' },
    rejected: { bg: '#fef2f2', color: '#ef4444' },
  };
  const cfg = colors[status] || colors.pending;
  return (
    <span style={{
      padding: '2px 8px', borderRadius: '99px', fontSize: '0.75rem', fontWeight: 600,
      background: cfg.bg, color: cfg.color,
    }}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function Section({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{
      background: 'var(--color-bg-card)', borderRadius: '10px',
      border: '1px solid var(--color-border)', marginBottom: '16px',
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', justifyContent: 'space-between',
          alignItems: 'center', padding: '14px 18px', border: 'none',
          background: 'none', cursor: 'pointer', color: 'var(--color-text-main)',
          fontWeight: 600, fontSize: '0.95rem',
        }}
      >
        {title}
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {open && <div style={{ padding: '0 18px 18px' }}>{children}</div>}
    </div>
  );
}

// ── Action Button ────────────────────────────────────────────────────────────

function ActionButton({
  icon: Icon, label, onClick, color = 'var(--color-primary)',
  disabled = false, loading = false,
}: {
  icon: React.ElementType; label: string; onClick: () => void;
  color?: string; disabled?: boolean; loading?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: '6px',
        padding: '8px 16px', border: 'none', borderRadius: '8px',
        background: color, color: '#fff', cursor: (disabled || loading) ? 'not-allowed' : 'pointer',
        fontWeight: 600, fontSize: '0.85rem', opacity: (disabled || loading) ? 0.6 : 1,
        transition: 'opacity 0.15s',
      }}
    >
      {loading ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <Icon size={13} />}
      {label}
    </button>
  );
}

// ── Reject Modal ─────────────────────────────────────────────────────────────

function RejectModal({ onClose, onConfirm }: { onClose: () => void; onConfirm: (reason: string) => void }) {
  const [reason, setReason] = useState('');
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }}>
      <div style={{
        background: 'var(--color-bg-card)', borderRadius: '12px',
        width: '100%', maxWidth: '420px', padding: '24px',
      }}>
        <h3 style={{ margin: '0 0 12px', color: '#ef4444' }}>Reject Candidate</h3>
        <p style={{ margin: '0 0 14px', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
          This will permanently close the candidate workflow. Please provide a reason.
        </p>
        <textarea
          value={reason}
          onChange={e => setReason(e.target.value)}
          placeholder="Rejection reason…"
          rows={3}
          style={{
            width: '100%', padding: '9px 12px', border: '1px solid var(--color-border)',
            borderRadius: '8px', background: 'var(--color-bg-body)',
            color: 'var(--color-text-main)', fontSize: '0.9rem',
            resize: 'vertical', boxSizing: 'border-box',
          }}
        />
        <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '16px' }}>
          <button onClick={onClose} style={{ padding: '8px 16px', border: '1px solid var(--color-border)', borderRadius: '8px', background: 'none', cursor: 'pointer' }}>
            Cancel
          </button>
          <button
            onClick={() => onConfirm(reason)}
            style={{ padding: '8px 16px', border: 'none', borderRadius: '8px', background: '#ef4444', color: '#fff', cursor: 'pointer', fontWeight: 600 }}
          >
            Reject
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Candidate Detail Page ───────────────────────────────────────────────

export const CandidateDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();

  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [note, setNote] = useState('');
  const [noteLoading, setNoteLoading] = useState(false);

  const loadCandidate = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError('');
    try {
      const c = await candidateService.getCandidate(Number(id));
      setCandidate(c);
    } catch (err: any) {
      setError(err.message || 'Failed to load candidate.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { loadCandidate(); }, [loadCandidate]);

  const doAction = async (actionName: string, fn: () => Promise<any>) => {
    setActionError('');
    setActionLoading(actionName);
    try {
      await fn();
      await loadCandidate();
    } catch (err: any) {
      setActionError(err.message || `Action '${actionName}' failed.`);
    } finally {
      setActionLoading(null);
    }
  };

  const verifyDoc = async (docId: number, decision: 'verified' | 'rejected', reason?: string) => {
    if (!candidate) return;
    await doAction(`doc-${docId}`, () =>
      candidateService.verifyDocument(candidate.id, docId, decision, reason)
    );
  };

  const submitNote = async () => {
    if (!candidate || !note.trim()) return;
    setNoteLoading(true);
    try {
      await candidateService.addNote(candidate.id, note.trim());
      setNote('');
      await loadCandidate();
    } catch (err: any) {
      setActionError(err.message);
    } finally {
      setNoteLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '60px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
        <Loader2 size={32} style={{ animation: 'spin 1s linear infinite', marginBottom: '12px' }} />
        <p>Loading candidate…</p>
      </div>
    );
  }

  if (error || !candidate) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: '#ef4444' }}>
        <AlertCircle size={32} style={{ marginBottom: '8px' }} />
        <p>{error || 'Candidate not found.'}</p>
      </div>
    );
  }

  const s = candidate.status;
  const can = {
    issueOffer:      hasPermission('candidate.onboard') && s === 'created',
    startOnboarding: hasPermission('candidate.onboard') && s === 'offered',
    verifyDocs:      hasPermission('candidate.verify') && s === 'submitted',
    approve:         hasPermission('candidate.verify') && s === 'verifying',
    convert:         hasPermission('candidate.convert') && s === 'approved',
    reject:          hasPermission('candidate.manage_status') && !['converted', 'rejected'].includes(s),
    verifyDoc:       hasPermission('candidate.verify'),
  };

  return (
    <div style={{ padding: '24px', maxWidth: '960px', margin: '0 auto' }}>
      {/* Back + Header */}
      <button
        onClick={() => navigate('/admin/candidates')}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: '6px',
          marginBottom: '20px', border: 'none', background: 'none',
          color: 'var(--color-text-muted)', cursor: 'pointer', fontSize: '0.875rem',
        }}
      >
        <ArrowLeft size={14} /> Back to Candidates
      </button>

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
            {candidate.first_name} {candidate.last_name}
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '6px', flexWrap: 'wrap' }}>
            <span style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>{candidate.email}</span>
            <StatusBadge status={s} display={candidate.status_display} />
            {candidate.employee_id_display && (
              <span style={{ fontSize: '0.8rem', background: '#dcfce7', color: 'var(--color-beyondsure-green)', padding: '3px 8px', borderRadius: '99px', fontWeight: 600 }}>
                Employee: {candidate.employee_id_display}
              </span>
            )}
          </div>
        </div>

        {/* Action toolbar */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {can.issueOffer && (
            <ActionButton icon={Send} label="Issue Offer" color="#3b82f6"
              onClick={() => doAction('issue-offer', () => candidateService.issueOffer(candidate.id))}
              loading={actionLoading === 'issue-offer'} />
          )}
          {can.startOnboarding && (
            <ActionButton icon={Clock} label="Start Onboarding" color="#f59e0b"
              onClick={() => doAction('start-onboarding', () => candidateService.issueOffer(candidate.id))}
              loading={actionLoading === 'start-onboarding'} />
          )}
          {can.verifyDocs && (
            <ActionButton icon={FileText} label="Move to Verifying" color="#0ea5e9"
              onClick={() => doAction('verify-docs', () => candidateService.verifyDocuments(candidate.id))}
              loading={actionLoading === 'verify-docs'} />
          )}
          {can.approve && (
            <ActionButton icon={CheckCircle} label="Approve" color="var(--color-beyondsure-green)"
              onClick={() => doAction('approve', () => candidateService.approveCandidate(candidate.id))}
              loading={actionLoading === 'approve'} />
          )}
          {can.convert && (
            <ActionButton icon={UserCheck} label="Convert to Employee" color="var(--color-beyondsure-green)"
              onClick={() => doAction('convert', () => candidateService.convertToEmployee(candidate.id))}
              loading={actionLoading === 'convert'} />
          )}
          {can.reject && (
            <ActionButton icon={XCircle} label="Reject" color="#ef4444"
              onClick={() => setShowRejectModal(true)} />
          )}
        </div>
      </div>

      {actionError && (
        <div style={{
          display: 'flex', gap: '8px', alignItems: 'flex-start',
          background: '#fef2f2', border: '1px solid #fecaca',
          borderRadius: '8px', padding: '12px', marginBottom: '16px', color: '#ef4444',
        }}>
          <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '1px' }} />
          {actionError}
        </div>
      )}

      {/* Profile */}
      <Section title="Profile">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '16px' }}>
          {[
            { label: 'Organization', value: candidate.organization_name },
            { label: 'Designation', value: candidate.designation_name || '—' },
            { label: 'Phone', value: candidate.phone_number || '—' },
            { label: 'Joining Date', value: candidate.proposed_joining_date || '—' },
            { label: 'Created', value: new Date(candidate.created_at).toLocaleDateString() },
            { label: 'Created By', value: candidate.created_by_email || '—' },
          ].map(row => (
            <div key={row.label}>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '4px' }}>
                {row.label}
              </div>
              <div style={{ fontSize: '0.9rem', color: 'var(--color-text-main)' }}>{row.value}</div>
            </div>
          ))}
        </div>
        {candidate.address && (
          <div style={{ marginTop: '14px' }}>
            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '4px' }}>
              Address
            </div>
            <div style={{ fontSize: '0.9rem', color: 'var(--color-text-main)', whiteSpace: 'pre-wrap' }}>{candidate.address}</div>
          </div>
        )}
        {candidate.notes && (
          <div style={{ marginTop: '14px' }}>
            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '4px' }}>
              Notes
            </div>
            <div style={{ fontSize: '0.9rem', color: 'var(--color-text-main)', whiteSpace: 'pre-wrap', background: 'var(--color-bg-body)', padding: '10px', borderRadius: '8px' }}>
              {candidate.notes}
            </div>
          </div>
        )}
      </Section>

      {/* Documents */}
      <Section title={`Documents (${candidate.document_count})`}>
        {candidate.documents.length === 0 ? (
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', margin: 0 }}>
            No documents uploaded yet.
          </p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {candidate.documents.map(doc => (
              <div key={doc.id} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '12px', border: '1px solid var(--color-border)',
                borderRadius: '8px', background: 'var(--color-bg-body)',
                flexWrap: 'wrap', gap: '10px',
              }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-main)' }}>
                    {doc.document_name}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                    {doc.document_type_display} · {(doc.file_size / 1024).toFixed(0)} KB · Uploaded {new Date(doc.uploaded_at).toLocaleDateString()}
                  </div>
                  {doc.rejection_reason && (
                    <div style={{ fontSize: '0.78rem', color: '#ef4444', marginTop: '4px' }}>
                      Rejection: {doc.rejection_reason}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <DocumentStatusBadge status={doc.status} />
                  {can.verifyDoc && doc.status === 'pending' && (
                    <>
                      <button
                        onClick={() => verifyDoc(doc.id, 'verified')}
                        disabled={!!actionLoading}
                        style={{
                          padding: '5px 10px', border: 'none', borderRadius: '6px',
                          background: 'var(--color-beyondsure-green)', color: '#fff',
                          cursor: 'pointer', fontSize: '0.78rem', fontWeight: 600,
                        }}
                      >
                        ✓ Verify
                      </button>
                      <button
                        onClick={() => {
                          const reason = window.prompt('Rejection reason:');
                          if (reason !== null) verifyDoc(doc.id, 'rejected', reason);
                        }}
                        disabled={!!actionLoading}
                        style={{
                          padding: '5px 10px', border: 'none', borderRadius: '6px',
                          background: '#ef4444', color: '#fff',
                          cursor: 'pointer', fontSize: '0.78rem', fontWeight: 600,
                        }}
                      >
                        ✗ Reject
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Issued Letters */}
      <Section title={`Letters (${candidate.issued_letters.length})`} defaultOpen={candidate.issued_letters.length > 0}>
        {candidate.issued_letters.length === 0 ? (
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', margin: 0 }}>
            No letters issued yet.
          </p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {candidate.issued_letters.map(letter => (
              <div key={letter.id} style={{
                border: '1px solid var(--color-border)', borderRadius: '8px',
                overflow: 'hidden',
              }}>
                <div style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '12px 14px', background: 'var(--color-bg-body)',
                }}>
                  <div>
                    <span style={{ fontWeight: 600, color: 'var(--color-text-main)', fontSize: '0.9rem' }}>
                      {letter.letter_type_display}
                    </span>
                    <span style={{ marginLeft: '8px', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                      v{letter.template_version} · Issued {new Date(letter.issued_at).toLocaleDateString()}
                      {letter.issued_by_email && ` by ${letter.issued_by_email}`}
                    </span>
                  </div>
                </div>
                <div style={{
                  padding: '14px', fontFamily: 'inherit', fontSize: '0.875rem',
                  color: 'var(--color-text-main)', whiteSpace: 'pre-wrap',
                  borderTop: '1px solid var(--color-border)', lineHeight: 1.6,
                  maxHeight: '300px', overflowY: 'auto',
                }}>
                  <strong>{letter.subject_snapshot}</strong>
                  <div style={{ marginTop: '12px' }}>{letter.body_snapshot}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Internal Notes */}
      <Section title="Internal Notes" defaultOpen={false}>
        <div style={{ marginBottom: '12px' }}>
          <textarea
            value={note}
            onChange={e => setNote(e.target.value)}
            placeholder="Add an internal note…"
            rows={3}
            style={{
              width: '100%', padding: '10px 12px', border: '1px solid var(--color-border)',
              borderRadius: '8px', background: 'var(--color-bg-body)',
              color: 'var(--color-text-main)', fontSize: '0.9rem',
              resize: 'vertical', boxSizing: 'border-box',
            }}
          />
          <button
            onClick={submitNote}
            disabled={!note.trim() || noteLoading}
            style={{
              marginTop: '8px', padding: '8px 16px', border: 'none',
              borderRadius: '8px', background: 'var(--color-primary)', color: '#fff',
              cursor: (!note.trim() || noteLoading) ? 'not-allowed' : 'pointer',
              fontWeight: 600, fontSize: '0.85rem', opacity: (!note.trim() || noteLoading) ? 0.6 : 1,
            }}
          >
            Add Note
          </button>
        </div>
      </Section>

      {showRejectModal && (
        <RejectModal
          onClose={() => setShowRejectModal(false)}
          onConfirm={reason => {
            setShowRejectModal(false);
            doAction('reject', () => candidateService.rejectCandidate(candidate.id, reason));
          }}
        />
      )}
    </div>
  );
};
