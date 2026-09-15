import React, { useState } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { authService } from '../services/auth';
import { Eye, EyeOff, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';

const styles = {
  container: {
    width: '100%',
    maxWidth: '400px',
    padding: 'var(--spacing-lg)',
    margin: '0 auto',
  },
  card: {
    backgroundColor: 'var(--color-bg-card)',
    padding: 'var(--spacing-xl)',
    borderRadius: 'var(--radius-lg)',
    boxShadow: 'var(--shadow-md)',
  },
  title: {
    fontSize: '1.25rem',
    fontWeight: 600,
    textAlign: 'center' as const,
    marginBottom: 'var(--spacing-sm)',
  },
  subtitle: {
    fontSize: '0.9rem',
    color: 'var(--color-text-muted)',
    textAlign: 'center' as const,
    marginBottom: 'var(--spacing-lg)',
  },
  formGroup: {
    marginBottom: 'var(--spacing-md)',
  },
  label: {
    display: 'block',
    marginBottom: 'var(--spacing-xs)',
    fontSize: '0.9rem',
    fontWeight: 500,
  },
  input: {
    width: '100%',
    padding: '0.75rem',
    paddingRight: '2.5rem',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--color-border)',
    fontSize: '1rem',
    outline: 'none',
  },
  passwordWrapper: {
    position: 'relative' as const,
    display: 'flex',
    alignItems: 'center',
  },
  eyeButton: {
    position: 'absolute' as const,
    right: '10px',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    color: 'var(--color-text-muted)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '4px',
  },
  button: {
    width: '100%',
    padding: '0.75rem',
    backgroundColor: 'var(--color-primary)',
    color: 'white',
    border: 'none',
    borderRadius: 'var(--radius-sm)',
    fontSize: '1rem',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'background-color 0.2s',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
  },
  footerLink: {
    display: 'block',
    textAlign: 'center' as const,
    marginTop: 'var(--spacing-lg)',
    color: 'var(--color-primary)',
    textDecoration: 'none',
    fontSize: '0.9rem',
  },
  errorBox: {
    backgroundColor: 'rgba(234, 84, 85, 0.1)',
    color: 'var(--color-status-danger)',
    padding: '12px',
    borderRadius: 'var(--radius-md)',
    marginBottom: '16px',
    fontSize: '0.9rem',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  successBox: {
    backgroundColor: 'rgba(40, 199, 111, 0.1)',
    color: 'var(--color-status-success)',
    padding: '12px',
    borderRadius: 'var(--radius-md)',
    marginBottom: '16px',
    fontSize: '0.9rem',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  }
};

export const ActivateAccountPage: React.FC = () => {
  const { uid: paramUid, token: paramToken } = useParams<{ uid?: string; token?: string }>();
  const [searchParams] = useSearchParams();
  const uid = paramUid || searchParams.get('uid') || '';
  const token = paramToken || searchParams.get('token') || '';

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password || !confirmPassword) return;

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (!uid || !token) {
      setError('Invalid activation link. Missing token parameters.');
      return;
    }

    setSubmitting(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const msg = await authService.activateAccount(uid, token, password);
      setSuccessMsg(msg);
      setPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setError(err.message || 'Failed to activate account. The link might be expired or already used.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h2 style={styles.title}>Activate Your Account</h2>
        <p style={styles.subtitle}>
          Create a secure password to activate your HRMS account.
        </p>

        {error && (
          <div style={styles.errorBox}>
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        {successMsg && (
          <div style={styles.successBox}>
            <CheckCircle size={18} />
            <span>{successMsg}</span>
          </div>
        )}

        {successMsg ? (
          <div>
            <Link to="/login" style={styles.button}>
              Proceed to Login
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div style={styles.formGroup}>
              <label style={styles.label}>New Password</label>
              <div style={styles.passwordWrapper}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  style={styles.input}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  disabled={submitting}
                />
                <button
                  type="button"
                  style={styles.eyeButton}
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>Confirm Password</label>
              <div style={styles.passwordWrapper}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  style={styles.input}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm your password"
                  required
                  disabled={submitting}
                />
              </div>
            </div>

            <button
              type="submit"
              style={{
                ...styles.button,
                opacity: submitting ? 0.7 : 1,
                cursor: submitting ? 'not-allowed' : 'pointer'
              }}
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <Loader2 size={18} className="animate-spin" style={{ marginRight: '8px' }} />
                  Activating...
                </>
              ) : (
                'Activate Account'
              )}
            </button>
          </form>
        )}

        <Link to="/login" style={styles.footerLink}>
          Back to Login
        </Link>
      </div>
    </div>
  );
};
