import React, { useState } from 'react';
import {
  Users,
  TrendingUp,
  Calendar,
} from 'lucide-react';

import { type WorkforceTrendItem } from '../../services/dashboard';

interface WorkforceTrendChartProps {
  data: WorkforceTrendItem[];
}

export const WorkforceTrendChart: React.FC<WorkforceTrendChartProps> = ({ data }) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  if (!data || data.length === 0) {
    return (
      <div
        data-testid="workforce-trend-empty"
        style={{
          padding: '40px 20px',
          textAlign: 'center',
          color: 'var(--color-text-muted)',
          backgroundColor: 'var(--color-bg-page)',
          borderRadius: 'var(--radius-md)',
          border: '1px dashed var(--color-border)',
        }}
      >
        <Users size={32} style={{ margin: '0 auto 10px', opacity: 0.5 }} />
        <p style={{ margin: 0, fontWeight: 500 }}>No workforce trend data available for this period.</p>
      </div>
    );
  }

  // Calculate 6-month aggregate metrics
  const firstMonth = data[0];
  const lastMonth = data[data.length - 1];
  const startHeadcount = firstMonth.start_headcount;
  const currentHeadcount = lastMonth.end_headcount;
  const totalNetGrowth = currentHeadcount - startHeadcount;

  const totalHires = data.reduce((acc, m) => acc + m.new_hires, 0);
  const totalExits = data.reduce((acc, m) => acc + m.exits, 0);
  const avgTurnover =
    data.reduce((acc, m) => acc + m.turnover_rate, 0) / (data.length || 1);

  // SVG Chart Layout & Dimensions
  const svgWidth = 720;
  const svgHeight = 220;
  const paddingLeft = 50;
  const paddingRight = 35;
  const paddingTop = 30;
  const paddingBottom = 40;
  const chartWidth = svgWidth - paddingLeft - paddingRight;
  const chartHeight = svgHeight - paddingTop - paddingBottom;

  // Compute Headcount scale bounds
  const allHeadcounts = data.flatMap((d) => [d.start_headcount, d.end_headcount]);
  const minHeadcount = Math.max(0, Math.min(...allHeadcounts) - 5);
  const maxHeadcount = Math.max(...allHeadcounts) + 5 || 10;
  const headcountRange = maxHeadcount - minHeadcount || 1;

  const stepX = data.length > 1 ? chartWidth / (data.length - 1) : chartWidth;
  const getX = (index: number) => paddingLeft + index * stepX;
  const getY = (val: number) => {
    const clamped = Math.max(minHeadcount, Math.min(maxHeadcount, val));
    return paddingTop + chartHeight - ((clamped - minHeadcount) / headcountRange) * chartHeight;
  };

  // Build SVG Path for End Headcount trajectory
  const pathPoints = data.map((d, i) => ({ x: getX(i), y: getY(d.end_headcount) }));
  const linePath = pathPoints
    .map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`)
    .join(' ');
  const areaPath = `${linePath} L ${pathPoints[pathPoints.length - 1].x.toFixed(1)} ${(paddingTop + chartHeight).toFixed(1)} L ${pathPoints[0].x.toFixed(1)} ${(paddingTop + chartHeight).toFixed(1)} Z`;

  const activeMonth = hoveredIndex !== null ? data[hoveredIndex] : null;

  return (
    <div data-testid="workforce-trend-chart" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
      {/* 6-Month Macro KPI Strip */}
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
            6m Headcount Trajectory
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '4px' }}>
            <span style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
              {currentHeadcount}
            </span>
            <span
              style={{
                fontSize: 'var(--font-size-xs)',
                fontWeight: 600,
                color: totalNetGrowth >= 0 ? 'var(--color-status-success)' : 'var(--color-status-danger)',
              }}
            >
              {totalNetGrowth >= 0 ? `+${totalNetGrowth}` : totalNetGrowth} net ({startHeadcount} start)
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
            Total New Hires
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '4px' }}>
            <span style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--color-status-success)' }}>
              +{totalHires}
            </span>
            <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
              onboarded
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
            Total Exits
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '4px' }}>
            <span style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--color-status-danger)' }}>
              -{totalExits}
            </span>
            <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
              departed
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
            Avg Monthly Turnover
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '4px' }}>
            <span
              style={{
                fontSize: '1.35rem',
                fontWeight: 700,
                color:
                  avgTurnover <= 2.5
                    ? 'var(--color-status-success)'
                    : avgTurnover <= 5.0
                    ? 'var(--color-status-warning)'
                    : 'var(--color-status-danger)',
              }}
            >
              {avgTurnover.toFixed(1)}%
            </span>
            <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
              per month
            </span>
          </div>
        </div>
      </div>

      {/* Responsive SVG Chart Container */}
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
            <TrendingUp size={15} style={{ color: 'var(--color-secondary)' }} />
            <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-main)' }}>
              6-Month Active Headcount & Talent Flow
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: 10, height: 3, backgroundColor: 'var(--color-secondary)', borderRadius: 2 }} />
              End Headcount
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: 8, height: 8, backgroundColor: 'var(--color-status-success)', borderRadius: 2 }} />
              Hires
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: 8, height: 8, backgroundColor: 'var(--color-status-danger)', borderRadius: 2 }} />
              Exits
            </span>
          </div>
        </div>

        {/* SVG Drawing */}
        <div style={{ width: '100%', overflowX: 'auto' }}>
          <svg
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            style={{ width: '100%', minWidth: '540px', height: 'auto', display: 'block' }}
          >
            <defs>
              <linearGradient id="workforceGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-secondary)" stopOpacity="0.28" />
                <stop offset="100%" stopColor="var(--color-secondary)" stopOpacity="0.02" />
              </linearGradient>
            </defs>

            {/* Horizontal Grid Lines */}
            {[0, 0.25, 0.5, 0.75, 1].map((ratio, i) => {
              const val = Math.round(minHeadcount + ratio * headcountRange);
              const y = getY(val);
              return (
                <g key={`y-grid-wf-${i}`}>
                  <line
                    x1={paddingLeft}
                    y1={y}
                    x2={svgWidth - paddingRight}
                    y2={y}
                    stroke="var(--color-border-subtle)"
                    strokeWidth="1"
                    strokeDasharray={i === 0 || i === 4 ? undefined : '3 3'}
                  />
                  <text
                    x={paddingLeft - 8}
                    y={y + 3}
                    textAnchor="end"
                    fontSize="10"
                    fill="var(--color-text-muted)"
                  >
                    {val}
                  </text>
                </g>
              );
            })}

            {/* Area Fill */}
            <path d={areaPath} fill="url(#workforceGradient)" />

            {/* Headcount Trajectory Line */}
            <path
              d={linePath}
              fill="none"
              stroke="var(--color-secondary)"
              strokeWidth="2.75"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {/* Inflow/Outflow Column Bars for each month */}
            {data.map((m, idx) => {
              const x = getX(idx);
              const maxH = 36;
              const maxMovement = Math.max(1, ...data.map((d) => Math.max(d.new_hires, d.exits)));
              const hireHeight = (m.new_hires / maxMovement) * maxH;
              const exitHeight = (m.exits / maxMovement) * maxH;
              const barYBase = paddingTop + chartHeight;

              return (
                <g key={`bars-group-${m.period}`}>
                  {/* New Hires Bar */}
                  {m.new_hires > 0 && (
                    <rect
                      x={x - 9}
                      y={barYBase - hireHeight}
                      width="7"
                      height={hireHeight}
                      fill="var(--color-status-success)"
                      rx="2"
                      opacity="0.85"
                    />
                  )}
                  {/* Exits Bar */}
                  {m.exits > 0 && (
                    <rect
                      x={x + 2}
                      y={barYBase - exitHeight}
                      width="7"
                      height={exitHeight}
                      fill="var(--color-status-danger)"
                      rx="2"
                      opacity="0.85"
                    />
                  )}
                </g>
              );
            })}

            {/* Node Points & Interaction Hitboxes */}
            {data.map((m, idx) => {
              const x = getX(idx);
              const y = getY(m.end_headcount);
              const isHovered = hoveredIndex === idx;

              return (
                <g
                  key={`wf-point-${m.period}`}
                  onClick={() => setHoveredIndex(hoveredIndex === idx ? null : idx)}
                  onMouseEnter={() => setHoveredIndex(idx)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  style={{ cursor: 'pointer' }}
                  data-testid={`workforce-month-${m.period}`}
                >
                  {/* Hitbox */}
                  <rect
                    x={x - stepX / 2}
                    y={paddingTop}
                    width={stepX}
                    height={chartHeight + paddingBottom}
                    fill="transparent"
                  />

                  {/* Vertical Guide Line */}
                  {isHovered && (
                    <line
                      x1={x}
                      y1={paddingTop}
                      x2={x}
                      y2={paddingTop + chartHeight}
                      stroke="var(--color-secondary)"
                      strokeWidth="1"
                      strokeDasharray="2 2"
                      opacity="0.6"
                    />
                  )}

                  {/* Outer Glow Halo */}
                  {isHovered && (
                    <circle
                      cx={x}
                      cy={y}
                      r="9"
                      fill="var(--color-secondary)"
                      opacity="0.2"
                    />
                  )}

                  {/* Circular Data Node */}
                  <circle
                    cx={x}
                    cy={y}
                    r={isHovered ? 6 : 4.5}
                    fill="white"
                    stroke="var(--color-secondary)"
                    strokeWidth="2.5"
                  />

                  {/* Value Above Node */}
                  <text
                    x={x}
                    y={y - 9}
                    textAnchor="middle"
                    fontSize="10.5"
                    fontWeight="700"
                    fill="var(--color-text-main)"
                  >
                    {m.end_headcount}
                  </text>

                  {/* X-Axis Month & Period Labels */}
                  <text
                    x={x}
                    y={svgHeight - paddingBottom + 16}
                    textAnchor="middle"
                    fontSize="11"
                    fontWeight={isHovered ? '700' : '500'}
                    fill={isHovered ? 'var(--color-secondary)' : 'var(--color-text-main)'}
                  >
                    {m.month_name.slice(0, 3)}
                  </text>
                  <text
                    x={x}
                    y={svgHeight - paddingBottom + 28}
                    textAnchor="middle"
                    fontSize="9.5"
                    fill="var(--color-text-muted)"
                  >
                    {m.year}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* Interactive Detail Card for Hovered or Selected Month */}
      {activeMonth && (
        <div
          data-testid="workforce-month-detail"
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
              <Calendar size={16} style={{ color: 'var(--color-secondary)' }} />
              <span style={{ fontWeight: 700, color: 'var(--color-text-main)', fontSize: 'var(--font-size-sm)' }}>
                {activeMonth.month_name} {activeMonth.year} ({activeMonth.period})
              </span>
              <span
                style={{
                  fontSize: 'var(--font-size-xs)',
                  padding: '2px 8px',
                  borderRadius: 'var(--radius-full)',
                  fontWeight: 600,
                  backgroundColor:
                    activeMonth.net_growth >= 0 ? 'var(--color-status-success-bg)' : 'var(--color-status-danger-bg)',
                  color:
                    activeMonth.net_growth >= 0 ? 'var(--color-status-success)' : 'var(--color-status-danger)',
                }}
              >
                Net Growth: {activeMonth.net_growth >= 0 ? `+${activeMonth.net_growth}` : activeMonth.net_growth}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>Turnover Rate:</span>
              <span
                style={{
                  fontSize: 'var(--font-size-sm)',
                  fontWeight: 700,
                  color:
                    activeMonth.turnover_rate <= 2.5
                      ? 'var(--color-status-success)'
                      : activeMonth.turnover_rate <= 5.0
                      ? 'var(--color-status-warning)'
                      : 'var(--color-status-danger)',
                }}
              >
                {activeMonth.turnover_rate.toFixed(1)}%
              </span>
            </div>
          </div>

          {/* Breakdown Pills */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: '8px' }}>
            <div style={{ padding: '8px 10px', backgroundColor: 'var(--color-bg-card)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border-subtle)' }}>
              <div style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>Start Headcount</div>
              <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-main)' }}>{activeMonth.start_headcount}</div>
            </div>

            <div style={{ padding: '8px 10px', backgroundColor: 'var(--color-bg-card)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border-subtle)' }}>
              <div style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>End Headcount</div>
              <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 700, color: 'var(--color-text-main)' }}>{activeMonth.end_headcount}</div>
            </div>

            <div style={{ padding: '8px 10px', backgroundColor: 'var(--color-status-success-bg)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-status-success-border)' }}>
              <div style={{ fontSize: '10px', color: 'var(--color-status-success)' }}>New Hires</div>
              <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 700, color: 'var(--color-status-success)' }}>+{activeMonth.new_hires}</div>
            </div>

            <div style={{ padding: '8px 10px', backgroundColor: 'var(--color-status-danger-bg)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-status-danger-border)' }}>
              <div style={{ fontSize: '10px', color: 'var(--color-status-danger)' }}>Exits</div>
              <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 700, color: 'var(--color-status-danger)' }}>-{activeMonth.exits}</div>
            </div>

            <div style={{ padding: '8px 10px', backgroundColor: 'var(--color-status-info-bg)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-status-info-border)' }}>
              <div style={{ fontSize: '10px', color: '#0284c7' }}>Average Headcount</div>
              <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: '#0284c7' }}>
                {((activeMonth.start_headcount + activeMonth.end_headcount) / 2).toFixed(1)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Month-by-Month Flow Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '6px' }}>
        {data.map((m, idx) => {
          const isSelected = hoveredIndex === idx;

          return (
            <div
              key={`month-card-${m.period}`}
              onClick={() => setHoveredIndex(hoveredIndex === idx ? null : idx)}
              style={{
                padding: '8px 6px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: isSelected ? 'var(--color-secondary-light)' : 'var(--color-bg-page)',
                border: isSelected ? '1px solid var(--color-secondary)' : '1px solid var(--color-border)',
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.15s ease',
              }}
            >
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-main)' }}>
                {m.month_name.slice(0, 3)}
              </div>
              <div style={{ fontSize: '9px', color: 'var(--color-text-muted)' }}>
                {m.year}
              </div>

              <div style={{ marginTop: '4px', fontSize: '12px', fontWeight: 700, color: 'var(--color-text-main)' }}>
                {m.end_headcount}
              </div>

              <div style={{ display: 'flex', justifyContent: 'center', gap: '4px', marginTop: '2px', fontSize: '9.5px', fontWeight: 600 }}>
                <span style={{ color: 'var(--color-status-success)' }}>+{m.new_hires}</span>
                <span style={{ color: 'var(--color-status-danger)' }}>-{m.exits}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
