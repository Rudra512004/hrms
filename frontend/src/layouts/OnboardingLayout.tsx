/**
 * OnboardingLayout — the restricted portal shell for candidates.
 *
 * Security: This layout is ONLY accessible to users whose account
 * is linked to a Candidate record (user.candidate != null).
 * It shares auth token with the main app but enforces the
 * candidate identity at the route level via OnboardingRoute.
 *
 * Candidates who visit /onboarding/* will NOT see any of the
 * HR/Employee/Admin chrome.
 */
import React from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { LogOut, FileText, User, Upload, CheckCircle } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export const OnboardingLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navItems = [
    { path: '/onboarding',           label: 'Overview',   icon: CheckCircle, end: true },
    { path: '/onboarding/profile',   label: 'My Profile', icon: User },
    { path: '/onboarding/documents', label: 'Documents',  icon: Upload },
    { path: '/onboarding/letters',   label: 'My Letters', icon: FileText },
  ];

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--color-bg-body)', fontFamily: 'Inter, system-ui, sans-serif' }}>
      {/* Sidebar */}
      <aside style={{
        width: '220px', minHeight: '100vh',
        background: 'var(--color-bg-card)',
        borderRight: '1px solid var(--color-border)',
        display: 'flex', flexDirection: 'column',
        flexShrink: 0,
      }}>
        {/* Brand */}
        <div style={{
          padding: '20px 16px', borderBottom: '1px solid var(--color-border)',
        }}>
          <div style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
            Candidate Portal
          </div>
          <div style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--color-text-main)' }}>
            Onboarding
          </div>
        </div>

        {/* Nav */}
        <nav style={{ padding: '12px 8px', flex: 1 }}>
          {navItems.map(item => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.end}
                style={({ isActive }) => ({
                  display: 'flex', alignItems: 'center', gap: '10px',
                  padding: '10px 10px', borderRadius: '8px',
                  marginBottom: '2px', textDecoration: 'none',
                  color: isActive ? 'var(--color-primary)' : 'var(--color-text-muted)',
                  background: isActive ? 'var(--color-primary-alpha, rgba(59,130,246,0.08))' : 'transparent',
                  fontWeight: isActive ? 600 : 400,
                  fontSize: '0.875rem',
                  transition: 'all 0.15s',
                })}
              >
                <Icon size={16} />
                {item.label}
              </NavLink>
            );
          })}
        </nav>

        {/* User + logout */}
        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--color-border)' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {user?.email}
          </div>
          <button
            onClick={handleLogout}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '8px 10px', width: '100%', border: 'none',
              borderRadius: '8px', background: 'none',
              color: 'var(--color-text-muted)', cursor: 'pointer',
              fontSize: '0.85rem', fontWeight: 500,
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-bg-body)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'none')}
          >
            <LogOut size={14} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, minWidth: 0, padding: '32px 24px', overflowY: 'auto' }}>
        <Outlet />
      </main>
    </div>
  );
};
