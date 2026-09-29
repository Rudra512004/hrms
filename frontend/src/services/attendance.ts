import { ApiError } from './employeeManagement';
import type {
  AttendanceRecord,
  AttendanceBreak,
  AttendanceLocation,
  ManagementAttendanceParams,
} from '../types/attendance';

export type { AttendanceRecord, AttendanceBreak, AttendanceLocation, ManagementAttendanceParams };
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

export const attendanceService = {
  // Self operations
  getHistory: async (options?: { signal?: AbortSignal }): Promise<AttendanceRecord[]> => {
    const response = await fetch('/api/v1/attendance/', {
      headers: getHeaders(false),
      signal: options?.signal,
    });
    return handleResponse<AttendanceRecord[]>(response);
  },

  checkIn: async (location?: AttendanceLocation): Promise<AttendanceRecord> => {
    const response = await fetch('/api/v1/attendance/check-in/', {
      method: 'POST',
      headers: getHeaders(Boolean(location)),
      body: location ? JSON.stringify(location) : undefined,
    });
    return handleResponse<AttendanceRecord>(response);
  },

  checkOut: async (location?: AttendanceLocation): Promise<AttendanceRecord> => {
    const response = await fetch('/api/v1/attendance/check-out/', {
      method: 'POST',
      headers: getHeaders(Boolean(location)),
      body: location ? JSON.stringify(location) : undefined,
    });
    return handleResponse<AttendanceRecord>(response);
  },

  startBreak: async (location?: AttendanceLocation): Promise<AttendanceRecord> => {
    const response = await fetch('/api/v1/attendance/start-break/', {
      method: 'POST',
      headers: getHeaders(Boolean(location)),
      body: location ? JSON.stringify(location) : undefined,
    });
    return handleResponse<AttendanceRecord>(response);
  },

  endBreak: async (location?: AttendanceLocation): Promise<AttendanceRecord> => {
    const response = await fetch('/api/v1/attendance/end-break/', {
      method: 'POST',
      headers: getHeaders(Boolean(location)),
      body: location ? JSON.stringify(location) : undefined,
    });
    return handleResponse<AttendanceRecord>(response);
  },

  // Management operations
  getManagementHistory: async (
    params?: ManagementAttendanceParams,
    options?: { signal?: AbortSignal }
  ): Promise<AttendanceRecord[]> => {
    let url = '/api/v1/attendance/management/';
    if (params) {
      const query = new URLSearchParams();
      if (
        params.branch_id !== undefined &&
        params.branch_id !== null &&
        params.branch_id !== '' &&
        params.branch_id !== 'all'
      ) {
        query.set('branch_id', String(params.branch_id));
      }
      if (
        params.team_id !== undefined &&
        params.team_id !== null &&
        params.team_id !== ''
      ) {
        query.set('team_id', String(params.team_id));
      }
      if (params.date) {
        query.set('date', params.date);
      }
      const qs = query.toString();
      if (qs) url += `?${qs}`;
    }

    const response = await fetch(url, {
      headers: getHeaders(false),
      signal: options?.signal,
    });

    return handleResponse<AttendanceRecord[]>(response);
  },
};
