import React from 'react';

interface CardProps {
  children: React.ReactNode;
  title?: string;
  className?: string;
  style?: React.CSSProperties;
}

const styles = {
  card: {
    backgroundColor: 'var(--color-bg-card)',
    borderRadius: 'var(--radius-lg)',
    boxShadow: 'var(--shadow-md)',
    border: '1px solid rgba(255, 255, 255, 0.8)',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column' as const,
  },
  header: {
    padding: 'var(--spacing-md) var(--spacing-lg)',
    borderBottom: '1px solid var(--color-border)',
  },
  title: {
    margin: 0,
    fontSize: '1.1rem',
    fontWeight: 600,
  },
  body: {
    padding: 'var(--spacing-lg)',
    flex: 1,
  }
};

export const Card: React.FC<CardProps> = ({ children, title, className = '', style = {} }) => {
  return (
    <div style={{ ...styles.card, ...style }} className={className}>
      {title && (
        <div style={styles.header}>
          <h3 style={styles.title}>{title}</h3>
        </div>
      )}
      <div style={styles.body}>
        {children}
      </div>
    </div>
  );
};
