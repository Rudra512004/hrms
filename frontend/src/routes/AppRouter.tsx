import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';

// Layouts
import { AppLayout } from '../layouts/AppLayout';
import { AuthLayout } from '../layouts/AuthLayout';

// Pages
import { DashboardPage } from '../pages/DashboardPage';
import { LoginPage } from '../pages/LoginPage';
import { RegisterOrganizationPage } from '../pages/RegisterOrganizationPage';
import { ForgotPasswordPage } from '../pages/ForgotPasswordPage';
import { ResetPasswordPage } from '../pages/ResetPasswordPage';
import { ActivateAccountPage } from '../pages/ActivateAccountPage';
import { PendingActivationPage } from '../pages/PendingActivationPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { ProfilePage } from '../pages/ProfilePage';
import { AttendancePage } from '../pages/AttendancePage';
import { AttendanceManagementPage } from '../pages/admin/AttendanceManagementPage';
import { LeavePage } from '../pages/LeavePage';
import { CalendarPage } from '../pages/CalendarPage';
import { PayrollPage } from '../pages/PayrollPage';
import { PayrollReportsPage } from '../pages/PayrollReportsPage';
import { SalaryConfigurationPage } from '../pages/admin/SalaryConfigurationPage';
import { MyPayslipsPage } from '../pages/MyPayslipsPage';

// Admin Pages
import { AdminLeavePage } from '../pages/admin/AdminLeavePage';
import { OfficeNetworksPage } from '../pages/admin/OfficeNetworksPage';
import { WfhRequestsPage } from '../pages/admin/WfhRequestsPage';
import { EmployeesPage } from '../pages/admin/EmployeesPage';
import { EmployeeProfilePage } from '../pages/admin/EmployeeProfilePage';
import { EmployeeAccessPage } from '../pages/admin/EmployeeAccessPage';
import { AuditLogsPage } from '../pages/admin/AuditLogsPage';
import { OrganizationControlCenterPage } from '../pages/admin/OrganizationControlCenterPage';
import { AnnouncementsPage } from '../pages/admin/AnnouncementsPage';
import { DailyRosterPage } from '../pages/admin/DailyRosterPage';
import { BreakTypesPage } from '../pages/admin/BreakTypesPage';
import { LocationAlertsPage } from '../pages/admin/LocationAlertsPage';
import { ProjectsPage } from '../pages/admin/ProjectsPage';
import { TimesheetPolicyPage } from '../pages/admin/TimesheetPolicyPage';
import { TimesheetsPage } from '../pages/TimesheetsPage';
import { ReviewsPage } from '../pages/ReviewsPage';
import { ManagerReviewsPage } from '../pages/admin/ManagerReviewsPage';
import { MyAssetsPage } from '../pages/MyAssetsPage';
import { EmployeeInformationPage } from '../pages/EmployeeInformationPage';
import { AdminLeaveTypesPage } from '../pages/admin/AdminLeaveTypesPage';
import { RolesPage } from '../pages/admin/RolesPage';
import { RolePermissionsPage } from '../pages/admin/RolePermissionsPage';
import { OrganizationsPage } from '../pages/admin/organization/OrganizationsPage';
import { DepartmentsPage } from '../pages/admin/organization/DepartmentsPage';
import { TeamsPage } from '../pages/admin/organization/TeamsPage';
import { DesignationsPage } from '../pages/admin/organization/DesignationsPage';
import { BranchesPage } from '../pages/admin/organization/BranchesPage';
import { OrganizationLaunchpadPage } from '../pages/admin/organization/OrganizationLaunchpadPage';
import { HolidaysPage } from '../pages/admin/HolidaysPage';
import { ShiftsPage } from '../pages/admin/ShiftsPage';
import { AssetsPage } from '../pages/admin/AssetsPage';
import { WorkingCalendarPage } from '../pages/admin/WorkingCalendarPage';
import { AttendancePolicyPage } from '../pages/admin/AttendancePolicyPage';
import { CandidatesPage } from '../pages/admin/CandidatesPage';
import { CandidateDetailPage } from '../pages/admin/CandidateDetailPage';
import { LetterTemplatesPage } from '../pages/admin/LetterTemplatesPage';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { OnboardingRoute } from '../components/OnboardingRoute';
import { OnboardingLayout } from '../layouts/OnboardingLayout';
import { OnboardingActivatePage } from '../pages/onboarding/OnboardingActivatePage';
import { OnboardingOverviewPage } from '../pages/onboarding/OnboardingOverviewPage';
import { OnboardingProfilePage } from '../pages/onboarding/OnboardingProfilePage';
import { OnboardingDocumentsPage } from '../pages/onboarding/OnboardingDocumentsPage';
import { OnboardingLettersPage } from '../pages/onboarding/OnboardingLettersPage';

