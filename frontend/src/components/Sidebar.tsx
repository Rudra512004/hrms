import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  Building2,
  GitBranch,
  Briefcase,
  Clock,
  Calendar,
  Settings,
  ShieldAlert,
  Network,
  CalendarDays,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

interface SidebarProps {
  isOpen: boolean;
}

interface NavItem {
  path: string;
  label: string;
  icon: React.ElementType;
  permission?: string;
  end?: boolean;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen }) => {
  const { hasPermission } = useAuth();

  const navigation: NavSection[] = [
    {
      title: 'Overview',
      items: [
        { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, end: true },
      ],
    },
    {
      title: 'People',
      items: [
        { path: '/admin/employees',    label: 'Employees',     icon: Users,      permission: 'employee.view' },
        { path: '/admin/organizations',label: 'Organizations', icon: Building2,  permission: 'organization.view' },
        { path: '/admin/departments',  label: 'Departments',   icon: GitBranch,  permission: 'department.view' },
        { path: '/admin/designations', label: 'Designations',  icon: Briefcase,  permission: 'designation.view' },
      ],
    },
    {
      title: 'Time',
      items: [
        { path: '/attendance',         label: 'My Attendance',         icon: Clock },
        { path: '/admin/attendance',   label: 'Attendance Management', icon: CalendarDays, permission: 'attendance.view_all' },
        { path: '/leaves',             label: 'My Leave',              icon: Calendar },
        { path: '/admin/leaves',       label: 'Leave Requests',        icon: Calendar,  permission: 'leave.view' },
        { path: '/admin/leave-types',  label: 'Leave Types',           icon: Settings,  permission: 'leave_type.manage' },
        { path: '/admin/wfh',          label: 'WFH Requests',          icon: Network,   permission: 'wfh.view' },
      ],
    },
    {
      title: 'Admin',
      items: [
        { path: '/admin/roles',          label: 'Roles & Permissions', icon: ShieldAlert, permission: 'role.view' },
        { path: '/admin/audit-logs',     label: 'Audit Logs',          icon: Settings,    permission: 'audit.view' },
        { path: '/admin/office-networks',label: 'Office Networks',     icon: Network,     permission: 'office_network.view' },
      ],
    },
  ];

  return (
    <aside className={`sidebar ${isOpen ? 'open' : 'closed'}`}>
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">BS</div>
        {isOpen && <span style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}>BEYONDSURE HRMS</span>}
      </div>

      {/* Nav */}
      <nav className="sidebar-menu" aria-label="Main navigation">
        {navigation.map((section, idx) => {
          const visibleItems = section.items.filter(
            (item) => !item.permission || hasPermission(item.permission)
          );
          if (visibleItems.length === 0) return null;

          return (
            <div key={idx}>
              {isOpen && (
                <div className="sidebar-section">{section.title}</div>
              )}
              {visibleItems.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.end !== undefined ? item.end : false}
                  className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
                  title={!isOpen ? item.label : undefined}
                >
                  <span className="sidebar-icon">
                    <item.icon size={18} />
                  </span>
                  {isOpen && <span>{item.label}</span>}
                </NavLink>
              ))}
            </div>
          );
        })}
      </nav>
    </aside>
  );
};
