import React, { useEffect, useState } from 'react';
import {
  Bell,
  Loader2,
  Plus,
  Send,
  CheckCircle,
  FileText,
  ExternalLink,
  ShieldCheck,
  X,
} from 'lucide-react';
import { Card } from '../../components/Card';
import { announcementService, type Announcement } from '../../services/announcements';
import { useAuth } from '../../contexts/AuthContext';

export const AnnouncementsPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const canManage = hasPermission('announcement.manage');

  const [items, setItems] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [form, setForm] = useState({
    title: '',
    body: '',
    is_published: true,
    expires_at: '',
    requires_acknowledgement: false,
    policy_pdf_url: '',
  });

  const load = () => {
    setLoading(true);
    announcementService
      .list()
      .then((x) => setItems(Array.isArray(x) ? x : []))
      .catch(() => setError('Unable to load announcements.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await announcementService.create({
        ...form,
        expires_at: form.expires_at || null,
        policy_pdf_url: form.policy_pdf_url.trim() || null,
      });
      setOpen(false);
      setForm({
        title: '',
        body: '',
        is_published: true,
        expires_at: '',
        requires_acknowledgement: false,
        policy_pdf_url: '',
      });
      load();
    } catch {
      setError('Unable to save the announcement.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 'var(--spacing-lg)',
          gap: 12,
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--font-size-2xl)' }}>Announcements</h1>
          <p className="text-muted" style={{ marginTop: 4 }}>
            Organization communications with acknowledgement tracking and compliance audit history.
          </p>
        </div>
        {canManage && (
          <button className="btn btn-primary" onClick={() => setOpen(true)} type="button">
            <Plus size={18} /> New announcement
          </button>
        )}
      </div>

      {error && (
        <div style={{ color: 'var(--color-status-danger)', marginBottom: 12 }}>{error}</div>
      )}

      {loading ? (
        <Card>
          <div style={{ padding: 32, textAlign: 'center' }}>
            <Loader2 className="animate-spin" color="var(--color-primary)" />
          </div>
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <div className="text-muted" style={{ padding: 24, textAlign: 'center' }}>
            No published announcements.
          </div>
        </Card>
      ) : (
        <div style={{ display: 'grid', gap: 'var(--spacing-md)' }}>
          {items.map((i) => (
            <Card key={i.id}>
              <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    background: i.requires_acknowledgement
                      ? 'var(--color-status-warning-bg, rgba(245, 158, 11, 0.12))'
                      : 'var(--color-primary-light, rgba(2, 132, 199, 0.1))',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    marginTop: 2,
                  }}
                >
                  <Bell
                    size={20}
                    color={
                      i.requires_acknowledgement
                        ? 'var(--color-status-warning, #d97706)'
                        : 'var(--color-primary, #0284c7)'
                    }
                  />
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <h2 style={{ fontSize: 'var(--font-size-lg)', margin: 0 }}>{i.title}</h2>
                    {i.requires_acknowledgement && (
                      <span
                        style={{
                          fontSize: '0.72rem',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: '6px',
                          background: 'rgba(217, 119, 6, 0.12)',
                          color: '#b45309',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                          letterSpacing: '0.02em',
                        }}
                      >
                        <ShieldCheck size={12} /> Acknowledgement Required
                      </span>
                    )}
                    {canManage && i.requires_acknowledgement && (
                      <span
                        style={{
                          fontSize: '0.72rem',
                          fontWeight: 600,
                          padding: '2px 8px',
                          borderRadius: '6px',
                          background: 'var(--color-bg-subtle, #f1f5f9)',
                          color: 'var(--color-text-main, #334155)',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                        }}
                      >
                        <CheckCircle size={12} color="#059669" />
                        {i.acknowledgement_count ?? 0} Acknowledged
                      </span>
                    )}
                  </div>

                  <p style={{ whiteSpace: 'pre-wrap', margin: '8px 0 12px', lineHeight: 1.5 }}>
                    {i.body}
                  </p>

                  {i.policy_pdf_url && (
                    <div style={{ marginBottom: 12 }}>
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
                        <FileText size={14} /> Attached Policy Document <ExternalLink size={12} />
                      </a>
                    </div>
                  )}

                  <small className="text-muted">
                    {i.branch_name || 'Organization-wide'} ·{' '}
                    {i.published_at ? new Date(i.published_at).toLocaleString() : 'Draft'} ·{' '}
                    {i.created_by_name}
                  </small>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {open && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,.5)',
            display: 'grid',
            placeItems: 'center',
            zIndex: 1000,
            padding: 16,
          }}
        >
          <Card style={{ width: 'min(600px, 100%)', maxHeight: '90vh', overflowY: 'auto' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 16,
              }}
            >
              <h2 style={{ margin: 0, fontSize: '1.25rem' }}>New Announcement</h2>
              <button
                type="button"
                onClick={() => setOpen(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={submit} style={{ display: 'grid', gap: 14 }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 4 }}>
                  Title
                </label>
                <input
                  className="input-neumorphic"
                  placeholder="e.g. Annual Company Policy & Code of Conduct Update"
                  required
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 4 }}>
                  Announcement Message
                </label>
                <textarea
                  className="input-neumorphic"
                  placeholder="Detail your communication here..."
                  required
                  rows={5}
                  value={form.body}
                  onChange={(e) => setForm({ ...form, body: e.target.value })}
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 4 }}>
                  Policy Document URL (Optional)
                </label>
                <input
                  className="input-neumorphic"
                  type="url"
                  placeholder="https://example.com/policies/handbook.pdf"
                  value={form.policy_pdf_url}
                  onChange={(e) => setForm({ ...form, policy_pdf_url: e.target.value })}
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 4 }}>
                  Expiration Date (Optional)
                </label>
                <input
                  type="datetime-local"
                  className="input-neumorphic"
                  value={form.expires_at}
                  onChange={(e) => setForm({ ...form, expires_at: e.target.value })}
                  style={{ width: '100%' }}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: '0.9rem' }}>
                  <input
                    type="checkbox"
                    checked={form.requires_acknowledgement}
                    onChange={(e) => setForm({ ...form, requires_acknowledgement: e.target.checked })}
                  />
                  <strong>Require Employee Acknowledgement</strong> (employees must confirm compliance)
                </label>

                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: '0.9rem' }}>
                  <input
                    type="checkbox"
                    checked={form.is_published}
                    onChange={(e) => setForm({ ...form, is_published: e.target.checked })}
                  />
                  <span>Publish immediately upon saving</span>
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </button>
                <button className="btn btn-primary" disabled={isSubmitting}>
                  {isSubmitting ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Send size={16} />
                  )}
                  {form.is_published ? 'Publish Announcement' : 'Save Draft'}
                </button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
};
