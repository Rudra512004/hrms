import React from 'react';
import { AlertCircle, CheckCircle, Info, AlertTriangle } from 'lucide-react';

export type AlertType = 'error' | 'success' | 'warning' | 'info';

interface AlertBannerProps {
  type: AlertType;
  message: string;
  className?: string;
  style?: React.CSSProperties;
}

const config: Record<AlertType, { cls: string; Icon: React.ElementType }> = {
  error:   { cls: 'alert-banner-error',   Icon: AlertCircle },
  success: { cls: 'alert-banner-success', Icon: CheckCircle },
  warning: { cls: 'alert-banner-warning', Icon: AlertTriangle },
  info:    { cls: 'alert-banner-info',    Icon: Info },
};

export const AlertBanner: React.FC<AlertBannerProps> = ({
  type,
  message,
  className = '',
  style,
}) => {
  const { cls, Icon } = config[type];
  return (
    <div className={`alert-banner ${cls} ${className}`} role="alert" style={style}>
      <Icon size={16} className="alert-banner-icon" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
};
