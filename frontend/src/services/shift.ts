export interface Shift {
    id: number;
    organization: number;
    name: string;
    start_time: string;
    end_time: string;
    grace_period: string | null;
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

export const shiftService = {
    getAll: async (): Promise<Shift[]> => {
        const response = await fetch('/api/v1/attendance/shifts/', {
            headers: getHeaders()
        });
        return handleResponse(response);
    },

    getById: async (id: number): Promise<Shift> => {
        const response = await fetch(`/api/v1/attendance/shifts/${id}/`, {
            headers: getHeaders()
        });
        return handleResponse(response);
    },

    create: async (data: Partial<Shift>): Promise<Shift> => {
        const response = await fetch('/api/v1/attendance/shifts/', {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(data)
        });
        return handleResponse(response);
    },

    update: async (id: number, data: Partial<Shift>): Promise<Shift> => {
        const response = await fetch(`/api/v1/attendance/shifts/${id}/`, {
            method: 'PATCH',
            headers: getHeaders(),
            body: JSON.stringify(data)
        });
        return handleResponse(response);
    },

    delete: async (id: number): Promise<void> => {
        const response = await fetch(`/api/v1/attendance/shifts/${id}/`, {
            method: 'DELETE',
            headers: getHeaders()
        });
        return handleResponse(response);
    }
};