export const AppRouter: React.FC = () => {
  return (
    <Routes>

      {/* Public Routes */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterOrganizationPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/reset-password/:uid/:token" element={<ResetPasswordPage />} />
        <Route path="/activate" element={<ActivateAccountPage />} />
        <Route path="/activate/:uid/:token" element={<ActivateAccountPage />} />
        <Route path="/pending-activation" element={<PendingActivationPage />} />
      </Route>

      {/* Protected Routes */}
      <Route element={<AppLayout />}>
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          {/* Employee Self-Service Routes — require an employee profile */}
          <Route element={<ProtectedRoute requiresEmployee />}>
            <Route path="/attendance" element={<AttendancePage />} />
            <Route path="/leaves" element={<LeavePage />} />
            <Route path="/calendar" element={<CalendarPage />} />
            <Route path="/payslips" element={<MyPayslipsPage />} />
            <Route path="/timesheets" element={<TimesheetsPage />} />
            <Route path="/reviews" element={<ReviewsPage />} />
            <Route path="/my-assets" element={<MyAssetsPage />} />
            <Route path="/my-letters" element={<EmployeeInformationPage mode="letters" />} />
            <Route path="/holidays" element={<EmployeeInformationPage mode="holidays" />} />
            <Route path="/announcements" element={<EmployeeInformationPage mode="announcements" />} />
          </Route>
          <Route path="/profile" element={<ProfilePage />} />


          <Route element={<ProtectedRoute requiredPermission="payroll.view" />}>
            <Route path="/payroll" element={<PayrollPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="payroll.view_reports" />}>
            <Route path="/payroll/reports" element={<PayrollReportsPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="payroll.manage_compensation" />}>
            <Route path="/admin/salary-configuration" element={<SalaryConfigurationPage />} />
          </Route>

          {/* Admin Routes */}
          <Route path="/admin" element={<Navigate to="/dashboard" replace />} />

          <Route element={<ProtectedRoute requiredPermission="employee.view" />}>
            <Route path="/admin/employees" element={<EmployeesPage />} />
            <Route path="/admin/employees/:id" element={<EmployeeProfilePage />} />
            <Route path="/admin/employees/:employeeId/access" element={<EmployeeAccessPage />} />
          </Route>
          
          <Route element={<ProtectedRoute requiredPermission="employee.update" />}>
            <Route path="/admin/reviews" element={<ManagerReviewsPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="asset.view" />}>
            <Route path="/admin/assets" element={<AssetsPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="attendance.view_all" />}>
            <Route path="/admin/attendance" element={<AttendanceManagementPage />} />
            <Route path="/admin/daily-roster" element={<DailyRosterPage />} />
            <Route path="/admin/location-alerts" element={<LocationAlertsPage />} />
            <Route path="/admin/projects" element={<ProjectsPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="shift.view" />}>
            <Route path="/admin/break-types" element={<BreakTypesPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="shift.manage" />}>
            <Route path="/admin/timesheet-policy" element={<TimesheetPolicyPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="office_network.view" />}>
            <Route path="/admin/office-networks" element={<OfficeNetworksPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="organization.view" />}>
            <Route path="/admin/organizations" element={<OrganizationsPage />} />
            <Route path="/admin/control-center" element={<OrganizationControlCenterPage />} />
          </Route>
          <Route element={<ProtectedRoute requiredPermission="announcement.view" />}><Route path="/admin/announcements" element={<AnnouncementsPage />} /></Route>


          <Route path="/admin/organization-launchpad" element={<OrganizationLaunchpadPage />} />

          <Route element={<ProtectedRoute requiredPermission="department.view" />}>
            <Route path="/admin/departments" element={<DepartmentsPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="team.view" />}>
            <Route path="/admin/teams" element={<TeamsPage />} />
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

          <Route element={<ProtectedRoute requiredPermission="organization.update" />}>
            <Route path="/admin/working-calendar" element={<WorkingCalendarPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="branch.view" />}>
            <Route path="/admin/attendance-policy" element={<AttendancePolicyPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission={['wfh.view', 'wfh.request']} />}>
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

          {/* Candidate & Onboarding — templates MUST come before :id param route */}
          <Route element={<ProtectedRoute requiredPermission="letter.view" />}>
            <Route path="/admin/candidates/templates" element={<LetterTemplatesPage />} />
          </Route>

          <Route element={<ProtectedRoute requiredPermission="candidate.view" />}>
            <Route path="/admin/candidates" element={<CandidatesPage />} />
            <Route path="/admin/candidates/:id" element={<CandidateDetailPage />} />
          </Route>
        </Route>

        {/* Catch-all within AppLayout */}
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      {/* Candidate Onboarding Portal — public activation, then guarded portal */}
      <Route path="/onboarding/activate" element={<OnboardingActivatePage />} />

      <Route element={<OnboardingLayout />}>
        <Route element={<OnboardingRoute />}>
          <Route path="/onboarding" element={<OnboardingOverviewPage />} />
          <Route path="/onboarding/profile" element={<OnboardingProfilePage />} />
          <Route path="/onboarding/documents" element={<OnboardingDocumentsPage />} />
          <Route path="/onboarding/letters" element={<OnboardingLettersPage />} />
        </Route>
      </Route>
    </Routes>
  );
};
