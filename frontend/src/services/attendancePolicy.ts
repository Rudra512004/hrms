import { ApiError } from './employeeManagement';
import type {
  AttendancePolicy,
  UpdateAttendancePolicyPayload,
} from '../types/attendance';

export type { AttendancePolicy, UpdateAttendancePolicyPayload };
export { ApiError };

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

export const attendancePolicyService = {
  getAttendancePolicy: async (
    branchId: number,
    options?: { signal?: AbortSignal }
  ): Promise<AttendancePolicy> => {
    const response = await fetch(`/api/v1/organization/branches/${branchId}/attendance-policy/`, {
      headers: getHeaders(false),
      signal: options?.signal,
    });
    return handleResponse<AttendancePolicy>(response);
  },

  updateAttendancePolicy: async (
    branchId: number,
    data: UpdateAttendancePolicyPayload
  ): Promise<AttendancePolicy> => {
    const response = await fetch(`/api/v1/organization/branches/${branchId}/attendance-policy/`, {
      method: 'PATCH',
      headers: getHeaders(true),
      body: JSON.stringify(data),
    });
    return handleResponse<AttendancePolicy>(response);
  },
};
