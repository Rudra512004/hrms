import React from 'react';
import { Menu, User, LogOut, ChevronRight } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

interface HeaderProps {
  toggleSidebar: () => void;
  isSidebarOpen: boolean;
}

// Maps route prefixes to human-readable breadcrumb labels
const routeLabels: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/attendance': 'My Attendance',
  '/leaves': 'My Leave',
  '/profile': 'My Profile',
  '/admin/employees': 'Employees',
  '/admin/attendance': 'Attendance Management',
  '/admin/leaves': 'Leave Requests',
  '/admin/leave-types': 'Leave Types',
  '/admin/wfh': 'WFH Requests',
  '/admin/roles': 'Roles & Permissions',
  '/admin/audit-logs': 'Audit Logs',
  '/admin/office-networks': 'Office Networks',
  '/admin/organizations': 'Organizations',
  '/admin/departments': 'Departments',
  '/admin/designations': 'Designations',
  '/admin/branches': 'Branches',
  '/admin/holidays': 'Holidays',
  '/admin/shifts': 'Shifts',
};

function getBreadcrumb(pathname: string): string {
  // Exact match first
  if (routeLabels[pathname]) return routeLabels[pathname];
  // Prefix match (handles /admin/employees/:id etc.)
  const match = Object.keys(routeLabels)
    .filter(k => pathname.startsWith(k))
    .sort((a, b) => b.length - a.length)[0];
  return match ? routeLabels[match] : 'BEYONDSURE HRMS';
}

export const Header: React.FC<HeaderProps> = ({ toggleSidebar }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const getInitials = (firstName: string, lastName: string) =>
    `${firstName?.charAt(0) || ''}${lastName?.charAt(0) || ''}`.toUpperCase() || '?';

  const breadcrumb = getBreadcrumb(location.pathname);

  return (
    <header className="app-header">
      {/* Left: toggle + breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
        <button
          className="header-toggle"
          onClick={toggleSidebar}
          aria-label="Toggle sidebar"
          type="button"
        >
          <Menu size={20} />
        </button>
        <div
          className="hide-on-mobile"
          style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}
        >
          <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 500 }}>
            BEYONDSURE HRMS
          </span>
          <ChevronRight size={12} color="var(--color-text-muted)" />
          <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {breadcrumb}
          </span>
        </div>
      </div>

      {/* Right: user info */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div
          className="hide-on-mobile"
          style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}
        >
          <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-main)', lineHeight: 1.3 }}>
            {user ? `${user.firstName} ${user.lastName}`.trim() || user.email : '…'}
          </span>
          <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', lineHeight: 1.3 }}>
            {user?.email}
          </span>
        </div>

        <button
          onClick={() => navigate('/profile')}
          title="My Profile"
          type="button"
          style={{
            width: 36,
            height: 36,
            borderRadius: '50%',
            backgroundColor: 'var(--color-primary-light)',
            color: 'var(--color-primary)',
            border: '2px solid var(--color-primary-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 700,
            fontSize: 'var(--font-size-xs)',
            cursor: 'pointer',
            flexShrink: 0,
            transition: 'border-color 0.15s',
          }}
        >
          {user ? getInitials(user.firstName, user.lastName) : <User size={16} />}
        </button>

        <button
          className="header-toggle"
          onClick={handleLogout}
          title="Logout"
          type="button"
          aria-label="Logout"
        >
          <LogOut size={18} />
        </button>
      </div>
    </header>
  );
};
