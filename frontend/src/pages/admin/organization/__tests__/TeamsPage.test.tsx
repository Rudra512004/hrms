import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TeamsPage } from '../TeamsPage';
import {
  organizationService,
  type Team,
  type Department,
  type Branch,
} from '../../../../services/organization';
import { employeeManagementService } from '../../../../services/employeeManagement';
import { type EmployeeProfile } from '../../../../services/employee';
import * as AuthContextModule from '../../../../contexts/AuthContext';
import * as BranchContextModule from '../../../../contexts/BranchContext';

vi.mock('../../../../services/organization', () => ({
  organizationService: {
    listTeams: vi.fn(),
    createTeam: vi.fn(),
    updateTeam: vi.fn(),
    deleteTeam: vi.fn(),
    listDepartments: vi.fn(),
    listBranches: vi.fn(),
  },
}));

vi.mock('../../../../services/employeeManagement', () => ({
  employeeManagementService: {
    listEmployees: vi.fn(),
  },
}));

const mockBranches: Branch[] = [
  { id: 1, organization: 1, name: 'Mumbai HQ', address: 'Mumbai', is_active: true },
  { id: 2, organization: 1, name: 'Pune Tech Park', address: 'Pune', is_active: true },
] as unknown as Branch[];

const mockDepartments: Department[] = [
  { id: 10, branch: 1, name: 'Engineering', description: 'Tech', is_active: true },
  { id: 20, branch: 2, name: 'Operations', description: 'Ops', is_active: true },
];

const mockEmployees: Partial<EmployeeProfile>[] = [
  { id: 101, first_name: 'Rahul', last_name: 'Sharma', employee_code: 'EMP001', branch: 1, employment_status: 'active' },
  { id: 102, first_name: 'Pooja', last_name: 'Patil', employee_code: 'EMP002', branch: 1, employment_status: 'active' },
  { id: 201, first_name: 'Vikram', last_name: 'Joshi', employee_code: 'EMP003', branch: 2, employment_status: 'active' },
];

const mockTeams: Team[] = [
  {
    id: 1,
    department: 10,
    department_name: 'Engineering',
    name: 'Backend Core',
    description: 'API services',
    is_active: true,
    manager: 101,
  },
  {
    id: 2,
    department: 20,
    department_name: 'Operations',
    name: 'Support Ops',
    description: 'Tier 1 support',
    is_active: true,
    manager: null,
  },
];

