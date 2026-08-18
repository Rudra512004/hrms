export interface EmployeeProfile {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  status: string;
  employee_code: string;
  phone_number: string;
  address: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
}

export const employeeService = {
  getProfile: async (): Promise<EmployeeProfile> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch('/api/v1/employees/me/', {
      headers: {
        'Authorization': `Token ${token}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch profile');
    }
    
    return await response.json();
  },
  
  updateProfile: async (data: Partial<EmployeeProfile>): Promise<EmployeeProfile> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch('/api/v1/employees/me/', {
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
  }
};
