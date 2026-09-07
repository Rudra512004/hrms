import React, { useState, useEffect, useMemo } from 'react';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { PageHeader } from '../../components/PageHeader';
import { AlertBanner } from '../../components/AlertBanner';
import { Loader2, Search, Calendar as CalendarIcon, CalendarDays } from 'lucide-react';
import { attendanceService, type AttendanceRecord } from '../../services/attendance';
import { useAuth } from '../../contexts/AuthContext';

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
  const timePart = parts.length === 2 ? parts[1] : parts[0];
  const [h, m, s] = timePart.split(':').map(Number);
  const days = parts.length === 2 ? parseInt(parts[0]) : 0;
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
        setError('You do not have permission to view organization-wide attendance.');
      } else {
        setError('Failed to load attendance history. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const filteredHistory = useMemo(() => {
    return history.filter((r) => {
      const matchDate = dateFilter === '' || r.date === dateFilter;
      const matchStatus = statusFilter === 'all' || r.status === statusFilter;
      const q = searchQuery.toLowerCase();
      const matchSearch =
        q === '' ||
        (r.employee_name && r.employee_name.toLowerCase().includes(q)) ||
        (r.employee_code && r.employee_code.toLowerCase().includes(q));
      return matchDate && matchStatus && matchSearch;
    });
  }, [history, dateFilter, statusFilter, searchQuery]);

  const columns = [
    {
      key: 'employee',
      title: 'Employee',
      render: (r: AttendanceRecord) => (
        <div>
          <div style={{ fontWeight: 600, fontSize: 'var(--font-size-sm)' }}>{r.employee_name || 'Unknown'}</div>
          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            {r.employee_code || '—'}
          </div>
        </div>
      ),
    },
    {
      key: 'date',
      title: 'Date',
      render: (r: AttendanceRecord) => (
        <span style={{ whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>{r.date}</span>
      ),
    },
    {
      key: 'check_in',
      title: 'Check In',
      render: (r: AttendanceRecord) => (
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>{formatTimeOnly(r.check_in)}</span>
      ),
    },
    {
      key: 'check_out',
      title: 'Check Out',
      render: (r: AttendanceRecord) => (
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>{formatTimeOnly(r.check_out)}</span>
      ),
    },
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
        const ms = r.productive_work_duration
          ? parseDjangoDuration(r.productive_work_duration)
          : r.check_in && !r.check_out
          ? Math.max(
              0,
              new Date().getTime() -
                new Date(r.check_in).getTime() -
                (r.breaks || []).reduce((acc, b) => {
                  const end = b.ended_at ? new Date(b.ended_at).getTime() : new Date().getTime();
                  return acc + (end - new Date(b.started_at).getTime());
                }, 0)
            )
          : 0;
        return <span style={{ fontVariantNumeric: 'tabular-nums' }}>{formatDurationMs(ms)}</span>;
      },
    },
    {
      key: 'status',
      title: 'Status',
      render: (r: AttendanceRecord) => <StatusBadge status={r.status as any} />,
    },
  ];

  if (!hasPermission('attendance.view_all')) {
    return (
      <div className="animate-fade-in">
        <PageHeader title="Attendance Management" subtitle="Organization-wide attendance overview." />
        <AlertBanner type="error" message="You do not have permission to access attendance management." />
      </div>
    );
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      <PageHeader
        title="Attendance Management"
        subtitle="Organization-wide attendance overview and history."
      />

      {error && <AlertBanner type="error" message={error} />}

      <Card noPadding>
        {/* Filters bar */}
        <div
          style={{
            display: 'flex',
            gap: 'var(--spacing-md)',
            flexWrap: 'wrap',
            padding: 'var(--spacing-md) var(--spacing-lg)',
            borderBottom: '1px solid var(--color-border)',
          }}
        >
          <div style={{ flex: '1 1 240px', position: 'relative' }}>
            <Search
              size={15}
              style={{
                position: 'absolute',
                top: '50%',
                left: '10px',
                transform: 'translateY(-50%)',
                color: 'var(--color-text-muted)',
                pointerEvents: 'none',
              }}
            />
            <input
              className="input-field"
              style={{ paddingLeft: '34px' }}
              placeholder="Search by name or employee code…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Search employees"
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: '0 1 200px' }}>
            <CalendarIcon size={15} color="var(--color-text-muted)" style={{ flexShrink: 0 }} />
            <input
              type="date"
              className="input-field"
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
              aria-label="Filter by date"
            />
          </div>

          <div style={{ flex: '0 1 180px' }}>
            <select
              className="input-field"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter by status"
            >
              <option value="all">All Statuses</option>
              <option value="present">Present</option>
              <option value="half_day">Half Day</option>
              <option value="absent">Absent</option>
            </select>
          </div>

          {dateFilter && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setDateFilter('')}
              type="button"
            >
              Clear Date
            </button>
          )}
        </div>

        {loading ? (
          <div className="loading-center">
            <Loader2 size={28} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
            <span>Loading attendance…</span>
          </div>
        ) : (
          <Table
            columns={columns}
            data={filteredHistory}
            keyExtractor={(r) => r.id.toString()}
            emptyIcon={CalendarDays}
            emptyTitle="No attendance records"
            emptyDescription={
              dateFilter
                ? `No attendance found for ${dateFilter}.`
                : 'No records match the current filters.'
            }
          />
        )}
      </Card>
    </div>
  );
};
