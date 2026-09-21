import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { EmployeeProfilePage } from '../EmployeeProfilePage';
import {
  employeeManagementService,
  ApiError,
  type EmployeeLifecycleEvent,
} from '../../../services/employeeManagement';
import {
  organizationService,
  type Branch,
  type Department,
  type Team,
  type Designation,
} from '../../../services/organization';
import * as AuthContextModule from '../../../contexts/AuthContext';
import { type EmployeeProfile } from '../../../services/employee';

// Mock Services
vi.mock('../../../services/employeeManagement', () => ({
  employeeManagementService: {
    getEmployee: vi.fn(),
    listEmployees: vi.fn(),
    transferEmployee: vi.fn(),
    promoteEmployee: vi.fn(),
    exitEmployee: vi.fn(),
    changeEmploymentStatus: vi.fn(),
    reactivateEmployee: vi.fn(),
    getLifecycleHistory: vi.fn(),
    updateEmployee: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number;
    errorData: any;
    constructor(response: any, errorData: any) {
      super(errorData?.detail || errorData?.message || 'API Request Failed');
      this.status = response.status;
      this.errorData = errorData;
    }
  },
}));

vi.mock('../../../services/organization', () => ({
  organizationService: {
    listBranches: vi.fn(),
    listDepartments: vi.fn(),
    listTeams: vi.fn(),
    listDesignations: vi.fn(),
  },
}));

vi.mock('../../../services/employeeDocuments', () => ({
  employeeDocumentService: {
    listDocuments: vi.fn().mockResolvedValue([]),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
    downloadDocument: vi.fn(),
    previewDocument: vi.fn(),
  },
}));

vi.mock('../../../services/assets', () => ({
  assetService: {
    getAssets: vi.fn().mockResolvedValue([]),
    getMyAssets: vi.fn().mockResolvedValue([]),
  },
}));

const mockBranches: Branch[] = [
  { id: 1, organization: 1, name: 'Mumbai HQ', address: 'Nariman Point', latitude: '18.9', longitude: '72.8', radius: 100, is_active: true, created_at: '2026-01-01', updated_at: '2026-01-01' },
  { id: 2, organization: 1, name: 'Pune Tech Park', address: 'Hinjawadi', latitude: '18.5', longitude: '73.7', radius: 100, is_active: true, created_at: '2026-01-01', updated_at: '2026-01-01' },
];

const mockDepartmentsBranch1: Department[] = [
  { id: 10, organization: 1, branch: 1, name: 'Engineering', description: 'Eng Dept', is_active: true },
  { id: 11, organization: 1, branch: 1, name: 'Product', description: 'Product Dept', is_active: true },
];

const mockDepartmentsBranch2: Department[] = [
  { id: 20, organization: 1, branch: 2, name: 'Operations', description: 'Ops Dept', is_active: true },
];

const mockTeamsDept10: Team[] = [
  { id: 100, department: 10, name: 'Backend Team', description: 'Backend Devs', is_active: true },
  { id: 101, department: 10, name: 'Frontend Team', description: 'Frontend Devs', is_active: true },
];

const mockTeamsDept20: Team[] = [
  { id: 200, department: 20, name: 'Ops Core', description: 'Ops Core', is_active: true },
];

const mockDesignations: Designation[] = [
  { id: 50, organization: 1, name: 'Software Engineer', description: 'SWE', is_active: true },
  { id: 51, organization: 1, name: 'Senior Software Engineer', description: 'Sr SWE', is_active: true },
  { id: 52, organization: 1, name: 'Staff Engineer', description: 'Staff', is_active: true },
];

const mockActiveEmployee: EmployeeProfile = {
  id: 1,
  email: 'alice@company.com',
  first_name: 'Alice',
  last_name: 'Smith',
  employee_code: 'EMP001',
  status: 'active',
  employment_status: 'active',
  branch: 1,
  branch_name: 'Mumbai HQ',
  department: 10,
  department_name: 'Engineering',
  team: 100,
  team_name: 'Backend Team',
  designation: 50,
  designation_name: 'Software Engineer',
  reporting_manager: null,
  joining_date: '2026-01-01',
  phone_number: '1234567890',
  address: '123 Tech Street',
};

