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
  leave_type: number;
  leave_type_name: string;
  allocated: number;
  used: number;
  remaining: number;
}

export interface LeaveRequest {
  id: number;
  employee: number;
  leave_type: number;
  leave_type_name: string;
  start_date: string;
  end_date: string;
  reason: string;
  status: 'pending' | 'approved' | 'rejected' | 'cancelled';
  duration_days: number;
  requested_at: string;
  reviewed_by: number | null;
  reviewed_at: string | null;
  reviewer_comment: string;
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

  getBalances: async (): Promise<LeaveBalance[]> => {
    const response = await fetch('/api/v1/leaves/balances/', { headers: getHeaders() });
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

  createRequest: async (data: { leave_type: number, start_date: string, end_date: string, reason: string }): Promise<LeaveRequest> => {
    const response = await fetch('/api/v1/leaves/requests/', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data)
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
  }
};
