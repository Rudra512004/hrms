import React, { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { Header } from '../components/Header';

export const AppLayout: React.FC = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    const saved = localStorage.getItem('beyondsure-sidebar');
    return saved !== null ? saved === 'true' : true;
  });
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 992;
      setIsMobile(mobile);
      if (mobile) {
        setIsSidebarOpen(false);
      } else {
        setIsSidebarOpen(true);
      }
    };
    window.addEventListener('resize', handleResize);
    handleResize(); // run once
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const toggleSidebar = () => {
    const newState = !isSidebarOpen;
    setIsSidebarOpen(newState);
    if (!isMobile) {
      localStorage.setItem('beyondsure-sidebar', String(newState));
    }
  };
  const closeSidebarOnMobile = () => {
    if (isMobile) {
      setIsSidebarOpen(false);
    }
  };

  return (
    <div className="app-wrapper">
      {/* Mobile overlay backdrop */}
      {isMobile && isSidebarOpen && (
        <div
          className="sidebar-backdrop"
          onClick={closeSidebarOnMobile}
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.4)',
            backdropFilter: 'blur(2px)',
            zIndex: 95,
            transition: 'opacity 0.3s ease'
          }}
        />
      )}

      <Sidebar isOpen={isSidebarOpen} isMobile={isMobile} onNavigate={closeSidebarOnMobile} />

      <div className={`app-main ${!isMobile ? (isSidebarOpen ? 'sidebar-open' : 'sidebar-closed') : 'sidebar-mobile'}`}>
        <Header toggleSidebar={toggleSidebar} isSidebarOpen={isSidebarOpen} />
        <main className="app-content animate-fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
