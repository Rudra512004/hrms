export interface Organization {
  id: number;
  name: string;
  description: string;
  is_active: boolean;
}

export interface Department {
  id: number;
  organization: number;
  organization_name?: string; // Optional for display
  name: string;
  description: string;
  is_active: boolean;
}

export interface Designation {
  id: number;
  organization: number;
  organization_name?: string; // Optional for display
  name: string;
  description: string;
  is_active: boolean;
}

const getHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Token ${token}` } : {})
  };
};

const handleResponse = async (response: Response) => {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const error = new Error('API Request Failed') as any;
    error.response = response;
    error.errorData = errorData;
    throw error;
  }
  if (response.status === 204) return null;
  return response.json();
};

export const organizationService = {
  // --- ORGANIZATIONS ---
  listOrganizations: async (): Promise<Organization[]> => {
    const response = await fetch('/api/v1/organization/organizations/', {
      headers: getHeaders()
    });
    return handleResponse(response);
  },

  createOrganization: async (data: Partial<Organization>): Promise<Organization> => {
    const response = await fetch('/api/v1/organization/organizations/', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data)
    });
    return handleResponse(response);
  },

  updateOrganization: async (id: number, data: Partial<Organization>): Promise<Organization> => {
    const response = await fetch(`/api/v1/organization/organizations/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify(data)
    });
    return handleResponse(response);
  },

  deleteOrganization: async (id: number): Promise<void> => {
    const response = await fetch(`/api/v1/organization/organizations/${id}/`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    return handleResponse(response);
  },

  // --- DEPARTMENTS ---
  listDepartments: async (organizationId?: number): Promise<Department[]> => {
    const url = organizationId 
      ? `/api/v1/organization/departments/?organization=${organizationId}`
      : '/api/v1/organization/departments/';
    const response = await fetch(url, {
      headers: getHeaders()
    });
    return handleResponse(response);
  },

  createDepartment: async (data: Partial<Department>): Promise<Department> => {
    const response = await fetch('/api/v1/organization/departments/', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data)
    });
    return handleResponse(response);
  },

  updateDepartment: async (id: number, data: Partial<Department>): Promise<Department> => {
    const response = await fetch(`/api/v1/organization/departments/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify(data)
    });
    return handleResponse(response);
  },

  deleteDepartment: async (id: number): Promise<void> => {
    const response = await fetch(`/api/v1/organization/departments/${id}/`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    return handleResponse(response);
  },

  // --- DESIGNATIONS ---
  listDesignations: async (organizationId?: number): Promise<Designation[]> => {
    const url = organizationId 
      ? `/api/v1/organization/designations/?organization=${organizationId}`
      : '/api/v1/organization/designations/';
    const response = await fetch(url, {
      headers: getHeaders()
    });
    return handleResponse(response);
  },

  createDesignation: async (data: Partial<Designation>): Promise<Designation> => {
    const response = await fetch('/api/v1/organization/designations/', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data)
    });
    return handleResponse(response);
  },

  updateDesignation: async (id: number, data: Partial<Designation>): Promise<Designation> => {
    const response = await fetch(`/api/v1/organization/designations/${id}/`, {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify(data)
    });
    return handleResponse(response);
  },

  deleteDesignation: async (id: number): Promise<void> => {
    const response = await fetch(`/api/v1/organization/designations/${id}/`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    return handleResponse(response);
  }
};
