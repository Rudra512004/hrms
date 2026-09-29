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
        recurring_rules: [],
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

  it('7. Renders recurring rules section and existing recurring overrides', async () => {
    (workingCalendarService.listWorkingCalendars as any).mockResolvedValue([
      {
        id: 10,
        branch: 1,
        work_days: '0,1,2,3,4,5',
        recurring_rules: [
          { id: 101, weekday: 5, occurrence: 1, is_working: false },
          { id: 102, weekday: 5, occurrence: 3, is_working: false },
        ],
      },
    ]);

    render(
      <MemoryRouter>
        <WorkingCalendarPage />
      </MemoryRouter>
    );

    await screen.findByText(/Recurring Monthly Rules/i);
    expect(screen.getByText(/Configured Monthly Overrides/i)).toBeInTheDocument();
    expect(screen.getByTestId('override-chip-5-1')).toHaveTextContent(/1st Saturday/i);
    expect(screen.getByTestId('override-chip-5-3')).toHaveTextContent(/3rd Saturday/i);
  });

  it('8. Configures recurring rule and saves complete payload with recurring_rules', async () => {
    render(
      <MemoryRouter>
        <WorkingCalendarPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Recurring Monthly Rules/i)).toBeInTheDocument();
    });

    // Select Saturday tab for recurring rules
    const satRuleTab = screen.getByTestId('rule-tab-5');
    fireEvent.click(satRuleTab);

    // Toggle 1st Saturday to "Off"
    const firstSatOffBtn = screen.getByTestId('rule-5-1-off');
    fireEvent.click(firstSatOffBtn);

    // Verify configured override chip appeared
    expect(screen.getByTestId('override-chip-5-1')).toHaveTextContent(/1st Saturday/i);

    // Click save
    const saveBtn = screen.getByRole('button', { name: /save working calendar/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(workingCalendarService.updateWorkingCalendar).toHaveBeenCalledWith(10, {
        work_days: '0,1,2,3,4',
        recurring_rules: [
          { weekday: 5, occurrence: 1, is_working: false },
        ],
      });
    });
  });

  it('9. Removes recurring override when toggled back to default', async () => {
    (workingCalendarService.listWorkingCalendars as any).mockResolvedValue([
      {
        id: 10,
        branch: 1,
        work_days: '0,1,2,3,4,5',
        recurring_rules: [
          { id: 101, weekday: 5, occurrence: 1, is_working: false },
        ],
      },
    ]);

    render(
      <MemoryRouter>
        <WorkingCalendarPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Configured Monthly Overrides \(1\):/i)).toBeInTheDocument();
    });

    // Select Saturday tab
    const satRuleTab = screen.getByTestId('rule-tab-5');
    fireEvent.click(satRuleTab);

    // Click Default for 1st Saturday
    const firstSatDefaultBtn = screen.getByTestId('rule-5-1-default');
    fireEvent.click(firstSatDefaultBtn);

    // Override chip should be gone
    expect(screen.queryByText(/Configured Monthly Overrides/i)).toBeNull();

    // Click save
    const saveBtn = screen.getByRole('button', { name: /save working calendar/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(workingCalendarService.updateWorkingCalendar).toHaveBeenCalledWith(10, {
        work_days: '0,1,2,3,4,5',
        recurring_rules: [],
      });
    });
  });
});
