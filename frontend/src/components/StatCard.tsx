import React from 'react';
import { Card } from './Card';
import { type LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  color?: string;
}

export const StatCard: React.FC<StatCardProps> = ({ title, value, icon: Icon, color = 'var(--color-primary)' }) => {
  return (
    <Card style={{ padding: '0', display: 'flex', flexDirection: 'row', alignItems: 'center' }}>
      <div style={{ padding: 'var(--spacing-lg)', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: `${color}15`, color: color, borderRight: '1px solid var(--color-border)' }}>
        <Icon size={32} />
      </div>
      <div style={{ padding: 'var(--spacing-lg)', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.05em' }}>{title}</p>
        <h2 style={{ margin: 0, fontSize: '1.75rem', fontWeight: 700, color: 'var(--color-text-main)', lineHeight: 1.2 }}>{value}</h2>
      </div>
    </Card>
  );
};
