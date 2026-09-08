// Payroll Reporting API service — mirrors backend contract from:
// apps/payroll/views_reporting.py & serializers_reporting.py
// Base URL: /api/v1/payroll/reports/

const BASE = '/api/v1/payroll/reports';

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
  return response.json() as Promise<T>;
};

// ─── Interfaces ──────────────────────────────────────────────────────────────

export interface PeriodMetadata {
  id: number;
  year: number;
  month: number;
  label: string;
  status: 'draft' | 'approved';
  start_date: string;
  end_date: string;
}

export interface PeriodSummaryMetrics {
  total_employees: number;
  total_basic_salary: string | null;
  total_gross_salary: string | null;
  total_net_salary: string | null;
  total_loss_of_pay: string | null;
  average_net_salary: string | null;
  scheduled_working_days: number;
  total_present_days: number;
  total_half_days: number;
  total_leave_days: number;
  total_absent_days: number;
  total_effective_paid_days: string;
}

export interface PeriodSummaryResponse {
  period: PeriodMetadata;
  summary: PeriodSummaryMetrics;
}

export interface ReconciliationRecord {
  id: number;
  employee_id: number;
  employee_code: string;
  employee_name: string;
  branch_name: string;
  department_name: string;
  working_days: number;
  present_days: number;
  half_days: number;
  leave_days: number;
  absent_days: number;
  effective_days: string;
  basic_salary: string | null;
  gross_salary: string | null;
  net_salary: string | null;
  loss_of_pay_amount: string | null;
  status: string;
}

export interface BranchBreakdown {
  branch_id: number | null;
  branch_name: string;
  headcount: number;
  total_net_salary: string | null;
  average_net_salary: string | null;
}

export interface DepartmentBreakdown {
  department_id: number | null;
  department_name: string;
  headcount: number;
  total_net_salary: string | null;
  average_net_salary: string | null;
}

export interface OrganizationBreakdownResponse {
  by_branch: BranchBreakdown[];
  by_department: DepartmentBreakdown[];
}

export interface PayrollExceptionItem {
  type: string;
  severity: 'high' | 'medium' | 'low';
  employee_id: number;
  employee_code: string;
  employee_name: string;
  message: string;
}

export interface ReconciliationFilters {
  period: number;
  branch?: number | string;
  department?: number | string;
  search?: string;
}

// ─── API Methods ─────────────────────────────────────────────────────────────

export const getPeriodSummary = async (periodId: number): Promise<PeriodSummaryResponse> => {
  const res = await fetch(`${BASE}/period-summary/?period=${periodId}`, {
    headers: getHeaders(),
  });
  return handleResponse<PeriodSummaryResponse>(res);
};

export const getReconciliationRecords = async (
  filters: ReconciliationFilters
): Promise<ReconciliationRecord[]> => {
  const params = new URLSearchParams();
  params.set('period', String(filters.period));
  if (filters.branch) params.set('branch', String(filters.branch));
  if (filters.department) params.set('department', String(filters.department));
  if (filters.search && filters.search.trim()) params.set('search', filters.search.trim());

  const res = await fetch(`${BASE}/reconciliation/?${params.toString()}`, {
    headers: getHeaders(),
  });
  const data = await handleResponse<{ period_id: number; count: number; records: ReconciliationRecord[] }>(res);
  return data.records || [];
};

export const getOrganizationBreakdown = async (
  periodId: number
): Promise<OrganizationBreakdownResponse> => {
  const res = await fetch(`${BASE}/organization-breakdown/?period=${periodId}`, {
    headers: getHeaders(),
  });
  return handleResponse<OrganizationBreakdownResponse>(res);
};

export const getPayrollExceptions = async (
  periodId: number
): Promise<PayrollExceptionItem[]> => {
  const res = await fetch(`${BASE}/exceptions/?period=${periodId}`, {
    headers: getHeaders(),
  });
  const data = await handleResponse<{ period_id: number; count: number; exceptions: PayrollExceptionItem[] }>(res);
  return data.exceptions || [];
};
