import React from 'react';

interface CardProps {
  children: React.ReactNode;
  title?: string;
  className?: string;
  style?: React.CSSProperties;
}

export const Card: React.FC<CardProps> = ({ children, title, className = '', style = {} }) => {
  return (
    <div className={`card ${className}`} style={{ padding: 0, display: 'flex', flexDirection: 'column', ...style }}>
      {title && (
        <div style={{ padding: 'var(--spacing-md) var(--spacing-lg)', borderBottom: '1px solid var(--color-border)' }}>
          <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 600 }}>{title}</h3>
        </div>
      )}
      <div style={{ padding: 'var(--spacing-lg)', flex: 1 }}>
        {children}
      </div>
    </div>
  );
};
