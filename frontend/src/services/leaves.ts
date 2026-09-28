import type { PaginatedResponse } from '../types/pagination';

export interface LeaveType {
  id: number;
  organization: number;
  name: string;
  description: string;
  annual_allocation: number;
  is_active: boolean;
}

export interface LeaveBalance {
  id: number;
  employee: number;
  employee_name?: string;
  employee_code?: string;
  leave_type: number;
  leave_type_name: string;
  allocated: number | string;
  used: number | string;
  carried_forward?: number | string;
  adjustment?: number | string;
  remaining: number | string;
}


export interface LeaveRequest {
  id: number;
  employee: number;
  employee_code?: string;
  employee_name?: string;
  leave_type: number;
  leave_type_name: string;
  start_date: string;
  end_date: string;
  reason: string;
  status: 'pending' | 'approved' | 'rejected' | 'cancelled';
  duration_days: number | string | null;
  is_half_day?: boolean;
  half_day_period?: 'first_half' | 'second_half' | null;
  supporting_document?: string | null;
  requested_at: string;
  reviewed_by: number | null;
  reviewed_at: string | null;
  reviewer_comment: string;
}

export interface CreateLeaveRequestPayload {
  leave_type: number;
  start_date: string;
  end_date: string;
  reason: string;
  is_half_day?: boolean;
  half_day_period?: 'first_half' | 'second_half' | null;
  supporting_document?: File | null;
}

export interface CalendarHoliday {
  id: number;
  name: string;
}

export interface CalendarLeave {
  id: number;
  leave_type_name: string;
  duration_days: number;
  is_half_day: boolean;
}

export interface CalendarDay {
  date: string;
  is_working_day: boolean;
  holiday: CalendarHoliday | null;
  leave: CalendarLeave | null;
}

export interface EmployeeCalendarResponse {
  employee_id: number;
  start_date: string;
  end_date: string;
  days: CalendarDay[];
}

export interface GetCalendarParams {
  start_date: string;
  end_date: string;
  employee_id?: number | string;
}

export interface ListLeaveRequestsParams {
  branch_id?: number | string;
  status?: string;
  employee_id?: number | string;
  paginate?: boolean;
  page?: number;
  page_size?: number;
  search?: string;
}

const getHeaders = () => {
  const token = localStorage.getItem('auth_token');
  if (!token) throw new Error('No authentication token');
  return {
    'Authorization': `Token ${token}`,
    'Content-Type': 'application/json'
  };
};

const handleResponse = async (response: Response) => {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw { response, errorData };
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
};

