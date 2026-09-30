import { type Branch, branchService } from './branch';
import { ApiError } from './employeeManagement';

export type { Branch };

export interface Organization {
  id: number;
  name: string;
  description?: string;
  is_active?: boolean;
  status?: string;
  created_at?: string;
  updated_at?: string;
}

/**
 * The initial, atomic organisation provisioning payload.  This deliberately
 * mirrors the existing /organization/setup/ API instead of changing any of
 * the established CRUD contracts used by the administration screens.
 */
export interface OrganizationSetupPayload {
  name: string;
  status: 'active' | 'inactive';
  branches: Array<{
    name: string;
    address?: string;
    latitude?: number | null;
    longitude?: number | null;
    radius?: number;
    network?: {
      name: string;
      network: string;
      description?: string;
      is_active?: boolean;
    };
  }>;
  working_calendar?: { work_days: string };
  attendance_policy?: {
    is_office_gps_enabled?: boolean;
    is_office_ip_enabled?: boolean;
    is_wfh_enabled?: boolean;
    wfh_bypasses_office_restrictions?: boolean;
  };
}

export interface OrganizationReadinessCheck {
  key: string;
  label: string;
  state: 'ready' | 'action_required' | 'recommended';
  detail: string;
  path: string;
  required: boolean;
}

export interface OrganizationReadiness {
  organization_id: number;
  organization_name: string;
  score: number;
  checks: OrganizationReadinessCheck[];
}

