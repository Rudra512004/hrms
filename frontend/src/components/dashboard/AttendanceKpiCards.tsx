import React from 'react';
import {
  CalendarCheck,
  Activity,
  Clock,
  AlertCircle,
  Users,
  Calendar,
  Briefcase,
  TrendingUp,
} from 'lucide-react';

interface AttendanceKpiCardsProps {
  hasEmployeeProfile: boolean;
  // Personal employee metrics
  presentDays?: number | null;
  totalWorkingDays?: number | null;
  attendancePercentage?: number | null;
  hoursWorkedFormatted?: string | null;
  lateArrivals?: number | null;
  // Org / Admin fallback metrics
  orgAttendancePercentage?: number | null;
  orgActiveWorkforce?: number | null;
  orgPendingApprovals?: number | null;
  teamReportsCount?: number | null;
  teamPresentCount?: number | null;
  loading?: boolean;
}

export const AttendanceKpiCards: React.FC<AttendanceKpiCardsProps> = ({
  hasEmployeeProfile,
  presentDays,
  totalWorkingDays,
  attendancePercentage,
  hoursWorkedFormatted,
  lateArrivals,
  orgAttendancePercentage,
  orgActiveWorkforce,
  orgPendingApprovals,
  teamReportsCount,
  teamPresentCount,
  loading = false,
}) => {
  if (loading) {
    return (
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 'var(--spacing-md)',
        }}
      >
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            style={{
              backgroundColor: 'var(--color-bg-card)',
              borderRadius: 'var(--radius-xl)',
              padding: '20px 22px',
              border: '1px solid var(--color-border)',
              boxShadow: 'var(--shadow-xs)',
              minHeight: '110px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              gap: '10px',
            }}
          >
            <div
              style={{
                width: '40%',
                height: '14px',
                backgroundColor: 'var(--color-bg-secondary)',
                borderRadius: '4px',
              }}
            />
            <div
              style={{
                width: '60%',
                height: '24px',
                backgroundColor: 'var(--color-bg-secondary)',
                borderRadius: '4px',
              }}
            />
          </div>
        ))}
      </div>
    );
  }

  // Employee-specific 4 KPI cards
  if (hasEmployeeProfile) {
    const pct = attendancePercentage !== null && attendancePercentage !== undefined ? attendancePercentage : null;
    const pctLabel = pct !== null ? `${pct.toFixed(1)}%` : '--';
    const pctColor =
      pct !== null
        ? pct >= 90
          ? 'var(--color-status-success)'
          : pct >= 75
          ? 'var(--color-status-warning)'
          : 'var(--color-status-danger)'
        : 'var(--color-text-muted)';

    const lateCount = lateArrivals ?? 0;
    const lateBadgeColor =
      lateCount === 0
        ? 'var(--color-status-success)'
        : lateCount <= 2
        ? 'var(--color-status-warning)'
        : 'var(--color-status-danger)';

    return (
      <div
        data-testid="attendance-kpi-grid"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 'var(--spacing-md)',
        }}
      >
        {/* KPI 1: Present Days */}
        <div
          style={{
            backgroundColor: 'var(--color-bg-card)',
            borderRadius: 'var(--radius-xl)',
            padding: '20px 22px',
            border: '1px solid var(--color-border)',
            boxShadow: 'var(--shadow-xs)',
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            transition: 'transform 0.15s ease, box-shadow 0.15s ease',
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 'var(--radius-lg)',
              backgroundColor: 'rgba(46, 125, 79, 0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              color: 'var(--color-status-success)',
            }}
          >
            <CalendarCheck size={24} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <span
              style={{
                fontSize: 'var(--font-size-xs)',
                fontWeight: 600,
                color: 'var(--color-text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                display: 'block',
                marginBottom: '2px',
              }}
            >
              Present Days
            </span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
              <span
                style={{
                  fontSize: '1.6rem',
                  fontWeight: 700,
                  color: 'var(--color-text-main)',
                  lineHeight: 1.2,
                }}
              >
                {presentDays !== null && presentDays !== undefined ? presentDays : '--'}
              </span>
              {totalWorkingDays ? (
                <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                  / {totalWorkingDays} days
                </span>
              ) : (
                <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                  this month
                </span>
              )}
            </div>
          </div>
        </div>

        {/* KPI 2: Attendance Percentage */}
        <div
          style={{
            backgroundColor: 'var(--color-bg-card)',
            borderRadius: 'var(--radius-xl)',
            padding: '20px 22px',
            border: '1px solid var(--color-border)',
            boxShadow: 'var(--shadow-xs)',
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            transition: 'transform 0.15s ease, box-shadow 0.15s ease',
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 'var(--radius-lg)',
              backgroundColor: 'rgba(53, 120, 181, 0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              color: 'var(--color-status-info)',
            }}
          >
            <Activity size={24} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <span
              style={{
                fontSize: 'var(--font-size-xs)',
                fontWeight: 600,
                color: 'var(--color-text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                display: 'block',
                marginBottom: '2px',
              }}
            >
              Attendance Rate
            </span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
              <span
                style={{
                  fontSize: '1.6rem',
                  fontWeight: 700,
                  color: pctColor,
                  lineHeight: 1.2,
                }}
              >
                {pctLabel}
              </span>
              <span
                style={{
                  fontSize: 'var(--font-size-xs)',
                  fontWeight: 600,
                  color: pctColor,
                  padding: '1px 6px',
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: 'var(--color-bg-secondary)',
                }}
              >
                {pct !== null ? (pct >= 90 ? 'Optimal' : pct >= 75 ? 'Average' : 'Low') : 'Logged'}
              </span>
            </div>
          </div>
        </div>

        {/* KPI 3: Hours Worked */}
        <div
          style={{
            backgroundColor: 'var(--color-bg-card)',
            borderRadius: 'var(--radius-xl)',
            padding: '20px 22px',
            border: '1px solid var(--color-border)',
            boxShadow: 'var(--shadow-xs)',
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            transition: 'transform 0.15s ease, box-shadow 0.15s ease',
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 'var(--radius-lg)',
              backgroundColor: 'rgba(124, 58, 237, 0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              color: 'var(--color-status-pending)',
            }}
          >
            <Clock size={24} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <span
              style={{
                fontSize: 'var(--font-size-xs)',
                fontWeight: 600,
                color: 'var(--color-text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                display: 'block',
                marginBottom: '2px',
              }}
            >
              Hours Worked
            </span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
              <span
                style={{
                  fontSize: '1.6rem',
                  fontWeight: 700,
                  color: 'var(--color-text-main)',
                  lineHeight: 1.2,
                }}
              >
                {hoursWorkedFormatted || '--'}
              </span>
              <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                productive
              </span>
            </div>
          </div>
        </div>

        {/* KPI 4: Late Arrivals */}
        <div
          style={{
            backgroundColor: 'var(--color-bg-card)',
            borderRadius: 'var(--radius-xl)',
            padding: '20px 22px',
            border: '1px solid var(--color-border)',
            boxShadow: 'var(--shadow-xs)',
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            transition: 'transform 0.15s ease, box-shadow 0.15s ease',
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 'var(--radius-lg)',
              backgroundColor: 'rgba(198, 138, 27, 0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              color: 'var(--color-status-warning)',
            }}
          >
            <AlertCircle size={24} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <span
              style={{
                fontSize: 'var(--font-size-xs)',
                fontWeight: 600,
                color: 'var(--color-text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                display: 'block',
                marginBottom: '2px',
              }}
            >
              Late Arrivals
            </span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
              <span
                style={{
                  fontSize: '1.6rem',
                  fontWeight: 700,
                  color: lateCount > 0 ? 'var(--color-status-warning)' : 'var(--color-status-success)',
                  lineHeight: 1.2,
                }}
              >
                {lateCount}
              </span>
              <span
                style={{
                  fontSize: 'var(--font-size-xs)',
                  fontWeight: 600,
                  color: lateBadgeColor,
                  padding: '1px 6px',
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: 'var(--color-bg-secondary)',
                }}
              >
                {lateCount === 0 ? 'On Time' : 'Grace Exceeded'}
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Headless Administrator / System Manager KPI strip
  return (
    <div
      data-testid="admin-kpi-grid"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 'var(--spacing-md)',
      }}
    >
      <div
        style={{
          backgroundColor: 'var(--color-bg-card)',
          borderRadius: 'var(--radius-xl)',
          padding: '20px 22px',
          border: '1px solid var(--color-border)',
          boxShadow: 'var(--shadow-xs)',
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
        }}
      >
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 'var(--radius-lg)',
            backgroundColor: 'rgba(31, 93, 54, 0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--color-primary)',
          }}
        >
          <TrendingUp size={24} />
        </div>
        <div>
          <span style={{ fontSize: 'var(--font-size-xs)', fontWeight: 600, color: 'var(--color-text-muted)', display: 'block' }}>
            ORG ATTENDANCE
          </span>
          <span style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
            {orgAttendancePercentage !== null && orgAttendancePercentage !== undefined
              ? `${orgAttendancePercentage.toFixed(1)}%`
              : '--'}
          </span>
        </div>
      </div>

      <div
        style={{
          backgroundColor: 'var(--color-bg-card)',
          borderRadius: 'var(--radius-xl)',
          padding: '20px 22px',
          border: '1px solid var(--color-border)',
          boxShadow: 'var(--shadow-xs)',
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
        }}
      >
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 'var(--radius-lg)',
            backgroundColor: 'rgba(53, 120, 181, 0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--color-status-info)',
          }}
        >
          <Users size={24} />
        </div>
        <div>
          <span style={{ fontSize: 'var(--font-size-xs)', fontWeight: 600, color: 'var(--color-text-muted)', display: 'block' }}>
            ACTIVE WORKFORCE
          </span>
          <span style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
            {orgActiveWorkforce !== null && orgActiveWorkforce !== undefined ? orgActiveWorkforce : '--'}
          </span>
        </div>
      </div>

      <div
        style={{
          backgroundColor: 'var(--color-bg-card)',
          borderRadius: 'var(--radius-xl)',
          padding: '20px 22px',
          border: '1px solid var(--color-border)',
          boxShadow: 'var(--shadow-xs)',
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
        }}
      >
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 'var(--radius-lg)',
            backgroundColor: 'rgba(198, 138, 27, 0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--color-status-warning)',
          }}
        >
          <Calendar size={24} />
        </div>
        <div>
          <span style={{ fontSize: 'var(--font-size-xs)', fontWeight: 600, color: 'var(--color-text-muted)', display: 'block' }}>
            PENDING APPROVALS
          </span>
          <span style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
            {orgPendingApprovals !== null && orgPendingApprovals !== undefined ? orgPendingApprovals : 0}
          </span>
        </div>
      </div>

      <div
        style={{
          backgroundColor: 'var(--color-bg-card)',
          borderRadius: 'var(--radius-xl)',
          padding: '20px 22px',
          border: '1px solid var(--color-border)',
          boxShadow: 'var(--shadow-xs)',
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
        }}
      >
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 'var(--radius-lg)',
            backgroundColor: 'rgba(46, 125, 79, 0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--color-secondary)',
          }}
        >
          <Briefcase size={24} />
        </div>
        <div>
          <span style={{ fontSize: 'var(--font-size-xs)', fontWeight: 600, color: 'var(--color-text-muted)', display: 'block' }}>
            TEAM PRESENT
          </span>
          <span style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
            {teamReportsCount ? `${teamPresentCount ?? 0}/${teamReportsCount}` : 'Enterprise'}
          </span>
        </div>
      </div>
    </div>
  );
};
