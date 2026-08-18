import React, { useState, useEffect } from 'react';
import { Menu, Search, Bell, User, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { authService, type User as AuthUser } from '../services/auth';

interface HeaderProps {
  toggleSidebar: () => void;
  isSidebarOpen: boolean;
}

const styles = {
  header: (isOpen: boolean) => ({
    height: '62px',
    backgroundColor: 'var(--color-bg-header)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 var(--spacing-md)',
    position: 'fixed' as const,
    top: '1rem',
    right: '1.5rem',
    left: isOpen ? 'calc(var(--sidebar-width) + 1.5rem)' : 'calc(var(--sidebar-width-collapsed) + 1.5rem)',
    zIndex: 90,
    transition: 'left 0.3s ease',
    borderRadius: 'var(--radius-md)',
    boxShadow: 'var(--shadow-sm)',
  }),
  leftSide: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-md)',
  },
  toggleBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--color-text-main)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 'var(--spacing-xs)',
    borderRadius: 'var(--radius-sm)',
  },
  searchBox: {
    display: 'flex',
    alignItems: 'center',
    backgroundColor: 'transparent',
    padding: '0.4rem',
  },
  searchInput: {
    border: 'none',
    background: 'none',
    outline: 'none',
    marginLeft: 'var(--spacing-sm)',
    fontSize: '0.95rem',
    width: '200px',
    color: 'var(--color-text-main)',
  },
  rightSide: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-md)',
  },
  iconBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--color-text-main)',
    position: 'relative' as const,
    cursor: 'pointer',
    padding: '8px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '50%',
  },
  badge: {
    position: 'absolute' as const,
    top: '2px',
    right: '2px',
    backgroundColor: 'var(--color-status-danger)',
    color: '#fff',
    fontSize: '0.65rem',
    fontWeight: 'bold',
    width: '16px',
    height: '16px',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  userArea: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-sm)',
    cursor: 'pointer',
    paddingLeft: 'var(--spacing-sm)',
  },
  avatar: {
    width: '38px',
    height: '38px',
    borderRadius: '50%',
    backgroundColor: 'var(--color-primary)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#fff',
  },
  userName: {
    fontSize: '0.9rem',
    fontWeight: 500,
    color: 'var(--color-text-main)',
  }
};

export const Header: React.FC<HeaderProps> = ({ toggleSidebar, isSidebarOpen }) => {
  const navigate = useNavigate();
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    authService.getCurrentUser().then(setUser);
  }, []);

  const handleLogout = async () => {
    await authService.logout();
    navigate('/login');
  };

  const getInitials = (firstName: string, lastName: string) => {
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  };

  return (
    <header style={styles.header(isSidebarOpen)}>
      <div style={styles.leftSide}>
        <button style={styles.toggleBtn} onClick={toggleSidebar}>
          <Menu size={24} />
        </button>
        <div style={styles.searchBox} className="desktop-only">
          <Search size={20} color="var(--color-text-main)" />
          <input 
            type="text" 
            placeholder="Search (Ctrl+/)" 
            style={styles.searchInput}
          />
        </div>
      </div>
      
      <div style={styles.rightSide}>
        <button style={styles.iconBtn}>
          <Bell size={22} />
          {/* <span style={styles.badge}>4</span> */}
        </button>
        
        <div style={styles.userArea}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', marginRight: '8px' }}>
            <span style={styles.userName}>{user ? `${user.firstName} ${user.lastName}` : 'Loading...'}</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
              {user ? (user as any).isStaff ? 'Admin' : 'Employee' : ''}
            </span>
          </div>
          <div style={styles.avatar}>
            {user ? (
              <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>{getInitials(user.firstName, user.lastName)}</span>
            ) : (
              <User size={20} />
            )}
          </div>
          <button style={{...styles.iconBtn, marginLeft: '4px'}} onClick={handleLogout} title="Logout">
            <LogOut size={20} />
          </button>
        </div>
      </div>
    </header>
  );
};
