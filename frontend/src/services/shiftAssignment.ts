import { ApiError } from './employeeManagement';
import type {
  EmployeeShiftAssignment,
  CreateShiftAssignmentPayload,
  UpdateShiftAssignmentPayload,
} from '../types/attendance';

export type {
  EmployeeShiftAssignment,
  CreateShiftAssignmentPayload,
  UpdateShiftAssignmentPayload,
};
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

export const shiftAssignmentService = {
  listAssignments: async (
    params?: { branch_id?: number | string | null },
    options?: { signal?: AbortSignal }
  ): Promise<EmployeeShiftAssignment[]> => {
    let url = '/api/v1/attendance/shift-assignments/';
    if (
      params?.branch_id !== undefined &&
      params?.branch_id !== null &&
      params?.branch_id !== '' &&
      params?.branch_id !== 'all'
    ) {
      url += `?branch_id=${params.branch_id}`;
    }

    const response = await fetch(url, {
      headers: getHeaders(false),
      signal: options?.signal,
    });
    return handleResponse<EmployeeShiftAssignment[]>(response);
  },

  getById: async (
    id: number,
    options?: { signal?: AbortSignal }
  ): Promise<EmployeeShiftAssignment> => {
    const response = await fetch(`/api/v1/attendance/shift-assignments/${id}/`, {
      headers: getHeaders(false),
      signal: options?.signal,
    });
    return handleResponse<EmployeeShiftAssignment>(response);
  },

  create: async (
    data: CreateShiftAssignmentPayload
  ): Promise<EmployeeShiftAssignment> => {
    const response = await fetch('/api/v1/attendance/shift-assignments/', {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(data),
    });
    return handleResponse<EmployeeShiftAssignment>(response);
  },

  update: async (
    id: number,
    data: UpdateShiftAssignmentPayload
  ): Promise<EmployeeShiftAssignment> => {
    const response = await fetch(`/api/v1/attendance/shift-assignments/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(true),
      body: JSON.stringify(data),
    });
    return handleResponse<EmployeeShiftAssignment>(response);
  },

  delete: async (id: number): Promise<void> => {
    const response = await fetch(`/api/v1/attendance/shift-assignments/${id}/`, {
      method: 'DELETE',
      headers: getHeaders(false),
    });
    return handleResponse<void>(response);
  },
};
