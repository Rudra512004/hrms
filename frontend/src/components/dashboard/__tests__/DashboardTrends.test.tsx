import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AttendanceTrendChart } from '../AttendanceTrendChart';
import { WorkforceTrendChart } from '../WorkforceTrendChart';
import { DashboardTrendsSection } from '../DashboardTrendsSection';
import { dashboardService, type AttendanceTrendItem, type WorkforceTrendItem } from '../../../services/dashboard';

describe('Dashboard Trends Component Suite', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mock7dAttendanceData: AttendanceTrendItem[] = [
    {
      date: '2026-09-06',
      day_name: 'Sunday',
      is_working_day: false,
      expected_total: 40,
      expected_working: 0,
      present: 0,
      half_day: 0,
      absent: 0,
      on_leave: 0,
      on_wfh: 0,
      attendance_percentage: null,
    },
    {
      date: '2026-09-07',
      day_name: 'Monday',
      is_working_day: true,
      expected_total: 40,
      expected_working: 38,
      present: 35,
      half_day: 2,
      absent: 1,
      on_leave: 2,
      on_wfh: 4,
      attendance_percentage: 94.7,
    },
    {
      date: '2026-09-08',
      day_name: 'Tuesday',
      is_working_day: true,
      expected_total: 40,
      expected_working: 37,
      present: 34,
      half_day: 1,
      absent: 2,
      on_leave: 3,
      on_wfh: 5,
      attendance_percentage: 93.2,
    },
    {
      date: '2026-09-09',
      day_name: 'Wednesday',
      is_working_day: true,
      expected_total: 40,
      expected_working: 39,
      present: 36,
      half_day: 2,
      absent: 1,
      on_leave: 1,
      on_wfh: 3,
      attendance_percentage: 94.9,
    },
    {
      date: '2026-09-10',
      day_name: 'Thursday',
      is_working_day: true,
      expected_total: 40,
      expected_working: 38,
      present: 33,
      half_day: 3,
      absent: 2,
      on_leave: 2,
      on_wfh: 6,
      attendance_percentage: 90.8,
    },
    {
      date: '2026-09-11',
      day_name: 'Friday',
      is_working_day: true,
      expected_total: 40,
      expected_working: 36,
      present: 30,
      half_day: 2,
      absent: 4,
      on_leave: 4,
      on_wfh: 5,
      attendance_percentage: 86.1,
    },
    {
      date: '2026-09-12',
      day_name: 'Saturday',
      is_working_day: false,
      expected_total: 40,
      expected_working: 0,
      present: 0,
      half_day: 0,
      absent: 0,
      on_leave: 0,
      on_wfh: 0,
      attendance_percentage: null,
    },
  ];

  const mock6mWorkforceData: WorkforceTrendItem[] = [
    {
      period: '2026-04',
      year: 2026,
      month: 4,
      month_name: 'April',
      start_headcount: 35,
      end_headcount: 37,
      new_hires: 3,
      exits: 1,
      net_growth: 2,
      turnover_rate: 2.8,
    },
    {
      period: '2026-05',
      year: 2026,
      month: 5,
      month_name: 'May',
      start_headcount: 37,
      end_headcount: 39,
      new_hires: 2,
      exits: 0,
      net_growth: 2,
      turnover_rate: 0.0,
    },
    {
      period: '2026-06',
      year: 2026,
      month: 6,
      month_name: 'June',
      start_headcount: 39,
      end_headcount: 40,
      new_hires: 2,
      exits: 1,
      net_growth: 1,
      turnover_rate: 2.5,
    },
    {
      period: '2026-07',
      year: 2026,
      month: 7,
      month_name: 'July',
      start_headcount: 40,
      end_headcount: 42,
      new_hires: 3,
      exits: 1,
      net_growth: 2,
      turnover_rate: 2.4,
    },
    {
      period: '2026-08',
      year: 2026,
      month: 8,
      month_name: 'August',
      start_headcount: 42,
      end_headcount: 43,
      new_hires: 2,
      exits: 1,
      net_growth: 1,
      turnover_rate: 2.4,
    },
    {
      period: '2026-09',
      year: 2026,
      month: 9,
      month_name: 'September',
      start_headcount: 43,
      end_headcount: 45,
      new_hires: 2,
      exits: 0,
      net_growth: 2,
      turnover_rate: 0.0,
    },
  ];

  describe('AttendanceTrendChart', () => {
    it('renders 7-day attendance trend with working day metrics and trajectory', () => {
      render(<AttendanceTrendChart data={mock7dAttendanceData} />);

      expect(screen.getByTestId('attendance-trend-chart')).toBeInTheDocument();
      expect(screen.getByText('Net Scheduled Attendance Trajectory')).toBeInTheDocument();

      // Working days average rate should be computed across the 5 working days:
      // (94.7 + 93.2 + 94.9 + 90.8 + 86.1) / 5 = 91.94% -> 91.9%
      expect(screen.getByText('91.9%')).toBeInTheDocument();
      expect(screen.getByText('(5 working days)')).toBeInTheDocument();

      // Check macro aggregates:
      // Present: 35 + 34 + 36 + 33 + 30 = 168
      // Half-day: 2 + 1 + 2 + 3 + 2 = 10 -> Total 178
      expect(screen.getByText('178')).toBeInTheDocument();
      expect(screen.getByText('(10 half-day)')).toBeInTheDocument();

      // Leaves: 2 + 3 + 1 + 2 + 4 = 12
      expect(screen.getAllByText('12')[0]).toBeInTheDocument();

      // WFH overlay instances: 4 + 5 + 3 + 6 + 5 = 23
      expect(screen.getByText('23')).toBeInTheDocument();
    });

    it('clearly distinguishes non-working days (weekends/holidays) and does not show false 0%', () => {
      render(<AttendanceTrendChart data={mock7dAttendanceData} />);

      // Non-working days should have OFF markers
      const offElements = screen.getAllByText('OFF');
      expect(offElements.length).toBeGreaterThanOrEqual(2);

      // Verify that "0%" is not falsely rendered on the Sunday or Saturday node labels
      const sundayTestId = screen.getByTestId('attendance-day-2026-09-06');
      expect(sundayTestId).toBeInTheDocument();
      expect(sundayTestId.textContent).not.toContain('0%');

      // Click on Sunday to inspect detail card
      fireEvent.click(screen.getByTestId('attendance-day-2026-09-06'));
      const detail = screen.getByTestId('attendance-day-detail');
      expect(detail).toBeInTheDocument();
      expect(detail.textContent).toContain('Non-Working / Weekend');
      expect(detail.textContent).toContain('attendance rate not scheduled');
    });

    it('displays interactive detail card when a working day is clicked', () => {
      render(<AttendanceTrendChart data={mock7dAttendanceData} />);

      // Click on Monday
      fireEvent.click(screen.getByTestId('attendance-day-2026-09-07'));
      const detail = screen.getByTestId('attendance-day-detail');
      expect(detail).toBeInTheDocument();
      expect(detail.textContent).toContain('Monday, 2026-09-07');
      expect(detail.textContent).toContain('Working Day');
      expect(detail.textContent).toContain('94.7%');
      expect(detail.textContent).toContain('Present');
      expect(detail.textContent).toContain('35');
      expect(detail.textContent).toContain('Half-Day');
      expect(detail.textContent).toContain('2');
      expect(detail.textContent).toContain('WFH (Overlay)');
      expect(detail.textContent).toContain('4');
    });

    it('renders clean empty state when data array is empty', () => {
      render(<AttendanceTrendChart data={[]} />);
      expect(screen.getByTestId('attendance-trend-empty')).toBeInTheDocument();
      expect(screen.getByText('No attendance trend data available for this period.')).toBeInTheDocument();
    });
  });

  describe('WorkforceTrendChart', () => {
    it('renders 6-month workforce trend with headcount trajectory, new hires, and exits', () => {
      render(<WorkforceTrendChart data={mock6mWorkforceData} />);

      expect(screen.getByTestId('workforce-trend-chart')).toBeInTheDocument();
      expect(screen.getByText('6-Month Active Headcount & Talent Flow')).toBeInTheDocument();

      // Current headcount = 45 (last month), Start = 35, Net = +10
      expect(screen.getAllByText('45')[0]).toBeInTheDocument();
      expect(screen.getByText('+10 net (35 start)')).toBeInTheDocument();

      // Total new hires: 3 + 2 + 2 + 3 + 2 + 2 = 14
      expect(screen.getByText('+14')).toBeInTheDocument();

      // Total exits: 1 + 0 + 1 + 1 + 1 + 0 = 4
      expect(screen.getByText('-4')).toBeInTheDocument();

      // Average monthly turnover rate: (2.8 + 0.0 + 2.5 + 2.4 + 2.4 + 0.0) / 6 = 1.68% -> 1.7%
      expect(screen.getByText('1.7%')).toBeInTheDocument();
    });

    it('displays interactive detail card when a month is clicked', () => {
      render(<WorkforceTrendChart data={mock6mWorkforceData} />);

      // Click on April
      fireEvent.click(screen.getByTestId('workforce-month-2026-04'));
      const detail = screen.getByTestId('workforce-month-detail');
      expect(detail).toBeInTheDocument();
      expect(detail.textContent).toContain('April 2026 (2026-04)');
      expect(detail.textContent).toContain('Net Growth: +2');
      expect(detail.textContent).toContain('Turnover Rate:');
      expect(detail.textContent).toContain('2.8%');
      expect(detail.textContent).toContain('Start Headcount');
      expect(detail.textContent).toContain('35');
      expect(detail.textContent).toContain('End Headcount');
      expect(detail.textContent).toContain('37');
    });

    it('renders clean empty state when data array is empty', () => {
      render(<WorkforceTrendChart data={[]} />);
      expect(screen.getByTestId('workforce-trend-empty')).toBeInTheDocument();
      expect(screen.getByText('No workforce trend data available for this period.')).toBeInTheDocument();
    });
  });

  describe('DashboardTrendsSection', () => {
    it('safely collapses and returns null when caller has no permissions (null trend data)', async () => {
      vi.spyOn(dashboardService, 'getTrends').mockImplementation(async (window) => {
        return {
          window,
          attendance_trend: null,
          workforce_trend: null,
        };
      });

      const { container } = render(<DashboardTrendsSection />);

      // Initially shows loading
      expect(screen.getByTestId('trends-loading')).toBeInTheDocument();

      // After resolution, collapses cleanly without leaking layout
      await waitFor(() => {
        expect(screen.queryByTestId('trends-loading')).not.toBeInTheDocument();
      });

      expect(container.firstChild).toBeNull();
    });

    it('renders tab switch and permits toggling between 7d and 6m when both permissions exist', async () => {
      vi.spyOn(dashboardService, 'getTrends').mockImplementation(async (window) => {
        if (window === '7d') {
          return {
            window: '7d',
            attendance_trend: mock7dAttendanceData,
            workforce_trend: null,
          };
        }
        return {
          window: '6m',
          attendance_trend: null,
          workforce_trend: mock6mWorkforceData,
        };
      });

      render(<DashboardTrendsSection />);

      // Wait for trends to load
      await waitFor(() => {
        expect(screen.getByText('Historical Performance Analytics')).toBeInTheDocument();
      });

      // Both tabs should be rendered
      const tab7d = screen.getByTestId('tab-7d-attendance');
      const tab6m = screen.getByTestId('tab-6m-workforce');
      expect(tab7d).toBeInTheDocument();
      expect(tab6m).toBeInTheDocument();

      // Default active tab is 7-Day Attendance
      expect(screen.getByTestId('attendance-trend-chart')).toBeInTheDocument();
      expect(screen.queryByTestId('workforce-trend-chart')).not.toBeInTheDocument();

      // Switch to 6-Month Headcount tab
      fireEvent.click(tab6m);
      expect(screen.getByTestId('workforce-trend-chart')).toBeInTheDocument();
      expect(screen.queryByTestId('attendance-trend-chart')).not.toBeInTheDocument();

      // Switch back to 7-Day Attendance tab
      fireEvent.click(tab7d);
      expect(screen.getByTestId('attendance-trend-chart')).toBeInTheDocument();
    });

    it('renders only 7-day attendance trend when caller only has attendance.view_all', async () => {
      vi.spyOn(dashboardService, 'getTrends').mockImplementation(async (window) => {
        if (window === '7d') {
          return {
            window: '7d',
            attendance_trend: mock7dAttendanceData,
            workforce_trend: null,
          };
        }
        return {
          window: '6m',
          attendance_trend: null,
          workforce_trend: null, // restricted
        };
      });

      render(<DashboardTrendsSection />);

      await waitFor(() => {
        expect(screen.getByText('Historical Performance Analytics')).toBeInTheDocument();
      });

      // No tab switch should be rendered; instead a single badge
      expect(screen.queryByTestId('tab-6m-workforce')).not.toBeInTheDocument();
      expect(screen.getByText('7-Day Attendance Trend')).toBeInTheDocument();
      expect(screen.getByTestId('attendance-trend-chart')).toBeInTheDocument();
    });

    it('renders only 6-month workforce trend when caller only has employee.view', async () => {
      vi.spyOn(dashboardService, 'getTrends').mockImplementation(async (window) => {
        if (window === '7d') {
          return {
            window: '7d',
            attendance_trend: null, // restricted
            workforce_trend: null,
          };
        }
        return {
          window: '6m',
          attendance_trend: null,
          workforce_trend: mock6mWorkforceData,
        };
      });

      render(<DashboardTrendsSection />);

      await waitFor(() => {
        expect(screen.getByText('Historical Performance Analytics')).toBeInTheDocument();
      });

      // No tab switch; automatically displays workforce trend
      expect(screen.queryByTestId('tab-7d-attendance')).not.toBeInTheDocument();
      expect(screen.getByText('6-Month Headcount Trend')).toBeInTheDocument();
      expect(screen.getByTestId('workforce-trend-chart')).toBeInTheDocument();
    });
  });
});

