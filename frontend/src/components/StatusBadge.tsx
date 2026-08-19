import React from 'react';

export type StatusType = 'active' | 'inactive' | 'pending' | 'approved' | 'rejected' | 'present' | 'absent' | 'warning' | 'cancelled';

interface StatusBadgeProps {
  status: StatusType;
  label?: string;
  className?: string;
}

const statusColors: Record<StatusType, string> = {
  active: 'var(--color-status-success)',
  present: 'var(--color-status-success)',
  approved: 'var(--color-status-success)',
  
  inactive: 'var(--color-text-muted)',
  
  pending: 'var(--color-status-pending)',
  
  rejected: 'var(--color-status-danger)',
  absent: 'var(--color-status-danger)',
  
  warning: 'var(--color-status-warning)',
  cancelled: 'var(--color-text-muted)',
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label, className = '' }) => {
  const color = statusColors[status] || 'var(--color-text-muted)';
  
  const style = {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '0.25em 0.6em',
    fontSize: '0.75rem',
    fontWeight: 600,
    lineHeight: 1,
    color: '#fff',
    backgroundColor: color,
    borderRadius: '10px',
  };
  
  return (
    <span style={style} className={className}>
      {label || status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
};
