import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
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
  Package,
  UserPlus,
  SlidersHorizontal,
  Bell,
  ListChecks,
  Coffee,
  MapPin,
  FolderKanban,
  Star,
  UserCheck,
  Loader2,
  X,
  ArrowRight,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

interface PaletteItem {
  id: string;
  title: string;
  category: string;
  subtitle?: string;
  icon: React.ElementType;
  path: string;
  permission?: string | string[];
  requiresEmployee?: boolean;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const { hasPermission, hasEmployeeProfile } = useAuth();

  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [employeeResults, setEmployeeResults] = useState<PaletteItem[]>([]);
  const [isSearchingEmployees, setIsSearchingEmployees] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // All application navigation items
  const allNavItems: PaletteItem[] = useMemo(
    () => [
      { id: 'nav-dash', title: 'Dashboard', category: 'Navigation', icon: LayoutDashboard, path: '/dashboard' },
      { id: 'nav-org-chart', title: 'Organization Chart', category: 'People', icon: Network, path: '/admin/org-chart', permission: 'organization.view' },
      { id: 'nav-emp', title: 'Employees', category: 'People', icon: Users, path: '/admin/employees', permission: 'employee.view' },
      { id: 'nav-cand', title: 'Candidates', category: 'People', icon: UserPlus, path: '/admin/candidates', permission: 'candidate.view' },
      { id: 'nav-assets', title: 'Assets', category: 'People', icon: Package, path: '/admin/assets', permission: 'asset.view' },
      { id: 'nav-orgs', title: 'Organizations', category: 'People', icon: Building2, path: '/admin/organizations', permission: 'organization.view' },
      { id: 'nav-depts', title: 'Departments', category: 'People', icon: GitBranch, path: '/admin/departments', permission: 'department.view' },
      { id: 'nav-teams', title: 'Teams', category: 'People', icon: Users, path: '/admin/teams', permission: 'team.view' },
      { id: 'nav-branches', title: 'Branches', category: 'People', icon: Building2, path: '/admin/branches', permission: 'branch.view' },
      { id: 'nav-desig', title: 'Designations', category: 'People', icon: Briefcase, path: '/admin/designations', permission: 'designation.view' },

      // Time & Attendance
      { id: 'nav-my-att', title: 'My Attendance', category: 'Time', icon: Clock, path: '/attendance', requiresEmployee: true },
      { id: 'nav-adm-att', title: 'Attendance Management', category: 'Time', icon: CalendarDays, path: '/admin/attendance', permission: 'attendance.view_all' },
      { id: 'nav-roster', title: 'Daily Roster', category: 'Time', icon: ListChecks, path: '/admin/daily-roster', permission: 'attendance.view_all' },
      { id: 'nav-breaks', title: 'Break Types', category: 'Time', icon: Coffee, path: '/admin/break-types', permission: 'shift.view' },
      { id: 'nav-loc-alerts', title: 'Location Alerts', category: 'Time', icon: MapPin, path: '/admin/location-alerts', permission: 'attendance.view_all' },
      { id: 'nav-projects', title: 'Projects', category: 'Time', icon: FolderKanban, path: '/admin/projects', permission: 'attendance.view_all' },
      { id: 'nav-ts-policy', title: 'Timesheet Policy', category: 'Time', icon: Settings, path: '/admin/timesheet-policy', permission: 'shift.manage' },
      { id: 'nav-my-leaves', title: 'My Leave', category: 'Time', icon: Calendar, path: '/leaves', requiresEmployee: true },
      { id: 'nav-cal', title: 'Calendar', category: 'Time', icon: CalendarDays, path: '/calendar', requiresEmployee: true },
      { id: 'nav-timesheets', title: 'My Timesheets', category: 'Time', icon: Clock, path: '/timesheets', requiresEmployee: true },
      { id: 'nav-reviews', title: 'My Reviews', category: 'Time', icon: Star, path: '/reviews', requiresEmployee: true },
      { id: 'nav-my-letters', title: 'My Letters & Requests', category: 'Self Service', icon: FileText, path: '/my-letters', requiresEmployee: true },
      { id: 'nav-my-assets', title: 'My Assets', category: 'Self Service', icon: Package, path: '/my-assets', requiresEmployee: true },
      { id: 'nav-holidays', title: 'Holidays', category: 'Time', icon: CalendarDays, path: '/holidays', requiresEmployee: true },
      { id: 'nav-announcements', title: 'Announcements', category: 'Organization', icon: Bell, path: '/announcements', requiresEmployee: true },
      { id: 'nav-delegations', title: 'Approval Delegations', category: 'Management', icon: UserCheck, path: '/approval-delegations', requiresEmployee: true },

      // Admin Time
      { id: 'nav-adm-leaves', title: 'Leave Requests', category: 'Time', icon: Calendar, path: '/admin/leaves', permission: 'leave.view' },
      { id: 'nav-adm-leave-types', title: 'Leave Types', category: 'Time', icon: Settings, path: '/admin/leave-types', permission: 'leave_type.manage' },
      { id: 'nav-adm-wfh', title: 'WFH Requests', category: 'Time', icon: Network, path: '/admin/wfh', permission: ['wfh.view', 'wfh.request'] },
      { id: 'nav-adm-holidays', title: 'Admin Holidays', category: 'Time', icon: CalendarDays, path: '/admin/holidays', permission: 'holiday.view' },
      { id: 'nav-adm-shifts', title: 'Shifts', category: 'Time', icon: Clock, path: '/admin/shifts', permission: 'shift.view' },
      { id: 'nav-adm-work-cal', title: 'Working Calendar', category: 'Time', icon: CalendarDays, path: '/admin/working-calendar', permission: 'organization.update' },

      // Finance
      { id: 'nav-payslips', title: 'My Payslips', category: 'Finance', icon: FileText, path: '/payslips', requiresEmployee: true },
      { id: 'nav-payroll', title: 'Payroll', category: 'Finance', icon: DollarSign, path: '/payroll', permission: 'payroll.view' },
      { id: 'nav-salary-cfg', title: 'Salary Configuration', category: 'Finance', icon: Settings, path: '/admin/salary-configuration', permission: 'payroll.manage_compensation' },
      { id: 'nav-payroll-rep', title: 'Payroll Reports', category: 'Finance', icon: BarChart2, path: '/payroll/reports', permission: 'payroll.view_reports' },

      // Admin & Security
      { id: 'nav-control-center', title: 'Control Center', category: 'Admin', icon: SlidersHorizontal, path: '/admin/control-center', permission: 'organization.view' },
      { id: 'nav-adm-announcements', title: 'Admin Announcements', category: 'Admin', icon: Bell, path: '/admin/announcements', permission: 'announcement.view' },
      { id: 'nav-roles', title: 'Roles & Permissions', category: 'Admin', icon: ShieldAlert, path: '/admin/roles', permission: 'role.view' },
      { id: 'nav-audit', title: 'Audit Logs', category: 'Admin', icon: Settings, path: '/admin/audit-logs', permission: 'audit.view' },
      { id: 'nav-networks', title: 'Office Networks', category: 'Admin', icon: Network, path: '/admin/office-networks', permission: 'office_network.view' },
      { id: 'nav-profile', title: 'My Profile', category: 'Account', icon: Users, path: '/profile' },
    ],
    []
  );

