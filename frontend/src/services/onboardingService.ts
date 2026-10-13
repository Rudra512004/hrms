/**
 * Organization Onboarding & Setup Wizard Service
 *
 * Implements the verified Phase 3C API contract:
 * Canonical: /api/v1/organization/wizard/
 * Alias:     /api/v1/organization/onboarding/
 */

export interface WizardMetadata {
  [key: string]: any;
}

export interface ReadinessSummary {
  score: number;
  total_checks: number;
  ready_checks: number;
}

export interface WizardStatusResponse {
  onboarding_id: number;
  organization_id: number;
  organization_name: string;
  organization_code?: string;
  status: 'not_started' | 'in_progress' | 'completed' | 'abandoned';
  current_stage: number;
  completed_stages: number[];
  completed_at: string | null;
  metadata?: WizardMetadata;
  readiness_summary?: ReadinessSummary;
}

export interface Stage1Payload {
  name: string;
  code?: string;
  currency_code?: string;
  date_format?: string;
  timezone?: string;
}

export interface Stage2Payload {
  name: string;
  code?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  timezone?: string;
  latitude?: number | null;
  longitude?: number | null;
  radius?: number;
}

export interface DepartmentItem {
  name: string;
  code?: string;
  description?: string;
}

export interface DesignationItem {
  name: string;
  code?: string;
  level?: number;
}

export interface Stage3Payload {
  departments: DepartmentItem[];
  designations: DesignationItem[];
}

export interface RecurringRuleItem {
  weekday: number;
  occurrence: number;
  is_working: boolean;
}

export interface HolidayItem {
  name: string;
  date: string;
  holiday_type?: string;
}

export interface Stage4Payload {
  work_days: string;
  recurring_rules?: RecurringRuleItem[];
  holidays?: HolidayItem[];
}

export interface ShiftItem {
  name: string;
  code?: string;
  start_time: string;
  end_time: string;
  grace_period_minutes?: number;
  work_days?: string;
}

export interface AttendancePolicyItem {
  is_office_gps_enabled?: boolean;
  is_office_ip_enabled?: boolean;
  is_wfh_enabled?: boolean;
  wfh_bypasses_office_restrictions?: boolean;
}

export interface OfficeNetworkItem {
  name: string;
  network: string;
  description?: string;
}

export interface Stage5Payload {
  shift: ShiftItem;
  attendance_policy?: AttendancePolicyItem;
  office_network?: OfficeNetworkItem;
}

export interface Stage6SelfPayload {
  assignment_type?: 'self';
  confirm: boolean;
}

export interface Stage6InvitePayload {
  assignment_type: 'invite';
  first_name: string;
  last_name?: string;
  email: string;
}

export type Stage6Payload = Stage6SelfPayload | Stage6InvitePayload;

export interface InvitationResendResponse {
  detail: string;
  invitation_id: number;
  email: string;
  status: string;
  email_delivery_status: string;
  resend_count: number;
  expires_at: string;
}

export interface InvitationRevokeResponse {
  detail: string;
  invitation_id: number;
  status: string;
}

export interface InvitationVerifyResponse {
  valid: boolean;
  organization_name: string;
  organization_code?: string;
  email: string;
  first_name: string;
  last_name: string;
  expires_at: string;
}

export interface InvitationAcceptPayload {
  token: string;
  password?: string;
  first_name?: string;
  last_name?: string;
}

export interface InvitationAcceptResponse {
  detail: string;
  organization_id: number;
  organization_name: string;
  role: string;
  status: string;
}

export interface CompleteWizardResponse {
  status: string;
  organization_id: number;
  completed_at: string;
  readiness_score: number;
  redirect_url: string;
}

export interface ReadinessCheck {
  name: string;
  state: 'ready' | 'action_required' | 'recommended';
  message: string;
}

export interface DiagnosticReadinessResponse {
  score: number;
  ready: boolean;
  checks: ReadinessCheck[];
}

export interface DraftSaveResponse {
  detail: string;
  stage: number;
  current_stage: number;
}

export class OnboardingApiError extends Error {
  status: number;
  data: Record<string, any>;

  constructor(status: number, message: string, data: Record<string, any> = {}) {
    super(message);
    this.name = 'OnboardingApiError';
    this.status = status;
    this.data = data;
  }
}

const getHeaders = (includeContentType = true): HeadersInit => {
  const token = localStorage.getItem('auth_token');
  const headers: Record<string, string> = {
    Accept: 'application/json',
  };
  if (includeContentType) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) {
    headers['Authorization'] = `Token ${token}`;
  }
  return headers;
};

const handleResponse = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    let errorMessage = 'An error occurred during onboarding.';

    if (errorData.detail) {
      errorMessage = errorData.detail;
    } else if (errorData.non_field_errors && Array.isArray(errorData.non_field_errors) && errorData.non_field_errors[0]) {
      errorMessage = errorData.non_field_errors[0];
    } else {
      const keys = Object.keys(errorData);
      if (keys.length > 0) {
        const val = errorData[keys[0]];
        if (Array.isArray(val) && val[0]) {
          errorMessage = `${keys[0]}: ${val[0]}`;
        } else if (typeof val === 'string') {
          errorMessage = `${keys[0]}: ${val}`;
        }
      }
    }
    throw new OnboardingApiError(response.status, errorMessage, errorData);
  }
  if (response.status === 204) return null as unknown as T;
  return response.json();
};