export interface Department {
  id: number;
  branch: number;
  branch_name?: string;
  organization?: number;
  organization_name?: string;
  name: string;
  description: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface Team {
  id: number;
  department: number;
  department_name?: string;
  name: string;
  description: string;
  is_active: boolean;
  manager?: number | null;
  created_at?: string;
  updated_at?: string;
}

export interface Designation {
  id: number;
  organization: number;
  organization_name?: string;
  name: string;
  description: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

const getHeaders = (includeContentType = true): HeadersInit => {
  const token = localStorage.getItem('auth_token');
  const headers: Record<string, string> = {
    'Accept': 'application/json'
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

export const organizationService = {
  // --- GUIDED ORGANIZATION PROVISIONING ---
  createOrganizationSetup: async (data: OrganizationSetupPayload): Promise<Organization> => {
    const response = await fetch('/api/v1/organization/setup/', {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(data),
    });
    return handleResponse<Organization>(response);
  },

  createTenantOrganizationSetup: async (data: OrganizationSetupPayload): Promise<Organization> => {
    const response = await fetch('/api/v1/organization/self-setup/', {
      method: 'POST', headers: getHeaders(true), body: JSON.stringify(data),
    });
    return handleResponse<Organization>(response);
  },

  getOrganizationReadiness: async (id: number): Promise<OrganizationReadiness> => {
    const response = await fetch(`/api/v1/organization/organizations/${id}/readiness/`, {
      headers: getHeaders(false),
    });
    return handleResponse<OrganizationReadiness>(response);
  },

  // --- ORGANIZATIONS ---
  listOrganizations: async (): Promise<Organization[]> => {
    const response = await fetch('/api/v1/organization/organizations/', {
      headers: getHeaders(false)
    });
    return handleResponse<Organization[]>(response);
  },

  createOrganization: async (data: Partial<Organization>): Promise<Organization> => {
    const response = await fetch('/api/v1/organization/organizations/', {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(data)
    });
    return handleResponse<Organization>(response);
  },

  updateOrganization: async (id: number, data: Partial<Organization>): Promise<Organization> => {
    const response = await fetch(`/api/v1/organization/organizations/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(true),
      body: JSON.stringify(data)
    });
    return handleResponse<Organization>(response);
  },

  deleteOrganization: async (id: number): Promise<void> => {
    const response = await fetch(`/api/v1/organization/organizations/${id}/`, {
      method: 'DELETE',
      headers: getHeaders(false)
    });
    return handleResponse<void>(response);
  },

  // --- BRANCHES ---
  listBranches: async (
    organizationId?: number,
    options?: { signal?: AbortSignal }
  ): Promise<Branch[]> => {
    const url = organizationId
      ? `/api/v1/organization/branches/?organization=${organizationId}`
      : '/api/v1/organization/branches/';
    const response = await fetch(url, {
      headers: getHeaders(false),
      signal: options?.signal,
    });
    return handleResponse<Branch[]>(response);
  },

  // --- DEPARTMENTS ---
  listDepartments: async (
    branchId?: number,
    options?: { signal?: AbortSignal }
  ): Promise<Department[]> => {
    const url = branchId
      ? `/api/v1/organization/departments/?branch=${branchId}`
      : '/api/v1/organization/departments/';
    const response = await fetch(url, {
      headers: getHeaders(false),
      signal: options?.signal,
    });
    return handleResponse<Department[]>(response);
  },

  createDepartment: async (data: Partial<Department>): Promise<Department> => {
    const response = await fetch('/api/v1/organization/departments/', {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(data)
    });
    return handleResponse<Department>(response);
  },

  updateDepartment: async (id: number, data: Partial<Department>): Promise<Department> => {
    const response = await fetch(`/api/v1/organization/departments/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(true),
      body: JSON.stringify(data)
    });
    return handleResponse<Department>(response);
  },

  deleteDepartment: async (id: number): Promise<void> => {
    const response = await fetch(`/api/v1/organization/departments/${id}/`, {
      method: 'DELETE',
      headers: getHeaders(false)
    });
    return handleResponse<void>(response);
  },

  // --- TEAMS ---
  listTeams: async (
    departmentId?: number,
    options?: { signal?: AbortSignal }
  ): Promise<Team[]> => {
    const url = departmentId
      ? `/api/v1/organization/teams/?department=${departmentId}`
      : '/api/v1/organization/teams/';
    const response = await fetch(url, {
      headers: getHeaders(false),
      signal: options?.signal,
    });
    return handleResponse<Team[]>(response);
  },

  createTeam: async (data: Partial<Team>): Promise<Team> => {
    const response = await fetch('/api/v1/organization/teams/', {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(data)
    });
    return handleResponse<Team>(response);
  },

  updateTeam: async (id: number, data: Partial<Team>): Promise<Team> => {
    const response = await fetch(`/api/v1/organization/teams/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(true),
      body: JSON.stringify(data)
    });
    return handleResponse<Team>(response);
  },

  deleteTeam: async (id: number): Promise<void> => {
    const response = await fetch(`/api/v1/organization/teams/${id}/`, {
      method: 'DELETE',
      headers: getHeaders(false)
    });
    return handleResponse<void>(response);
  },

  // --- DESIGNATIONS ---
  listDesignations: async (
    organizationId?: number,
    options?: { signal?: AbortSignal }
  ): Promise<Designation[]> => {
    const url = organizationId 
      ? `/api/v1/organization/designations/?organization=${organizationId}`
      : '/api/v1/organization/designations/';
    const response = await fetch(url, {
      headers: getHeaders(false),
      signal: options?.signal,
    });
    return handleResponse<Designation[]>(response);
  },

  createDesignation: async (data: Partial<Designation>): Promise<Designation> => {
    const response = await fetch('/api/v1/organization/designations/', {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(data)
    });
    return handleResponse<Designation>(response);
  },

  updateDesignation: async (id: number, data: Partial<Designation>): Promise<Designation> => {
    const response = await fetch(`/api/v1/organization/designations/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(true),
      body: JSON.stringify(data)
    });
    return handleResponse<Designation>(response);
  },

  deleteDesignation: async (id: number): Promise<void> => {
    const response = await fetch(`/api/v1/organization/designations/${id}/`, {
      method: 'DELETE',
      headers: getHeaders(false)
    });
    return handleResponse<void>(response);
  }
};

export { branchService };
