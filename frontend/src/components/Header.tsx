import React from 'react';
import { Menu, Search, Bell, User, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

interface HeaderProps {
  toggleSidebar: () => void;
  isSidebarOpen: boolean;
}

export const Header: React.FC<HeaderProps> = ({ toggleSidebar }) => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const getInitials = (firstName: string, lastName: string) => {
    return `${firstName?.charAt(0) || ''}${lastName?.charAt(0) || ''}`.toUpperCase();
  };

  return (
    <header className="app-header">
      <div className="flex items-center gap-4">
        <button className="header-toggle" onClick={toggleSidebar}>
          <Menu size={20} />
        </button>
        <div className="flex items-center gap-2 hide-on-mobile">
          <Search size={18} className="text-muted" />
          <input 
            type="text" 
            placeholder="Search..." 
            style={{ 
              border: 'none', 
              background: 'transparent', 
              outline: 'none', 
              fontSize: '0.875rem' 
            }}
          />
        </div>
      </div>
      
      <div className="flex items-center gap-4">
        <button className="btn-ghost" style={{ padding: '8px', borderRadius: '50%' }}>
          <Bell size={20} />
        </button>
        
        <div className="flex items-center gap-2">
          <div className="hide-on-mobile" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
            <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>
              {user ? `${user.firstName} ${user.lastName}` : 'Loading...'}
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
              {user ? user.email : ''}
            </span>
          </div>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            backgroundColor: 'var(--color-primary-light)',
            color: 'var(--color-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 600,
            fontSize: '0.875rem'
          }}>
            {user ? getInitials(user.firstName, user.lastName) : <User size={18} />}
          </div>
          <button 
            className="btn-ghost" 
            style={{ padding: '8px', borderRadius: '50%' }} 
            onClick={handleLogout} 
            title="Logout"
          >
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </header>
  );
};
