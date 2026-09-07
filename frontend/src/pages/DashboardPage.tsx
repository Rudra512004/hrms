import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Card } from '../components/Card';
import { StatCard } from '../components/StatCard';
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

  const handleCheckIn = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      const rec = await attendanceService.checkIn();
      setAttendanceToday(rec);
    } catch (e: any) {
      setActionError(e?.errorData?.detail || e?.response?.data?.detail || 'Check-in failed. Are you on an authorized network?');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCheckOut = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      const rec = await attendanceService.checkOut();
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
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-xl)' }}>
      {/* Greeting */}
      <div>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: '0 0 4px 0', color: 'var(--color-text-main)' }}>
          {greeting()}, {user.firstName || user.email.split('@')[0]} 👋
        </h1>
        <p style={{ color: 'var(--color-text-muted)', margin: 0, fontSize: 'var(--font-size-sm)' }}>
          {dateStr}
        </p>
      </div>

      {/* Admin stat cards */}
      {(hasPermission('employee.view') || hasPermission('leave.view')) && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 'var(--spacing-md)' }}>
          {hasPermission('employee.view') && (
            <StatCard
              title="Total Employees"
              value={adminLoading ? '—' : employees.length}
              icon={Users}
              color="var(--color-primary)"
            />
          )}
          {hasPermission('employee.view') && (
            <StatCard
              title="Active Employees"
              value={adminLoading ? '—' : activeEmployees.length}
              icon={Activity}
              color="var(--color-status-success)"
            />
          )}
          {hasPermission('leave.view') && (
            <StatCard
              title="Pending Leaves"
              value={adminLoading ? '—' : pendingLeaves.length}
              icon={Calendar}
              color="var(--color-status-warning)"
            />
          )}
        </div>
      )}

      {/* Main grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--spacing-lg)' }}>
        {/* Left column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
          {/* Attendance card */}
          <Card title="Today's Attendance">
            {personalLoading ? (
              <div className="loading-center" style={{ padding: '24px' }}>
                <Loader2 size={20} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
                {actionError && (
                  <AlertBanner type="error" message={actionError} />
                )}

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
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
                      <p style={{ margin: 0, fontWeight: 600, fontSize: 'var(--font-size-base)' }}>
                        {attendanceToday ? 'Clocked In' : 'Not Clocked In'}
                      </p>
                      <p style={{ margin: 0, fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                        {attendanceToday?.check_in
                          ? new Date(attendanceToday.check_in).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                          : '--:--'}
                        {' – '}
                        {attendanceToday?.check_out
                          ? new Date(attendanceToday.check_out).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                          : '--:--'}
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
                      <button className="btn btn-primary" onClick={handleCheckIn} disabled={actionLoading} style={{ flex: 1 }}>
                        {actionLoading ? <Loader2 size={15} className="animate-spin" /> : <LogIn size={15} />}
                        Web Check In
                      </button>
                    ) : (
                      <button className="btn btn-primary" onClick={handleCheckOut} disabled={actionLoading} style={{ flex: 1 }}>
                        {actionLoading ? <Loader2 size={15} className="animate-spin" /> : <LogOut size={15} />}
                        Check Out
                      </button>
                    )}
                  </div>
                )}

                <button
                  className="btn btn-ghost"
                  onClick={() => navigate('/attendance')}
                  style={{ width: '100%', fontSize: 'var(--font-size-xs)', paddingTop: 6, paddingBottom: 6 }}
                >
                  View Full Attendance <ChevronRight size={13} />
                </button>
              </div>
            )}
          </Card>

          {/* Leave balances */}
          <Card title="My Leave Balances">
            {personalLoading ? (
              <div className="loading-center" style={{ padding: '24px' }}>
                <Loader2 size={20} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
              </div>
            ) : leaveBalances.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                {leaveBalances.map((lb) => (
                  <div
                    key={lb.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '10px 0',
                      borderBottom: '1px solid var(--color-border)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          backgroundColor: 'var(--color-primary)',
                          flexShrink: 0,
                        }}
                      />
                      <span style={{ fontWeight: 500, fontSize: 'var(--font-size-sm)' }}>{lb.leave_type_name}</span>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span style={{ fontWeight: 600, color: 'var(--color-primary)', fontSize: 'var(--font-size-sm)' }}>
                        {lb.remaining} days
                      </span>
                      <span style={{ display: 'block', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                        Used: {lb.used}
                      </span>
                    </div>
                  </div>
                ))}
                <button
                  className="btn btn-secondary"
                  onClick={() => navigate('/leaves')}
                  style={{ width: '100%', marginTop: 'var(--spacing-sm)', fontSize: 'var(--font-size-sm)' }}
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
            <Card title="Recent Hires">
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
                      }}
                      onClick={() => navigate(`/admin/employees/${emp.id}`)}
                    >
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          borderRadius: '50%',
                          backgroundColor: 'var(--color-primary-light)',
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
                        <p style={{ margin: 0, fontWeight: 500, fontSize: 'var(--font-size-sm)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
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
                    View All Employees <ChevronRight size={13} />
                  </button>
                </div>
              ) : (
                <EmptyState title="No Employees" description="No employees found." icon={Users} />
              )}
            </Card>
          )}

          {hasPermission('audit.view') && (
            <Card title="Recent Activity">
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
                          backgroundColor: 'var(--color-primary-light)',
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
                        <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', fontWeight: 500, textTransform: 'capitalize' }}>
                          {log.action.replace(/_/g, ' ')}
                        </p>
                        <p style={{ margin: 0, fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                          {log.actor_email} · {new Date(log.timestamp).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  ))}
                  <button
                    className="btn btn-ghost"
                    onClick={() => navigate('/admin/audit-logs')}
                    style={{ width: '100%', marginTop: '8px', fontSize: 'var(--font-size-xs)' }}
                  >
                    View Audit Logs <ChevronRight size={13} />
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
