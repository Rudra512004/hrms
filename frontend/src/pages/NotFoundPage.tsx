import React from 'react';
import { Link } from 'react-router-dom';

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '60vh',
    textAlign: 'center' as const,
  },
  code: {
    fontSize: '6rem',
    fontWeight: 700,
    color: 'var(--color-primary)',
    margin: 0,
  },
  message: {
    fontSize: '1.5rem',
    marginBottom: 'var(--spacing-xl)',
    color: 'var(--color-text-muted)',
  },
  button: {
    padding: '0.75rem 1.5rem',
    backgroundColor: 'var(--color-primary)',
    color: '#fff',
    textDecoration: 'none',
    borderRadius: 'var(--radius-sm)',
    fontWeight: 600,
  }
};

export const NotFoundPage: React.FC = () => {
  return (
    <div style={styles.container}>
      <h1 style={styles.code}>404</h1>
      <p style={styles.message}>Oops! Page not found.</p>
      <Link to="/dashboard" style={styles.button}>Back to Home</Link>
    </div>
  );
};
