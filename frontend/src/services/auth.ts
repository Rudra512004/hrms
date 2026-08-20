/**
 * Pending DEV1 API Contract:
 * Do NOT invent endpoint URLs.
 * Do NOT call nonexistent APIs.
 * Do NOT fake successful authentication.
 * 
 * This file serves as the architectural abstraction for authentication.
 * It will be implemented once the official API documentation is provided.
 */

export interface User {
  id: string;
  hrmsId?: string; // Assigned later in the identity lifecycle
  email: string;
  firstName: string;
  lastName: string;
  status?: string;
  isStaff?: boolean;
  isSuperuser?: boolean;
}

export const authService = {
  /**
   * Log in using company email and password.
   */
  login: async (email: string, password: string): Promise<void> => {
    const response = await fetch('/api/v1/auth/login/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.non_field_errors?.[0] || 'Login failed');
    }
    
    const data = await response.json();
    if (data.token) {
      localStorage.setItem('auth_token', data.token);
    }
  },

  /**
   * Activate an account and set a password.
   */
  activate: async (uid: string, token: string, password: string): Promise<void> => {
    const response = await fetch('/api/v1/auth/activate/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uid, token, password })
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.non_field_errors?.[0] || 'Activation failed');
    }
  },

  /**
   * Log out the current user.
   */
  logout: async (): Promise<void> => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      await fetch('/api/v1/auth/logout/', {
        method: 'POST',
        headers: { 
          'Authorization': `Token ${token}` 
        }
      }).catch(console.error); // Ignore errors on logout
      localStorage.removeItem('auth_token');
    }
  },

  /**
   * Fetch the currently authenticated user session.
   */
  getCurrentUser: async (): Promise<User | null> => {
    const token = localStorage.getItem('auth_token');
    if (!token) return null;
    
    try {
      const response = await fetch('/api/v1/auth/me/', {
        headers: {
          'Authorization': `Token ${token}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        return {
          id: data.id.toString(),
          email: data.email,
          firstName: data.first_name,
          lastName: data.last_name,
          hrmsId: data.employee_code,
          status: data.status,
          isStaff: data.is_staff,
          isSuperuser: data.is_superuser,
        } as User & { status?: string; isStaff?: boolean; isSuperuser?: boolean };
      } else {
        // Token might be invalid
        localStorage.removeItem('auth_token');
        return null;
      }
    } catch (e) {
      console.error('Failed to fetch user', e);
      return null;
    }
  }
};
