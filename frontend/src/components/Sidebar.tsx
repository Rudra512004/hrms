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
  Network
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
      title: 'Dashboard',
      items: [
        { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard }
      ]
    },
    {
      title: 'People',
      items: [
        { path: '/admin/employees', label: 'Employees', icon: Users, permission: 'employee.view' },
        { path: '/admin/organizations', label: 'Organizations', icon: Building2, permission: 'organization.view' },
        { path: '/admin/departments', label: 'Departments', icon: GitBranch, permission: 'department.view' },
        { path: '/admin/designations', label: 'Designations', icon: Briefcase, permission: 'designation.view' },
      ]
    },
    {
      title: 'Time',
      items: [
        { path: '/attendance', label: 'My Attendance', icon: Clock },
        { path: '/admin/attendance', label: 'Attendance Management', icon: Clock, permission: 'attendance.view_all' },
        { path: '/leaves', label: 'My Leave', icon: Calendar },
        { path: '/admin/leaves', label: 'Leave Requests', icon: Calendar, permission: 'leave.view' },
        { path: '/admin/leave-types', label: 'Leave Types', icon: Calendar, permission: 'leave_type.manage' },
        { path: '/admin/wfh', label: 'WFH Requests', icon: Settings, permission: 'wfh.view' }
      ]
    },
    {
      title: 'Admin',
      items: [
        { path: '/admin/roles', label: 'Roles & Permissions', icon: ShieldAlert, permission: 'role.view' },
        { path: '/admin/audit-logs', label: 'Audit Logs', icon: Settings, permission: 'audit.view' },
        { path: '/admin/office-networks', label: 'Office Networks', icon: Network, permission: 'office_network.view' },
      ]
    }
  ];

  return (
    <aside className={`sidebar ${isOpen ? 'open' : 'closed'}`}>
      <div className="sidebar-logo">
        {isOpen ? 'BEYONDSURE HRMS' : 'BH'}
      </div>
      <nav className="sidebar-menu">
        {navigation.map((section, idx) => {
          // Filter items based on permission
          const visibleItems = section.items.filter(
            item => !item.permission || hasPermission(item.permission)
          );

          if (visibleItems.length === 0) return null;

          return (
            <div key={idx}>
              <div 
                className="sidebar-section" 
                style={{ display: isOpen ? 'block' : 'none' }}
              >
                {section.title}
              </div>
              {visibleItems.map((item) => (
                <NavLink 
                  key={item.path} 
                  to={item.path} 
                  end={item.end !== undefined ? item.end : item.path === '/admin'}
                  className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
                  title={!isOpen ? item.label : undefined}
                >
                  <div className="sidebar-icon">
                    <item.icon size={20} />
                  </div>
                  <span style={{ display: isOpen ? 'block' : 'none' }}>
                    {item.label}
                  </span>
                </NavLink>
              ))}
            </div>
          );
        })}
      </nav>
    </aside>
  );
};
