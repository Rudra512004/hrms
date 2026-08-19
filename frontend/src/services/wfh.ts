export interface WfhRequest {
  id: number;
  employee: number;
  start_at: string;
  end_at: string;
  reason: string;
  status: 'pending' | 'approved' | 'rejected' | 'cancelled';
  requested_at: string;
  reviewed_by: number | null;
  reviewed_at: string | null;
  reviewer_comment: string;
}

export const wfhService = {
  getAll: async (): Promise<WfhRequest[]> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch('/api/v1/employees/wfh-requests/', {
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
