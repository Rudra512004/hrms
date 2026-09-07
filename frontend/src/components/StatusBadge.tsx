import React from 'react';

export type StatusType =
  | 'active' | 'inactive'
  | 'pending' | 'approved' | 'rejected' | 'cancelled'
  | 'present' | 'absent' | 'half_day'
  | 'warning' | 'info'
  | 'onboarding' | 'exited';

interface StatusBadgeProps {
  status: StatusType | string;
  label?: string;
  className?: string;
}

const statusClass: Record<string, string> = {
  active:     'badge badge-success',
  present:    'badge badge-success',
  approved:   'badge badge-success',

  pending:    'badge badge-pending',
  onboarding: 'badge badge-pending',

  rejected:   'badge badge-danger',
  absent:     'badge badge-danger',
  exited:     'badge badge-danger',

  warning:    'badge badge-warning',
  half_day:   'badge badge-warning',

  info:       'badge badge-info',

  inactive:   'badge badge-neutral',
  cancelled:  'badge badge-neutral',
};

const defaultLabel: Record<string, string> = {
  half_day: 'Half Day',
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label, className = '' }) => {
  const cls = statusClass[status] ?? 'badge badge-neutral';
  const text = label ?? defaultLabel[status] ?? (status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, ' '));
  return (
    <span className={`${cls} ${className}`}>
      {text}
    </span>
  );
};
