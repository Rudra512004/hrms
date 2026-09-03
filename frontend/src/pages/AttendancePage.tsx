import React, { useState, useEffect } from 'react';
import { Card } from '../components/Card';
import { Table } from '../components/Table';
import { StatusBadge } from '../components/StatusBadge';
import { LogIn, LogOut, AlertCircle, Loader2, Pause, Play } from 'lucide-react';
import { attendanceService, type AttendanceRecord } from '../services/attendance';

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 'var(--spacing-xl)',
  },
  header: {
    marginBottom: 'var(--spacing-md)',
  },
  title: {
    fontSize: '1.5rem',
    fontWeight: 700,
    color: 'var(--color-text-main)',
    margin: '0 0 var(--spacing-xs) 0',
  },
  subtitle: {
    color: 'var(--color-text-muted)',
    margin: 0,
    fontSize: '0.95rem',
  },
  timerContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    padding: 'var(--spacing-xl)',
    gap: 'var(--spacing-md)',
    backgroundColor: 'var(--color-bg-card)',
  },
  timerText: {
    fontSize: '3.5rem',
    fontWeight: 700,
    fontVariantNumeric: 'tabular-nums',
    color: 'var(--color-text-main)',
    margin: 0,
    lineHeight: 1,
  },
  timerLabel: {
    fontSize: '1rem',
    fontWeight: 600,
    letterSpacing: '0.05em',
    textTransform: 'uppercase' as const,
  },
  actions: {
    display: 'flex',
    gap: 'var(--spacing-md)',
    marginTop: 'var(--spacing-md)',
    width: '100%',
    maxWidth: '400px',
  },
  alert: {
    padding: 'var(--spacing-md)',
    borderRadius: 'var(--radius-md)',
    backgroundColor: 'var(--color-status-danger)15',
    color: 'var(--color-status-danger)',
    border: '1px solid var(--color-status-danger)30',
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-sm)',
    marginBottom: 'var(--spacing-md)',
  },
  centerState: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '400px',
    color: 'var(--color-text-muted)',
  },
  tableContainer: {
    overflowX: 'auto' as const,
  },
  summaryGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
    gap: 'var(--spacing-md)',
    width: '100%',
    maxWidth: '500px',
    marginTop: 'var(--spacing-md)',
    paddingTop: 'var(--spacing-md)',
    borderTop: '1px solid var(--color-border)',
  },
  summaryItem: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '4px',
  },
  summaryLabel: {
    fontSize: '0.85rem',
    color: 'var(--color-text-muted)',
    fontWeight: 500,
  },
  summaryValue: {
    fontSize: '1.1rem',
    color: 'var(--color-text-main)',
    fontWeight: 600,
  }
};

