import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  Users,
  RefreshCw,
  Loader2,
  TrendingUp,
} from 'lucide-react';

import { Card } from '../Card';
import { AlertBanner } from '../AlertBanner';
import {
  dashboardService,
  type AttendanceTrendItem,
  type WorkforceTrendItem,
} from '../../services/dashboard';
import { AttendanceTrendChart } from './AttendanceTrendChart';
import { WorkforceTrendChart } from './WorkforceTrendChart';

type TabKey = 'attendance' | 'workforce';

export const DashboardTrendsSection: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabKey>('attendance');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [attendanceTrend, setAttendanceTrend] = useState<AttendanceTrendItem[] | null>(null);
  const [workforceTrend, setWorkforceTrend] = useState<WorkforceTrendItem[] | null>(null);

  const fetchTrends = useCallback(async (isSilent = false) => {
    if (!isSilent) {
      setLoading(true);
      setError(null);
    }

    try {
      // Concurrently query both trend windows
      const [res7d, res6m] = await Promise.all([
        dashboardService.getTrends('7d').catch((err) => {
          console.warn('Failed to fetch 7d attendance trends:', err);
          return null;
        }),
        dashboardService.getTrends('6m').catch((err) => {
          console.warn('Failed to fetch 6m workforce trends:', err);
          return null;
        }),
      ]);

      const attData = res7d?.attendance_trend ?? null;
      const wfData = res6m?.workforce_trend ?? null;

      setAttendanceTrend(attData);
      setWorkforceTrend(wfData);

      // Auto-select the available tab if one is restricted
      if (!attData && wfData) {
        setActiveTab('workforce');
      } else if (attData && !wfData) {
        setActiveTab('attendance');
      }
    } catch (err: any) {
      console.error('Failed to load dashboard historical trends:', err);
      if (!isSilent) {
        setError(
          err?.errorData?.detail ||
            err?.message ||
            'Unable to load historical trends. Please try again.'
        );
      }
    } finally {
      if (!isSilent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchTrends();
  }, [fetchTrends]);

  // If both trends are restricted / null (e.g. personal employee lacking attendance.view_all and employee.view)
  // Safely collapse and return null without rendering broken or unauthorized cards
  if (!loading && !error && attendanceTrend === null && workforceTrend === null) {
    return null;
  }

  const hasBoth = Boolean(attendanceTrend && workforceTrend);

  return (
    <Card
      title="Historical Performance Analytics"
      actions={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Tab Selection Switch if both trends are permitted */}
          {hasBoth && (
            <div
              style={{
                display: 'inline-flex',
                backgroundColor: 'var(--color-bg-page)',
                padding: '3px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border)',
                gap: '2px',
              }}
            >
              <button
                type="button"
                data-testid="tab-7d-attendance"
                onClick={() => setActiveTab('attendance')}
                style={{
                  padding: '4px 10px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 'var(--font-size-xs)',
                  fontWeight: activeTab === 'attendance' ? 600 : 500,
                  color: activeTab === 'attendance' ? 'var(--color-primary)' : 'var(--color-text-muted)',
                  backgroundColor: activeTab === 'attendance' ? 'var(--color-bg-card)' : 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                  boxShadow: activeTab === 'attendance' ? 'var(--shadow-xs)' : 'none',
                  transition: 'all 0.15s ease',
                }}
              >
                <Activity size={12} /> 7-Day Attendance
              </button>
              <button
                type="button"
                data-testid="tab-6m-workforce"
                onClick={() => setActiveTab('workforce')}
                style={{
                  padding: '4px 10px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 'var(--font-size-xs)',
                  fontWeight: activeTab === 'workforce' ? 600 : 500,
                  color: activeTab === 'workforce' ? 'var(--color-secondary)' : 'var(--color-text-muted)',
                  backgroundColor: activeTab === 'workforce' ? 'var(--color-bg-card)' : 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                  boxShadow: activeTab === 'workforce' ? 'var(--shadow-xs)' : 'none',
                  transition: 'all 0.15s ease',
                }}
              >
                <TrendingUp size={12} /> 6-Month Headcount
              </button>
            </div>
          )}

          {/* Single Badge Indicator if only one is available */}
          {!hasBoth && (attendanceTrend || workforceTrend) && (
            <span
              style={{
                fontSize: 'var(--font-size-xs)',
                color: attendanceTrend ? 'var(--color-primary)' : 'var(--color-secondary)',
                backgroundColor: attendanceTrend ? 'var(--color-primary-light)' : 'var(--color-secondary-light)',
                padding: '4px 10px',
                borderRadius: 'var(--radius-full)',
                fontWeight: 600,
                border: `1px solid ${attendanceTrend ? 'var(--color-primary-border)' : 'var(--color-secondary-border)'}`,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
              }}
            >
              {attendanceTrend ? <Activity size={13} /> : <Users size={13} />}
              {attendanceTrend ? '7-Day Attendance Trend' : '6-Month Headcount Trend'}
            </span>
          )}

          {/* Refresh Button */}
          <button
            className="btn btn-ghost"
            onClick={() => fetchTrends()}
            title="Refresh trends"
            type="button"
            style={{ padding: '6px' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
        {/* Error Notification */}
        {error && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
            <AlertBanner type="error" message={error} style={{ flex: 1 }} />
            <button className="btn btn-secondary" onClick={() => fetchTrends()} type="button">
              Retry
            </button>
          </div>
        )}

        {/* Loading Spinner */}
        {loading && !attendanceTrend && !workforceTrend && (
          <div className="loading-center" style={{ padding: '40px 0' }} data-testid="trends-loading">
            <Loader2 size={28} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
          </div>
        )}

        {/* Main Chart Rendering based on Active Tab */}
        {!loading && activeTab === 'attendance' && attendanceTrend && (
          <AttendanceTrendChart data={attendanceTrend} />
        )}

        {!loading && activeTab === 'workforce' && workforceTrend && (
          <WorkforceTrendChart data={workforceTrend} />
        )}
      </div>
    </Card>
  );
};
