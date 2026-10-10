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
  status: 'draft' | 'locked' | 'processing' | 'review' | 'finalized' | 'disbursed';
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
  lop_days?: string;             // Decimal as string
  // Salary fields — only present when user has payroll.view_sensitive
  basic_salary?: string;
  gross_salary?: string;
  net_salary?: string;
  lop_amount?: string;
  status: 'draft' | 'finalized' | 'disbursed';
  generated_at: string;
}

export interface PayslipLine {
  id: number;
  category: 'earning' | 'deduction';
  component_code: string;
  name: string;
  amount: string;
  order: number;
  metadata?: Record<string, any>;
}

export interface PayslipSummary {
  id: number;
  payslip_number: string;
  status: 'issued' | 'revoked';
  issued_at: string;
  period_label: string;
  year: number;
  month: number;
  start_date: string;
  end_date: string;
  net_salary: string;
  employee_code: string;
  employee_name: string;
  verification_token?: string;
  gross_earnings?: string;
  total_deductions?: string;
  net_pay?: string;
}

export interface PayslipDetail {
  id: number;
  payslip_number: string;
  status: 'issued' | 'revoked';
  issued_at: string;
  period_label: string;
  verification_token?: string;
  integrity_hash?: string;
  net_pay_in_words?: string;
  organization: {
    name: string;
    legal_name?: string;
    address?: string | null;
    cin?: string | null;
    branch?: string | null;
  };
  employee: {
    id: number;
    code: string;
    name: string;
    email: string;
    department: string | null;
    designation: string | null;
    joining_date?: string | null;
    bank_name?: string | null;
    masked_bank_account?: string | null;
    bank_ifsc?: string | null;
    payment_mode?: string | null;
    masked_pan?: string | null;
    uan?: string | null;
    esic_number?: string | null;
  };
  period: {
    id: number;
    year: number;
    month: number;
    label: string;
    start_date: string;
    end_date: string;
  };
  attendance: {
    calendar_days?: number;
    working_days: number;
    present_days: string | number;
    half_days: number;
    leave_days: string | number;
    absent_days: number;
    effective_days: string | number;
    lop_days?: string | number;
  };
  financials: {
    basic_salary: string | null;
    gross_salary: string | null;
    deductions: string | null;
    net_salary: string | null;
    net_pay_in_words?: string | null;
  };
  lines: PayslipLine[];
}

export interface SettlementLine {
  id: number;
  category: 'earning' | 'deduction' | 'recovery';
  code: string;
  name: string;
  amount: string;
  calculation_basis?: string;
  source_reference?: string;
  order: number;
  metadata?: Record<string, any>;
}

export interface FinalSettlement {
  id: number;
  settlement_number: string;
  status: 'draft' | 'review' | 'approved' | 'finalized' | 'cancelled';
  exit_date: string;
  resignation_date?: string | null;
  settlement_date: string;
  total_earnings: string;
  total_deductions: string;
  total_recoveries: string;
  net_settlement_amount: string;
  currency: string;
  remarks?: string;
  cancellation_reason?: string;
  integrity_hash?: string;
  lines?: SettlementLine[];
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

// ─── P6.9A Tax Declarations & Investment Proof Types ─────────────────────────

export interface FinancialYear {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
  is_locked: boolean;
  created_at: string;
}

export interface TaxDeclarationCategory {
  id: number;
  code: string;
  name: string;
  description: string;
  max_limit: string | null;
  regime_applicability: 'both' | 'old' | 'new';
  is_active: boolean;
}

export interface InvestmentProof {
  id: number;
  declaration_item: number;
  proof_type: string;
  document_name: string;
  file_size: number;
  mime_type: string;
  status: 'submitted' | 'under_review' | 'verified' | 'rejected';
  rejection_reason?: string | null;
  reviewed_by_email?: string | null;
  reviewed_at?: string | null;
  submitted_at: string;
}

export interface InvestmentDeclaration {
  id: number;
  declaration: number;
  category: number;
  category_code: string;
  description: string;
  declared_amount: string;
  verified_amount: string;
  status: 'pending' | 'verified' | 'rejected';
  rejection_reason?: string | null;
  metadata?: Record<string, any>;
  proofs: InvestmentProof[];
  created_at: string;
  updated_at: string;
}

export interface TaxDeclarationSummary {
  id: number;
  employee: number;
  employee_code: string;
  employee_name: string;
  financial_year: number;
  financial_year_name: string;
  financial_year_start: string;
  financial_year_end: string;
  tax_regime: 'OLD' | 'NEW';
  status: 'draft' | 'submitted' | 'under_review' | 'verified' | 'rejected';
  total_declared_amount: string;
  total_verified_amount: string;
  items_count: number;
  submission_date?: string | null;
  verification_date?: string | null;
  created_at: string;
}

export interface TaxDeclarationDetail {
  id: number;
  employee: number;
  employee_code: string;
  employee_name: string;
  financial_year: number;
  financial_year_name: string;
  financial_year_start: string;
  financial_year_end: string;
  financial_year_locked: boolean;
  tax_regime: 'OLD' | 'NEW';
  status: 'draft' | 'submitted' | 'under_review' | 'verified' | 'rejected';
  total_declared_amount: string;
  total_verified_amount: string;
  submission_date?: string | null;
  verification_date?: string | null;
  verified_by_email?: string | null;
  rejection_reason?: string | null;
  notes?: string;
  snapshot_data?: Record<string, any>;
  items: InvestmentDeclaration[];
  created_at: string;
  updated_at: string;
}

export interface CreateTaxDeclarationPayload {
  financial_year_id?: number;
  financial_year_name?: string;
  tax_regime?: 'OLD' | 'NEW';
  notes?: string;
}

export interface UpdateTaxDeclarationPayload {
  tax_regime?: 'OLD' | 'NEW';
  notes?: string;
}

export interface CreateInvestmentItemPayload {
  category_code: string;
  description: string;
  declared_amount: string | number;
  metadata?: Record<string, any>;
}

export interface UpdateInvestmentItemPayload {
  description?: string;
  declared_amount?: string | number;
  metadata?: Record<string, any>;
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

