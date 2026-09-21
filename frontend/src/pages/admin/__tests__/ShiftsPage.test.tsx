import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ShiftsPage } from '../ShiftsPage';
import { shiftService, type Shift } from '../../../services/shift';
import * as AuthContextModule from '../../../contexts/AuthContext';
import * as BranchContextModule from '../../../contexts/BranchContext';

vi.mock('../../../services/shift', () => ({
  shiftService: {
    listShifts: vi.fn(),
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

const mockShifts: Shift[] = [
  {
    id: 1,
    branch: 1,
    name: 'General Shift',
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
];

describe('ShiftsPage (C5.5.4)', () => {
  let mockAuthContextValue: any;
  let mockBranchContextValue: any;

  beforeEach(() => {
    mockAuthContextValue = {
      user: { id: 1, email: 'admin@beyondsure.com', role: 'Admin' },
      isAuthenticated: true,
      hasPermission: vi.fn((p: string) => ['shift.view', 'shift.manage'].includes(p)),
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

    (shiftService.listShifts as any).mockResolvedValue(mockShifts);
    (shiftService.create as any).mockResolvedValue({
      id: 2,
      branch: 1,
      name: 'Evening Shift',
      start_time: '14:00:00',
      end_time: '22:00:00',
      grace_period: '00:15:00',
      full_day_hours: '08:00:00',
      half_day_hours: '04:00:00',
      work_days: '0,1,2,3,4',
      is_active: true,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    });
    (shiftService.update as any).mockResolvedValue({ ...mockShifts[0], name: 'Updated Shift' });
    (shiftService.delete as any).mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('1. Renders shift list with timing and work days', async () => {
    render(
      <MemoryRouter>
        <ShiftsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('General Shift')).toBeInTheDocument();
      expect(screen.getByText(/09:00 – 18:00/)).toBeInTheDocument();
      expect(screen.getByText('Mon, Tue, Wed, Thu, Fri')).toBeInTheDocument();
    });

    expect(shiftService.listShifts).toHaveBeenCalledWith({ branch_id: 1 }, expect.anything());
  });

  it('2. All Locations prevents mutation and shows banner', async () => {
    mockBranchContextValue.branchId = null;
    mockBranchContextValue.selectedBranch = { type: 'all' };

    render(
      <MemoryRouter>
        <ShiftsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Select a branch from the header to manage this configuration/i)
      ).toBeInTheDocument();
    });

    const addBtn = screen.getByRole('button', { name: /add shift/i });
    expect(addBtn).toBeDisabled();
  });

  it('3. Creates a shift and serializes day pills to backend contract "0,1,2,3,4"', async () => {
    render(
      <MemoryRouter>
        <ShiftsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('General Shift')).toBeInTheDocument();
    });

    const addBtn = screen.getByRole('button', { name: /add shift/i });
    fireEvent.click(addBtn);

    expect(screen.getByRole('dialog')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/shift name/i), { target: { value: 'Night Shift' } });
    fireEvent.change(screen.getByLabelText(/start time/i), { target: { value: '22:00' } });
    fireEvent.change(screen.getByLabelText(/end time/i), { target: { value: '06:00' } });

    // Toggle Friday off and Saturday on
    const friBtn = screen.getByTitle('Friday');
    const satBtn = screen.getByTitle('Saturday');
    fireEvent.click(friBtn); // Deselects Friday (4)
    fireEvent.click(satBtn); // Selects Saturday (5)

    fireEvent.click(screen.getByRole('button', { name: /create shift/i }));

    await waitFor(() => {
      expect(shiftService.create).toHaveBeenCalledWith({
        branch: 1,
        name: 'Night Shift',
        start_time: '22:00:00',
        end_time: '06:00:00',
        grace_period: '00:15:00',
        full_day_hours: '08:00:00',
        half_day_hours: '04:00:00',
        work_days: '0,1,2,3,5', // Mon, Tue, Wed, Thu, Sat
        is_active: true,
      });
    });
  });

  it('4. Deletes a shift with confirmation dialog', async () => {
    render(
      <MemoryRouter>
        <ShiftsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('General Shift')).toBeInTheDocument();
    });

    const deleteBtn = screen.getByLabelText('Delete General Shift');
    fireEvent.click(deleteBtn);

    expect(screen.getByText('Confirm Deletion')).toBeInTheDocument();

    const confirmBtn = screen.getByRole('button', { name: /^delete$/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(shiftService.delete).toHaveBeenCalledWith(1);
    });
  });

  it('5. Read-only user without shift.manage cannot see Add, Edit, or Delete actions', async () => {
    mockAuthContextValue.hasPermission = vi.fn((p: string) => p === 'shift.view');

    render(
      <MemoryRouter>
        <ShiftsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('General Shift')).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /add shift/i })).toBeNull();
    expect(screen.queryByLabelText('Edit General Shift')).toBeNull();
    expect(screen.queryByLabelText('Delete General Shift')).toBeNull();
  });
});
