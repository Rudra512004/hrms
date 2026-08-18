import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';

// Layouts
import { AppLayout } from '../layouts/AppLayout';
import { AuthLayout } from '../layouts/AuthLayout';

// Pages
import { DashboardPage } from '../pages/DashboardPage';
import { LoginPage } from '../pages/LoginPage';
import { PendingActivationPage } from '../pages/PendingActivationPage';
import { NotFoundPage } from '../pages/NotFoundPage';

export const AppRouter: React.FC = () => {
  return (
    <Routes>
      {/* Public Routes */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/pending-activation" element={<PendingActivationPage />} />
      </Route>

      {/* Protected Routes (Simulated) */}
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        
        {/* Module Placeholders */}
        <Route path="/employees" element={<div>Employees Module Placeholder</div>} />
        <Route path="/attendance" element={<div>Attendance Module Placeholder</div>} />
        <Route path="/leave" element={<div>Leave Module Placeholder</div>} />
        <Route path="/payroll" element={<div>Payroll Module Placeholder</div>} />
        <Route path="/users" element={<div>Users Module Placeholder</div>} />
        <Route path="/roles" element={<div>Roles Module Placeholder</div>} />
        <Route path="/organization" element={<div>Organization Module Placeholder</div>} />
        <Route path="/audit-logs" element={<div>Audit Logs Placeholder</div>} />
        <Route path="/settings" element={<div>Settings Placeholder</div>} />

        {/* Catch-all within AppLayout */}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
};
