import React from 'react';
import { Menu, Search, Bell, User } from 'lucide-react';

interface HeaderProps {
  toggleSidebar: () => void;
  isSidebarOpen: boolean;
}

const styles = {
  header: (isOpen: boolean) => ({
    height: 'var(--header-height)',
    backgroundColor: 'var(--color-bg-header)',
    borderBottom: '1px solid var(--color-border)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 var(--spacing-lg)',
    position: 'fixed' as const,
    top: 0,
    right: 0,
    left: isOpen ? 'var(--sidebar-width)' : 'var(--sidebar-width-collapsed)',
    zIndex: 90,
    transition: 'left 0.3s ease',
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
    backgroundColor: 'var(--color-bg-body)',
    borderRadius: '20px',
    padding: '0.4rem 1rem',
    marginLeft: 'var(--spacing-md)',
  },
  searchInput: {
    border: 'none',
    background: 'none',
    outline: 'none',
    marginLeft: 'var(--spacing-sm)',
    fontSize: '0.9rem',
    width: '200px',
  },
  rightSide: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-lg)',
  },
  iconBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--color-text-muted)',
    position: 'relative' as const,
  },
  badge: {
    position: 'absolute' as const,
    top: '-4px',
    right: '-4px',
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
  },
  avatar: {
    width: '32px',
    height: '32px',
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
  }
};

export const Header: React.FC<HeaderProps> = ({ toggleSidebar, isSidebarOpen }) => {
  return (
    <header style={styles.header(isSidebarOpen)}>
      <div style={styles.leftSide}>
        <button style={styles.toggleBtn} onClick={toggleSidebar}>
          <Menu size={24} />
        </button>
        <div style={styles.searchBox} className="desktop-only">
          <Search size={18} color="var(--color-text-muted)" />
          <input 
            type="text" 
            placeholder="Search here" 
            style={styles.searchInput}
          />
        </div>
      </div>
      
      <div style={styles.rightSide}>
        <button style={styles.iconBtn}>
          <Bell size={20} />
          <span style={styles.badge}>3</span>
        </button>
        
        <div style={styles.userArea}>
          <div style={styles.avatar}>
            <User size={18} />
          </div>
          <span style={styles.userName}>Admin User</span>
        </div>
      </div>
    </header>
  );
};
