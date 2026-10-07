import type { CsvTemplate, ImportJob, ImportJobError } from '../types/dataImport';

const getHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return {
    'Authorization': `Token ${token}`
  };
};

const getJsonHeaders = () => {
  return {
    ...getHeaders(),
    'Content-Type': 'application/json'
  };
};

export const dataImportService = {
  getTemplates: async (): Promise<CsvTemplate[]> => {
    const response = await fetch('/api/v1/data-import/templates/', {
      headers: getHeaders()
    });
    if (!response.ok) throw new Error('Failed to fetch templates');
    return response.json();
  },

  getTemplateDownloadUrl: (key: string): string => {
    // Return the URL so the browser can download it
    // But since it needs auth header, we might have to fetch and create object URL
    return `/api/v1/data-import/templates/${key}/download/`;
  },

  downloadTemplate: async (key: string, filename: string): Promise<void> => {
    const response = await fetch(`/api/v1/data-import/templates/${key}/download/`, {
      headers: getHeaders()
    });
    if (!response.ok) throw new Error('Failed to download template');
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();
  },

  getJobs: async (): Promise<ImportJob[]> => {
    const response = await fetch('/api/v1/data-import/jobs/', {
      headers: getHeaders()
    });
    if (!response.ok) throw new Error('Failed to fetch jobs');
    return response.json();
  },

  createJob: async (templateKey: string, file: File): Promise<ImportJob> => {
    const formData = new FormData();
    formData.append('template_key', templateKey);
    formData.append('file', file);

    const response = await fetch('/api/v1/data-import/jobs/', {
      method: 'POST',
      headers: getHeaders(), // Don't set Content-Type here, let browser set it with boundary
      body: formData
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to create job: ${errorText}`);
    }
    return response.json();
  },

  validateJob: async (id: string): Promise<ImportJob> => {
    const response = await fetch(`/api/v1/data-import/jobs/${id}/validate/`, {
      method: 'POST',
      headers: getJsonHeaders()
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || 'Validation failed');
    }
    return response.json();
  },

  executeJob: async (id: string): Promise<ImportJob> => {
    const response = await fetch(`/api/v1/data-import/jobs/${id}/execute/`, {
      method: 'POST',
      headers: getJsonHeaders()
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || 'Execution failed');
    }
    return response.json();
  },

  getJobErrors: async (id: string): Promise<ImportJobError[]> => {
    const response = await fetch(`/api/v1/data-import/jobs/${id}/errors/`, {
      headers: getHeaders()
    });
    if (!response.ok) throw new Error('Failed to fetch job errors');
    return response.json();
  }
};
