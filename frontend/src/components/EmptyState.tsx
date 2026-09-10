import React from 'react';
import { FileText, type LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ 
  icon: Icon = FileText, 
  title, 
  description, 
  action 
}) => {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 'var(--spacing-xl) var(--spacing-md)',
      textAlign: 'center',
      color: 'var(--color-text-muted)'
    }}>
      <Icon size={40} style={{ opacity: 0.5, marginBottom: 'var(--spacing-md)' }} />
      <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--color-text-main)', margin: '0 0 var(--spacing-xs) 0' }}>
        {title}
      </h3>
      <p style={{ margin: '0 0 var(--spacing-md) 0', fontSize: '0.875rem', maxWidth: '300px' }}>
        {description}
      </p>
      {action && <div>{action}</div>}
    </div>
  );
};
