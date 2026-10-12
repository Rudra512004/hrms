import React, { useState, useEffect } from 'react';
import {
  Clock,
  LogIn,
  LogOut,
  Coffee,
  Loader2,
  ChevronRight,
  CheckCircle2,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { StatusBadge } from '../StatusBadge';
import { AlertBanner } from '../AlertBanner';
import { type PersonalAttendanceToday } from '../../services/dashboard';

interface TodayAttendanceCardProps {
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

export const TodayAttendanceCard: React.FC<TodayAttendanceCardProps> = ({
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
  const [currentTime, setCurrentTime] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(
        now.toLocaleTimeString(undefined, {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true,
        })
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  // Derive authoritative break duration from backend timestamps
  const calculateBreakDuration = (): number => {
    const baseCompleted = attendance?.total_break_duration_seconds ?? 0;
    if (!attendance?.is_on_break || !attendance.current_break_started_at) {
      return baseCompleted;
    }
    const startedMs = new Date(attendance.current_break_started_at).getTime();
    if (isNaN(startedMs)) {
      return baseCompleted;
    }
    const nowMs = Date.now();
    // Clamp to non-negative to handle any local/server clock skew
    const elapsedSeconds = Math.max(0, Math.floor((nowMs - startedMs) / 1000));
    return baseCompleted + elapsedSeconds;
  };

  const [liveBreakDuration, setLiveBreakDuration] = useState<number>(calculateBreakDuration);

  // Sync state whenever attendance prop changes
  useEffect(() => {
    setLiveBreakDuration(calculateBreakDuration());
  }, [
    attendance?.is_on_break,
    attendance?.total_break_duration_seconds,
    attendance?.current_break_started_at,
  ]);

  // Periodic ~1-minute timer and visibilitychange listener
  useEffect(() => {
    if (!attendance?.is_on_break) return;

    const syncDuration = () => {
      setLiveBreakDuration(calculateBreakDuration());
    };

    // Update approximately once per minute
    const timerId = setInterval(syncDuration, 60000);

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        syncDuration();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(timerId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [
    attendance?.is_on_break,
    attendance?.total_break_duration_seconds,
    attendance?.current_break_started_at,
  ]);

  const getStatusInfo = () => {
    if (!attendance || !attendance.check_in) {
      return {
        badgeStatus: 'neutral' as const,
        label: 'Not Clocked In',
        text: 'Not Clocked In',
        description: 'Record your arrival to begin shift tracking',
      };
    }
    if (attendance.check_out) {
      return {
        badgeStatus: 'present' as const,
        label: 'Shift Completed',
        text: 'Shift Completed',
        description: 'All shift punches recorded for today',
      };
    }
    if (attendance.is_on_break) {
      let desc = 'Break time is being tracked';
      if (attendance.current_break_started_at) {
        const d = new Date(attendance.current_break_started_at);
        if (!isNaN(d.getTime())) {
          desc = `Break started at ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
        }
      }
      return {
        badgeStatus: 'warning' as const,
        label: 'On Break',
        text: 'Currently On Break',
        description: desc,
      };
    }
    return {
      badgeStatus: 'info' as const,
      label: 'Working Now',
      text: 'Working Now',
      description: 'Productive work duration active',
    };
  };

  const statusInfo = getStatusInfo();

  return (
    <div
      data-testid="today-attendance-card"
      style={{
        backgroundColor: 'var(--color-bg-card)',
        borderRadius: 'var(--radius-xl)',
        padding: '24px',
        border: '1px solid var(--color-border)',
        boxShadow: 'var(--shadow-sm)',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
      }}
    >
      {/* Header: Title + Digital Clock */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          borderBottom: '1px solid var(--color-border-subtle)',
          paddingBottom: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'rgba(31, 93, 54, 0.1)',
              color: 'var(--color-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Clock size={20} />
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
              Today's Attendance
            </h2>
            <p style={{ margin: 0, fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
              Work shift controls and real-time punch state
            </p>
          </div>
        </div>

        {/* Real-time Clock Pill */}
        <div
          style={{
            backgroundColor: 'var(--color-bg-subtle)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: 'var(--radius-full)',
            padding: '6px 14px',
            fontSize: 'var(--font-size-sm)',
            fontWeight: 700,
            color: 'var(--color-text-main)',
            fontVariantNumeric: 'tabular-nums',
            letterSpacing: '0.04em',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor:
                attendance?.check_in && !attendance.check_out
                  ? 'var(--color-status-success)'
                  : 'var(--color-text-muted)',
              display: 'inline-block',
            }}
          />
          {currentTime || 'Loading time...'}
        </div>
      </div>

      {loading ? (
        <div className="loading-center" style={{ padding: '36px' }}>
          <Loader2 size={24} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
        </div>
      ) : (
        <>
          {actionError && <AlertBanner type="error" message={actionError} />}

          {/* Current Punch Status Hero Strip */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '16px 18px',
              backgroundColor: 'var(--color-bg-page)',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-border)',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
                <span
                  style={{
                    fontSize: 'var(--font-size-base)',
                    fontWeight: 700,
                    color: 'var(--color-text-main)',
                  }}
                >
                  {statusInfo.text}
                </span>
              </div>
              <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                {statusInfo.description}
              </span>
            </div>
            <StatusBadge status={statusInfo.badgeStatus} label={statusInfo.label} />
          </div>

          {/* Detailed Timestamps & Worked Durations */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
              gap: '12px',
            }}
          >
            <div
              style={{
                padding: '12px 14px',
                backgroundColor: 'var(--color-bg-subtle)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border-subtle)',
              }}
            >
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 500, marginBottom: '4px' }}>
                Punch In
              </div>
              <div style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
                {attendance?.check_in
                  ? new Date(attendance.check_in).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  : '--:--'}
              </div>
            </div>

            <div
              style={{
                padding: '12px 14px',
                backgroundColor: 'var(--color-bg-subtle)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border-subtle)',
              }}
            >
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 500, marginBottom: '4px' }}>
                Punch Out
              </div>
              <div style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
                {attendance?.check_out
                  ? new Date(attendance.check_out).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  : '--:--'}
              </div>
            </div>

            <div
              style={{
                padding: '12px 14px',
                backgroundColor: 'var(--color-bg-subtle)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border-subtle)',
              }}
            >
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 500, marginBottom: '4px' }}>
                Worked Time
              </div>
              <div style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--color-status-success)' }}>
                {attendance?.check_in ? formatSeconds(attendance.productive_work_duration_seconds) : '--'}
              </div>
            </div>

            <div
              style={{
                padding: '12px 14px',
                backgroundColor: 'var(--color-bg-subtle)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border-subtle)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 500 }}>
                  Break Time
                </span>
                {attendance?.check_in && attendance?.is_on_break && (
                  <span
                    data-testid="live-break-badge"
                    style={{
                      fontSize: '10px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                      backgroundColor: 'rgba(217, 119, 6, 0.15)',
                      color: 'var(--color-status-warning)',
                      padding: '2px 6px',
                      borderRadius: 'var(--radius-full)',
                    }}
                  >
                    Live
                  </span>
                )}
              </div>
              <div
                data-testid="live-break-duration"
                style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--color-status-warning)' }}
              >
                {attendance?.check_in ? formatSeconds(liveBreakDuration) : '--'}
              </div>
            </div>
          </div>

          {/* Interactive Punch & Break Controls */}
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', paddingTop: '4px' }}>
            {!attendance || !attendance.check_in ? (
              <button
                className="btn btn-primary"
                onClick={onCheckIn}
                disabled={actionLoading}
                style={{ flex: 1, minWidth: '160px', padding: '12px 20px', fontSize: 'var(--font-size-base)', fontWeight: 600 }}
                type="button"
              >
                {actionLoading ? <Loader2 size={18} className="animate-spin" /> : <LogIn size={18} />}
                Web Punch In
              </button>
            ) : !attendance.check_out ? (
              <>
                <button
                  className="btn btn-primary"
                  onClick={onCheckOut}
                  disabled={actionLoading}
                  style={{ flex: 1, minWidth: '130px', padding: '12px 16px', fontWeight: 600 }}
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
                    style={{ flex: 1, minWidth: '130px', padding: '12px 16px', fontWeight: 600 }}
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
                    style={{ flex: 1, minWidth: '130px', padding: '12px 16px', fontWeight: 600 }}
                    type="button"
                  >
                    {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <Coffee size={16} />}
                    Take Break
                  </button>
                )}
              </>
            ) : (
              <div
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'rgba(46, 125, 79, 0.08)',
                  color: 'var(--color-status-success)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  fontSize: 'var(--font-size-sm)',
                  fontWeight: 600,
                }}
              >
                <CheckCircle2 size={18} />
                Daily punch sequence complete for today.
              </div>
            )}
          </div>

          {/* Navigation Footer */}
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
              onClick={() => navigate('/attendance')}
              style={{ fontSize: 'var(--font-size-xs)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
              type="button"
            >
              View Complete Attendance History <ChevronRight size={14} />
            </button>
          </div>
        </>
      )}
    </div>
  );
};
