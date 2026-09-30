const BASE = '/api/v1/payroll';

const headers = () => ({
  Authorization: `Token ${localStorage.getItem('auth_token') || ''}`,
  'Content-Type': 'application/json',
});

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...options, headers: { ...headers(), ...options?.headers } });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || Object.values(data).flat().join(' ') || 'Request failed.');
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export interface SalaryComponent {
  id: number;
  organization: number;
  organization_name: string;
  name: string;
  code: string;
  kind: 'earning' | 'deduction';
  is_taxable: boolean;
  is_active: boolean;
}

export interface SalaryStructureLine {
  id: number;
  component: number;
  component_name: string;
  component_code: string;
  component_kind: 'earning' | 'deduction';
  amount: string;
}

export interface SalaryStructure {
  id: number;
  organization: number;
  organization_name: string;
  name: string;
  is_active: boolean;
  components: SalaryStructureLine[];
  monthly_earnings: string;
  monthly_deductions: string;
}

export const salaryConfigurationService = {
  getComponents: () => request<SalaryComponent[]>(`${BASE}/salary-components/`),
  createComponent: (data: Pick<SalaryComponent, 'name' | 'code' | 'kind' | 'is_taxable' | 'is_active'>) =>
    request<SalaryComponent>(`${BASE}/salary-components/`, { method: 'POST', body: JSON.stringify(data) }),
  updateComponent: (id: number, data: Partial<SalaryComponent>) =>
    request<SalaryComponent>(`${BASE}/salary-components/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
  getStructures: () => request<SalaryStructure[]>(`${BASE}/salary-structures/`),
  createStructure: (data: Pick<SalaryStructure, 'name' | 'is_active'>) =>
    request<SalaryStructure>(`${BASE}/salary-structures/`, { method: 'POST', body: JSON.stringify(data) }),
  setStructureComponent: (structureId: number, component: number, amount: string) =>
    request<SalaryStructureLine>(`${BASE}/salary-structures/${structureId}/components/`, {
      method: 'POST', body: JSON.stringify({ component, amount }),
    }),
  removeStructureComponent: (structureId: number, componentId: number) =>
    request<void>(`${BASE}/salary-structures/${structureId}/components/${componentId}/`, { method: 'DELETE' }),
};
