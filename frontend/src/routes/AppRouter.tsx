import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';

// Layouts
import { AppLayout } from '../layouts/AppLayout';
import { AuthLayout } from '../layouts/AuthLayout';

// Pages
import { DashboardPage } from '../pages/DashboardPage';
import { LoginPage } from '../pages/LoginPage';
import { ForgotPasswordPage } from '../pages/ForgotPasswordPage';
import { ResetPasswordPage } from '../pages/ResetPasswordPage';
import { PendingActivationPage } from '../pages/PendingActivationPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { ProfilePage } from '../pages/ProfilePage';
import { AttendancePage } from '../pages/AttendancePage';
import { LeavePage } from '../pages/LeavePage';

// Admin Pages
import { AdminDashboardPage } from '../pages/admin/AdminDashboardPage';
import { AdminLeavePage } from '../pages/admin/AdminLeavePage';
import { OfficeNetworksPage } from '../pages/admin/OfficeNetworksPage';
import { WfhRequestsPage } from '../pages/admin/WfhRequestsPage';
import { EmployeesPage } from '../pages/admin/EmployeesPage';
import { EmployeeAccessPage } from '../pages/admin/EmployeeAccessPage';
import { AuditLogsPage } from '../pages/admin/AuditLogsPage';
import { AdminLeaveTypesPage } from '../pages/admin/AdminLeaveTypesPage';
import { ProtectedRoute } from '../components/ProtectedRoute';

export const AppRouter: React.FC = () => {
  return (
    <Routes>

      {/* Public Routes */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password/:uid/:token" element={<ResetPasswordPage />} />
        <Route path="/pending-activation" element={<PendingActivationPage />} />
      </Route>

      {/* Protected Routes */}
      <Route element={<AppLayout />}>
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/attendance" element={<AttendancePage />} />
          <Route path="/leaves" element={<LeavePage />} />
          <Route path="/profile" element={<ProfilePage />} />

          {/* Admin Routes */}
          <Route path="/admin" element={<AdminDashboardPage />} />

          <Route element={<ProtectedRoute requiredPermission="employee.view" />}>
            <Route path="/admin/employees" element={<EmployeesPage />} />
            <Route path="/admin/employees/:employeeId/access" element={<EmployeeAccessPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="office_network.view" />}>
            <Route path="/admin/office-networks" element={<OfficeNetworksPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="wfh.view" />}>
            <Route path="/admin/wfh" element={<WfhRequestsPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="leave_type.manage" />}>
            <Route path="/admin/leaves" element={<AdminLeavePage />} />
            <Route path="/admin/leave-types" element={<AdminLeaveTypesPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="audit.view" />}>
            <Route path="/admin/audit-logs" element={<AuditLogsPage />} />
          </Route>
        </Route>

        {/* Catch-all within AppLayout */}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
};
