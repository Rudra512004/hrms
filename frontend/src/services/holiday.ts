import { ApiError } from './employeeManagement';
import type { Holiday, CreateHolidayPayload, UpdateHolidayPayload } from '../types/attendance';

export type { Holiday, CreateHolidayPayload, UpdateHolidayPayload };
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

export const holidayService = {
  listHolidays: async (
    params?: { branch_id?: number | string | null },
    options?: { signal?: AbortSignal }
  ): Promise<Holiday[]> => {
    let url = '/api/v1/attendance/holidays/';
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
    return handleResponse<Holiday[]>(response);
  },

  getAll: async (
    params?: { branch_id?: number | string | null },
    options?: { signal?: AbortSignal }
  ): Promise<Holiday[]> => {
    return holidayService.listHolidays(params, options);
  },

  getById: async (id: number, options?: { signal?: AbortSignal }): Promise<Holiday> => {
    const response = await fetch(`/api/v1/attendance/holidays/${id}/`, {
      headers: getHeaders(false),
      signal: options?.signal,
    });
    return handleResponse<Holiday>(response);
  },

  create: async (data: CreateHolidayPayload | Partial<Holiday>): Promise<Holiday> => {
    const response = await fetch('/api/v1/attendance/holidays/', {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(data),
    });
    return handleResponse<Holiday>(response);
  },

  update: async (id: number, data: UpdateHolidayPayload | Partial<Holiday>): Promise<Holiday> => {
    const response = await fetch(`/api/v1/attendance/holidays/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(true),
      body: JSON.stringify(data),
    });
    return handleResponse<Holiday>(response);
  },

  delete: async (id: number): Promise<void> => {
    const response = await fetch(`/api/v1/attendance/holidays/${id}/`, {
      method: 'DELETE',
      headers: getHeaders(false),
    });
    return handleResponse<void>(response);
  },
};
