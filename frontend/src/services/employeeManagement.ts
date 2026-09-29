import { type EmployeeProfile } from './employee';

export interface ProvisionEmployeeData {
  email: string;
  first_name: string;
  last_name: string;
  personal_email?: string;
  employee_code?: string;
  organization?: number;
  branch?: number | null;
  department?: number | null;
  team?: number | null;
  designation?: number | null;
  reporting_manager?: number | null;
  role?: number | null;
}

export interface ProvisionEmployeeResponse {
  detail: string;
  employee: EmployeeProfile;
  activation_info?: {
    uid: string;
    token: string;
  };
  onboarding_email_status?: string;
}

export interface UpdateEmployeePayload {
  phone_number?: string;
  address?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  team?: number | null;
  designation?: number | null;
  reporting_manager?: number | null;
  joining_date?: string | null;
  notice_period_start?: string | null;
  notice_period_end?: string | null;
  exit_reason?: string;
  [key: string]: any;
}

export interface EmployeeTransferPayload {
  branch?: number | null;
  department?: number | null;
  team?: number | null;
  effective_date: string;
  reason?: string;
}

export interface EmployeePromotionPayload {
  designation: number;
  effective_date: string;
  reason?: string;
  new_basic_salary?: number | string | null;
}

export type EmployeeExitType = 'resignation' | 'termination' | 'end_of_contract' | 'retirement' | 'other';

export interface EmployeeExitPayload {
  exit_type: EmployeeExitType;
  exit_date: string;
  exit_reason?: string;
  resignation_date?: string | null;
  notice_period_start?: string | null;
  notice_period_end?: string | null;
  set_notice_status?: boolean;
}

export interface EmployeeReactivatePayload {
  reason?: string;
}

export interface ChangeEmploymentStatusPayload {
  employment_status: string;
  reason?: string;
}

export interface EmployeeLifecycleEvent {
  id: number;
  employee: number;
  event_type: string;
  event_type_display?: string;
  from_status?: string | null;
  to_status?: string | null;
  from_department?: number | null;
  from_department_name?: string;
  to_department?: number | null;
  to_department_name?: string;
  from_branch?: number | null;
  from_branch_name?: string;
  to_branch?: number | null;
  to_branch_name?: string;
  from_designation?: number | null;
  from_designation_name?: string;
  to_designation?: number | null;
  to_designation_name?: string;
  effective_date: string;
  reason?: string;
  created_by?: number | null;
  created_by_email?: string;
  created_at: string;
}

export interface ListEmployeesParams {
  branch_id?: number | string;
  search?: string;
  status?: string;
}

export class ApiError extends Error {
  response: Response;
  status: number;
  errorData: any;

  constructor(response: Response, errorData: any, message?: string) {
    const detail = errorData?.detail || errorData?.message || (typeof errorData === 'string' ? errorData : undefined);
    super(message || detail || `API Request Failed with status ${response.status}`);
    this.name = 'ApiError';
    this.response = response;
    this.status = response.status;
    this.errorData = errorData;
  }
}

const getHeaders = (includeContentType = true): HeadersInit => {
  const token = localStorage.getItem('auth_token');
  if (!token) throw new Error('No authentication token');
  const headers: Record<string, string> = {
    'Authorization': `Token ${token}`,
    'Accept': 'application/json'
  };
  if (includeContentType) {
    headers['Content-Type'] = 'application/json';
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

export const employeeManagementService = {
  listEmployees: async (
    params?: ListEmployeesParams,
    options?: { signal?: AbortSignal }
  ): Promise<EmployeeProfile[]> => {
    let url = '/api/v1/employees/management/';
    if (params) {
      const query = new URLSearchParams();
      if (params.branch_id !== undefined && params.branch_id !== null && params.branch_id !== '') {
        query.set('branch_id', String(params.branch_id));
      }
      if (params.search) {
        query.set('search', params.search);
      }
      if (params.status) {
        query.set('status', params.status);
      }
      const qs = query.toString();
      if (qs) url += `?${qs}`;
    }

    const response = await fetch(url, {
      headers: getHeaders(false),
      signal: options?.signal,
    });

    return handleResponse<EmployeeProfile[]>(response);
  },

  getEmployee: async (id: number): Promise<EmployeeProfile> => {
    const response = await fetch(`/api/v1/employees/management/${id}/`, {
      headers: getHeaders(false)
    });

    return handleResponse<EmployeeProfile>(response);
  },

  createEmployee: async (data: ProvisionEmployeeData): Promise<ProvisionEmployeeResponse> => {
    const response = await fetch('/api/v1/employees/management/', {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(data)
    });

    return handleResponse<ProvisionEmployeeResponse>(response);
  },

  updateEmployee: async (
    id: number,
    data: Partial<EmployeeProfile> | UpdateEmployeePayload
  ): Promise<EmployeeProfile> => {
    const response = await fetch(`/api/v1/employees/management/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(true),
      body: JSON.stringify(data)
    });

    return handleResponse<EmployeeProfile>(response);
  },

  activateEmployee: async (id: number): Promise<EmployeeProfile> => {
    const response = await fetch(`/api/v1/employees/management/${id}/activate/`, {
      method: 'POST',
      headers: getHeaders(false)
    });

    return handleResponse<EmployeeProfile>(response);
  },

  deactivateEmployee: async (id: number): Promise<EmployeeProfile> => {
    const response = await fetch(`/api/v1/employees/management/${id}/deactivate/`, {
      method: 'POST',
      headers: getHeaders(false)
    });

    return handleResponse<EmployeeProfile>(response);
  },

  changeEmploymentStatus: async (
    id: number,
    payload: string | ChangeEmploymentStatusPayload
  ): Promise<EmployeeProfile> => {
    const body = typeof payload === 'string'
      ? { employment_status: payload }
      : payload;

    const response = await fetch(`/api/v1/employees/management/${id}/change_employment_status/`, {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(body)
    });

    return handleResponse<EmployeeProfile>(response);
  },

  transferEmployee: async (id: number, payload: EmployeeTransferPayload): Promise<EmployeeProfile> => {
    const response = await fetch(`/api/v1/employees/management/${id}/transfer/`, {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(payload)
    });

    return handleResponse<EmployeeProfile>(response);
  },

  promoteEmployee: async (id: number, payload: EmployeePromotionPayload): Promise<EmployeeProfile> => {
    const response = await fetch(`/api/v1/employees/management/${id}/promote/`, {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(payload)
    });

    return handleResponse<EmployeeProfile>(response);
  },

  exitEmployee: async (id: number, payload: EmployeeExitPayload): Promise<EmployeeProfile> => {
    const response = await fetch(`/api/v1/employees/management/${id}/exit/`, {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(payload)
    });

    return handleResponse<EmployeeProfile>(response);
  },

  reactivateEmployee: async (id: number, payload?: EmployeeReactivatePayload): Promise<EmployeeProfile> => {
    const response = await fetch(`/api/v1/employees/management/${id}/reactivate/`, {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(payload || {})
    });

    return handleResponse<EmployeeProfile>(response);
  },

  getLifecycleHistory: async (id: number): Promise<EmployeeLifecycleEvent[]> => {
    const response = await fetch(`/api/v1/employees/management/${id}/lifecycle_history/`, {
      headers: getHeaders(false)
    });

    return handleResponse<EmployeeLifecycleEvent[]>(response);
  }
};
