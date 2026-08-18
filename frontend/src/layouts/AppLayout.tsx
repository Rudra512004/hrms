import React, { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { Header } from '../components/Header';
import { Breadcrumb } from '../components/Breadcrumb';

const styles = {
  appWrapper: {
    display: 'flex',
    minHeight: '100vh',
    width: '100%',
    backgroundColor: 'var(--color-bg-body)',
  },
  mainContent: (isSidebarOpen: boolean) => ({
    flex: 1,
    marginLeft: isSidebarOpen ? 'var(--sidebar-width)' : 'var(--sidebar-width-collapsed)',
    padding: 'calc(62px + 2rem) 1.5rem 1.5rem 1.5rem', // 62px header + padding
    transition: 'margin-left 0.3s ease',
    minHeight: '100vh',
    width: `calc(100% - ${isSidebarOpen ? 'var(--sidebar-width)' : 'var(--sidebar-width-collapsed)'})`,
  }),
};

export const AppLayout: React.FC = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // Responsive behavior
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 992) {
        setIsSidebarOpen(false);
      } else {
        setIsSidebarOpen(true);
      }
    };

    window.addEventListener('resize', handleResize);
    handleResize(); // Initial check

    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  return (
    <div style={styles.appWrapper}>
      <Sidebar isOpen={isSidebarOpen} />
      <Header toggleSidebar={toggleSidebar} isSidebarOpen={isSidebarOpen} />
      
      <main style={styles.mainContent(isSidebarOpen)}>
        <Breadcrumb />
        <Outlet />
      </main>
    </div>
  );
};
