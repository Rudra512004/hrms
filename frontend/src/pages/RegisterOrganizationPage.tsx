import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, Loader2 } from 'lucide-react';
import { authService } from '../services/auth';

export const RegisterOrganizationPage: React.FC = () => {
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '' });
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true); setError(null);
    try {
      setMessage(await authService.registerTenantOwner({
        first_name: form.first_name.trim(), last_name: form.last_name.trim(), email: form.email.trim(),
      }));
    } catch (requestError: any) {
      setError(requestError.message || 'Unable to start registration.');
    } finally { setSaving(false); }
  };

  return <div style={{ width: '100%', maxWidth: 460, margin: '48px auto', padding: 'var(--spacing-xl)' }}>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, padding: 4, marginBottom: 28, borderRadius: 'var(--radius-md)', background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }} aria-label="Account access options">
      <Link to="/login" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 38, borderRadius: 'var(--radius-sm)', color: 'var(--color-text-sub)', fontWeight: 600, fontSize: 'var(--font-size-sm)' }}>Sign in</Link>
      <span style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 38, borderRadius: 'var(--radius-sm)', background: 'var(--color-bg-card)', color: 'var(--color-primary)', fontWeight: 600, fontSize: 'var(--font-size-sm)', boxShadow: 'var(--shadow-xs)' }}>Sign up</span>
    </div>
    <h1 style={{ marginBottom: 8 }}>Create your HRMS workspace</h1>
    <p className="text-muted" style={{ marginBottom: 24 }}>Enter your details to register as the tenant owner. We will send you an email to activate your account and set a password.</p>
    {message ? <div className="alert-banner alert-banner-success" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><CheckCircle2 size={18} /><span>{message}</span></div> : <form onSubmit={submit} style={{ display: 'grid', gap: 16 }}>
      {error && <div className="alert-banner alert-banner-error">{error}</div>}
      <label className="form-group"><span className="form-label">First name</span><input className="input-field" required value={form.first_name} onChange={e => setForm({ ...form, first_name: e.target.value })} /></label>
      <label className="form-group"><span className="form-label">Last name</span><input className="input-field" required value={form.last_name} onChange={e => setForm({ ...form, last_name: e.target.value })} /></label>
      <label className="form-group"><span className="form-label">Business email</span><input className="input-field" type="email" autoComplete="email" required value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></label>
      <button className="btn btn-primary" disabled={saving}>{saving && <Loader2 size={17} className="animate-spin" />}{saving ? 'Sending verification…' : 'Verify email and continue'}</button>
    </form>}
    <p className="text-muted" style={{ marginTop: 20, fontSize: 'var(--font-size-sm)' }}>Already have an account? <Link to="/login" className="text-primary">Sign in</Link></p>
  </div>;
};
