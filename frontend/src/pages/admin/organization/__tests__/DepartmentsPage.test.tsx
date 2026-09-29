import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DepartmentsPage } from '../DepartmentsPage';
import { organizationService, type Department, type Branch } from '../../../../services/organization';
import * as AuthContextModule from '../../../../contexts/AuthContext';
import * as BranchContextModule from '../../../../contexts/BranchContext';

vi.mock('../../../../services/organization', () => ({
  organizationService: {
    listDepartments: vi.fn(),
    listBranches: vi.fn(),
    createDepartment: vi.fn(),
    updateDepartment: vi.fn(),
    deleteDepartment: vi.fn(),
  },
}));

const mockBranches: Branch[] = [
  { id: 1, organization: 1, name: 'Mumbai HQ', address: 'Mumbai', is_active: true },
  { id: 2, organization: 1, name: 'Bangalore Office', address: 'Bangalore', is_active: true },
] as unknown as Branch[];

const mockDepartments: Department[] = [
  {
    id: 10,
    branch: 1,
    branch_name: 'Mumbai HQ',
    name: 'Engineering',
    description: 'Software development',
    is_active: true,
  },
  {
    id: 20,
    branch: 2,
    branch_name: 'Bangalore Office',
    name: 'Support',
    description: 'Customer success',
    is_active: true,
  },
];

describe('DepartmentsPage — Branch Hierarchy Integration', () => {
  let mockAuthContext: any;
  let mockBranchContext: any;

  beforeEach(() => {
    vi.clearAllMocks();

    mockAuthContext = {
      user: { id: 1, email: 'admin@beyondsure.com' },
      hasPermission: vi.fn((p: string) => ['department.view', 'department.manage'].includes(p)),
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
  });

  const renderComponent = () =>
    render(
      <MemoryRouter>
        <DepartmentsPage />
      </MemoryRouter>
    );

  it('1. Renders department list with Branch column displaying branch name', async () => {
    renderComponent();

    expect(await screen.findByText('Engineering')).toBeInTheDocument();
    expect(screen.getByText('Mumbai HQ')).toBeInTheDocument();
    expect(screen.getByText('Support')).toBeInTheDocument();
    expect(screen.getByText('Bangalore Office')).toBeInTheDocument();

    // Verify "Branch" column header is rendered (and not "Organization")
    const tableHeaders = screen.getAllByRole('columnheader').map(th => th.textContent);
    expect(tableHeaders).toContain('Branch');
    expect(tableHeaders).not.toContain('Organization');
  });

  it('2. Add Department modal shows authorized branch selector prefilled with active branch', async () => {
    renderComponent();

    const addBtn = await screen.findByTestId('add-department-btn');
    fireEvent.click(addBtn);

    const modal = await screen.findByTestId('department-modal');
    expect(modal).toBeInTheDocument();

    const branchSelect = screen.getByTestId('department-branch-select') as HTMLSelectElement;
    expect(branchSelect).toBeInTheDocument();

    // Contains only authorized branches
    const options = Array.from(branchSelect.options).map(o => o.text);
    expect(options).toContain('Mumbai HQ');
    expect(options).toContain('Bangalore Office');

    // Preselected with branchId 1
    expect(branchSelect.value).toBe('1');
  });

  it('3. Successfully creates a department with name and branch payload', async () => {
    vi.mocked(organizationService.createDepartment).mockResolvedValue({
      id: 30,
      branch: 1,
      name: 'QA Automation',
      description: 'Test engineers',
      is_active: true,
    });

    renderComponent();

    fireEvent.click(await screen.findByTestId('add-department-btn'));

    const nameInput = screen.getByTestId('department-name-input');
    const descInput = screen.getByTestId('department-desc-input');
    const saveBtn = screen.getByTestId('department-save-btn');

    fireEvent.change(nameInput, { target: { value: 'QA Automation' } });
    fireEvent.change(descInput, { target: { value: 'Test engineers' } });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(organizationService.createDepartment).toHaveBeenCalledWith({
        name: 'QA Automation',
        branch: 1,
        description: 'Test engineers',
        is_active: true,
      });
    });
  });

  it('4. Successfully edits a department while keeping branch read-only', async () => {
    vi.mocked(organizationService.updateDepartment).mockResolvedValue({
      id: 10,
      branch: 1,
      name: 'Engineering Core',
      description: 'Platform and infra',
      is_active: true,
    });

    renderComponent();

    const editBtn = await screen.findByTestId('edit-dept-10');
    fireEvent.click(editBtn);

    expect(await screen.findByText('Edit Department')).toBeInTheDocument();

    // Branch selector should be disabled
    const branchSelect = screen.getByTestId('department-branch-select') as HTMLSelectElement;
    expect(branchSelect).toBeDisabled();

    const nameInput = screen.getByTestId('department-name-input');
    fireEvent.change(nameInput, { target: { value: 'Engineering Core' } });

    const saveBtn = screen.getByTestId('department-save-btn');
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(organizationService.updateDepartment).toHaveBeenCalledWith(10, {
        name: 'Engineering Core',
        description: 'Software development',
        is_active: true,
      });
    });
  });

  it('5. Validates missing branch and displays validation error', async () => {
    renderComponent();

    fireEvent.click(await screen.findByTestId('add-department-btn'));

    const nameInput = screen.getByTestId('department-name-input');
    const branchSelect = screen.getByTestId('department-branch-select');
    const saveBtn = screen.getByTestId('department-save-btn');

    fireEvent.change(nameInput, { target: { value: 'New Dept' } });
    fireEvent.change(branchSelect, { target: { value: '0' } });
    fireEvent.click(saveBtn);

    expect(await screen.findByText('Branch is required.')).toBeInTheDocument();
    expect(organizationService.createDepartment).not.toHaveBeenCalled();
  });

  it('6. Handles backend validation error (e.g. duplicate name in branch)', async () => {
    vi.mocked(organizationService.createDepartment).mockRejectedValue({
      errorData: { name: ['A department with this name already exists in this branch.'] },
    });

    renderComponent();

    fireEvent.click(await screen.findByTestId('add-department-btn'));

    const nameInput = screen.getByTestId('department-name-input');
    fireEvent.change(nameInput, { target: { value: 'Engineering' } });

    const saveBtn = screen.getByTestId('department-save-btn');
    fireEvent.click(saveBtn);

    expect(
      await screen.findByText('A department with this name already exists in this branch.')
    ).toBeInTheDocument();
  });

  it('7. Enforces branch isolation when header branchId changes', async () => {
    // When branchId is 2, listDepartments is called with branchId 2
    mockBranchContext.branchId = 2;

    renderComponent();

    await waitFor(() => {
      expect(organizationService.listDepartments).toHaveBeenCalledWith(2);
    });
  });

  it('8. Permission gating: hides management actions when user lacks department.manage', async () => {
    mockAuthContext.hasPermission.mockImplementation((p: string) => p === 'department.view');

    renderComponent();

    await screen.findByText('Engineering');
    expect(screen.queryByTestId('add-department-btn')).not.toBeInTheDocument();
    expect(screen.queryByTestId('edit-dept-10')).not.toBeInTheDocument();
  });
});
