import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  onboardingService,
  OnboardingApiError,
  type Stage1Payload,
  type Stage2Payload,
  type Stage3Payload,
  type Stage4Payload,
  type Stage5Payload,
} from '../onboardingService';

describe('Phase 3D — Onboarding Service API Contract Test Suite', () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', mockFetch);
    localStorage.setItem('auth_token', 'test-auth-token-123');
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  describe('1. GET /api/v1/organization/wizard/status/', () => {
    it('queries onboarding status without org_id using auth token headers', async () => {
      const mockStatus = {
        onboarding_id: 1,
        organization_id: 10,
        organization_name: 'Acme Corp',
        status: 'in_progress',
        current_stage: 2,
        completed_stages: [1],
        completed_at: null,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockStatus,
      });

      const result = await onboardingService.getStatus();

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/wizard/status/');
      expect(options.headers).toMatchObject({
        Authorization: 'Token test-auth-token-123',
        Accept: 'application/json',
      });
      expect(result).toEqual(mockStatus);
    });

    it('appends org_id query parameter when specified', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ onboarding_id: 2, organization_id: 45 }),
      });

      await onboardingService.getStatus(45);

      const [url] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/wizard/status/?org_id=45');
    });
  });

  describe('2. POST /api/v1/organization/wizard/start/', () => {
    it('initializes wizard session with Stage 1 organization details', async () => {
      const payload: Stage1Payload = {
        name: 'Apex Global Technologies',
        code: 'APEX',
        currency_code: 'INR',
        date_format: 'DD/MM/YYYY',
        timezone: 'Asia/Kolkata',
      };

      const mockResponse = {
        onboarding_id: 12,
        organization_id: 45,
        name: 'Apex Global Technologies',
        code: 'APEX',
        current_stage: 2,
        completed_stages: [1],
        status: 'in_progress',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => mockResponse,
      });

      const result = await onboardingService.startWizard(payload);

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/wizard/start/');
      expect(options.method).toBe('POST');
      expect(JSON.parse(options.body)).toEqual(payload);
      expect(result).toEqual(mockResponse);
    });
  });

  describe('3. POST /api/v1/organization/wizard/stage/<n>/ (Stages 2 through 6)', () => {
    it('submits Stage 2 branch details via submitStage2Branch', async () => {
      const stage2Data: Stage2Payload = {
        name: 'Headquarters Bengaluru',
        code: 'HQ-BLR',
        city: 'Bengaluru',
        radius: 200.0,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ current_stage: 3, completed_stages: [1, 2] }),
      });

      const result = await onboardingService.submitStage2Branch(stage2Data);

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/wizard/stage/2/');
      expect(JSON.parse(options.body)).toEqual(stage2Data);
      expect(result.current_stage).toBe(3);
    });

    it('submits Stage 3 structure via submitStage3Structure', async () => {
      const stage3Data: Stage3Payload = {
        departments: [{ name: 'Engineering', code: 'ENG' }],
        designations: [{ name: 'Lead Engineer', code: 'LEAD', level: 1 }],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ current_stage: 4, completed_stages: [1, 2, 3] }),
      });

      const result = await onboardingService.submitStage3Structure(stage3Data);

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/wizard/stage/3/');
      expect(JSON.parse(options.body)).toEqual(stage3Data);
      expect(result.current_stage).toBe(4);
    });

    it('submits Stage 4 calendar via submitStage4Calendar', async () => {
      const stage4Data: Stage4Payload = {
        work_days: '0,1,2,3,4',
        recurring_rules: [{ weekday: 5, occurrence: 2, is_working: false }],
        holidays: [{ name: 'Republic Day', date: '2026-01-26', holiday_type: 'public' }],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ current_stage: 5, completed_stages: [1, 2, 3, 4] }),
      });

      const result = await onboardingService.submitStage4Calendar(stage4Data);

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/wizard/stage/4/');
      expect(JSON.parse(options.body)).toEqual(stage4Data);
      expect(result.current_stage).toBe(5);
    });

    it('submits Stage 5 shifts and policy via submitStage5ShiftsPolicy', async () => {
      const stage5Data: Stage5Payload = {
        shift: {
          name: 'General Shift',
          start_time: '09:00:00',
          end_time: '18:00:00',
          grace_period_minutes: 15,
        },
        attendance_policy: {
          is_office_gps_enabled: true,
          is_office_ip_enabled: false,
          is_wfh_enabled: true,
        },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ current_stage: 6, completed_stages: [1, 2, 3, 4, 5] }),
      });

      const result = await onboardingService.submitStage5ShiftsPolicy(stage5Data);

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/wizard/stage/5/');
      expect(JSON.parse(options.body)).toEqual(stage5Data);
      expect(result.current_stage).toBe(6);
    });

    it('submits Stage 6 admin confirmation via submitStage6AdminRbac', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ current_stage: 7, completed_stages: [1, 2, 3, 4, 5, 6] }),
      });

      const result = await onboardingService.submitStage6AdminRbac({ confirm: true });

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/wizard/stage/6/');
      expect(JSON.parse(options.body)).toEqual({ confirm: true });
      expect(result.current_stage).toBe(7);
    });
  });

  describe('4. Draft, Readiness & Complete Endpoints', () => {
    it('saves draft metadata via saveDraft', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ detail: 'Draft saved successfully.', stage: 2, current_stage: 2 }),
      });

      const result = await onboardingService.saveDraft(2, { proposed_branch: 'Bengaluru' });

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/wizard/draft/');
      expect(JSON.parse(options.body)).toEqual({
        stage: 2,
        data: { proposed_branch: 'Bengaluru' },
      });
      expect(result.detail).toBe('Draft saved successfully.');
    });

    it('queries diagnostic readiness scorecard via getReadiness', async () => {
      const mockReadiness = {
        score: 86,
        ready: false,
        checks: [
          { name: 'branches', state: 'ready', message: 'At least one active branch configured.' },
          { name: 'leave_types', state: 'action_required', message: 'No leave types configured.' },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockReadiness,
      });

      const result = await onboardingService.getReadiness();

      const [url] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/wizard/readiness/');
      expect(result).toEqual(mockReadiness);
    });

    it('completes onboarding and triggers launch via completeWizard', async () => {
      const mockComplete = {
        status: 'completed',
        organization_id: 10,
        completed_at: '2026-10-13T09:00:00Z',
        readiness_score: 86,
        redirect_url: '/dashboard',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockComplete,
      });

      const result = await onboardingService.completeWizard();

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/wizard/complete/');
      expect(options.method).toBe('POST');
      expect(result).toEqual(mockComplete);
    });
  });

  describe('5. Error Handling & OnboardingApiError', () => {
    it('throws OnboardingApiError with field-specific validation errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ radius: ['Branch radius must be at least 100.0 meters.'] }),
      });

      await expect(onboardingService.submitStage2Branch({ name: 'HQ', radius: 50 })).rejects.toThrow(
        'radius: Branch radius must be at least 100.0 meters.'
      );
    });

    it('throws OnboardingApiError with detail message on prerequisite violation', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'Preceding stages must be completed first.' }),
      });

      await expect(onboardingService.submitStage(3, {})).rejects.toThrow(
        'Preceding stages must be completed first.'
      );
    });

    it('throws OnboardingApiError with 403 on cross-tenant access rejection', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'You do not have administrative access to this organization.' }),
      });

      await expect(onboardingService.getStatus(999)).rejects.toBeInstanceOf(OnboardingApiError);
      await expect(onboardingService.getStatus(999)).rejects.toMatchObject({
        name: 'OnboardingApiError',
        status: 403,
        message: 'You do not have administrative access to this organization.',
      });
    });
  });
});
