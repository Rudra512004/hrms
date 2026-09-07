import React, { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { Header } from '../components/Header';
import { Breadcrumb } from '../components/Breadcrumb';

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
    <div className="app-wrapper">
      <Sidebar isOpen={isSidebarOpen} />
      
      <div className={`app-main ${isSidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
        <Header toggleSidebar={toggleSidebar} isSidebarOpen={isSidebarOpen} />
        
        <main className="app-content">
          <Breadcrumb />
          <Outlet />
        </main>
      </div>
    </div>
  );
};
