import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { HolidaysPage } from '../HolidaysPage';
import { holidayService, type Holiday } from '../../../services/holiday';
import * as AuthContextModule from '../../../contexts/AuthContext';
import * as BranchContextModule from '../../../contexts/BranchContext';

vi.mock('../../../services/holiday', () => ({
  holidayService: {
    listHolidays: vi.fn(),
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

const mockHolidays: Holiday[] = [
  {
    id: 1,
    branch: 1,
    name: 'New Year Day',
    date: '2026-01-01',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 2,
    branch: 1,
    name: 'Republic Day',
    date: '2026-01-26',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

describe('HolidaysPage (C5.5.4)', () => {
  let mockAuthContextValue: any;
  let mockBranchContextValue: any;

  beforeEach(() => {
    mockAuthContextValue = {
      user: { id: 1, email: 'admin@beyondsure.com', role: 'Admin' },
      isAuthenticated: true,
      hasPermission: vi.fn((p: string) => ['holiday.view', 'holiday.manage'].includes(p)),
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
        { id: 2, organization: 1, name: 'Pune Tech Park', address: 'Hinjawadi', is_active: true },
      ],
      isLoading: false,
      error: null,
      selectBranch: vi.fn(),
      refreshBranches: vi.fn(),
    };

    vi.spyOn(AuthContextModule, 'useAuth').mockImplementation(() => mockAuthContextValue);
    vi.spyOn(BranchContextModule, 'useBranchContext').mockImplementation(() => mockBranchContextValue);

    (holidayService.listHolidays as any).mockResolvedValue(mockHolidays);
    (holidayService.create as any).mockResolvedValue({
      id: 3,
      branch: 1,
      name: 'Diwali',
      date: '2026-11-08',
      is_active: true,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    });
    (holidayService.update as any).mockResolvedValue({ ...mockHolidays[0], name: 'Updated New Year' });
    (holidayService.delete as any).mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('1. Renders holidays list for the selected branch', async () => {
    render(
      <MemoryRouter>
        <HolidaysPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('New Year Day')).toBeInTheDocument();
      expect(screen.getByText('Republic Day')).toBeInTheDocument();
    });

    expect(holidayService.listHolidays).toHaveBeenCalledWith({ branch_id: 1 }, expect.anything());
  });

  it('2. All Locations prevents mutation and shows banner', async () => {
    mockBranchContextValue.branchId = null;
    mockBranchContextValue.selectedBranch = { type: 'all' };

    render(
      <MemoryRouter>
        <HolidaysPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Select a branch from the header to manage this configuration/i)
      ).toBeInTheDocument();
    });

    const addBtn = screen.getByRole('button', { name: /add holiday/i });
    expect(addBtn).toBeDisabled();
  });

  it('3. Creates a new holiday with branch ID when a branch is selected', async () => {
    render(
      <MemoryRouter>
        <HolidaysPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('New Year Day')).toBeInTheDocument();
    });

    const addBtn = screen.getByRole('button', { name: /add holiday/i });
    fireEvent.click(addBtn);

    expect(screen.getByRole('dialog')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/holiday name/i), { target: { value: 'Diwali' } });
    fireEvent.change(screen.getByLabelText(/date/i), { target: { value: '2026-11-08' } });

    fireEvent.click(screen.getByRole('button', { name: /create holiday/i }));

    await waitFor(() => {
      expect(holidayService.create).toHaveBeenCalledWith({
        branch: 1,
        name: 'Diwali',
        date: '2026-11-08',
        is_active: true,
      });
    });
  });

  it('4. Deletes holiday with confirmation dialog', async () => {
    render(
      <MemoryRouter>
        <HolidaysPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('New Year Day')).toBeInTheDocument();
    });

    const deleteBtn = screen.getByLabelText('Delete New Year Day');
    fireEvent.click(deleteBtn);

    // Confirmation dialog appears
    expect(screen.getByText('Confirm Deletion')).toBeInTheDocument();

    const confirmDeleteBtn = screen.getByRole('button', { name: /^delete$/i });
    fireEvent.click(confirmDeleteBtn);

    await waitFor(() => {
      expect(holidayService.delete).toHaveBeenCalledWith(1);
    });
  });

  it('5. Read-only user without holiday.manage cannot see Add, Edit, or Delete actions', async () => {
    mockAuthContextValue.hasPermission = vi.fn((p: string) => p === 'holiday.view');

    render(
      <MemoryRouter>
        <HolidaysPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('New Year Day')).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /add holiday/i })).toBeNull();
    expect(screen.queryByLabelText('Edit New Year Day')).toBeNull();
    expect(screen.queryByLabelText('Delete New Year Day')).toBeNull();
  });

  it('6. Surfaces backend error banner properly', async () => {
    (holidayService.listHolidays as any).mockRejectedValue({
      status: 403,
      errorData: { detail: '403 Forbidden: You do not have permission to view holidays.' },
    });

    render(
      <MemoryRouter>
        <HolidaysPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/You do not have permission to view holidays/i)).toBeInTheDocument();
    });
  });
});
