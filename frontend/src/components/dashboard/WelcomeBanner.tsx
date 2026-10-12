import React from 'react';
import {
  Calendar,
  LogIn,
  LogOut,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Briefcase,
  FileText,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { type User } from '../../services/auth';
import { type PersonalAttendanceToday } from '../../services/dashboard';

interface WelcomeBannerProps {
  user: User;
  hasEmployeeProfile: boolean;
  attendanceToday?: PersonalAttendanceToday | null;
  actionLoading?: boolean;
  loading?: boolean;
  onCheckIn?: () => void;
  onCheckOut?: () => void;
  onRefresh?: () => void;
}

export const WelcomeBanner: React.FC<WelcomeBannerProps> = ({
  user,
  hasEmployeeProfile,
  attendanceToday,
  actionLoading = false,
  loading = false,
  onCheckIn,
  onCheckOut,
  onRefresh,
}) => {
  const navigate = useNavigate();

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  };

  const dateStr = new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });

  const orgName = user.organizationName
    ? `${user.organizationName} • BeyondSure HRMS Workspace`
    : 'BeyondSure HRMS Workspace';
  const roleText = user.designation
    ? `${user.designation}${user.department ? ` • ${user.department}` : ''}`
    : hasEmployeeProfile
    ? 'Employee'
    : 'System Administrator';

  const getAttendanceChip = () => {
    if (!hasEmployeeProfile) return null;
    if (!attendanceToday || !attendanceToday.check_in) {
      return {
        label: 'Not Clocked In',
        bg: 'rgba(255, 255, 255, 0.15)',
        dot: '#e2e8f0',
      };
    }
    if (attendanceToday.check_out) {
      return {
        label: 'Shift Completed',
        bg: 'rgba(255, 255, 255, 0.2)',
        dot: '#93c5fd',
      };
    }
    if (attendanceToday.is_on_break) {
      return {
        label: 'On Break',
        bg: 'rgba(245, 158, 11, 0.25)',
        dot: '#fbbf24',
      };
    }
    return {
      label: 'Clocked In',
      bg: 'rgba(16, 185, 129, 0.25)',
      dot: '#34d399',
    };
  };

  const attendanceChip = getAttendanceChip();

  return (
    <div
      data-testid="welcome-banner"
      style={{
        background: 'linear-gradient(135deg, #173F28 0%, #1F5D36 55%, #2E7D4F 100%)',
        borderRadius: 'var(--radius-xl)',
        padding: '26px 30px',
        color: '#FFFFFF',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '20px',
        boxShadow: '0 10px 25px -5px rgba(23, 63, 40, 0.35)',
        border: '1px solid rgba(255, 255, 255, 0.12)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Decorative Background Accent */}
      <div
        style={{
          position: 'absolute',
          right: '-50px',
          top: '-50px',
          width: '260px',
          height: '260px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0) 70%)',
          pointerEvents: 'none',
        }}
      />

      <div style={{ position: 'relative', zIndex: 1, minWidth: 0 }}>
        {/* Title & Status Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginBottom: '8px' }}>
          <h1
            style={{
              fontSize: '1.65rem',
              fontWeight: 700,
              margin: 0,
              color: '#FFFFFF',
              letterSpacing: '-0.02em',
              lineHeight: 1.2,
            }}
          >
            {greeting()}, {user.firstName || user.email.split('@')[0]}
          </h1>

          {/* Role Pill */}
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 10px',
              borderRadius: 'var(--radius-full)',
              fontSize: '0.72rem',
              fontWeight: 600,
              backgroundColor: 'rgba(255, 255, 255, 0.18)',
              color: '#FFFFFF',
              backdropFilter: 'blur(4px)',
            }}
          >
            {hasEmployeeProfile ? <Briefcase size={12} /> : <ShieldAlert size={12} />}
            {roleText}
          </span>

          {/* Attendance State Chip */}
          {attendanceChip && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '3px 10px',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.72rem',
                fontWeight: 600,
                backgroundColor: attendanceChip.bg,
                color: '#FFFFFF',
                backdropFilter: 'blur(4px)',
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  backgroundColor: attendanceChip.dot,
                  display: 'inline-block',
                }}
              />
              {attendanceChip.label}
            </span>
          )}
        </div>

        {/* Date and Organization Subtitle */}
        <p
          style={{
            margin: 0,
            fontSize: 'var(--font-size-sm)',
            color: 'rgba(255, 255, 255, 0.85)',
          }}
        >
          {dateStr} • {orgName}
        </p>
      </div>

      {/* Banner Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', position: 'relative', zIndex: 1 }}>
        {hasEmployeeProfile ? (
          <>
            {!attendanceToday || !attendanceToday.check_in ? (
              <button
                className="btn"
                onClick={onCheckIn}
                disabled={actionLoading}
                type="button"
                style={{
                  backgroundColor: '#FFFFFF',
                  color: 'var(--color-primary)',
                  fontWeight: 700,
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                  border: 'none',
                  padding: '9px 18px',
                }}
              >
                {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <LogIn size={16} />}
                Web Check In
              </button>
            ) : !attendanceToday.check_out ? (
              <button
                className="btn"
                onClick={onCheckOut}
                disabled={actionLoading}
                type="button"
                style={{
                  backgroundColor: '#FFFFFF',
                  color: 'var(--color-primary)',
                  fontWeight: 700,
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                  border: 'none',
                  padding: '9px 18px',
                }}
              >
                {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <LogOut size={16} />}
                Check Out
              </button>
            ) : null}

            <button
              className="btn"
              onClick={() => navigate('/leaves')}
              type="button"
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.18)',
                color: '#FFFFFF',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                fontWeight: 600,
                backdropFilter: 'blur(4px)',
                padding: '9px 16px',
              }}
            >
              <Calendar size={15} /> Apply Leave
            </button>

            <button
              className="btn"
              onClick={() => navigate('/payslips')}
              type="button"
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.18)',
                color: '#FFFFFF',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                fontWeight: 600,
                backdropFilter: 'blur(4px)',
                padding: '9px 16px',
              }}
            >
              <FileText size={15} /> My Payslips
            </button>
          </>
        ) : (
          <>
            <button
              className="btn"
              onClick={() => navigate('/admin/employees')}
              type="button"
              style={{
                backgroundColor: '#FFFFFF',
                color: 'var(--color-primary)',
                fontWeight: 700,
                border: 'none',
                padding: '9px 18px',
              }}
            >
              Employees
            </button>
            <button
              className="btn"
              onClick={() => navigate('/admin/attendance')}
              type="button"
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.18)',
                color: '#FFFFFF',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                fontWeight: 600,
                padding: '9px 16px',
              }}
            >
              Attendance
            </button>
          </>
        )}

        {onRefresh && (
          <button
            className="btn"
            onClick={onRefresh}
            title="Refresh dashboard metrics"
            type="button"
            aria-label="Refresh dashboard"
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.15)',
              color: '#FFFFFF',
              border: '1px solid rgba(255, 255, 255, 0.25)',
              padding: '9px 10px',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
        )}
      </div>
    </div>
  );
};
