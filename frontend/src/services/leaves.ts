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
  return response.json();
};

export const leaveService = {
  getLeaveTypes: async (): Promise<LeaveType[]> => {
    const response = await fetch('/api/v1/leaves/types/', { headers: getHeaders() });
    return handleResponse(response);
  },

  getBalances: async (): Promise<LeaveBalance[]> => {
    const response = await fetch('/api/v1/leaves/balances/', { headers: getHeaders() });
    return handleResponse(response);
  },

  getRequests: async (): Promise<LeaveRequest[]> => {
    const response = await fetch('/api/v1/leaves/requests/', { headers: getHeaders() });
    return handleResponse(response);
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
