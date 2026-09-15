export interface PersonalAttendanceToday {
  id: number;
  date: string;
  status: string;
  check_in: string | null;
  check_out: string | null;
  is_on_break: boolean;
  total_break_duration_seconds: number;
  productive_work_duration_seconds: number;
}

export interface PersonalLeaveBalance {
  leave_type_id: number;
  leave_type_name: string;
  allocated: number;
  used: number;
  remaining: number;
}

export interface UpcomingHoliday {
  id: number;
  name: string;
  date: string;
}

export interface PersonalDashboardData {
  attendance_today: PersonalAttendanceToday | null;
  leave_balances: PersonalLeaveBalance[];
  my_pending_requests: {
    leaves: number;
    wfh: number;
    total: number;
  };
  upcoming_holidays: UpcomingHoliday[];
}

export interface TeamPendingLeaveItem {
  id: number;
  employee_id: number;
  employee_name: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  duration_days: number;
  reason: string;
  created_at: string;
}

export interface TeamPendingWFHItem {
  id: number;
  employee_id: number;
  employee_name: string;
  start_at: string;
  end_at: string;
  reason: string;
  requested_at: string;
}

export interface TeamDashboardData {
  direct_reports_count: number;
  attendance_today: {
    present: number;
    half_day: number;
    absent: number;
    on_leave: number;
    on_wfh: number;
    on_break: number;
  };
  pending_approvals: {
    leaves_count: number;
    wfh_count: number;
    leaves: TeamPendingLeaveItem[];
    wfh: TeamPendingWFHItem[];
  };
}

export interface OrganizationWorkforce {
  total_active: number;
  total_onboarding: number;
  total_on_notice: number;
  by_department: Array<{ name: string; count: number }>;
  by_branch: Array<{ name: string; count: number }>;
  recent_hires: Array<{
    id: number;
    name: string;
    department: string | null;
    designation: string | null;
    joining_date: string | null;
  }>;
}

export interface OrganizationAttendanceToday {
  expected_total: number;
  expected_working: number;
  present: number;
  half_day: number;
  absent: number;
  on_leave: number;
  on_wfh: number;
  on_break: number;
  attendance_percentage: number;
}

export interface OrganizationPendingApprovals {
  leaves_count?: number;
  wfh_count?: number;
}

export interface OrganizationDashboardData {
  workforce?: OrganizationWorkforce;
  attendance_today?: OrganizationAttendanceToday;
  pending_approvals?: OrganizationPendingApprovals;
}

export interface DashboardOverviewResponse {
  personal: PersonalDashboardData | null;
  team: TeamDashboardData | null;
  organization: OrganizationDashboardData | null;
}

export interface AttendanceTrendItem {
  date: string;
  day_name: string;
  is_working_day: boolean;
  expected_total: number;
  expected_working: number;
  present: number;
  half_day: number;
  absent: number;
  on_leave: number;
  on_wfh: number;
  attendance_percentage: number | null;
}

export interface WorkforceTrendItem {
  period: string;
  year: number;
  month: number;
  month_name: string;
  start_headcount: number;
  end_headcount: number;
  new_hires: number;
  exits: number;
  net_growth: number;
  turnover_rate: number;
}

export type TrendsWindow = '7d' | '6m';

export interface DashboardTrendsResponse {
  window: TrendsWindow;
  attendance_trend: AttendanceTrendItem[] | null;
  workforce_trend: WorkforceTrendItem[] | null;
}

export const dashboardService = {
  getOverview: async (): Promise<DashboardOverviewResponse> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch('/api/v1/dashboard/overview/', {
      headers: {
        'Authorization': `Token ${token}`,
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }

    return await response.json();
  },

  getTrends: async (window: TrendsWindow): Promise<DashboardTrendsResponse> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch(`/api/v1/dashboard/trends/?window=${window}`, {
      headers: {
        'Authorization': `Token ${token}`,
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }

    return await response.json();
  },
};

