import React, { useState } from 'react';
import {
  Activity,
  Calendar,
} from 'lucide-react';
import { type AttendanceTrendItem } from '../../services/dashboard';

interface AttendanceTrendChartProps {
  data: AttendanceTrendItem[];
}

export const AttendanceTrendChart: React.FC<AttendanceTrendChartProps> = ({ data }) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  if (!data || data.length === 0) {
    return (
      <div
        data-testid="attendance-trend-empty"
        style={{
          padding: '40px 20px',
          textAlign: 'center',
          color: 'var(--color-text-muted)',
          backgroundColor: 'var(--color-bg-page)',
          borderRadius: 'var(--radius-md)',
          border: '1px dashed var(--color-border)',
        }}
      >
        <Calendar size={32} style={{ margin: '0 auto 10px', opacity: 0.5 }} />
        <p style={{ margin: 0, fontWeight: 500 }}>No attendance trend data available for this period.</p>
      </div>
    );
  }

  // Calculate summary metrics across the 7-day window
  const workingDays = data.filter((d) => d.is_working_day && d.attendance_percentage !== null);
  const avgAttendance =
    workingDays.length > 0
      ? workingDays.reduce((acc, d) => acc + (d.attendance_percentage ?? 0), 0) / workingDays.length
      : null;

  const totalPresentInPeriod = data.reduce((acc, d) => acc + d.present, 0);
  const totalHalfDayInPeriod = data.reduce((acc, d) => acc + d.half_day, 0);
  const totalLeaveInPeriod = data.reduce((acc, d) => acc + d.on_leave, 0);
  const totalWfhInPeriod = data.reduce((acc, d) => acc + d.on_wfh, 0);

  // SVG dimensions and layout configuration
  const svgWidth = 720;
  const svgHeight = 220;
  const paddingLeft = 55;
  const paddingRight = 35;
  const paddingTop = 25;
  const paddingBottom = 40;
  const chartWidth = svgWidth - paddingLeft - paddingRight;
  const chartHeight = svgHeight - paddingTop - paddingBottom;

  const stepX = data.length > 1 ? chartWidth / (data.length - 1) : chartWidth;

  const getX = (index: number) => paddingLeft + index * stepX;
  const getY = (percentage: number) => {
    const clamped = Math.max(0, Math.min(100, percentage));
    return paddingTop + chartHeight - (clamped / 100) * chartHeight;
  };

  // Build SVG path segments connecting working days (skips non-working days cleanly)
  const lineSegments: string[] = [];
  const areaSegments: string[] = [];
  let currentLineSegment: { x: number; y: number }[] = [];

  data.forEach((item, idx) => {
    if (item.is_working_day && item.attendance_percentage !== null) {
      currentLineSegment.push({ x: getX(idx), y: getY(item.attendance_percentage) });
    } else {
      if (currentLineSegment.length > 1) {
        lineSegments.push(
          currentLineSegment.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`).join(' ')
        );
        const first = currentLineSegment[0];
        const last = currentLineSegment[currentLineSegment.length - 1];
        const bottomY = paddingTop + chartHeight;
        areaSegments.push(
          `${currentLineSegment.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`).join(' ')} L ${last.x.toFixed(1)} ${bottomY} L ${first.x.toFixed(1)} ${bottomY} Z`
        );
      }
      currentLineSegment = [];
    }
  });

  if (currentLineSegment.length > 1) {
    lineSegments.push(
      currentLineSegment.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`).join(' ')
    );
    const first = currentLineSegment[0];
    const last = currentLineSegment[currentLineSegment.length - 1];
    const bottomY = paddingTop + chartHeight;
    areaSegments.push(
      `${currentLineSegment.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`).join(' ')} L ${last.x.toFixed(1)} ${bottomY} L ${first.x.toFixed(1)} ${bottomY} Z`
    );
  }

  const activeItem = hoveredIndex !== null ? data[hoveredIndex] : null;

  return (
    <div data-testid="attendance-trend-chart" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
      {/* 7-Day Performance Banner Strip */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: '10px',
        }}
      >
        <div
          style={{
            padding: '12px 14px',
            backgroundColor: 'var(--color-bg-page)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border)',
          }}
        >
          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 500 }}>
            7d Average Rate
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '4px' }}>
            <span
              style={{
                fontSize: '1.35rem',
                fontWeight: 700,
                color:
                  avgAttendance === null
                    ? 'var(--color-text-muted)'
                    : avgAttendance >= 90
                    ? 'var(--color-status-success)'
                    : avgAttendance >= 75
                    ? 'var(--color-status-warning)'
                    : 'var(--color-status-danger)',
              }}
            >
              {avgAttendance !== null ? `${avgAttendance.toFixed(1)}%` : 'N/A'}
            </span>
            <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
              ({workingDays.length} working days)
            </span>
          </div>
        </div>

        <div
          style={{
            padding: '12px 14px',
            backgroundColor: 'var(--color-bg-page)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border)',
          }}
        >
          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 500 }}>
            Total Present & Half-Day
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '4px' }}>
            <span style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
              {totalPresentInPeriod + totalHalfDayInPeriod}
            </span>
            <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
              ({totalHalfDayInPeriod} half-day)
            </span>
          </div>
        </div>

        <div
          style={{
            padding: '12px 14px',
            backgroundColor: 'var(--color-bg-page)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border)',
          }}
        >
          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 500 }}>
            Scheduled Leave Days
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '4px' }}>
            <span style={{ fontSize: '1.35rem', fontWeight: 700, color: '#7c3aed' }}>
              {totalLeaveInPeriod}
            </span>
            <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>approved</span>
          </div>
        </div>

        <div
          style={{
            padding: '12px 14px',
            backgroundColor: 'var(--color-bg-page)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border)',
          }}
        >
          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 500 }}>
            Remote WFH Overlay
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '4px' }}>
            <span style={{ fontSize: '1.35rem', fontWeight: 700, color: '#0284c7' }}>
              {totalWfhInPeriod}
            </span>
            <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>instances</span>
          </div>
        </div>
      </div>

      {/* SVG Trend Visualization Container */}
      <div
        style={{
          position: 'relative',
          backgroundColor: 'var(--color-bg-card)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--color-border)',
          padding: '14px 8px 8px 8px',
          overflow: 'hidden',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 12px 8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={15} style={{ color: 'var(--color-primary)' }} />
            <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-main)' }}>
              Net Scheduled Attendance Trajectory
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: 10, height: 3, backgroundColor: 'var(--color-primary)', borderRadius: 2 }} />
              Scheduled Attendance %
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: 12, height: 12, backgroundColor: 'rgba(100, 116, 139, 0.1)', border: '1px dashed #cbd5e1', borderRadius: 2 }} />
              Weekend / Off-Day
            </span>
          </div>
        </div>

        {/* Responsive SVG Chart */}
        <div style={{ width: '100%', overflowX: 'auto' }}>
          <svg
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            style={{ width: '100%', minWidth: '540px', height: 'auto', display: 'block' }}
          >
            <defs>
              <linearGradient id="attendanceGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-primary)" stopOpacity="0.25" />
                <stop offset="100%" stopColor="var(--color-primary)" stopOpacity="0.01" />
              </linearGradient>
            </defs>

            {/* Y-Axis Grid Lines & Labels */}
            {[0, 25, 50, 75, 100].map((val) => {
              const y = getY(val);
              return (
                <g key={`y-grid-${val}`}>
                  <line
                    x1={paddingLeft}
                    y1={y}
                    x2={svgWidth - paddingRight}
                    y2={y}
                    stroke="var(--color-border-subtle)"
                    strokeWidth="1"
                    strokeDasharray={val === 0 || val === 100 ? undefined : '3 3'}
                  />
                  <text
                    x={paddingLeft - 8}
                    y={y + 3}
                    textAnchor="end"
                    fontSize="10"
                    fill="var(--color-text-muted)"
                  >
                    {val}%
                  </text>
                </g>
              );
            })}

            {/* Non-Working Day Background Shading & Column Bands */}
            {data.map((item, idx) => {
              if (item.is_working_day && item.attendance_percentage !== null) return null;
              const colWidth = stepX * 0.85;
              const x = getX(idx) - colWidth / 2;
              return (
                <g key={`non-working-${item.date}`}>
                  <rect
                    x={x}
                    y={paddingTop}
                    width={colWidth}
                    height={chartHeight}
                    fill="rgba(100, 116, 139, 0.06)"
                    stroke="#cbd5e1"
                    strokeWidth="1"
                    strokeDasharray="4 3"
                    rx="4"
                  />
                  <text
                    x={getX(idx)}
                    y={paddingTop + chartHeight / 2 - 8}
                    textAnchor="middle"
                    fontSize="11"
                    fontWeight="600"
                    fill="#94a3b8"
                  >
                    OFF
                  </text>
                  <text
                    x={getX(idx)}
                    y={paddingTop + chartHeight / 2 + 8}
                    textAnchor="middle"
                    fontSize="9"
                    fill="#94a3b8"
                  >
                    {item.day_name.slice(0, 3)}
                  </text>
                </g>
              );
            })}

            {/* Gradient Fill Areas under working-day line */}
            {areaSegments.map((d, i) => (
              <path key={`area-${i}`} d={d} fill="url(#attendanceGradient)" />
            ))}

            {/* Working-Day Trend Lines */}
            {lineSegments.map((d, i) => (
              <path
                key={`line-${i}`}
                d={d}
                fill="none"
                stroke="var(--color-primary)"
                strokeWidth="2.75"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            ))}

            {/* Interactive Day Node Points & Click/Hover Triggers */}
            {data.map((item, idx) => {
              const x = getX(idx);
              const isWorking = item.is_working_day && item.attendance_percentage !== null;
              const y = isWorking ? getY(item.attendance_percentage!) : paddingTop + chartHeight / 2;
              const isHovered = hoveredIndex === idx;

              return (
                <g
                  key={`point-group-${item.date}`}
                  onClick={() => setHoveredIndex(hoveredIndex === idx ? null : idx)}
                  onMouseEnter={() => setHoveredIndex(idx)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  style={{ cursor: 'pointer' }}
                  data-testid={`attendance-day-${item.date}`}
                >
                  {/* Invisible Hitbox for easier cursor interaction */}
                  <rect
                    x={x - stepX / 2}
                    y={paddingTop}
                    width={stepX}
                    height={chartHeight + paddingBottom}
                    fill="transparent"
                  />

                  {/* Vertical cursor guide line when hovered */}
                  {isHovered && (
                    <line
                      x1={x}
                      y1={paddingTop}
                      x2={x}
                      y2={paddingTop + chartHeight}
                      stroke="var(--color-primary)"
                      strokeWidth="1"
                      strokeDasharray="2 2"
                      opacity="0.6"
                    />
                  )}

                  {isWorking ? (
                    <>
                      {/* Outer Glow Halo when hovered */}
                      {isHovered && (
                        <circle
                          cx={x}
                          cy={y}
                          r="9"
                          fill="var(--color-primary)"
                          opacity="0.2"
                        />
                      )}
                      <circle
                        cx={x}
                        cy={y}
                        r={isHovered ? 6 : 4.5}
                        fill="white"
                        stroke={
                          item.attendance_percentage! >= 90
                            ? 'var(--color-status-success)'
                            : item.attendance_percentage! >= 75
                            ? 'var(--color-status-warning)'
                            : 'var(--color-status-danger)'
                        }
                        strokeWidth="2.5"
                      />
                      {/* On-node value badge */}
                      <text
                        x={x}
                        y={y - 10}
                        textAnchor="middle"
                        fontSize="10"
                        fontWeight="700"
                        fill="var(--color-text-main)"
                      >
                        {item.attendance_percentage!.toFixed(0)}%
                      </text>
                    </>
                  ) : (
                    <circle
                      cx={x}
                      cy={paddingTop + chartHeight - 8}
                      r="3.5"
                      fill="#94a3b8"
                      stroke="white"
                      strokeWidth="1.5"
                    />
                  )}

                  {/* X-Axis Date & Day Labels */}
                  <text
                    x={x}
                    y={svgHeight - paddingBottom + 16}
                    textAnchor="middle"
                    fontSize="11"
                    fontWeight={isHovered ? '700' : '500'}
                    fill={isHovered ? 'var(--color-primary)' : isWorking ? 'var(--color-text-main)' : 'var(--color-text-muted)'}
                  >
                    {item.day_name.slice(0, 3)}
                  </text>
                  <text
                    x={x}
                    y={svgHeight - paddingBottom + 28}
                    textAnchor="middle"
                    fontSize="9.5"
                    fill="var(--color-text-muted)"
                  >
                    {item.date.slice(5)}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* Interactive Detail Card for Hovered or Selected Day */}
      {activeItem && (
        <div
          data-testid="attendance-day-detail"
          style={{
            padding: '14px 16px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--color-bg-page)',
            border: '1px solid var(--color-border)',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            animation: 'fadeIn 0.2s ease',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Calendar size={16} style={{ color: 'var(--color-primary)' }} />
              <span style={{ fontWeight: 700, color: 'var(--color-text-main)', fontSize: 'var(--font-size-sm)' }}>
                {activeItem.day_name}, {activeItem.date}
              </span>
              <span
                style={{
                  fontSize: 'var(--font-size-xs)',
                  padding: '2px 8px',
                  borderRadius: 'var(--radius-full)',
                  fontWeight: 600,
                  backgroundColor: activeItem.is_working_day ? 'var(--color-status-success-bg)' : 'rgba(100, 116, 139, 0.1)',
                  color: activeItem.is_working_day ? 'var(--color-status-success)' : 'var(--color-text-muted)',
                }}
              >
                {activeItem.is_working_day ? 'Working Day' : 'Non-Working / Weekend'}
              </span>
            </div>

            {activeItem.is_working_day && activeItem.attendance_percentage !== null ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                  Scheduled Attendance:
                </span>
                <span
                  style={{
                    fontSize: 'var(--font-size-base)',
                    fontWeight: 700,
                    color:
                      activeItem.attendance_percentage >= 90
                        ? 'var(--color-status-success)'
                        : activeItem.attendance_percentage >= 75
                        ? 'var(--color-status-warning)'
                        : 'var(--color-status-danger)',
                  }}
                >
                  {activeItem.attendance_percentage.toFixed(1)}%
                </span>
              </div>
            ) : (
              <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontStyle: 'italic' }}>
                Non-working day (attendance rate not scheduled)
              </span>
            )}
          </div>

          {/* Breakdown Pills */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: '8px' }}>
            <div style={{ padding: '8px 10px', backgroundColor: 'var(--color-bg-card)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border-subtle)' }}>
              <div style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>Active Workforce</div>
              <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-main)' }}>{activeItem.expected_total}</div>
            </div>

            <div style={{ padding: '8px 10px', backgroundColor: 'var(--color-bg-card)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border-subtle)' }}>
              <div style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>Scheduled Working</div>
              <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-main)' }}>{activeItem.expected_working}</div>
            </div>

            <div style={{ padding: '8px 10px', backgroundColor: 'var(--color-status-success-bg)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-status-success-border)' }}>
              <div style={{ fontSize: '10px', color: 'var(--color-status-success)' }}>Present</div>
              <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 700, color: 'var(--color-status-success)' }}>{activeItem.present}</div>
            </div>

            <div style={{ padding: '8px 10px', backgroundColor: 'var(--color-status-warning-bg)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-status-warning-border)' }}>
              <div style={{ fontSize: '10px', color: 'var(--color-status-warning)' }}>Half-Day</div>
              <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 700, color: 'var(--color-status-warning)' }}>{activeItem.half_day}</div>
            </div>

            <div style={{ padding: '8px 10px', backgroundColor: 'var(--color-status-pending-bg)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-status-pending-border)' }}>
              <div style={{ fontSize: '10px', color: '#7c3aed' }}>On Leave</div>
              <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 700, color: '#7c3aed' }}>{activeItem.on_leave}</div>
            </div>

            <div style={{ padding: '8px 10px', backgroundColor: 'var(--color-status-danger-bg)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-status-danger-border)' }}>
              <div style={{ fontSize: '10px', color: 'var(--color-status-danger)' }}>Absent</div>
              <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 700, color: 'var(--color-status-danger)' }}>{activeItem.absent}</div>
            </div>

            <div style={{ padding: '8px 10px', backgroundColor: 'var(--color-status-info-bg)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-status-info-border)' }}>
              <div style={{ fontSize: '10px', color: '#0284c7' }}>WFH (Overlay)</div>
              <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 700, color: '#0284c7' }}>{activeItem.on_wfh}</div>
            </div>
          </div>
        </div>
      )}

      {/* Day-by-Day Scannable Bar Strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '6px' }}>
        {data.map((item, idx) => {
          const isWorking = item.is_working_day && item.attendance_percentage !== null;
          const isSelected = hoveredIndex === idx;

          return (
            <div
              key={`day-card-${item.date}`}
              onClick={() => setHoveredIndex(hoveredIndex === idx ? null : idx)}
              style={{
                padding: '8px 6px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: isSelected ? 'var(--color-primary-light)' : 'var(--color-bg-page)',
                border: isSelected ? '1px solid var(--color-primary)' : '1px solid var(--color-border)',
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.15s ease',
              }}
            >
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-main)' }}>
                {item.day_name.slice(0, 3)}
              </div>
              <div style={{ fontSize: '9px', color: 'var(--color-text-muted)' }}>
                {item.date.slice(8)}
              </div>

              {isWorking ? (
                <div
                  style={{
                    marginTop: '4px',
                    fontSize: '11px',
                    fontWeight: 700,
                    color:
                      item.attendance_percentage! >= 90
                        ? 'var(--color-status-success)'
                        : item.attendance_percentage! >= 75
                        ? 'var(--color-status-warning)'
                        : 'var(--color-status-danger)',
                  }}
                >
                  {item.attendance_percentage!.toFixed(0)}%
                </div>
              ) : (
                <div
                  style={{
                    marginTop: '4px',
                    fontSize: '10px',
                    fontWeight: 600,
                    color: '#94a3b8',
                  }}
                >
                  OFF
                </div>
              )}

              {/* Mini Status Breakdown Bar */}
              <div
                style={{
                  height: '4px',
                  borderRadius: '2px',
                  backgroundColor: isWorking ? 'var(--color-border)' : 'transparent',
                  marginTop: '5px',
                  overflow: 'hidden',
                  display: 'flex',
                }}
              >
                {isWorking && item.expected_total > 0 && (
                  <>
                    <div style={{ width: `${(item.present / item.expected_total) * 100}%`, backgroundColor: 'var(--color-status-success)' }} />
                    <div style={{ width: `${(item.half_day / item.expected_total) * 100}%`, backgroundColor: 'var(--color-status-warning)' }} />
                    <div style={{ width: `${(item.on_leave / item.expected_total) * 100}%`, backgroundColor: '#7c3aed' }} />
                    <div style={{ width: `${(item.absent / item.expected_total) * 100}%`, backgroundColor: 'var(--color-status-danger)' }} />
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
