import React from 'react';
import { type EmployeeLifecycleEvent } from '../../services/employeeManagement';
import { EmptyState } from '../EmptyState';
import {
  History,
  ArrowRight,
  Loader2,
  AlertCircle,
  Calendar,
  User,
  GitCommit,
  ArrowUpRight,
  LogOut,
  RefreshCw,
  Activity,
  Layers,
} from 'lucide-react';

interface LifecycleHistoryTabProps {
  events: EmployeeLifecycleEvent[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

const getEventBadge = (eventType: string) => {
  switch (eventType) {
    case 'transfer':
      return {
        label: 'Transfer',
        color: '#0284c7',
        bg: '#f0f9ff',
        border: '#bae6fd',
        icon: <Layers size={14} color="#0284c7" />,
      };
    case 'promotion':
      return {
        label: 'Promotion',
        color: '#7026e3',
        bg: '#f5f3ff',
        border: '#ddd6fe',
        icon: <ArrowUpRight size={14} color="#7026e3" />,
      };
    case 'exit':
      return {
        label: 'Exit',
        color: '#dc2626',
        bg: '#fef2f2',
        border: '#fecaca',
        icon: <LogOut size={14} color="#dc2626" />,
      };
    case 'resignation':
      return {
        label: 'Resignation / Notice',
        color: '#d97706',
        bg: '#fffbeb',
        border: '#fde68a',
        icon: <Activity size={14} color="#d97706" />,
      };
    case 'reactivation':
      return {
        label: 'Reactivation',
        color: '#059669',
        bg: '#ecfdf5',
        border: '#a7f3d0',
        icon: <RefreshCw size={14} color="#059669" />,
      };
    default:
      return {
        label: 'Status Change',
        color: '#475569',
        bg: '#f8fafc',
        border: '#e2e8f0',
        icon: <GitCommit size={14} color="#475569" />,
      };
  }
};

export const LifecycleHistoryTab: React.FC<LifecycleHistoryTabProps> = ({
  events,
  loading,
  error,
  onRetry,
}) => {
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '60px' }} data-testid="lifecycle-loading">
        <Loader2 className="animate-spin" size={32} color="var(--color-primary)" />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '32px', textAlign: 'center' }} data-testid="lifecycle-error">
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          color: 'var(--color-status-danger, #dc2626)',
          backgroundColor: 'var(--color-status-danger-bg, #fef2f2)',
          padding: '12px 20px',
          borderRadius: 'var(--radius-md, 8px)',
          border: '1px solid var(--color-status-danger-border, #fecaca)',
          marginBottom: '16px',
        }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
        <div>
          <button className="btn btn-secondary" onClick={onRetry}>
            Retry Loading History
          </button>
        </div>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <EmptyState
        title="No Lifecycle History"
        description="No transfer, promotion, separation, or status change events have been recorded for this employee yet."
        icon={History}
      />
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }} data-testid="lifecycle-history-list">
      {events.map((event) => {
        const badge = getEventBadge(event.event_type);
        const eventTitle = event.event_type_display || badge.label;

        return (
          <div
            key={event.id}
            style={{
              padding: '16px 20px',
              backgroundColor: 'var(--color-bg-card, #ffffff)',
              borderRadius: 'var(--radius-lg, 10px)',
              border: '1px solid var(--color-border)',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
              transition: 'box-shadow 0.15s ease',
            }}
            data-testid={`lifecycle-event-${event.id}`}
          >
            {/* Header row: Badge, Title, Effective Date */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '5px',
                    padding: '3px 10px',
                    borderRadius: '20px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: badge.color,
                    backgroundColor: badge.bg,
                    border: `1px solid ${badge.border}`,
                    textTransform: 'uppercase',
                    letterSpacing: '0.03em',
                  }}
                >
                  {badge.icon}
                  {eventTitle}
                </span>

                <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Calendar size={13} /> Effective: <strong style={{ color: 'var(--color-text-main)' }}>{event.effective_date}</strong>
                </span>
              </div>

              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <User size={13} /> {event.created_by_email ? `By ${event.created_by_email}` : 'System'} &bull;{' '}
                {new Date(event.created_at).toLocaleDateString(undefined, {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                })}
              </div>
            </div>

            {/* Event Specific Diffs / Details */}
            <div style={{ fontSize: '0.9rem', color: 'var(--color-text-sub)' }}>
              {event.event_type === 'transfer' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span>
                    <strong>{event.from_branch_name || 'No Branch'}</strong> ({event.from_department_name || 'No Dept'})
                  </span>
                  <ArrowRight size={14} color="var(--color-primary)" />
                  <span style={{ color: 'var(--color-primary)', fontWeight: 600 }}>
                    <strong>{event.to_branch_name || 'No Branch'}</strong> ({event.to_department_name || 'No Dept'})
                  </span>
                </div>
              )}

              {event.event_type === 'promotion' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span>{event.from_designation_name || 'Previous Designation'}</span>
                  <ArrowRight size={14} color="var(--color-primary)" />
                  <span style={{ color: 'var(--color-primary)', fontWeight: 600 }}>
                    {event.to_designation_name || 'Promoted Designation'}
                  </span>
                </div>
              )}

              {(event.event_type === 'status_change' || event.event_type === 'resignation' || event.event_type === 'exit' || event.event_type === 'reactivation') && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span style={{ textTransform: 'capitalize' }}>{event.from_status || '—'}</span>
                  <ArrowRight size={14} color="var(--color-primary)" />
                  <span style={{ color: badge.color, fontWeight: 600, textTransform: 'capitalize' }}>
                    {event.to_status || '—'}
                  </span>
                </div>
              )}
            </div>

            {/* Reason */}
            {event.reason && (
              <div style={{
                fontSize: '0.82rem',
                color: 'var(--color-text-muted)',
                backgroundColor: 'var(--color-bg-secondary, #f8fafc)',
                padding: '6px 12px',
                borderRadius: '6px',
                borderLeft: `3px solid ${badge.color}`,
              }}>
                <span style={{ fontWeight: 500 }}>Reason:</span> {event.reason}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
