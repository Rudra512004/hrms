import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { usePagination } from '../../hooks/usePagination';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { PageHeader } from '../../components/PageHeader';
import { AlertBanner } from '../../components/AlertBanner';
import { Loader2, Search, Calendar as CalendarIcon, CalendarDays, Users, RefreshCw, Download, Plus, Edit2, CheckCircle2, Save } from 'lucide-react';
import { Modal } from '../../components/Modal';
import { attendanceService, type AttendanceRecord, type ManagementAttendanceParams } from '../../services/attendance';
import { organizationService, type Team } from '../../services/organization';
import { employeeManagementService } from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import { exportToCsv, type CsvColumn } from '../../utils/exportCsv';
import { useAuth } from '../../contexts/AuthContext';
import { useBranchContext } from '../../contexts/BranchContext';

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
  const { branchId, selectedBranch } = useBranchContext();

  const [history, setHistory] = useState<AttendanceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter states
  const [searchQuery, setSearchQuery] = useState('');
  const [dateFilter, setDateFilter] = useState(new Date().toISOString().split('T')[0]);
  const [teamFilter, setTeamFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Teams list for dropdown
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamsLoading, setTeamsLoading] = useState(false);

  // Pagination state with URL synchronization
  const {
    page,
    pageSize,
    totalCount,
    setTotalCount,
    handlePageChange,
    resetPage,
  } = usePagination({ defaultPageSize: 20 });

  // Reset page to 1 if branch changes
  const prevBranchIdRef = useRef(branchId);
  useEffect(() => {
    if (prevBranchIdRef.current !== branchId) {
      prevBranchIdRef.current = branchId;
      resetPage();
    }
  }, [branchId, resetPage]);

  // Request cancellation ref
  const abortControllerRef = useRef<AbortController | null>(null);

  // Manual Adjustment state
  const [showAdjustModal, setShowAdjustModal] = useState(false);
  const [adjustSubmitting, setAdjustSubmitting] = useState(false);
  const [adjustError, setAdjustError] = useState<string | null>(null);
  const [adjustSuccess, setAdjustSuccess] = useState<string | null>(null);
  const [employeeList, setEmployeeList] = useState<EmployeeProfile[]>([]);
  const [employeesLoading, setEmployeesLoading] = useState(false);

  const [adjustForm, setAdjustForm] = useState({
    employee_id: '',
    date: new Date().toISOString().split('T')[0],
    check_in: '09:00',
    check_out: '18:00',
    status: 'present' as 'present' | 'absent' | 'half_day',
    reason: '',
    is_late: false,
  });

  const openAdjustModal = async (record?: AttendanceRecord) => {
    setAdjustError(null);
    setAdjustSuccess(null);
    if (record) {
      setAdjustForm({
        employee_id: String(record.employee),
        date: record.date,
        check_in: record.check_in ? new Date(record.check_in).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : '09:00',
        check_out: record.check_out ? new Date(record.check_out).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : '18:00',
        status: (record.status as any) || 'present',
        reason: '',
        is_late: Boolean(record.is_late),
      });
    } else {
      setAdjustForm({
        employee_id: '',
        date: dateFilter || new Date().toISOString().split('T')[0],
        check_in: '09:00',
        check_out: '18:00',
        status: 'present',
        reason: '',
        is_late: false,
      });
    }
    setShowAdjustModal(true);

    if (employeeList.length === 0) {
      setEmployeesLoading(true);
      try {
        const res = await employeeManagementService.listEmployees({ paginate: false });
        const list = Array.isArray(res) ? res : (res as any)?.results || [];
        setEmployeeList(list);
      } catch {
        // fallback gracefully
      } finally {
        setEmployeesLoading(false);
      }
    }
  };

  const handleAdjustSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAdjustError(null);
    setAdjustSuccess(null);

    if (!adjustForm.employee_id) {
      setAdjustError('Please select an employee.');
      return;
    }
    if (!adjustForm.reason.trim()) {
      setAdjustError('Please provide an adjustment reason / notes.');
      return;
    }

    try {
      setAdjustSubmitting(true);
      await attendanceService.adjustAttendance({
        employee_id: parseInt(adjustForm.employee_id, 10),
        date: adjustForm.date,
        check_in: adjustForm.status !== 'absent' ? adjustForm.check_in : null,
        check_out: adjustForm.status !== 'absent' ? adjustForm.check_out : null,
        status: adjustForm.status,
        reason: adjustForm.reason,
        is_late: adjustForm.is_late,
      });

      setAdjustSuccess('Attendance adjusted successfully.');
      setTimeout(() => {
        setShowAdjustModal(false);
        setAdjustSuccess(null);
        loadAttendance();
      }, 1000);
    } catch (err: any) {
      setAdjustError(err.message || 'Failed to adjust attendance.');
    } finally {
      setAdjustSubmitting(false);
    }
  };


  // Load authorized teams on mount
  useEffect(() => {
    let isMounted = true;
    const loadTeams = async () => {
      try {
        setTeamsLoading(true);
        const data = await organizationService.listTeams();
        if (isMounted) {
          setTeams(Array.isArray(data) ? data : []);
        }
      } catch {
        // Teams filter will simply be empty or fallback gracefully
        if (isMounted) setTeams([]);
      } finally {
        if (isMounted) setTeamsLoading(false);
      }
    };
    loadTeams();
    return () => {
      isMounted = false;
    };
  }, []);

  const loadAttendance = useCallback(async () => {
    if (!hasPermission('attendance.view_all')) {
      setLoading(false);
      return;
    }

    // Cancel any previous pending request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      setLoading(true);
      setError(null);

      const params: ManagementAttendanceParams = {
        paginate: true,
        page,
        page_size: pageSize,
      };

      // Only pass branch_id when a specific branch is selected; omit for All Locations
      if (branchId !== null && branchId !== undefined) {
        params.branch_id = branchId;
      }

      // Team filter
      if (teamFilter && teamFilter !== 'all') {
        params.team_id = parseInt(teamFilter, 10);
      }

      // Date filter
      if (dateFilter && dateFilter.trim()) {
        params.date = dateFilter.trim();
      }

      const data = await attendanceService.getManagementHistory(params, { signal: controller.signal });
      if (abortControllerRef.current === controller) {
        if (Array.isArray(data)) {
          setHistory(data);
          setTotalCount(data.length);
        } else if (data && Array.isArray(data.results)) {
          setHistory(data.results);
          setTotalCount(data.count);
        } else {
          setHistory([]);
          setTotalCount(0);
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        return; // Ignored aborted request
      }
      if (abortControllerRef.current === controller) {
        if (err?.errorData?.detail) {
          setError(err.errorData.detail);
        } else if (err?.status === 403 || err?.response?.status === 403) {
          setError('403 Forbidden: You do not have permission to view this attendance data.');
        } else if (err?.message) {
          setError(err.message);
        } else {
          setError('Failed to load attendance history. Please try again.');
        }
        setHistory([]);
        setTotalCount(0);
      }
    } finally {
      if (abortControllerRef.current === controller) {
        setLoading(false);
      }
    }
  }, [hasPermission, branchId, teamFilter, dateFilter, page, pageSize, setTotalCount]);

  // Refetch whenever branchId, teamFilter, or dateFilter changes
  useEffect(() => {
    // Reset data immediately on branch switch to avoid stale data display
    setHistory([]);
    loadAttendance();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [loadAttendance]);

  // Client-side search and status filtering over returned server records
  const filteredHistory = useMemo(() => {
    return history.filter((r) => {
      const matchStatus = statusFilter === 'all' || r.status === statusFilter;
      const q = searchQuery.toLowerCase().trim();
      const matchSearch =
        q === '' ||
        (r.employee_name && r.employee_name.toLowerCase().includes(q)) ||
        (r.employee_code && r.employee_code.toLowerCase().includes(q));
      return matchStatus && matchSearch;
    });
  }, [history, statusFilter, searchQuery]);

  const handleExportCsv = () => {
    const cols: CsvColumn<AttendanceRecord>[] = [
      { header: 'Employee Name', accessor: (r) => r.employee_name || '' },
      { header: 'Employee Code', accessor: (r) => r.employee_code || '' },
      { header: 'Date', accessor: (r) => r.date },
      { header: 'Check In', accessor: (r) => r.check_in ? formatTimeOnly(r.check_in) : '--:--' },
      { header: 'Check Out', accessor: (r) => r.check_out ? formatTimeOnly(r.check_out) : '--:--' },
      { header: 'Distance (m)', accessor: (r) => r.distance_from_branch != null ? `${r.distance_from_branch}m` : 'N/A' },
      { header: 'Status', accessor: (r) => r.status },
      { header: 'Late', accessor: (r) => r.is_late ? 'Yes' : 'No' },
      {
        header: 'Total Break (HH:MM:SS)',
        accessor: (r) => {
          const ms = r.total_break_duration
            ? parseDjangoDuration(r.total_break_duration)
            : 0;
          return formatDurationMs(ms);
        },
      },
      {
        header: 'Productive Work (HH:MM:SS)',
        accessor: (r) => {
          const ms = r.productive_work_duration
            ? parseDjangoDuration(r.productive_work_duration)
            : 0;
          return formatDurationMs(ms);
        },
      },
    ];

    const filename = `attendance_report_${dateFilter || 'all'}_${new Date().toISOString().split('T')[0]}`;
    exportToCsv(filename, cols, filteredHistory);
  };

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
      key: 'distance',
      title: 'Distance',
      render: (r: AttendanceRecord) => (
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>{r.distance_from_branch != null ? `${r.distance_from_branch}m` : '—'}</span>
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
    {
      key: 'is_late',
      title: 'Late',
      render: (r: AttendanceRecord) =>
        r.is_late ? (
          <span className="badge badge-warning" data-testid={`late-badge-${r.id}`}>
            Late
          </span>
        ) : (
          <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-xs)' }}>—</span>
        ),
    },
    {
      key: 'actions',
      title: 'Action',
      render: (r: AttendanceRecord) => (
        <button
          className="btn btn-secondary btn-sm"
          style={{ padding: '3px 8px', fontSize: 'var(--font-size-xs)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
          onClick={() => openAdjustModal(r)}
          title="Adjust Attendance Record"
          type="button"
        >
          <Edit2 size={12} />
          <span>Adjust</span>
        </button>
      ),
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

  const branchTitle = selectedBranch.type === 'branch' && selectedBranch.branch?.name
    ? `Branch: ${selectedBranch.branch.name}`
    : 'All Locations';

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--spacing-md)' }}>
        <PageHeader
          title="Attendance Management"
          subtitle={`Attendance overview for ${branchTitle}.`}
        />
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleExportCsv}
            disabled={filteredHistory.length === 0}
            type="button"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            title="Export filtered records to CSV"
          >
            <Download size={14} />
            <span>Export CSV</span>
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={loadAttendance}
            disabled={loading}
            type="button"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => openAdjustModal()}
            type="button"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
          >
            <Plus size={14} />
            <span>Manual Entry</span>
          </button>
        </div>
      </div>


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
            alignItems: 'center',
          }}
        >
          {/* Search */}
          <div style={{ flex: '1 1 220px', position: 'relative' }}>
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
              placeholder="Search by name or code…"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                resetPage();
              }}
              aria-label="Search employees"
            />
          </div>

          {/* Date Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: '0 1 190px' }}>
            <CalendarIcon size={15} color="var(--color-text-muted)" style={{ flexShrink: 0 }} />
            <input
              type="date"
              className="input-field"
              value={dateFilter}
              onChange={(e) => {
                setDateFilter(e.target.value);
                resetPage();
              }}
              aria-label="Filter by date"
            />
          </div>

          {/* Team Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: '0 1 180px' }}>
            <Users size={15} color="var(--color-text-muted)" style={{ flexShrink: 0 }} />
            <select
              className="input-field"
              value={teamFilter}
              onChange={(e) => {
                setTeamFilter(e.target.value);
                resetPage();
              }}
              aria-label="Filter by team"
              disabled={teamsLoading}
            >
              <option value="all">All Teams</option>
              {teams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div style={{ flex: '0 1 160px' }}>
            <select
              className="input-field"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                resetPage();
              }}
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
              onClick={() => {
                setDateFilter('');
                resetPage();
              }}
              type="button"
            >
              Clear Date
            </button>
          )}
        </div>

        {loading && history.length === 0 ? (
          <div className="loading-center" style={{ padding: 'var(--spacing-2xl)' }}>
            <Loader2 size={28} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
            <span style={{ marginTop: '8px' }}>Loading attendance records…</span>
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
                ? `No attendance records found for ${dateFilter}.`
                : 'No attendance records match the current filters.'
            }
            pagination
            count={totalCount}
            page={page}
            pageSize={pageSize}
            onPageChange={handlePageChange}
            loading={loading}
          />
        )}
      </Card>

      {/* Manual Attendance Adjustment Modal */}
      {showAdjustModal && (
        <Modal
          title="Manual Attendance Adjustment"
          onClose={() => {
            if (!adjustSubmitting) {
              setShowAdjustModal(false);
              setAdjustError(null);
            }
          }}
          size="md"
        >
          <form onSubmit={handleAdjustSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
            {adjustError && <AlertBanner type="error" message={adjustError} />}
            {adjustSuccess && (
              <div
                style={{
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'rgba(34, 197, 94, 0.15)',
                  color: 'rgb(21, 128, 61)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <CheckCircle2 size={16} />
                <span>{adjustSuccess}</span>
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600 }}>Employee *</label>
              <select
                className="input-field"
                value={adjustForm.employee_id}
                onChange={(e) => setAdjustForm((prev) => ({ ...prev, employee_id: e.target.value }))}
                required
                disabled={employeesLoading || adjustSubmitting}
              >
                <option value="">{employeesLoading ? 'Loading employees...' : 'Select Employee'}</option>
                {employeeList.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.first_name} {emp.last_name} ({emp.employee_code || emp.email})
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-md)' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <label style={{ fontSize: '0.85rem', fontWeight: 600 }}>Date *</label>
                <input
                  type="date"
                  className="input-field"
                  value={adjustForm.date}
                  onChange={(e) => setAdjustForm((prev) => ({ ...prev, date: e.target.value }))}
                  required
                  disabled={adjustSubmitting}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <label style={{ fontSize: '0.85rem', fontWeight: 600 }}>Status *</label>
                <select
                  className="input-field"
                  value={adjustForm.status}
                  onChange={(e) => setAdjustForm((prev) => ({ ...prev, status: e.target.value as any }))}
                  disabled={adjustSubmitting}
                >
                  <option value="present">Present</option>
                  <option value="half_day">Half Day</option>
                  <option value="absent">Absent</option>
                </select>
              </div>
            </div>

            {adjustForm.status !== 'absent' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-md)' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: 600 }}>Check-in Time (HH:MM)</label>
                  <input
                    type="time"
                    className="input-field"
                    value={adjustForm.check_in}
                    onChange={(e) => setAdjustForm((prev) => ({ ...prev, check_in: e.target.value }))}
                    disabled={adjustSubmitting}
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: 600 }}>Check-out Time (HH:MM)</label>
                  <input
                    type="time"
                    className="input-field"
                    value={adjustForm.check_out}
                    onChange={(e) => setAdjustForm((prev) => ({ ...prev, check_out: e.target.value }))}
                    disabled={adjustSubmitting}
                  />
                </div>
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="checkbox"
                id="adjust-late"
                checked={adjustForm.is_late}
                onChange={(e) => setAdjustForm((prev) => ({ ...prev, is_late: e.target.checked }))}
                disabled={adjustSubmitting}
              />
              <label htmlFor="adjust-late" style={{ fontSize: '0.85rem', cursor: 'pointer' }}>
                Mark as Late Check-in
              </label>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600 }}>Adjustment Reason / Notes *</label>
              <textarea
                className="input-field"
                style={{ minHeight: '75px', resize: 'vertical' }}
                value={adjustForm.reason}
                onChange={(e) => setAdjustForm((prev) => ({ ...prev, reason: e.target.value }))}
                placeholder="Reason for manual adjustment (e.g. system downtime, swipe card failure, regularization approval)..."
                required
                disabled={adjustSubmitting}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--spacing-sm)', marginTop: 'var(--spacing-sm)' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowAdjustModal(false)}
                disabled={adjustSubmitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={adjustSubmitting}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              >
                {adjustSubmitting ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                <span>{adjustSubmitting ? 'Saving...' : 'Save Adjustment'}</span>
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
