import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ShiftAssignmentsPage } from '../ShiftAssignmentsPage';
import { shiftAssignmentService } from '../../../services/shiftAssignment';
import { shiftService, type Shift } from '../../../services/shift';
import { employeeManagementService } from '../../../services/employeeManagement';
import { type EmployeeProfile } from '../../../services/employee';
import * as AuthContextModule from '../../../contexts/AuthContext';
import * as BranchContextModule from '../../../contexts/BranchContext';

vi.mock('../../../services/shiftAssignment', () => ({
  shiftAssignmentService: {
    listAssignments: vi.fn(),
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number;
    errorData: any;
    constructor(response: any, errorData: any) {
      super(errorData?.detail || 'API Error');
      this.status = response?.status || 500;
      this.errorData = errorData;
    }
  },
}));

vi.mock('../../../services/shift', () => ({
  shiftService: {
    listShifts: vi.fn(),
  },
}));

vi.mock('../../../services/employeeManagement', () => ({
  employeeManagementService: {
    listEmployees: vi.fn(),
  },
}));

const mockShifts: Shift[] = [
  {
    id: 1,
    branch: 1,
    name: 'General Morning Shift',
    start_time: '09:00:00',
    end_time: '18:00:00',
    grace_period: '00:15:00',
    full_day_hours: '08:00:00',
    half_day_hours: '04:00:00',
    work_days: '0,1,2,3,4',
    is_active: true,
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  },
  {
    id: 2,
    branch: 1,
    name: 'Night Shift',
    start_time: '21:00:00',
    end_time: '06:00:00',
    grace_period: '00:15:00',
    full_day_hours: '08:00:00',
    half_day_hours: '04:00:00',
    work_days: '0,1,2,3,4',
    is_active: true,
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  },
];

const mockEmployees: EmployeeProfile[] = [
  {
    id: 101,
    email: 'rahul@beyondsure.com',
    first_name: 'Rahul',
    last_name: 'Sharma',
    status: 'active',
    employee_code: 'EMP-001',
    employment_status: 'active',
    department_name: 'Engineering',
    team_name: 'Frontend',
  },
  {
    id: 102,
    email: 'priya@beyondsure.com',
    first_name: 'Priya',
    last_name: 'Patel',
    status: 'active',
    employee_code: 'EMP-002',
    employment_status: 'active',
    department_name: 'Operations',
    team_name: 'Support',
  },
];

const mockAssignments = [
  {
    id: 501,
    employee: 101,
    shift: 1,
    effective_from: '2026-01-01',
    effective_to: null, // Ongoing / Active
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 502,
    employee: 102,
    shift: 2,
    effective_from: '2099-01-01',
    effective_to: '2099-12-31', // Upcoming
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 503,
    employee: 101,
    shift: 2,
    effective_from: '2020-01-01',
    effective_to: '2020-12-31', // Expired
    created_at: '2020-01-01T00:00:00Z',
    updated_at: '2020-01-01T00:00:00Z',
  },
];

