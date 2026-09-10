import React from 'react';
import { type LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  color?: string;
  bg?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  icon: Icon,
  color = 'var(--color-primary)',
  bg,
}) => {
  const iconBg = bg || (color.startsWith('var(')
    ? `color-mix(in srgb, ${color} 12%, transparent)`
    : `${color}18`);

  return (
    <div className="stat-card">
      <div
        className="stat-card-icon"
        style={{
          backgroundColor: iconBg,
          color: color,
        }}
      >
        <Icon size={24} />
      </div>
      <div>
        <div className="stat-card-value">{value}</div>
        <div className="stat-card-label">{title}</div>
      </div>
    </div>
  );
};
