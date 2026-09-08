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
  DollarSign,
  FileText,
  BarChart2,
} from 'lucide-react';

import { useAuth } from '../contexts/AuthContext';

interface SidebarProps {
  isOpen: boolean;
}

interface NavItem {
  path: string;
  label: string;
  icon: React.ElementType;
  permission?: string | string[];
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
        { path: '/admin/branches',     label: 'Branches',      icon: Building2,  permission: 'branch.view' },
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
        { path: '/admin/holidays',     label: 'Holidays',              icon: CalendarDays, permission: 'holiday.view' },
        { path: '/admin/shifts',       label: 'Shifts',                icon: Clock,     permission: 'shift.view' },
      ],
    },
    {
      title: 'Finance',
      items: [
        { path: '/payslips', label: 'My Payslips', icon: FileText },
        { path: '/payroll', label: 'Payroll', icon: DollarSign, permission: 'payroll.view' },
        { path: '/payroll/reports', label: 'Reports', icon: BarChart2, permission: 'payroll.view_reports' },
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
      <div className="sidebar-logo" style={{ justifyContent: 'center', padding: isOpen ? '0 14px' : '0 8px' }}>
        {isOpen ? (
          <div
            style={{
              backgroundColor: '#ffffff',
              borderRadius: '8px',
              padding: '6px 14px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.15)',
            }}
          >
            <img
              src="/beyondsure-logo.webp"
              alt="BeyondSure HRMS"
              style={{
                width: '100%',
                maxWidth: '170px',
                height: 'auto',
                maxHeight: '28px',
                objectFit: 'contain',
                display: 'block',
              }}
            />
          </div>
        ) : (
          <div
            style={{
              backgroundColor: '#ffffff',
              borderRadius: '8px',
              padding: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.15)',
            }}
          >
            <img
              src="/favicon.svg"
              alt="BeyondSure"
              style={{
                width: 24,
                height: 24,
                objectFit: 'contain',
                flexShrink: 0,
              }}
            />
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="sidebar-menu" aria-label="Main navigation">
        {navigation.map((section, idx) => {
          const visibleItems = section.items.filter((item) => {
            if (!item.permission) return true;
            return Array.isArray(item.permission)
              ? item.permission.some((p) => hasPermission(p))
              : hasPermission(item.permission);
          });
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

      {/* Sidebar Footer */}
      {isOpen && (
        <div
          style={{
            padding: '12px 16px',
            borderTop: '1px solid var(--color-border-sidebar)',
            fontSize: '0.7rem',
            color: '#64748b',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ fontWeight: 600, color: '#94a3b8' }}>BEYONDSURE</span>
          <span style={{ backgroundColor: 'rgba(112, 38, 227, 0.25)', color: '#c4b5fd', padding: '2px 6px', borderRadius: '4px', fontSize: '0.65rem', fontWeight: 600 }}>ENTERPRISE</span>
        </div>
      )}
    </aside>
  );
};
