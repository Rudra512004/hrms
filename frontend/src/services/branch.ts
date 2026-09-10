export interface Branch {
    id: number;
    organization: number;
    name: string;
    address: string;
    latitude: string | number | null;
    longitude: string | number | null;
    radius: string | number;
    is_active: boolean;
    created_at: string;
    updated_at: string;
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

export const branchService = {
    getAll: async (): Promise<Branch[]> => {
        const response = await fetch('/api/v1/organization/branches/', {
            headers: getHeaders()
        });
        return handleResponse(response);
    },

    getById: async (id: number): Promise<Branch> => {
        const response = await fetch(`/api/v1/organization/branches/${id}/`, {
            headers: getHeaders()
        });
        return handleResponse(response);
    },

    create: async (data: Partial<Branch>): Promise<Branch> => {
        const response = await fetch('/api/v1/organization/branches/', {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(data)
        });
        return handleResponse(response);
    },

    update: async (id: number, data: Partial<Branch>): Promise<Branch> => {
        const response = await fetch(`/api/v1/organization/branches/${id}/`, {
            method: 'PATCH',
            headers: getHeaders(),
            body: JSON.stringify(data)
        });
        return handleResponse(response);
    },

    delete: async (id: number): Promise<void> => {
        const response = await fetch(`/api/v1/organization/branches/${id}/`, {
            method: 'DELETE',
            headers: getHeaders()
        });
        return handleResponse(response);
    }
};
