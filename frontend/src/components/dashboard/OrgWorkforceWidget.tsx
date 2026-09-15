import React from 'react';
import { Users, UserPlus, AlertCircle, ChevronRight, Building, MapPin } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../Card';
import { type OrganizationWorkforce } from '../../services/dashboard';

interface OrgWorkforceWidgetProps {
  workforce: OrganizationWorkforce;
}

export const OrgWorkforceWidget: React.FC<OrgWorkforceWidgetProps> = ({ workforce }) => {
  const navigate = useNavigate();
  const totalActive = workforce.total_active || 1;

  const getDaysAgo = (dateStr: string | null) => {
    if (!dateStr) return null;
    const diff = Math.floor((new Date().getTime() - new Date(dateStr).getTime()) / (1000 * 60 * 60 * 24));
    if (diff <= 0) return 'Joined today';
    if (diff === 1) return 'Joined yesterday';
    return `Joined ${diff}d ago`;
  };

  return (
    <Card
      title="Workforce Analytics & Capacity"
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
          }}
        >
          {workforce.total_active} Total Active
        </span>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
        {/* Executive Employment Status Summary */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '10px',
          }}
        >
          <div
            style={{
              padding: '12px 14px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--color-bg-page)',
              border: '1px solid var(--color-border)',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
            }}
          >
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(112, 38, 227, 0.1)',
                color: 'var(--color-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <Users size={18} />
            </div>
            <div>
              <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-text-main)', lineHeight: 1.1 }}>
                {workforce.total_active}
              </div>
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                Active Staff
              </div>
            </div>
          </div>

          <div
            style={{
              padding: '12px 14px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--color-bg-page)',
              border: '1px solid var(--color-border)',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
            }}
          >
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(14, 165, 233, 0.1)',
                color: 'var(--color-secondary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <UserPlus size={18} />
            </div>
            <div>
              <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-text-main)', lineHeight: 1.1 }}>
                {workforce.total_onboarding}
              </div>
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                Onboarding
              </div>
            </div>
          </div>

          <div
            style={{
              padding: '12px 14px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--color-bg-page)',
              border: '1px solid var(--color-border)',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
            }}
          >
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(217, 119, 6, 0.1)',
                color: 'var(--color-status-warning)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <AlertCircle size={18} />
            </div>
            <div>
              <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-text-main)', lineHeight: 1.1 }}>
                {workforce.total_on_notice}
              </div>
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                On Notice
              </div>
            </div>
          </div>
        </div>

        {/* Department Distribution Chart */}
        {workforce.by_department.length > 0 && (
          <div
            style={{
              padding: '14px 16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--color-bg-page)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '12px',
              }}
            >
              <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-main)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Building size={14} color="var(--color-primary)" /> Department Allocation
              </span>
              <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                {workforce.by_department.length} Departments
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {workforce.by_department.map((dept) => {
                const pct = Math.min(100, Math.round((dept.count / totalActive) * 100));
                return (
                  <div key={dept.name} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 'var(--font-size-xs)' }}>
                      <span style={{ fontWeight: 500, color: 'var(--color-text-main)' }}>{dept.name}</span>
                      <span style={{ color: 'var(--color-text-muted)', fontWeight: 600 }}>
                        {dept.count} <span style={{ fontWeight: 400, color: 'var(--color-text-muted)' }}>({pct}%)</span>
                      </span>
                    </div>
                    <div
                      style={{
                        height: '6px',
                        backgroundColor: 'var(--color-border)',
                        borderRadius: 'var(--radius-full)',
                        overflow: 'hidden',
                      }}
                    >
                      <div
                        style={{
                          height: '100%',
                          width: `${pct}%`,
                          background: 'linear-gradient(90deg, var(--color-primary) 0%, #0ea5e9 100%)',
                          borderRadius: 'var(--radius-full)',
                          transition: 'width 0.4s ease',
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Branch Distribution Chips */}
        {workforce.by_branch.length > 0 && (
          <div>
            <div
              style={{
                fontSize: 'var(--font-size-xs)',
                fontWeight: 600,
                color: 'var(--color-text-sub)',
                marginBottom: '8px',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              <MapPin size={13} /> Branch Presence
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {workforce.by_branch.map((b) => {
                const bPct = Math.round((b.count / totalActive) * 100);
                return (
                  <div
                    key={b.name}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--color-bg-page)',
                      border: '1px solid var(--color-border)',
                      fontSize: 'var(--font-size-xs)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                    }}
                  >
                    <span style={{ fontWeight: 500, color: 'var(--color-text-main)' }}>{b.name}</span>
                    <span
                      style={{
                        padding: '1px 6px',
                        borderRadius: 'var(--radius-full)',
                        backgroundColor: 'var(--color-bg-subtle)',
                        color: 'var(--color-primary)',
                        fontWeight: 700,
                      }}
                    >
                      {b.count} ({bPct}%)
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Recent Hires Spotlight */}
        {workforce.recent_hires.length > 0 && (
          <div>
            <div
              style={{
                fontSize: 'var(--font-size-xs)',
                fontWeight: 600,
                color: 'var(--color-text-sub)',
                marginBottom: '8px',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              Recent Joiners
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {workforce.recent_hires.map((emp) => {
                const initials = emp.name
                  .split(' ')
                  .map((n) => n[0])
                  .filter(Boolean)
                  .slice(0, 2)
                  .join('')
                  .toUpperCase() || 'E';

                const daysAgoText = getDaysAgo(emp.joining_date);

                return (
                  <div
                    key={emp.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '8px 10px',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--color-border-subtle)',
                      backgroundColor: 'var(--color-bg-page)',
                      cursor: 'pointer',
                      transition: 'border-color 0.15s ease',
                    }}
                    onClick={() => navigate(`/admin/employees/${emp.id}`)}
                  >
                    <div
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: '50%',
                        background: 'linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%)',
                        color: 'var(--color-primary)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 700,
                        fontSize: 'var(--font-size-xs)',
                        flexShrink: 0,
                      }}
                    >
                      {initials}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p
                        style={{
                          margin: 0,
                          fontWeight: 600,
                          fontSize: 'var(--font-size-xs)',
                          color: 'var(--color-text-main)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {emp.name}
                      </p>
                      <p
                        style={{
                          margin: 0,
                          fontSize: '0.7rem',
                          color: 'var(--color-text-muted)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {emp.designation || 'No Designation'} · {emp.department || 'General'}
                      </p>
                    </div>
                    {daysAgoText && (
                      <span
                        style={{
                          fontSize: '0.7rem',
                          color: 'var(--color-text-muted)',
                          backgroundColor: 'var(--color-bg-subtle)',
                          padding: '2px 6px',
                          borderRadius: 'var(--radius-xs)',
                        }}
                      >
                        {daysAgoText}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <button
          className="btn btn-ghost"
          onClick={() => navigate('/admin/employees')}
          style={{ width: '100%', fontSize: 'var(--font-size-xs)', paddingTop: 6, paddingBottom: 6 }}
          type="button"
        >
          View All Employees Directory <ChevronRight size={13} />
        </button>
      </div>
    </Card>
  );
};