export const leaveService = {
  getLeaveTypes: async (): Promise<LeaveType[]> => {
    const response = await fetch('/api/v1/leaves/types/', { headers: getHeaders() });
    return handleResponse(response);
  },

  getAdminLeaveTypes: async (): Promise<LeaveType[]> => {
    const response = await fetch('/api/v1/leaves/admin/types/', { headers: getHeaders() });
    return handleResponse(response);
  },

  createLeaveType: async (data: Partial<LeaveType>): Promise<LeaveType> => {
    const response = await fetch('/api/v1/leaves/admin/types/', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data)
    });
    return handleResponse(response);
  },

  updateLeaveType: async (id: number, data: Partial<LeaveType>): Promise<LeaveType> => {
    const response = await fetch(`/api/v1/leaves/admin/types/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify(data)
    });
    return handleResponse(response);
  },

  deleteLeaveType: async (id: number): Promise<void> => {
    const response = await fetch(`/api/v1/leaves/admin/types/${id}/`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    return handleResponse(response);
  },

  getBalances: async (params?: { employee_id?: number | string; leave_type_id?: number | string }): Promise<LeaveBalance[]> => {
    let url = '/api/v1/leaves/balances/';
    if (params) {
      const q = new URLSearchParams();
      if (params.employee_id) q.set('employee_id', String(params.employee_id));
      if (params.leave_type_id) q.set('leave_type_id', String(params.leave_type_id));
      const qs = q.toString();
      if (qs) url += `?${qs}`;
    }
    const response = await fetch(url, { headers: getHeaders() });
    return handleResponse(response);
  },

  adjustBalance: async (balanceId: number, amount: number | string, reason: string): Promise<LeaveBalance> => {
    const response = await fetch(`/api/v1/leaves/balances/${balanceId}/adjust/`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ amount, reason })
    });
    return handleResponse(response);
  },


  getRequests: (async (
    params?: ListLeaveRequestsParams,
    options?: { signal?: AbortSignal }
  ): Promise<any> => {
    let url = '/api/v1/leaves/requests/';
    if (params) {
      const query = new URLSearchParams();
      if (params.paginate) {
        query.set('paginate', 'true');
      }
      if (params.page !== undefined && params.page !== null) {
        query.set('page', String(params.page));
      }
      if (params.page_size !== undefined && params.page_size !== null) {
        query.set('page_size', String(params.page_size));
      }
      if (params.branch_id !== undefined && params.branch_id !== null && params.branch_id !== '' && params.branch_id !== 'all') {
        query.set('branch_id', String(params.branch_id));
      }
      if (params.status && params.status !== 'all') {
        query.set('status', params.status);
      }
      if (params.employee_id) {
        query.set('employee_id', String(params.employee_id));
      }
      if (params.search) {
        query.set('search', params.search);
      }
      const qs = query.toString();
      if (qs) url += `?${qs}`;
    }

    const response = await fetch(url, {
      headers: getHeaders(),
      signal: options?.signal,
    });
    const data = await handleResponse(response);
    if (params?.paginate) {
      if (Array.isArray(data)) {
        return {
          count: data.length,
          next: null,
          previous: null,
          results: data,
        };
      }
      return data;
    }
    return data;
  }) as {
    (params: ListLeaveRequestsParams & { paginate: true }, options?: { signal?: AbortSignal }): Promise<PaginatedResponse<LeaveRequest>>;
    (params?: ListLeaveRequestsParams & { paginate?: false }, options?: { signal?: AbortSignal }): Promise<LeaveRequest[]>;
    (params?: ListLeaveRequestsParams, options?: { signal?: AbortSignal }): Promise<PaginatedResponse<LeaveRequest> | LeaveRequest[]>;
  },

  createRequest: async (data: CreateLeaveRequestPayload): Promise<LeaveRequest> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    let body: any;
    const headers: Record<string, string> = {
      'Authorization': `Token ${token}`,
    };

    if (data.supporting_document) {
      const formData = new FormData();
      formData.append('leave_type', String(data.leave_type));
      formData.append('start_date', data.start_date);
      formData.append('end_date', data.end_date);
      formData.append('reason', data.reason);
      if (data.is_half_day) {
        formData.append('is_half_day', 'true');
        if (data.half_day_period) {
          formData.append('half_day_period', data.half_day_period);
        }
      } else {
        formData.append('is_half_day', 'false');
      }
      formData.append('supporting_document', data.supporting_document);
      body = formData;
    } else {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify({
        leave_type: data.leave_type,
        start_date: data.start_date,
        end_date: data.end_date,
        reason: data.reason,
        is_half_day: !!data.is_half_day,
        ...(data.is_half_day && data.half_day_period ? { half_day_period: data.half_day_period } : {}),
      });
    }

    const response = await fetch('/api/v1/leaves/requests/', {
      method: 'POST',
      headers,
      body,
    });
    return handleResponse(response);
  },

  approveRequest: async (id: number, reviewer_comment?: string): Promise<LeaveRequest> => {
    const response = await fetch(`/api/v1/leaves/requests/${id}/approve/`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ reviewer_comment: reviewer_comment || '' })
    });
    return handleResponse(response);
  },

  rejectRequest: async (id: number, reviewer_comment?: string): Promise<LeaveRequest> => {
    const response = await fetch(`/api/v1/leaves/requests/${id}/reject/`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ reviewer_comment: reviewer_comment || '' })
    });
    return handleResponse(response);
  },

  cancelRequest: async (id: number): Promise<LeaveRequest> => {
    const response = await fetch(`/api/v1/leaves/requests/${id}/cancel/`, {
      method: 'POST',
      headers: getHeaders()
    });
    return handleResponse(response);
  },

  getCalendar: async (params: GetCalendarParams, options?: { signal?: AbortSignal }): Promise<EmployeeCalendarResponse> => {
    const query = new URLSearchParams();
    query.set('start_date', params.start_date);
    query.set('end_date', params.end_date);
    if (params.employee_id !== undefined && params.employee_id !== null && params.employee_id !== '') {
      query.set('employee_id', String(params.employee_id));
    }
    const response = await fetch(`/api/v1/leaves/calendar/?${query.toString()}`, {
      headers: getHeaders(),
      signal: options?.signal,
    });
    return handleResponse(response);
  }
};