const mockExitedEmployee: EmployeeProfile = {
  ...mockActiveEmployee,
  id: 2,
  employee_code: 'EMP002',
  status: 'inactive',
  employment_status: 'exited',
  exit_date: '2026-06-30',
  exit_reason: 'Resigned for personal reasons',
};

const mockLifecycleEvents: EmployeeLifecycleEvent[] = [
  {
    id: 1,
    employee: 1,
    event_type: 'transfer',
    event_type_display: 'Transfer',
    from_status: 'active',
    to_status: 'active',
    from_branch: 1,
    from_branch_name: 'Mumbai HQ',
    to_branch: 2,
    to_branch_name: 'Pune Tech Park',
    from_department: 10,
    from_department_name: 'Engineering',
    to_department: 20,
    to_department_name: 'Operations',
    effective_date: '2026-03-01',
    reason: 'Strategic relocation to Pune',
    created_by: 99,
    created_by_email: 'hr.admin@company.com',
    created_at: '2026-03-01T10:00:00Z',
  },
  {
    id: 2,
    employee: 1,
    event_type: 'promotion',
    event_type_display: 'Promotion',
    from_status: 'active',
    to_status: 'active',
    from_designation: 50,
    from_designation_name: 'Software Engineer',
    to_designation: 51,
    to_designation_name: 'Senior Software Engineer',
    effective_date: '2026-05-01',
    reason: 'Annual appraisal promotion',
    created_by: 99,
    created_by_email: 'hr.admin@company.com',
    created_at: '2026-05-01T09:30:00Z',
  },
];

