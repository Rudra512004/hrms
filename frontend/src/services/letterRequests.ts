export type LetterRequestType =
  | 'BONAFIDE'
  | 'ADDRESS_PROOF'
  | 'EXPERIENCE'
  | 'SALARY_CERTIFICATE'
  | 'EMPLOYMENT_VERIFICATION'
  | string;

export type LetterRequestStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'ISSUED';

export interface LetterRequest {
  id: number;
  employee: number;
  employee_name: string;
  letter_type: LetterRequestType;
  reason: string;
  status: LetterRequestStatus;
  issued_document: string | null;
  approved_by: number | null;
  approved_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateLetterRequestPayload {
  letter_type: string;
  reason: string;
  employee?: number;
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

export const letterRequestService = {
  list: async (employeeId?: number): Promise<LetterRequest[]> => {
    const url = employeeId
      ? `/api/v1/employees/letter-requests/?employee=${employeeId}`
      : '/api/v1/employees/letter-requests/';
    const response = await fetch(url, {
      headers: getHeaders(false),
    });
    return handleResponse<LetterRequest[]>(response);
  },

  create: async (data: CreateLetterRequestPayload): Promise<LetterRequest> => {
    const response = await fetch('/api/v1/employees/letter-requests/', {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(data),
    });
    return handleResponse<LetterRequest>(response);
  },

  updateStatus: async (id: number, status: 'APPROVED' | 'REJECTED'): Promise<LetterRequest> => {
    const response = await fetch(`/api/v1/employees/letter-requests/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(true),
      body: JSON.stringify({ status }),
    });
    return handleResponse<LetterRequest>(response);
  },
};
