// Employee Documents API service — mirrors apps/employees/views.py EmployeeDocumentViewSet
// Base URL: /api/v1/employees/documents/

export interface EmployeeDocument {
  id: number;
  employee: number;
  document_type: string;
  document_type_display: string;
  document_name: string;
  file_size: number;
  mime_type: string;
  description: string;
  expiry_date: string | null;
  status: string;
  status_display: string;
  uploaded_at: string;
  uploaded_by: number;
  uploaded_by_email: string;
}

const getAuthHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('auth_token');
  if (!token) throw new Error('No authentication token');
  return {
    Authorization: `Token ${token}`,
  };
};

export const employeeDocumentService = {
  listDocuments: async (employeeId?: number): Promise<EmployeeDocument[]> => {
    const url = employeeId
      ? `/api/v1/employees/documents/?employee=${employeeId}`
      : `/api/v1/employees/documents/`;

    const res = await fetch(url, {
      headers: {
        ...getAuthHeaders(),
        Accept: 'application/json',
      },
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw { status: res.status, data: err };
    }

    const data = await res.json();
    // Handle both raw arrays and potential pagination envelopes
    if (Array.isArray(data)) {
      return data;
    }
    if (data && Array.isArray(data.results)) {
      return data.results;
    }
    return [];
  },

  getDocument: async (id: number): Promise<EmployeeDocument> => {
    const res = await fetch(`/api/v1/employees/documents/${id}/`, {
      headers: {
        ...getAuthHeaders(),
        Accept: 'application/json',
      },
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw { status: res.status, data: err };
    }

    return await res.json();
  },

  uploadDocument: async (formData: FormData): Promise<EmployeeDocument> => {
    const res = await fetch('/api/v1/employees/documents/', {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
        // Do NOT set Content-Type so browser sets boundary for multipart/form-data
      },
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw { status: res.status, data: err };
    }

    return await res.json();
  },

  deleteDocument: async (id: number): Promise<void> => {
    const res = await fetch(`/api/v1/employees/documents/${id}/`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw { status: res.status, data: err };
    }
  },

  downloadDocument: async (id: number, filename: string): Promise<void> => {
    const res = await fetch(`/api/v1/employees/documents/${id}/download/`, {
      headers: getAuthHeaders(),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw { status: res.status, data: err };
    }

    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename || 'document';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(blobUrl);
  },

  previewDocument: async (id: number): Promise<void> => {
    const res = await fetch(`/api/v1/employees/documents/${id}/preview/`, {
      headers: getAuthHeaders(),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw { status: res.status, data: err };
    }

    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    window.open(blobUrl, '_blank');
    setTimeout(() => {
      window.URL.revokeObjectURL(blobUrl);
    }, 60000);
  },
};
