import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  UserCircle,
  Settings,
  Network,
  Clock,
  Calendar,
  Users,
  ShieldAlert,
  Building2,
  Briefcase,
  GitBranch
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

interface SidebarProps {
  isOpen: boolean;
}

const styles = {
  sidebar: (isOpen: boolean) => ({
    width: isOpen ? 'var(--sidebar-width)' : 'var(--sidebar-width-collapsed)',
    backgroundColor: 'var(--color-bg-sidebar)',
    color: 'var(--color-text-sidebar)',
    height: '100vh',
    position: 'fixed' as const,
    left: 0,
    top: 0,
    bottom: 0,
    zIndex: 100,
    transition: 'width 0.3s ease',
    overflowY: 'auto' as const,
    overflowX: 'hidden' as const,
    display: 'flex',
    flexDirection: 'column' as const,
    boxShadow: 'var(--shadow-md)', // Neumorphic soft shadow
    borderRight: '1px solid rgba(255, 255, 255, 0.8)',
  }),
  logoArea: {
    height: 'var(--header-height)',
    display: 'flex',
    alignItems: 'center',
    padding: '0 var(--spacing-lg)',
    fontSize: '1.5rem',
    fontWeight: 700,
    color: 'var(--color-primary)',
    marginBottom: 'var(--spacing-md)',
  },
  menu: {
    padding: '0 var(--spacing-md)',
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '4px',
  },
  sectionTitle: (isOpen: boolean) => ({
    padding: 'var(--spacing-sm) var(--spacing-md)',
    fontSize: '0.75rem',
    textTransform: 'uppercase' as const,
    color: 'var(--color-text-muted)',
    marginTop: 'var(--spacing-md)',
    opacity: isOpen ? 1 : 0,
    display: isOpen ? 'block' : 'none',
  }),
  link: (isActive: boolean, isOpen: boolean) => ({
    display: 'flex',
    alignItems: 'center',
    padding: '10px 16px',
    justifyContent: isOpen ? 'flex-start' : 'center',
    color: isActive ? 'var(--color-text-inverse)' : 'var(--color-text-sidebar)',
    textDecoration: 'none',
    transition: 'all 0.2s',
    borderRadius: 'var(--radius-md)',
    backgroundColor: isActive ? 'var(--color-primary)' : 'transparent',
    boxShadow: isActive ? '0 2px 4px rgba(115, 103, 240, 0.4)' : 'none',
    marginBottom: '4px',
  }),
  icon: {
    marginRight: '12px',
    display: 'flex',
    alignItems: 'center',
  },
  iconCollapsed: {
    marginRight: 0,
    display: 'flex',
    alignItems: 'center',
  },
  label: (isOpen: boolean) => ({
    display: isOpen ? 'block' : 'none',
    fontWeight: 500,
  })
};

interface NavItem {
  path: string;
  label: string;
  icon: React.ElementType;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen }) => {
  const { hasPermission } = useAuth();

  const navigation: NavSection[] = [
    {
      title: 'Apps & Pages',
      items: [
        { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
        { path: '/attendance', label: 'Attendance', icon: Clock },
        { path: '/leaves', label: 'Leave', icon: Calendar },
        { path: '/profile', label: 'My Profile', icon: UserCircle },
      ]
    }
  ];

  const adminItems: NavItem[] = [];
  if (hasPermission('employee.view') || hasPermission('office_network.view') || hasPermission('wfh.view') || hasPermission('leave.view') || hasPermission('leave_type.manage') || hasPermission('audit.view') || hasPermission('organization.view') || hasPermission('department.view') || hasPermission('designation.view')) {
    adminItems.push({ path: '/admin', label: 'Overview', icon: Settings });
  }
  if (hasPermission('employee.view')) adminItems.push({ path: '/admin/employees', label: 'Employees', icon: Users });
  if (hasPermission('organization.view')) adminItems.push({ path: '/admin/organizations', label: 'Organizations', icon: Building2 });
  if (hasPermission('department.view')) adminItems.push({ path: '/admin/departments', label: 'Departments', icon: GitBranch });
  if (hasPermission('designation.view')) adminItems.push({ path: '/admin/designations', label: 'Designations', icon: Briefcase });
  if (hasPermission('office_network.view')) adminItems.push({ path: '/admin/office-networks', label: 'Office Networks', icon: Network });
  if (hasPermission('wfh.view')) adminItems.push({ path: '/admin/wfh', label: 'WFH Requests', icon: Settings });
  if (hasPermission('leave.view') || hasPermission('leave_type.manage')) adminItems.push({ path: '/admin/leaves', label: 'Leave Requests', icon: Calendar });
  if (hasPermission('leave_type.manage')) adminItems.push({ path: '/admin/leave-types', label: 'Leave Types', icon: Calendar });
  if (hasPermission('audit.view')) adminItems.push({ path: '/admin/audit-logs', label: 'Audit Logs', icon: ShieldAlert });

  if (adminItems.length > 0) {
    navigation.push({
      title: 'Administration',
      items: adminItems
    });
  }

  return (
    <aside style={styles.sidebar(isOpen)}>
      <div style={styles.logoArea}>
        {isOpen ? 'Vuexy HRMS' : 'VH'}
      </div>
      <nav style={styles.menu}>
        {navigation.map((section, idx) => (
          <div key={idx}>
            <div style={styles.sectionTitle(isOpen)}>{section.title}</div>
            {section.items.map((item) => (
              <NavLink 
                key={item.path} 
                to={item.path} 
                end={item.path === '/admin'}
                style={({ isActive }) => styles.link(isActive, isOpen)}
                title={!isOpen ? item.label : undefined}
              >
                {({ isActive }) => (
                  <>
                    <div style={isOpen ? styles.icon : styles.iconCollapsed}>
                      <item.icon size={22} color={isActive ? 'var(--color-text-inverse)' : 'var(--color-text-sidebar)'} />
                    </div>
                    <span style={styles.label(isOpen)}>{item.label}</span>
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
};
