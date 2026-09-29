import React, { useState, useEffect } from 'react';
import { FileText, Plus, Loader2, Check, ChevronDown, ChevronUp } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { candidateService, type LetterTemplate, type CreateLetterTemplatePayload } from '../../services/candidates';

const LETTER_TYPES = [
  { value: 'offer', label: 'Offer Letter' },
  { value: 'appointment', label: 'Appointment Letter' },
];

const PLACEHOLDERS = ['{{candidate_name}}', '{{designation}}', '{{joining_date}}', '{{organization}}', '{{employee_code}}'];

function TemplateCard({ t, open, onToggle }: { t: LetterTemplate; open: boolean; onToggle: () => void }) {
  return (
    <div style={{
      border: '1px solid var(--color-border)', borderRadius: '10px',
      overflow: 'hidden', marginBottom: '12px',
    }}>
      <button
        onClick={onToggle}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 16px', border: 'none', background: 'var(--color-bg-card)',
          cursor: 'pointer', color: 'var(--color-text-main)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <FileText size={16} style={{ color: 'var(--color-primary)' }} />
          <div style={{ textAlign: 'left' }}>
            <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>
              {t.letter_type_display}
              <span style={{ marginLeft: '8px', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                v{t.version}
              </span>
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
              {t.subject}
              {t.is_active && <span style={{ marginLeft: '8px', color: 'var(--color-beyondsure-green)', fontWeight: 600 }}>● Active</span>}
            </div>
          </div>
        </div>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {open && (
        <div style={{
          padding: '14px 16px', borderTop: '1px solid var(--color-border)',
          background: 'var(--color-bg-body)', whiteSpace: 'pre-wrap',
          fontSize: '0.875rem', color: 'var(--color-text-main)', lineHeight: 1.6,
          maxHeight: '300px', overflowY: 'auto',
        }}>
          {t.body}
        </div>
      )}
    </div>
  );
}

export const LetterTemplatesPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const [templates, setTemplates] = useState<LetterTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [openTemplate, setOpenTemplate] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [filter, setFilter] = useState('');

  const [form, setForm] = useState<CreateLetterTemplatePayload>({
    letter_type: 'offer', subject: '', body: '',
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  useEffect(() => {
    setLoading(true);
    candidateService.listTemplates()
      .then(setTemplates)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError('');
    setSaving(true);
    try {
      const t = await candidateService.createTemplate(form);
      setTemplates(prev => [t, ...prev]);
      setShowCreate(false);
      setForm({ letter_type: 'offer', subject: '', body: '' });
    } catch (err: any) {
      setSaveError(err.message || 'Failed to save template.');
    } finally {
      setSaving(false);
    }
  };

  const filtered = filter ? templates.filter(t => t.letter_type === filter) : templates;

  return (
    <div style={{ padding: '24px', maxWidth: '900px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
            Letter Templates
          </h1>
          <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>
            Manage Offer and Appointment letter templates
          </p>
        </div>
        {hasPermission('letter.issue') && (
          <button
            onClick={() => setShowCreate(s => !s)}
            id="create-template-btn"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '8px 16px', border: 'none', borderRadius: '8px',
              background: 'var(--color-primary)', color: '#fff',
              cursor: 'pointer', fontWeight: 600, fontSize: '0.875rem',
            }}
          >
            <Plus size={14} /> New Template
          </button>
        )}
      </div>

      {/* Available placeholders guide */}
      <div style={{
        background: 'var(--color-bg-card)', borderRadius: '10px',
        padding: '12px 16px', marginBottom: '20px',
        border: '1px solid var(--color-border)',
      }}>
        <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--color-text-muted)', marginBottom: '8px', textTransform: 'uppercase' }}>
          Available Placeholders
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {PLACEHOLDERS.map(p => (
            <code key={p} style={{
              background: 'var(--color-bg-body)', border: '1px solid var(--color-border)',
              borderRadius: '4px', padding: '2px 6px', fontSize: '0.8rem',
              color: 'var(--color-primary)',
            }}>
              {p}
            </code>
          ))}
        </div>
      </div>

      {/* Create Form */}
      {showCreate && (
        <div style={{
          background: 'var(--color-bg-card)', borderRadius: '10px',
          border: '1px solid var(--color-primary)', padding: '20px', marginBottom: '20px',
        }}>
          <h3 style={{ margin: '0 0 16px', fontSize: '1rem' }}>Create New Template</h3>
          {saveError && (
            <div style={{ color: '#ef4444', marginBottom: '12px', fontSize: '0.875rem' }}>{saveError}</div>
          )}
          <form onSubmit={handleCreate}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                  Letter Type
                </label>
                <select
                  value={form.letter_type}
                  onChange={e => setForm(f => ({ ...f, letter_type: e.target.value as any }))}
                  style={{
                    width: '100%', padding: '9px 12px', border: '1px solid var(--color-border)',
                    borderRadius: '8px', background: 'var(--color-bg-body)',
                    color: 'var(--color-text-main)', fontSize: '0.9rem', boxSizing: 'border-box',
                  }}
                >
                  {LETTER_TYPES.map(lt => <option key={lt.value} value={lt.value}>{lt.label}</option>)}
                </select>
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                  Subject
                </label>
                <input
                  value={form.subject}
                  onChange={e => setForm(f => ({ ...f, subject: e.target.value }))}
                  required
                  style={{
                    width: '100%', padding: '9px 12px', border: '1px solid var(--color-border)',
                    borderRadius: '8px', background: 'var(--color-bg-body)',
                    color: 'var(--color-text-main)', fontSize: '0.9rem', boxSizing: 'border-box',
                  }}
                />
              </div>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Body (use placeholders above)
              </label>
              <textarea
                value={form.body}
                onChange={e => setForm(f => ({ ...f, body: e.target.value }))}
                required
                rows={10}
                style={{
                  width: '100%', padding: '10px 12px', border: '1px solid var(--color-border)',
                  borderRadius: '8px', background: 'var(--color-bg-body)',
                  color: 'var(--color-text-main)', fontSize: '0.9rem',
                  fontFamily: 'monospace', resize: 'vertical', boxSizing: 'border-box',
                }}
              />
            </div>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '16px' }}>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                style={{ padding: '8px 16px', border: '1px solid var(--color-border)', borderRadius: '8px', background: 'none', cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '6px',
                  padding: '8px 16px', border: 'none', borderRadius: '8px',
                  background: 'var(--color-primary)', color: '#fff',
                  cursor: saving ? 'not-allowed' : 'pointer', fontWeight: 600, opacity: saving ? 0.7 : 1,
                }}
              >
                {saving ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <Check size={13} />}
                {saving ? 'Saving…' : 'Save Template'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Filter */}
      <div style={{ marginBottom: '16px', display: 'flex', gap: '8px' }}>
        {[{ value: '', label: 'All' }, ...LETTER_TYPES].map(lt => (
          <button
            key={lt.value}
            onClick={() => setFilter(lt.value)}
            style={{
              padding: '6px 14px', border: '1px solid var(--color-border)',
              borderRadius: '99px', background: filter === lt.value ? 'var(--color-primary)' : 'var(--color-bg-card)',
              color: filter === lt.value ? '#fff' : 'var(--color-text-main)',
              cursor: 'pointer', fontSize: '0.85rem', fontWeight: 500,
            }}
          >
            {lt.label}
          </button>
        ))}
      </div>

      {/* Templates list */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--color-text-muted)' }}>
          <Loader2 size={24} style={{ animation: 'spin 1s linear infinite', marginBottom: '8px' }} />
          <p>Loading templates…</p>
        </div>
      ) : error ? (
        <div style={{ color: '#ef4444', padding: '20px' }}>{error}</div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--color-text-muted)' }}>
          <FileText size={32} style={{ opacity: 0.3, marginBottom: '12px' }} />
          <p>No templates yet. Create your first one above.</p>
        </div>
      ) : (
        filtered.map(t => (
          <TemplateCard
            key={t.id}
            t={t}
            open={openTemplate === t.id}
            onToggle={() => setOpenTemplate(o => o === t.id ? null : t.id)}
          />
        ))
      )}
    </div>
  );
};
