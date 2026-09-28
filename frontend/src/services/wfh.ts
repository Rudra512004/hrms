export interface WfhRequest {
  id: number;
  employee: number;
  employee_code?: string;
  employee_name?: string;
  start_at: string;
  end_at: string;
  reason: string;
  status: 'pending' | 'approved' | 'rejected' | 'cancelled';
  requested_at: string;
  reviewed_by: number | null;
  reviewed_at: string | null;
  reviewer_comment: string;
}

export interface CreateWfhPayload {
  start_at: string;
  end_at: string;
  reason: string;
}

export const wfhService = {
  create: async (data: CreateWfhPayload): Promise<WfhRequest> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch('/api/v1/employees/wfh-requests/', {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }

    return await response.json();
  },

  getAll: async (params?: { status?: string }): Promise<WfhRequest[]> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    let url = '/api/v1/employees/wfh-requests/';
    if (params?.status && params.status !== 'all') {
      url += `?status=${encodeURIComponent(params.status)}`;
    }

    const response = await fetch(url, {
      headers: {
        'Authorization': `Token ${token}`
      }
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    
    return await response.json();
  },

  approve: async (id: number, reviewer_comment?: string): Promise<WfhRequest> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch(`/api/v1/employees/wfh-requests/${id}/approve/`, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ reviewer_comment: reviewer_comment || '' })
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    
    return await response.json();
  },

  reject: async (id: number, reviewer_comment?: string): Promise<WfhRequest> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch(`/api/v1/employees/wfh-requests/${id}/reject/`, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ reviewer_comment: reviewer_comment || '' })
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    
    return await response.json();
  },

  cancel: async (id: number): Promise<WfhRequest> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch(`/api/v1/employees/wfh-requests/${id}/cancel/`, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}`
      }
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    
    return await response.json();
  }
};
