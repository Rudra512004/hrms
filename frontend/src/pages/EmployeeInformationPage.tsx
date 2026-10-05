import React, { useEffect, useState, useCallback } from 'react';
import {
  Bell,
  CalendarDays,
  FileText,
  CheckCircle,
  AlertCircle,
  ExternalLink,
  ShieldAlert,
  Loader2,
  Plus,
  Download,
  Send,
  X,
  FileCheck,
} from 'lucide-react';
import { Card } from '../components/Card';
import { StatusBadge } from '../components/StatusBadge';
import { announcementService } from '../services/announcements';
import {
  letterRequestService,
  type LetterRequest,
  type LetterRequestType,
} from '../services/letterRequests';

type Mode = 'letters' | 'holidays' | 'announcements';

const config = {
  letters: {
    title: 'My Letters',
    icon: FileText,
    path: '/api/v1/employees/me/letters/',
    description: 'Self-service letter requests and letters issued to you by HR.',
  },
  holidays: {
    title: 'Holidays',
    icon: CalendarDays,
    path: '/api/v1/employees/me/holidays/',
    description: 'Confirmed holidays for your assigned branch.',
  },
  announcements: {
    title: 'Announcements',
    icon: Bell,
    path: '/api/v1/employees/me/announcements/',
    description: 'Official organization updates and compliance policies.',
  },
};

const LETTER_TYPES: { value: LetterRequestType; label: string }[] = [
  { value: 'BONAFIDE', label: 'Bonafide Certificate' },
  { value: 'ADDRESS_PROOF', label: 'Address Proof / Verification Letter' },
  { value: 'EXPERIENCE', label: 'Experience / Service Certificate' },
  { value: 'SALARY_CERTIFICATE', label: 'Salary Certificate' },
  { value: 'EMPLOYMENT_VERIFICATION', label: 'Employment Verification Letter' },
];

