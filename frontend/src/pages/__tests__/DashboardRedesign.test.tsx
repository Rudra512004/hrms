import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { WelcomeBanner } from '../../components/dashboard/WelcomeBanner';
import { TodayAttendanceCard } from '../../components/dashboard/TodayAttendanceCard';
import { AttendanceKpiCards } from '../../components/dashboard/AttendanceKpiCards';
import { AttendanceTrendWidget } from '../../components/dashboard/AttendanceTrendWidget';
import { RecentLeaveRequestsWidget } from '../../components/dashboard/RecentLeaveRequestsWidget';
import { DashboardPage } from '../DashboardPage';

import * as AuthContext from '../../contexts/AuthContext';
import { dashboardService } from '../../services/dashboard';
import { attendanceService } from '../../services/attendance';
import { leaveService } from '../../services/leaves';

// Mock contexts and services
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

vi.mock('../../services/dashboard', () => ({
  dashboardService: {
    getOverview: vi.fn(),
    getTrends: vi.fn(),
  },
}));

vi.mock('../../services/attendance', () => ({
  attendanceService: {
    getHistory: vi.fn(),
    checkIn: vi.fn(),
    checkOut: vi.fn(),
    startBreak: vi.fn(),
    endBreak: vi.fn(),
  },
}));

vi.mock('../../services/leaves', () => ({
  leaveService: {
    getRequests: vi.fn(),
  },
}));

