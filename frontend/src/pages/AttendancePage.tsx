import React, { useState, useEffect } from 'react';
import { Card } from '../components/Card';
import { Table } from '../components/Table';
import { StatusBadge } from '../components/StatusBadge';
import { LogIn, LogOut, AlertCircle, Loader2 } from 'lucide-react';
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
  todayCard: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 'var(--spacing-md)',
  },
  todayHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid var(--color-border)',
    paddingBottom: 'var(--spacing-sm)',
    marginBottom: 'var(--spacing-sm)',
  },
  todayDate: {
    fontSize: '1.1rem',
    fontWeight: 600,
    color: 'var(--color-text-main)',
    margin: 0,
  },
  timeRow: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '8px 0',
  },
  timeLabel: {
    color: 'var(--color-text-muted)',
    fontWeight: 500,
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  timeValue: {
    color: 'var(--color-text-main)',
    fontWeight: 600,
  },
  actions: {
    display: 'flex',
    gap: 'var(--spacing-md)',
    marginTop: 'var(--spacing-md)',
    paddingTop: 'var(--spacing-md)',
    borderTop: '1px solid var(--color-border)',
  },
  btn: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    padding: '10px 16px',
    borderRadius: 'var(--radius-md)',
    fontSize: '0.95rem',
    fontWeight: 600,
    cursor: 'pointer',
    border: 'none',
    transition: 'background-color 0.2s',
    flex: 1,
  },
  btnPrimary: {
    backgroundColor: 'var(--color-primary)',
    color: '#fff',
  },
  btnSecondary: {
    backgroundColor: 'var(--color-status-warning)',
    color: '#fff',
  },
  btnDisabled: {
    backgroundColor: 'var(--color-text-muted)',
    cursor: 'not-allowed',
    opacity: 0.7,
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
  }
};

const formatTime = (isoString: string | null) => {
  if (!isoString) return '--:--';
  return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const formatDate = (dateString: string) => {
  if (!dateString) return '';
  return new Date(dateString).toLocaleDateString([], { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
};

export const AttendancePage: React.FC = () => {
  const [history, setHistory] = useState<AttendanceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAttendance();
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

  const handleCheckIn = async () => {
    try {
      setActionLoading(true);
      setError(null);
      await attendanceService.checkIn();
      await loadAttendance();
    } catch (err: any) {
      handleError(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCheckOut = async () => {
    try {
      setActionLoading(true);
      setError(null);
      await attendanceService.checkOut();
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
    { key: 'status', title: 'Status', render: (r: AttendanceRecord) => <StatusBadge status={r.status as any} /> },
    { key: 'check_in', title: 'Check In', render: (r: AttendanceRecord) => formatTime(r.check_in) },
    { key: 'check_out', title: 'Check Out', render: (r: AttendanceRecord) => formatTime(r.check_out) },
  ];

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>My Attendance</h1>
        <p style={styles.subtitle}>Manage your daily check-in and check-out</p>
      </div>

      {error && (
        <div style={styles.alert}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      <Card>
        <div style={styles.todayCard}>
          <div style={styles.todayHeader}>
            <h3 style={styles.todayDate}>{formatDate(todayStr)}</h3>
            {todayRecord ? <StatusBadge status={todayRecord.status as any} /> : <StatusBadge status="absent" />}
          </div>
          
          <div style={styles.timeRow}>
            <span style={styles.timeLabel}><LogIn size={18} /> Check In Time</span>
            <span style={styles.timeValue}>{formatTime(todayRecord?.check_in || null)}</span>
          </div>
          
          <div style={styles.timeRow}>
            <span style={styles.timeLabel}><LogOut size={18} /> Check Out Time</span>
            <span style={styles.timeValue}>{formatTime(todayRecord?.check_out || null)}</span>
          </div>

          <div style={styles.actions}>
            <button
              onClick={handleCheckIn}
              disabled={actionLoading || isCheckedIn}
              style={{ ...styles.btn, ...(actionLoading || isCheckedIn ? styles.btnDisabled : styles.btnPrimary) }}
            >
              {actionLoading && !isCheckedIn ? <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} /> : <LogIn size={18} />}
              Check In
            </button>
            <button
              onClick={handleCheckOut}
              disabled={actionLoading || !isCheckedIn || isCheckedOut}
              style={{ ...styles.btn, ...(actionLoading || !isCheckedIn || isCheckedOut ? styles.btnDisabled : styles.btnSecondary) }}
            >
              {actionLoading && isCheckedIn && !isCheckedOut ? <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} /> : <LogOut size={18} />}
              Check Out
            </button>
          </div>
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
