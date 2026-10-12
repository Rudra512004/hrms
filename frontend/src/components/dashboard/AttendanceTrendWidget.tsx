import React, { useState } from 'react';
import {
  TrendingUp,
  Activity,
  Clock,
  Loader2,
} from 'lucide-react';
import { type AttendanceTrendItem } from '../../services/dashboard';
import { type AttendanceRecord } from '../../types/attendance';

interface AttendanceTrendWidgetProps {
  personalRecords?: AttendanceRecord[];
  orgTrendData?: AttendanceTrendItem[] | null;
  hasOrgViewPermission?: boolean;
  loading?: boolean;
}

// Parses "HH:MM:SS" into hours (e.g. "08:30:00" -> 8.5)
const parseDurationToHours = (durationStr: string | null): number => {
  if (!durationStr) return 0;
  const parts = durationStr.split(':');
  if (parts.length >= 2) {
    const hours = parseInt(parts[0], 10) || 0;
    const minutes = parseInt(parts[1], 10) || 0;
    return Math.round((hours + minutes / 60) * 10) / 10;
  }
  return 0;
};

export const AttendanceTrendWidget: React.FC<AttendanceTrendWidgetProps> = ({
  personalRecords = [],
  orgTrendData = null,
  hasOrgViewPermission = false,
  loading = false,
}) => {
  const [activeTab, setActiveTab] = useState<'personal' | 'org'>(
    personalRecords.length > 0 || !hasOrgViewPermission ? 'personal' : 'org'
  );
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // Process personal records for the trend (last 7 recorded days ascending)
  const recentPersonalRecords = [...personalRecords]
    .sort((a, b) => (a.date > b.date ? 1 : -1))
    .slice(-7);

  // Chart Dimensions
  const svgWidth = 640;
  const svgHeight = 200;
  const paddingLeft = 45;
  const paddingRight = 25;
  const paddingTop = 20;
  const paddingBottom = 35;
  const chartWidth = svgWidth - paddingLeft - paddingRight;
  const chartHeight = svgHeight - paddingTop - paddingBottom;

  // Render Personal Trend Chart
  const renderPersonalChart = () => {
    if (recentPersonalRecords.length === 0) {
      return (
        <div
          data-testid="personal-trend-empty"
          style={{
            padding: '36px 20px',
            textAlign: 'center',
            backgroundColor: 'var(--color-bg-page)',
            borderRadius: 'var(--radius-lg)',
            border: '1px dashed var(--color-border)',
          }}
        >
          <Clock size={32} style={{ margin: '0 auto 10px', color: 'var(--color-text-muted)' }} />
          <p style={{ margin: '0 0 4px', fontWeight: 600, color: 'var(--color-text-main)' }}>
            No Attendance History Yet
          </p>
          <p style={{ margin: 0, fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            Log attendance punches to view your 7-day productive hours trend.
          </p>
        </div>
      );
    }

    const maxHours = Math.max(
      10,
      Math.ceil(Math.max(...recentPersonalRecords.map((r) => parseDurationToHours(r.productive_work_duration))))
    );

    const stepX = recentPersonalRecords.length > 1 ? chartWidth / (recentPersonalRecords.length - 1) : chartWidth / 2;
    const getX = (i: number) => paddingLeft + (recentPersonalRecords.length > 1 ? i * stepX : chartWidth / 2);
    const getY = (hrs: number) => paddingTop + chartHeight - (Math.min(hrs, maxHours) / maxHours) * chartHeight;

    const points = recentPersonalRecords.map((r, i) => ({
      x: getX(i),
      y: getY(parseDurationToHours(r.productive_work_duration)),
      hours: parseDurationToHours(r.productive_work_duration),
      record: r,
    }));

    const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
    const areaD = `${pathD} L ${points[points.length - 1].x.toFixed(1)} ${paddingTop + chartHeight} L ${points[0].x.toFixed(1)} ${paddingTop + chartHeight} Z`;

    const activePoint = hoveredIndex !== null ? points[hoveredIndex] : null;

    return (
      <div style={{ position: 'relative', width: '100%' }}>
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          style={{ width: '100%', height: 'auto', display: 'block' }}
          role="img"
          aria-label="Personal attendance hours trend"
        >
          <defs>
            <linearGradient id="personalGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1F5D36" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#1F5D36" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines (0h, 4h, 8h) */}
          {[0, maxHours / 2, maxHours].map((h, idx) => {
            const y = getY(h);
            return (
              <g key={idx}>
                <line
                  x1={paddingLeft}
                  y1={y}
                  x2={svgWidth - paddingRight}
                  y2={y}
                  stroke="var(--color-border-subtle)"
                  strokeDasharray="4 4"
                  strokeWidth="1"
                />
                <text
                  x={paddingLeft - 8}
                  y={y + 4}
                  textAnchor="end"
                  fontSize="11"
                  fill="var(--color-text-muted)"
                  fontFamily="Inter, sans-serif"
                >
                  {`${Math.round(h)}h`}
                </text>
              </g>
            );
          })}

          {/* Fill Area */}
          <path d={areaD} fill="url(#personalGradient)" />

          {/* Line */}
          <path d={pathD} fill="none" stroke="var(--color-primary)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />

          {/* Dots & Labels */}
          {points.map((p, i) => {
            const dateObj = new Date(p.record.date);
            const dateLabel = dateObj.toLocaleDateString(undefined, { weekday: 'short' });
            const isHovered = hoveredIndex === i;

            return (
              <g key={i}>
                <line
                  x1={p.x}
                  y1={paddingTop + chartHeight}
                  x2={p.x}
                  y2={paddingTop + chartHeight + 6}
                  stroke="var(--color-border)"
                  strokeWidth="1"
                />
                <text
                  x={p.x}
                  y={paddingTop + chartHeight + 18}
                  textAnchor="middle"
                  fontSize="11"
                  fontWeight="600"
                  fill="var(--color-text-sub)"
                  fontFamily="Inter, sans-serif"
                >
                  {dateLabel}
                </text>

                {/* Interactive Hit Area */}
                <circle
                  cx={p.x}
                  cy={p.y}
                  r="16"
                  fill="transparent"
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setHoveredIndex(i)}
                  onMouseLeave={() => setHoveredIndex(null)}
                />

                {/* Dot */}
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={isHovered ? 6 : 4}
                  fill={p.record.is_late ? '#C68A1B' : '#1F5D36'}
                  stroke="#FFFFFF"
                  strokeWidth="2"
                  style={{ pointerEvents: 'none', transition: 'r 0.15s ease' }}
                />
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip Overlay */}
        {activePoint && (
          <div
            style={{
              position: 'absolute',
              top: '10px',
              right: '20px',
              backgroundColor: 'var(--color-bg-card)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              padding: '8px 12px',
              boxShadow: 'var(--shadow-md)',
              fontSize: 'var(--font-size-xs)',
              pointerEvents: 'none',
              zIndex: 10,
            }}
          >
            <div style={{ fontWeight: 700, color: 'var(--color-text-main)' }}>
              {activePoint.record.date} ({new Date(activePoint.record.date).toLocaleDateString(undefined, { weekday: 'long' })})
            </div>
            <div style={{ color: 'var(--color-primary)', fontWeight: 600 }}>
              Worked: {activePoint.hours}h ({activePoint.record.productive_work_duration || '--'})
            </div>
            {activePoint.record.is_late && (
              <div style={{ color: 'var(--color-status-warning)', fontWeight: 600 }}>
                • Late arrival recorded
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // Render Organization Trend Chart
  const renderOrgChart = () => {
    if (!orgTrendData || orgTrendData.length === 0) {
      return (
        <div
          data-testid="org-trend-empty"
          style={{
            padding: '36px 20px',
            textAlign: 'center',
            backgroundColor: 'var(--color-bg-page)',
            borderRadius: 'var(--radius-lg)',
            border: '1px dashed var(--color-border)',
          }}
        >
          <Activity size={32} style={{ margin: '0 auto 10px', color: 'var(--color-text-muted)' }} />
          <p style={{ margin: '0 0 4px', fontWeight: 600, color: 'var(--color-text-main)' }}>
            No Organization Trend Data
          </p>
          <p style={{ margin: 0, fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            No net attendance aggregated for this period.
          </p>
        </div>
      );
    }

    const stepX = orgTrendData.length > 1 ? chartWidth / (orgTrendData.length - 1) : chartWidth / 2;
    const getX = (i: number) => paddingLeft + i * stepX;
    const getY = (pct: number) => paddingTop + chartHeight - (Math.min(100, Math.max(0, pct)) / 100) * chartHeight;

    const points = orgTrendData.map((d, i) => ({
      x: getX(i),
      y: getY(d.attendance_percentage ?? 0),
      item: d,
    }));

    const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
    const areaD = `${pathD} L ${points[points.length - 1].x.toFixed(1)} ${paddingTop + chartHeight} L ${points[0].x.toFixed(1)} ${paddingTop + chartHeight} Z`;

    return (
      <div style={{ position: 'relative', width: '100%' }}>
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          style={{ width: '100%', height: 'auto', display: 'block' }}
          role="img"
          aria-label="Organization attendance trend"
        >
          <defs>
            <linearGradient id="orgGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2E7D4F" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#2E7D4F" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {[0, 50, 100].map((pct, idx) => {
            const y = getY(pct);
            return (
              <g key={idx}>
                <line
                  x1={paddingLeft}
                  y1={y}
                  x2={svgWidth - paddingRight}
                  y2={y}
                  stroke="var(--color-border-subtle)"
                  strokeDasharray="4 4"
                  strokeWidth="1"
                />
                <text
                  x={paddingLeft - 8}
                  y={y + 4}
                  textAnchor="end"
                  fontSize="11"
                  fill="var(--color-text-muted)"
                  fontFamily="Inter, sans-serif"
                >
                  {`${pct}%`}
                </text>
              </g>
            );
          })}

          <path d={areaD} fill="url(#orgGradient)" />
          <path d={pathD} fill="none" stroke="var(--color-status-success)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />

          {points.map((p, i) => (
            <g key={i}>
              <text
                x={p.x}
                y={paddingTop + chartHeight + 18}
                textAnchor="middle"
                fontSize="11"
                fontWeight="600"
                fill="var(--color-text-sub)"
                fontFamily="Inter, sans-serif"
              >
                {p.item.day_name.slice(0, 3)}
              </text>
              <circle
                cx={p.x}
                cy={p.y}
                r={4}
                fill="#2E7D4F"
                stroke="#FFFFFF"
                strokeWidth="2"
              />
            </g>
          ))}
        </svg>
      </div>
    );
  };

  return (
    <div
      data-testid="attendance-trend-widget"
      style={{
        backgroundColor: 'var(--color-bg-card)',
        borderRadius: 'var(--radius-xl)',
        padding: '24px',
        border: '1px solid var(--color-border)',
        boxShadow: 'var(--shadow-sm)',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}
    >
      {/* Widget Header with Toggle */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          borderBottom: '1px solid var(--color-border-subtle)',
          paddingBottom: '14px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'rgba(46, 125, 79, 0.1)',
              color: 'var(--color-status-success)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <TrendingUp size={20} />
          </div>
          <div>
            <h2
              style={{
                fontSize: '1.1rem',
                fontWeight: 700,
                margin: 0,
                color: 'var(--color-text-main)',
              }}
            >
              Attendance Trend
            </h2>
            <p style={{ margin: 0, fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
              Recent working days pattern and activity
            </p>
          </div>
        </div>

        {/* Tab Toggle if user has Org permissions */}
        {hasOrgViewPermission && orgTrendData && (
          <div
            style={{
              display: 'flex',
              backgroundColor: 'var(--color-bg-page)',
              borderRadius: 'var(--radius-md)',
              padding: '3px',
              border: '1px solid var(--color-border-subtle)',
            }}
          >
            <button
              onClick={() => setActiveTab('personal')}
              type="button"
              style={{
                border: 'none',
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm)',
                fontSize: 'var(--font-size-xs)',
                fontWeight: 600,
                cursor: 'pointer',
                backgroundColor: activeTab === 'personal' ? 'var(--color-bg-card)' : 'transparent',
                color: activeTab === 'personal' ? 'var(--color-text-main)' : 'var(--color-text-muted)',
                boxShadow: activeTab === 'personal' ? 'var(--shadow-xs)' : 'none',
              }}
            >
              My Hours
            </button>
            <button
              onClick={() => setActiveTab('org')}
              type="button"
              style={{
                border: 'none',
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm)',
                fontSize: 'var(--font-size-xs)',
                fontWeight: 600,
                cursor: 'pointer',
                backgroundColor: activeTab === 'org' ? 'var(--color-bg-card)' : 'transparent',
                color: activeTab === 'org' ? 'var(--color-text-main)' : 'var(--color-text-muted)',
                boxShadow: activeTab === 'org' ? 'var(--shadow-xs)' : 'none',
              }}
            >
              Org Rate
            </button>
          </div>
        )}
      </div>

      {loading ? (
        <div className="loading-center" style={{ padding: '40px' }}>
          <Loader2 size={24} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
        </div>
      ) : activeTab === 'personal' ? (
        renderPersonalChart()
      ) : (
        renderOrgChart()
      )}
    </div>
  );
};
