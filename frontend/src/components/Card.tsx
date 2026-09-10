import React from 'react';

interface CardProps {
  children: React.ReactNode;
  title?: string;
  actions?: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  noPadding?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  title,
  actions,
  className = '',
  style = {},
  noPadding = false,
}) => {
  const hasHeader = title || actions;
  return (
    <div className={`card ${className}`} style={style}>
      {hasHeader && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 'var(--spacing-sm)',
            padding: '14px var(--spacing-lg)',
            borderBottom: '1px solid var(--color-border)',
          }}
        >
          {title && (
            <h3 style={{ margin: 0, fontSize: 'var(--font-size-base)', fontWeight: 600, color: 'var(--color-text-main)' }}>
              {title}
            </h3>
          )}
          {actions && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)', marginLeft: 'auto' }}>
              {actions}
            </div>
          )}
        </div>
      )}
      <div style={noPadding ? {} : { padding: 'var(--spacing-lg)' }}>
        {children}
      </div>
    </div>
  );
};
