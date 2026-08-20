import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { authService } from '../services/auth';
import { Eye, EyeOff, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';

const styles = {
  container: {
    width: '100%',
    maxWidth: '400px',
    padding: 'var(--spacing-lg)',
    margin: '0 auto',
  },
  logo: {
    textAlign: 'center' as const,
    fontSize: '2rem',
    fontWeight: 700,
    color: 'var(--color-primary)',
    marginBottom: 'var(--spacing-xl)',
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

export const ResetPasswordPage: React.FC = () => {
  const { uid, token } = useParams<{ uid: string; token: string }>();
  
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPassword || !confirmPassword) return;

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (!uid || !token) {
      setError('Invalid reset link. Missing token parameters.');
      return;
    }

    setSubmitting(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const msg = await authService.confirmPasswordReset(uid, token, newPassword, confirmPassword);
      setSuccessMsg(msg);
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setError(err.message || 'Failed to reset password. The link might be expired or invalid.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.logo}>SmartHR</div>
      <div style={styles.card}>
        <h2 style={styles.title}>Reset Password</h2>
        <p style={styles.subtitle}>Enter your new password below</p>
        
        {error && (
          <div style={styles.errorBox}>
            <AlertCircle size={18} /> {error}
          </div>
        )}

        {successMsg && (
          <div style={styles.successBox}>
            <CheckCircle size={18} /> {successMsg}
          </div>
        )}

        {!successMsg && (
          <form onSubmit={handleSubmit}>
            <div style={styles.formGroup}>
              <label style={styles.label}>New Password</label>
              <div style={styles.passwordWrapper}>
                <input 
                  type={showPassword ? 'text' : 'password'} 
                  style={styles.input} 
                  placeholder="********"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                />
                <button 
                  type="button" 
                  style={styles.eyeButton} 
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
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
                  placeholder="********"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
              </div>
            </div>

            <button type="submit" style={styles.button} disabled={submitting}>
              {submitting ? <Loader2 size={18} className="animate-spin" /> : 'Reset Password'}
            </button>
          </form>
        )}

        {successMsg && (
          <Link to="/login" style={styles.button}>
            Return to Login
          </Link>
        )}

        {!successMsg && (
          <Link to="/login" style={styles.footerLink}>
            &lt; Back to Login
          </Link>
        )}
      </div>
    </div>
  );
};
