import React, { useState, useEffect } from 'react';
import { Card } from '../components/Card';
import { Table } from '../components/Table';
import { StatusBadge } from '../components/StatusBadge';
import { PageHeader } from '../components/PageHeader';
import { AlertBanner } from '../components/AlertBanner';
import { LogIn, LogOut, Loader2, Pause, Play, Clock } from 'lucide-react';
import { attendanceService, type AttendanceRecord } from '../services/attendance';

const formatTimeOnly = (isoString: string | null) => {
  if (!isoString) return '--:--';
  return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const formatDate = (dateString: string) => {
  if (!dateString) return '';
  return new Date(dateString + 'T00:00:00').toLocaleDateString([], {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

const formatDurationMs = (ms: number) => {
  if (ms < 0) ms = 0;
  const totalSeconds = Math.floor(ms / 1000);
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
};

const parseDjangoDuration = (dur: string | null) => {
  if (!dur) return 0;
  const parts = dur.split(' ');
  const timePart = parts.length === 2 ? parts[1] : parts[0];
  const [h, m, s] = timePart.split(':').map(Number);
  const days = parts.length === 2 ? parseInt(parts[0]) : 0;
  return (days * 86400 + h * 3600 + m * 60 + (s || 0)) * 1000;
};

export const AttendancePage: React.FC = () => {
  const [history, setHistory] = useState<AttendanceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(Date.now());

  useEffect(() => {
    loadAttendance();
  }, []);

  useEffect(() => {
    const interval = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  const loadAttendance = async () => {
    try {
      setLoading(true);
      const data = await attendanceService.getHistory();
      setHistory(data);
    } catch {
      setError('Failed to load attendance history.');
    } finally {
      setLoading(false);
    }
  };

  const handleError = (err: any) => {
    if (err?.response?.status === 403) {
      setError('Attendance actions are unavailable from your current network or location.');
    } else if (err?.errorData?.detail) {
      setError(err.errorData.detail);
    } else {
      setError('An unexpected error occurred. Please try again.');
    }
  };

  const handleAction = async (actionFn: () => Promise<any>) => {
    try {
      setActionLoading(true);
      setError(null);
      await actionFn();
      await loadAttendance();
    } catch (err: any) {
      handleError(err);
    } finally {
      setActionLoading(false);
    }
  };

  const todayStr = new Date().toISOString().split('T')[0];
  const todayRecord = history.find((r) => r.date === todayStr);

  const isCheckedIn = !!todayRecord?.check_in;
  const isCheckedOut = !!todayRecord?.check_out;
  const isOnBreak = !!todayRecord?.is_on_break;

  let productiveMs = 0;
  let activeBreakMs = 0;
  let totalBreakMs = 0;

  if (todayRecord?.check_in) {
    if (isCheckedOut) {
      productiveMs = parseDjangoDuration(todayRecord.productive_work_duration);
      totalBreakMs = parseDjangoDuration(todayRecord.total_break_duration);
    } else {
      const startMs = new Date(todayRecord.check_in).getTime();
      const totalElapsed = nowMs - startMs;
      for (const b of todayRecord.breaks || []) {
        const bStart = new Date(b.started_at).getTime();
        const bEnd = b.ended_at ? new Date(b.ended_at).getTime() : nowMs;
        const dur = bEnd - bStart;
        totalBreakMs += dur;
        if (!b.ended_at) activeBreakMs = dur;
      }
      productiveMs = Math.max(0, totalElapsed - totalBreakMs);
    }
  }

  let timerStateLabel = 'NOT CHECKED IN';
  let timerStateColor = 'var(--color-text-muted)';
  let mainTimerDisplay = '00:00:00';

  if (isCheckedOut) {
    timerStateLabel = 'COMPLETED';
    timerStateColor = 'var(--color-status-success)';
    mainTimerDisplay = formatDurationMs(productiveMs);
  } else if (isOnBreak) {
    timerStateLabel = 'ON BREAK';
    timerStateColor = 'var(--color-status-warning)';
    mainTimerDisplay = formatDurationMs(activeBreakMs);
  } else if (isCheckedIn) {
    timerStateLabel = 'WORKING';
    timerStateColor = 'var(--color-status-success)';
    mainTimerDisplay = formatDurationMs(productiveMs);
  }

  const columns = [
    {
      key: 'date',
      title: 'Date',
      render: (r: AttendanceRecord) => (
        <span style={{ whiteSpace: 'nowrap' }}>{formatDate(r.date)}</span>
      ),
    },
    { key: 'check_in', title: 'Check In',  render: (r: AttendanceRecord) => formatTimeOnly(r.check_in) },
    { key: 'check_out', title: 'Check Out', render: (r: AttendanceRecord) => formatTimeOnly(r.check_out) },
    {
      key: 'break',
      title: 'Break',
      render: (r: AttendanceRecord) => {
        const ms = r.total_break_duration
          ? parseDjangoDuration(r.total_break_duration)
          : (r.breaks || []).reduce((acc, b) => {
              const end = b.ended_at ? new Date(b.ended_at).getTime() : new Date().getTime();
              return acc + (end - new Date(b.started_at).getTime());
            }, 0);
        return <span style={{ fontVariantNumeric: 'tabular-nums' }}>{formatDurationMs(ms)}</span>;
      },
    },
    {
      key: 'work',
      title: 'Productive',
      render: (r: AttendanceRecord) => {
        let ms = 0;
        if (r.productive_work_duration) {
          ms = parseDjangoDuration(r.productive_work_duration);
        } else if (r.check_in && !r.check_out) {
          const breakMs = (r.breaks || []).reduce((acc, b) => {
            const end = b.ended_at ? new Date(b.ended_at).getTime() : new Date().getTime();
            return acc + (end - new Date(b.started_at).getTime());
          }, 0);
          ms = Math.max(0, new Date().getTime() - new Date(r.check_in).getTime() - breakMs);
        }
        return <span style={{ fontVariantNumeric: 'tabular-nums' }}>{formatDurationMs(ms)}</span>;
      },
    },
    {
      key: 'status',
      title: 'Status',
      render: (r: AttendanceRecord) => <StatusBadge status={r.status as any} />,
    },
  ];

  if (loading && history.length === 0) {
    return (
      <div className="loading-center">
        <Loader2 size={28} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
        <span>Loading attendance…</span>
      </div>
    );
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      <PageHeader
        title="My Attendance"
        subtitle="Manage your daily check-in, check-out, and breaks."
      />

      {error && <AlertBanner type="error" message={error} style={{ marginBottom: 0 }} />}

      {/* Timer Card */}
      <Card>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            padding: 'var(--spacing-xl) var(--spacing-lg)',
            gap: 'var(--spacing-md)',
          }}
        >
          {/* State label */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: 'var(--font-size-xs)',
              fontWeight: 700,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: timerStateColor,
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                backgroundColor: timerStateColor,
                display: 'inline-block',
              }}
            />
            {timerStateLabel}
          </div>

          {/* Main timer */}
          <div
            style={{
              fontSize: '3.5rem',
              fontWeight: 700,
              fontVariantNumeric: 'tabular-nums',
              color: 'var(--color-text-main)',
              lineHeight: 1,
              letterSpacing: '-0.02em',
            }}
          >
            {mainTimerDisplay}
          </div>

          {/* Action buttons */}
          <div
            style={{
              display: 'flex',
              gap: 'var(--spacing-sm)',
              marginTop: 'var(--spacing-sm)',
              width: '100%',
              maxWidth: 420,
            }}
          >
            {!isCheckedIn && !isCheckedOut && (
              <button
                onClick={() => handleAction(attendanceService.checkIn)}
                disabled={actionLoading}
                className="btn btn-primary"
                style={{ flex: 1, padding: '10px 16px' }}
              >
                {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <LogIn size={16} />}
                Check In
              </button>
            )}
            {isCheckedIn && !isCheckedOut && !isOnBreak && (
              <>
                <button
                  onClick={() => handleAction(attendanceService.startBreak)}
                  disabled={actionLoading}
                  className="btn btn-secondary"
                  style={{ flex: 1, padding: '10px 16px' }}
                >
                  {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <Pause size={16} />}
                  Start Break
                </button>
                <button
                  onClick={() => handleAction(attendanceService.checkOut)}
                  disabled={actionLoading}
                  className="btn btn-primary"
                  style={{ flex: 1, padding: '10px 16px' }}
                >
                  {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <LogOut size={16} />}
                  Check Out
                </button>
              </>
            )}
            {isCheckedIn && !isCheckedOut && isOnBreak && (
              <button
                onClick={() => handleAction(attendanceService.endBreak)}
                disabled={actionLoading}
                className="btn btn-warning"
                style={{ flex: 1, padding: '10px 16px' }}
              >
                {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                End Break
              </button>
            )}
          </div>

          {/* Summary row when checked in */}
          {isCheckedIn && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 'var(--spacing-md)',
                width: '100%',
                maxWidth: 480,
                marginTop: 'var(--spacing-md)',
                paddingTop: 'var(--spacing-md)',
                borderTop: '1px solid var(--color-border)',
              }}
            >
              {[
                { label: 'Check In',   value: formatTimeOnly(todayRecord?.check_in || null) },
                { label: 'Check Out',  value: formatTimeOnly(todayRecord?.check_out || null) },
                { label: 'Break',      value: formatDurationMs(totalBreakMs) },
                { label: 'Productive', value: formatDurationMs(productiveMs) },
              ].map(({ label, value }) => (
                <div key={label} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 500, marginBottom: 4 }}>
                    {label}
                  </div>
                  <div style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                    {value}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      {/* History */}
      <Card title="Attendance History" noPadding>
        <Table
          columns={columns}
          data={history}
          keyExtractor={(r) => r.id.toString()}
          emptyIcon={Clock}
          emptyTitle="No attendance records"
          emptyDescription="Your attendance history will appear here after your first check-in."
        />
      </Card>
    </div>
  );
};