export const EmployeeInformationPage: React.FC<{ mode: Mode }> = ({ mode }) => {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Announcement acknowledgement state
  const [acknowledgingId, setAcknowledgingId] = useState<number | null>(null);
  const [ackSuccessId, setAckSuccessId] = useState<number | null>(null);

  // Letter request tab state
  const [letterTab, setLetterTab] = useState<'requests' | 'issued'>('requests');
  const [letterRequests, setLetterRequests] = useState<LetterRequest[]>([]);
  const [isRequestModalOpen, setIsRequestModalOpen] = useState(false);
  const [submittingLetter, setSubmittingLetter] = useState(false);
  const [letterForm, setLetterForm] = useState({
    letter_type: 'BONAFIDE',
    reason: '',
  });

  const activeConfig = config[mode];
  const Icon = activeConfig.icon;

  const loadData = useCallback(() => {
    setLoading(true);
    setError(null);

    const token = localStorage.getItem('auth_token') || '';
    const headers = { Authorization: `Token ${token}` };

    if (mode === 'letters' && letterTab === 'requests') {
      letterRequestService
        .list()
        .then((res) => {
          setLetterRequests(Array.isArray(res) ? res : []);
        })
        .catch(() => setError('Unable to load letter requests.'))
        .finally(() => setLoading(false));
      return;
    }

    fetch(activeConfig.path, { headers })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data) => setItems(Array.isArray(data) ? data : []))
      .catch(() => setError('Unable to load this information.'))
      .finally(() => setLoading(false));
  }, [mode, letterTab, activeConfig.path]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Acknowledge announcement handler
  const handleAcknowledge = async (announcementId: number) => {
    setAcknowledgingId(announcementId);
    setError(null);
    try {
      await announcementService.acknowledge(announcementId);
      setItems((prev) =>
        prev.map((item) =>
          item.id === announcementId ? { ...item, is_acknowledged: true } : item
        )
      );
      setAckSuccessId(announcementId);
      setTimeout(() => setAckSuccessId(null), 4000);
    } catch (err: any) {
      console.error('Failed to acknowledge announcement:', err);
      setError(err?.message || 'Unable to submit acknowledgement. Please try again.');
    } finally {
      setAcknowledgingId(null);
    }
  };

  // Submit letter request handler
  const handleSubmitLetterRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!letterForm.reason.trim()) return;

    setSubmittingLetter(true);
    setError(null);
    try {
      await letterRequestService.create({
        letter_type: letterForm.letter_type,
        reason: letterForm.reason.trim(),
      });
      setIsRequestModalOpen(false);
      setLetterForm({ letter_type: 'BONAFIDE', reason: '' });
      loadData();
    } catch (err: any) {
      console.error('Failed to submit letter request:', err);
      setError(err?.message || 'Failed to submit letter request.');
    } finally {
      setSubmittingLetter(false);
    }
  };

  return (
    <div>
      {/* Header bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 12,
          marginBottom: 'var(--spacing-lg)',
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
            <Icon size={26} color="var(--color-primary)" />
            {activeConfig.title}
          </h1>
          <p className="text-muted" style={{ margin: '4px 0 0 0' }}>
            {activeConfig.description}
          </p>
        </div>

        {mode === 'letters' && (
          <button
            className="btn btn-primary"
            onClick={() => setIsRequestModalOpen(true)}
            type="button"
          >
            <Plus size={18} /> Request Letter
          </button>
        )}
      </div>

      {error && (
        <Card style={{ marginBottom: 'var(--spacing-md)' }}>
          <div
            style={{
              padding: 12,
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

      {/* Mode = Letters Tab switcher */}
      {mode === 'letters' && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 'var(--spacing-md)' }}>
          <button
            className={`btn ${letterTab === 'requests' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setLetterTab('requests')}
            type="button"
          >
            My Letter Requests
          </button>
          <button
            className={`btn ${letterTab === 'issued' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setLetterTab('issued')}
            type="button"
          >
            Issued Letters
          </button>
        </div>
      )}

      {/* Loading state */}
      {loading ? (
        <Card>
          <div style={{ padding: 48, textAlign: 'center' }}>
            <Loader2 size={32} className="animate-spin" color="var(--color-primary)" />
          </div>
        </Card>
      ) : mode === 'letters' && letterTab === 'requests' ? (
        /* Letter Requests Self-Service List */
        letterRequests.length === 0 ? (
          <Card>
            <div style={{ textAlign: 'center', padding: '40px 20px' }}>
              <FileCheck size={40} color="var(--color-text-muted)" style={{ margin: '0 auto 10px' }} />
              <h3 style={{ margin: 0 }}>No Letter Requests Yet</h3>
              <p className="text-muted" style={{ margin: '6px 0 16px' }}>
                Need a bonafide letter, experience certificate, or address verification? Submit a request above.
              </p>
              <button
                className="btn btn-primary"
                onClick={() => setIsRequestModalOpen(true)}
                type="button"
              >
                <Plus size={16} /> Request a Letter
              </button>
            </div>
          </Card>
        ) : (
          <div style={{ display: 'grid', gap: 'var(--spacing-md)' }}>
            {letterRequests.map((req) => (
              <Card key={req.id}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    flexWrap: 'wrap',
                    gap: 12,
                  }}
                >
                  <div style={{ display: 'flex', gap: 12, minWidth: 0, flex: 1 }}>
                    <div
                      style={{
                        width: 40,
                        height: 40,
                        borderRadius: '8px',
                        background: 'var(--color-primary-light, rgba(2, 132, 199, 0.1))',
                        color: 'var(--color-primary, #0284c7)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
                      <FileText size={20} />
                    </div>

                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <strong style={{ fontSize: '1rem', color: 'var(--color-text-main)' }}>
                          {LETTER_TYPES.find((t) => t.value === req.letter_type)?.label || req.letter_type}
                        </strong>
                        <StatusBadge
                          status={
                            req.status === 'APPROVED' || req.status === 'ISSUED'
                              ? 'approved'
                              : req.status === 'REJECTED'
                              ? 'rejected'
                              : 'pending'
                          }
                          label={req.status}
                        />
                      </div>

                      <p style={{ margin: '6px 0 8px', color: 'var(--color-text-sub)', fontSize: '0.9rem' }}>
                        {req.reason}
                      </p>

                      <div style={{ display: 'flex', gap: 14, fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                        <span>Requested: {new Date(req.created_at).toLocaleDateString()}</span>
                        {req.approved_by_name && <span>Reviewed by: {req.approved_by_name}</span>}
                      </div>
                    </div>
                  </div>

                  {req.issued_document && (
                    <a
                      href={req.issued_document}
                      target="_blank"
                      rel="noreferrer"
                      className="btn btn-secondary"
                      style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 6 }}
                    >
                      <Download size={15} /> Download Letter
                    </a>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )) : (
        /* Announcements, Holidays, or Issued Letters List */
        <div style={{ display: 'grid', gap: 'var(--spacing-md)' }}>
          {items.map((i) => {
            const isAcknowledged = Boolean(i.is_acknowledged);
            const requiresAck = Boolean(i.requires_acknowledgement);

            return (
              <Card key={i.id}>
                <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                  <Icon
                    size={22}
                    style={{
                      flexShrink: 0,
                      marginTop: 2,
                      color:
                        mode === 'announcements' && requiresAck && !isAcknowledged
                          ? 'var(--color-status-warning, #d97706)'
                          : 'var(--color-primary)',
                    }}
                  />

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <strong style={{ fontSize: '1rem', color: 'var(--color-text-main)' }}>
                        {mode === 'letters'
                          ? i.subject_snapshot || 'Issued Letter'
                          : mode === 'holidays'
                          ? i.name
                          : i.title}
                      </strong>

                      {mode === 'announcements' && requiresAck && (
                        <span
                          style={{
                            fontSize: '0.72rem',
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: '6px',
                            background: isAcknowledged
                              ? 'rgba(5, 150, 105, 0.12)'
                              : 'rgba(217, 119, 6, 0.12)',
                            color: isAcknowledged ? '#059669' : '#b45309',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                          }}
                        >
                          {isAcknowledged ? (
                            <>
                              <CheckCircle size={12} /> Acknowledged
                            </>
                          ) : (
                            <>
                              <ShieldAlert size={12} /> Acknowledgement Required
                            </>
                          )}
                        </span>
                      )}
                    </div>

                    <p style={{ whiteSpace: 'pre-wrap', margin: '8px 0 10px', lineHeight: 1.5 }}>
                      {mode === 'letters'
                        ? i.body_snapshot
                        : mode === 'holidays'
                        ? `${new Date(`${i.date}T00:00:00`).toLocaleDateString(undefined, {
                            weekday: 'long',
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric',
                          })}${i.description ? ` — ${i.description}` : ''}`
                        : i.body}
                    </p>

                    {mode === 'announcements' && i.policy_pdf_url && (
                      <div style={{ margin: '8px 0 12px' }}>
                        <a
                          href={i.policy_pdf_url}
                          target="_blank"
                          rel="noreferrer"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            fontSize: '0.82rem',
                            fontWeight: 600,
                            color: 'var(--color-primary, #0284c7)',
                            textDecoration: 'none',
                            padding: '4px 10px',
                            borderRadius: '6px',
                            background: 'var(--color-primary-light, rgba(2, 132, 199, 0.08))',
                          }}
                        >
                          <FileText size={14} /> Review Policy Document <ExternalLink size={12} />
                        </a>
                      </div>
                    )}

                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        flexWrap: 'wrap',
                        gap: 10,
                        marginTop: 4,
                      }}
                    >
                      <small className="text-muted">
                        {mode === 'letters'
                          ? `Issued: ${new Date(i.issued_at).toLocaleDateString()}`
                          : mode === 'holidays'
                          ? i.date
                          : `${i.branch_name || 'Organization-wide'} · ${
                              i.published_at ? new Date(i.published_at).toLocaleString() : 'Draft'
                            }`}
                      </small>

                      {/* Announcement Acknowledgement Action */}
                      {mode === 'announcements' && requiresAck && (
                        <div>
                          {isAcknowledged ? (
                            <span
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 6,
                                fontSize: '0.82rem',
                                color: 'var(--color-status-success, #059669)',
                                fontWeight: 600,
                              }}
                            >
                              <CheckCircle size={16} /> Completed
                            </span>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-primary"
                              disabled={acknowledgingId === i.id}
                              onClick={() => handleAcknowledge(i.id)}
                              style={{
                                padding: '6px 14px',
                                fontSize: '0.82rem',
                              }}
                            >
                              {acknowledgingId === i.id ? (
                                <>
                                  <Loader2 size={14} className="animate-spin" /> Submitting...
                                </>
                              ) : (
                                <>
                                  <CheckCircle size={14} /> Acknowledge Compliance
                                </>
                              )}
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    {ackSuccessId === i.id && (
                      <div
                        style={{
                          marginTop: 8,
                          padding: '6px 10px',
                          borderRadius: '6px',
                          background: 'rgba(5, 150, 105, 0.1)',
                          color: '#059669',
                          fontSize: '0.82rem',
                          fontWeight: 500,
                        }}
                      >
                        ✓ Acknowledgement successfully recorded. Thank you!
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}

          {!items.length && (
            <Card>
              <p className="text-muted" style={{ textAlign: 'center', padding: 24, margin: 0 }}>
                Nothing to show yet.
              </p>
            </Card>
          )}
        </div>
      )}

      {/* Letter Request Modal */}
      {isRequestModalOpen && (
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
          <Card style={{ width: 'min(520px, 100%)' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 16,
              }}
            >
              <h2 style={{ margin: 0, fontSize: '1.25rem' }}>Request an Official Letter</h2>
              <button
                type="button"
                onClick={() => setIsRequestModalOpen(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmitLetterRequest} style={{ display: 'grid', gap: 14 }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 4 }}>
                  Letter Type
                </label>
                <select
                  className="input-neumorphic"
                  value={letterForm.letter_type}
                  onChange={(e) => setLetterForm({ ...letterForm, letter_type: e.target.value })}
                  style={{ width: '100%', height: 38 }}
                >
                  {LETTER_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 4 }}>
                  Purpose / Justification
                </label>
                <textarea
                  className="input-neumorphic"
                  placeholder="e.g. Required for bank loan application or embassy visa submission..."
                  required
                  rows={4}
                  value={letterForm.reason}
                  onChange={(e) => setLetterForm({ ...letterForm, reason: e.target.value })}
                  style={{ width: '100%' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsRequestModalOpen(false)}
                  disabled={submittingLetter}
                >
                  Cancel
                </button>
                <button className="btn btn-primary" disabled={submittingLetter}>
                  {submittingLetter ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Send size={16} />
                  )}
                  Submit Request
                </button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
};
