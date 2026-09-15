import React from 'react';
import { Calendar, Laptop, Receipt, Users, ShieldAlert, Clock, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../Card';

interface QuickActionsWidgetProps {
  hasTeam?: boolean;
  hasOrg?: boolean;
}

export const QuickActionsWidget: React.FC<QuickActionsWidgetProps> = ({
  hasTeam = false,
  hasOrg = false,
}) => {
  const navigate = useNavigate();

  const routineActions = [
    {
      title: 'Attendance Log',
      description: 'View punch times & breaks',
      icon: Clock,
      color: '#d97706',
      bg: '#fffbeb',
      onClick: () => navigate('/attendance'),
    },
    {
      title: 'Apply Leave',
      description: 'Submit time off or sick leave',
      icon: Calendar,
      color: 'var(--color-primary)',
      bg: 'var(--color-primary-light)',
      onClick: () => navigate('/leaves'),
    },
    {
      title: 'Request WFH',
      description: 'Submit remote work request',
      icon: Laptop,
      color: '#0284c7',
      bg: '#f0f9ff',
      onClick: () => navigate('/leaves'),
    },
    {
      title: 'My Payslips',
      description: 'View monthly pay statements',
      icon: Receipt,
      color: '#059669',
      bg: '#ecfdf5',
      onClick: () => navigate('/payslips'),
    },
  ];

  const elevatedActions = [];
  if (hasTeam) {
    elevatedActions.push({
      title: 'Team Approvals',
      description: 'Review direct report requests',
      icon: Users,
      color: '#7c3aed',
      bg: '#f5f3ff',
      onClick: () => navigate('/leaves'),
    });
  }

  if (hasOrg) {
    elevatedActions.push({
      title: 'Staff Directory',
      description: 'Browse all company employees',
      icon: Users,
      color: '#2563eb',
      bg: '#eff6ff',
      onClick: () => navigate('/admin/employees'),
    });
    elevatedActions.push({
      title: 'Security Audit',
      description: 'Review system activity log',
      icon: ShieldAlert,
      color: '#dc2626',
      bg: '#fef2f2',
      onClick: () => navigate('/admin/audit-logs'),
    });
  }

  return (
    <Card title="Quick Actions">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {/* Core Actions */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '8px' }}>
          {routineActions.map((action) => {
            const Icon = action.icon;
            return (
              <div
                key={action.title}
                onClick={action.onClick}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--color-bg-page)',
                  border: '1px solid var(--color-border)',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-1px)';
                  e.currentTarget.style.borderColor = 'var(--color-border-strong)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'none';
                  e.currentTarget.style.borderColor = 'var(--color-border)';
                }}
              >
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: action.bg,
                    color: action.color,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  <Icon size={16} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 'var(--font-size-xs)', fontWeight: 600, color: 'var(--color-text-main)' }}>
                    {action.title}
                  </div>
                  <div
                    style={{
                      fontSize: '0.68rem',
                      color: 'var(--color-text-muted)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {action.description}
                  </div>
                </div>
                <ArrowRight size={12} color="var(--color-text-muted)" />
              </div>
            );
          })}
        </div>

        {/* Elevated Actions if applicable */}
        {elevatedActions.length > 0 && (
          <div>
            <div
              style={{
                fontSize: '0.68rem',
                fontWeight: 600,
                color: 'var(--color-text-muted)',
                marginBottom: '6px',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              Management & Operations
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '8px' }}>
              {elevatedActions.map((action) => {
                const Icon = action.icon;
                return (
                  <div
                    key={action.title}
                    onClick={action.onClick}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--color-bg-page)',
                      border: '1px solid var(--color-border)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.transform = 'translateY(-1px)';
                      e.currentTarget.style.borderColor = 'var(--color-border-strong)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'none';
                      e.currentTarget.style.borderColor = 'var(--color-border)';
                    }}
                  >
                    <div
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: action.bg,
                        color: action.color,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
                      <Icon size={16} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 'var(--font-size-xs)', fontWeight: 600, color: 'var(--color-text-main)' }}>
                        {action.title}
                      </div>
                      <div
                        style={{
                          fontSize: '0.68rem',
                          color: 'var(--color-text-muted)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {action.description}
                      </div>
                    </div>
                    <ArrowRight size={12} color="var(--color-text-muted)" />
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
};
