import React from 'react';
import { Coffee, Plus, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../Card';
import { EmptyState } from '../EmptyState';
import { type PersonalLeaveBalance } from '../../services/dashboard';

interface LeaveBalanceWidgetProps {
  balances: PersonalLeaveBalance[];
  loading?: boolean;
}

export const LeaveBalanceWidget: React.FC<LeaveBalanceWidgetProps> = ({
  balances,
  loading = false,
}) => {
  const navigate = useNavigate();

  return (
    <Card title="My Leave Balances">
      {loading ? (
        <div className="loading-center" style={{ padding: '28px' }}>
          <Loader2 size={24} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
        </div>
      ) : balances.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {balances.map((lb) => {
            const total = lb.allocated || (lb.used + lb.remaining) || 1;
            const pct = Math.min(100, Math.max(0, Math.round(((total - lb.remaining) / total) * 100)));
            const isLow = lb.remaining <= 1;

            return (
              <div key={lb.leave_type_id} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-main)' }}>
                    {lb.leave_type_name}
                  </span>
                  <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                    <strong style={{ color: isLow ? 'var(--color-status-danger)' : 'var(--color-primary)', fontWeight: 700 }}>
                      {lb.remaining}
                    </strong>{' '}
                    / {total} days remaining
                  </span>
                </div>

                {/* Progress bar */}
                <div
                  style={{
                    height: '7px',
                    backgroundColor: 'var(--color-border)',
                    borderRadius: 'var(--radius-full)',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${pct}%`,
                      background:
                        pct > 80
                          ? 'var(--color-status-danger)'
                          : 'linear-gradient(90deg, var(--color-primary) 0%, #0ea5e9 100%)',
                      borderRadius: 'var(--radius-full)',
                      transition: 'width 0.4s ease',
                    }}
                  />
                </div>
              </div>
            );
          })}

          <button
            className="btn btn-secondary"
            onClick={() => navigate('/leaves')}
            style={{ width: '100%', marginTop: '6px', fontSize: 'var(--font-size-sm)' }}
            type="button"
          >
            <Plus size={14} /> Request Leave
          </button>
        </div>
      ) : (
        <EmptyState title="No Balances" description="No active leave allocations found." icon={Coffee} />
      )}
    </Card>
  );
};
