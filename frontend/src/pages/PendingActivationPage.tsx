import React from 'react';
import { Link } from 'react-router-dom';
import { Clock } from 'lucide-react';

const styles = {
  container: {
    width: '100%',
    maxWidth: '500px',
    padding: 'var(--spacing-lg)',
    margin: '0 auto',
    textAlign: 'center' as const,
  },
  card: {
    backgroundColor: 'var(--color-bg-card)',
    padding: 'var(--spacing-xl)',
    borderRadius: 'var(--radius-lg)',
    boxShadow: 'var(--shadow-md)',
  },
  iconWrapper: {
    display: 'flex',
    justifyContent: 'center',
    marginBottom: 'var(--spacing-lg)',
    color: 'var(--color-status-warning)',
  },
  title: {
    fontSize: '1.5rem',
    fontWeight: 600,
    color: 'var(--color-text-main)',
    marginBottom: 'var(--spacing-md)',
  },
  text: {
    fontSize: '1rem',
    color: 'var(--color-text-muted)',
    marginBottom: 'var(--spacing-xl)',
    lineHeight: 1.5,
  },
  button: {
    display: 'inline-block',
    padding: '0.75rem 1.5rem',
    backgroundColor: 'var(--color-primary)',
    color: '#fff',
    textDecoration: 'none',
    borderRadius: 'var(--radius-sm)',
    fontWeight: 600,
  }
};

export const PendingActivationPage: React.FC = () => {
  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.iconWrapper}>
          <Clock size={64} />
        </div>
        <h2 style={styles.title}>Account Pending Activation</h2>
        <p style={styles.text}>
          Your account has been created and is awaiting HRMS activation. 
          An administrator will assign your HRMS ID shortly. You will receive an email once your account is active.
        </p>
        <Link to="/login" style={styles.button}>Return to Login</Link>
      </div>
    </div>
  );
};
