/**
 * Candidate & Onboarding API service.
 *
 * Two surfaces:
 *  1. HR/Admin endpoints — require candidate.* permissions
 *  2. Candidate portal endpoints — only for users with a candidate account
 */

const getAuthHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('auth_token');
  return token
    ? { Authorization: `Token ${token}`, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' };
};

const getAuthHeadersForUpload = (): Record<string, string> => {
  const token = localStorage.getItem('auth_token');
  return token ? { Authorization: `Token ${token}` } : {};
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

export type CandidateStatus =
  | 'created'
  | 'offered'
  | 'onboarding'
  | 'submitted'
  | 'verifying'
  | 'approved'
  | 'converted'
  | 'rejected';

export interface CandidateDocument {
  id: number;
  candidate: number;
  document_type: string;
  document_type_display: string;
  document_name: string;
  file_size: number;
  mime_type: string;
  description: string;
  status: 'pending' | 'verified' | 'rejected';
  status_display: string;
  rejection_reason: string;
  uploaded_at: string;
  uploaded_by: number | null;
  uploaded_by_email: string;
  reviewed_at: string | null;
  reviewed_by: number | null;
  reviewed_by_email: string;
}

export interface IssuedLetter {
  id: number;
  candidate: number;
  candidate_name: string;
  letter_type: string;
  letter_type_display: string;
  template: number | null;
  template_version: number | null;
  subject_snapshot: string;
  body_snapshot: string;
  issued_by: number | null;
  issued_by_email: string;
  issued_at: string;
}

export interface Candidate {
  id: number;
  organization: number;
  organization_name: string;
  first_name: string;
  last_name: string;
  email: string;
  phone_number: string;
  address: string;
  applied_designation: number | null;
  designation_name: string;
  proposed_joining_date: string | null;
  notes: string;
  status: CandidateStatus;
  status_display: string;
  user: number | null;
  employee: number | null;
  employee_id_display: string | null;
  created_by: number | null;
  created_by_email: string;
  document_count: number;
  documents: CandidateDocument[];
  issued_letters: IssuedLetter[];
  created_at: string;
  updated_at: string;
}

export interface CandidateListItem {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone_number: string;
  applied_designation: number | null;
  designation_name: string;
  proposed_joining_date: string | null;
  status: CandidateStatus;
  status_display: string;
  document_count: number;
  created_at: string;
}

export interface LetterTemplate {
  id: number;
  organization: number;
  letter_type: string;
  letter_type_display: string;
  version: number;
  subject: string;
  body: string;
  is_active: boolean;
  created_by: number | null;
  created_by_email: string;
  created_at: string;
  updated_at: string;
}

export interface CreateCandidatePayload {
  first_name: string;
  last_name: string;
  email: string;
  phone_number?: string;
  address?: string;
  applied_designation?: number | null;
  proposed_joining_date?: string | null;
  notes?: string;
  organization?: number;
}

export interface CreateLetterTemplatePayload {
  letter_type: 'offer' | 'appointment';
  subject: string;
  body: string;
  organization?: number;
}

// ---------------------------------------------------------------------------
// HR Candidate Service
// ---------------------------------------------------------------------------

export const candidateService = {
  /**
   * List candidates. Supports ?status=&search=&organization_id=
   */
  listCandidates: async (params?: {
    status?: string;
    search?: string;
    organization_id?: number;
    page?: number;
    page_size?: number;
  }): Promise<{ results: CandidateListItem[]; count: number }> => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    if (params?.search) qs.set('search', params.search);
    if (params?.organization_id) qs.set('organization_id', String(params.organization_id));
    if (params?.page) qs.set('page', String(params.page));
    if (params?.page_size) qs.set('page_size', String(params.page_size));
    qs.set('paginate', 'true');

    const res = await fetch(`/api/v1/candidates/?${qs}`, { headers: getAuthHeaders() });
    return handleResponse<{ results: CandidateListItem[]; count: number }>(res);
  },

  getCandidate: async (id: number): Promise<Candidate> => {
    const res = await fetch(`/api/v1/candidates/${id}/`, { headers: getAuthHeaders() });
    return handleResponse<Candidate>(res);
  },

  createCandidate: async (payload: CreateCandidatePayload): Promise<Candidate> => {
    const res = await fetch('/api/v1/candidates/', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse<Candidate>(res);
  },

  updateCandidate: async (id: number, payload: Partial<CreateCandidatePayload>): Promise<Candidate> => {
    const res = await fetch(`/api/v1/candidates/${id}/`, {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse<Candidate>(res);
  },

  issueOffer: async (id: number): Promise<{ detail: string; candidate: Candidate; issued_letter: IssuedLetter }> => {
    const res = await fetch(`/api/v1/candidates/${id}/issue-offer/`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  verifyDocuments: async (id: number): Promise<Candidate> => {
    const res = await fetch(`/api/v1/candidates/${id}/verify-documents/`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return handleResponse<Candidate>(res);
  },

  approveCandidate: async (id: number): Promise<Candidate> => {
    const res = await fetch(`/api/v1/candidates/${id}/approve/`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return handleResponse<Candidate>(res);
  },

  rejectCandidate: async (id: number, reason: string): Promise<Candidate> => {
    const res = await fetch(`/api/v1/candidates/${id}/reject/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ reason }),
    });
    return handleResponse<Candidate>(res);
  },

  convertToEmployee: async (id: number): Promise<{ detail: string; candidate: Candidate; employee_id: number; employee_code: string }> => {
    const res = await fetch(`/api/v1/candidates/${id}/convert-to-employee/`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return handleResponse(res);
  },

  addNote: async (id: number, note: string): Promise<{ id: number; note: string; author_email: string; created_at: string }> => {
    const res = await fetch(`/api/v1/candidates/${id}/add-note/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ note }),
    });
    return handleResponse(res);
  },

  // HR Document actions
  listDocuments: async (candidateId: number): Promise<CandidateDocument[]> => {
    const res = await fetch(`/api/v1/candidates/${candidateId}/documents/`, { headers: getAuthHeaders() });
    return handleResponse<CandidateDocument[]>(res);
  },

  verifyDocument: async (
    candidateId: number,
    documentId: number,
    decision: 'verified' | 'rejected',
    rejection_reason?: string
  ): Promise<CandidateDocument> => {
    const res = await fetch(`/api/v1/candidates/${candidateId}/documents/${documentId}/verify/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ decision, rejection_reason }),
    });
    return handleResponse<CandidateDocument>(res);
  },

  // Letter Templates
  listTemplates: async (params?: { letter_type?: string; organization_id?: number }): Promise<LetterTemplate[]> => {
    const qs = new URLSearchParams();
    if (params?.letter_type) qs.set('letter_type', params.letter_type);
    if (params?.organization_id) qs.set('organization_id', String(params.organization_id));
    const res = await fetch(`/api/v1/candidates/letters/templates/?${qs}`, { headers: getAuthHeaders() });
    return handleResponse<LetterTemplate[]>(res);
  },

  createTemplate: async (payload: CreateLetterTemplatePayload): Promise<LetterTemplate> => {
    const res = await fetch('/api/v1/candidates/letters/templates/', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse<LetterTemplate>(res);
  },
};

// ---------------------------------------------------------------------------
// Candidate Portal Service (candidate self-service)
// ---------------------------------------------------------------------------

export interface CandidatePortalProfile {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone_number: string;
  address: string;
  applied_designation: number | null;
  proposed_joining_date: string | null;
  status: CandidateStatus;
  organization: number;
}

export const candidatePortalService = {
  activate: async (uid: string, token: string, password: string): Promise<{ detail: string }> => {
    const res = await fetch('/api/v1/candidates/portal/activate/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uid, token, password }),
    });
    return handleResponse<{ detail: string }>(res);
  },

  getProfile: async (): Promise<CandidatePortalProfile> => {
    const res = await fetch('/api/v1/candidates/portal/me/', { headers: getAuthHeaders() });
    return handleResponse<CandidatePortalProfile>(res);
  },

  updateProfile: async (data: Partial<CandidatePortalProfile>): Promise<CandidatePortalProfile> => {
    const res = await fetch('/api/v1/candidates/portal/me/', {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<CandidatePortalProfile>(res);
  },

  getDocuments: async (): Promise<CandidateDocument[]> => {
    const res = await fetch('/api/v1/candidates/portal/documents/', { headers: getAuthHeaders() });
    return handleResponse<CandidateDocument[]>(res);
  },

  uploadDocument: async (formData: FormData): Promise<CandidateDocument> => {
    const res = await fetch('/api/v1/candidates/portal/documents/', {
      method: 'POST',
      headers: getAuthHeadersForUpload(),
      body: formData,
    });
    return handleResponse<CandidateDocument>(res);
  },

  deleteDocument: async (documentId: number): Promise<void> => {
    const res = await fetch(`/api/v1/candidates/portal/documents/${documentId}/`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    return handleResponse<void>(res);
  },

  submitOnboarding: async (): Promise<{ detail: string; status: string }> => {
    const res = await fetch('/api/v1/candidates/portal/submit/', {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return handleResponse<{ detail: string; status: string }>(res);
  },

  getLetters: async (): Promise<IssuedLetter[]> => {
    const res = await fetch('/api/v1/candidates/portal/letters/', { headers: getAuthHeaders() });
    return handleResponse<IssuedLetter[]>(res);
  },
};
