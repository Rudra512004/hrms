/**
 * Candidate onboarding — personal profile page.
 */
import React, { useState, useEffect } from 'react';
import { Save, Loader2, AlertCircle, CheckCircle } from 'lucide-react';
import { candidatePortalService, type CandidatePortalProfile } from '../../services/candidates';

export const OnboardingProfilePage: React.FC = () => {
  const [profile, setProfile]   = useState<CandidatePortalProfile | null>(null);
  const [form, setForm]         = useState<Partial<CandidatePortalProfile>>({});
  const [loading, setLoading]   = useState(true);
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState('');
  const [success, setSuccess]   = useState('');

  useEffect(() => {
    candidatePortalService.getProfile()
      .then(p => { setProfile(p); setForm({ phone_number: p.phone_number, address: p.address }); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setSaving(true);
    try {
      const updated = await candidatePortalService.updateProfile(form);
      setProfile(updated);
      setSuccess('Profile updated successfully.');
    } catch (err: any) {
      setError(err.message || 'Update failed.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '60px', color: 'var(--color-text-muted)' }}>Loading…</div>;
  }

  if (!profile) {
    return <div style={{ color: '#ef4444' }}>{error || 'Failed to load profile.'}</div>;
  }

  const readOnly = !['offered', 'onboarding'].includes(profile.status);

  return (
    <div style={{ maxWidth: '600px' }}>
      <h1 style={{ margin: '0 0 4px', fontSize: '1.4rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
        My Profile
      </h1>
      <p style={{ margin: '0 0 24px', color: 'var(--color-text-muted)' }}>
        {readOnly ? 'Your profile is read-only at this stage.' : 'You can update your contact details.'}
      </p>

      {/* Read-only fields */}
      <div style={{
        background: 'var(--color-bg-card)', borderRadius: '10px',
        border: '1px solid var(--color-border)', padding: '20px', marginBottom: '20px',
      }}>
        <h2 style={{ margin: '0 0 16px', fontSize: '0.95rem', fontWeight: 700 }}>Personal Information</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          {[
            { label: 'First Name', value: profile.first_name },
            { label: 'Last Name', value: profile.last_name },
            { label: 'Email', value: profile.email },
            { label: 'Status', value: profile.status.charAt(0).toUpperCase() + profile.status.slice(1) },
          ].map(f => (
            <div key={f.label}>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '4px' }}>
                {f.label}
              </div>
              <div style={{ fontSize: '0.9rem', color: 'var(--color-text-main)' }}>{f.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Editable fields */}
      {!readOnly && (
        <div style={{
          background: 'var(--color-bg-card)', borderRadius: '10px',
          border: '1px solid var(--color-border)', padding: '20px',
        }}>
          <h2 style={{ margin: '0 0 16px', fontSize: '0.95rem', fontWeight: 700 }}>Contact Details</h2>

          {error && (
            <div style={{ display: 'flex', gap: '8px', color: '#ef4444', marginBottom: '12px', fontSize: '0.875rem' }}>
              <AlertCircle size={15} style={{ flexShrink: 0, marginTop: '1px' }} /> {error}
            </div>
          )}
          {success && (
            <div style={{ display: 'flex', gap: '8px', color: 'var(--color-beyondsure-green)', marginBottom: '12px', fontSize: '0.875rem' }}>
              <CheckCircle size={15} style={{ flexShrink: 0, marginTop: '1px' }} /> {success}
            </div>
          )}

          <form onSubmit={handleSave}>
            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Phone Number
              </label>
              <input
                type="tel"
                value={form.phone_number || ''}
                onChange={e => setForm(f => ({ ...f, phone_number: e.target.value }))}
                style={{
                  width: '100%', padding: '9px 12px', border: '1px solid var(--color-border)',
                  borderRadius: '8px', background: 'var(--color-bg-body)',
                  color: 'var(--color-text-main)', fontSize: '0.9rem', boxSizing: 'border-box',
                }}
              />
            </div>
            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Address
              </label>
              <textarea
                value={form.address || ''}
                onChange={e => setForm(f => ({ ...f, address: e.target.value }))}
                rows={3}
                style={{
                  width: '100%', padding: '9px 12px', border: '1px solid var(--color-border)',
                  borderRadius: '8px', background: 'var(--color-bg-body)',
                  color: 'var(--color-text-main)', fontSize: '0.9rem',
                  resize: 'vertical', boxSizing: 'border-box',
                }}
              />
            </div>
            <button
              type="submit"
              disabled={saving}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '6px',
                padding: '9px 18px', border: 'none', borderRadius: '8px',
                background: 'var(--color-primary)', color: '#fff',
                cursor: saving ? 'not-allowed' : 'pointer', fontWeight: 600,
                opacity: saving ? 0.7 : 1,
              }}
            >
              {saving ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Save size={14} />}
              {saving ? 'Saving…' : 'Save Changes'}
            </button>
          </form>
        </div>
      )}
    </div>
  );
};
