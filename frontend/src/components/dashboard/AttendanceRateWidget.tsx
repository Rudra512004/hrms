import React from 'react';
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  Calendar,
  UserX,
  Laptop,
  Coffee,
  ChevronRight,
  Info,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../Card';
import { type OrganizationAttendanceToday } from '../../services/dashboard';

interface AttendanceRateWidgetProps {
  attendance: OrganizationAttendanceToday;
}

export const AttendanceRateWidget: React.FC<AttendanceRateWidgetProps> = ({ attendance }) => {
  const navigate = useNavigate();
  const rate = attendance.attendance_percentage;
  const total = attendance.expected_total || 1;

  // Segment widths proportional to total workforce
  const presentPct = Math.round((attendance.present / total) * 100);
  const halfDayPct = Math.round((attendance.half_day / total) * 100);
  const leavePct = Math.round((attendance.on_leave / total) * 100);
  const absentPct = Math.max(0, 100 - (presentPct + halfDayPct + leavePct));

  const getRateColor = (r: number) => {
    if (r >= 90) return 'var(--color-status-success)';
    if (r >= 75) return 'var(--color-status-warning)';
    return 'var(--color-status-danger)';
  };

  const rateColor = getRateColor(rate);
  const effectivePresent = attendance.present + attendance.half_day * 0.5;

  return (
    <Card
      title="Net Scheduled Attendance Rate"
      actions={
        <span
          style={{
            fontSize: 'var(--font-size-xs)',
            color: 'var(--color-primary)',
            backgroundColor: 'var(--color-primary-light)',
            padding: '4px 10px',
            borderRadius: 'var(--radius-full)',
            fontWeight: 600,
            border: '1px solid var(--color-primary-border)',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '5px',
          }}
        >
          <Activity size={13} /> Organization Pulse
        </span>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
        {/* Headline Rate Callout & Segmented Stacked Bar */}
        <div
          style={{
            padding: '18px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--color-bg-page)',
            border: '1px solid var(--color-border)',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                <span style={{ fontSize: '2.5rem', fontWeight: 800, color: rateColor, lineHeight: 1, letterSpacing: '-0.03em' }}>
                  {rate.toFixed(1)}%
                </span>
                <span
                  style={{
                    fontSize: 'var(--font-size-xs)',
                    fontWeight: 600,
                    padding: '3px 8px',
                    borderRadius: 'var(--radius-full)',
                    backgroundColor: rate >= 90 ? 'var(--color-status-success-bg)' : rate >= 75 ? 'var(--color-status-warning-bg)' : 'var(--color-status-danger-bg)',
                    color: rateColor,
                    border: `1px solid ${rateColor}40`,
                  }}
                >
                  {rate >= 90 ? 'Optimal' : rate >= 75 ? 'Moderate' : 'Needs Review'}
                </span>
              </div>
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                Effective Present ({effectivePresent}) ÷ Scheduled Working ({attendance.expected_working})
              </div>
            </div>

            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
                {attendance.present} / {attendance.expected_working}
              </div>
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                Full Day Present / Scheduled
              </div>
            </div>
          </div>

          {/* Proportional Segmented Attendance Bar */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div
              style={{
                height: '10px',
                borderRadius: 'var(--radius-full)',
                overflow: 'hidden',
                display: 'flex',
                backgroundColor: 'var(--color-border)',
                width: '100%',
              }}
              title={`Present: ${presentPct}%, Half Day: ${halfDayPct}%, Leave: ${leavePct}%, Absent: ${absentPct}%`}
            >
              {presentPct > 0 && (
                <div
                  style={{
                    width: `${presentPct}%`,
                    backgroundColor: 'var(--color-status-success)',
                    transition: 'width 0.4s ease',
                  }}
                />
              )}
              {halfDayPct > 0 && (
                <div
                  style={{
                    width: `${halfDayPct}%`,
                    backgroundColor: 'var(--color-status-warning)',
                    transition: 'width 0.4s ease',
                  }}
                />
              )}
              {leavePct > 0 && (
                <div
                  style={{
                    width: `${leavePct}%`,
                    backgroundColor: 'var(--color-primary)',
                    transition: 'width 0.4s ease',
                  }}
                />
              )}
              {absentPct > 0 && (
                <div
                  style={{
                    width: `${absentPct}%`,
                    backgroundColor: 'var(--color-status-danger)',
                    transition: 'width 0.4s ease',
                  }}
                />
              )}
            </div>

            {/* Visual Bar Legend */}
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: '12px',
                fontSize: '0.72rem',
                color: 'var(--color-text-muted)',
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'var(--color-status-success)' }} />
                Present ({attendance.present})
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'var(--color-status-warning)' }} />
                Half Day ({attendance.half_day})
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'var(--color-primary)' }} />
                Approved Leave ({attendance.on_leave})
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'var(--color-status-danger)' }} />
                Absent ({attendance.absent})
              </span>
            </div>
          </div>
        </div>

        {/* Detailed Metric Cards */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: '10px',
          }}
        >
          {/* Scheduled Working */}
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--color-bg-page)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
              Scheduled Working
            </div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-text-main)', marginTop: '2px' }}>
              {attendance.expected_working}
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)' }}>
              {attendance.expected_total} active - {attendance.on_leave} on leave
            </div>
          </div>

          {/* Full Day Present */}
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--color-status-success-bg)',
              border: '1px solid var(--color-status-success-border)',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: 'var(--color-status-success)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', textTransform: 'uppercase' }}>
              <CheckCircle2 size={12} /> Present
            </div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-status-success)', marginTop: '2px' }}>
              {attendance.present}
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--color-text-sub)' }}>
              {Math.round((attendance.present / total) * 100)}% of total active
            </div>
          </div>

          {/* Half Day */}
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--color-status-warning-bg)',
              border: '1px solid var(--color-status-warning-border)',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: 'var(--color-status-warning)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', textTransform: 'uppercase' }}>
              <AlertTriangle size={12} /> Half Day
            </div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-status-warning)', marginTop: '2px' }}>
              {attendance.half_day}
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--color-text-sub)' }}>
              0.5 effective credit
            </div>
          </div>

          {/* Approved Leave */}
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--color-primary-light)',
              border: '1px solid var(--color-primary-border)',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: 'var(--color-primary)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', textTransform: 'uppercase' }}>
              <Calendar size={12} /> Approved Leave
            </div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-primary)', marginTop: '2px' }}>
              {attendance.on_leave}
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--color-text-sub)' }}>
              Excused scheduled
            </div>
          </div>

          {/* Absent */}
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--color-status-danger-bg)',
              border: '1px solid var(--color-status-danger-border)',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: 'var(--color-status-danger)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', textTransform: 'uppercase' }}>
              <UserX size={12} /> Absent
            </div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-status-danger)', marginTop: '2px' }}>
              {attendance.absent}
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--color-text-sub)' }}>
              Unexcused absence
            </div>
          </div>

          {/* Remote WFH Overlay */}
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--color-secondary-light)',
              border: '1px solid var(--color-secondary-border)',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: 'var(--color-secondary-hover)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', textTransform: 'uppercase' }}>
              <Laptop size={12} /> Remote WFH
            </div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-secondary-hover)', marginTop: '2px' }}>
              {attendance.on_wfh}
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--color-text-sub)' }}>
              Working remotely
            </div>
          </div>

          {/* On Break */}
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--color-bg-page)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', textTransform: 'uppercase' }}>
              <Coffee size={12} /> On Break
            </div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-text-main)', marginTop: '2px' }}>
              {attendance.on_break}
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)' }}>
              Punched out for break
            </div>
          </div>
        </div>

        {/* Informative Denominator Clarification Box */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 12px',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--color-bg-subtle)',
            border: '1px solid var(--color-border-subtle)',
            fontSize: '0.73rem',
            color: 'var(--color-text-muted)',
          }}
        >
          <Info size={14} style={{ flexShrink: 0, color: 'var(--color-primary)' }} />
          <span>
            <strong>Scheduled Attendance Rate:</strong> Employees with approved leave are excluded from the denominator.
            Employees on remote WFH remain in expected working.
          </span>
        </div>

        <button
          className="btn btn-ghost"
          onClick={() => navigate('/attendance')}
          style={{ width: '100%', fontSize: 'var(--font-size-xs)', paddingTop: 6, paddingBottom: 6 }}
          type="button"
        >
          View Detailed Attendance Insights <ChevronRight size={13} />
        </button>
      </div>
    </Card>
  );
};
