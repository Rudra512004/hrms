import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AttendanceManagementPage } from '../AttendanceManagementPage';
import { attendanceService, type AttendanceRecord } from '../../../services/attendance';
import { organizationService, type Team } from '../../../services/organization';
import * as AuthContextModule from '../../../contexts/AuthContext';
import * as BranchContextModule from '../../../contexts/BranchContext';

vi.mock('../../../services/attendance', () => ({
  attendanceService: {
    getManagementHistory: vi.fn(),
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

vi.mock('../../../services/organization', () => ({
  organizationService: {
    listTeams: vi.fn(),
  },
}));

const mockRecords: AttendanceRecord[] = [
  {
    id: 101,
    employee: 1,
    employee_name: 'Alice Smith',
    employee_code: 'EMP-001',
    date: '2026-09-21',
    check_in: '2026-09-21T09:30:00Z',
    check_out: '2026-09-21T18:00:00Z',
    status: 'present',
    is_late: true, // Backend determined late
    total_break_duration: '00:45:00',
    productive_work_duration: '07:45:00',
    is_on_break: false,
    breaks: [],
  },
  {
    id: 102,
    employee: 2,
    employee_name: 'Bob Jones',
    employee_code: 'EMP-002',
    date: '2026-09-21',
    check_in: '2026-09-21T09:00:00Z',
    check_out: '2026-09-21T18:00:00Z',
    status: 'present',
    is_late: false, // Backend determined NOT late
    total_break_duration: '01:00:00',
    productive_work_duration: '08:00:00',
    is_on_break: false,
    breaks: [],
  },
  {
    id: 103,
    employee: 3,
    employee_name: 'Charlie Brown',
    employee_code: 'EMP-003',
    date: '2026-09-21',
    check_in: null,
    check_out: null,
    status: 'absent',
    is_late: false,
    total_break_duration: null,
    productive_work_duration: null,
    is_on_break: false,
    breaks: [],
  },
];

const mockTeams: Team[] = [
  { id: 10, department: 1, name: 'Core Platform', description: 'Platform Team', is_active: true },
  { id: 20, department: 1, name: 'Growth Team', description: 'Growth Team', is_active: true },
];

describe('AttendanceManagementPage (C5.5.4)', () => {
  let mockAuthContextValue: any;
  let mockBranchContextValue: any;

  beforeEach(() => {
    mockAuthContextValue = {
      user: { id: 1, email: 'admin@beyondsure.com', role: 'Super Admin' },
      isAuthenticated: true,
      hasPermission: vi.fn((p: string) => p === 'attendance.view_all'),
      loading: false,
      error: null,
      refreshAuth: vi.fn(),
      logout: vi.fn(),
    };

    mockBranchContextValue = {
      selectedBranch: { type: 'all' },
      branchId: null,
      branches: [
        { id: 1, organization: 1, name: 'Mumbai HQ', address: 'Nariman Point', is_active: true },
        { id: 2, organization: 1, name: 'Pune Tech Park', address: 'Hinjawadi', is_active: true },
      ],
      isLoading: false,
      error: null,
      selectBranch: vi.fn(),
      refreshBranches: vi.fn(),
    };

    vi.spyOn(AuthContextModule, 'useAuth').mockImplementation(() => mockAuthContextValue);
    vi.spyOn(BranchContextModule, 'useBranchContext').mockImplementation(() => mockBranchContextValue);

    (organizationService.listTeams as any).mockResolvedValue(mockTeams);
    (attendanceService.getManagementHistory as any).mockResolvedValue(mockRecords);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('1. All Locations request omits branch_id from parameters', async () => {
    mockBranchContextValue.branchId = null;
    mockBranchContextValue.selectedBranch = { type: 'all' };

    render(
      <MemoryRouter>
        <AttendanceManagementPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(attendanceService.getManagementHistory).toHaveBeenCalled();
    });

    const calledParams = (attendanceService.getManagementHistory as any).mock.calls[0][0];
    expect(calledParams.branch_id).toBeUndefined();
    expect(screen.getByText('Alice Smith')).toBeInTheDocument();
  });

  it('2. Specific branch sends numeric branch_id in request', async () => {
    mockBranchContextValue.branchId = 1;
    mockBranchContextValue.selectedBranch = {
      type: 'branch',
      branchId: 1,
      branch: { id: 1, name: 'Mumbai HQ' },
    };

    render(
      <MemoryRouter>
        <AttendanceManagementPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(attendanceService.getManagementHistory).toHaveBeenCalled();
    });

    const calledParams = (attendanceService.getManagementHistory as any).mock.calls[0][0];
    expect(calledParams.branch_id).toBe(1);
  });

  it('3. Team filter sends team_id in query parameters', async () => {
    render(
      <MemoryRouter>
        <AttendanceManagementPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('All Teams')).toBeInTheDocument();
    });

    const teamSelect = screen.getByLabelText('Filter by team');
    fireEvent.change(teamSelect, { target: { value: '10' } });

    await waitFor(() => {
      const calls = (attendanceService.getManagementHistory as any).mock.calls;
      const lastCallParams = calls[calls.length - 1][0];
      expect(lastCallParams.team_id).toBe(10);
    });
  });

  it('4. Date filter sends date in query parameters and clear date resets it', async () => {
    render(
      <MemoryRouter>
        <AttendanceManagementPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(attendanceService.getManagementHistory).toHaveBeenCalled();
    });

    const dateInput = screen.getByLabelText('Filter by date');
    fireEvent.change(dateInput, { target: { value: '2026-09-20' } });

    await waitFor(() => {
      const calls = (attendanceService.getManagementHistory as any).mock.calls;
      const lastCallParams = calls[calls.length - 1][0];
      expect(lastCallParams.date).toBe('2026-09-20');
    });

    const clearButton = screen.getByRole('button', { name: /clear date/i });
    fireEvent.click(clearButton);

    await waitFor(() => {
      const calls = (attendanceService.getManagementHistory as any).mock.calls;
      const lastCallParams = calls[calls.length - 1][0];
      expect(lastCallParams.date).toBeUndefined();
    });
  });

  it('5. Strictly displays backend is_late without client calculation', async () => {
    render(
      <MemoryRouter>
        <AttendanceManagementPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Alice Smith')).toBeInTheDocument();
    });

    // Alice is marked is_late=true by backend -> should have Late badge
    expect(screen.getByTestId('late-badge-101')).toHaveTextContent('Late');

    // Bob is marked is_late=false -> should NOT have a late badge for id 102
    expect(screen.queryByTestId('late-badge-102')).toBeNull();
  });

  it('6. Displays backend statuses (present, absent) appropriately', async () => {
    render(
      <MemoryRouter>
        <AttendanceManagementPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Alice Smith')).toBeInTheDocument();
    });

    expect(screen.getAllByText('Present').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Absent').length).toBeGreaterThanOrEqual(1);
  });

  it('7. Displays empty state when no records are returned', async () => {
    (attendanceService.getManagementHistory as any).mockResolvedValue([]);

    render(
      <MemoryRouter>
        <AttendanceManagementPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('No attendance records')).toBeInTheDocument();
    });
  });

  it('8. Surfaces backend ApiError properly', async () => {
    (attendanceService.getManagementHistory as any).mockRejectedValue({
      status: 403,
      errorData: { detail: 'You do not have permission to view organization-wide attendance.' },
    });

    render(
      <MemoryRouter>
        <AttendanceManagementPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText(/You do not have permission to view organization-wide attendance/i)
      ).toBeInTheDocument();
    });
  });

  it('9. Hides content and shows alert when user lacks attendance.view_all permission', async () => {
    mockAuthContextValue.hasPermission = vi.fn(() => false);

    render(
      <MemoryRouter>
        <AttendanceManagementPage />
      </MemoryRouter>
    );

    expect(screen.getByText(/You do not have permission to access attendance management/i)).toBeInTheDocument();
    expect(attendanceService.getManagementHistory).not.toHaveBeenCalled();
  });
});
