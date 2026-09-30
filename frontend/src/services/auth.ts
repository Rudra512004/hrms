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
  hrmsId?: string; // Employee code — only set for users with an employee profile
  email: string;
  firstName: string;
  lastName: string;
  status?: string;
  isSuperuser?: boolean;
  hasEmployeeProfile: boolean; // True only if linked to an Employee record
  canCreateOrganization?: boolean;
}

export interface AuthSession {
  user: User;
  roles: string[];
  permissions: string[];
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

  getCurrentUser: async (): Promise<AuthSession | null> => {
    const token = localStorage.getItem('auth_token');
    if (!token) return null;

    try {
      const response = await fetch('/api/v1/authorization/me/', {
        headers: {
          'Authorization': `Token ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        return {
          user: {
            id: data.user.id.toString(),
            email: data.user.email,
            firstName: data.user.first_name,
            lastName: data.user.last_name,
            hrmsId: data.user.employee_code,
            status: data.user.status,
            isSuperuser: Boolean(data.user.is_superuser),
            hasEmployeeProfile: Boolean(data.user.has_employee_profile),
            canCreateOrganization: Boolean(data.user.can_create_organization),
          },
          roles: data.roles || [],
          permissions: data.permissions || [],
        };
      } else {
        // Token might be invalid
        localStorage.removeItem('auth_token');
        return null;
      }
    } catch (e) {
      console.error('Failed to fetch user', e);
      return null;
    }
  },

  registerTenantOwner: async (data: { email: string; first_name: string; last_name: string }): Promise<string> => {
    const response = await fetch('/api/v1/auth/register/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const firstError = Object.values(payload)[0];
      throw new Error(Array.isArray(firstError) ? firstError[0] : 'Unable to create your account.');
    }
    return payload.detail;
  },

  updateAccountProfile: async (data: { first_name: string; last_name: string }): Promise<void> => {
    const token = localStorage.getItem('auth_token');
    const response = await fetch('/api/v1/auth/me/', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Token ${token}` } : {}),
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const firstError = Object.values(errorData)[0];
      throw new Error(Array.isArray(firstError) ? firstError[0] : 'Unable to save account profile.');
    }
  },

  /**
   * Request password reset link.
   */
  requestPasswordReset: async (email: string): Promise<string> => {
    const response = await fetch('/api/v1/auth/password-reset/request/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to request password reset');
    }

    const data = await response.json();
    return data.detail;
  },

  /**
   * Confirm password reset with token.
   */
  confirmPasswordReset: async (uid: string, token: string, new_password: string, confirm_password: string): Promise<string> => {
    const response = await fetch('/api/v1/auth/password-reset/confirm/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uid, token, new_password, confirm_password })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      if (errorData.non_field_errors) {
         throw new Error(errorData.non_field_errors[0]);
      }
      if (errorData.detail) {
         throw new Error(errorData.detail);
      }
      const firstErrorKey = Object.keys(errorData)[0];
      if (firstErrorKey && Array.isArray(errorData[firstErrorKey])) {
         throw new Error(errorData[firstErrorKey][0]);
      }
      throw new Error('Failed to reset password');
    }

    const data = await response.json();
    return data.detail;
  },

  /**
   * Activate account with token and password.
   */
  activateAccount: async (uid: string, token: string, password: string): Promise<string> => {
    const response = await fetch('/api/v1/auth/activate/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uid, token, password })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      if (errorData.non_field_errors) {
        throw new Error(errorData.non_field_errors[0]);
      }
      if (errorData.detail) {
        throw new Error(errorData.detail);
      }
      const firstErrorKey = Object.keys(errorData)[0];
      if (firstErrorKey && Array.isArray(errorData[firstErrorKey])) {
        throw new Error(errorData[firstErrorKey][0]);
      }
      throw new Error('Failed to activate account');
    }

    const data = await response.json();
    return data.detail || 'Account successfully activated.';
  },

  /**
   * Change password for authenticated user.
   */
  changePassword: async (old_password: string, new_password: string, confirm_password: string): Promise<string> => {
    const token = localStorage.getItem('auth_token');
    const response = await fetch('/api/v1/auth/password-change/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Token ${token}` } : {})
      },
      body: JSON.stringify({ old_password, new_password, confirm_password })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      if (errorData.non_field_errors) {
        throw new Error(errorData.non_field_errors[0]);
      }
      if (errorData.detail) {
        throw new Error(errorData.detail);
      }
      const firstErrorKey = Object.keys(errorData)[0];
      if (firstErrorKey && Array.isArray(errorData[firstErrorKey])) {
        throw new Error(errorData[firstErrorKey][0]);
      }
      throw new Error('Failed to change password');
    }

    const data = await response.json();
    if (data.token) {
      localStorage.setItem('auth_token', data.token);
    }
    return data.detail || 'Password changed successfully.';
  }
};
