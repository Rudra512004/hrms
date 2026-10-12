import React from 'react';
import { Calendar, PlusCircle, ChevronRight, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { StatusBadge } from '../StatusBadge';
import { type LeaveRequest } from '../../services/leaves';

interface RecentLeaveRequestsWidgetProps {
  requests: LeaveRequest[];
  loading?: boolean;
}

export const RecentLeaveRequestsWidget: React.FC<RecentLeaveRequestsWidgetProps> = ({
  requests,
  loading = false,
}) => {
  const navigate = useNavigate();

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  const getStatusBadge = (status: LeaveRequest['status']) => {
    switch (status) {
      case 'approved':
        return <StatusBadge status="success" label="Approved" />;
      case 'rejected':
        return <StatusBadge status="danger" label="Rejected" />;
      case 'cancelled':
        return <StatusBadge status="neutral" label="Cancelled" />;
      case 'pending':
      default:
        return <StatusBadge status="warning" label="Pending" />;
    }
  };

  return (
    <div
      data-testid="recent-leave-requests-widget"
      style={{
        backgroundColor: 'var(--color-bg-card)',
        borderRadius: 'var(--radius-xl)',
        padding: '24px',
        border: '1px solid var(--color-border)',
        boxShadow: 'var(--shadow-sm)',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          borderBottom: '1px solid var(--color-border-subtle)',
          paddingBottom: '14px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'rgba(53, 120, 181, 0.1)',
              color: 'var(--color-status-info)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Calendar size={20} />
          </div>
          <div>
            <h2
              style={{
                fontSize: '1.1rem',
                fontWeight: 700,
                margin: 0,
                color: 'var(--color-text-main)',
              }}
            >
              Recent Leave Requests
            </h2>
            <p style={{ margin: 0, fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
              Status of your personal time-off applications
            </p>
          </div>
        </div>

        <button
          className="btn btn-secondary"
          onClick={() => navigate('/leaves')}
          style={{ fontSize: 'var(--font-size-xs)', padding: '6px 12px' }}
          type="button"
        >
          <PlusCircle size={14} /> Apply Leave
        </button>
      </div>

      {loading ? (
        <div className="loading-center" style={{ padding: '36px' }}>
          <Loader2 size={24} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
        </div>
      ) : requests.length === 0 ? (
        <div
          data-testid="leave-requests-empty"
          style={{
            padding: '36px 20px',
            textAlign: 'center',
            backgroundColor: 'var(--color-bg-page)',
            borderRadius: 'var(--radius-lg)',
            border: '1px dashed var(--color-border)',
          }}
        >
          <Calendar size={32} style={{ margin: '0 auto 10px', color: 'var(--color-text-muted)' }} />
          <p style={{ margin: '0 0 6px', fontWeight: 600, color: 'var(--color-text-main)' }}>
            No Leave Requests Found
          </p>
          <p style={{ margin: '0 0 14px', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            You haven't submitted any leave requests yet.
          </p>
          <button
            className="btn btn-primary"
            onClick={() => navigate('/leaves')}
            style={{ fontSize: 'var(--font-size-xs)', padding: '6px 14px' }}
            type="button"
          >
            Apply for Leave
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {requests.slice(0, 5).map((req) => {
            const isSingleDay = req.start_date === req.end_date;
            const dateDisplay = isSingleDay
              ? formatDate(req.start_date)
              : `${formatDate(req.start_date)} - ${formatDate(req.end_date)}`;

            const durationText = req.is_half_day
              ? `0.5 Day (${req.half_day_period === 'second_half' ? '2nd Half' : '1st Half'})`
              : `${req.duration_days || 1} ${Number(req.duration_days) === 1 ? 'Day' : 'Days'}`;

            return (
              <div
                key={req.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px 16px',
                  backgroundColor: 'var(--color-bg-page)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--color-border-subtle)',
                  flexWrap: 'wrap',
                  gap: '10px',
                  transition: 'background-color 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', minWidth: '180px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span
                      style={{
                        fontWeight: 700,
                        fontSize: 'var(--font-size-sm)',
                        color: 'var(--color-text-main)',
                      }}
                    >
                      {req.leave_type_name || 'Leave'}
                    </span>
                    <span
                      style={{
                        fontSize: '0.7rem',
                        fontWeight: 600,
                        padding: '1px 7px',
                        borderRadius: 'var(--radius-full)',
                        backgroundColor: 'var(--color-bg-secondary)',
                        color: 'var(--color-text-sub)',
                      }}
                    >
                      {durationText}
                    </span>
                  </div>
                  <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                    {dateDisplay}
                  </span>
                  {req.reason && (
                    <span
                      style={{
                        fontSize: 'var(--font-size-xs)',
                        color: 'var(--color-text-sub)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        maxWidth: '280px',
                      }}
                      title={req.reason}
                    >
                      "{req.reason}"
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {getStatusBadge(req.status)}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Footer */}
      <div
        style={{
          borderTop: '1px solid var(--color-border-subtle)',
          paddingTop: '12px',
          display: 'flex',
          justifyContent: 'flex-end',
        }}
      >
        <button
          className="btn btn-ghost"
          onClick={() => navigate('/leaves')}
          style={{ fontSize: 'var(--font-size-xs)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
          type="button"
        >
          View All Requests <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
};
