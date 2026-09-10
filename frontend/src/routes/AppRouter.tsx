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
import { AttendanceManagementPage } from '../pages/admin/AttendanceManagementPage';
import { LeavePage } from '../pages/LeavePage';
import { PayrollPage } from '../pages/PayrollPage';
import { PayrollReportsPage } from '../pages/PayrollReportsPage';
import { MyPayslipsPage } from '../pages/MyPayslipsPage';

// Admin Pages
import { AdminLeavePage } from '../pages/admin/AdminLeavePage';
import { OfficeNetworksPage } from '../pages/admin/OfficeNetworksPage';
import { WfhRequestsPage } from '../pages/admin/WfhRequestsPage';
import { EmployeesPage } from '../pages/admin/EmployeesPage';
import { EmployeeProfilePage } from '../pages/admin/EmployeeProfilePage';
import { EmployeeAccessPage } from '../pages/admin/EmployeeAccessPage';
import { AuditLogsPage } from '../pages/admin/AuditLogsPage';
import { AdminLeaveTypesPage } from '../pages/admin/AdminLeaveTypesPage';
import { RolesPage } from '../pages/admin/RolesPage';
import { RolePermissionsPage } from '../pages/admin/RolePermissionsPage';
import { OrganizationsPage } from '../pages/admin/organization/OrganizationsPage';
import { DepartmentsPage } from '../pages/admin/organization/DepartmentsPage';
import { DesignationsPage } from '../pages/admin/organization/DesignationsPage';
import { BranchesPage } from '../pages/admin/organization/BranchesPage';
import { HolidaysPage } from '../pages/admin/HolidaysPage';
import { ShiftsPage } from '../pages/admin/ShiftsPage';
import { AssetsPage } from '../pages/admin/AssetsPage';
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
          <Route path="/payslips" element={<MyPayslipsPage />} />
          <Route path="/profile" element={<ProfilePage />} />


          <Route element={<ProtectedRoute requiredPermission="payroll.view" />}>
            <Route path="/payroll" element={<PayrollPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="payroll.view_reports" />}>
            <Route path="/payroll/reports" element={<PayrollReportsPage />} />
          </Route>

          {/* Admin Routes */}
          <Route path="/admin" element={<Navigate to="/dashboard" replace />} />

          <Route element={<ProtectedRoute requiredPermission="employee.view" />}>
            <Route path="/admin/employees" element={<EmployeesPage />} />
            <Route path="/admin/employees/:id" element={<EmployeeProfilePage />} />
            <Route path="/admin/employees/:employeeId/access" element={<EmployeeAccessPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="asset.view" />}>
            <Route path="/admin/assets" element={<AssetsPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="attendance.view_all" />}>
            <Route path="/admin/attendance" element={<AttendanceManagementPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="office_network.view" />}>
            <Route path="/admin/office-networks" element={<OfficeNetworksPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="organization.view" />}>
            <Route path="/admin/organizations" element={<OrganizationsPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="department.view" />}>
            <Route path="/admin/departments" element={<DepartmentsPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="designation.view" />}>
            <Route path="/admin/designations" element={<DesignationsPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="branch.view" />}>
            <Route path="/admin/branches" element={<BranchesPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="holiday.view" />}>
            <Route path="/admin/holidays" element={<HolidaysPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="shift.view" />}>
            <Route path="/admin/shifts" element={<ShiftsPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="wfh.view" />}>
            <Route path="/admin/wfh" element={<WfhRequestsPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="leave.view" />}>
            <Route path="/admin/leaves" element={<AdminLeavePage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="leave_type.manage" />}>
            <Route path="/admin/leave-types" element={<AdminLeaveTypesPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="role.view" />}>
            <Route path="/admin/roles" element={<RolesPage />} />
            <Route path="/admin/roles/:roleId/permissions" element={<RolePermissionsPage />} />
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