  generatePeriod: async (periodId: number): Promise<{ detail: string; warning?: string }> => {
    const res = await fetch(`${BASE}/periods/${periodId}/generate/`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({}),
    });
    return handleResponse<{ detail: string; warning?: string }>(res);
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

  // Payslips
  getMyPayslips: async (): Promise<PayslipSummary[]> => {
    const res = await fetch(`${BASE}/payslips/my/`, { headers: getHeaders() });
    return handleResponse<PayslipSummary[]>(res);
  },

  getPayslipDetail: async (id: number): Promise<PayslipDetail> => {
    const res = await fetch(`${BASE}/payslips/${id}/`, { headers: getHeaders() });
    return handleResponse<PayslipDetail>(res);
  },

  getPayslips: async (periodId?: number, employeeId?: number): Promise<PayslipSummary[]> => {
    const params = new URLSearchParams();
    if (periodId) params.set('period', String(periodId));
    if (employeeId) params.set('employee', String(employeeId));
    const query = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${BASE}/payslips/${query}`, { headers: getHeaders() });
    return handleResponse<PayslipSummary[]>(res);
  },

  downloadPayslipPdf: async (id: number): Promise<{ blob: Blob; filename: string }> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    const res = await fetch(`${BASE}/payslips/${id}/pdf/`, {
      headers: {
        Authorization: `Token ${token}`,
      },
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw { response: res, errorData };
    }
    const disposition = res.headers.get('content-disposition');
    let filename = `Payslip_${id}.pdf`;
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename="?([^";]+)"?/);
      if (match && match[1]) filename = match[1];
    }
    const blob = await res.blob();
    return { blob, filename };
  },

  // FnF Final Settlements (Administrative)
  getFinalSettlements: async (params?: { employee?: number; status?: string }): Promise<FinalSettlement[]> => {
    const searchParams = new URLSearchParams();
    if (params?.employee) searchParams.set('employee', String(params.employee));
    if (params?.status) searchParams.set('status', params.status);
    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    const res = await fetch(`${BASE}/fnf/${query}`, { headers: getHeaders() });
    return handleResponse<FinalSettlement[]>(res);
  },

  getFinalSettlementDetail: async (id: number): Promise<FinalSettlement> => {
    const res = await fetch(`${BASE}/fnf/${id}/`, { headers: getHeaders() });
    return handleResponse<FinalSettlement>(res);
  },

  // FnF Employee Self-Service
  getMyFinalSettlements: async (): Promise<FinalSettlement[]> => {
    const res = await fetch(`${BASE}/fnf/my/`, { headers: getHeaders() });
    return handleResponse<FinalSettlement[]>(res);
  },

  getMyFinalSettlementDetail: async (id: number): Promise<FinalSettlement> => {
    const res = await fetch(`${BASE}/fnf/my/${id}/`, { headers: getHeaders() });
    return handleResponse<FinalSettlement>(res);
  },

  // ─── P6.9A Employee Tax Declarations ─────────────────────────────────────────

  getFinancialYears: async (): Promise<FinancialYear[]> => {
    const res = await fetch(`${BASE}/tax/financial-years/`, { headers: getHeaders() });
    return handleResponse<FinancialYear[]>(res);
  },

  getTaxCategories: async (): Promise<TaxDeclarationCategory[]> => {
    const res = await fetch(`${BASE}/tax/categories/`, { headers: getHeaders() });
    return handleResponse<TaxDeclarationCategory[]>(res);
  },

  getMyTaxDeclarations: async (financialYear?: number | string): Promise<TaxDeclarationSummary[]> => {
    const query = financialYear ? `?financial_year=${encodeURIComponent(String(financialYear))}` : '';
    const res = await fetch(`${BASE}/tax/declarations/my/${query}`, { headers: getHeaders() });
    return handleResponse<TaxDeclarationSummary[]>(res);
  },

  getTaxDeclarationDetail: async (id: number): Promise<TaxDeclarationDetail> => {
    const res = await fetch(`${BASE}/tax/declarations/${id}/`, { headers: getHeaders() });
    return handleResponse<TaxDeclarationDetail>(res);
  },

  createTaxDeclaration: async (payload: CreateTaxDeclarationPayload): Promise<TaxDeclarationDetail> => {
    const res = await fetch(`${BASE}/tax/declarations/`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse<TaxDeclarationDetail>(res);
  },

  updateTaxDeclaration: async (id: number, payload: UpdateTaxDeclarationPayload): Promise<TaxDeclarationDetail> => {
    const res = await fetch(`${BASE}/tax/declarations/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse<TaxDeclarationDetail>(res);
  },

