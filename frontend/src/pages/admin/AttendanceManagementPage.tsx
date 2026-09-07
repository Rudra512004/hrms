import React, { useState, useEffect, useMemo } from 'react';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { AlertCircle, Loader2, Search, Calendar as CalendarIcon } from 'lucide-react';
import { attendanceService, type AttendanceRecord } from '../../services/attendance';
import { useAuth } from '../../contexts/AuthContext';

const styles = {
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 'var(--spacing-lg)',
  },
  title: {
    margin: 0,
    fontSize: '1.25rem',
    color: 'var(--color-text-main)',
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
  input: {
    width: '100%',
    padding: '10px 12px',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-md)',
    backgroundColor: 'var(--color-bg-body)',
    color: 'var(--color-text-main)',
    fontSize: '0.95rem',
  },
};

const formatTimeOnly = (isoString: string | null) => {
  if (!isoString) return '--:--';
  return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
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
  let timePart = parts.length === 2 ? parts[1] : parts[0];
  const [h, m, s] = timePart.split(':').map(Number);
  let days = parts.length === 2 ? parseInt(parts[0]) : 0;
  return (days * 86400 + h * 3600 + m * 60 + (s || 0)) * 1000;
};

export const AttendanceManagementPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const [history, setHistory] = useState<AttendanceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [dateFilter, setDateFilter] = useState(new Date().toISOString().split('T')[0]);
  const [statusFilter, setStatusFilter] = useState('all');

  useEffect(() => {
    loadAttendance();
  }, []);

  const loadAttendance = async () => {
    try {
      setLoading(true);
      const data = await attendanceService.getManagementHistory();
      setHistory(data);
    } catch (err: any) {
      if (err?.response?.status === 403) {
        setError("403 Forbidden: You do not have permission to view global attendance.");
      } else {
        setError("Failed to load attendance history.");
      }
    } finally {
      setLoading(false);
    }
  };

  const filteredHistory = useMemo(() => {
    return history.filter(r => {
      const matchDate = dateFilter === '' || r.date === dateFilter;
      const matchStatus = statusFilter === 'all' || r.status === statusFilter;
      const q = searchQuery.toLowerCase();
      const matchSearch = q === '' ||
        (r.employee_name && r.employee_name.toLowerCase().includes(q)) ||
        (r.employee_code && r.employee_code.toLowerCase().includes(q));
      
      return matchDate && matchStatus && matchSearch;
    });
  }, [history, dateFilter, statusFilter, searchQuery]);

  const columns = [
    { key: 'employee', title: 'Employee', render: (r: AttendanceRecord) => (
      <div>
        <div style={{ fontWeight: 500 }}>{r.employee_name || 'Unknown'}</div>
        <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>{r.employee_code || '-'}</div>
      </div>
    )},
    { key: 'date', title: 'Date', render: (r: AttendanceRecord) => r.date },
    { key: 'check_in', title: 'Check In', render: (r: AttendanceRecord) => formatTimeOnly(r.check_in) },
    { key: 'check_out', title: 'Check Out', render: (r: AttendanceRecord) => formatTimeOnly(r.check_out) },
    { key: 'break', title: 'Break', render: (r: AttendanceRecord) => (r.total_break_duration || (r.breaks && r.breaks.length > 0)) ? formatDurationMs(parseDjangoDuration(r.total_break_duration) || r.breaks.reduce((acc, b) => acc + ((b.ended_at ? new Date(b.ended_at).getTime() : new Date().getTime()) - new Date(b.started_at).getTime()), 0)) : '00:00:00' },
    { key: 'work', title: 'Work Hours', render: (r: AttendanceRecord) => r.productive_work_duration ? formatDurationMs(parseDjangoDuration(r.productive_work_duration)) : (r.check_in && !r.check_out ? formatDurationMs(new Date().getTime() - new Date(r.check_in).getTime() - (r.breaks || []).reduce((acc, b) => acc + ((b.ended_at ? new Date(b.ended_at).getTime() : new Date().getTime()) - new Date(b.started_at).getTime()), 0)) : '00:00:00') },
    { key: 'status', title: 'Status', render: (r: AttendanceRecord) => <StatusBadge status={r.status as any} /> },
  ];

  if (!hasPermission('attendance.view_all')) {
    return (
      <Card>
        <div style={styles.alert}>
          <AlertCircle size={20} />
          <span>You do not have permission to access attendance management.</span>
        </div>
      </Card>
    );
  }

  return (
    <div className="animate-fade-in">
      <div style={styles.header}>
        <h1 style={styles.title}>Attendance Management</h1>
      </div>

      {error && (
        <div style={styles.alert}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      <Card>
        <div style={{ display: 'flex', gap: 'var(--spacing-md)', marginBottom: 'var(--spacing-lg)', flexWrap: 'wrap' }}>
          <div style={{ flex: '1', minWidth: '250px', position: 'relative' }}>
            <div style={{ position: 'absolute', top: '10px', left: '12px', color: 'var(--color-text-muted)' }}>
              <Search size={18} />
            </div>
            <input 
              style={{...styles.input, paddingLeft: '38px'}} 
              placeholder="Search by employee name or code..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '200px' }}>
             <CalendarIcon size={18} color="var(--color-text-muted)" />
             <input
               type="date"
               style={styles.input}
               value={dateFilter}
               onChange={(e) => setDateFilter(e.target.value)}
             />
          </div>
          <select
            style={{...styles.input, width: '200px'}}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Statuses</option>
            <option value="present">Present</option>
            <option value="half_day">Half Day</option>
            <option value="absent">Absent</option>
          </select>
        </div>

        {loading ? (
           <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--spacing-xl)' }}>
             <Loader2 size={32} color="var(--color-primary)" className="animate-spin" />
           </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <Table
              columns={columns}
              data={filteredHistory}
              keyExtractor={(r) => r.id.toString()}
            />
          </div>
        )}
      </Card>
    </div>
  );
};
