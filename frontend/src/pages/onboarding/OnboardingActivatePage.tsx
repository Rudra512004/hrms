/**
 * Candidate onboarding — activate account from email link.
 * Route: /onboarding/activate?uid=&token=
 */
import React, { useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { CheckCircle, AlertCircle, Loader2, Eye, EyeOff } from 'lucide-react';
import { candidatePortalService } from '../../services/candidates';

export const OnboardingActivatePage: React.FC = () => {
  const [params] = useSearchParams();
  const navigate  = useNavigate();

  const uid   = params.get('uid') || '';
  const token = params.get('token') || '';

  const [password, setPassword]   = useState('');
  const [confirm, setConfirm]     = useState('');
  const [showPw, setShowPw]       = useState(false);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState('');
  const [success, setSuccess]     = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    if (password !== confirm) { setError('Passwords do not match.'); return; }
    if (!uid || !token)       { setError('Invalid activation link. Please check your email.'); return; }

    setLoading(true);
    try {
      await candidatePortalService.activate(uid, token, password);
      setSuccess(true);
      setTimeout(() => navigate('/login'), 3000);
    } catch (err: any) {
      setError(err.message || 'Activation failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--color-bg-body)', padding: '16px',
    }}>
      <div style={{
        width: '100%', maxWidth: '420px',
        background: 'var(--color-bg-card)', borderRadius: '14px',
        border: '1px solid var(--color-border)', padding: '32px',
        boxShadow: 'var(--shadow-lg)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div style={{ fontSize: '2rem', marginBottom: '8px' }}>🎉</div>
          <h1 style={{ margin: '0 0 6px', fontSize: '1.3rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
            Activate Your Account
          </h1>
          <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
            Set a password to access your onboarding portal.
          </p>
        </div>

        {success ? (
          <div style={{ textAlign: 'center' }}>
            <CheckCircle size={48} style={{ color: 'var(--color-beyondsure-green)', marginBottom: '12px' }} />
            <h2 style={{ color: 'var(--color-beyondsure-green)', margin: '0 0 8px' }}>Account Activated!</h2>
            <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
              Redirecting you to the login page…
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
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

            {['Password', 'Confirm Password'].map((label, i) => (
              <div key={label} style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                  {label}
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showPw ? 'text' : 'password'}
                    value={i === 0 ? password : confirm}
                    onChange={e => i === 0 ? setPassword(e.target.value) : setConfirm(e.target.value)}
                    required
                    minLength={8}
                    style={{
                      width: '100%', padding: '9px 40px 9px 12px',
                      border: '1px solid var(--color-border)', borderRadius: '8px',
                      background: 'var(--color-bg-body)', color: 'var(--color-text-main)',
                      fontSize: '0.9rem', boxSizing: 'border-box',
                    }}
                  />
                  {i === 0 && (
                    <button
                      type="button"
                      onClick={() => setShowPw(p => !p)}
                      style={{
                        position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
                        border: 'none', background: 'none', cursor: 'pointer',
                        color: 'var(--color-text-muted)',
                      }}
                    >
                      {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  )}
                </div>
              </div>
            ))}

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%', padding: '11px', border: 'none', borderRadius: '8px',
                background: 'var(--color-primary)', color: '#fff',
                cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: '0.95rem',
                opacity: loading ? 0.7 : 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
              }}
            >
              {loading && <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />}
              {loading ? 'Activating…' : 'Activate Account'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};
