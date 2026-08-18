import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Users, 
  Calendar, 
  CalendarOff, 
  Banknote, 
  Settings, 
  ShieldCheck, 
  Building2, 
  FileText
} from 'lucide-react';

interface SidebarProps {
  isOpen: boolean;
}

const styles = {
  sidebar: (isOpen: boolean) => ({
    width: isOpen ? 'var(--sidebar-width)' : 'var(--sidebar-width-collapsed)',
    backgroundColor: 'var(--color-bg-sidebar)',
    color: 'var(--color-text-inverse)',
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
  }),
  logoArea: {
    height: 'var(--header-height)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '1.5rem',
    fontWeight: 700,
    color: 'var(--color-primary)',
    borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
  },
  menu: {
    padding: 'var(--spacing-md) 0',
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 'var(--spacing-xs)',
  },
  sectionTitle: (isOpen: boolean) => ({
    padding: 'var(--spacing-sm) var(--spacing-lg)',
    fontSize: '0.75rem',
    textTransform: 'uppercase' as const,
    color: '#8a9bb2',
    letterSpacing: '0.5px',
    marginTop: 'var(--spacing-md)',
    opacity: isOpen ? 1 : 0,
    display: isOpen ? 'block' : 'none',
  }),
  link: (isActive: boolean, isOpen: boolean) => ({
    display: 'flex',
    alignItems: 'center',
    padding: isOpen ? 'var(--spacing-sm) var(--spacing-lg)' : 'var(--spacing-sm) 0',
    justifyContent: isOpen ? 'flex-start' : 'center',
    color: isActive ? 'var(--color-primary)' : '#b8c7ce',
    textDecoration: 'none',
    transition: 'all 0.2s',
    borderLeft: isActive ? '3px solid var(--color-primary)' : '3px solid transparent',
    backgroundColor: isActive ? 'var(--color-bg-sidebar-hover)' : 'transparent',
  }),
  icon: {
    marginRight: 'var(--spacing-md)',
  },
  iconCollapsed: {
    marginRight: 0,
  },
  label: (isOpen: boolean) => ({
    display: isOpen ? 'block' : 'none',
  })
};

interface NavItem {
  path: string;
  label: string;
  icon: React.ReactNode;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const navigation: NavSection[] = [
  {
    title: 'Main',
    items: [
      { path: '/dashboard', label: 'Dashboard', icon: <LayoutDashboard size={20} /> },
      { path: '/employees', label: 'Employees', icon: <Users size={20} /> },
      { path: '/attendance', label: 'Attendance', icon: <Calendar size={20} /> },
      { path: '/leave', label: 'Leave', icon: <CalendarOff size={20} /> },
      { path: '/payroll', label: 'Payroll', icon: <Banknote size={20} /> },
    ]
  },
  {
    title: 'Administration',
    items: [
      { path: '/users', label: 'Users', icon: <Users size={20} /> },
      { path: '/roles', label: 'Roles & Permissions', icon: <ShieldCheck size={20} /> },
      { path: '/organization', label: 'Organization', icon: <Building2 size={20} /> },
      { path: '/audit-logs', label: 'Audit Logs', icon: <FileText size={20} /> },
    ]
  },
  {
    title: 'System',
    items: [
      { path: '/settings', label: 'Settings', icon: <Settings size={20} /> },
    ]
  }
];

export const Sidebar: React.FC<SidebarProps> = ({ isOpen }) => {
  return (
    <aside style={styles.sidebar(isOpen)}>
      <div style={styles.logoArea}>
        {isOpen ? 'SmartHR' : 'HR'}
      </div>
      <nav style={styles.menu}>
        {navigation.map((section, idx) => (
          <div key={idx}>
            <div style={styles.sectionTitle(isOpen)}>{section.title}</div>
            {section.items.map((item) => (
              <NavLink 
                key={item.path} 
                to={item.path} 
                style={({ isActive }) => styles.link(isActive, isOpen)}
                title={!isOpen ? item.label : undefined}
              >
                <div style={isOpen ? styles.icon : styles.iconCollapsed}>
                  {item.icon}
                </div>
                <span style={styles.label(isOpen)}>{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
};
