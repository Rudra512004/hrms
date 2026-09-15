import React from 'react';
import { Clock, LogIn, LogOut, Coffee, Loader2, ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../Card';
import { StatusBadge } from '../StatusBadge';
import { AlertBanner } from '../AlertBanner';
import { type PersonalAttendanceToday } from '../../services/dashboard';

interface PersonalAttendanceWidgetProps {
  attendance: PersonalAttendanceToday | null;
  loading?: boolean;
  actionLoading: boolean;
  actionError: string | null;
  onCheckIn: () => void;
  onCheckOut: () => void;
  onStartBreak: () => void;
  onEndBreak: () => void;
}

const formatSeconds = (seconds: number): string => {
  if (!seconds || seconds <= 0) return '0m';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
};

export const PersonalAttendanceWidget: React.FC<PersonalAttendanceWidgetProps> = ({
  attendance,
  loading = false,
  actionLoading,
  actionError,
  onCheckIn,
  onCheckOut,
  onStartBreak,
  onEndBreak,
}) => {
  const navigate = useNavigate();

  const getStatusInfo = () => {
    if (!attendance) {
      return {
        badgeStatus: 'absent' as const,
        label: 'Not Clocked In',
        text: 'Not Clocked In',
      };
    }
    if (attendance.check_out) {
      return {
        badgeStatus: 'present' as const,
        label: 'Shift Ended',
        text: 'Shift Completed',
      };
    }
    if (attendance.is_on_break) {
      return {
        badgeStatus: 'warning' as const,
        label: 'On Break',
        text: 'Currently On Break',
      };
    }
    return {
      badgeStatus: 'info' as const,
      label: 'Working Now',
      text: 'Working Now',
    };
  };

  const statusInfo = getStatusInfo();

  return (
    <Card title="Today's Attendance Terminal">
      {loading ? (
        <div className="loading-center" style={{ padding: '28px' }}>
          <Loader2 size={24} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
          {actionError && <AlertBanner type="error" message={actionError} />}

          {/* Primary Status Banner */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '14px 16px',
              backgroundColor: 'var(--color-bg-page)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border)',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--color-primary-light)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <Clock size={22} color="var(--color-primary)" />
              </div>
              <div>
                <p
                  style={{
                    margin: 0,
                    fontWeight: 700,
                    fontSize: 'var(--font-size-base)',
                    color: 'var(--color-text-main)',
                  }}
                >
                  {statusInfo.text}
                </p>
                <p style={{ margin: 0, fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                  Punch In:{' '}
                  <strong style={{ color: 'var(--color-text-sub)' }}>
                    {attendance?.check_in
                      ? new Date(attendance.check_in).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      : '--:--'}
                  </strong>
                  {' • '}
                  Punch Out:{' '}
                  <strong style={{ color: 'var(--color-text-sub)' }}>
                    {attendance?.check_out
                      ? new Date(attendance.check_out).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      : '--:--'}
                  </strong>
                </p>
              </div>
            </div>
            <StatusBadge status={statusInfo.badgeStatus} label={statusInfo.label} />
          </div>

          {/* Work & Break Duration Metrics */}
          {attendance && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '12px',
              }}
            >
              <div
                style={{
                  padding: '10px 14px',
                  backgroundColor: 'var(--color-bg-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border-subtle)',
                }}
              >
                <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 500 }}>
                  Productive Work
                </div>
                <div style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--color-status-success)' }}>
                  {formatSeconds(attendance.productive_work_duration_seconds)}
                </div>
              </div>

              <div
                style={{
                  padding: '10px 14px',
                  backgroundColor: 'var(--color-bg-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border-subtle)',
                }}
              >
                <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 500 }}>
                  Break Time
                </div>
                <div style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--color-status-warning)' }}>
                  {formatSeconds(attendance.total_break_duration_seconds)}
                </div>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: 'var(--spacing-sm)', flexWrap: 'wrap' }}>
            {!attendance ? (
              <button
                className="btn btn-primary"
                onClick={onCheckIn}
                disabled={actionLoading}
                style={{ flex: 1, minWidth: '160px', padding: '10px 16px' }}
                type="button"
              >
                {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <LogIn size={16} />}
                Web Punch In
              </button>
            ) : !attendance.check_out ? (
              <>
                <button
                  className="btn btn-primary"
                  onClick={onCheckOut}
                  disabled={actionLoading}
                  style={{ flex: 1, minWidth: '140px', padding: '10px 16px' }}
                  type="button"
                >
                  {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <LogOut size={16} />}
                  Punch Out
                </button>

                {attendance.is_on_break ? (
                  <button
                    className="btn btn-secondary"
                    onClick={onEndBreak}
                    disabled={actionLoading}
                    style={{ flex: 1, minWidth: '140px', padding: '10px 16px' }}
                    type="button"
                  >
                    {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <Coffee size={16} />}
                    End Break
                  </button>
                ) : (
                  <button
                    className="btn btn-secondary"
                    onClick={onStartBreak}
                    disabled={actionLoading}
                    style={{ flex: 1, minWidth: '140px', padding: '10px 16px' }}
                    type="button"
                  >
                    {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <Coffee size={16} />}
                    Take Break
                  </button>
                )}
              </>
            ) : null}
          </div>

          <button
            className="btn btn-ghost"
            onClick={() => navigate('/attendance')}
            style={{ width: '100%', fontSize: 'var(--font-size-xs)', paddingTop: 6, paddingBottom: 6 }}
            type="button"
          >
            View Full Attendance History <ChevronRight size={13} />
          </button>
        </div>
      )}
    </Card>
  );
};
