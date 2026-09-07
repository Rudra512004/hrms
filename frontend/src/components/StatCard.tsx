import React from 'react';
import { type LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  color?: string;
}

export const StatCard: React.FC<StatCardProps> = ({ title, value, icon: Icon, color = 'var(--color-primary)' }) => {
  return (
    <div className="stat-card">
      <div
        className="stat-card-icon"
        style={{
          backgroundColor: `${color}18`,
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