describe('TeamsPage — Team Administration & Hierarchy Integration', () => {
  let mockAuthContext: any;
  let mockBranchContext: any;

  beforeEach(() => {
    vi.clearAllMocks();

    mockAuthContext = {
      user: { id: 1, email: 'admin@beyondsure.com' },
      hasPermission: vi.fn((p: string) => ['team.view', 'team.manage'].includes(p)),
      loading: false,
      error: null,
      refreshAuth: vi.fn(),
      logout: vi.fn(),
    };

    mockBranchContext = {
      branchId: 1,
      branches: mockBranches,
      selectedBranch: { type: 'branch', branchId: 1, branch: mockBranches[0] },
      isLoading: false,
      error: null,
      selectBranch: vi.fn(),
      refreshBranches: vi.fn(),
    };

    vi.spyOn(AuthContextModule, 'useAuth').mockImplementation(() => mockAuthContext);
    vi.spyOn(BranchContextModule, 'useBranchContext').mockImplementation(() => mockBranchContext);

    vi.mocked(organizationService.listBranches).mockResolvedValue(mockBranches);
    vi.mocked(organizationService.listDepartments).mockResolvedValue(mockDepartments);
    vi.mocked(organizationService.listTeams).mockResolvedValue(mockTeams);
    vi.mocked(employeeManagementService.listEmployees).mockResolvedValue(mockEmployees as EmployeeProfile[]);
  });

  const renderComponent = () =>
    render(
      <MemoryRouter>
        <TeamsPage />
      </MemoryRouter>
    );

  it('1. Renders team list with Department, Branch, Manager, and Status', async () => {
    renderComponent();

    expect(await screen.findByText('Backend Core')).toBeInTheDocument();
    expect(screen.getAllByText('Engineering')[0]).toBeInTheDocument();
    expect(screen.getByText('Mumbai HQ')).toBeInTheDocument();
    expect(screen.getByText('Rahul Sharma')).toBeInTheDocument();

    const headers = screen.getAllByRole('columnheader').map(th => th.textContent);
    expect(headers).toContain('Team Name');
    expect(headers).toContain('Department');
    expect(headers).toContain('Branch');
    expect(headers).toContain('Manager');
    expect(headers).toContain('Status');
  });

  it('2. Hierarchy-safe department selector shows only departments for the active branch', async () => {
    renderComponent();

    const addBtn = await screen.findByTestId('add-team-btn');
    fireEvent.click(addBtn);

    const deptSelect = screen.getByTestId('team-department-select') as HTMLSelectElement;
    expect(deptSelect).toBeInTheDocument();

    const deptOptions = Array.from(deptSelect.options).map(o => o.text);
    // Since branchId=1 (Mumbai HQ), only Engineering (branch=1) should be present
    expect(deptOptions).toContain('Engineering');
    expect(deptOptions).not.toContain('Operations');
  });

  it('3. Successfully creates a team with name, department, and manager', async () => {
    vi.mocked(organizationService.createTeam).mockResolvedValue({
      id: 3,
      department: 10,
      name: 'Frontend Team',
      description: 'Web client',
      is_active: true,
      manager: 102,
    });

    renderComponent();

    fireEvent.click(await screen.findByTestId('add-team-btn'));

    const nameInput = screen.getByTestId('team-name-input');
    const deptSelect = screen.getByTestId('team-department-select');
    const mgrSelect = screen.getByTestId('team-manager-select');
    const descInput = screen.getByTestId('team-desc-input');
    const saveBtn = screen.getByTestId('team-save-btn');

    fireEvent.change(nameInput, { target: { value: 'Frontend Team' } });
    fireEvent.change(deptSelect, { target: { value: '10' } });
    fireEvent.change(mgrSelect, { target: { value: '102' } });
    fireEvent.change(descInput, { target: { value: 'Web client' } });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(organizationService.createTeam).toHaveBeenCalledWith({
        name: 'Frontend Team',
        department: 10,
        description: 'Web client',
        manager: 102,
        is_active: true,
      });
    });
  });

  it('4. Successfully edits a team while keeping department read-only', async () => {
    vi.mocked(organizationService.updateTeam).mockResolvedValue({
      id: 1,
      department: 10,
      name: 'Backend Platform',
      description: 'Core microservices',
      is_active: true,
      manager: 102,
    });

    renderComponent();

    const editBtn = await screen.findByTestId('edit-team-1');
    fireEvent.click(editBtn);

    expect(await screen.findByText('Edit Team')).toBeInTheDocument();

    // Department should be disabled during edit
    const deptSelect = screen.getByTestId('team-department-select') as HTMLSelectElement;
    expect(deptSelect).toBeDisabled();

    const nameInput = screen.getByTestId('team-name-input');
    fireEvent.change(nameInput, { target: { value: 'Backend Platform' } });

    const saveBtn = screen.getByTestId('team-save-btn');
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(organizationService.updateTeam).toHaveBeenCalledWith(1, {
        name: 'Backend Platform',
        description: 'API services',
        manager: 101,
        is_active: true,
      });
    });
  });

  it('5. Delete team shows clear error when backend rejects deletion of team with active employees', async () => {
    const alertMock = vi.fn();
    window.confirm = vi.fn().mockReturnValue(true);
    window.alert = alertMock;

    vi.mocked(organizationService.deleteTeam).mockRejectedValue({
      response: { status: 400 },
      errorData: { detail: 'Cannot delete team while active employees are assigned to it.' },
    });

    renderComponent();

    const deleteBtn = await screen.findByTestId('delete-team-1');
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(alertMock).toHaveBeenCalledWith('Cannot delete team while active employees are assigned to it.');
    });
  });

  it('6. Permission gating: hides Add Team and Action buttons when lacking team.manage', async () => {
    mockAuthContext.hasPermission.mockImplementation((p: string) => p === 'team.view');

    renderComponent();

    await screen.findByText('Backend Core');
    expect(screen.queryByTestId('add-team-btn')).not.toBeInTheDocument();
    expect(screen.queryByTestId('edit-team-1')).not.toBeInTheDocument();
  });

  it('7. Branch isolation: when header branch changes, filters teams list accordingly', async () => {
    // Both teams in mockTeams: Team 1 (Dept 10 -> Branch 1), Team 2 (Dept 20 -> Branch 2)
    // When branchId is 1: Team 1 is displayed, Team 2 is filtered out
    mockBranchContext.branchId = 1;

    renderComponent();

    expect(await screen.findByText('Backend Core')).toBeInTheDocument();
    expect(screen.queryByText('Support Ops')).not.toBeInTheDocument();
  });
});
