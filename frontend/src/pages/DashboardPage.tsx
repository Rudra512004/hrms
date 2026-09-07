import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Card } from '../components/Card';
import { StatCard } from '../components/StatCard';
import { EmptyState } from '../components/EmptyState';
import { StatusBadge } from '../components/StatusBadge';
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
  ShieldAlert
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

// Services
import { attendanceService, type AttendanceRecord } from '../services/attendance';
import { leaveService, type LeaveBalance, type LeaveRequest } from '../services/leaves';
import { employeeManagementService } from '../services/employeeManagement';
import { type EmployeeProfile } from '../services/employee';
import { auditService, type AuditLog } from '../services/audit';

export const DashboardPage: React.FC = () => {
  const { user, hasPermission } = useAuth();
  const navigate = useNavigate();

  // Personal States
  const [attendanceToday, setAttendanceToday] = useState<AttendanceRecord | null>(null);
  const [leaveBalances, setLeaveBalances] = useState<LeaveBalance[]>([]);
  const [actionLoading, setActionLoading] = useState(false);
  const [personalLoading, setPersonalLoading] = useState(true);

  // Admin States
  const [employees, setEmployees] = useState<EmployeeProfile[]>([]);
  const [allLeaves, setAllLeaves] = useState<LeaveRequest[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [adminLoading, setAdminLoading] = useState(true);

  useEffect(() => {
    // Load Personal Data (Attendance, Leave Balances)
    const loadPersonalData = async () => {
      try {
        const [attHistory, lb] = await Promise.all([
          attendanceService.getHistory().catch(() => []),
          leaveService.getBalances().catch(() => [])
        ]);
        const todayStr = new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD
        const todayAtt = attHistory.find(h => h.date === todayStr) || null;
        setAttendanceToday(todayAtt);
        setLeaveBalances(lb);
      } catch (err) {
        console.error("Error loading personal data", err);
      } finally {
        setPersonalLoading(false);
      }
    };

    loadPersonalData();
  }, []);

  useEffect(() => {
    // Load Admin Data (conditional based on RBAC)
    const loadAdminData = async () => {
      setAdminLoading(true);
      try {
        const promises: Promise<any>[] = [];
        
        if (hasPermission('employee.view')) promises.push(employeeManagementService.listEmployees().then(setEmployees).catch(() => []));
        if (hasPermission('leave.view')) promises.push(leaveService.getRequests().then(setAllLeaves).catch(() => []));
        if (hasPermission('audit.view')) promises.push(auditService.getLogs().then(setAuditLogs).catch(() => []));
        
        await Promise.all(promises);
      } catch (err) {
        console.error("Error loading admin data", err);
      } finally {
        setAdminLoading(false);
      }
    };

    loadAdminData();
  }, [hasPermission]);

  // Actions
  const handleCheckIn = async () => {
    setActionLoading(true);
    try {
      const rec = await attendanceService.checkIn();
      setAttendanceToday(rec);
    } catch (e: any) { alert(e.errorData?.detail || 'Failed'); }
    finally { setActionLoading(false); }
  };

  const handleCheckOut = async () => {
    setActionLoading(true);
    try {
      const rec = await attendanceService.checkOut();
      setAttendanceToday(rec);
    } catch (e: any) { alert(e.errorData?.detail || 'Failed'); }
    finally { setActionLoading(false); }
  };

  // Derived Admin Metrics
  const pendingLeaves = allLeaves.filter(l => l.status === 'pending');
  const activeEmployees = employees.filter(e => e.status === 'active');
  const recentHires = [...employees].sort((a, b) => b.id - a.id).slice(0, 5);
  const recentActivity = [...auditLogs].slice(0, 5);

  const dateStr = new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });

  if (!user) return <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}><Loader2 className="animate-spin text-muted" size={32} /></div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-xl)' }}>
      
      {/* Page Header */}
      <div>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: '0 0 var(--spacing-xs) 0' }}>
          Good morning, {user.firstName}
        </h1>
        <p style={{ color: 'var(--color-text-muted)', margin: 0, fontSize: '0.95rem' }}>
          {dateStr} &bull; Here's your HR overview
        </p>
      </div>

      {/* Admin Metrics Grid (Only if permitted) */}
      {(hasPermission('employee.view') || hasPermission('leave.view')) && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 'var(--spacing-lg)' }}>
          {hasPermission('employee.view') && (
            <StatCard 
              title="Total Employees" 
              value={adminLoading ? '-' : employees.length} 
              icon={Users} 
              color="var(--color-primary)" 
            />
          )}
          {hasPermission('employee.view') && (
            <StatCard 
              title="Active Employees" 
              value={adminLoading ? '-' : activeEmployees.length} 
              icon={Activity} 
              color="var(--color-status-success)" 
            />
          )}
          {hasPermission('leave.view') && (
            <StatCard 
              title="Pending Leaves" 
              value={adminLoading ? '-' : pendingLeaves.length} 
              icon={Calendar} 
              color="var(--color-status-warning)" 
            />
          )}
        </div>
      )}

      {/* Main Content Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--spacing-lg)' }}>
        
        {/* Left Column: Personal Data */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
          
          <Card title="Today's Attendance">
            {personalLoading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}><Loader2 className="animate-spin text-muted" /></div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ padding: '12px', borderRadius: '50%', backgroundColor: 'var(--color-primary-light)', color: 'var(--color-primary)' }}>
                      <Clock size={24} />
                    </div>
                    <div>
                      <p style={{ margin: 0, fontWeight: 600 }}>{attendanceToday ? 'Clocked In' : 'Not Clocked In'}</p>
                      <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                        {attendanceToday?.check_in ? new Date(attendanceToday.check_in).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '--:--'}
                        {' - '}
                        {attendanceToday?.check_out ? new Date(attendanceToday.check_out).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '--:--'}
                      </p>
                    </div>
                  </div>
                  <StatusBadge 
                    status={!attendanceToday ? 'absent' : attendanceToday.check_out ? 'present' : attendanceToday.is_on_break ? 'warning' : 'info'} 
                    label={!attendanceToday ? 'Absent' : attendanceToday.check_out ? 'Completed' : attendanceToday.is_on_break ? 'On Break' : 'Working'}
                  />
                </div>

                {!attendanceToday?.check_out && (
                  <div style={{ display: 'flex', gap: 'var(--spacing-sm)', marginTop: 'var(--spacing-sm)' }}>
                    {!attendanceToday ? (
                      <button className="btn btn-primary" onClick={handleCheckIn} disabled={actionLoading} style={{ flex: 1 }}>
                        {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <LogIn size={16} />} Web Clock In
                      </button>
                    ) : (
                      <>
                        <button className="btn btn-primary" onClick={handleCheckOut} disabled={actionLoading} style={{ flex: 1 }}>
                          {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <LogOut size={16} />} Clock Out
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            )}
          </Card>

          <Card title="My Leave Balances">
            {personalLoading ? (
               <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}><Loader2 className="animate-spin text-muted" /></div>
            ) : leaveBalances.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-sm)' }}>
                {leaveBalances.map(lb => (
                  <div key={lb.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--color-border)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--color-primary)' }} />
                      <span style={{ fontWeight: 500, fontSize: '0.9rem' }}>{lb.leave_type_name}</span>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span style={{ fontWeight: 600, color: 'var(--color-text-main)' }}>{lb.remaining} days</span>
                      <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Used: {lb.used}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No Balances" description="You don't have any active leave balances." icon={Coffee} />
            )}
            <button className="btn btn-secondary w-full" onClick={() => navigate('/leaves')} style={{ marginTop: 'var(--spacing-md)' }}>
              <Plus size={16} /> Request Leave
            </button>
          </Card>

        </div>

        {/* Right Column: Admin Data */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
          
          {hasPermission('employee.view') && (
            <Card title="Recent Hires">
              {adminLoading ? (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}><Loader2 className="animate-spin text-muted" /></div>
              ) : recentHires.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-sm)' }}>
                  {recentHires.map(emp => (
                    <div key={emp.id} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '8px 0', borderBottom: '1px solid var(--color-border)' }}>
                      <div style={{ width: '36px', height: '36px', borderRadius: '50%', backgroundColor: 'var(--color-bg-body)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-muted)', fontWeight: 600 }}>
                        {emp.first_name[0]}{emp.last_name[0]}
                      </div>
                      <div style={{ flex: 1 }}>
                        <p style={{ margin: 0, fontWeight: 500, fontSize: '0.9rem' }}>{emp.first_name} {emp.last_name}</p>
                        <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>{emp.designation_name || 'No Designation'} &bull; {emp.department_name || 'No Dept'}</p>
                      </div>
                    </div>
                  ))}
                  <button className="btn btn-ghost" onClick={() => navigate('/admin/employees')} style={{ marginTop: '8px', width: '100%' }}>
                    View All <ChevronRight size={16} />
                  </button>
                </div>
              ) : (
                <EmptyState title="No Employees" description="No employees found in the organization." icon={Users} />
              )}
            </Card>
          )}

          {hasPermission('audit.view') && (
            <Card title="Recent Activity">
              {adminLoading ? (
                 <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}><Loader2 className="animate-spin text-muted" /></div>
              ) : recentActivity.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
                  {recentActivity.map(log => (
                    <div key={log.id} style={{ display: 'flex', gap: '12px' }}>
                      <div style={{ marginTop: '4px', color: 'var(--color-primary)' }}>
                        <ShieldAlert size={16} />
                      </div>
                      <div>
                        <p style={{ margin: 0, fontSize: '0.9rem', fontWeight: 500 }}>{log.action.replace(/_/g, ' ')}</p>
                        <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                          by {log.actor_email} &bull; {new Date(log.timestamp).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  ))}
                  <button className="btn btn-ghost" onClick={() => navigate('/admin/audit-logs')} style={{ marginTop: '8px', width: '100%' }}>
                    View Audit Logs <ChevronRight size={16} />
                  </button>
                </div>
              ) : (
                <EmptyState title="No Activity" description="No recent system activity recorded." icon={Activity} />
              )}
            </Card>
          )}
          
        </div>
      </div>
    </div>
  );
};
