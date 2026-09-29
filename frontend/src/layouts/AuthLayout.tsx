import React from 'react';
import { Outlet } from 'react-router-dom';

const styles = {
  authWrapper: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    width: '100%',
    backgroundColor: 'var(--color-bg-body)',
    backgroundImage: 'radial-gradient(ellipse at 50% 0%, var(--color-primary-glow) 0%, var(--color-bg-body) 65%)',
    padding: 'var(--spacing-md)',
  }
};

export const AuthLayout: React.FC = () => {
  return (
    <div style={styles.authWrapper}>
      <Outlet />
    </div>
  );
};
