import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService } from '../services/auth';

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
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--color-border)',
    fontSize: '1rem',
    outline: 'none',
  },
  options: {
    display: 'flex',
    justifyContent: 'flex-end',
    alignItems: 'center',
    marginBottom: 'var(--spacing-lg)',
    fontSize: '0.85rem',
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
  },
  dividerContainer: {
    display: 'flex',
    alignItems: 'center',
    margin: 'var(--spacing-lg) 0',
  },
  dividerLine: {
    flex: 1,
    height: '1px',
    backgroundColor: 'var(--color-border)',
  },
  dividerText: {
    margin: '0 var(--spacing-md)',
    color: 'var(--color-text-muted)',
    fontSize: '0.85rem',
    textTransform: 'uppercase' as const,
  },

  link: {
    color: 'var(--color-primary)',
    textDecoration: 'none',
  },
  footer: {
    textAlign: 'center' as const,
    marginTop: 'var(--spacing-lg)',
    fontSize: '0.9rem',
  }
};

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    await authService.login(email, password);
    // Temporary redirect for development shell
    navigate('/dashboard');
  };

  return (
    <div style={styles.container}>
      <div style={styles.logo}>SmartHR</div>
      <div style={styles.card}>
        <h2 style={styles.title}>Welcome Back</h2>
        
        <form onSubmit={handleLogin}>
          <div style={styles.formGroup}>
            <label style={styles.label}>Company Email</label>
            <input 
              type="email" 
              style={styles.input} 
              placeholder="email@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          
          <div style={styles.formGroup}>
            <label style={styles.label}>Password</label>
            <input 
              type="password" 
              style={styles.input} 
              placeholder="********"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          
          <div style={styles.options}>
            <a href="#" style={styles.link} onClick={(e) => e.preventDefault()}>Forgot password?</a>
          </div>
          
          <button type="submit" style={styles.button}>Login</button>
        </form>


      </div>
    </div>
  );
};
