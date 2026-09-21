import { ApiError } from './employeeManagement';
import type { Shift, CreateShiftPayload, UpdateShiftPayload } from '../types/attendance';

export type { Shift, CreateShiftPayload, UpdateShiftPayload };
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

export const shiftService = {
  listShifts: async (
    params?: { branch_id?: number | string | null },
    options?: { signal?: AbortSignal }
  ): Promise<Shift[]> => {
    let url = '/api/v1/attendance/shifts/';
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
    return handleResponse<Shift[]>(response);
  },

  getAll: async (
    params?: { branch_id?: number | string | null },
    options?: { signal?: AbortSignal }
  ): Promise<Shift[]> => {
    return shiftService.listShifts(params, options);
  },

  getById: async (id: number, options?: { signal?: AbortSignal }): Promise<Shift> => {
    const response = await fetch(`/api/v1/attendance/shifts/${id}/`, {
      headers: getHeaders(false),
      signal: options?.signal,
    });
    return handleResponse<Shift>(response);
  },

  create: async (data: CreateShiftPayload | Partial<Shift>): Promise<Shift> => {
    const response = await fetch('/api/v1/attendance/shifts/', {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(data),
    });
    return handleResponse<Shift>(response);
  },

  update: async (id: number, data: UpdateShiftPayload | Partial<Shift>): Promise<Shift> => {
    const response = await fetch(`/api/v1/attendance/shifts/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(true),
      body: JSON.stringify(data),
    });
    return handleResponse<Shift>(response);
  },

  delete: async (id: number): Promise<void> => {
    const response = await fetch(`/api/v1/attendance/shifts/${id}/`, {
      method: 'DELETE',
      headers: getHeaders(false),
    });
    return handleResponse<void>(response);
  },
};
