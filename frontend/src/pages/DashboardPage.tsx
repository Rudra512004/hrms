import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../components/Card';
import { StatusBadge } from '../components/StatusBadge';
import {
  User as UserIcon, AlertCircle, Loader2,
  Clock, Calendar, Shield, Settings, Users, LogIn, LogOut, Coffee
} from 'lucide-react';
import { authService, type User as AuthUser } from '../services/auth';
import { attendanceService, type AttendanceRecord } from '../services/attendance';
import { leaveService, type LeaveBalance } from '../services/leaves';

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [attendanceToday, setAttendanceToday] = useState<AttendanceRecord | null>(null);
  const [leaveBalances, setLeaveBalances] = useState<LeaveBalance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const u = await authService.getCurrentUser();
        if (!u) throw new Error("Could not load user data.");
        setUser(u);

        // Fetch Attendance
        try {
          const history = await attendanceService.getHistory();
          const today = new Date().toISOString().split('T')[0];
          const todayRecord = history.find(r => r.date === today);
          setAttendanceToday(todayRecord || null);
        } catch (e) {
          console.error("Attendance fetch failed", e);
        }

        // Fetch Leaves
        try {
          const balances = await leaveService.getBalances();
          setLeaveBalances(balances);
        } catch (e) {
          console.error("Leaves fetch failed", e);
        }

      } catch (err: any) {
        setError(err.message || "An unexpected error occurred.");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleCheckIn = async () => {
    setActionLoading(true);
    try {
      const rec = await attendanceService.checkIn();
      setAttendanceToday(rec);
    } catch (e: any) {
      alert(e.errorData?.non_field_errors?.[0] || 'Check-in failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCheckOut = async () => {
    setActionLoading(true);
    try {
      const rec = await attendanceService.checkOut();
      setAttendanceToday(rec);
    } catch (e: any) {
      alert(e.errorData?.non_field_errors?.[0] || 'Check-out failed');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px', color: 'var(--color-text-muted)' }}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite', marginBottom: 'var(--spacing-md)' }} />
        <p>Loading your dashboard...</p>
      </div>
    );
  }

  if (error || !user) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
        <AlertCircle size={48} color="var(--color-status-danger)" style={{ marginBottom: 'var(--spacing-md)' }} />
        <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: 'var(--spacing-sm)' }}>Unable to load dashboard</h3>
        <p style={{ color: 'var(--color-text-muted)' }}>{error}</p>
      </div>
    );
  }

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const dateStr = new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  return (
    <div className="container animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-xl)', padding: 'var(--spacing-md) 0' }}>

      {/* Header */}
      <div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: '0 0 var(--spacing-xs) 0' }}>{greeting}, {user.firstName}!</h1>
        <p style={{ color: 'var(--color-text-muted)', margin: 0 }}>{dateStr} • Here is your HRMS overview.</p>
      </div>

      <div className="grid-cols-3" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 'var(--spacing-lg)' }}>

        {/* Attendance Card */}
        <Card title="Today's Attendance">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)', alignItems: 'center', textAlign: 'center', padding: 'var(--spacing-md) 0' }}>
            <Clock size={48} color="var(--color-primary)" style={{ opacity: 0.8 }} />
            {attendanceToday ? (
              <>
                <p><strong>Status:</strong> <StatusBadge status={attendanceToday.status as any} /></p>
                {attendanceToday.check_in && <p><strong>In:</strong> {new Date(attendanceToday.check_in).toLocaleTimeString()}</p>}
                {attendanceToday.check_out && <p><strong>Out:</strong> {new Date(attendanceToday.check_out).toLocaleTimeString()}</p>}

                {!attendanceToday.check_out && (
                  <button className="btn btn-primary" onClick={handleCheckOut} disabled={actionLoading} style={{ width: '100%', marginTop: 'var(--spacing-sm)' }}>
                    {actionLoading ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <LogOut size={16} />} Check Out
                  </button>
                )}
              </>
            ) : (
              <>
                <p style={{ color: 'var(--color-text-muted)' }}>You have not checked in today.</p>
                <button className="btn btn-primary" onClick={handleCheckIn} disabled={actionLoading} style={{ width: '100%', marginTop: 'var(--spacing-sm)' }}>
                  {actionLoading ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <LogIn size={16} />} Check In
                </button>
              </>
            )}
          </div>
        </Card>

        {/* Leave Balances */}
        <Card title="Leave Balances">
          {leaveBalances.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
              {leaveBalances.map(lb => (
                <div key={lb.id} style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--spacing-sm) 0', borderBottom: '1px solid var(--color-border)' }}>
                  <span style={{ fontWeight: 500 }}>{lb.leave_type_name}</span>
                  <div style={{ display: 'flex', gap: 'var(--spacing-md)' }}>
                    <span style={{ color: 'var(--color-text-muted)', fontSize: '0.9em' }}>Used: {lb.used}</span>
                    <span style={{ color: 'var(--color-status-success)', fontWeight: 600 }}>{lb.remaining} left</span>
                  </div>
                </div>
              ))}
              <button className="btn btn-secondary" onClick={() => navigate('/leaves')} style={{ marginTop: 'var(--spacing-sm)' }}>
                Apply Leave
              </button>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: 'var(--spacing-xl) 0', color: 'var(--color-text-muted)' }}>
              <Coffee size={32} style={{ margin: '0 auto var(--spacing-sm) auto', opacity: 0.5 }} />
              <p>No leave balances available.</p>
            </div>
          )}
        </Card>

        {/* Quick Actions */}
        <Card title="Quick Actions">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 'var(--spacing-sm)' }}>
            <button className="btn btn-secondary" onClick={() => navigate('/profile')} style={{ justifyContent: 'flex-start' }}><UserIcon size={18}/> Profile</button>
            <button className="btn btn-secondary" onClick={() => navigate('/leaves')} style={{ justifyContent: 'flex-start' }}><Calendar size={18}/> My Leaves</button>

            {user.isStaff && (
              <>
                <div style={{ height: '1px', backgroundColor: 'var(--color-border)', margin: 'var(--spacing-sm) 0' }} />
                <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85em', textTransform: 'uppercase', fontWeight: 600, margin: '0 0 var(--spacing-xs) 0' }}>HR / Admin</p>
                <button className="btn btn-ghost" onClick={() => navigate('/admin/employees')} style={{ justifyContent: 'flex-start' }}><Users size={18}/> Manage Employees</button>
                <button className="btn btn-ghost" onClick={() => navigate('/admin/leaves')} style={{ justifyContent: 'flex-start' }}><Calendar size={18}/> Manage Leaves</button>
              </>
            )}

            {user.isSuperuser && (
              <>
                <div style={{ height: '1px', backgroundColor: 'var(--color-border)', margin: 'var(--spacing-sm) 0' }} />
                <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85em', textTransform: 'uppercase', fontWeight: 600, margin: '0 0 var(--spacing-xs) 0' }}>Superadmin</p>
                <button className="btn btn-ghost" onClick={() => navigate('/admin/leave-types')} style={{ justifyContent: 'flex-start' }}><Settings size={18}/> Leave Types</button>
                <button className="btn btn-ghost" onClick={() => navigate('/admin/audit-logs')} style={{ justifyContent: 'flex-start' }}><Shield size={18}/> Audit Logs</button>
              </>
            )}
          </div>
        </Card>

      </div>
    </div>
  );
};

export { DashboardPage };
