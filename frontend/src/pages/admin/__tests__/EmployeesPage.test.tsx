import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { EmployeesPage } from '../EmployeesPage';
import { EmployeeProfilePage } from '../EmployeeProfilePage';
import { employeeManagementService, ApiError } from '../../../services/employeeManagement';
import { organizationService, type Branch, type Department, type Team, type Designation } from '../../../services/organization';
import * as AuthContextModule from '../../../contexts/AuthContext';
import * as BranchContextModule from '../../../contexts/BranchContext';
import { type EmployeeProfile } from '../../../services/employee';

// Mock Services
vi.mock('../../../services/employeeManagement', () => ({
  employeeManagementService: {
    listEmployees: vi.fn(),
    createEmployee: vi.fn(),
    updateEmployee: vi.fn(),
    getEmployee: vi.fn(),
    changeEmploymentStatus: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number;
    errorData: any;
    constructor(response: any, errorData: any) {
      super(errorData?.detail || 'API Error');
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

const mockDesignations: Designation[] = [
  { id: 50, organization: 1, name: 'Software Engineer', description: 'SWE', is_active: true },
  { id: 51, organization: 1, name: 'Staff Engineer', description: 'Staff', is_active: true },
];

const mockEmployees: EmployeeProfile[] = [
  {
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
  },
  {
    id: 2,
    email: 'bob@company.com',
    first_name: 'Bob',
    last_name: 'Jones',
    employee_code: 'EMP002',
    status: 'active',
    employment_status: 'active',
    branch: 2,
    branch_name: 'Pune Tech Park',
    department: 20,
    department_name: 'Operations',
    team: null,
    team_name: undefined,
    designation: 51,
    designation_name: 'Staff Engineer',
    reporting_manager: 1,
    reporting_manager_name: 'Alice Smith',
  },
];

describe('C5.3 Employee Management UI Suite', () => {
  let mockBranchContextValue: any;
  let mockAuthContextValue: any;

  beforeEach(() => {
    vi.clearAllMocks();

    mockAuthContextValue = {
      user: { id: 1, email: 'admin@company.com', firstName: 'Admin', lastName: 'User', status: 'active' },
      roles: ['Super Admin'],
      permissions: ['employee.view', 'employee.create', 'employee.update', 'employee.manage_status', 'role.assign'],
      hasPermission: vi.fn((perm: string) =>
        ['employee.view', 'employee.create', 'employee.update', 'employee.manage_status', 'role.assign'].includes(perm)
      ),
      loading: false,
      error: null,
      refreshAuth: vi.fn(),
      logout: vi.fn(),
    };

    mockBranchContextValue = {
      selectedBranch: { type: 'all' },
      branchId: null,
      branches: mockBranches,
      isLoading: false,
      error: null,
      selectBranch: vi.fn(),
      refreshBranches: vi.fn(),
    };

    vi.spyOn(AuthContextModule, 'useAuth').mockImplementation(() => mockAuthContextValue);
    vi.spyOn(BranchContextModule, 'useBranchContext').mockImplementation(() => mockBranchContextValue);

    (employeeManagementService.listEmployees as any).mockResolvedValue(mockEmployees);
    (organizationService.listBranches as any).mockResolvedValue(mockBranches);
    (organizationService.listDepartments as any).mockImplementation((branchId?: number) => {
      if (branchId === 1) return Promise.resolve(mockDepartmentsBranch1);
      if (branchId === 2) return Promise.resolve(mockDepartmentsBranch2);
      return Promise.resolve([]);
    });
    (organizationService.listTeams as any).mockImplementation((deptId?: number) => {
      if (deptId === 10) return Promise.resolve(mockTeamsDept10);
      return Promise.resolve([]);
    });
    (organizationService.listDesignations as any).mockResolvedValue(mockDesignations);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ==========================================
  // SECTION A: Branch Context Integration
  // ==========================================
  describe('A. Branch Context Integration', () => {
    it('1. All Locations loads employee list without branch_id query parameter', async () => {
      mockBranchContextValue.branchId = null;

      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(employeeManagementService.listEmployees).toHaveBeenCalledTimes(1);
      });

      const calledParams = (employeeManagementService.listEmployees as any).mock.calls[0][0];
      expect(calledParams.branch_id).toBeUndefined();
      expect(await screen.findByText('Alice Smith')).toBeInTheDocument();
      expect(await screen.findByText('Bob Jones')).toBeInTheDocument();
    });

    it('2. Specific Branch sends exact branch_id parameter to listEmployees', async () => {
      mockBranchContextValue.branchId = 1;

      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(employeeManagementService.listEmployees).toHaveBeenCalledTimes(1);
      });

      const calledParams = (employeeManagementService.listEmployees as any).mock.calls[0][0];
      expect(calledParams.branch_id).toBe(1);
    });

    it('3. Branch switch reloads employee data without page reload', async () => {
      const { rerender } = render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(employeeManagementService.listEmployees).toHaveBeenCalledTimes(1);
      });

      // User changes branch in Header -> BranchContext branchId updates to 2
      mockBranchContextValue.branchId = 2;
      rerender(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(employeeManagementService.listEmployees).toHaveBeenCalledTimes(2);
      });

      const secondCallParams = (employeeManagementService.listEmployees as any).mock.calls[1][0];
      expect(secondCallParams.branch_id).toBe(2);
    });

    it('4. Stale request cannot overwrite newer branch state on rapid branch changes', async () => {
      // Simulate slow response for branch 1, fast response for branch 2
      let resolveBranch1: (val: any) => void;
      const branch1Promise = new Promise(resolve => {
        resolveBranch1 = resolve;
      });

      (employeeManagementService.listEmployees as any).mockImplementation((params: any) => {
        if (params.branch_id === 1) {
          return branch1Promise;
        }
        if (params.branch_id === 2) {
          return Promise.resolve([mockEmployees[1]]); // only Bob
        }
        return Promise.resolve(mockEmployees);
      });

      mockBranchContextValue.branchId = 1;
      const { rerender } = render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      // Rapid switch to Branch 2 before Branch 1 resolves
      mockBranchContextValue.branchId = 2;
      rerender(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      // Fast branch 2 arrives
      await waitFor(() => {
        expect(screen.getByText('Bob Jones')).toBeInTheDocument();
      });

      // Late branch 1 response arrives
      resolveBranch1!([mockEmployees[0]]); // Alice

      // Verify that Alice (from stale request) did NOT overwrite the UI
      await waitFor(() => {
        expect(screen.getByText('Bob Jones')).toBeInTheDocument();
      });
      expect(screen.queryByText('Alice Smith')).not.toBeInTheDocument();
    });
  });

  // ==========================================
  // SECTION B: Cascading Selectors
  // ==========================================
  describe('B. Cascading Selectors (Branch -> Department -> Team)', () => {
    it('5. Selecting a Branch loads its Departments', async () => {
      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await screen.findByText('Alice Smith');
      fireEvent.click(screen.getByTestId('add-employee-btn'));

      const branchSelect = await screen.findByTestId('select-branch');
      fireEvent.change(branchSelect, { target: { value: '1' } });

      await waitFor(() => {
        expect(organizationService.listDepartments).toHaveBeenCalledWith(1, expect.any(Object));
      });

      const deptSelect = screen.getByTestId('select-department');
      await waitFor(() => {
        expect(within(deptSelect).getByText('Engineering')).toBeInTheDocument();
        expect(within(deptSelect).getByText('Product')).toBeInTheDocument();
      });
    });

    it('6. Selecting a Department loads its Teams', async () => {
      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await screen.findByText('Alice Smith');
      fireEvent.click(screen.getByTestId('add-employee-btn'));

      // Select Branch 1
      fireEvent.change(await screen.findByTestId('select-branch'), { target: { value: '1' } });
      const deptSelect = screen.getByTestId('select-department');
      await waitFor(() => {
        expect(within(deptSelect).getByText('Engineering')).toBeInTheDocument();
      });

      // Select Department 10
      fireEvent.change(deptSelect, { target: { value: '10' } });

      await waitFor(() => {
        expect(organizationService.listTeams).toHaveBeenCalledWith(10, expect.any(Object));
      });

      const teamSelect = screen.getByTestId('select-team');
      await waitFor(() => {
        expect(within(teamSelect).getByText('Backend Team')).toBeInTheDocument();
        expect(within(teamSelect).getByText('Frontend Team')).toBeInTheDocument();
      });
    });

    it('7. Changing Branch clears Department and Team selections and downstream lists', async () => {
      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await screen.findByText('Alice Smith');
      fireEvent.click(screen.getByTestId('add-employee-btn'));

      const branchSelect = await screen.findByTestId('select-branch');
      fireEvent.change(branchSelect, { target: { value: '1' } });
      const deptSelect = screen.getByTestId('select-department');
      await waitFor(() => {
        expect(within(deptSelect).getByText('Engineering')).toBeInTheDocument();
      });

      fireEvent.change(deptSelect, { target: { value: '10' } });
      const teamSelect = screen.getByTestId('select-team');
      await waitFor(() => {
        expect(within(teamSelect).getByText('Backend Team')).toBeInTheDocument();
      });

      fireEvent.change(teamSelect, { target: { value: '100' } });
      expect((teamSelect as HTMLSelectElement).value).toBe('100');

      // Change Branch to Pune Tech Park (2)
      fireEvent.change(branchSelect, { target: { value: '2' } });

      // Department & Team should be reset
      await waitFor(() => {
        expect((deptSelect as HTMLSelectElement).value).toBe('0');
        expect((teamSelect as HTMLSelectElement).value).toBe('0');
      });

      // Old teams from Branch 1 should not be present in teamSelect
      expect(within(teamSelect).queryByText('Backend Team')).not.toBeInTheDocument();
      // Branch 2 departments should now be loaded in deptSelect
      await waitFor(() => {
        expect(within(deptSelect).getByText('Operations')).toBeInTheDocument();
      });
    });

    it('8. Changing Department clears Team selection', async () => {
      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await screen.findByText('Alice Smith');
      fireEvent.click(screen.getByTestId('add-employee-btn'));

      fireEvent.change(await screen.findByTestId('select-branch'), { target: { value: '1' } });
      const deptSelect = screen.getByTestId('select-department');
      await waitFor(() => {
        expect(within(deptSelect).getByText('Engineering')).toBeInTheDocument();
      });

      fireEvent.change(deptSelect, { target: { value: '10' } });
      const teamSelect = screen.getByTestId('select-team');
      await waitFor(() => {
        expect(within(teamSelect).getByText('Backend Team')).toBeInTheDocument();
      });

      fireEvent.change(teamSelect, { target: { value: '100' } });
      expect((teamSelect as HTMLSelectElement).value).toBe('100');

      // Change department to Product (11)
      fireEvent.change(deptSelect, { target: { value: '11' } });

      await waitFor(() => {
        expect((teamSelect as HTMLSelectElement).value).toBe('0');
      });
      expect(within(teamSelect).queryByText('Backend Team')).not.toBeInTheDocument();
    });

    it('9. Dependent selectors show loading and disabled state while fetching parent data', async () => {
      let resolveDeptFetch: (data: any) => void;
      (organizationService.listDepartments as any).mockImplementation(() => {
        return new Promise(resolve => {
          resolveDeptFetch = resolve;
        });
      });

      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await screen.findByText('Alice Smith');
      fireEvent.click(screen.getByTestId('add-employee-btn'));

      const branchSelect = await screen.findByTestId('select-branch');
      fireEvent.change(branchSelect, { target: { value: '1' } });

      const deptSelect = screen.getByTestId('select-department');
      expect(deptSelect).toBeDisabled();
      expect(within(deptSelect).getByText('Loading departments...')).toBeInTheDocument();

      // Resolve departments
      resolveDeptFetch!(mockDepartmentsBranch1);

      await waitFor(() => {
        expect(deptSelect).not.toBeDisabled();
        expect(within(deptSelect).getByText('Engineering')).toBeInTheDocument();
      });
    });

    it('10. Empty department and team results are handled gracefully', async () => {
      (organizationService.listDepartments as any).mockResolvedValueOnce([]);

      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await screen.findByText('Alice Smith');
      fireEvent.click(screen.getByTestId('add-employee-btn'));

      fireEvent.change(await screen.findByTestId('select-branch'), { target: { value: '1' } });

      const deptSelect = screen.getByTestId('select-department');
      await waitFor(() => {
        expect(within(deptSelect).getByText('No departments found')).toBeInTheDocument();
      });
    });
  });

  // ==========================================
  // SECTION C: Create Employee Workflow
  // ==========================================
  describe('C. Create Employee Workflow', () => {
    it('11. Submits valid hierarchy (Branch, Department, Team, Designation) upon creation', async () => {
      (employeeManagementService.createEmployee as any).mockResolvedValue({
        detail: 'Employee provisioned successfully.',
        employee: { ...mockEmployees[0], id: 99, employee_code: 'EMP099' },
        onboarding_email_status: 'sent',
      });

      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await screen.findByText('Alice Smith');
      fireEvent.click(screen.getByTestId('add-employee-btn'));

      // Fill basic inputs
      fireEvent.change(screen.getByTestId('input-first-name'), { target: { value: 'Charlie' } });
      fireEvent.change(screen.getByTestId('input-last-name'), { target: { value: 'Brown' } });
      fireEvent.change(screen.getByTestId('input-email'), { target: { value: 'charlie@company.com' } });

      // Cascading selectors
      const branchSelect = await screen.findByTestId('select-branch');
      fireEvent.change(branchSelect, { target: { value: '1' } });

      const deptSelect = screen.getByTestId('select-department');
      await waitFor(() => {
        expect(within(deptSelect).getByText('Engineering')).toBeInTheDocument();
      });

      fireEvent.change(deptSelect, { target: { value: '10' } });
      const teamSelect = screen.getByTestId('select-team');
      await waitFor(() => {
        expect(within(teamSelect).getByText('Backend Team')).toBeInTheDocument();
      });

      fireEvent.change(teamSelect, { target: { value: '100' } });

      // Designation & Manager
      fireEvent.change(screen.getByTestId('select-designation'), { target: { value: '50' } });
      fireEvent.change(screen.getByTestId('select-reporting-manager'), { target: { value: '1' } });

      fireEvent.click(screen.getByTestId('save-employee-btn'));

      await waitFor(() => {
        expect(employeeManagementService.createEmployee).toHaveBeenCalledTimes(1);
      });

      const createPayload = (employeeManagementService.createEmployee as any).mock.calls[0][0];
      expect(createPayload).toMatchObject({
        first_name: 'Charlie',
        last_name: 'Brown',
        email: 'charlie@company.com',
        branch: 1,
        department: 10,
        team: 100,
        designation: 50,
        reporting_manager: 1,
      });
    });

    it('12. Team selection does not produce contradictory parent IDs', async () => {
      (employeeManagementService.createEmployee as any).mockResolvedValue({
        detail: 'Success',
        employee: { ...mockEmployees[0], id: 101 },
      });

      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await screen.findByText('Alice Smith');
      fireEvent.click(screen.getByTestId('add-employee-btn'));

      fireEvent.change(screen.getByTestId('input-first-name'), { target: { value: 'Dave' } });
      fireEvent.change(screen.getByTestId('input-last-name'), { target: { value: 'Miller' } });
      fireEvent.change(screen.getByTestId('input-email'), { target: { value: 'dave@company.com' } });

      // Select branch 1 -> department 10 -> team 100
      const branchSelect = await screen.findByTestId('select-branch');
      fireEvent.change(branchSelect, { target: { value: '1' } });

      const deptSelect = screen.getByTestId('select-department');
      await waitFor(() => {
        expect(within(deptSelect).getByText('Engineering')).toBeInTheDocument();
      });

      fireEvent.change(deptSelect, { target: { value: '10' } });
      const teamSelect = screen.getByTestId('select-team');
      await waitFor(() => {
        expect(within(teamSelect).getByText('Backend Team')).toBeInTheDocument();
      });
      fireEvent.change(teamSelect, { target: { value: '100' } });

      fireEvent.click(screen.getByTestId('save-employee-btn'));

      await waitFor(() => {
        expect(employeeManagementService.createEmployee).toHaveBeenCalled();
      });

      const payload = (employeeManagementService.createEmployee as any).mock.calls[0][0];
      expect(payload.branch).toBe(1);
      expect(payload.department).toBe(10);
      expect(payload.team).toBe(100);
    });

    it('13. HTTP 400 validation errors display next to respective fields', async () => {
      const mock400Error = new (ApiError as any)(
        { status: 400 },
        {
          branch: ['Invalid branch selected.'],
          department: ['Department does not belong to branch.'],
          team: ['Cannot assign inactive team.'],
          reporting_manager: ['Employee cannot report to themselves.'],
        }
      );
      (employeeManagementService.createEmployee as any).mockRejectedValue(mock400Error);

      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await screen.findByText('Alice Smith');
      fireEvent.click(screen.getByTestId('add-employee-btn'));

      fireEvent.change(screen.getByTestId('input-first-name'), { target: { value: 'Eve' } });
      fireEvent.change(screen.getByTestId('input-last-name'), { target: { value: 'Adams' } });
      fireEvent.change(screen.getByTestId('input-email'), { target: { value: 'eve@company.com' } });

      fireEvent.click(screen.getByTestId('save-employee-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('error-branch')).toHaveTextContent('Invalid branch selected.');
        expect(screen.getByTestId('error-department')).toHaveTextContent('Department does not belong to branch.');
        expect(screen.getByTestId('error-team')).toHaveTextContent('Cannot assign inactive team.');
        expect(screen.getByTestId('error-reporting-manager')).toHaveTextContent('Employee cannot report to themselves.');
      });
    });

    it('14. HTTP 403 authorization failure displays distinct authorization error alert', async () => {
      const mock403Error = new (ApiError as any)(
        { status: 403 },
        { detail: 'You do not have permission to provision employees into this organizational unit.' }
      );
      (employeeManagementService.createEmployee as any).mockRejectedValue(mock403Error);

      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await screen.findByText('Alice Smith');
      fireEvent.click(screen.getByTestId('add-employee-btn'));

      fireEvent.change(screen.getByTestId('input-first-name'), { target: { value: 'Eve' } });
      fireEvent.change(screen.getByTestId('input-last-name'), { target: { value: 'Adams' } });
      fireEvent.change(screen.getByTestId('input-email'), { target: { value: 'eve@company.com' } });

      fireEvent.click(screen.getByTestId('save-employee-btn'));

      await waitFor(() => {
        const errorAlert = screen.getByTestId('form-error-alert');
        expect(errorAlert).toHaveTextContent('You do not have permission to provision employees into this organizational unit.');
      });
    });
  });

  // ==========================================
  // SECTION D: Ordinary Update Workflow
  // ==========================================
  describe('D. Ordinary Update Workflow (PATCH Guardrails)', () => {
    it('15. Ordinary update uses PATCH method and excludes sensitive contact info if not exposed', async () => {
      (employeeManagementService.updateEmployee as any).mockResolvedValue(mockEmployees[0]);

      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await screen.findByText('Alice Smith');
      fireEvent.click(screen.getByTestId('edit-employee-1'));

      await screen.findByText('Edit Employee Info');

      fireEvent.click(screen.getByTestId('save-employee-btn'));

      await waitFor(() => {
        expect(employeeManagementService.updateEmployee).toHaveBeenCalledTimes(1);
      });

      expect((employeeManagementService.updateEmployee as any).mock.calls[0][0]).toBe(1);
    });

    it('16 & 17. Branch and Department cannot be changed in ordinary edit flow', async () => {
      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await screen.findByText('Alice Smith');
      fireEvent.click(screen.getByTestId('edit-employee-1'));

      const disabledBranch = await screen.findByTestId('disabled-edit-branch');
      const disabledDept = screen.getByTestId('disabled-edit-department');

      expect(disabledBranch).toBeDisabled();
      expect(disabledDept).toBeDisabled();
      expect(disabledBranch).toHaveValue('Mumbai HQ');
      expect(disabledDept).toHaveValue('Engineering');
      expect(screen.getByText(/Branch transfer must be performed through the dedicated transfer workflow/)).toBeInTheDocument();
      expect(screen.getByText(/Department transfer must be performed through the dedicated transfer workflow/)).toBeInTheDocument();
    });

    it('18. Same-department Team reassignment is permitted through ordinary edit', async () => {
      (employeeManagementService.updateEmployee as any).mockResolvedValue(mockEmployees[0]);

      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await screen.findByText('Alice Smith');
      fireEvent.click(screen.getByTestId('edit-employee-1'));

      await screen.findByTestId('disabled-edit-branch');
      const teamSelect = screen.getByTestId('select-edit-team');
      await waitFor(() => {
        expect(within(teamSelect).getByText('Frontend Team')).toBeInTheDocument();
      });

      // Change team within department 10 to Frontend Team (101)
      fireEvent.change(teamSelect, { target: { value: '101' } });

      fireEvent.click(screen.getByTestId('save-employee-btn'));

      await waitFor(() => {
        expect(employeeManagementService.updateEmployee).toHaveBeenCalled();
      });

      const patchPayload = (employeeManagementService.updateEmployee as any).mock.calls[0][1];
      expect(patchPayload.team).toBe(101);
      expect(patchPayload.branch).toBeUndefined();
      expect(patchPayload.department).toBeUndefined();
    });
  });

  // ==========================================
  // SECTION E: Employee Profile Hierarchy Rendering
  // ==========================================
  describe('E. Profile Hierarchy Display', () => {
    it('19. EmployeeProfilePage renders complete hierarchy (Branch, Department, Team, Designation, Manager)', async () => {
      (employeeManagementService.getEmployee as any).mockResolvedValue({
        ...mockEmployees[0],
        reporting_manager_name: 'Bob Jones',
      });

      render(
        <MemoryRouter initialEntries={['/admin/employees/1']}>
          <Routes>
            <Route path="/admin/employees/:id" element={<EmployeeProfilePage />} />
          </Routes>
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(employeeManagementService.getEmployee).toHaveBeenCalledWith(1);
      });

      expect(await screen.findByTestId('profile-branch')).toHaveTextContent('Mumbai HQ');
      expect(screen.getByTestId('profile-department')).toHaveTextContent('Engineering');
      expect(screen.getByTestId('profile-team')).toHaveTextContent('Backend Team');
      expect(screen.getByTestId('profile-designation')).toHaveTextContent('Software Engineer');
      expect(screen.getByTestId('profile-reporting-manager')).toHaveTextContent('Bob Jones');
    });

    it('19b. EmployeeProfilePage renders "—" fallback for missing hierarchy attributes', async () => {
      (employeeManagementService.getEmployee as any).mockResolvedValue({
        id: 3,
        first_name: 'NoHierarchy',
        last_name: 'User',
        email: 'nohierarchy@company.com',
        status: 'active',
        employment_status: 'active',
        employee_code: 'EMP999',
        branch_name: null,
        department_name: null,
        team_name: null,
        designation_name: null,
        reporting_manager_name: null,
      });

      render(
        <MemoryRouter initialEntries={['/admin/employees/3']}>
          <Routes>
            <Route path="/admin/employees/:id" element={<EmployeeProfilePage />} />
          </Routes>
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(employeeManagementService.getEmployee).toHaveBeenCalledWith(3);
      });

      expect(await screen.findByTestId('profile-branch')).toHaveTextContent('—');
      expect(screen.getByTestId('profile-department')).toHaveTextContent('—');
      expect(screen.getByTestId('profile-team')).toHaveTextContent('—');
      expect(screen.getByTestId('profile-designation')).toHaveTextContent('—');
      expect(screen.getByTestId('profile-reporting-manager')).toHaveTextContent('—');
    });
  });

  // ==========================================
  // SECTION F: RBAC & Dynamic Permissions
  // ==========================================
  describe('F. RBAC & Dynamic Permissions', () => {
    it('20. UI visibility uses permissions instead of hardcoded role names', async () => {
      // User with 'employee.view' only (no create, no update, no manage_status)
      mockAuthContextValue.hasPermission = vi.fn((perm: string) => perm === 'employee.view');

      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await screen.findByText('Alice Smith');

      // Add Employee button should NOT be rendered
      expect(screen.queryByTestId('add-employee-btn')).not.toBeInTheDocument();

      // Edit, Status, and RBAC action buttons should NOT be rendered
      expect(screen.queryByTestId('edit-employee-1')).not.toBeInTheDocument();
      expect(screen.queryByTestId('status-employee-1')).not.toBeInTheDocument();
      expect(screen.queryByTestId('rbac-employee-1')).not.toBeInTheDocument();

      // View Profile button should be rendered
      expect(screen.getByTestId('view-profile-1')).toBeInTheDocument();
    });

    it('21. User with employee.create and employee.update sees action buttons regardless of role title', async () => {
      // User has custom role with create and update permissions
      mockAuthContextValue.roles = ['Custom Team Lead'];
      mockAuthContextValue.hasPermission = vi.fn((perm: string) =>
        ['employee.view', 'employee.create', 'employee.update'].includes(perm)
      );

      render(
        <MemoryRouter>
          <EmployeesPage />
        </MemoryRouter>
      );

      await screen.findByText('Alice Smith');

      expect(screen.getByTestId('add-employee-btn')).toBeInTheDocument();
      expect(screen.getByTestId('edit-employee-1')).toBeInTheDocument();
      expect(screen.queryByTestId('status-employee-1')).not.toBeInTheDocument();
    });
  });
});