describe('C5.4 Employee Lifecycle Management UI Suite', () => {
  let mockAuthContextValue: any;

  beforeEach(() => {
    vi.clearAllMocks();

    mockAuthContextValue = {
      user: { id: 99, email: 'admin@company.com', firstName: 'Admin', lastName: 'User', status: 'active' },
      roles: ['Super Admin'],
      permissions: [
        'employee.view',
        'employee.transfer',
        'employee.promote',
        'employee.manage_status',
        'employee.exit',
        'employee.update',
        'employee.lifecycle.view',
      ],
      hasPermission: vi.fn((perm: string) => mockAuthContextValue.permissions.includes(perm)),
      loading: false,
      error: null,
      refreshAuth: vi.fn(),
      logout: vi.fn(),
    };

    vi.spyOn(AuthContextModule, 'useAuth').mockImplementation(() => mockAuthContextValue);

    (employeeManagementService.getEmployee as any).mockResolvedValue(mockActiveEmployee);
    (employeeManagementService.listEmployees as any).mockResolvedValue([mockActiveEmployee]);
    (employeeManagementService.getLifecycleHistory as any).mockResolvedValue(mockLifecycleEvents);
    (organizationService.listBranches as any).mockResolvedValue(mockBranches);
    (organizationService.listDesignations as any).mockResolvedValue(mockDesignations);
    (organizationService.listDepartments as any).mockImplementation((branchId?: number) => {
      if (branchId === 1) return Promise.resolve(mockDepartmentsBranch1);
      if (branchId === 2) return Promise.resolve(mockDepartmentsBranch2);
      return Promise.resolve([]);
    });
    (organizationService.listTeams as any).mockImplementation((deptId?: number) => {
      if (deptId === 10) return Promise.resolve(mockTeamsDept10);
      if (deptId === 20) return Promise.resolve(mockTeamsDept20);
      return Promise.resolve([]);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const renderProfile = async (employeeId = 1) => {
    render(
      <MemoryRouter initialEntries={[`/admin/employees/${employeeId}`]}>
        <Routes>
          <Route path="/admin/employees/:id" element={<EmployeeProfilePage />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByRole('heading', { level: 1, name: /Alice Smith/i });
  };

  // ==========================================
  // SECTION 1: Permission-Based Visibility & RBAC
  // ==========================================
  describe('1. Permission-Based Action Visibility', () => {
    it('1.1. Only employee.view -> All lifecycle action buttons are hidden', async () => {
      mockAuthContextValue.permissions = ['employee.view'];

      await renderProfile(1);

      expect(screen.queryByTestId('action-transfer-btn')).not.toBeInTheDocument();
      expect(screen.queryByTestId('action-promote-btn')).not.toBeInTheDocument();
      expect(screen.queryByTestId('action-status-btn')).not.toBeInTheDocument();
      expect(screen.queryByTestId('action-exit-btn')).not.toBeInTheDocument();
      expect(screen.queryByTestId('action-reactivate-btn')).not.toBeInTheDocument();
      expect(screen.queryByTestId('action-edit-btn')).not.toBeInTheDocument();

      // Lifecycle history tab remains accessible with employee.view
      expect(screen.getByTestId('tab-lifecycle')).toBeInTheDocument();
    });

    it('1.2. employee.transfer exclusively controls Transfer action', async () => {
      mockAuthContextValue.permissions = ['employee.view', 'employee.transfer'];

      await renderProfile(1);

      expect(screen.getByTestId('action-transfer-btn')).toBeInTheDocument();
      expect(screen.queryByTestId('action-promote-btn')).not.toBeInTheDocument();
      expect(screen.queryByTestId('action-status-btn')).not.toBeInTheDocument();
      expect(screen.queryByTestId('action-exit-btn')).not.toBeInTheDocument();
      expect(screen.queryByTestId('action-edit-btn')).not.toBeInTheDocument();
    });

    it('1.3. employee.promote exclusively controls Promote action', async () => {
      mockAuthContextValue.permissions = ['employee.view', 'employee.promote'];

      await renderProfile(1);

      expect(screen.queryByTestId('action-transfer-btn')).not.toBeInTheDocument();
      expect(screen.getByTestId('action-promote-btn')).toBeInTheDocument();
      expect(screen.queryByTestId('action-status-btn')).not.toBeInTheDocument();
      expect(screen.queryByTestId('action-exit-btn')).not.toBeInTheDocument();
    });

    it('1.4. employee.manage_status enables Status Change and Exit', async () => {
      mockAuthContextValue.permissions = ['employee.view', 'employee.manage_status'];

      await renderProfile(1);

      expect(screen.getByTestId('action-status-btn')).toBeInTheDocument();
      expect(screen.getByTestId('action-exit-btn')).toBeInTheDocument();
      expect(screen.queryByTestId('action-transfer-btn')).not.toBeInTheDocument();
      expect(screen.queryByTestId('action-promote-btn')).not.toBeInTheDocument();
    });

    it('1.5. employee.update controls ordinary editing only and does not act as fallback for transfer/promotion', async () => {
      mockAuthContextValue.permissions = ['employee.view', 'employee.update'];

      await renderProfile(1);

      expect(screen.getByTestId('action-edit-btn')).toBeInTheDocument();
      expect(screen.queryByTestId('action-transfer-btn')).not.toBeInTheDocument();
      expect(screen.queryByTestId('action-promote-btn')).not.toBeInTheDocument();
    });

    it('1.6. Arbitrary custom roles with permissions see buttons without role-title checks', async () => {
      mockAuthContextValue.roles = ['Custom Team Lead'];
      mockAuthContextValue.permissions = ['employee.view', 'employee.transfer', 'employee.promote'];

      await renderProfile(1);

      expect(screen.getByTestId('action-transfer-btn')).toBeInTheDocument();
      expect(screen.getByTestId('action-promote-btn')).toBeInTheDocument();
      expect(screen.queryByTestId('action-status-btn')).not.toBeInTheDocument();
    });
  });

  // ==========================================
  // SECTION 2: Exited Employee Guards
  // ==========================================
  describe('2. Exited Employee State Guards', () => {
    it('2.1. Exited employee disables Transfer, Promotion, Exit and exposes Reactivate', async () => {
      (employeeManagementService.getEmployee as any).mockResolvedValue(mockExitedEmployee);

      await renderProfile(2);

      // Transfer & Promote must be disabled for exited employee
      const transferBtn = screen.getByTestId('action-transfer-btn');
      const promoteBtn = screen.getByTestId('action-promote-btn');
      const exitBtn = screen.getByTestId('action-exit-btn');

      expect(transferBtn).toBeDisabled();
      expect(promoteBtn).toBeDisabled();
      expect(exitBtn).toBeDisabled();

      // Normal status change is hidden in favor of explicit Reactivate
      expect(screen.queryByTestId('action-status-btn')).not.toBeInTheDocument();

      // Reactivate button must be available
      expect(screen.getByTestId('action-reactivate-btn')).toBeInTheDocument();
      expect(screen.getByTestId('action-reactivate-btn')).not.toBeDisabled();
    });

    it('2.2. Active employee does NOT render Reactivate button', async () => {
      await renderProfile(1);

      expect(screen.queryByTestId('action-reactivate-btn')).not.toBeInTheDocument();
      expect(screen.getByTestId('action-transfer-btn')).not.toBeDisabled();
      expect(screen.getByTestId('action-promote-btn')).not.toBeDisabled();
    });
  });

  // ==========================================
  // SECTION 3: Employee Transfer Workflow
  // ==========================================
  describe('3. Employee Transfer Workflow', () => {
    it('3.1. Renders cascading selectors (Branch -> Department -> Team) and submits valid transfer', async () => {
      (employeeManagementService.transferEmployee as any).mockResolvedValue({
        ...mockActiveEmployee,
        branch: 2,
        branch_name: 'Pune Tech Park',
        department: 20,
        department_name: 'Operations',
        team: 200,
        team_name: 'Ops Core',
      });

      await renderProfile(1);

      // Open Transfer Modal
      fireEvent.click(screen.getByTestId('action-transfer-btn'));
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Transfer Employee')).toBeInTheDocument();

      // Wait until initial data loading completes and form controls are enabled
      await waitFor(() => {
        expect(screen.getByTestId('transfer-branch-select')).not.toBeDisabled();
      });

      // Clear mock call count from initial mount
      (organizationService.listDepartments as any).mockClear();

      // Select Destination Branch: Pune Tech Park (id: 2)
      const branchSelect = screen.getByTestId('transfer-branch-select');
      fireEvent.change(branchSelect, { target: { value: '2' } });

      await waitFor(() => {
        expect(organizationService.listDepartments).toHaveBeenCalledWith(2, expect.anything());
      });

      // Select Destination Department: Operations (id: 20)
      const deptSelect = screen.getByTestId('transfer-department-select');
      await waitFor(() => {
        expect(within(deptSelect).getByText(/Operations/)).toBeInTheDocument();
      });
      fireEvent.change(deptSelect, { target: { value: '20' } });

      await waitFor(() => {
        expect(organizationService.listTeams).toHaveBeenCalledWith(20, expect.anything());
      });

      // Select Destination Team: Ops Core (id: 200)
      const teamSelect = screen.getByTestId('transfer-team-select');
      await waitFor(() => {
        expect(within(teamSelect).getByText(/Ops Core/)).toBeInTheDocument();
      });
      fireEvent.change(teamSelect, { target: { value: '200' } });

      // Enter Effective Date & Reason
      const dateInput = screen.getByTestId('transfer-effective-date');
      fireEvent.change(dateInput, { target: { value: '2026-10-01' } });

      const reasonInput = screen.getByTestId('transfer-reason');
      fireEvent.change(reasonInput, { target: { value: 'Pune expansion lead' } });

      // Confirm Transfer
      fireEvent.click(screen.getByTestId('submit-transfer-btn'));

      await waitFor(() => {
        expect(employeeManagementService.transferEmployee).toHaveBeenCalledWith(1, {
          branch: 2,
          department: 20,
          team: 200,
          effective_date: '2026-10-01',
          reason: 'Pune expansion lead',
        });
      });

      // Modal closes, success toast displayed, and profile hierarchy reflects update
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(screen.getByTestId('lifecycle-success-toast')).toHaveTextContent('Employee transferred successfully.');
      expect(screen.getByTestId('profile-branch')).toHaveTextContent('Pune Tech Park');
      expect(screen.getByTestId('profile-department')).toHaveTextContent('Operations');
    });

    it('3.2. Displays 403 authorization error when destination unit is outside authorized scope', async () => {
      (employeeManagementService.transferEmployee as any).mockRejectedValue(
        new ApiError({ status: 403 } as any, { detail: 'You do not have permission to transfer employees into this organizational unit.' })
      );

      await renderProfile(1);

      fireEvent.click(screen.getByTestId('action-transfer-btn'));
      await waitFor(() => {
        expect(screen.getByTestId('transfer-branch-select')).not.toBeDisabled();
      });

      const branchSelect = screen.getByTestId('transfer-branch-select');
      fireEvent.change(branchSelect, { target: { value: '2' } });

      fireEvent.click(screen.getByTestId('submit-transfer-btn'));

      const errorBox = await screen.findByTestId('transfer-error-box');
      expect(errorBox).toHaveTextContent('You do not have permission to transfer employees into this organizational unit.');
      // Modal remains open on error
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('3.3. Displays 400 contradictory hierarchy validation errors inline', async () => {
      (employeeManagementService.transferEmployee as any).mockRejectedValue(
        new ApiError({ status: 400 } as any, { department: 'Department must match the employee\'s final branch.' })
      );

      await renderProfile(1);

      fireEvent.click(screen.getByTestId('action-transfer-btn'));
      await waitFor(() => {
        expect(screen.getByTestId('submit-transfer-btn')).not.toBeDisabled();
      });

      fireEvent.click(screen.getByTestId('submit-transfer-btn'));

      await waitFor(() => {
        expect(screen.getByText('Department must match the employee\'s final branch.')).toBeInTheDocument();
      });
    });
  });

  // ==========================================
  // SECTION 4: Employee Promotion Workflow
  // ==========================================
  describe('4. Employee Promotion Workflow', () => {
    it('4.1. Promotes employee with designation, effective-date, and optional salary', async () => {
      (employeeManagementService.promoteEmployee as any).mockResolvedValue({
        ...mockActiveEmployee,
        designation: 51,
        designation_name: 'Senior Software Engineer',
      });

      await renderProfile(1);

      fireEvent.click(screen.getByTestId('action-promote-btn'));
      expect(screen.getByText('Promote Employee')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByTestId('promotion-designation-select')).not.toBeDisabled();
      });

      // Select new designation
      const desigSelect = screen.getByTestId('promotion-designation-select');
      fireEvent.change(desigSelect, { target: { value: '51' } });

      // Effective date
      const dateInput = screen.getByTestId('promotion-effective-date');
      fireEvent.change(dateInput, { target: { value: '2026-11-01' } });

      // New basic salary
      const salaryInput = screen.getByTestId('promotion-salary-input');
      fireEvent.change(salaryInput, { target: { value: '85000.00' } });

      // Reason
      const reasonInput = screen.getByTestId('promotion-reason');
      fireEvent.change(reasonInput, { target: { value: 'Outstanding performance appraisal' } });

      fireEvent.click(screen.getByTestId('submit-promotion-btn'));

      await waitFor(() => {
        expect(employeeManagementService.promoteEmployee).toHaveBeenCalledWith(1, {
          designation: 51,
          effective_date: '2026-11-01',
          new_basic_salary: '85000.00',
          reason: 'Outstanding performance appraisal',
        });
      });

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(screen.getByTestId('lifecycle-success-toast')).toHaveTextContent('Employee promoted successfully.');
      expect(screen.getByTestId('profile-designation')).toHaveTextContent('Senior Software Engineer');
    });

    it('4.2. Displays error when promotion fails on backend', async () => {
      (employeeManagementService.promoteEmployee as any).mockRejectedValue(
        new ApiError({ status: 400 } as any, { detail: 'Cannot promote an exited employee.' })
      );

      await renderProfile(1);

      fireEvent.click(screen.getByTestId('action-promote-btn'));
      await waitFor(() => {
        expect(screen.getByTestId('promotion-designation-select')).not.toBeDisabled();
      });

      const desigSelect = screen.getByTestId('promotion-designation-select');
      fireEvent.change(desigSelect, { target: { value: '51' } });
      fireEvent.click(screen.getByTestId('submit-promotion-btn'));

      const errorBox = await screen.findByTestId('promotion-error-box');
      expect(errorBox).toHaveTextContent('Cannot promote an exited employee.');
    });
  });

  // ==========================================
  // SECTION 5: Exit & Notice Period Workflow
  // ==========================================
  describe('5. Exit & Notice Period Workflow', () => {
    it('5.1. Processes notice period initiation with set_notice_status: true', async () => {
      (employeeManagementService.exitEmployee as any).mockResolvedValue({
        ...mockActiveEmployee,
        employment_status: 'on_notice',
        notice_period_start: '2026-09-01',
        notice_period_end: '2026-11-30',
        exit_date: '2026-11-30',
      });

      await renderProfile(1);

      fireEvent.click(screen.getByTestId('action-exit-btn'));
      expect(screen.getByText('Process Employee Exit')).toBeInTheDocument();

      // Switch to Notice Period tab
      fireEvent.click(screen.getByTestId('tab-exit-notice'));

      const exitDate = screen.getByTestId('exit-date-input');
      fireEvent.change(exitDate, { target: { value: '2026-11-30' } });

      const noticeStart = screen.getByTestId('exit-notice-start');
      fireEvent.change(noticeStart, { target: { value: '2026-09-01' } });

      const noticeEnd = screen.getByTestId('exit-notice-end');
      fireEvent.change(noticeEnd, { target: { value: '2026-11-30' } });

      fireEvent.click(screen.getByTestId('submit-exit-btn'));

      await waitFor(() => {
        expect(employeeManagementService.exitEmployee).toHaveBeenCalledWith(1, expect.objectContaining({
          set_notice_status: true,
          exit_date: '2026-11-30',
          notice_period_start: '2026-09-01',
          notice_period_end: '2026-11-30',
        }));
      });

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(screen.getByTestId('lifecycle-success-toast')).toHaveTextContent('Employee placed on notice period.');
    });

    it('5.2. Processes final exit with set_notice_status: false and warns about account deactivation', async () => {
      (employeeManagementService.exitEmployee as any).mockResolvedValue({
        ...mockActiveEmployee,
        employment_status: 'exited',
        status: 'inactive',
        exit_date: '2026-12-31',
      });

      await renderProfile(1);

      fireEvent.click(screen.getByTestId('action-exit-btn'));
      expect(screen.getByText('Final Separation Warning:')).toBeInTheDocument();

      const exitDate = screen.getByTestId('exit-date-input');
      fireEvent.change(exitDate, { target: { value: '2026-12-31' } });

      const exitType = screen.getByTestId('exit-type-select');
      fireEvent.change(exitType, { target: { value: 'termination' } });

      fireEvent.click(screen.getByTestId('submit-exit-btn'));

      await waitFor(() => {
        expect(employeeManagementService.exitEmployee).toHaveBeenCalledWith(1, expect.objectContaining({
          set_notice_status: false,
          exit_type: 'termination',
          exit_date: '2026-12-31',
        }));
      });

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(screen.getByTestId('lifecycle-success-toast')).toHaveTextContent('Employee exit processed successfully.');
    });

    it('5.3. Validates that notice period end cannot be before notice start', async () => {
      await renderProfile(1);

      fireEvent.click(screen.getByTestId('action-exit-btn'));
      fireEvent.click(screen.getByTestId('tab-exit-notice'));

      const noticeStart = screen.getByTestId('exit-notice-start');
      fireEvent.change(noticeStart, { target: { value: '2026-10-15' } });

      const noticeEnd = screen.getByTestId('exit-notice-end');
      fireEvent.change(noticeEnd, { target: { value: '2026-10-01' } });

      fireEvent.click(screen.getByTestId('submit-exit-btn'));

      expect(await screen.findByText('Notice period end date cannot be before start date.')).toBeInTheDocument();
      expect(employeeManagementService.exitEmployee).not.toHaveBeenCalled();
    });
  });

  // ==========================================
  // SECTION 6: Status Change & Reactivation
  // ==========================================
  describe('6. Status Change & Reactivation', () => {
    it('6.1. Changes employment status to on_leave with reason', async () => {
      (employeeManagementService.changeEmploymentStatus as any).mockResolvedValue({
        ...mockActiveEmployee,
        employment_status: 'on_leave',
      });

      await renderProfile(1);

      fireEvent.click(screen.getByTestId('action-status-btn'));
      expect(screen.getByText('Change Employment Status')).toBeInTheDocument();

      const statusSelect = screen.getByTestId('status-select');
      fireEvent.change(statusSelect, { target: { value: 'on_leave' } });

      const reasonInput = screen.getByTestId('status-reason-input');
      fireEvent.change(reasonInput, { target: { value: 'Sabbatical leave' } });

      fireEvent.click(screen.getByTestId('submit-status-btn'));

      await waitFor(() => {
        expect(employeeManagementService.changeEmploymentStatus).toHaveBeenCalledWith(1, {
          employment_status: 'on_leave',
          reason: 'Sabbatical leave',
        });
      });

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(screen.getByTestId('lifecycle-success-toast')).toHaveTextContent('Employment status updated successfully.');
    });

    it('6.2. Reactivates exited employee using dedicated reactivate endpoint', async () => {
      (employeeManagementService.getEmployee as any).mockResolvedValue(mockExitedEmployee);
      (employeeManagementService.reactivateEmployee as any).mockResolvedValue({
        ...mockExitedEmployee,
        employment_status: 'active',
        status: 'active',
        exit_date: null,
        exit_reason: '',
      });

      await renderProfile(2);

      // Click Reactivate Employee
      const reactivateBtn = screen.getByTestId('action-reactivate-btn');
      fireEvent.click(reactivateBtn);

      expect(screen.getByText('Reactivate Exited Employee')).toBeInTheDocument();

      const reasonInput = screen.getByTestId('reactivate-reason-input');
      fireEvent.change(reasonInput, { target: { value: 'Rehired under new agreement' } });

      fireEvent.click(screen.getByTestId('submit-reactivate-btn'));

      await waitFor(() => {
        expect(employeeManagementService.reactivateEmployee).toHaveBeenCalledWith(2, {
          reason: 'Rehired under new agreement',
        });
      });

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(screen.getByTestId('lifecycle-success-toast')).toHaveTextContent('Employee reactivated successfully.');
    });
  });

  // ==========================================
  // SECTION 7: Normal Employee Editing
  // ==========================================
  describe('7. Normal Employee Editing', () => {
    it('7.1. Edits allowed profile fields while leaving branch and department to Transfer', async () => {
      (employeeManagementService.updateEmployee as any).mockResolvedValue({
        ...mockActiveEmployee,
        phone_number: '9998887777',
        address: '789 New Blvd',
      });

      await renderProfile(1);

      fireEvent.click(screen.getByTestId('action-edit-btn'));
      expect(screen.getByText('Edit Employee Details')).toBeInTheDocument();

      // Check the notice informing user that branch/department changes require Transfer
      expect(screen.getByText(/transfers require the dedicated/)).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByTestId('submit-edit-btn')).not.toBeDisabled();
      });

      const phoneInput = screen.getByTestId('edit-phone-input');
      fireEvent.change(phoneInput, { target: { value: '9998887777' } });

      const addressInput = screen.getByTestId('edit-address-input');
      fireEvent.change(addressInput, { target: { value: '789 New Blvd' } });

      fireEvent.click(screen.getByTestId('submit-edit-btn'));

      await waitFor(() => {
        expect(employeeManagementService.updateEmployee).toHaveBeenCalledWith(1, expect.objectContaining({
          phone_number: '9998887777',
          address: '789 New Blvd',
        }));
      });

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(screen.getByTestId('lifecycle-success-toast')).toHaveTextContent('Employee profile updated successfully.');
    });
  });

  // ==========================================
  // SECTION 8: Lifecycle History Tab & Display
  // ==========================================
  describe('8. Lifecycle History Display', () => {
    it('8.1. Fetches and displays lifecycle timeline events with from/to differences', async () => {
      await renderProfile(1);

      // Click on Lifecycle History tab
      const lifecycleTab = screen.getByTestId('tab-lifecycle');
      fireEvent.click(lifecycleTab);

      await waitFor(() => {
        expect(employeeManagementService.getLifecycleHistory).toHaveBeenCalledWith(1);
      });

      // Verifies event rows rendered
      expect(await screen.findByTestId('lifecycle-event-1')).toBeInTheDocument();
      expect(screen.getByTestId('lifecycle-event-2')).toBeInTheDocument();

      // Event 1: Transfer from Mumbai HQ -> Pune Tech Park
      const event1 = screen.getByTestId('lifecycle-event-1');
      expect(within(event1).getByText('Transfer')).toBeInTheDocument();
      expect(within(event1).getByText('Mumbai HQ')).toBeInTheDocument();
      expect(within(event1).getByText('Pune Tech Park')).toBeInTheDocument();
      expect(within(event1).getByText(/Strategic relocation to Pune/)).toBeInTheDocument();

      // Event 2: Promotion from Software Engineer -> Senior Software Engineer
      const event2 = screen.getByTestId('lifecycle-event-2');
      expect(within(event2).getByText('Promotion')).toBeInTheDocument();
      expect(within(event2).getByText('Software Engineer')).toBeInTheDocument();
      expect(within(event2).getByText('Senior Software Engineer')).toBeInTheDocument();
    });

    it('8.2. Displays empty state when employee has no lifecycle records', async () => {
      (employeeManagementService.getLifecycleHistory as any).mockResolvedValue([]);

      await renderProfile(1);

      fireEvent.click(screen.getByTestId('tab-lifecycle'));

      expect(await screen.findByText('No Lifecycle History')).toBeInTheDocument();
      expect(screen.getByText(/No transfer, promotion, separation, or status change events/)).toBeInTheDocument();
    });

    it('8.3. Handles lifecycle history error and allows retry', async () => {
      (employeeManagementService.getLifecycleHistory as any).mockRejectedValueOnce(
        new Error('Network error loading history')
      );

      await renderProfile(1);

      fireEvent.click(screen.getByTestId('tab-lifecycle'));

      expect(await screen.findByTestId('lifecycle-error')).toBeInTheDocument();
      expect(screen.getByText('Failed to load employee lifecycle history.')).toBeInTheDocument();

      // Retry
      (employeeManagementService.getLifecycleHistory as any).mockResolvedValueOnce(mockLifecycleEvents);
      fireEvent.click(screen.getByText('Retry Loading History'));

      expect(await screen.findByTestId('lifecycle-event-1')).toBeInTheDocument();
    });
  });
});
