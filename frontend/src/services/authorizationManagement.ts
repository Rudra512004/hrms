export interface Role {
  id: number;
  organization: number;
  name: string;
  description: string;
  is_active: boolean;
}

export interface Permission {
  id: number;
  name: string;
  codename: string;
  resource: string;
  action: string;
  description: string;
  is_active: boolean;
}

export interface UserRole {
  id: number;
  user: number;
  role: number;
  role_name: string;
  assigned_by: number | null;
  assigned_at: string;
  expires_at: string | null;
  is_revoked: boolean;
  revoked_at: string | null;
}

export interface UserPermissionGrant {
  id: number;
  user: number;
  permission: number;
  permission_codename: string;
  granted_by: number | null;
  granted_at: string;
  expires_at: string | null;
  is_revoked: boolean;
  revoked_at: string | null;
}

export const authorizationManagementService = {
  listRoles: async (): Promise<Role[]> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch('/api/v1/authorization/roles/', {
      headers: {
        'Authorization': `Token ${token}`,
        'Accept': 'application/json'
      }
    });
    if (!response.ok) throw new Error('Failed to fetch roles');
    return await response.json();
  },

  listPermissions: async (): Promise<Permission[]> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch('/api/v1/authorization/permissions/', {
      headers: {
        'Authorization': `Token ${token}`,
        'Accept': 'application/json'
      }
    });
    if (!response.ok) throw new Error('Failed to fetch permissions');
    return await response.json();
  },

  listUserRoles: async (userId: number): Promise<UserRole[]> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch(`/api/v1/authorization/user-roles/?user=${userId}`, {
      headers: {
        'Authorization': `Token ${token}`,
        'Accept': 'application/json'
      }
    });
    if (!response.ok) throw new Error('Failed to fetch user roles');
    return await response.json();
  },

  assignRole: async (userId: number, roleId: number): Promise<UserRole> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch('/api/v1/authorization/user-roles/', {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({ user: userId, role: roleId })
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    return await response.json();
  },

  revokeRole: async (userRoleId: number): Promise<{ detail: string }> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch(`/api/v1/authorization/user-roles/${userRoleId}/revoke/`, {
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

  listUserPermissions: async (userId: number): Promise<UserPermissionGrant[]> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch(`/api/v1/authorization/user-permissions/?user=${userId}`, {
      headers: {
        'Authorization': `Token ${token}`,
        'Accept': 'application/json'
      }
    });
    if (!response.ok) throw new Error('Failed to fetch user permissions');
    return await response.json();
  },

  grantPermission: async (userId: number, permissionId: number): Promise<UserPermissionGrant> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch('/api/v1/authorization/user-permissions/', {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({ user: userId, permission: permissionId })
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    return await response.json();
  },

  revokePermission: async (userPermissionGrantId: number): Promise<{ detail: string }> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch(`/api/v1/authorization/user-permissions/${userPermissionGrantId}/revoke/`, {
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

  getMyPermissions: async (): Promise<string[]> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    const response = await fetch('/api/v1/authorization/permissions/my_permissions/', {
      headers: {
        'Authorization': `Token ${token}`,
        'Accept': 'application/json'
      }
    });
    
    if (!response.ok) throw new Error('Failed to fetch effective permissions');
    return await response.json();
  }
};
