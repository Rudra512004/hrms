import { type EmployeeProfile } from './employee';

export interface ProvisionEmployeeData {
  email: string;
  personal_email: string;
  first_name: string;
  last_name: string;
  employee_code: string;
}

export const employeeManagementService = {
  listEmployees: async (): Promise<EmployeeProfile[]> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch('/api/v1/employees/management/', {
      headers: {
        'Authorization': `Token ${token}`,
        'Accept': 'application/json'
      }
    });

    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        throw new Error(`Authorization failed: ${response.status}`);
      }
      throw new Error('Failed to fetch employees');
    }

    return await response.json();
  },

  getEmployee: async (id: number): Promise<EmployeeProfile> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch(`/api/v1/employees/management/${id}/`, {
      headers: {
        'Authorization': `Token ${token}`,
        'Accept': 'application/json'
      }
    });

    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        throw new Error(`Authorization failed: ${response.status}`);
      }
      throw new Error('Failed to fetch employee details');
    }

    return await response.json();
  },

  createEmployee: async (data: ProvisionEmployeeData): Promise<{ detail: string, employee: EmployeeProfile, activation_info?: any, onboarding_email_status?: string }> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch('/api/v1/employees/management/', {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }

    return await response.json();
  },

  updateEmployee: async (id: number, data: Partial<EmployeeProfile>): Promise<EmployeeProfile> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch(`/api/v1/employees/management/${id}/`, {
      method: 'PATCH',
      headers: {
        'Authorization': `Token ${token}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }

    return await response.json();
  },

  activateEmployee: async (id: number): Promise<{ detail: string }> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch(`/api/v1/employees/management/${id}/activate/`, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}`,
        'Accept': 'application/json'
      }
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }

    return await response.json();
  },

  deactivateEmployee: async (id: number): Promise<{ detail: string }> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch(`/api/v1/employees/management/${id}/deactivate/`, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}`,
        'Accept': 'application/json'
      }
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }

    return await response.json();
  }
};
