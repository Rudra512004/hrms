import React from 'react';
import { Calendar } from 'lucide-react';
import { Card } from '../Card';
import { EmptyState } from '../EmptyState';
import { type UpcomingHoliday } from '../../services/dashboard';

interface UpcomingHolidaysWidgetProps {
  holidays: UpcomingHoliday[];
}

export const UpcomingHolidaysWidget: React.FC<UpcomingHolidaysWidgetProps> = ({ holidays }) => {
  const getRelativeDaysText = (dateStr: string) => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const target = new Date(dateStr);
    target.setHours(0, 0, 0, 0);

    const diffDays = Math.round((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Tomorrow';
    if (diffDays > 1) return `In ${diffDays} days`;
    return '';
  };

  return (
    <Card title="Upcoming Holidays">
      {holidays.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {holidays.map((h) => {
            const relText = getRelativeDaysText(h.date);
            const dateObj = new Date(h.date);
            const dayNum = dateObj.toLocaleDateString(undefined, { day: 'numeric' });
            const monthStr = dateObj.toLocaleDateString(undefined, { month: 'short' });
            const weekday = dateObj.toLocaleDateString(undefined, { weekday: 'long' });

            return (
              <div
                key={h.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--color-bg-page)',
                  border: '1px solid var(--color-border)',
                }}
              >
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'rgba(112, 38, 227, 0.08)',
                    border: '1px solid rgba(112, 38, 227, 0.16)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  <span style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--color-primary)', textTransform: 'uppercase' }}>
                    {monthStr}
                  </span>
                  <span style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--color-primary)', lineHeight: 1 }}>
                    {dayNum}
                  </span>
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <p
                    style={{
                      margin: 0,
                      fontWeight: 600,
                      fontSize: 'var(--font-size-sm)',
                      color: 'var(--color-text-main)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {h.name}
                  </p>
                  <p style={{ margin: 0, fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                    {weekday}
                  </p>
                </div>

                {relText && (
                  <span
                    style={{
                      fontSize: 'var(--font-size-xs)',
                      fontWeight: 600,
                      padding: '2px 8px',
                      borderRadius: 'var(--radius-full)',
                      backgroundColor: 'var(--color-primary-light)',
                      color: 'var(--color-primary)',
                      border: '1px solid var(--color-primary-border)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {relText}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <EmptyState title="No Holidays Soon" description="No scheduled public holidays in the near future." icon={Calendar} />
      )}
    </Card>
  );
};
