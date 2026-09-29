import React from 'react';
import { Menu, User, LogOut, ChevronRight, MapPin, ChevronDown } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useBranchContext } from '../contexts/BranchContext';
import { NotificationBell } from './NotificationBell';

interface HeaderProps {
  toggleSidebar: () => void;
  isSidebarOpen: boolean;
}

// Maps route prefixes to human-readable breadcrumb labels
const routeLabels: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/attendance': 'My Attendance',
  '/leaves': 'My Leave',
  '/payslips': 'My Payslips',
  '/payroll/reports': 'Payroll Reports',
  '/payroll': 'Payroll',
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
  '/admin/assets': 'Assets',
  '/notifications': 'Notifications',
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
  const { selectedBranch, selectBranch, branches, isLoading, error } = useBranchContext();

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
          <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-primary)', fontWeight: 600, letterSpacing: '0.04em' }}>
            BEYONDSURE HRMS
          </span>
          <ChevronRight size={12} color="var(--color-text-muted)" />
          <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {breadcrumb}
          </span>
        </div>
      </div>

      {/* Right: actions + user info */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {/* Branch Context Selector */}
        <div
          className="branch-selector-container"
          style={{
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <MapPin
            size={14}
            style={{
              position: 'absolute',
              left: '9px',
              color: 'var(--color-primary)',
              pointerEvents: 'none',
              zIndex: 1,
            }}
          />
          <select
            id="header-branch-selector"
            aria-label="Select Branch Location"
            value={selectedBranch.type === 'branch' ? selectedBranch.branchId : 'all'}
            onChange={(e) => {
              const val = e.target.value;
              if (val === 'all') {
                selectBranch('all');
              } else {
                selectBranch(Number(val));
              }
            }}
            disabled={isLoading || !!error}
            style={{
              appearance: 'none',
              paddingLeft: '28px',
              paddingRight: '24px',
              paddingTop: '5px',
              paddingBottom: '5px',
              height: '32px',
              fontSize: 'var(--font-size-xs)',
              fontWeight: 500,
              color: 'var(--color-text-main)',
              backgroundColor: 'var(--color-bg-subtle, #f8fafc)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md, 6px)',
              cursor: isLoading || !!error ? 'not-allowed' : 'pointer',
              outline: 'none',
              maxWidth: '180px',
            }}
          >
            {isLoading ? (
              <option value="all">Loading locations...</option>
            ) : error ? (
              <option value="all">Locations unavailable</option>
            ) : (
              <>
                <option value="all">All Locations</option>
                {branches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </>
            )}
          </select>
          <ChevronDown
            size={13}
            style={{
              position: 'absolute',
              right: '7px',
              color: 'var(--color-text-muted)',
              pointerEvents: 'none',
            }}
          />
        </div>
        <div
          className="hide-on-mobile"
          style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}
        >
          <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-main)', lineHeight: 1.3 }}>
            {user ? `${user.firstName} ${user.lastName}`.trim() || user.email : 'â€¦'}
          </span>
          <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', lineHeight: 1.3 }}>
            {user?.email}
          </span>
        </div>

        <NotificationBell />

        <button
          onClick={() => navigate('/profile')}
          title="My Profile"
          type="button"
          style={{
            width: 36,
            height: 36,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--color-primary) 0%, #8b5cf6 100%)',
            color: '#ffffff',
            border: 'none',
            boxShadow: '0 2px 8px rgba(112, 38, 227, 0.28)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 700,
            fontSize: 'var(--font-size-xs)',
            cursor: 'pointer',
            flexShrink: 0,
            transition: 'transform 0.15s ease, box-shadow 0.15s ease',
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