export const onboardingService = {
  /**
   * GET /api/v1/organization/wizard/status/
   * Queries the current onboarding progress and metadata.
   */
  getStatus: async (orgId?: number): Promise<WizardStatusResponse> => {
    const query = orgId ? `?org_id=${orgId}` : '';
    const response = await fetch(`/api/v1/organization/wizard/status/${query}`, {
      method: 'GET',
      headers: getHeaders(false),
    });
    return handleResponse<WizardStatusResponse>(response);
  },

  /**
   * POST /api/v1/organization/wizard/start/
   * Initializes tenant organization and runs Stage 1.
   */
  startWizard: async (data: Stage1Payload, orgId?: number): Promise<WizardStatusResponse> => {
    const query = orgId ? `?org_id=${orgId}` : '';
    const response = await fetch(`/api/v1/organization/wizard/start/${query}`, {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(data),
    });
    return handleResponse<WizardStatusResponse>(response);
  },

  /**
   * POST /api/v1/organization/wizard/stage/<int:stage_number>/
   * Submits a discrete stage payload to the dispatcher.
   */
  submitStage: async (
    stageNumber: number,
    data: any,
    orgId?: number
  ): Promise<WizardStatusResponse> => {
    const query = orgId ? `?org_id=${orgId}` : '';
    const response = await fetch(`/api/v1/organization/wizard/stage/${stageNumber}/${query}`, {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(data),
    });
    return handleResponse<WizardStatusResponse>(response);
  },

  /**
   * Dedicated Stage Submissions (Convenience Methods)
   */
  submitStage2Branch: async (data: Stage2Payload, orgId?: number): Promise<WizardStatusResponse> => {
    return onboardingService.submitStage(2, data, orgId);
  },

  submitStage3Structure: async (data: Stage3Payload, orgId?: number): Promise<WizardStatusResponse> => {
    return onboardingService.submitStage(3, data, orgId);
  },

  submitStage4Calendar: async (data: Stage4Payload, orgId?: number): Promise<WizardStatusResponse> => {
    return onboardingService.submitStage(4, data, orgId);
  },

  submitStage5ShiftsPolicy: async (data: Stage5Payload, orgId?: number): Promise<WizardStatusResponse> => {
    return onboardingService.submitStage(5, data, orgId);
  },

  submitStage6AdminRbac: async (data: Stage6Payload = { confirm: true }, orgId?: number): Promise<WizardStatusResponse> => {
    return onboardingService.submitStage(6, data, orgId);
  },

  /**
   * POST /api/v1/organization/wizard/stage-6/resend/
   * Resends an active pending administrator invitation and rotates the token.
   */
  resendStage6Invitation: async (orgId?: number): Promise<InvitationResendResponse> => {
    const query = orgId ? `?org_id=${orgId}` : '';
    const response = await fetch(`/api/v1/organization/wizard/stage-6/resend/${query}`, {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify({}),
    });
    return handleResponse<InvitationResendResponse>(response);
  },

  /**
   * POST /api/v1/organization/wizard/stage-6/revoke/
   * Revokes an active pending administrator invitation.
   */
  revokeStage6Invitation: async (orgId?: number): Promise<InvitationRevokeResponse> => {
    const query = orgId ? `?org_id=${orgId}` : '';
    const response = await fetch(`/api/v1/organization/wizard/stage-6/revoke/${query}`, {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify({}),
    });
    return handleResponse<InvitationRevokeResponse>(response);
  },

  /**
   * GET /api/v1/organization/invitations/verify/?token=<raw_token>
   * Validates invitation token without leaking arbitrary user existence.
   */
  verifyInvitation: async (token: string): Promise<InvitationVerifyResponse> => {
    const response = await fetch(`/api/v1/organization/invitations/verify/?token=${encodeURIComponent(token)}`, {
      method: 'GET',
      headers: getHeaders(false),
    });
    return handleResponse<InvitationVerifyResponse>(response);
  },

  /**
   * POST /api/v1/organization/invitations/accept/
   * Atomically accepts an invitation and provisions the organization Super Admin role.
   */
  acceptInvitation: async (payload: InvitationAcceptPayload): Promise<InvitationAcceptResponse> => {
    const response = await fetch('/api/v1/organization/invitations/accept/', {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify(payload),
    });
    return handleResponse<InvitationAcceptResponse>(response);
  },

  /**
   * POST /api/v1/organization/wizard/draft/
   * Saves partial, non-sensitive draft metadata.
   */
  saveDraft: async (stage: number, data: Record<string, any>, orgId?: number): Promise<DraftSaveResponse> => {
    const query = orgId ? `?org_id=${orgId}` : '';
    const response = await fetch(`/api/v1/organization/wizard/draft/${query}`, {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify({ stage, data }),
    });
    return handleResponse<DraftSaveResponse>(response);
  },

  /**
   * GET /api/v1/organization/wizard/readiness/
   * Queries full readiness diagnostic assessment.
   */
  getReadiness: async (orgId?: number): Promise<DiagnosticReadinessResponse> => {
    const query = orgId ? `?org_id=${orgId}` : '';
    const response = await fetch(`/api/v1/organization/wizard/readiness/${query}`, {
      method: 'GET',
      headers: getHeaders(false),
    });
    return handleResponse<DiagnosticReadinessResponse>(response);
  },

  /**
   * POST /api/v1/organization/wizard/complete/
   * Finalizes setup and activates the tenant organization.
   */
  completeWizard: async (orgId?: number): Promise<CompleteWizardResponse> => {
    const query = orgId ? `?org_id=${orgId}` : '';
    const response = await fetch(`/api/v1/organization/wizard/complete/${query}`, {
      method: 'POST',
      headers: getHeaders(true),
      body: JSON.stringify({}),
    });
    return handleResponse<CompleteWizardResponse>(response);
  },
};
