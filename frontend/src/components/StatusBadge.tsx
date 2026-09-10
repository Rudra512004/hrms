import React from 'react';

export type StatusType =
  | 'active' | 'inactive'
  | 'pending' | 'approved' | 'rejected' | 'cancelled'
  | 'present' | 'absent' | 'half_day' | 'on_leave'
  | 'warning' | 'info'
  | 'onboarding' | 'exited'
  | 'draft' | 'processing' | 'paid' | 'failed' | 'finalized' | 'generated';

interface StatusBadgeProps {
  status: StatusType | string;
  label?: string;
  className?: string;
}

const statusClass: Record<string, string> = {
  // Success
  active:     'badge badge-success',
  present:    'badge badge-success',
  approved:   'badge badge-success',
  paid:       'badge badge-success',
  finalized:  'badge badge-success',
  generated:  'badge badge-success',

  // Pending / In-progress
  pending:    'badge badge-pending',
  onboarding: 'badge badge-pending',

  // Warning
  draft:      'badge badge-warning',
  processing: 'badge badge-warning',
  warning:    'badge badge-warning',
  half_day:   'badge badge-warning',
  on_leave:   'badge badge-warning',

  // Danger
  rejected:   'badge badge-danger',
  failed:     'badge badge-danger',
  cancelled:  'badge badge-danger',
  absent:     'badge badge-danger',
  exited:     'badge badge-danger',

  // Info
  info:       'badge badge-info',

  // Neutral
  inactive:   'badge badge-neutral',
  archived:   'badge badge-neutral',
};

const defaultLabel: Record<string, string> = {
  half_day: 'Half Day',
  on_leave: 'On Leave',
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label, className = '' }) => {
  const normalized = (status || '').toLowerCase();
  const cls = statusClass[normalized] ?? 'badge badge-neutral';
  const text = label ?? defaultLabel[normalized] ?? (
    normalized ? normalized.charAt(0).toUpperCase() + normalized.slice(1).replace(/_/g, ' ') : ''
  );

  return (
    <span className={`${cls} ${className}`}>
      <span className="badge-dot" aria-hidden="true" />
      <span>{text}</span>
    </span>
  );
};