describe('ShiftAssignmentsPage Suite (C5.5.5)', () => {
  let mockAuthContextValue: any;
  let mockBranchContextValue: any;

  beforeEach(() => {
    mockAuthContextValue = {
      user: { id: 1, email: 'admin@beyondsure.com', role: 'Admin' },
      isAuthenticated: true,
      hasPermission: vi.fn((p: string) => ['shift_assignment.view', 'shift_assignment.manage'].includes(p)),
      loading: false,
      error: null,
      refreshAuth: vi.fn(),
      logout: vi.fn(),
    };

    mockBranchContextValue = {
      selectedBranch: { type: 'branch', branchId: 1, branch: { id: 1, name: 'Mumbai HQ' } },
      branchId: 1,
      branches: [
        { id: 1, organization: 1, name: 'Mumbai HQ', address: 'Nariman Point', is_active: true },
      ],
      isLoading: false,
      error: null,
      selectBranch: vi.fn(),
      refreshBranches: vi.fn(),
    };

    vi.spyOn(AuthContextModule, 'useAuth').mockImplementation(() => mockAuthContextValue);
    vi.spyOn(BranchContextModule, 'useBranchContext').mockImplementation(() => mockBranchContextValue);

    (shiftAssignmentService.listAssignments as any).mockResolvedValue(mockAssignments);
    (shiftService.listShifts as any).mockResolvedValue(mockShifts);
    (employeeManagementService.listEmployees as any).mockResolvedValue(mockEmployees);
    (shiftAssignmentService.create as any).mockResolvedValue({
      id: 504,
      employee: 101,
      shift: 1,
      effective_from: '2026-10-01',
      effective_to: null,
      created_at: '',
      updated_at: '',
    });
    (shiftAssignmentService.update as any).mockResolvedValue({
      id: 501,
      employee: 101,
      shift: 1,
      effective_from: '2026-01-01',
      effective_to: '2026-09-30',
      created_at: '',
      updated_at: '',
    });
    (shiftAssignmentService.delete as any).mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // 1. All Locations state
  it('1. When All Locations is selected, shows prompt and hides mutation buttons without sending all sentinel', async () => {
    mockBranchContextValue.branchId = null;
    mockBranchContextValue.selectedBranch = { type: 'all', branchId: null, branch: null };

    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    expect(screen.getByText(/Select a specific branch from the header to view and manage shift assignments\./i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Assign Shift/i })).not.toBeInTheDocument();
    expect(shiftAssignmentService.listAssignments).not.toHaveBeenCalled();
  });

  // 2. Branch data loading
  it('2. Branch data loading loads assignments, shifts, and active employees in parallel with branch_id', async () => {
    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(shiftAssignmentService.listAssignments).toHaveBeenCalledWith(
        { branch_id: 1 },
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
      expect(shiftService.listShifts).toHaveBeenCalledWith(
        { branch_id: 1 },
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
      expect(employeeManagementService.listEmployees).toHaveBeenCalledWith(
        { branch_id: 1, status: 'active' },
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });
  });

  // 3. Branch switching
  it('3. Branch switching clears stale data and queries newly selected branch', async () => {
    const { rerender } = render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText('Rahul Sharma').length).toBeGreaterThan(0);
    });

    // Switch branch to 2
    mockBranchContextValue.branchId = 2;
    mockBranchContextValue.selectedBranch = { type: 'branch', branchId: 2, branch: { id: 2, name: 'Bangalore Office' } };

    rerender(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(shiftAssignmentService.listAssignments).toHaveBeenCalledWith(
        { branch_id: 2 },
        expect.anything()
      );
    });
  });

  // 4, 5, 6. Table rendering, employee join, and shift join
  it('4, 5, 6. Renders table with joined employee name/code, shift name/timing, and derived status', async () => {
    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      // Employee names & codes
      expect(screen.getAllByText('Rahul Sharma').length).toBeGreaterThan(0);
      expect(screen.getByText('Priya Patel')).toBeInTheDocument();
      expect(screen.getAllByText('EMP-001').length).toBeGreaterThan(0);
      expect(screen.getByText('EMP-002')).toBeInTheDocument();

      // Shifts & timings
      expect(screen.getByText('General Morning Shift')).toBeInTheDocument();
      expect(screen.getAllByText('Night Shift').length).toBeGreaterThan(0);
      expect(screen.getByText('09:00 – 18:00')).toBeInTheDocument();
      expect(screen.getAllByText('21:00 – 06:00').length).toBeGreaterThan(0);

      // Statuses in table
      const table = screen.getByRole('table');
      expect(within(table).getByText('Active')).toBeInTheDocument();
      expect(within(table).getByText('Upcoming')).toBeInTheDocument();
      expect(within(table).getByText('Expired')).toBeInTheDocument();
    });
  });

  // 7. Search filter
  it('7. Searches assignments by employee name or employee code client-side', async () => {
    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Priya Patel')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search by employee name or code/i);
    fireEvent.change(searchInput, { target: { value: 'Priya' } });

    expect(screen.queryByText('Rahul Sharma')).not.toBeInTheDocument();
    expect(screen.getByText('Priya Patel')).toBeInTheDocument();

    // Search by code
    fireEvent.change(searchInput, { target: { value: 'EMP-001' } });
    expect(screen.getAllByText('Rahul Sharma').length).toBe(2);
    expect(screen.queryByText('Priya Patel')).not.toBeInTheDocument();
  });

  // 8. Shift filter
  it('8. Filters assignments by shift client-side', async () => {
    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('General Morning Shift')).toBeInTheDocument();
    });

    const shiftSelect = screen.getByLabelText(/Filter by shift/i);
    // Select Night Shift (id: 2)
    fireEvent.change(shiftSelect, { target: { value: '2' } });

    expect(screen.queryByText('General Morning Shift')).not.toBeInTheDocument();
    expect(screen.getAllByText('Night Shift').length).toBe(2);
  });

  // 9. Status filter
  it('9. Filters assignments by derived status (Active, Upcoming, Expired)', async () => {
    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      const table = screen.getByRole('table');
      expect(within(table).getByText('Active')).toBeInTheDocument();
      expect(within(table).getByText('Upcoming')).toBeInTheDocument();
      expect(within(table).getByText('Expired')).toBeInTheDocument();
    });

    const statusSelect = screen.getByLabelText(/Filter by status/i);

    // Filter by 'upcoming'
    fireEvent.change(statusSelect, { target: { value: 'upcoming' } });
    const tableUpcoming = screen.getByRole('table');
    expect(within(tableUpcoming).queryByText('Active')).not.toBeInTheDocument();
    expect(within(tableUpcoming).queryByText('Expired')).not.toBeInTheDocument();
    expect(within(tableUpcoming).getByText('Upcoming')).toBeInTheDocument();

    // Filter by 'expired'
    fireEvent.change(statusSelect, { target: { value: 'expired' } });
    const tableExpired = screen.getByRole('table');
    expect(within(tableExpired).queryByText('Upcoming')).not.toBeInTheDocument();
    expect(within(tableExpired).getByText('Expired')).toBeInTheDocument();
  });

  // 10 & 11. Assign modal & successful create
  it('10 & 11. Assign modal opens and creates a new shift assignment successfully', async () => {
    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Assign Shift/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Assign Shift/i }));

    expect(screen.getByRole('heading', { name: /Assign Employee Shift/i })).toBeInTheDocument();

    // Fill form
    const employeeSelect = screen.getByLabelText(/^Employee/i);
    const shiftSelect = screen.getByLabelText(/^Shift/i);
    const fromInput = screen.getByLabelText(/Effective From/i);

    fireEvent.change(employeeSelect, { target: { value: '101' } });
    fireEvent.change(shiftSelect, { target: { value: '1' } });
    fireEvent.change(fromInput, { target: { value: '2026-10-01' } });

    // Submit
    const submitBtn = screen.getByRole('button', { name: /Save Shift Assignment/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(shiftAssignmentService.create).toHaveBeenCalledWith({
        employee: 101,
        shift: 1,
        effective_from: '2026-10-01',
        effective_to: null,
      });
      expect(screen.getByText(/Shift assignment created successfully\./i)).toBeInTheDocument();
    });
  });

  // 12. Invalid date range
  it('12. Rejects submission when effective_to is earlier than effective_from', async () => {
    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Assign Shift/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Assign Shift/i }));

    // Uncheck ongoing
    const ongoingToggle = screen.getByLabelText(/Ongoing assignment/i);
    fireEvent.click(ongoingToggle);

    const fromInput = screen.getByLabelText(/Effective From/i);
    const toInput = screen.getByLabelText(/Effective To/i);

    fireEvent.change(fromInput, { target: { value: '2026-10-01' } });
    fireEvent.change(toInput, { target: { value: '2026-09-01' } });

    const submitBtn = screen.getByRole('button', { name: /Save Shift Assignment/i });
    fireEvent.click(submitBtn);

    expect(screen.getByText(/Effective to date cannot be earlier than effective from date\./i)).toBeInTheDocument();
    expect(shiftAssignmentService.create).not.toHaveBeenCalled();
  });

  // 13. Backend overlap error display
  it('13. Displays backend overlap error inside modal when server returns 400', async () => {
    (shiftAssignmentService.create as any).mockRejectedValueOnce({
      status: 400,
      errorData: { effective_from: 'Employee cannot have overlapping shift assignments.' },
    });

    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Assign Shift/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Assign Shift/i }));

    const submitBtn = screen.getByRole('button', { name: /Save Shift Assignment/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Employee cannot have overlapping shift assignments\./i)).toBeInTheDocument();
    });
  });

  // 14. End assignment flow
  it('14. End assignment opens modal with inclusive dates notice and sends PATCH with effective_to', async () => {
    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /End assignment for Rahul Sharma/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /End assignment for Rahul Sharma/i }));

    expect(screen.getByRole('heading', { name: /End Shift Assignment/i })).toBeInTheDocument();
    expect(screen.getByText(/Assignment dates are inclusive\./i)).toBeInTheDocument();

    const endDateInput = screen.getByLabelText(/Effective End Date/i);
    fireEvent.change(endDateInput, { target: { value: '2026-09-30' } });

    fireEvent.click(screen.getByRole('button', { name: /Confirm End Date/i }));

    await waitFor(() => {
      expect(shiftAssignmentService.update).toHaveBeenCalledWith(501, { effective_to: '2026-09-30' });
      expect(screen.getByText(/Shift assignment ended successfully\./i)).toBeInTheDocument();
    });
  });

  // 15. Edit assignment flow
  it('15. Edit assignment allows modifying shift and dates while keeping employee fixed', async () => {
    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /Edit assignment for Rahul Sharma/i }).length).toBeGreaterThan(0);
    });

    const editBtns = screen.getAllByRole('button', { name: /Edit assignment for Rahul Sharma/i });
    fireEvent.click(editBtns[0]);

    expect(screen.getByRole('heading', { name: /Edit Shift Assignment/i })).toBeInTheDocument();

    // Employee field should be disabled in edit mode
    const employeeInput = screen.getByLabelText(/^Employee/i);
    expect(employeeInput).toBeDisabled();

    // Change shift to Night Shift (2)
    const shiftSelect = screen.getByLabelText(/^Shift/i);
    fireEvent.change(shiftSelect, { target: { value: '2' } });

    fireEvent.click(screen.getByRole('button', { name: /Update Assignment/i }));

    await waitFor(() => {
      expect(shiftAssignmentService.update).toHaveBeenCalledWith(501, {
        shift: 2,
        effective_from: '2026-01-01',
        effective_to: null,
      });
      expect(screen.getByText(/Shift assignment updated successfully\./i)).toBeInTheDocument();
    });
  });

  // 16 & 17. Delete confirmation modal & deletion
  it('16 & 17. Delete confirmation shows employee, shift, warning without native window.confirm and performs DELETE', async () => {
    window.confirm = vi.fn();
    const confirmSpy = vi.spyOn(window, 'confirm');

    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /Delete assignment for Rahul Sharma/i }).length).toBeGreaterThan(0);
    });

    const deleteBtns = screen.getAllByRole('button', { name: /Delete assignment for Rahul Sharma/i });
    fireEvent.click(deleteBtns[0]);

    // Native confirm should NEVER be called
    expect(confirmSpy).not.toHaveBeenCalled();

    // Custom modal appears
    expect(screen.getByRole('heading', { name: /Confirm Assignment Deletion/i })).toBeInTheDocument();
    expect(screen.getByText(/Are you sure you want to permanently delete this shift assignment\?/i)).toBeInTheDocument();

    // Confirm deletion
    const confirmDeleteBtn = screen.getByRole('button', { name: /Delete Assignment$/i });
    fireEvent.click(confirmDeleteBtn);

    await waitFor(() => {
      expect(shiftAssignmentService.delete).toHaveBeenCalledWith(501);
      expect(screen.getByText(/Shift assignment deleted successfully\./i)).toBeInTheDocument();
    });
  });

  // 18. View-only permission hides mutation buttons
  it('18. View-only user with shift_assignment.view cannot create, edit, end, or delete assignments', async () => {
    mockAuthContextValue.hasPermission = vi.fn((p: string) => p === 'shift_assignment.view');

    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText('Rahul Sharma').length).toBeGreaterThan(0);
    });

    expect(screen.queryByRole('button', { name: /Assign Shift/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /End assignment/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Edit assignment/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Delete assignment/i })).not.toBeInTheDocument();
  });

  // 19. Manage permission shows mutation buttons
  it('19. User with shift_assignment.manage can see Assign, Edit, End, and Delete controls', async () => {
    mockAuthContextValue.hasPermission = vi.fn((p: string) =>
      ['shift_assignment.view', 'shift_assignment.manage'].includes(p)
    );

    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Assign Shift/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /End assignment for Rahul Sharma/i })).toBeInTheDocument();
    });
  });

  // 20. Access denied when lacking shift_assignment.view
  it('20. Displays 403 Forbidden alert when user lacks shift_assignment.view permission', async () => {
    mockAuthContextValue.hasPermission = vi.fn(() => false);

    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    expect(
      screen.getByText(/403 Forbidden: You do not have permission to view shift assignments\./i)
    ).toBeInTheDocument();
    expect(shiftAssignmentService.listAssignments).not.toHaveBeenCalled();
  });

  // 21. AbortController signal handling
  it('21. Passes AbortSignal to parallel data fetches', async () => {
    render(
      <MemoryRouter>
        <ShiftAssignmentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      const calls = (shiftAssignmentService.listAssignments as any).mock.calls;
      expect(calls[0][1]).toHaveProperty('signal');
      expect(calls[0][1].signal).toBeInstanceOf(AbortSignal);
    });
  });
});
