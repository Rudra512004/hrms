export interface OfficeNetwork {
  id: number;
  organization: number;
  name: string;
  network: string; // CIDR format, e.g., "203.0.113.0/24"
  description: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export const officeNetworkService = {
  getAll: async (): Promise<OfficeNetwork[]> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch('/api/v1/organization/office-networks/', {
      headers: {
        'Authorization': `Token ${token}`
      }
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    
    return await response.json();
  },

  create: async (data: Partial<OfficeNetwork>): Promise<OfficeNetwork> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch('/api/v1/organization/office-networks/', {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    
    return await response.json();
  },

  update: async (id: number, data: Partial<OfficeNetwork>): Promise<OfficeNetwork> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch(`/api/v1/organization/office-networks/${id}/`, {
      method: 'PATCH',
      headers: {
        'Authorization': `Token ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    
    return await response.json();
  },

  delete: async (id: number): Promise<void> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch(`/api/v1/organization/office-networks/${id}/`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Token ${token}`
      }
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
  }
};
