import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Navigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';

import { useAuth } from '../contexts/AuthContext';
import { AlertBanner } from '../components/AlertBanner';
import { attendanceService, type AttendanceRecord } from '../services/attendance';
import {
  dashboardService,
  type DashboardOverviewResponse,
  type AttendanceTrendItem,
} from '../services/dashboard';
import { leaveService, type LeaveRequest } from '../services/leaves';

import {
  WelcomeBanner,
  AttendanceKpiCards,
  TodayAttendanceCard,
  AttendanceTrendWidget,
  RecentLeaveRequestsWidget,
  LeaveBalanceWidget,
  TeamAttendanceWidget,
  OrgWorkforceWidget,
  AttendanceRateWidget,
  QuickActionsWidget,
  UpcomingHolidaysWidget,
  PendingApprovalsWidget,
  DashboardTrendsSection,
  BreakReasonModal,
} from '../components/dashboard';
import type { BreakReasonKey } from '../types/attendance';

export const DashboardPage: React.FC = () => {
  const { user, hasEmployeeProfile } = useAuth();

  const [dashboardData, setDashboardData] = useState<DashboardOverviewResponse | null>(null);
  const [attendanceHistory, setAttendanceHistory] = useState<AttendanceRecord[]>([]);
  const [recentLeaveRequests, setRecentLeaveRequests] = useState<LeaveRequest[]>([]);
  const [orgTrendData, setOrgTrendData] = useState<AttendanceTrendItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const [isBreakModalOpen, setIsBreakModalOpen] = useState(false);
  const [breakActionLoading, setBreakActionLoading] = useState(false);
  const [breakActionError, setBreakActionError] = useState<string | null>(null);

  const fetchDashboardData = useCallback(
    async (isSilent = false) => {
      if (!isSilent) {
        setLoading(true);
        setError(null);
      }
      try {
        const [overviewData, historyData, leavesData, trendsData] = await Promise.all([
          dashboardService.getOverview(),
          hasEmployeeProfile
            ? attendanceService.getHistory().catch((err) => {
                console.warn('Failed to load personal attendance history:', err);
                return [] as AttendanceRecord[];
              })
            : Promise.resolve([] as AttendanceRecord[]),
          hasEmployeeProfile
            ? leaveService
                .getRequests({ page_size: 5 })
                .then((res: any) => {
                  if (Array.isArray(res)) return res;
                  if (res && Array.isArray(res.results)) return res.results;
                  return [] as LeaveRequest[];
                })
                .catch((err) => {
                  console.warn('Failed to load recent leave requests:', err);
                  return [] as LeaveRequest[];
                })
            : Promise.resolve([] as LeaveRequest[]),
          Promise.resolve()
            .then(() => dashboardService.getTrends('7d'))
            .then((res) => res?.attendance_trend ?? null)
            .catch(() => null),
        ]);

        setDashboardData(overviewData);
        setAttendanceHistory(historyData);
        setRecentLeaveRequests(leavesData);
        setOrgTrendData(trendsData);
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
    },
    [hasEmployeeProfile]
  );

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

  const handleOpenBreakModal = () => {
    setBreakActionError(null);
    setIsBreakModalOpen(true);
  };

  const handleStartBreak = async (reason: BreakReasonKey = 'lunch', comment?: string) => {
    setBreakActionLoading(true);
    setBreakActionError(null);
    try {
      let loc;
      try {
        loc = await getGeolocation();
      } catch (e) {
        console.warn('Geolocation capture failed', e);
      }
      await attendanceService.startBreak({
        reason,
        comment,
        ...(loc || {}),
      });
      await fetchDashboardData(true);
      setIsBreakModalOpen(false);
    } catch (e: any) {
      const msg = e?.errorData?.detail || 'Failed to start break. Please try again.';
      setBreakActionError(msg);
      throw e;
    } finally {
      setBreakActionLoading(false);
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

  const personal = dashboardData?.personal;
  const team = dashboardData?.team;
  const org = dashboardData?.organization;
  const attendanceToday = personal?.attendance_today;
  const leaveBalances = personal?.leave_balances || [];

  // Compute month-to-date personal metrics
  const kpiMetrics = useMemo(() => {
    if (!hasEmployeeProfile) return null;

    const now = new Date();
    const currentMonth = now.getMonth();
    const currentYear = now.getFullYear();

    const currentMonthRecords = attendanceHistory.filter((rec) => {
      if (!rec.date) return false;
      const d = new Date(rec.date);
      return d.getMonth() === currentMonth && d.getFullYear() === currentYear;
    });

    const relevantRecords = currentMonthRecords.length > 0 ? currentMonthRecords : attendanceHistory;

    const presentDays = relevantRecords.filter(
      (r) => r.status === 'present' || r.status === 'half_day' || Boolean(r.check_in)
    ).length;

    const lateArrivals = relevantRecords.filter((r) => r.is_late).length;

    let elapsedWorkingDays = 0;
    for (let day = 1; day <= now.getDate(); day++) {
      const checkDate = new Date(currentYear, currentMonth, day);
      const dayOfWeek = checkDate.getDay();
      if (dayOfWeek !== 0 && dayOfWeek !== 6) {
        elapsedWorkingDays++;
      }
    }
    const totalWorkingDays = Math.max(elapsedWorkingDays, relevantRecords.length, 1);

    const attendancePercentage =
      relevantRecords.length > 0
        ? Math.min(100, Math.round((presentDays / totalWorkingDays) * 100 * 10) / 10)
        : org?.attendance_today?.attendance_percentage ?? null;

    let totalSecondsWorked = 0;
    for (const rec of relevantRecords) {
      if (rec.productive_work_duration) {
        const parts = rec.productive_work_duration.split(':');
        if (parts.length >= 2) {
          const h = parseInt(parts[0], 10) || 0;
          const m = parseInt(parts[1], 10) || 0;
          const s = parseInt(parts[2], 10) || 0;
          totalSecondsWorked += h * 3600 + m * 60 + s;
        }
      }
    }

    if (attendanceToday?.check_in && attendanceToday?.productive_work_duration_seconds) {
      const todayDateStr = now.toISOString().split('T')[0];
      const hasTodayInRecords = relevantRecords.some((r) => r.date === todayDateStr);
      if (!hasTodayInRecords) {
        totalSecondsWorked += attendanceToday.productive_work_duration_seconds;
      }
    }

    const hoursWorked = Math.floor(totalSecondsWorked / 3600);
    const minsWorked = Math.floor((totalSecondsWorked % 3600) / 60);
    const hoursWorkedFormatted = `${hoursWorked}h ${minsWorked}m`;

    return {
      presentDays,
      totalWorkingDays,
      attendancePercentage,
      hoursWorkedFormatted,
      lateArrivals,
    };
  }, [hasEmployeeProfile, attendanceHistory, attendanceToday, org]);

  if (!user) {
    return (
      <div className="loading-center">
        <Loader2 size={28} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
      </div>
    );
  }

  // Redirect newly activated tenant owners to the onboarding launchpad
  if (user.canCreateOrganization) {
    return <Navigate to="/admin/organization-launchpad" replace />;
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      {/* 1. Deep-green Role-Aware Welcome Banner */}
      <WelcomeBanner
        user={user}
        hasEmployeeProfile={hasEmployeeProfile}
        attendanceToday={attendanceToday}
        actionLoading={actionLoading}
        loading={loading}
        onCheckIn={handleCheckIn}
        onCheckOut={handleCheckOut}
        onRefresh={() => fetchDashboardData()}
      />

      {/* Global Error Banner */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
          <AlertBanner type="error" message={error} style={{ flex: 1 }} />
          <button className="btn btn-secondary" onClick={() => fetchDashboardData()} type="button">
            Retry
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && !dashboardData && (
        <div className="loading-center" style={{ padding: '60px 0' }}>
          <Loader2 size={32} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
        </div>
      )}

      {/* 2. White Rounded Attendance KPI Cards Strip */}
      <AttendanceKpiCards
        hasEmployeeProfile={hasEmployeeProfile}
        presentDays={kpiMetrics?.presentDays}
        totalWorkingDays={kpiMetrics?.totalWorkingDays}
        attendancePercentage={kpiMetrics?.attendancePercentage}
        hoursWorkedFormatted={kpiMetrics?.hoursWorkedFormatted}
        lateArrivals={kpiMetrics?.lateArrivals}
        orgAttendancePercentage={org?.attendance_today?.attendance_percentage}
        orgActiveWorkforce={org?.workforce?.total_active}
        orgPendingApprovals={
          org?.pending_approvals
            ? (org.pending_approvals.leaves_count || 0) + (org.pending_approvals.wfh_count || 0)
            : team?.pending_approvals
            ? team.pending_approvals.leaves_count + team.pending_approvals.wfh_count
            : null
        }
        teamReportsCount={team?.direct_reports_count}
        teamPresentCount={team?.attendance_today?.present}
        loading={loading && !dashboardData}
      />

      {/* 3. Main Asymmetric Dashboard Grid */}
      {dashboardData && (
        <div className="dashboard-main-grid">
          {/* Primary Operations & Analytics Rail (Left) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)', minWidth: 0 }}>
            {/* Today's Attendance Terminal (Employees Only) */}
            {hasEmployeeProfile && (
              <TodayAttendanceCard
                attendance={attendanceToday || null}
                loading={loading && !dashboardData}
                actionLoading={actionLoading || breakActionLoading}
                actionError={actionError}
                onCheckIn={handleCheckIn}
                onCheckOut={handleCheckOut}
                onStartBreak={handleOpenBreakModal}
                onEndBreak={handleEndBreak}
              />
            )}

            {/* Attendance Trend Widget */}
            <AttendanceTrendWidget
              personalRecords={attendanceHistory}
              orgTrendData={orgTrendData}
              hasOrgViewPermission={Boolean(org || team)}
              loading={loading && !dashboardData}
            />

            {/* Team Attendance Pulse for Managers */}
            {team && <TeamAttendanceWidget team={team} />}

            {/* Net Scheduled Attendance Rate & Distribution Bar for Org */}
            {org?.attendance_today && <AttendanceRateWidget attendance={org.attendance_today} />}

            {/* Organization Workforce & Department Analytics */}
            {org?.workforce && <OrgWorkforceWidget workforce={org.workforce} />}

            {/* Historical Analytics & Trends (7d Attendance / 6m Workforce) */}
            <DashboardTrendsSection />
          </div>

          {/* Operational & Requests Rail (Right) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)', minWidth: 0 }}>
            {/* Recent Leave Requests Widget (Employees Only) */}
            {hasEmployeeProfile && (
              <RecentLeaveRequestsWidget
                requests={recentLeaveRequests}
                loading={loading && !dashboardData}
              />
            )}

            {/* Leave Balances with Progress Indicators (Employees Only) */}
            {hasEmployeeProfile && <LeaveBalanceWidget balances={leaveBalances} />}

            {/* Pending Approvals Command Center */}
            <PendingApprovalsWidget
              teamApprovals={team?.pending_approvals}
              orgApprovals={org?.pending_approvals}
              personalPending={personal?.my_pending_requests}
            />

            {/* Categorized Quick Actions */}
            <QuickActionsWidget hasTeam={Boolean(team)} hasOrg={Boolean(org?.workforce || org?.attendance_today)} />

            {/* Upcoming Company Holidays */}
            {personal?.upcoming_holidays && personal.upcoming_holidays.length > 0 && (
              <UpcomingHolidaysWidget holidays={personal.upcoming_holidays} />
            )}
          </div>
        </div>
      )}

      {hasEmployeeProfile && (
        <BreakReasonModal
          isOpen={isBreakModalOpen}
          onClose={() => {
            if (!breakActionLoading) {
              setIsBreakModalOpen(false);
              setBreakActionError(null);
            }
          }}
          onSubmit={handleStartBreak}
          loading={breakActionLoading}
          error={breakActionError}
        />
      )}
    </div>
  );
};