  submitTaxDeclaration: async (id: number): Promise<TaxDeclarationDetail> => {
    const res = await fetch(`${BASE}/tax/declarations/${id}/submit/`, {
      method: 'POST',
      headers: getHeaders(),
    });
    return handleResponse<TaxDeclarationDetail>(res);
  },

  addInvestmentItem: async (declarationId: number, payload: CreateInvestmentItemPayload): Promise<InvestmentDeclaration> => {
    const res = await fetch(`${BASE}/tax/declarations/${declarationId}/items/`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse<InvestmentDeclaration>(res);
  },

  updateInvestmentItem: async (declarationId: number, itemId: number, payload: UpdateInvestmentItemPayload): Promise<InvestmentDeclaration> => {
    const res = await fetch(`${BASE}/tax/declarations/${declarationId}/items/${itemId}/`, {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse<InvestmentDeclaration>(res);
  },

  deleteInvestmentItem: async (declarationId: number, itemId: number): Promise<void> => {
    const res = await fetch(`${BASE}/tax/declarations/${declarationId}/items/${itemId}/delete/`, {
      method: 'DELETE',
      headers: getHeaders(),
    });
    return handleResponse<void>(res);
  },

  uploadInvestmentProof: async (declarationId: number, itemId: number, formData: FormData): Promise<InvestmentProof> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    const res = await fetch(`${BASE}/tax/declarations/${declarationId}/items/${itemId}/proofs/`, {
      method: 'POST',
      headers: {
        Authorization: `Token ${token}`,
      },
      body: formData,
    });
    return handleResponse<InvestmentProof>(res);
  },

  downloadInvestmentProof: async (declarationId: number, itemId: number, proofId: number): Promise<{ blob: Blob; filename: string }> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    const res = await fetch(`${BASE}/tax/declarations/${declarationId}/items/${itemId}/proofs/${proofId}/download/`, {
      headers: {
        Authorization: `Token ${token}`,
      },
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw { response: res, errorData };
    }
    const disposition = res.headers.get('content-disposition');
    let filename = `Proof_${proofId}.pdf`;
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename="?([^";]+)"?/);
      if (match && match[1]) filename = match[1];
    }
    const blob = await res.blob();
    return { blob, filename };
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
    if (data?.message) return data.message;
    if (typeof data === 'string') return data;
    if (data && typeof data === 'object') {
      const msgs = Object.values(data)
        .map((v) => {
          if (Array.isArray(v)) return v.join(' ');
          if (typeof v === 'string') return v;
          return '';
        })
        .filter(Boolean)
        .join(' ');
      if (msgs) return msgs;
    }
  }
  if (err instanceof Error) {
    return err.message;
  }
  return 'An unexpected error occurred.';
};

