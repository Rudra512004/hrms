export interface Role {
  id: number;
  organization: number;
  name: string;
  slug: string;
  description: string;
  badge: string | null;
  users_count: number;
  permissions_count: number;
  effective_permissions_count?: number;
  can_delete: boolean;
  is_system: boolean;
  is_active: boolean;
  permission_ids: number[];
  created_at?: string;
  updated_at?: string;
}

export interface Permission {
  id: number;
  name: string;
  codename: string;
  resource: string;
  action: string;
  description: string;
  is_active: boolean;
  column?: number;
  category?: string;
}

export interface PermissionAction {
  id: number;
  codename: string;
  label: string;
  name: string;
  description: string;
  column: number;
  category: string;
  is_active?: boolean;
  is_preserved_enterprise?: boolean;
}

export interface PermissionCategoryGroup {
  category: string;
  actions: PermissionAction[];
}

export interface PermissionMatrixResponse {
  total_visible_count: number;
  columns: {
    [columnKey: string]: PermissionCategoryGroup[];
  };
}

export interface RolePermissionsUpdateResponse {
  role_id: number;
  role_name: string;
  permissions_count: number;
  effective_permissions_count: number;
  updated_at: string;
}

export interface UserRole {
  id: number;
  user: number;
  user_email?: string;
  role: number;
  role_name: string;
  role_slug?: string;
  scope: string;
  branch: number | null;
  team: number | null;
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
}

export interface RolePermission {
  id: number;
  role: number;
  permission: number;
  permission_codename: string;
  created_at: string;
}

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return {
    'Accept': 'application/json',
    ...(token ? { 'Authorization': `Token ${token}` } : {})
  };
};

export const authorizationManagementService = {
  listRoles: async (): Promise<Role[]> => {
    const response = await fetch('/api/v1/authorization/roles/', {
      headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Failed to fetch roles');
    return await response.json();
  },

  getRole: async (roleId: number): Promise<Role> => {
    const response = await fetch(`/api/v1/authorization/roles/${roleId}/`, {
      headers: getAuthHeaders()
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    return await response.json();
  },

  createRole: async (data: { name: string; description?: string }): Promise<Role> => {
    const response = await fetch('/api/v1/authorization/roles/', {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
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

  updateRole: async (roleId: number, data: Partial<Role>): Promise<Role> => {
    const response = await fetch(`/api/v1/authorization/roles/${roleId}/`, {
      method: 'PATCH',
      headers: {
        ...getAuthHeaders(),
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

  deleteRole: async (roleId: number): Promise<void> => {
    const response = await fetch(`/api/v1/authorization/roles/${roleId}/`, {
      method: 'DELETE',
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
  },

  listPermissions: async (): Promise<Permission[]> => {
    const response = await fetch('/api/v1/authorization/permissions/?format=flat', {
      headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Failed to fetch permissions');
    return await response.json();
  },

  getPermissionMatrix: async (): Promise<PermissionMatrixResponse> => {
    const response = await fetch('/api/v1/authorization/permissions/', {
      headers: getAuthHeaders()
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    return await response.json();
  },

  updateRolePermissions: async (roleId: number, permissionIds: number[]): Promise<RolePermissionsUpdateResponse> => {
    const response = await fetch(`/api/v1/authorization/roles/${roleId}/permissions/`, {
      method: 'PUT',
      headers: {
        ...getAuthHeaders(),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ permission_ids: permissionIds })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    return await response.json();
  },

  listUserRoles: async (userId: number): Promise<UserRole[]> => {
    const response = await fetch(`/api/v1/authorization/user-roles/?user=${userId}`, {
      headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Failed to fetch user roles');
    return await response.json();
  },

  assignRole: async (userId: number, roleId: number, scope: string = 'organization', branch: number | null = null, team: number | null = null): Promise<UserRole> => {
    const response = await fetch('/api/v1/authorization/user-roles/', {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ user: userId, role: roleId, scope, branch, team })
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    return await response.json();
  },

  revokeRole: async (userRoleId: number): Promise<{ detail: string }> => {
    const response = await fetch(`/api/v1/authorization/user-roles/${userRoleId}/revoke/`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    return await response.json();
  },

  listUserPermissions: async (userId: number): Promise<UserPermissionGrant[]> => {
    const response = await fetch(`/api/v1/authorization/user-permissions/?user=${userId}`, {
      headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Failed to fetch user permissions');
    return await response.json();
  },

  grantPermission: async (userId: number, permissionId: number): Promise<UserPermissionGrant> => {
    const response = await fetch('/api/v1/authorization/user-permissions/', {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
        'Content-Type': 'application/json'
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
    const response = await fetch(`/api/v1/authorization/user-permissions/${userPermissionGrantId}/revoke/`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    return await response.json();
  },

  getMyPermissions: async (): Promise<string[]> => {
    const response = await fetch('/api/v1/authorization/permissions/my_permissions/', {
      headers: getAuthHeaders()
    });
    
    if (!response.ok) throw new Error('Failed to fetch effective permissions');
    return await response.json();
  },

  listRolePermissions: async (roleId: number): Promise<RolePermission[]> => {
    const response = await fetch(`/api/v1/authorization/role-permissions/?role=${roleId}`, {
      headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Failed to fetch role permissions');
    return await response.json();
  },

  assignPermissionToRole: async (roleId: number, permissionId: number): Promise<RolePermission> => {
    const response = await fetch('/api/v1/authorization/role-permissions/', {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ role: roleId, permission: permissionId })
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    return await response.json();
  },

  revokePermissionFromRole: async (rolePermissionId: number): Promise<{ detail: string }> => {
    const response = await fetch(`/api/v1/authorization/role-permissions/${rolePermissionId}/revoke/`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    return await response.json();
  }
};
