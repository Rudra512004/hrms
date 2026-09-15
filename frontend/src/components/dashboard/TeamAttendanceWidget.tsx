import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  Calendar,
  Laptop,
  Coffee,
  UserX,
  ChevronRight,
  Users2,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../Card';
import { type TeamDashboardData } from '../../services/dashboard';

interface TeamAttendanceWidgetProps {
  team: TeamDashboardData;
}

export const TeamAttendanceWidget: React.FC<TeamAttendanceWidgetProps> = ({ team }) => {
  const navigate = useNavigate();
  const att = team.attendance_today;
  const total = team.direct_reports_count || 1;

  const presentPct = Math.round((att.present / total) * 100);
  const halfDayPct = Math.round((att.half_day / total) * 100);
  const leavePct = Math.round((att.on_leave / total) * 100);
  const absentPct = Math.max(0, 100 - (presentPct + halfDayPct + leavePct));

  return (
    <Card
      title="Team Attendance Pulse"
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
          <Users2 size={13} /> {team.direct_reports_count} Direct Reports
        </span>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
        {/* Team Segmented Proportional Bar */}
        <div
          style={{
            padding: '14px 16px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--color-bg-page)',
            border: '1px solid var(--color-border)',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-main)' }}>
              Today's Team Distribution
            </span>
            <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 600 }}>
              {att.present} of {team.direct_reports_count} on duty ({presentPct}%)
            </span>
          </div>

          <div
            style={{
              height: '8px',
              borderRadius: 'var(--radius-full)',
              overflow: 'hidden',
              display: 'flex',
              backgroundColor: 'var(--color-border)',
              width: '100%',
            }}
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
        </div>

        {/* Pulse Status Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(115px, 1fr))',
            gap: '8px',
          }}
        >
          {/* Present */}
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--color-status-success-bg)',
              border: '1px solid var(--color-status-success-border)',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: 'var(--color-status-success)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <CheckCircle2 size={12} /> Present
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-status-success)', marginTop: '2px' }}>
              {att.present}
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
            <div style={{ fontSize: '0.7rem', color: 'var(--color-status-warning)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <AlertTriangle size={12} /> Half Day
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-status-warning)', marginTop: '2px' }}>
              {att.half_day}
            </div>
          </div>

          {/* On Leave */}
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--color-primary-light)',
              border: '1px solid var(--color-primary-border)',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: 'var(--color-primary)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Calendar size={12} /> On Leave
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-primary)', marginTop: '2px' }}>
              {att.on_leave}
            </div>
          </div>

          {/* On WFH */}
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--color-secondary-light)',
              border: '1px solid var(--color-secondary-border)',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: 'var(--color-secondary-hover)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Laptop size={12} /> Remote WFH
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-secondary-hover)', marginTop: '2px' }}>
              {att.on_wfh}
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
            <div style={{ fontSize: '0.7rem', color: 'var(--color-status-danger)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <UserX size={12} /> Absent
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-status-danger)', marginTop: '2px' }}>
              {att.absent}
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
            <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Coffee size={12} /> On Break
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-text-main)', marginTop: '2px' }}>
              {att.on_break}
            </div>
          </div>
        </div>

        <button
          className="btn btn-ghost"
          onClick={() => navigate('/attendance')}
          style={{ width: '100%', fontSize: 'var(--font-size-xs)', paddingTop: 6, paddingBottom: 6 }}
          type="button"
        >
          View Team Attendance History <ChevronRight size={13} />
        </button>
      </div>
    </Card>
  );
};