describe('Phase 16B: Role-Aware Employee Dashboard Redesign', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('1. WelcomeBanner Component', () => {
    const mockUser = {
      id: 1,
      email: 'alex.morgan@beyondsure.com',
      firstName: 'Alex',
      lastName: 'Morgan',
      isSuperuser: false,
      designation: 'Senior Software Engineer',
      department: 'Engineering',
      organizationName: 'BeyondSure Labs',
      role: 'employee',
      roles: ['employee'],
      permissions: ['can_view_self'],
    };

    it('renders personalized greeting, user designation, department, and org title', () => {
      render(
        <MemoryRouter>
          <WelcomeBanner
            user={mockUser as any}
            hasEmployeeProfile={true}
            attendanceToday={null}
          />
        </MemoryRouter>
      );

      expect(screen.getByText(/Alex/i)).toBeInTheDocument();
      expect(screen.getByText(/Senior Software Engineer • Engineering/i)).toBeInTheDocument();
      expect(screen.getByText(/BeyondSure Labs • BeyondSure HRMS Workspace/i)).toBeInTheDocument();
      expect(screen.getByText(/Not Clocked In/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Web Check In/i })).toBeInTheDocument();
    });

    it('displays Clocked In status pill when user has active punch', () => {
      render(
        <MemoryRouter>
          <WelcomeBanner
            user={mockUser as any}
            hasEmployeeProfile={true}
            attendanceToday={{
              id: 10,
              date: '2026-10-12',
              status: 'present',
              check_in: '2026-10-12T09:00:00Z',
              check_out: null,
              is_on_break: false,
              total_break_duration_seconds: 0,
              productive_work_duration_seconds: 7200,
            }}
          />
        </MemoryRouter>
      );

      expect(screen.getByText(/Clocked In/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Check Out/i })).toBeInTheDocument();
    });

    it('displays On Break status chip when employee is currently taking a break', () => {
      render(
        <MemoryRouter>
          <WelcomeBanner
            user={mockUser as any}
            hasEmployeeProfile={true}
            attendanceToday={{
              id: 10,
              date: '2026-10-12',
              status: 'present',
              check_in: '2026-10-12T09:00:00Z',
              check_out: null,
              is_on_break: true,
              total_break_duration_seconds: 900,
              productive_work_duration_seconds: 7200,
            }}
          />
        </MemoryRouter>
      );

      expect(screen.getByText(/On Break/i)).toBeInTheDocument();
    });

    it('renders admin badge and admin navigation shortcuts when user lacks employee profile', () => {
      const adminUser = {
        ...mockUser,
        designation: undefined,
        department: undefined,
      };

      render(
        <MemoryRouter>
          <WelcomeBanner
            user={adminUser as any}
            hasEmployeeProfile={false}
          />
        </MemoryRouter>
      );

      expect(screen.getByText(/System Administrator/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Employees/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Attendance/i })).toBeInTheDocument();
    });
  });

  describe('2. TodayAttendanceCard Component', () => {
    it('displays digital clock, unpunched state, and triggers onCheckIn', () => {
      const onCheckIn = vi.fn();
      render(
        <MemoryRouter>
          <TodayAttendanceCard
            attendance={null}
            actionLoading={false}
            actionError={null}
            onCheckIn={onCheckIn}
            onCheckOut={vi.fn()}
            onStartBreak={vi.fn()}
            onEndBreak={vi.fn()}
          />
        </MemoryRouter>
      );

      expect(screen.getByText("Today's Attendance")).toBeInTheDocument();
      expect(screen.getAllByText(/Not Clocked In/i).length).toBeGreaterThanOrEqual(1);
      const checkInBtn = screen.getByRole('button', { name: /Web Punch In/i });
      fireEvent.click(checkInBtn);
      expect(onCheckIn).toHaveBeenCalledTimes(1);
    });

    it('displays active punch durations and enables Take Break and Punch Out', () => {
      const onCheckOut = vi.fn();
      const onStartBreak = vi.fn();

      render(
        <MemoryRouter>
          <TodayAttendanceCard
            attendance={{
              id: 1,
              date: '2026-10-12',
              status: 'present',
              check_in: '2026-10-12T09:15:00Z',
              check_out: null,
              is_on_break: false,
              total_break_duration_seconds: 1200, // 20m
              productive_work_duration_seconds: 14400, // 4h 0m
            }}
            actionLoading={false}
            actionError={null}
            onCheckIn={vi.fn()}
            onCheckOut={onCheckOut}
            onStartBreak={onStartBreak}
            onEndBreak={vi.fn()}
          />
        </MemoryRouter>
      );

      expect(screen.getAllByText(/Working Now/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('4h 0m')).toBeInTheDocument();
      expect(screen.getByText('20m')).toBeInTheDocument();

      const breakBtn = screen.getByRole('button', { name: /Take Break/i });
      fireEvent.click(breakBtn);
      expect(onStartBreak).toHaveBeenCalledTimes(1);

      const checkOutBtn = screen.getByRole('button', { name: /Punch Out/i });
      fireEvent.click(checkOutBtn);
      expect(onCheckOut).toHaveBeenCalledTimes(1);
    });

    it('displays End Break button when on break', () => {
      const onEndBreak = vi.fn();

      render(
        <MemoryRouter>
          <TodayAttendanceCard
            attendance={{
              id: 1,
              date: '2026-10-12',
              status: 'present',
              check_in: '2026-10-12T09:15:00Z',
              check_out: null,
              is_on_break: true,
              total_break_duration_seconds: 900,
              productive_work_duration_seconds: 10800,
            }}
            actionLoading={false}
            actionError={null}
            onCheckIn={vi.fn()}
            onCheckOut={vi.fn()}
            onStartBreak={vi.fn()}
            onEndBreak={onEndBreak}
          />
        </MemoryRouter>
      );

      expect(screen.getByText(/Currently On Break/i)).toBeInTheDocument();
      const endBreakBtn = screen.getByRole('button', { name: /End Break/i });
      fireEvent.click(endBreakBtn);
      expect(onEndBreak).toHaveBeenCalledTimes(1);
    });

    it('disables action buttons when actionLoading is true to prevent duplicate clicks', () => {
      render(
        <MemoryRouter>
          <TodayAttendanceCard
            attendance={null}
            actionLoading={true}
            actionError={null}
            onCheckIn={vi.fn()}
            onCheckOut={vi.fn()}
            onStartBreak={vi.fn()}
            onEndBreak={vi.fn()}
          />
        </MemoryRouter>
      );

      const checkInBtn = screen.getByRole('button', { name: /Web Punch In/i });
      expect(checkInBtn).toBeDisabled();
    });

    it('derives live break duration from current_break_started_at and displays active badge', () => {
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();

      render(
        <MemoryRouter>
          <TodayAttendanceCard
            attendance={{
              id: 1,
              date: '2026-10-12',
              status: 'present',
              check_in: '2026-10-12T09:00:00Z',
              check_out: null,
              is_on_break: true,
              total_break_duration_seconds: 600, // 10 minutes already completed
              current_break_started_at: fiveMinutesAgo, // + 5 minutes live = 15m
              productive_work_duration_seconds: 7200,
            }}
            actionLoading={false}
            actionError={null}
            onCheckIn={vi.fn()}
            onCheckOut={vi.fn()}
            onStartBreak={vi.fn()}
            onEndBreak={vi.fn()}
          />
        </MemoryRouter>
      );

      expect(screen.getByTestId('live-break-badge')).toHaveTextContent('Live');
      expect(screen.getByTestId('live-break-duration')).toHaveTextContent('15m');
      expect(screen.getByText(/Break started at/i)).toBeInTheDocument();
    });

    it('safely handles missing or invalid current_break_started_at without errors', () => {
      render(
        <MemoryRouter>
          <TodayAttendanceCard
            attendance={{
              id: 1,
              date: '2026-10-12',
              status: 'present',
              check_in: '2026-10-12T09:00:00Z',
              check_out: null,
              is_on_break: true,
              total_break_duration_seconds: 600,
              current_break_started_at: 'invalid-date-string',
              productive_work_duration_seconds: 7200,
            }}
            actionLoading={false}
            actionError={null}
            onCheckIn={vi.fn()}
            onCheckOut={vi.fn()}
            onStartBreak={vi.fn()}
            onEndBreak={vi.fn()}
          />
        </MemoryRouter>
      );

      // Falls back safely to total_break_duration_seconds
      expect(screen.getByTestId('live-break-duration')).toHaveTextContent('10m');
    });

    it('recalculates live break duration on document visibilitychange event', () => {
      const initialTime = Date.now();
      const viDateSpy = vi.spyOn(Date, 'now').mockReturnValue(initialTime);
      const tenMinutesAgo = new Date(initialTime - 10 * 60 * 1000).toISOString();

      render(
        <MemoryRouter>
          <TodayAttendanceCard
            attendance={{
              id: 1,
              date: '2026-10-12',
              status: 'present',
              check_in: '2026-10-12T09:00:00Z',
              check_out: null,
              is_on_break: true,
              total_break_duration_seconds: 0,
              current_break_started_at: tenMinutesAgo,
              productive_work_duration_seconds: 7200,
            }}
            actionLoading={false}
            actionError={null}
            onCheckIn={vi.fn()}
            onCheckOut={vi.fn()}
            onStartBreak={vi.fn()}
            onEndBreak={vi.fn()}
          />
        </MemoryRouter>
      );

      expect(screen.getByTestId('live-break-duration')).toHaveTextContent('10m');

      // User returns to tab 5 minutes later
      viDateSpy.mockReturnValue(initialTime + 5 * 60 * 1000);
      Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
      fireEvent(document, new Event('visibilitychange'));

      expect(screen.getByTestId('live-break-duration')).toHaveTextContent('15m');
      viDateSpy.mockRestore();
    });
  });

  describe('3. AttendanceKpiCards Component', () => {
    it('renders 4 employee KPI cards with real calculations', () => {
      render(
        <AttendanceKpiCards
          hasEmployeeProfile={true}
          presentDays={19}
          totalWorkingDays={22}
          attendancePercentage={86.4}
          hoursWorkedFormatted="152h 20m"
          lateArrivals={1}
        />
      );

      expect(screen.getByText('Present Days')).toBeInTheDocument();
      expect(screen.getByText('19')).toBeInTheDocument();
      expect(screen.getByText('/ 22 days')).toBeInTheDocument();

      expect(screen.getByText('Attendance Rate')).toBeInTheDocument();
      expect(screen.getByText('86.4%')).toBeInTheDocument();

      expect(screen.getByText('Hours Worked')).toBeInTheDocument();
      expect(screen.getByText('152h 20m')).toBeInTheDocument();

      expect(screen.getByText('Late Arrivals')).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument();
    });

    it('renders admin fallback KPI cards when hasEmployeeProfile is false', () => {
      render(
        <AttendanceKpiCards
          hasEmployeeProfile={false}
          orgAttendancePercentage={92.5}
          orgActiveWorkforce={48}
          orgPendingApprovals={5}
          teamReportsCount={8}
          teamPresentCount={7}
        />
      );

      expect(screen.getByText(/ORG ATTENDANCE/i)).toBeInTheDocument();
      expect(screen.getByText('92.5%')).toBeInTheDocument();
      expect(screen.getByText(/ACTIVE WORKFORCE/i)).toBeInTheDocument();
      expect(screen.getByText('48')).toBeInTheDocument();
      expect(screen.getByText(/PENDING APPROVALS/i)).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });
  });

  describe('4. AttendanceTrendWidget Component', () => {
    it('renders empty state when no personal records exist', () => {
      render(
        <AttendanceTrendWidget
          personalRecords={[]}
          hasOrgViewPermission={false}
        />
      );

      expect(screen.getByTestId('personal-trend-empty')).toBeInTheDocument();
      expect(screen.getByText(/No Attendance History Yet/i)).toBeInTheDocument();
    });

    it('renders 7-day personal attendance curve with SVG when records are available', () => {
      const records = [
        {
          id: 1,
          employee: 1,
          date: '2026-10-06',
          check_in: '2026-10-06T09:00:00Z',
          check_out: '2026-10-06T17:30:00Z',
          status: 'present',
          is_late: false,
          total_break_duration: '00:45:00',
          productive_work_duration: '07:45:00',
          is_on_break: false,
          breaks: [],
        },
        {
          id: 2,
          employee: 1,
          date: '2026-10-07',
          check_in: '2026-10-07T09:10:00Z',
          check_out: '2026-10-07T17:40:00Z',
          status: 'present',
          is_late: true,
          total_break_duration: '00:30:00',
          productive_work_duration: '08:00:00',
          is_on_break: false,
          breaks: [],
        },
      ];

      render(
        <AttendanceTrendWidget
          personalRecords={records as any}
          hasOrgViewPermission={false}
        />
      );

      expect(screen.getByText('Attendance Trend')).toBeInTheDocument();
      expect(screen.getByRole('img', { name: /Personal attendance hours trend/i })).toBeInTheDocument();
    });
  });

  describe('5. RecentLeaveRequestsWidget Component', () => {
    it('renders empty state when no leave requests exist', () => {
      render(
        <MemoryRouter>
          <RecentLeaveRequestsWidget requests={[]} />
        </MemoryRouter>
      );

      expect(screen.getByTestId('leave-requests-empty')).toBeInTheDocument();
      expect(screen.getByText(/No Leave Requests Found/i)).toBeInTheDocument();
    });

    it('renders up to 5 leave requests with status badges, dates, and durations', () => {
      const requests = [
        {
          id: 101,
          employee: 1,
          leave_type: 1,
          leave_type_name: 'Casual Leave',
          start_date: '2026-10-15',
          end_date: '2026-10-16',
          duration_days: 2,
          reason: 'Family function',
          status: 'approved' as const,
          requested_at: '2026-10-10T10:00:00Z',
          reviewed_by: 2,
          reviewed_at: '2026-10-11T12:00:00Z',
          reviewer_comment: 'Approved',
        },
        {
          id: 102,
          employee: 1,
          leave_type: 2,
          leave_type_name: 'Sick Leave',
          start_date: '2026-10-20',
          end_date: '2026-10-20',
          duration_days: 1,
          reason: 'Doctor appointment',
          status: 'pending' as const,
          requested_at: '2026-10-11T14:00:00Z',
          reviewed_by: null,
          reviewed_at: null,
          reviewer_comment: '',
        },
      ];

      render(
        <MemoryRouter>
          <RecentLeaveRequestsWidget requests={requests as any} />
        </MemoryRouter>
      );

      expect(screen.getByText('Recent Leave Requests')).toBeInTheDocument();
      expect(screen.getByText('Casual Leave')).toBeInTheDocument();
      expect(screen.getByText('2 Days')).toBeInTheDocument();
      expect(screen.getByText(/Family function/i)).toBeInTheDocument();
      expect(screen.getByText('Approved')).toBeInTheDocument();

      expect(screen.getByText('Sick Leave')).toBeInTheDocument();
      expect(screen.getByText('Pending')).toBeInTheDocument();
    });
  });

  describe('6. Redesigned DashboardPage Integration', () => {
    it('assembles the complete role-aware employee dashboard concurrently', async () => {
      vi.mocked(AuthContext.useAuth).mockReturnValue({
        user: {
          id: 1,
          email: 'jordan@beyondsure.com',
          firstName: 'Jordan',
          lastName: 'Lee',
          isSuperuser: false,
          canCreateOrganization: false,
          designation: 'Product Designer',
          department: 'Design',
          organizationName: 'BeyondSure Systems',
        },
        hasEmployeeProfile: true,
        loading: false,
        error: null,
      } as any);

      vi.mocked(dashboardService.getOverview).mockResolvedValue({
        personal: {
          attendance_today: {
            id: 25,
            date: '2026-10-12',
            status: 'present',
            check_in: '2026-10-12T09:00:00Z',
            check_out: null,
            is_on_break: false,
            total_break_duration_seconds: 0,
            productive_work_duration_seconds: 14400,
          },
          leave_balances: [
            { leave_type_id: 1, leave_type_name: 'Earned Leave', allocated: 15, used: 3, remaining: 12 },
          ],
          my_pending_requests: { leaves: 0, wfh: 0, total: 0 },
          upcoming_holidays: [],
        },
        team: null,
        organization: null,
      } as any);

      vi.mocked(attendanceService.getHistory).mockResolvedValue([
        {
          id: 201,
          employee: 1,
          date: '2026-10-08',
          check_in: '2026-10-08T09:00:00Z',
          check_out: '2026-10-08T17:30:00Z',
          status: 'present',
          is_late: false,
          total_break_duration: '00:30:00',
          productive_work_duration: '08:00:00',
          is_on_break: false,
          breaks: [],
        },
      ] as any);

      vi.mocked(leaveService.getRequests).mockResolvedValue([
        {
          id: 301,
          employee: 1,
          leave_type: 1,
          leave_type_name: 'Earned Leave',
          start_date: '2026-10-25',
          end_date: '2026-10-26',
          duration_days: 2,
          reason: 'Vacation',
          status: 'approved',
          requested_at: '2026-10-01T10:00:00Z',
          reviewed_by: 2,
          reviewed_at: '2026-10-02T10:00:00Z',
          reviewer_comment: 'Approved',
        },
      ] as any);

      render(
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText(/Jordan/i)).toBeInTheDocument();
      });

      // Verify Welcome Banner
      expect(screen.getByTestId('welcome-banner')).toBeInTheDocument();
      expect(screen.getByText(/Product Designer • Design/i)).toBeInTheDocument();

      // Verify Attendance KPI Cards
      expect(screen.getByTestId('attendance-kpi-grid')).toBeInTheDocument();
      expect(screen.getByText('Present Days')).toBeInTheDocument();
      expect(screen.getByText('Attendance Rate')).toBeInTheDocument();
      expect(screen.getByText('Hours Worked')).toBeInTheDocument();
      expect(screen.getByText('Late Arrivals')).toBeInTheDocument();

      // Verify Today's Attendance Terminal
      expect(screen.getByTestId('today-attendance-card')).toBeInTheDocument();
      expect(screen.getAllByText(/Working Now/i).length).toBeGreaterThanOrEqual(1);

      // Verify Attendance Trend Widget
      expect(screen.getByTestId('attendance-trend-widget')).toBeInTheDocument();

      // Verify Recent Leave Requests Widget
      expect(screen.getByTestId('recent-leave-requests-widget')).toBeInTheDocument();
      expect(screen.getAllByText(/Earned Leave/i).length).toBeGreaterThanOrEqual(1);
    });
  });
});
