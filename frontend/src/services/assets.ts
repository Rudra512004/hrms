// Assets API service — mirrors backend apps/assets/ API contract
// Base URL: /api/v1/assets/

export interface AssetCategory {
  id: number;
  organization: number;
  name: string;
  code: string;
  description: string;
  is_active: boolean;
  asset_count: number;
  created_at: string;
  updated_at: string;
}

export interface CurrentAssignment {
  id: number;
  employee_id: number;
  employee_code: string;
  employee_name: string;
  allocated_at: string;
  expected_return_date: string | null;
  condition_at_allocation: string;
}

export interface AssetAssignment {
  id: number;
  asset: number;
  asset_tag: string;
  asset_name: string;
  category_name: string;
  employee: number;
  employee_code: string;
  employee_name: string;
  allocated_at: string;
  expected_return_date: string | null;
  returned_at: string | null;
  condition_at_allocation: string;
  condition_at_return: string;
  allocation_notes: string;
  return_notes: string;
  assigned_by: number | null;
  assigned_by_email: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Asset {
  id: number;
  asset_tag: string;
  name: string;
  category: number;
  category_name: string;
  category_code: string;
  branch: number | null;
  branch_name: string | null;
  serial_number: string;
  model_number: string;
  status: 'available' | 'assigned' | 'under_maintenance' | 'retired' | 'lost';
  status_display: string;
  purchase_date: string | null;
  purchase_cost: string | null;
  warranty_expiry: string | null;
  notes: string;
  current_assignment: CurrentAssignment | null;
  assignment_history?: AssetAssignment[];
  created_at: string;
  updated_at: string;
}

export interface CreateAssetPayload {
  asset_tag: string;
  name: string;
  category: number;
  branch?: number | null;
  serial_number?: string;
  model_number?: string;
  purchase_date?: string | null;
  purchase_cost?: string | null;
  warranty_expiry?: string | null;
  notes?: string;
}

export interface AssignAssetPayload {
  employee: number;
  expected_return_date?: string | null;
  condition_at_allocation?: string;
  allocation_notes?: string;
}

export interface ReturnAssetPayload {
  condition_at_return?: string;
  return_notes?: string;
  return_date?: string;
  next_status?: 'available' | 'under_maintenance' | 'retired';
}

const getAuthHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('auth_token');
  if (!token) throw new Error('No authentication token');
  return {
    Authorization: `Token ${token}`,
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };
};

const handleResponse = async <T>(res: Response): Promise<T> => {
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw { status: res.status, data: errorData };
  }
  if (res.status === 204) return null as unknown as T;
  return (await res.json()) as T;
};

export const assetService = {
  getCategories: async (): Promise<AssetCategory[]> => {
    const res = await fetch('/api/v1/assets/categories/', { headers: getAuthHeaders() });
    const data = await handleResponse<any>(res);
    return Array.isArray(data) ? data : data.results || [];
  },

  createCategory: async (payload: { name: string; code: string; description?: string }): Promise<AssetCategory> => {
    const res = await fetch('/api/v1/assets/categories/', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return await handleResponse<AssetCategory>(res);
  },

  getAssets: async (params?: {
    category?: number;
    status?: string;
    branch?: number;
    employee?: number;
    search?: string;
  }): Promise<Asset[]> => {
    const query = new URLSearchParams();
    if (params?.category) query.append('category', params.category.toString());
    if (params?.status) query.append('status', params.status);
    if (params?.branch) query.append('branch', params.branch.toString());
    if (params?.employee) query.append('employee', params.employee.toString());
    if (params?.search) query.append('search', params.search);

    const qs = query.toString() ? `?${query.toString()}` : '';
    const res = await fetch(`/api/v1/assets/${qs}`, { headers: getAuthHeaders() });
    const data = await handleResponse<any>(res);
    return Array.isArray(data) ? data : data.results || [];
  },

  getAsset: async (id: number): Promise<Asset> => {
    const res = await fetch(`/api/v1/assets/${id}/`, { headers: getAuthHeaders() });
    return await handleResponse<Asset>(res);
  },

  createAsset: async (payload: CreateAssetPayload): Promise<Asset> => {
    const res = await fetch('/api/v1/assets/', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return await handleResponse<Asset>(res);
  },

  updateAsset: async (id: number, payload: Partial<CreateAssetPayload>): Promise<Asset> => {
    const res = await fetch(`/api/v1/assets/${id}/`, {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return await handleResponse<Asset>(res);
  },

  deleteAsset: async (id: number): Promise<void> => {
    const res = await fetch(`/api/v1/assets/${id}/`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    return await handleResponse<void>(res);
  },

  assignAsset: async (id: number, payload: AssignAssetPayload): Promise<AssetAssignment> => {
    const res = await fetch(`/api/v1/assets/${id}/assign/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return await handleResponse<AssetAssignment>(res);
  },

  returnAsset: async (id: number, payload: ReturnAssetPayload): Promise<Asset> => {
    const res = await fetch(`/api/v1/assets/${id}/return/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return await handleResponse<Asset>(res);
  },

  getMyAssets: async (): Promise<Asset[]> => {
    const res = await fetch('/api/v1/assets/my-assets/', { headers: getAuthHeaders() });
    const data = await handleResponse<any>(res);
    return Array.isArray(data) ? data : data.results || [];
  },
};
