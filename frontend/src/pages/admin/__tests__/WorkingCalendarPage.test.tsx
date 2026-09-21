import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { WorkingCalendarPage } from '../WorkingCalendarPage';
import { workingCalendarService, type WorkingCalendar } from '../../../services/workingCalendar';
import * as AuthContextModule from '../../../contexts/AuthContext';
import * as BranchContextModule from '../../../contexts/BranchContext';

vi.mock('../../../services/workingCalendar', () => ({
  workingCalendarService: {
    listWorkingCalendars: vi.fn(),
    updateWorkingCalendar: vi.fn(),
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

const mockCalendars: WorkingCalendar[] = [
  {
    id: 10,
    branch: 1,
    work_days: '0,1,2,3,4',
  },
];

describe('WorkingCalendarPage (C5.5.4)', () => {
  let mockAuthContextValue: any;
  let mockBranchContextValue: any;

  beforeEach(() => {
    mockAuthContextValue = {
      user: { id: 1, email: 'admin@beyondsure.com', role: 'Admin' },
      isAuthenticated: true,
      hasPermission: vi.fn((p: string) => p === 'organization.update'),
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

    (workingCalendarService.listWorkingCalendars as any).mockResolvedValue(mockCalendars);
    (workingCalendarService.updateWorkingCalendar as any).mockResolvedValue({
      id: 10,
      branch: 1,
      work_days: '0,1,2,3,4,5',
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('1. When All Locations is selected, prompts to select a branch and hides form', async () => {
    mockBranchContextValue.branchId = null;
    mockBranchContextValue.selectedBranch = { type: 'all' };

    render(
      <MemoryRouter>
        <WorkingCalendarPage />
      </MemoryRouter>
    );

    expect(
      screen.getByText(/Select a branch from the header to manage this configuration/i)
    ).toBeInTheDocument();
    expect(screen.queryByText(/Weekly Working Days/i)).toBeNull();
  });

  it('2. Loads calendar for selected branch and displays working days', async () => {
    render(
      <MemoryRouter>
        <WorkingCalendarPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Branch: Mumbai HQ/i)).toBeInTheDocument();
      expect(screen.getByText(/Weekly Working Days/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/5 days configured: Monday, Tuesday, Wednesday, Thursday, Friday/i)).toBeInTheDocument();
  });

  it('3. Toggles working day and saves updated configuration', async () => {
    render(
      <MemoryRouter>
        <WorkingCalendarPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Branch: Mumbai HQ/i)).toBeInTheDocument();
    });

    // Toggle Saturday (5) on
    const satBtn = screen.getByTitle('Saturday');
    fireEvent.click(satBtn);

    const saveBtn = screen.getByRole('button', { name: /save working calendar/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(workingCalendarService.updateWorkingCalendar).toHaveBeenCalledWith(10, {
        work_days: '0,1,2,3,4,5',
      });
    });
  });

  it('4. When working calendar is missing from backend, displays configuration problem without Mon-Fri fallback', async () => {
    (workingCalendarService.listWorkingCalendars as any).mockResolvedValue([]); // No calendar for branch 1

    render(
      <MemoryRouter>
        <WorkingCalendarPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Working calendar is not configured for branch 1/i)
      ).toBeInTheDocument();
    });

    // Form should not pretend Mon-Fri exists
    expect(screen.queryByText(/5 days configured/i)).toBeNull();
  });

  it('5. Surfaces backend 403 error properly', async () => {
    (workingCalendarService.listWorkingCalendars as any).mockRejectedValue({
      status: 403,
      errorData: { detail: '403 Forbidden: You do not have permission to view or manage working calendar.' },
    });

    render(
      <MemoryRouter>
        <WorkingCalendarPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText(/You do not have permission to view or manage working calendar/i)
      ).toBeInTheDocument();
    });
  });

  it('6. Requires organization.update permission to view page', async () => {
    mockAuthContextValue.hasPermission = vi.fn(() => false);

    render(
      <MemoryRouter>
        <WorkingCalendarPage />
      </MemoryRouter>
    );

    expect(
      screen.getByText(/You do not have permission to access working calendar configuration/i)
    ).toBeInTheDocument();
  });
});
