import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AdminLeavePage } from '../AdminLeavePage';
import { leaveService, type LeaveRequest } from '../../../services/leaves';
import * as AuthContextModule from '../../../contexts/AuthContext';
import * as BranchContextModule from '../../../contexts/BranchContext';

vi.mock('../../../services/leaves', () => ({
  leaveService: {
    getRequests: vi.fn(),
    approveRequest: vi.fn(),
    rejectRequest: vi.fn(),
  },
}));

const mockRequests: LeaveRequest[] = [
  {
    id: 101,
    employee: 1,
    leave_type: 1,
    leave_type_name: 'Annual Leave',
    start_date: '2026-10-01',
    end_date: '2026-10-03',
    reason: 'Vacation',
    status: 'pending',
    duration_days: 3,
    requested_at: '2026-09-20T10:00:00Z',
    reviewed_by: null,
    reviewed_at: null,
    reviewer_comment: '',
  },
  {
    id: 102,
    employee: 2,
    leave_type: 2,
    leave_type_name: 'Sick Leave',
    start_date: '2026-10-05',
    end_date: '2026-10-05',
    reason: 'Fever',
    status: 'approved',
    duration_days: 1,
    requested_at: '2026-09-21T09:00:00Z',
    reviewed_by: 1,
    reviewed_at: '2026-09-21T11:00:00Z',
    reviewer_comment: 'Approved by manager',
  },
];

describe('AdminLeavePage Pagination & Filtering', () => {
  let mockAuthContextValue: any;
  let mockBranchContextValue: any;

  beforeEach(() => {
    vi.clearAllMocks();

    mockAuthContextValue = {
      user: { id: 99, email: 'admin@company.com', role: 'Super Admin' },
      isAuthenticated: true,
      hasPermission: vi.fn((perm: string) => ['leave.approve', 'leave.reject'].includes(perm)),
      loading: false,
      error: null,
      refreshAuth: vi.fn(),
      logout: vi.fn(),
    };

    mockBranchContextValue = {
      selectedBranch: { type: 'all' },
      branchId: null,
      branches: [
        { id: 1, organization: 1, name: 'Mumbai HQ' },
        { id: 2, organization: 1, name: 'Pune Tech Park' },
      ],
      isLoading: false,
      error: null,
      selectBranch: vi.fn(),
      refreshBranches: vi.fn(),
    };

    vi.spyOn(AuthContextModule, 'useAuth').mockImplementation(() => mockAuthContextValue);
    vi.spyOn(BranchContextModule, 'useBranchContext').mockImplementation(() => mockBranchContextValue);

    (leaveService.getRequests as any).mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: mockRequests,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('1. Requests paginated leave requests on mount', async () => {
    render(
      <MemoryRouter>
        <AdminLeavePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(leaveService.getRequests).toHaveBeenCalledTimes(1);
    });

    const calledParams = (leaveService.getRequests as any).mock.calls[0][0];
    expect(calledParams.paginate).toBe(true);
    expect(calledParams.page).toBe(1);
    expect(calledParams.page_size).toBe(20);
    expect(calledParams.branch_id).toBeUndefined();

    expect(await screen.findByText('Annual Leave')).toBeInTheDocument();
    expect(await screen.findByText('Sick Leave')).toBeInTheDocument();
    expect(screen.getByTestId('table-pagination')).toBeInTheDocument();
  });

  it('2. Specific branch sends branch_id in query parameters', async () => {
    mockBranchContextValue.branchId = 1;

    render(
      <MemoryRouter>
        <AdminLeavePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(leaveService.getRequests).toHaveBeenCalledTimes(1);
    });

    const calledParams = (leaveService.getRequests as any).mock.calls[0][0];
    expect(calledParams.branch_id).toBe(1);
  });

  it('3. Changing status filter resets page to 1 and passes status to API', async () => {
    render(
      <MemoryRouter>
        <AdminLeavePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(leaveService.getRequests).toHaveBeenCalledTimes(1);
    });

    const statusSelect = screen.getByTestId('leave-status-filter');
    fireEvent.change(statusSelect, { target: { value: 'pending' } });

    await waitFor(() => {
      expect(leaveService.getRequests).toHaveBeenCalledTimes(2);
    });

    const secondCallParams = (leaveService.getRequests as any).mock.calls[1][0];
    expect(secondCallParams.status).toBe('pending');
    expect(secondCallParams.page).toBe(1);
  });

  it('4. Navigating page requests next page from backend', async () => {
    (leaveService.getRequests as any).mockResolvedValue({
      count: 40,
      next: 'http://.../?page=2',
      previous: null,
      results: mockRequests,
    });

    render(
      <MemoryRouter>
        <AdminLeavePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(leaveService.getRequests).toHaveBeenCalledTimes(1);
    });

    const nextBtn = screen.getByTestId('pagination-next');
    expect(nextBtn).not.toBeDisabled();
    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(leaveService.getRequests).toHaveBeenCalledTimes(2);
    });

    const secondCallParams = (leaveService.getRequests as any).mock.calls[1][0];
    expect(secondCallParams.page).toBe(2);
  });

  it('5. Handles 403 Forbidden gracefully without crashing', async () => {
    (leaveService.getRequests as any).mockRejectedValue({
      response: { status: 403 },
      status: 403,
    });

    render(
      <MemoryRouter>
        <AdminLeavePage />
      </MemoryRouter>
    );

    expect(await screen.findByText('Access Denied')).toBeInTheDocument();
  });
});
