import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { authService } from '../services/auth';
import { useAuth } from '../contexts/AuthContext';
import { Eye, EyeOff } from 'lucide-react';

const styles = {
  container: {
    width: '100%',
    maxWidth: '420px',
    padding: 'var(--spacing-md)',
    margin: '0 auto',
  },
  logo: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 'var(--spacing-xl)',
  },
  logoImage: {
    width: '100%',
    maxWidth: '220px',
    height: 'auto',
    objectFit: 'contain' as const,
    display: 'block',
  },
  card: {
    backgroundColor: 'var(--color-bg-card)',
    padding: '32px 28px',
    borderRadius: 'var(--radius-xl)',
    border: '1px solid var(--color-border)',
    boxShadow: 'var(--shadow-lg)',
  },
  title: {
    fontSize: '1.35rem',
    fontWeight: 700,
    textAlign: 'center' as const,
    color: 'var(--color-text-main)',
    marginBottom: '4px',
    letterSpacing: '-0.02em',
  },
  subtitle: {
    fontSize: 'var(--font-size-sm)',
    color: 'var(--color-text-muted)',
    textAlign: 'center' as const,
    marginBottom: 'var(--spacing-lg)',
  },
  formGroup: {
    marginBottom: 'var(--spacing-md)',
  },
  label: {
    display: 'block',
    marginBottom: '6px',
    fontSize: 'var(--font-size-sm)',
    fontWeight: 500,
    color: 'var(--color-text-sub)',
  },
  input: {
    width: '100%',
    padding: '10px 14px',
    paddingRight: '2.5rem',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--color-border)',
    fontSize: 'var(--font-size-sm)',
    color: 'var(--color-text-main)',
    backgroundColor: 'var(--color-bg-surface)',
    outline: 'none',
    transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
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
  options: {
    display: 'flex',
    justifyContent: 'flex-end',
    alignItems: 'center',
    marginBottom: 'var(--spacing-lg)',
    fontSize: 'var(--font-size-xs)',
  },
  button: {
    width: '100%',
    padding: '11px 16px',
    background: 'linear-gradient(135deg, var(--color-primary) 0%, #8b5cf6 100%)',
    color: 'white',
    border: '1px solid var(--color-primary)',
    borderRadius: 'var(--radius-md)',
    fontSize: 'var(--font-size-sm)',
    fontWeight: 600,
    cursor: 'pointer',
    boxShadow: '0 4px 14px rgba(112, 38, 227, 0.28)',
    transition: 'all 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
  },
  link: {
    color: 'var(--color-primary)',
    textDecoration: 'none',
    fontWeight: 500,
  },
  footer: {
    textAlign: 'center' as const,
    marginTop: 'var(--spacing-lg)',
    fontSize: '0.85rem',
    color: 'var(--color-text-muted)',
  }
};

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { refreshAuth } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      await authService.login(email.toLowerCase().trim(), password);
      await refreshAuth();
      // Temporary redirect for development shell
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.logo}>
        <img src="/beyondsure-logo.webp" alt="BeyondSure HRMS" style={styles.logoImage} />
      </div>
      <div style={styles.card}>
        <h2 style={styles.title}>Welcome Back</h2>
        <p style={styles.subtitle}>Sign in to your organization workspace</p>

        {error && (
          <div style={{
            backgroundColor: 'var(--color-status-danger-bg)',
            color: 'var(--color-status-danger)',
            border: '1px solid var(--color-status-danger-border)',
            padding: '10px 14px',
            borderRadius: 'var(--radius-md)',
            marginBottom: 'var(--spacing-md)',
            fontSize: 'var(--font-size-xs)',
            textAlign: 'center',
            fontWeight: 500,
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleLogin}>
          <div style={styles.formGroup}>
            <label style={styles.label}>Company Email</label>
            <input
              type="email"
              style={styles.input}
              placeholder="email@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoCapitalize="none"
              autoCorrect="off"
              required
            />
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Password</label>
            <div style={styles.passwordWrapper}>
              <input
                type={showPassword ? 'text' : 'password'}
                style={styles.input}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
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

          <div style={styles.options}>
            <Link to="/forgot-password" style={styles.link}>Forgot password?</Link>
          </div>

          <button
            type="submit"
            style={{
              ...styles.button,
              opacity: isLoading ? 0.75 : 1,
              cursor: isLoading ? 'not-allowed' : 'pointer'
            }}
            disabled={isLoading}
          >
            {isLoading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
      <div style={styles.footer}>
        Enterprise Grade HR Management System
      </div>
    </div>
  );
};
