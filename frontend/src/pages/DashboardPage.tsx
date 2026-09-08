import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Card } from '../components/Card';
import { EmptyState } from '../components/EmptyState';
import { StatusBadge } from '../components/StatusBadge';
import { AlertBanner } from '../components/AlertBanner';
import {
  Users,
  Calendar,
  Clock,
  Activity,
  LogIn,
  LogOut,
  Coffee,
  Loader2,
  ChevronRight,
  Plus,
  ShieldAlert,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { attendanceService, type AttendanceRecord } from '../services/attendance';
import { leaveService, type LeaveBalance, type LeaveRequest } from '../services/leaves';
import { employeeManagementService } from '../services/employeeManagement';
import { type EmployeeProfile } from '../services/employee';
import { auditService, type AuditLog } from '../services/audit';

export const DashboardPage: React.FC = () => {
  const { user, hasPermission } = useAuth();
  const navigate = useNavigate();

  const [attendanceToday, setAttendanceToday] = useState<AttendanceRecord | null>(null);
  const [leaveBalances, setLeaveBalances] = useState<LeaveBalance[]>([]);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [personalLoading, setPersonalLoading] = useState(true);

  const [employees, setEmployees] = useState<EmployeeProfile[]>([]);
  const [allLeaves, setAllLeaves] = useState<LeaveRequest[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [adminLoading, setAdminLoading] = useState(true);

  useEffect(() => {
    const loadPersonalData = async () => {
      try {
        const [attHistory, lb] = await Promise.all([
          attendanceService.getHistory().catch(() => []),
          leaveService.getBalances().catch(() => []),
        ]);
        const todayStr = new Date().toLocaleDateString('en-CA');
        setAttendanceToday(attHistory.find((h) => h.date === todayStr) || null);
        setLeaveBalances(lb);
      } catch (err) {
        console.error('Error loading personal data', err);
      } finally {
        setPersonalLoading(false);
      }
    };
    loadPersonalData();
  }, []);

  useEffect(() => {
    const loadAdminData = async () => {
      setAdminLoading(true);
      try {
        const promises: Promise<any>[] = [];
        if (hasPermission('employee.view')) promises.push(employeeManagementService.listEmployees().then(setEmployees).catch(() => null));
        if (hasPermission('leave.view')) promises.push(leaveService.getRequests().then(setAllLeaves).catch(() => null));
        if (hasPermission('audit.view')) promises.push(auditService.getLogs().then(setAuditLogs).catch(() => null));
        await Promise.all(promises);
      } catch (err) {
        console.error('Error loading admin data', err);
      } finally {
        setAdminLoading(false);
      }
    };
    loadAdminData();
  }, [hasPermission]);

  const getGeolocation = (): Promise<{ latitude: number; longitude: number; accuracy: number }> => {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("Geolocation is not supported by your browser."));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (position) => {
          resolve({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
          });
        },
        (error) => {
          reject(error);
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      );
    });
  };

  const handleCheckIn = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      let loc;
      try {
        loc = await getGeolocation();
      } catch (e) {
        console.warn('Geolocation failed', e);
      }
      const rec = await attendanceService.checkIn(loc);
      setAttendanceToday(rec);
    } catch (e: any) {
      if (e?.errorData?.detail === 'ATTENDANCE_OUTSIDE_GEOFENCE') {
        setActionError('You are outside the authorized office geofence or not on the office network.');
      } else if (e?.errorData?.detail === 'POOR_GPS_ACCURACY') {
        setActionError('Poor GPS accuracy. Please step outside or connect to Wi-Fi to improve location accuracy.');
      } else {
        setActionError(e?.errorData?.detail || e?.response?.data?.detail || 'Check-in failed. Please ensure location services are enabled.');
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleCheckOut = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      let loc;
      try {
        loc = await getGeolocation();
      } catch (e) {
        console.warn('Geolocation failed', e);
      }
      const rec = await attendanceService.checkOut(loc);
      setAttendanceToday(rec);
    } catch (e: any) {
      setActionError(e?.errorData?.detail || 'Check-out failed. Please try again.');
    } finally {
      setActionLoading(false);
    }
  };

  const pendingLeaves = allLeaves.filter((l) => l.status === 'pending');
  const activeEmployees = employees.filter((e) => e.status === 'active');
  const recentHires = [...employees].sort((a, b) => b.id - a.id).slice(0, 5);
  const recentActivity = auditLogs.slice(0, 5);

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  };

  const dateStr = new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });

  if (!user) {
    return (
      <div className="loading-center">
        <Loader2 size={28} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
      </div>
    );
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      {/* Executive Welcome Hero Banner */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(112, 38, 227, 0.08) 0%, rgba(71, 191, 255, 0.06) 100%)',
          border: '1px solid rgba(112, 38, 227, 0.16)',
          borderRadius: 'var(--radius-xl)',
          padding: '22px 26px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
          boxShadow: 'var(--shadow-xs)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px', flexWrap: 'wrap' }}>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, color: 'var(--color-text-main)', letterSpacing: '-0.02em' }}>
              {greeting()}, {user.firstName || user.email.split('@')[0]}
            </h1>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '2px 8px',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.7rem',
                fontWeight: 600,
                backgroundColor: attendanceToday && !attendanceToday.check_out ? 'rgba(5, 150, 105, 0.12)' : 'rgba(100, 116, 139, 0.1)',
                color: attendanceToday && !attendanceToday.check_out ? 'var(--color-status-success)' : 'var(--color-text-muted)',
                border: attendanceToday && !attendanceToday.check_out ? '1px solid rgba(5, 150, 105, 0.25)' : '1px solid rgba(100, 116, 139, 0.2)',
              }}
            >
              <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'currentColor' }} />
              {attendanceToday ? (attendanceToday.check_out ? 'Shift Completed' : (attendanceToday.is_on_break ? 'On Break' : 'Clocked In')) : 'Not Clocked In'}
            </span>
          </div>
          <p style={{ color: 'var(--color-text-muted)', margin: 0, fontSize: 'var(--font-size-sm)' }}>
            {dateStr} • BeyondSure HRMS Workspace
          </p>
        </div>

        {/* Quick actions in banner */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {!attendanceToday ? (
            <button className="btn btn-primary" onClick={handleCheckIn} disabled={actionLoading} type="button">
              {actionLoading ? <Loader2 size={15} className="animate-spin" /> : <LogIn size={15} />}
              Web Check In
            </button>
          ) : !attendanceToday.check_out ? (
            <button className="btn btn-primary" onClick={handleCheckOut} disabled={actionLoading} type="button">
              {actionLoading ? <Loader2 size={15} className="animate-spin" /> : <LogOut size={15} />}
              Check Out
            </button>
          ) : null}

          <button className="btn btn-secondary" onClick={() => navigate('/leaves')} type="button">
            <Calendar size={15} /> Apply Leave
          </button>
          <button className="btn btn-secondary" onClick={() => navigate('/payslips')} type="button">
            My Payslips
          </button>
        </div>
      </div>

      {/* 4 Distinctive Brand KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))', gap: 'var(--spacing-md)' }}>
        {/* Card 1: Total Employees */}
        <div
          className="stat-card"
          style={{ borderTop: '3px solid var(--color-primary)', cursor: hasPermission('employee.view') ? 'pointer' : 'default' }}
          onClick={() => hasPermission('employee.view') && navigate('/admin/employees')}
        >
          <div
            className="stat-card-icon"
            style={{ backgroundColor: 'rgba(112, 38, 227, 0.12)', color: 'var(--color-primary)' }}
          >
            <Users size={22} />
          </div>
          <div>
            <div className="stat-card-value">
              {adminLoading ? '—' : (hasPermission('employee.view') ? employees.length : '1')}
            </div>
            <div className="stat-card-label">
              {hasPermission('employee.view') ? `${activeEmployees.length} active workforce` : 'Your Organization'}
            </div>
          </div>
        </div>

        {/* Card 2: Attendance Status */}
        <div
          className="stat-card"
          style={{ borderTop: '3px solid var(--color-accent)', cursor: 'pointer' }}
          onClick={() => navigate('/attendance')}
        >
          <div
            className="stat-card-icon"
            style={{ backgroundColor: 'rgba(71, 191, 255, 0.14)', color: '#0284c7' }}
          >
            <Clock size={22} />
          </div>
          <div>
            <div className="stat-card-value" style={{ fontSize: '1.4rem' }}>
              {attendanceToday?.check_in
                ? new Date(attendanceToday.check_in).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                : 'Not Logged'}
            </div>
            <div className="stat-card-label">
              {attendanceToday?.check_out ? 'Shift closed' : (attendanceToday ? 'Clocked In today' : 'No punch recorded')}
            </div>
          </div>
        </div>

        {/* Card 3: Pending Leaves */}
        <div
          className="stat-card"
          style={{ borderTop: '3px solid #d97706', cursor: 'pointer' }}
          onClick={() => navigate(hasPermission('leave.view') ? '/admin/leaves' : '/leaves')}
        >
          <div
            className="stat-card-icon"
            style={{ backgroundColor: 'rgba(217, 119, 6, 0.12)', color: '#d97706' }}
          >
            <Calendar size={22} />
          </div>
          <div>
            <div className="stat-card-value">
              {hasPermission('leave.view') ? (adminLoading ? '—' : pendingLeaves.length) : (personalLoading ? '—' : leaveBalances.length)}
            </div>
            <div className="stat-card-label">
              {hasPermission('leave.view') ? 'Pending leave approvals' : 'Active leave types'}
            </div>
          </div>
        </div>

        {/* Card 4: Available Leave Balance */}
        <div
          className="stat-card"
          style={{ borderTop: '3px solid #059669', cursor: 'pointer' }}
          onClick={() => navigate('/leaves')}
        >
          <div
            className="stat-card-icon"
            style={{ backgroundColor: 'rgba(5, 150, 105, 0.12)', color: '#059669' }}
          >
            <Coffee size={22} />
          </div>
          <div>
            <div className="stat-card-value">
              {personalLoading ? '—' : `${leaveBalances.reduce((acc, b) => acc + (b.remaining || 0), 0)}d`}
            </div>
            <div className="stat-card-label">
              Remaining leave balance
            </div>
          </div>
        </div>
      </div>

      {/* Main grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--spacing-lg)' }}>
        {/* Left column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
          {/* Today's Attendance Terminal */}
          <Card title="Today's Attendance Terminal">
            {personalLoading ? (
              <div className="loading-center" style={{ padding: '24px' }}>
                <Loader2 size={20} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
                {actionError && (
                  <AlertBanner type="error" message={actionError} />
                )}

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 14px', backgroundColor: 'var(--color-bg-page)', borderRadius: 'var(--radius-md)' }}>
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
                      }}
                    >
                      <Clock size={22} color="var(--color-primary)" />
                    </div>
                    <div>
                      <p style={{ margin: 0, fontWeight: 700, fontSize: 'var(--font-size-base)', color: 'var(--color-text-main)' }}>
                        {attendanceToday ? (attendanceToday.check_out ? 'Shift Ended' : (attendanceToday.is_on_break ? 'On Break' : 'Working Now')) : 'Not Clocked In'}
                      </p>
                      <p style={{ margin: 0, fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                        Punch In: <strong style={{ color: 'var(--color-text-sub)' }}>{attendanceToday?.check_in ? new Date(attendanceToday.check_in).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--:--'}</strong>
                        {' • '}
                        Punch Out: <strong style={{ color: 'var(--color-text-sub)' }}>{attendanceToday?.check_out ? new Date(attendanceToday.check_out).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--:--'}</strong>
                      </p>
                    </div>
                  </div>
                  <StatusBadge
                    status={
                      !attendanceToday ? 'absent'
                      : attendanceToday.check_out ? 'present'
                      : attendanceToday.is_on_break ? 'warning'
                      : 'info'
                    }
                    label={
                      !attendanceToday ? 'Absent'
                      : attendanceToday.check_out ? 'Completed'
                      : attendanceToday.is_on_break ? 'On Break'
                      : 'Working'
                    }
                  />
                </div>

                {!attendanceToday?.check_out && (
                  <div style={{ display: 'flex', gap: 'var(--spacing-sm)' }}>
                    {!attendanceToday ? (
                      <button className="btn btn-primary" onClick={handleCheckIn} disabled={actionLoading} style={{ flex: 1, padding: '10px 16px' }}>
                        {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <LogIn size={16} />}
                        Record Web Check In
                      </button>
                    ) : (
                      <button className="btn btn-primary" onClick={handleCheckOut} disabled={actionLoading} style={{ flex: 1, padding: '10px 16px' }}>
                        {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <LogOut size={16} />}
                        Record Check Out
                      </button>
                    )}
                  </div>
                )}

                <button
                  className="btn btn-ghost"
                  onClick={() => navigate('/attendance')}
                  style={{ width: '100%', fontSize: 'var(--font-size-xs)', paddingTop: 6, paddingBottom: 6 }}
                >
                  View Full Attendance History <ChevronRight size={13} />
                </button>
              </div>
            )}
          </Card>

          {/* Leave Balances with Visual Progress Meters */}
          <Card title="My Leave Balances">
            {personalLoading ? (
              <div className="loading-center" style={{ padding: '24px' }}>
                <Loader2 size={20} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
              </div>
            ) : leaveBalances.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {leaveBalances.map((lb) => {
                  const total = lb.allocated || (lb.used + lb.remaining) || 1;
                  const pct = Math.min(100, Math.round(((total - lb.remaining) / total) * 100));
                  return (
                    <div key={lb.id} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 600, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-main)' }}>
                          {lb.leave_type_name}
                        </span>
                        <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                          <strong style={{ color: 'var(--color-primary)', fontWeight: 700 }}>{lb.remaining}</strong> / {total} days remaining
                        </span>
                      </div>
                      {/* Visual progress bar */}
                      <div
                        style={{
                          height: '7px',
                          backgroundColor: 'var(--color-border)',
                          borderRadius: 'var(--radius-full)',
                          overflow: 'hidden',
                        }}
                      >
                        <div
                          style={{
                            height: '100%',
                            width: `${pct}%`,
                            background: pct > 80 ? 'var(--color-status-danger)' : 'linear-gradient(90deg, var(--color-primary) 0%, #0ea5e9 100%)',
                            borderRadius: 'var(--radius-full)',
                            transition: 'width 0.4s ease',
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
                <button
                  className="btn btn-secondary"
                  onClick={() => navigate('/leaves')}
                  style={{ width: '100%', marginTop: '6px', fontSize: 'var(--font-size-sm)' }}
                >
                  <Plus size={14} /> Request Leave
                </button>
              </div>
            ) : (
              <EmptyState title="No Balances" description="No active leave balances." icon={Coffee} />
            )}
          </Card>
        </div>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
          {hasPermission('employee.view') && (
            <Card title="Recent Team Members">
              {adminLoading ? (
                <div className="loading-center" style={{ padding: '24px' }}>
                  <Loader2 size={20} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
                </div>
              ) : recentHires.length > 0 ? (
                <div>
                  {recentHires.map((emp) => (
                    <div
                      key={emp.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        padding: '10px 0',
                        borderBottom: '1px solid var(--color-border)',
                        cursor: 'pointer',
                        transition: 'background-color 0.12s ease',
                      }}
                      onClick={() => navigate(`/admin/employees/${emp.id}`)}
                    >
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          borderRadius: '50%',
                          background: 'linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%)',
                          color: 'var(--color-primary)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontWeight: 700,
                          fontSize: 'var(--font-size-xs)',
                          flexShrink: 0,
                        }}
                      >
                        {emp.first_name?.[0]}{emp.last_name?.[0]}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p style={{ margin: 0, fontWeight: 600, fontSize: 'var(--font-size-sm)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {emp.first_name} {emp.last_name}
                        </p>
                        <p style={{ margin: 0, fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {emp.designation_name || 'No Designation'} · {emp.department_name || 'No Dept'}
                        </p>
                      </div>
                      <StatusBadge status={(emp.status as any) || 'active'} />
                    </div>
                  ))}
                  <button
                    className="btn btn-ghost"
                    onClick={() => navigate('/admin/employees')}
                    style={{ width: '100%', marginTop: '8px', fontSize: 'var(--font-size-xs)' }}
                  >
                    View All Employees Directory <ChevronRight size={13} />
                  </button>
                </div>
              ) : (
                <EmptyState title="No Employees" description="No employees found." icon={Users} />
              )}
            </Card>
          )}

          {hasPermission('audit.view') && (
            <Card title="System Activity Stream">
              {adminLoading ? (
                <div className="loading-center" style={{ padding: '24px' }}>
                  <Loader2 size={20} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
                </div>
              ) : recentActivity.length > 0 ? (
                <div>
                  {recentActivity.map((log) => (
                    <div
                      key={log.id}
                      style={{
                        display: 'flex',
                        gap: '12px',
                        padding: '10px 0',
                        borderBottom: '1px solid var(--color-border)',
                      }}
                    >
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: 'var(--radius-md)',
                          backgroundColor: 'rgba(112, 38, 227, 0.1)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                          marginTop: 2,
                        }}
                      >
                        <ShieldAlert size={14} color="var(--color-primary)" />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', fontWeight: 600, textTransform: 'capitalize', color: 'var(--color-text-main)' }}>
                          {log.action.replace(/_/g, ' ')}
                        </p>
                        <p style={{ margin: 0, fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                          {log.actor_email} • {new Date(log.timestamp).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  ))}
                  <button
                    className="btn btn-ghost"
                    onClick={() => navigate('/admin/audit-logs')}
                    style={{ width: '100%', marginTop: '8px', fontSize: 'var(--font-size-xs)' }}
                  >
                    View Complete Audit Logs <ChevronRight size={13} />
                  </button>
                </div>
              ) : (
                <EmptyState title="No Activity" description="No recent system activity." icon={Activity} />
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};
