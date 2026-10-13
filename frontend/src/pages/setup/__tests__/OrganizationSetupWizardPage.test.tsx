import '@testing-library/jest-dom/vitest';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { OrganizationSetupWizardPage } from '../OrganizationSetupWizardPage';
import { onboardingService } from '../../../services/onboardingService';
import * as AuthContextModule from '../../../contexts/AuthContext';

vi.mock('../../../services/onboardingService', () => ({
  onboardingService: {
    getStatus: vi.fn(),
    startWizard: vi.fn(),
    submitStage: vi.fn(),
    submitStage2Branch: vi.fn(),
    submitStage3Structure: vi.fn(),
    submitStage4Calendar: vi.fn(),
    submitStage5ShiftsPolicy: vi.fn(),
    submitStage6AdminRbac: vi.fn(),
    saveDraft: vi.fn(),
    getReadiness: vi.fn(),
    completeWizard: vi.fn(),
  },
  OnboardingApiError: class OnboardingApiError extends Error {
    status: number;
    data: any;
    constructor(status: number, message: string, data: any = {}) {
      super(message);
      this.status = status;
      this.data = data;
    }
  },
}));

describe('Phase 3D — OrganizationSetupWizardPage UI Component Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: {
        id: '1',
        email: 'owner@beyondsure.com',
        firstName: 'Owner',
        lastName: 'User',
        isSuperuser: false,
        hasEmployeeProfile: false,
      },
      roles: [],
      permissions: [],
      loading: false,
      error: null,
      hasPermission: vi.fn(() => false),
      hasEmployeeProfile: false,
      refreshAuth: vi.fn(),
      logout: vi.fn(),
    });
  });

  it('renders loading state initially while querying onboarding state', async () => {
    vi.mocked(onboardingService.getStatus).mockReturnValue(new Promise(() => {}));

    render(
      <MemoryRouter initialEntries={['/setup/1']}>
        <Routes>
          <Route path="/setup/:stageNumber" element={<OrganizationSetupWizardPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Loading Setup Wizard...')).toBeInTheDocument();
  });

  it('renders Stage 1 organization details form and handles submission', async () => {
    vi.mocked(onboardingService.getStatus).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 10,
      organization_name: '',
      status: 'not_started',
      current_stage: 1,
      completed_stages: [],
      completed_at: null,
    });

    vi.mocked(onboardingService.startWizard).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 10,
      organization_name: 'Apex Corp',
      status: 'in_progress',
      current_stage: 2,
      completed_stages: [1],
      completed_at: null,
    });

    render(
      <MemoryRouter initialEntries={['/setup/1']}>
        <Routes>
          <Route path="/setup/:stageNumber" element={<OrganizationSetupWizardPage />} />
          <Route path="/setup/2" element={<div>Stage 2 Destination</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Organization Legal Name/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Organization Legal Name/i), {
      target: { value: 'Apex Corp' },
    });
    fireEvent.change(screen.getByLabelText(/Organization Code/i), {
      target: { value: 'APEX' },
    });

    fireEvent.click(screen.getByRole('button', { name: /Continue to Head Office/i }));

    await waitFor(() => {
      expect(onboardingService.startWizard).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Apex Corp',
          code: 'APEX',
          currency_code: 'INR',
        })
      );
    });
  });

  it('validates Stage 2 branch geofence radius client-side (min 100m)', async () => {
    vi.mocked(onboardingService.getStatus).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 10,
      organization_name: 'Apex Corp',
      status: 'in_progress',
      current_stage: 2,
      completed_stages: [1],
      completed_at: null,
    });

    render(
      <MemoryRouter initialEntries={['/setup/2']}>
        <Routes>
          <Route path="/setup/:stageNumber" element={<OrganizationSetupWizardPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Branch Name/i)).toBeInTheDocument();
    });

    // Enter radius below 100m
    const radiusInput = screen.getByLabelText(/Radius in Meters/i);
    fireEvent.change(radiusInput, { target: { value: '50' } });

    fireEvent.click(screen.getByRole('button', { name: /Continue to Structure/i }));

    await waitFor(() => {
      expect(screen.getByText(/Geofence radius must be at least 100.0 meters/i)).toBeInTheDocument();
      expect(onboardingService.submitStage2Branch).not.toHaveBeenCalled();
    });
  });

  it('renders Stage 3 structure with departments and designations', async () => {
    vi.mocked(onboardingService.getStatus).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 10,
      organization_name: 'Apex Corp',
      status: 'in_progress',
      current_stage: 3,
      completed_stages: [1, 2],
      completed_at: null,
    });

    vi.mocked(onboardingService.submitStage3Structure).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 10,
      organization_name: 'Apex Corp',
      status: 'in_progress',
      current_stage: 4,
      completed_stages: [1, 2, 3],
      completed_at: null,
    });

    render(
      <MemoryRouter initialEntries={['/setup/3']}>
        <Routes>
          <Route path="/setup/:stageNumber" element={<OrganizationSetupWizardPage />} />
          <Route path="/setup/4" element={<div>Stage 4 Destination</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Organizational Hierarchy & Structure/i)).toBeInTheDocument();
    });

    // Should have Add Department and Add Designation buttons
    expect(screen.getByRole('button', { name: /Add Department/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Add Designation/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Continue to Working Calendar/i }));

    await waitFor(() => {
      expect(onboardingService.submitStage3Structure).toHaveBeenCalledWith(
        expect.objectContaining({
          departments: expect.any(Array),
          designations: expect.any(Array),
        })
      );
    });
  });

  it('renders Stage 4 calendar and toggles working days', async () => {
    vi.mocked(onboardingService.getStatus).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 10,
      organization_name: 'Apex Corp',
      status: 'in_progress',
      current_stage: 4,
      completed_stages: [1, 2, 3],
      completed_at: null,
    });

    vi.mocked(onboardingService.submitStage4Calendar).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 10,
      organization_name: 'Apex Corp',
      status: 'in_progress',
      current_stage: 5,
      completed_stages: [1, 2, 3, 4],
      completed_at: null,
    });

    render(
      <MemoryRouter initialEntries={['/setup/4']}>
        <Routes>
          <Route path="/setup/:stageNumber" element={<OrganizationSetupWizardPage />} />
          <Route path="/setup/5" element={<div>Stage 5 Destination</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Working Calendar & Statutory Holidays/i)).toBeInTheDocument();
    });

    // Toggle 6-Day Week
    fireEvent.click(screen.getByRole('button', { name: /6-Day Week/i }));

    fireEvent.click(screen.getByRole('button', { name: /Continue to Shifts & Policy/i }));

    await waitFor(() => {
      expect(onboardingService.submitStage4Calendar).toHaveBeenCalledWith(
        expect.objectContaining({
          work_days: '0,1,2,3,4,5',
        })
      );
    });
  });

  it('renders Stage 5 shifts and attendance policies', async () => {
    vi.mocked(onboardingService.getStatus).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 10,
      organization_name: 'Apex Corp',
      status: 'in_progress',
      current_stage: 5,
      completed_stages: [1, 2, 3, 4],
      completed_at: null,
    });

    vi.mocked(onboardingService.submitStage5ShiftsPolicy).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 10,
      organization_name: 'Apex Corp',
      status: 'in_progress',
      current_stage: 6,
      completed_stages: [1, 2, 3, 4, 5],
      completed_at: null,
    });

    render(
      <MemoryRouter initialEntries={['/setup/5']}>
        <Routes>
          <Route path="/setup/:stageNumber" element={<OrganizationSetupWizardPage />} />
          <Route path="/setup/6" element={<div>Stage 6 Destination</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Primary Operational Shift/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Continue to Administrator & RBAC/i }));

    await waitFor(() => {
      expect(onboardingService.submitStage5ShiftsPolicy).toHaveBeenCalledWith(
        expect.objectContaining({
          shift: expect.objectContaining({ name: 'General Day Shift' }),
          attendance_policy: expect.objectContaining({ is_office_gps_enabled: true }),
        })
      );
    });
  });

  it('renders Stage 6 admin confirmation and requires checkbox confirmation', async () => {
    vi.mocked(onboardingService.getStatus).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 10,
      organization_name: 'Apex Corp',
      status: 'in_progress',
      current_stage: 6,
      completed_stages: [1, 2, 3, 4, 5],
      completed_at: null,
    });

    vi.mocked(onboardingService.submitStage6AdminRbac).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 10,
      organization_name: 'Apex Corp',
      status: 'in_progress',
      current_stage: 7,
      completed_stages: [1, 2, 3, 4, 5, 6],
      completed_at: null,
    });

    render(
      <MemoryRouter initialEntries={['/setup/6']}>
        <Routes>
          <Route path="/setup/:stageNumber" element={<OrganizationSetupWizardPage />} />
          <Route path="/setup/7" element={<div>Stage 7 Destination</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Initial Administrator & Dynamic RBAC Governance/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Continue to Final Review/i }));

    await waitFor(() => {
      expect(onboardingService.submitStage6AdminRbac).toHaveBeenCalledWith({ confirm: true });
    });
  });

  it('renders Stage 7 review with live readiness scorecard and completes setup', async () => {
    vi.mocked(onboardingService.getStatus).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 10,
      organization_name: 'Apex Corp',
      status: 'in_progress',
      current_stage: 7,
      completed_stages: [1, 2, 3, 4, 5, 6],
      completed_at: null,
      metadata: {
        stage_1: { name: 'Apex Corp', code: 'APEX', currency_code: 'INR' },
        stage_2: { name: 'Headquarters Bengaluru', city: 'Bengaluru', radius: 200 },
      },
      readiness_summary: { score: 86, total_checks: 7, ready_checks: 6 },
    });

    vi.mocked(onboardingService.getReadiness).mockResolvedValueOnce({
      score: 86,
      ready: false,
      checks: [
        { name: 'branches', state: 'ready', message: 'At least one active branch configured.' },
        { name: 'shifts', state: 'ready', message: 'Configured active shift verified.' },
      ],
    });

    vi.mocked(onboardingService.completeWizard).mockResolvedValueOnce({
      status: 'completed',
      organization_id: 10,
      completed_at: '2026-10-13T09:00:00Z',
      readiness_score: 86,
      redirect_url: '/dashboard',
    });

    render(
      <MemoryRouter initialEntries={['/setup/7']}>
        <Routes>
          <Route path="/setup/:stageNumber" element={<OrganizationSetupWizardPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Setup Verification & Operational Launch/i)).toBeInTheDocument();
      expect(screen.getByText('86% Ready')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Complete Setup & Launch Organization/i }));

    await waitFor(() => {
      expect(onboardingService.completeWizard).toHaveBeenCalledWith(10);
    });
  });

  it('handles draft persistence via Save Draft button', async () => {
    vi.mocked(onboardingService.getStatus).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 10,
      organization_name: 'Apex Corp',
      status: 'in_progress',
      current_stage: 2,
      completed_stages: [1],
      completed_at: null,
    });

    vi.mocked(onboardingService.saveDraft).mockResolvedValueOnce({
      detail: 'Draft saved successfully.',
      stage: 2,
      current_stage: 2,
    });

    render(
      <MemoryRouter initialEntries={['/setup/2']}>
        <Routes>
          <Route path="/setup/:stageNumber" element={<OrganizationSetupWizardPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Save Draft/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Save Draft/i }));

    await waitFor(() => {
      expect(onboardingService.saveDraft).toHaveBeenCalledWith(
        2,
        expect.objectContaining({ stage: 2 })
      );
      expect(screen.getByText(/Draft saved at/i)).toBeInTheDocument();
    });
  });

  it('guards against uncompleted stage hopping', async () => {
    vi.mocked(onboardingService.getStatus).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 10,
      organization_name: 'Apex Corp',
      status: 'in_progress',
      current_stage: 2,
      completed_stages: [1],
      completed_at: null,
    });

    render(
      <MemoryRouter initialEntries={['/setup/5']}>
        <Routes>
          <Route path="/setup/:stageNumber" element={<OrganizationSetupWizardPage />} />
          <Route path="/setup/2" element={<div>Redirected to Stage 2</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Redirected to Stage 2')).toBeInTheDocument();
    });
  });
});
