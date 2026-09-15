import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users,
  Clock,
  Calendar,
  Coffee,
  Activity,
  LogIn,
  LogOut,
  Loader2,
  RefreshCw,
} from 'lucide-react';

import { useAuth } from '../contexts/AuthContext';
import { AlertBanner } from '../components/AlertBanner';
import { StatCard } from '../components/StatCard';
import { attendanceService } from '../services/attendance';
import { dashboardService, type DashboardOverviewResponse } from '../services/dashboard';

import {
  PersonalAttendanceWidget,
  LeaveBalanceWidget,
  TeamAttendanceWidget,
  OrgWorkforceWidget,
  AttendanceRateWidget,
  QuickActionsWidget,
  UpcomingHolidaysWidget,
  PendingApprovalsWidget,
  DashboardTrendsSection,
} from '../components/dashboard';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [dashboardData, setDashboardData] = useState<DashboardOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetchDashboardData = useCallback(async (isSilent = false) => {
    if (!isSilent) {
      setLoading(true);
      setError(null);
    }
    try {
      const data = await dashboardService.getOverview();
      setDashboardData(data);
    } catch (err: any) {
      console.error('Failed to load dashboard overview:', err);
      if (!isSilent) {
        setError(
          err?.errorData?.detail ||
            err?.message ||
            'Unable to load dashboard data. Please check your connection and try again.'
        );
      }
    } finally {
      if (!isSilent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  const getGeolocation = (): Promise<{ latitude: number; longitude: number; accuracy: number }> => {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error('Geolocation is not supported by your browser.'));
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
        (err) => {
          reject(err);
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
        console.warn('Geolocation capture failed, proceeding without coordinates', e);
      }
      await attendanceService.checkIn(loc);
      await fetchDashboardData(true);
    } catch (e: any) {
      if (e?.errorData?.detail === 'ATTENDANCE_OUTSIDE_GEOFENCE') {
        setActionError('You are outside the authorized office geofence or not on the office network.');
      } else if (e?.errorData?.detail === 'POOR_GPS_ACCURACY') {
        setActionError('Poor GPS accuracy. Please step outside or connect to Wi-Fi to improve location accuracy.');
      } else {
        setActionError(
          e?.errorData?.detail ||
            e?.response?.data?.detail ||
            'Check-in failed. Please ensure location services are enabled.'
        );
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
        console.warn('Geolocation capture failed, proceeding without coordinates', e);
      }
      await attendanceService.checkOut(loc);
      await fetchDashboardData(true);
    } catch (e: any) {
      setActionError(e?.errorData?.detail || 'Check-out failed. Please try again.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStartBreak = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      let loc;
      try {
        loc = await getGeolocation();
      } catch (e) {
        console.warn('Geolocation capture failed', e);
      }
      await attendanceService.startBreak(loc);
      await fetchDashboardData(true);
    } catch (e: any) {
      setActionError(e?.errorData?.detail || 'Failed to start break. Please try again.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleEndBreak = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      let loc;
      try {
        loc = await getGeolocation();
      } catch (e) {
        console.warn('Geolocation capture failed', e);
      }
      await attendanceService.endBreak(loc);
      await fetchDashboardData(true);
    } catch (e: any) {
      setActionError(e?.errorData?.detail || 'Failed to end break. Please try again.');
    } finally {
      setActionLoading(false);
    }
  };

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

  const personal = dashboardData?.personal;
  const team = dashboardData?.team;
  const org = dashboardData?.organization;

  const attendanceToday = personal?.attendance_today;
  const leaveBalances = personal?.leave_balances || [];
  const totalLeaveRemaining = leaveBalances.reduce((acc, b) => acc + (b.remaining || 0), 0);

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
            <h1
              style={{
                fontSize: '1.5rem',
                fontWeight: 700,
                margin: 0,
                color: 'var(--color-text-main)',
                letterSpacing: '-0.02em',
              }}
            >
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
                backgroundColor:
                  attendanceToday && !attendanceToday.check_out
                    ? 'rgba(5, 150, 105, 0.12)'
                    : 'rgba(100, 116, 139, 0.1)',
                color:
                  attendanceToday && !attendanceToday.check_out
                    ? 'var(--color-status-success)'
                    : 'var(--color-text-muted)',
                border:
                  attendanceToday && !attendanceToday.check_out
                    ? '1px solid rgba(5, 150, 105, 0.25)'
                    : '1px solid rgba(100, 116, 139, 0.2)',
              }}
            >
              <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'currentColor' }} />
              {attendanceToday
                ? attendanceToday.check_out
                  ? 'Shift Completed'
                  : attendanceToday.is_on_break
                  ? 'On Break'
                  : 'Clocked In'
                : 'Not Clocked In'}
            </span>
          </div>
          <p style={{ color: 'var(--color-text-muted)', margin: 0, fontSize: 'var(--font-size-sm)' }}>
            {dateStr} • BeyondSure HRMS Workspace
          </p>
        </div>

        {/* Quick actions inside banner */}
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
          <button
            className="btn btn-ghost"
            onClick={() => fetchDashboardData()}
            title="Refresh dashboard"
            type="button"
            style={{ padding: '8px' }}
          >
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Global Error Banner if initial fetch failed */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
          <AlertBanner type="error" message={error} style={{ flex: 1 }} />
          <button className="btn btn-secondary" onClick={() => fetchDashboardData()} type="button">
            Retry
          </button>
        </div>
      )}

      {/* Loading Skeleton Indicator */}
      {loading && !dashboardData && (
        <div className="loading-center" style={{ padding: '60px 0' }}>
          <Loader2 size={32} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
        </div>
      )}

      {/* Executive KPI Hierarchy Strip */}
      {dashboardData && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: 'var(--spacing-md)',
          }}
        >
          {/* Card 1: Primary Organizational Rate OR Shift Status */}
          {org?.attendance_today ? (
            <StatCard
              title="Net Attendance Rate"
              value={`${org.attendance_today.attendance_percentage.toFixed(1)}%`}
              icon={Activity}
              color={
                org.attendance_today.attendance_percentage >= 90
                  ? 'var(--color-status-success)'
                  : org.attendance_today.attendance_percentage >= 75
                  ? 'var(--color-status-warning)'
                  : 'var(--color-status-danger)'
              }
            />
          ) : (
            <StatCard
              title={attendanceToday?.check_out ? 'Shift Closed' : attendanceToday ? 'Clocked In' : 'No Punch Recorded'}
              value={
                attendanceToday?.check_in
                  ? new Date(attendanceToday.check_in).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  : 'Not Logged'
              }
              icon={Clock}
              color="#0284c7"
            />
          )}

          {/* Card 2: Workforce Capacity OR Team Status */}
          {org?.workforce ? (
            <StatCard
              title="Active Workforce"
              value={org.workforce.total_active}
              icon={Users}
              color="var(--color-primary)"
            />
          ) : team ? (
            <StatCard
              title="Team Direct Reports"
              value={`${team.attendance_today.present}/${team.direct_reports_count} Present`}
              icon={Users}
              color="var(--color-primary)"
            />
          ) : (
            <StatCard
              title={attendanceToday?.check_out ? 'Shift Closed' : attendanceToday ? 'Clocked In' : 'No Punch Recorded'}
              value={
                attendanceToday?.check_in
                  ? new Date(attendanceToday.check_in).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  : 'Not Logged'
              }
              icon={Clock}
              color="#0284c7"
            />
          )}

          {/* Card 3: Pending Approvals / Actions */}
          {team ? (
            <StatCard
              title="Pending Team Approvals"
              value={team.pending_approvals.leaves_count + team.pending_approvals.wfh_count}
              icon={Calendar}
              color="#d97706"
            />
          ) : org?.pending_approvals ? (
            <StatCard
              title="Pending Org Approvals"
              value={(org.pending_approvals.leaves_count || 0) + (org.pending_approvals.wfh_count || 0)}
              icon={Calendar}
              color="#d97706"
            />
          ) : (
            <StatCard
              title="My Pending Requests"
              value={personal?.my_pending_requests.total || 0}
              icon={Calendar}
              color="#d97706"
            />
          )}

          {/* Card 4: Available Leave Balance */}
          <StatCard
            title="Available Leave Days"
            value={`${totalLeaveRemaining}d`}
            icon={Coffee}
            color="#059669"
          />
        </div>
      )}

      {/* Main Responsive Asymmetric Layout */}
      {dashboardData && (
        <div className="dashboard-main-grid">
          {/* Primary Analytics Rail (Left) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)', minWidth: 0 }}>
            {/* Net Scheduled Attendance Rate & Distribution Bar */}
            {org?.attendance_today && <AttendanceRateWidget attendance={org.attendance_today} />}

            {/* Historical Analytics & Trends (7d Attendance / 6m Workforce) */}
            <DashboardTrendsSection />

            {/* Team Attendance Pulse for Managers */}
            {team && <TeamAttendanceWidget team={team} />}

            {/* Organization Workforce & Department Analytics */}
            {org?.workforce && <OrgWorkforceWidget workforce={org.workforce} />}
          </div>

          {/* Operational & Actions Rail (Right) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)', minWidth: 0 }}>
            {/* Personal Attendance Terminal */}
            <PersonalAttendanceWidget
              attendance={attendanceToday || null}
              actionLoading={actionLoading}
              actionError={actionError}
              onCheckIn={handleCheckIn}
              onCheckOut={handleCheckOut}
              onStartBreak={handleStartBreak}
              onEndBreak={handleEndBreak}
            />

            {/* Pending Approvals Command Center */}
            <PendingApprovalsWidget
              teamApprovals={team?.pending_approvals}
              orgApprovals={org?.pending_approvals}
              personalPending={personal?.my_pending_requests}
            />

            {/* Categorized Quick Actions */}
            <QuickActionsWidget hasTeam={Boolean(team)} hasOrg={Boolean(org?.workforce || org?.attendance_today)} />

            {/* Leave Balances with Progress Indicators */}
            <LeaveBalanceWidget balances={leaveBalances} />

            {/* Upcoming Company Holidays */}
            {personal && <UpcomingHolidaysWidget holidays={personal.upcoming_holidays} />}
          </div>
        </div>
      )}
    </div>
  );
};
