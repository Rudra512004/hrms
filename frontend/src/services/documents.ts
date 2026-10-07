/**
 * Documents API service for Phase 3 (Template Management, PDF Generation, Vault)
 */

const getAuthHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('auth_token');
  return token
    ? { Authorization: `Token ${token}`, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' };
};

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const message =
      err.detail ||
      err.non_field_errors?.[0] ||
      Object.values(err).flat().join(' ') ||
      `HTTP ${res.status}`;
    throw new Error(message as string);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DocumentCategory {
  id: number;
  name: string;
  description: string;
  is_active: boolean;
  created_at: string;
}

export interface TemplateVersion {
  id: number;
  template: number;
  version_number: number;
  subject: string;
  body: string;
  is_published: boolean;
  created_at: string;
  created_by: number | null;
}

export interface DocumentTemplateList {
  id: number;
  name: string;
  template_type: 'email' | 'pdf';
  category: number | null;
  category_name: string | null;
  is_active: boolean;
  active_version: number | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentTemplateDetail extends DocumentTemplateList {
  versions: TemplateVersion[];
}

export interface IssuedDocument {
  id: number;
  employee_name: string | null;
  candidate_name: string | null;
  document_type: 'email' | 'pdf';
  title: string;
  body_snapshot: string;
  file_attachment: string | null;
  issued_at: string;
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

export const documentService = {
  // Categories
  listCategories: async (): Promise<DocumentCategory[]> => {
    const res = await fetch('/api/v1/documents/categories/', { headers: getAuthHeaders() });
    return handleResponse<DocumentCategory[]>(res);
  },
  createCategory: async (data: { name: string; description?: string }): Promise<DocumentCategory> => {
    const res = await fetch('/api/v1/documents/categories/', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<DocumentCategory>(res);
  },

  // Templates
  listTemplates: async (): Promise<DocumentTemplateList[]> => {
    const res = await fetch('/api/v1/documents/templates/', { headers: getAuthHeaders() });
    return handleResponse<DocumentTemplateList[]>(res);
  },
  getTemplate: async (id: number): Promise<DocumentTemplateDetail> => {
    const res = await fetch(`/api/v1/documents/templates/${id}/`, { headers: getAuthHeaders() });
    return handleResponse<DocumentTemplateDetail>(res);
  },
  createTemplate: async (data: { name: string; template_type: 'email' | 'pdf'; category?: number | null }): Promise<DocumentTemplateDetail> => {
    const res = await fetch('/api/v1/documents/templates/', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<DocumentTemplateDetail>(res);
  },
  updateTemplate: async (id: number, data: { name?: string; is_active?: boolean; category?: number | null }): Promise<DocumentTemplateDetail> => {
    const res = await fetch(`/api/v1/documents/templates/${id}/`, {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<DocumentTemplateDetail>(res);
  },
  deleteTemplate: async (id: number): Promise<void> => {
    const res = await fetch(`/api/v1/documents/templates/${id}/`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    return handleResponse<void>(res);
  },

  // Template Versions
  addVersion: async (templateId: number, data: { subject: string; body: string; is_published: boolean }): Promise<TemplateVersion> => {
    const res = await fetch(`/api/v1/documents/templates/${templateId}/add_version/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<TemplateVersion>(res);
  },
  activateVersion: async (templateId: number, versionId: number): Promise<TemplateVersion> => {
    const res = await fetch(`/api/v1/documents/templates/${templateId}/activate_version/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ version_id: versionId }),
    });
    return handleResponse<TemplateVersion>(res);
  },
  previewTemplate: async (templateId: number, data: { version_id?: number; context_data?: any }): Promise<{ html: string }> => {
    const res = await fetch(`/api/v1/documents/templates/${templateId}/preview/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<{ html: string }>(res);
  },

  // Issued Documents
  listIssuedDocuments: async (): Promise<IssuedDocument[]> => {
    const res = await fetch('/api/v1/documents/issued/', { headers: getAuthHeaders() });
    return handleResponse<IssuedDocument[]>(res);
  },
  getIssuedDocument: async (id: number): Promise<IssuedDocument> => {
    const res = await fetch(`/api/v1/documents/issued/${id}/`, { headers: getAuthHeaders() });
    return handleResponse<IssuedDocument>(res);
  },
  generateDocument: async (data: { template_id: number; employee_id?: number; candidate_id?: number; context_data?: any }): Promise<IssuedDocument> => {
    const res = await fetch('/api/v1/documents/issued/generate/', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<IssuedDocument>(res);
  },
};
