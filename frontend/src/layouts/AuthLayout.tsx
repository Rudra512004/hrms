import React from 'react';
import { Outlet } from 'react-router-dom';

/**
 * AuthLayout — transparent full-screen shell for unauthenticated pages.
 * The global watermark sits at z-index:0; this wrapper sits at z-index:1.
 * Login uses its own two-panel layout; this shell must NOT constrain width.
 */
export const AuthLayout: React.FC = () => {
  return (
    <div
      style={{
        minHeight: '100vh',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'transparent',
        position: 'relative',
        zIndex: 1,
      }}
    >
      <Outlet />
    </div>
  );
};
