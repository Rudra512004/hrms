import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CalendarPage } from '../CalendarPage';
import { leaveService, type EmployeeCalendarResponse } from '../../services/leaves';
import { employeeManagementService } from '../../services/employeeManagement';
import * as AuthContextModule from '../../contexts/AuthContext';

vi.mock('../../services/leaves', () => ({
  leaveService: {
    getCalendar: vi.fn(),
  },
}));

vi.mock('../../services/employeeManagement', () => ({
  employeeManagementService: {
    listEmployees: vi.fn(),
  },
}));

const getMockCalendarForRange = (start_date: string, end_date: string): EmployeeCalendarResponse => {
  const [yearStr, monthStr] = start_date.split('-');
  const prefix = `${yearStr}-${monthStr}`;
  return {
    employee_id: 1,
    start_date,
    end_date,
    days: [
      {
        date: `${prefix}-01`,
        is_working_day: false,
        holiday: null,
        leave: null,
      },
      {
        date: `${prefix}-02`,
        is_working_day: true,
        holiday: null,
        leave: null,
      },
      {
        date: `${prefix}-05`,
        is_working_day: false,
        holiday: {
          id: 10,
          name: 'Company Foundation Day',
        },
        leave: null,
      },
      {
        date: `${prefix}-10`,
        is_working_day: true,
        holiday: null,
        leave: {
          id: 42,
          leave_type_name: 'Annual Leave',
          duration_days: 1.0,
          is_half_day: false,
        },
      },
      {
        date: `${prefix}-11`,
        is_working_day: true,
        holiday: null,
        leave: {
          id: 43,
          leave_type_name: 'Sick Leave',
          duration_days: 0.5,
          is_half_day: true,
        },
      },
    ],
  };
};

const mockEmployees = [
  {
    id: 1,
    first_name: 'Alice',
    last_name: 'Smith',
    employee_code: 'EMP-001',
    user: { id: 101, email: 'alice@company.com' },
  },
  {
    id: 2,
    first_name: 'Bob',
    last_name: 'Jones',
    employee_code: 'EMP-002',
    user: { id: 102, email: 'bob@company.com' },
  },
];

describe('CalendarPage Component', () => {
  let mockAuthContextValue: any;

  beforeEach(() => {
    vi.clearAllMocks();

    mockAuthContextValue = {
      user: { id: 1, email: 'alice@company.com' },
      isAuthenticated: true,
      hasPermission: vi.fn((perm: string) => perm === 'leave.view'),
      loading: false,
    };

    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue(mockAuthContextValue);
    vi.mocked(leaveService.getCalendar).mockImplementation(async (params) => {
      return getMockCalendarForRange(params.start_date, params.end_date);
    });
    vi.mocked(employeeManagementService.listEmployees).mockResolvedValue(mockEmployees as any);
  });

  it('renders CalendarPage with header, controls, KPI stats, and weekdays', async () => {
    render(
      <MemoryRouter>
        <CalendarPage />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { level: 1, name: 'Employee Calendar' })).toBeInTheDocument();
    expect(screen.getByText('Scheduled Work Days')).toBeInTheDocument();
    expect(screen.getByText('Branch Holidays')).toBeInTheDocument();
    expect(screen.getByText('Approved Leaves')).toBeInTheDocument();

    await waitFor(() => {
      expect(leaveService.getCalendar).toHaveBeenCalledTimes(1);
    });

    // Verify weekdays header
    ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].forEach((day) => {
      expect(screen.getByText(day)).toBeInTheDocument();
    });
  });

  it('displays holidays and approved leaves on the calendar', async () => {
    render(
      <MemoryRouter>
        <CalendarPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Company Foundation Day')).toBeInTheDocument();
      expect(screen.getByText('Annual Leave')).toBeInTheDocument();
      expect(screen.getByText(/Sick Leave/)).toBeInTheDocument();
    });
  });

  it('navigates to next and previous months when chevron buttons are clicked', async () => {
    render(
      <MemoryRouter>
        <CalendarPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(leaveService.getCalendar).toHaveBeenCalledTimes(1);
    });

    const nextBtn = screen.getByLabelText('Next Month');
    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(leaveService.getCalendar).toHaveBeenCalledTimes(2);
    });

    const prevBtn = screen.getByLabelText('Previous Month');
    fireEvent.click(prevBtn);

    await waitFor(() => {
      expect(leaveService.getCalendar).toHaveBeenCalledTimes(3);
    });
  });

  it('opens day details modal when a day cell is clicked', async () => {
    render(
      <MemoryRouter>
        <CalendarPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Company Foundation Day')).toBeInTheDocument();
    });

    // Click on the holiday element
    const holidayBadge = screen.getByText('Company Foundation Day');
    fireEvent.click(holidayBadge);

    await waitFor(() => {
      expect(screen.getByText(/Schedule Details/)).toBeInTheDocument();
      expect(screen.getByText('Public Holiday:')).toBeInTheDocument();
    });

    // Close modal
    const closeBtn = screen.getByRole('button', { name: 'Close' });
    fireEvent.click(closeBtn);

    await waitFor(() => {
      expect(screen.queryByText(/Public Holiday:/)).not.toBeInTheDocument();
    });
  });

  it('allows manager with leave.view to switch between employees', async () => {
    render(
      <MemoryRouter>
        <CalendarPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Employee:/)).toBeInTheDocument();
    });

    const select = screen.getByLabelText(/Employee:/);
    fireEvent.change(select, { target: { value: '2' } });

    await waitFor(() => {
      expect(leaveService.getCalendar).toHaveBeenCalledWith(
        expect.objectContaining({ employee_id: '2' }),
        expect.anything()
      );
    });
  });

  it('displays error banner when calendar API call fails', async () => {
    vi.mocked(leaveService.getCalendar).mockRejectedValueOnce({
      errorData: { detail: 'Employee is not assigned to a branch.' },
    });

    render(
      <MemoryRouter>
        <CalendarPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Employee is not assigned to a branch.')).toBeInTheDocument();
    });
  });
});
