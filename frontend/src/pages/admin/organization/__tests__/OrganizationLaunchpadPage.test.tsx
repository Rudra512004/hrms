import '@testing-library/jest-dom/vitest';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { OrganizationLaunchpadPage } from '../OrganizationLaunchpadPage';
import { organizationService } from '../../../../services/organization';
import { onboardingService } from '../../../../services/onboardingService';
import * as AuthContextModule from '../../../../contexts/AuthContext';

vi.mock('../../../../services/organization', () => ({
  organizationService: { createOrganizationSetup: vi.fn() },
}));

vi.mock('../../../../services/onboardingService', () => ({
  onboardingService: {
    getStatus: vi.fn(),
    completeWizard: vi.fn(),
  },
}));

describe('OrganizationLaunchpadPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: { id: '1', email: 'admin@example.com', firstName: 'Admin', lastName: 'User', isSuperuser: true, hasEmployeeProfile: false },
      roles: ['Super Admin'], permissions: [], loading: false, error: null,
      hasPermission: vi.fn(() => true), hasEmployeeProfile: false,
      refreshAuth: vi.fn(), logout: vi.fn(),
    });
    vi.mocked(organizationService.createOrganizationSetup).mockResolvedValue({ id: 1, name: 'Acme', status: 'active' });
    vi.mocked(onboardingService.getStatus).mockResolvedValue({
      onboarding_id: 1,
      organization_id: 1,
      organization_name: 'Acme Corp',
      status: 'in_progress',
      current_stage: 3,
      completed_stages: [1, 2],
      completed_at: null,
      readiness_summary: { score: 60, total_checks: 6, ready_checks: 3 },
    });
  });

  it('provisions the first branch and safe policy defaults atomically', async () => {
    vi.mocked(onboardingService.getStatus).mockRejectedValueOnce(new Error('No session'));
    render(<MemoryRouter><OrganizationLaunchpadPage /></MemoryRouter>);

    fireEvent.change(screen.getByLabelText('Organization name'), { target: { value: 'Acme' } });
    fireEvent.change(screen.getByLabelText('First branch / location'), { target: { value: 'Mumbai HQ' } });
    fireEvent.change(screen.getByLabelText('Address (optional)'), { target: { value: 'Nariman Point' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create organization and first branch' }));

    await waitFor(() => expect(organizationService.createOrganizationSetup).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Acme',
      status: 'active',
      branches: [expect.objectContaining({ name: 'Mumbai HQ', address: 'Nariman Point', radius: 100 })],
      working_calendar: { work_days: '0,1,2,3,4' },
      attendance_policy: expect.objectContaining({ is_office_gps_enabled: true, is_office_ip_enabled: false, is_wfh_enabled: false }),
    })));
  });

  it('renders live in-progress onboarding orchestrator with stage progress and readiness score', async () => {
    render(<MemoryRouter><OrganizationLaunchpadPage /></MemoryRouter>);

    await waitFor(() => {
      expect(screen.getByText(/Onboarding In Progress • Stage 3\/7/i)).toBeInTheDocument();
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
      expect(screen.getByText('60% Ready')).toBeInTheDocument();
    });
    expect(screen.getByRole('link', { name: /Resume Wizard/i })).toHaveAttribute('href', '/setup/3');
  });

  it('allows completing setup and activating organization when stages 1-6 are complete', async () => {
    vi.mocked(onboardingService.getStatus).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 42,
      organization_name: 'Ready Corp',
      status: 'in_progress',
      current_stage: 7,
      completed_stages: [1, 2, 3, 4, 5, 6],
      completed_at: null,
      readiness_summary: { score: 100, total_checks: 6, ready_checks: 6 },
    });
    vi.mocked(onboardingService.completeWizard).mockResolvedValueOnce({
      status: 'completed',
      organization_id: 42,
      completed_at: new Date().toISOString(),
      readiness_score: 100,
      redirect_url: '/dashboard',
    });

    render(<MemoryRouter><OrganizationLaunchpadPage /></MemoryRouter>);

    const activateBtn = await screen.findByRole('button', { name: /Complete Setup & Launch Organization/i });
    expect(activateBtn).toBeInTheDocument();

    fireEvent.click(activateBtn);

    await waitFor(() => {
      expect(onboardingService.completeWizard).toHaveBeenCalledWith(42);
    });
  });

  it('renders operational live state when organization onboarding is already completed', async () => {
    vi.mocked(onboardingService.getStatus).mockResolvedValueOnce({
      onboarding_id: 1,
      organization_id: 99,
      organization_name: 'Live Enterprise',
      status: 'completed',
      current_stage: 7,
      completed_stages: [1, 2, 3, 4, 5, 6, 7],
      completed_at: new Date().toISOString(),
      readiness_summary: { score: 100, total_checks: 6, ready_checks: 6 },
    });

    render(<MemoryRouter><OrganizationLaunchpadPage /></MemoryRouter>);

    await waitFor(() => {
      expect(screen.getByText(/Fully Activated & Operational/i)).toBeInTheDocument();
      expect(screen.getByText('Live Enterprise')).toBeInTheDocument();
    });
    expect(screen.getByRole('link', { name: /Go to HRMS Dashboard/i })).toHaveAttribute('href', '/dashboard');
    expect(screen.getByRole('link', { name: /Theme & Branding/i })).toHaveAttribute('href', '/admin/branding');
  });
});