  // Authorize navigation items strictly using existing permission state
  const authorizedNavItems = useMemo(() => {
    return allNavItems.filter((item) => {
      if (item.requiresEmployee && !hasEmployeeProfile) return false;
      if (!item.permission) return true;
      if (Array.isArray(item.permission)) {
        return item.permission.some((p) => hasPermission(p));
      }
      return hasPermission(item.permission);
    });
  }, [allNavItems, hasPermission, hasEmployeeProfile]);

  // Filter navigation items matching query
  const filteredNavItems = useMemo(() => {
    if (!query.trim()) return authorizedNavItems.slice(0, 10);
    const q = query.toLowerCase();
    return authorizedNavItems.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        item.category.toLowerCase().includes(q)
    );
  }, [authorizedNavItems, query]);

  // Employee quick lookup via existing API if user has employee.view permission
  const canSearchEmployees = hasPermission('employee.view');

  useEffect(() => {
    if (!canSearchEmployees || !query.trim() || query.trim().length < 2) {
      setEmployeeResults([]);
      setIsSearchingEmployees(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearchingEmployees(true);
      try {
        const token = localStorage.getItem('auth_token');
        const res = await fetch(`/api/v1/employees/?search=${encodeURIComponent(query.trim())}`, {
          headers: token ? { Authorization: `Token ${token}` } : {},
        });
        if (res.ok) {
          const data = await res.json();
          const items = Array.isArray(data) ? data : data.results || [];
          const mapped: PaletteItem[] = items.slice(0, 5).map((emp: any) => ({
            id: `emp-${emp.id}`,
            title: `${emp.first_name || ''} ${emp.last_name || ''}`.trim() || emp.email,
            subtitle: `${emp.employee_code || ''} · ${emp.designation_name || emp.department_name || 'Employee'}`,
            category: 'Employees',
            icon: Users,
            path: `/admin/employees/${emp.id}`,
          }));
          setEmployeeResults(mapped);
        }
      } catch (err) {
        console.error('Command palette employee search error:', err);
      } finally {
        setIsSearchingEmployees(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query, canSearchEmployees]);

  // Combined list of actionable results
  const combinedResults = useMemo(() => {
    return [...filteredNavItems, ...employeeResults];
  }, [filteredNavItems, employeeResults]);

  // Reset selectedIndex whenever results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [combinedResults]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Keyboard navigation inside palette
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % (combinedResults.length || 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + combinedResults.length) % (combinedResults.length || 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const selected = combinedResults[selectedIndex];
      if (selected) {
        navigate(selected.path);
        onClose();
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(4px)',
        zIndex: 2000,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        padding: '80px 16px 16px',
        animation: 'fadeIn 0.15s ease-out',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '620px',
          background: 'var(--color-bg-card, #ffffff)',
          borderRadius: 'var(--radius-xl, 16px)',
          boxShadow: '0 20px 40px rgba(0, 0, 0, 0.25), 0 0 0 1px var(--color-border, #cbd5e1)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: 'calc(100vh - 160px)',
        }}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Search Input Bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '16px 20px',
            borderBottom: '1px solid var(--color-border, #e2e8f0)',
          }}
        >
          <Search size={20} color="var(--color-primary, #0284c7)" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Type a command, page, or search employees..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              background: 'transparent',
              fontSize: '1.05rem',
              color: 'var(--color-text-main, #0f172a)',
            }}
          />
          {isSearchingEmployees && <Loader2 size={16} className="animate-spin text-muted" />}
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--color-text-muted, #64748b)',
              padding: 4,
            }}
            title="Close (Esc)"
          >
            <X size={18} />
          </button>
        </div>

        {/* Results List */}
        <div
          ref={listRef}
          style={{
            overflowY: 'auto',
            padding: '8px',
            display: 'flex',
            flexDirection: 'column',
            gap: '2px',
          }}
        >
          {combinedResults.length === 0 ? (
            <div style={{ padding: '32px 20px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
              No matching commands or navigation routes found.
            </div>
          ) : (
            combinedResults.map((item, idx) => {
              const isSelected = idx === selectedIndex;
              const Icon = item.icon;
              return (
                <div
                  key={item.id}
                  onClick={() => {
                    navigate(item.path);
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '10px 14px',
                    borderRadius: 'var(--radius-md, 8px)',
                    cursor: 'pointer',
                    background: isSelected
                      ? 'var(--color-primary-light, rgba(2, 132, 199, 0.1))'
                      : 'transparent',
                    color: isSelected
                      ? 'var(--color-primary, #0284c7)'
                      : 'var(--color-text-main, #0f172a)',
                    transition: 'background 0.1s ease',
                  }}
                >
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: '8px',
                      background: isSelected
                        ? 'var(--color-primary, #0284c7)'
                        : 'var(--color-bg-subtle, #f1f5f9)',
                      color: isSelected ? '#ffffff' : 'var(--color-text-muted, #64748b)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <Icon size={16} />
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, fontSize: '0.92rem' }}>{item.title}</div>
                    {item.subtitle && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                        {item.subtitle}
                      </div>
                    )}
                  </div>

                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      padding: '2px 8px',
                      borderRadius: '6px',
                      background: 'var(--color-bg-subtle, #f1f5f9)',
                      color: 'var(--color-text-muted, #64748b)',
                      letterSpacing: '0.02em',
                    }}
                  >
                    {item.category}
                  </span>

                  {isSelected && <ArrowRight size={14} color="var(--color-primary, #0284c7)" />}
                </div>
              );
            })
          )}
        </div>

        {/* Footer shortcuts hint */}
        <div
          style={{
            padding: '10px 18px',
            borderTop: '1px solid var(--color-border, #e2e8f0)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.75rem',
            color: 'var(--color-text-muted, #64748b)',
            background: 'var(--color-bg-subtle, #f8fafc)',
          }}
        >
          <div style={{ display: 'flex', gap: '14px' }}>
            <span>
              <kbd style={kbdStyle}>↑</kbd> <kbd style={kbdStyle}>↓</kbd> Navigate
            </span>
            <span>
              <kbd style={kbdStyle}>↵</kbd> Select
            </span>
            <span>
              <kbd style={kbdStyle}>ESC</kbd> Close
            </span>
          </div>
          <span>BEYONDSURE Command Palette</span>
        </div>
      </div>
    </div>
  );
};

const kbdStyle: React.CSSProperties = {
  background: 'var(--color-bg-card, #ffffff)',
  border: '1px solid var(--color-border, #cbd5e1)',
  borderRadius: '4px',
  padding: '1px 5px',
  fontSize: '0.7rem',
  boxShadow: '0 1px 1px rgba(0,0,0,0.1)',
};
