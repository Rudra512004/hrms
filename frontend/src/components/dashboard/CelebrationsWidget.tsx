import React, { useState, useEffect } from 'react';
import {
  Gift,
  Cake,
  Award,
  UserPlus,
  Loader2,
  Calendar,
  AlertCircle,
} from 'lucide-react';
import { Card } from '../Card';
import { dashboardService, type CelebrationItem } from '../../services/dashboard';

export const CelebrationsWidget: React.FC = () => {
  const [celebrations, setCelebrations] = useState<CelebrationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCelebrations = () => {
    setLoading(true);
    setError(null);
    dashboardService
      .getCelebrations()
      .then((data) => {
        setCelebrations(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        console.error('Failed to load celebrations:', err);
        setError('Unable to load celebrations.');
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchCelebrations();
  }, []);

  const formatDisplayDate = (dateStr: string) => {
    try {
      const parts = dateStr.split('-');
      if (parts.length === 3) {
        const year = parseInt(parts[0], 10);
        const month = parseInt(parts[1], 10) - 1;
        const day = parseInt(parts[2], 10);
        const d = new Date(year, month, day);
        return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
      }
      return dateStr;
    } catch {
      return dateStr;
    }
  };

  return (
    <Card
      title="Celebrations"
      actions={
        celebrations.length > 0 ? (
          <span
            style={{
              fontSize: '0.72rem',
              fontWeight: 700,
              padding: '2px 8px',
              borderRadius: '10px',
              backgroundColor: 'rgba(236, 72, 153, 0.12)',
              color: '#db2777',
            }}
          >
            {celebrations.length} upcoming
          </span>
        ) : undefined
      }
    >
      {loading ? (
        <div style={{ padding: '24px', textAlign: 'center' }}>
          <Loader2 size={24} className="animate-spin" color="var(--color-primary)" />
        </div>
      ) : error ? (
        <div
          style={{
            padding: '16px',
            color: 'var(--color-status-danger)',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
          <button
            className="btn btn-secondary"
            onClick={fetchCelebrations}
            type="button"
            style={{ padding: '2px 8px', fontSize: '0.75rem' }}
          >
            Retry
          </button>
        </div>
      ) : celebrations.length === 0 ? (
        <div style={{ padding: '20px 12px', textAlign: 'center' }}>
          <Gift size={28} color="var(--color-text-muted)" style={{ margin: '0 auto 8px', opacity: 0.6 }} />
          <p className="text-muted" style={{ margin: 0, fontSize: '0.88rem' }}>
            No upcoming celebrations in the next 30 days.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {celebrations.map((item, idx) => {
            const isBirthday = item.type === 'birthday';
            const isAnniversary = item.type === 'anniversary';

            const iconColor = isBirthday
              ? '#ec4899'
              : isAnniversary
              ? '#8b5cf6'
              : '#0284c7';

            const bgGlow = isBirthday
              ? 'rgba(236, 72, 153, 0.08)'
              : isAnniversary
              ? 'rgba(139, 92, 246, 0.08)'
              : 'rgba(2, 132, 199, 0.08)';

            const label = isBirthday
              ? 'Birthday'
              : isAnniversary
              ? `${item.years || 1} Year${(item.years || 1) > 1 ? 's' : ''} Anniversary`
              : 'New Joinee';

            const IconComponent = isBirthday
              ? Cake
              : isAnniversary
              ? Award
              : UserPlus;

            return (
              <div
                key={`${item.id}-${item.type}-${idx}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-md, 8px)',
                  background: 'var(--surface-control-bg, var(--color-bg-subtle, #f8fafc))',
                  border: '1px solid var(--color-border-subtle, #e2e8f0)',
                  transition: 'transform 0.15s ease',
                }}
              >
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: '50%',
                    background: bgGlow,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  <IconComponent size={18} color={iconColor} />
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontWeight: 600,
                      fontSize: '0.9rem',
                      color: 'var(--color-text-main, #0f172a)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {item.name}
                  </div>
                  <div
                    style={{
                      fontSize: '0.75rem',
                      color: iconColor,
                      fontWeight: 500,
                    }}
                  >
                    {label}
                  </div>
                </div>

                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    color: 'var(--color-text-muted, #64748b)',
                    background: 'var(--color-bg-card, #ffffff)',
                    padding: '3px 8px',
                    borderRadius: '6px',
                    border: '1px solid var(--color-border-subtle, #e2e8f0)',
                    flexShrink: 0,
                  }}
                >
                  <Calendar size={12} />
                  <span>{formatDisplayDate(item.date)}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
};
