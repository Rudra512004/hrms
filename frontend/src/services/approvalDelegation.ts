export interface ApprovalDelegation {
  id: number;
  organization: number;
  delegator: number;
  delegator_name: string;
  delegate: number;
  delegate_name: string;
  valid_from: string;
  valid_until: string | null;
  delegate_types: string[]; // e.g. ['leave', 'wfh', 'attendance', 'timesheet']
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateDelegationPayload {
  delegate: number;
  valid_from: string;
  valid_until?: string | null;
  delegate_types: string[];
  is_active?: boolean;
}

const getHeaders = (isJson: boolean = true) => {
  const token = localStorage.getItem('auth_token');
  const headers: Record<string, string> = {};
  if (isJson) headers['Content-Type'] = 'application/json';
  if (token) headers['Authorization'] = `Token ${token}`;
  return headers;
};

const handleResponse = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.non_field_errors?.[0] || 'Request failed');
  }
  return response.json();
};

export const approvalDelegationService = {
  list: async (): Promise<ApprovalDelegation[]> => {
    const response = await fetch('/api/v1/employees/approval-delegations/', {
      headers: getHeaders(false),
    });
    return handleResponse<ApprovalDelegation[]>(response);
  },

  create: async (data: CreateDelegationPayload): Promise<ApprovalDelegation> => {
    const response = await fetch('/api/v1/employees/approval-delegations/', {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(data),
    });
    return handleResponse<ApprovalDelegation>(response);
  },

  update: async (id: number, data: Partial<ApprovalDelegation>): Promise<ApprovalDelegation> => {
    const response = await fetch(`/api/v1/employees/approval-delegations/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(true),
      body: JSON.stringify(data),
    });
    return handleResponse<ApprovalDelegation>(response);
  },

  delete: async (id: number): Promise<void> => {
    const response = await fetch(`/api/v1/employees/approval-delegations/${id}/`, {
      method: 'DELETE',
      headers: getHeaders(false),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to delete delegation');
    }
  },
};
