import { ApiError } from './employeeManagement';

export interface ProductivityOverview {
  attendance_count: number;
  total_online_duration: string;
  total_active_duration: string;
  total_idle_duration: string;
  total_productive_duration: string;
  total_unproductive_duration: string;
  total_neutral_duration: string;
  total_break_duration: string;
  average_active_percent: number;
  total_mouse_clicks: number;
  total_key_presses: number;
}

export interface ProductivityTrend {
  date: string;
  attendance_count: number;
  total_online_duration: string;
  total_active_duration: string;
  total_idle_duration: string;
  total_productive_duration: string;
  total_break_duration: string;
  average_active_percent: number;
}

export interface TeamBreakdown {
  team_id: number;
  team_name: string;
  attendance_count: number;
  total_active_duration: string;
  total_idle_duration: string;
  total_productive_duration: string;
  average_active_percent: number;
}

export interface EmployeeBreakdown {
  employee_id: number;
  employee_name: string;
  attendance_count: number;
  total_online_duration: string;
  total_active_duration: string;
  total_idle_duration: string;
  total_productive_duration: string;
  total_unproductive_duration: string;
  average_active_percent: number;
}

export interface ProductivityParams {
  start_date: string;
  end_date: string;
  branch_id?: number | string;
  department_id?: number | string;
  team_id?: number | string;
  employee_id?: number | string;
}

const getHeaders = (includeContentType = true): HeadersInit => {
  const token = localStorage.getItem('auth_token');
  const headers: Record<string, string> = {
    'Accept': 'application/json',
  };
  if (includeContentType) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) {
    headers['Authorization'] = `Token ${token}`;
  }
  return headers;
};

const handleResponse = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(response, errorData);
  }
  if (response.status === 204) return null as unknown as T;
  return response.json();
};

const buildQueryString = (params: any) => {
  const searchParams = new URLSearchParams();
  for (const key in params) {
    if (params[key] !== undefined && params[key] !== null && params[key] !== '') {
      searchParams.append(key, String(params[key]));
    }
  }
  const str = searchParams.toString();
  return str ? `?${str}` : '';
};

export const productivityService = {
  getOverview: async (params: ProductivityParams): Promise<ProductivityOverview> => {
    const qs = buildQueryString(params);
    const response = await fetch(`/api/v1/attendance/productivity/overview/${qs}`, {
      headers: getHeaders(false),
    });
    return handleResponse<ProductivityOverview>(response);
  },

  getTrends: async (params: ProductivityParams): Promise<ProductivityTrend[]> => {
    const qs = buildQueryString(params);
    const response = await fetch(`/api/v1/attendance/productivity/trends/${qs}`, {
      headers: getHeaders(false),
    });
    return handleResponse<ProductivityTrend[]>(response);
  },

  getTeamBreakdown: async (params: ProductivityParams): Promise<TeamBreakdown[]> => {
    const qs = buildQueryString(params);
    const response = await fetch(`/api/v1/attendance/productivity/team-breakdown/${qs}`, {
      headers: getHeaders(false),
    });
    return handleResponse<TeamBreakdown[]>(response);
  },

  getEmployeeBreakdown: async (params: ProductivityParams): Promise<EmployeeBreakdown[]> => {
    const qs = buildQueryString(params);
    const response = await fetch(`/api/v1/attendance/productivity/employee-breakdown/${qs}`, {
      headers: getHeaders(false),
    });
    return handleResponse<EmployeeBreakdown[]>(response);
  },
};