const formatTimeOnly = (isoString: string | null) => {
  if (!isoString) return '--:--';
  return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const formatDate = (dateString: string) => {
  if (!dateString) return '';
  return new Date(dateString).toLocaleDateString([], { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
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
  // formats: "HH:MM:SS" or "DD HH:MM:SS"
  const parts = dur.split(' ');
  let timePart = parts.length === 2 ? parts[1] : parts[0];
  const [h, m, s] = timePart.split(':').map(Number);
  let days = parts.length === 2 ? parseInt(parts[0]) : 0;
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
    const interval = setInterval(() => {
      setNowMs(Date.now());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const loadAttendance = async () => {
    try {
      setLoading(true);
      const data = await attendanceService.getHistory();
      setHistory(data);
    } catch {
      setError("Failed to load attendance history.");
    } finally {
      setLoading(false);
    }
  };

  const handleError = (err: any) => {
    if (err?.response?.status === 403) {
      setError("Attendance actions are currently unavailable from your current network or location.");
    } else if (err?.errorData?.detail) {
      setError(err.errorData.detail);
    } else {
      setError("An unexpected error occurred.");
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
  const todayRecord = history.find(r => r.date === todayStr);

  const isCheckedIn = !!todayRecord?.check_in;
  const isCheckedOut = !!todayRecord?.check_out;
  const isOnBreak = !!todayRecord?.is_on_break;

  let productiveMs = 0;
  let activeBreakMs = 0;
  let totalBreakMs = 0;

  if (todayRecord && todayRecord.check_in) {
    if (isCheckedOut) {
      productiveMs = parseDjangoDuration(todayRecord.productive_work_duration);
      totalBreakMs = parseDjangoDuration(todayRecord.total_break_duration);
    } else {
      const startMs = new Date(todayRecord.check_in).getTime();
      const endMs = nowMs;
      const totalElapsed = endMs - startMs;

      for (const b of (todayRecord.breaks || [])) {
        const bStart = new Date(b.started_at).getTime();
        const bEnd = b.ended_at ? new Date(b.ended_at).getTime() : nowMs;
        const dur = bEnd - bStart;
        totalBreakMs += dur;
        if (!b.ended_at) {
          activeBreakMs = dur;
        }
      }
      productiveMs = Math.max(0, totalElapsed - totalBreakMs);
    }
  }

  if (loading && history.length === 0) {
    return (
      <div style={styles.centerState}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite', marginBottom: 'var(--spacing-md)' }} />
        <p>Loading attendance data...</p>
      </div>
    );
  }

  const columns = [
    { key: 'date', title: 'Date', render: (r: AttendanceRecord) => formatDate(r.date) },
    { key: 'check_in', title: 'Check In', render: (r: AttendanceRecord) => formatTimeOnly(r.check_in) },
    { key: 'check_out', title: 'Check Out', render: (r: AttendanceRecord) => formatTimeOnly(r.check_out) },
    { key: 'break', title: 'Break', render: (r: AttendanceRecord) => (r.total_break_duration || (r.breaks && r.breaks.length > 0)) ? formatDurationMs(parseDjangoDuration(r.total_break_duration) || r.breaks.reduce((acc, b) => acc + ((b.ended_at ? new Date(b.ended_at).getTime() : new Date().getTime()) - new Date(b.started_at).getTime()), 0)) : '00:00:00' },
    { key: 'work', title: 'Work Hours', render: (r: AttendanceRecord) => r.productive_work_duration ? formatDurationMs(parseDjangoDuration(r.productive_work_duration)) : (r.check_in && !r.check_out ? formatDurationMs(new Date().getTime() - new Date(r.check_in).getTime() - (r.breaks || []).reduce((acc, b) => acc + ((b.ended_at ? new Date(b.ended_at).getTime() : new Date().getTime()) - new Date(b.started_at).getTime()), 0)) : '00:00:00') },
    { key: 'status', title: 'Status', render: (r: AttendanceRecord) => <StatusBadge status={r.status as any} /> },
  ];

  let timerStateLabel = "NOT CHECKED IN";
  let timerStateColor = "var(--color-text-muted)";
  let mainTimerDisplay = "00:00:00";

  if (isCheckedOut) {
    timerStateLabel = "COMPLETED";
    timerStateColor = "var(--color-status-success)";
    mainTimerDisplay = formatDurationMs(productiveMs);
  } else if (isOnBreak) {
    timerStateLabel = "ON BREAK";
    timerStateColor = "var(--color-status-warning)";
    mainTimerDisplay = formatDurationMs(activeBreakMs);
  } else if (isCheckedIn) {
    timerStateLabel = "WORKING";
    timerStateColor = "var(--color-status-success)";
    mainTimerDisplay = formatDurationMs(productiveMs);
  }

  return (
    <div style={styles.container} className="animate-fade-in">
      <div style={styles.header}>
        <h1 style={styles.title}>My Attendance</h1>
        <p style={styles.subtitle}>Manage your daily check-in and breaks</p>
      </div>

      {error && (
        <div style={styles.alert}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      <Card className="transition-all">
        <div style={styles.timerContainer}>
          <div style={{ ...styles.timerLabel, color: timerStateColor }}>
            {timerStateLabel}
          </div>
          <div style={styles.timerText}>
            {mainTimerDisplay}
          </div>

          <div style={styles.actions}>
            {!isCheckedIn && !isCheckedOut && (
              <button
                onClick={() => handleAction(attendanceService.checkIn)}
                disabled={actionLoading}
                className="btn btn-primary"
                style={{ flex: 1 }}
              >
                {actionLoading ? <Loader2 size={18} className="animate-spin" /> : <LogIn size={18} />}
                Check In
              </button>
            )}

            {isCheckedIn && !isCheckedOut && !isOnBreak && (
              <>
                <button
                  onClick={() => handleAction(attendanceService.startBreak)}
                  disabled={actionLoading}
                  className="btn btn-secondary"
                  style={{ flex: 1 }}
                >
                  {actionLoading ? <Loader2 size={18} className="animate-spin" /> : <Pause size={18} />}
                  Start Break
                </button>
                <button
                  onClick={() => handleAction(attendanceService.checkOut)}
                  disabled={actionLoading}
                  className="btn btn-primary"
                  style={{ flex: 1 }}
                >
                  {actionLoading ? <Loader2 size={18} className="animate-spin" /> : <LogOut size={18} />}
                  Check Out
                </button>
              </>
            )}

            {isCheckedIn && !isCheckedOut && isOnBreak && (
              <button
                onClick={() => handleAction(attendanceService.endBreak)}
                disabled={actionLoading}
                className="btn btn-primary"
                style={{ flex: 1 }}
              >
                {actionLoading ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
                End Break
              </button>
            )}
          </div>

          {isCheckedIn && (
            <div style={styles.summaryGrid}>
              <div style={styles.summaryItem}>
                <span style={styles.summaryLabel}>Check In</span>
                <span style={styles.summaryValue}>{formatTimeOnly(todayRecord?.check_in || null)}</span>
              </div>
              <div style={styles.summaryItem}>
                <span style={styles.summaryLabel}>Check Out</span>
                <span style={styles.summaryValue}>{formatTimeOnly(todayRecord?.check_out || null)}</span>
              </div>
              <div style={styles.summaryItem}>
                <span style={styles.summaryLabel}>Break Time</span>
                <span style={styles.summaryValue}>{formatDurationMs(totalBreakMs)}</span>
              </div>
              <div style={styles.summaryItem}>
                <span style={styles.summaryLabel}>Productive</span>
                <span style={styles.summaryValue}>{formatDurationMs(productiveMs)}</span>
              </div>
            </div>
          )}
        </div>
      </Card>

      <div>
        <h3 style={{ ...styles.title, fontSize: '1.25rem', marginBottom: 'var(--spacing-md)' }}>Attendance History</h3>
        <Card>
          <div style={styles.tableContainer}>
            <Table
              columns={columns}
              data={history}
              keyExtractor={(r) => r.id.toString()}
            />
          </div>
        </Card>
      </div>
    </div>
  );
};
