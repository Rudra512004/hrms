import { ApiError } from './employeeManagement';
import type {
  WorkingCalendar,
  WorkingCalendarRule,
  UpdateWorkingCalendarPayload,
} from '../types/attendance';

export type { WorkingCalendar, WorkingCalendarRule, UpdateWorkingCalendarPayload };
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

export const workingCalendarService = {
  listWorkingCalendars: async (
    options?: { signal?: AbortSignal }
  ): Promise<WorkingCalendar[]> => {
    const response = await fetch('/api/v1/organization/working-calendars/', {
      headers: getHeaders(false),
      signal: options?.signal,
    });
    return handleResponse<WorkingCalendar[]>(response);
  },

  getWorkingCalendar: async (
    id: number,
    options?: { signal?: AbortSignal }
  ): Promise<WorkingCalendar> => {
    const response = await fetch(`/api/v1/organization/working-calendars/${id}/`, {
      headers: getHeaders(false),
      signal: options?.signal,
    });
    return handleResponse<WorkingCalendar>(response);
  },

  updateWorkingCalendar: async (
    id: number,
    data: UpdateWorkingCalendarPayload
  ): Promise<WorkingCalendar> => {
    const response = await fetch(`/api/v1/organization/working-calendars/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(true),
      body: JSON.stringify(data),
    });
    return handleResponse<WorkingCalendar>(response);
  },

  /**
   * Strictly parses the configured work days string into integer day values (0=Mon, 6=Sun).
   * Does NOT fall back to Mon–Fri; throws if calendar or work_days is missing/invalid.
   */
  getWorkDaysList: (calendar: { work_days?: string | null }): number[] => {
    if (!calendar || !calendar.work_days || !calendar.work_days.trim()) {
      throw new Error('Working calendar has unconfigured work days.');
    }
    return calendar.work_days
      .split(',')
      .map((d) => {
        const parsed = parseInt(d.trim(), 10);
        if (isNaN(parsed) || parsed < 0 || parsed > 6) {
          throw new Error(`Invalid work day '${d}'. Must be integers between 0 and 6.`);
        }
        return parsed;
      });
  },
};
