// Payroll API service — mirrors the actual backend contract from:
// apps/payroll/urls.py, views.py, serializers.py
// Base URL: /api/v1/payroll/

const BASE = '/api/v1/payroll';

const getHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('auth_token');
  if (!token) throw new Error('No authentication token');
  return {
    Authorization: `Token ${token}`,
    'Content-Type': 'application/json',
  };
};

const handleResponse = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw { response, errorData };
  }
  if (response.status === 204) return null as unknown as T;
  return response.json() as Promise<T>;
};

// ─── Types ────────────────────────────────────────────────────────────────────

export interface CompensationHistory {
  id: number;
  employee: number;
  employee_code: string;
  effective_from: string;
  effective_to: string | null;
  basic_salary: string;          // DecimalField — always a string from DRF
  created_by: number | null;
  created_by_email: string | null;
  created_at: string;
}

export interface PayrollPeriod {
  id: number;
  organization: number;
  organization_name: string;
  year: number;
  month: number;                 // 1–12
  start_date: string;
  end_date: string;
  status: 'draft' | 'approved';
  generated_at: string | null;
  approved_by: number | null;
  approved_by_email: string | null;
  approved_at: string | null;
  record_count: number;
  created_at: string;
  updated_at: string;
}

export interface PayrollRecord {
  id: number;
  period: number;
  period_label: string;
  employee: number;
  employee_code: string;
  employee_name: string;
  working_days: number;
  present_days: number;
  half_days: number;
  absent_days: number;
  leave_days: number;
  effective_days: string;        // Decimal as string
  // Salary fields — only present when user has payroll.view_sensitive
  basic_salary?: string;
  gross_salary?: string;
  net_salary?: string;
  status: 'draft' | 'approved';
  generated_at: string;
}

export interface CreatePeriodPayload {
  year: number;
  month: number;
  start_date: string;
  end_date: string;
}

export interface SetCompensationPayload {
  employee: number;
  effective_from: string;
  basic_salary: string;
  effective_to?: string;
}

// ─── Service ──────────────────────────────────────────────────────────────────

export const payrollService = {
  // Compensation History
  getCompensation: async (employeeId?: number): Promise<CompensationHistory[]> => {
    const params = employeeId ? `?employee=${employeeId}` : '';
    const res = await fetch(`${BASE}/compensation/${params}`, { headers: getHeaders() });
    return handleResponse<CompensationHistory[]>(res);
  },

  setCompensation: async (data: SetCompensationPayload): Promise<CompensationHistory> => {
    const res = await fetch(`${BASE}/compensation/set/`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<CompensationHistory>(res);
  },

  // Payroll Periods
  getPeriods: async (): Promise<PayrollPeriod[]> => {
    const res = await fetch(`${BASE}/periods/`, { headers: getHeaders() });
    return handleResponse<PayrollPeriod[]>(res);
  },

  createPeriod: async (data: CreatePeriodPayload): Promise<PayrollPeriod> => {
    const res = await fetch(`${BASE}/periods/`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<PayrollPeriod>(res);
  },

  generatePeriod: async (periodId: number): Promise<{ detail: string }> => {
    const res = await fetch(`${BASE}/periods/${periodId}/generate/`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({}),
    });
    return handleResponse<{ detail: string }>(res);
  },

  approvePeriod: async (periodId: number): Promise<PayrollPeriod> => {
    const res = await fetch(`${BASE}/periods/${periodId}/approve/`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({}),
    });
    return handleResponse<PayrollPeriod>(res);
  },

  // Payroll Records
  getRecords: async (periodId?: number, employeeId?: number): Promise<PayrollRecord[]> => {
    const params = new URLSearchParams();
    if (periodId) params.set('period', String(periodId));
    if (employeeId) params.set('employee', String(employeeId));
    const query = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${BASE}/records/${query}`, { headers: getHeaders() });
    return handleResponse<PayrollRecord[]>(res);
  },
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

export const MONTH_NAMES = [
  '', 'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

export const formatCurrency = (value: string | undefined): string => {
  if (value === undefined || value === null) return '—';
  const num = parseFloat(value);
  if (isNaN(num)) return '—';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(num);
};

export const extractApiError = (err: unknown): string => {
  if (err && typeof err === 'object' && 'errorData' in err) {
    const data = (err as any).errorData;
    if (data?.detail) return data.detail;
    const msgs = Object.values(data || {}).flat().join(' ');
    if (msgs) return msgs;
  }
  return 'An unexpected error occurred.';
};
