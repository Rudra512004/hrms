import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { DashboardPage } from '../DashboardPage';
import { RegisterOrganizationPage } from '../RegisterOrganizationPage';
import { ActivateAccountPage } from '../ActivateAccountPage';
import * as AuthContext from '../../contexts/AuthContext';
import { authService } from '../../services/auth';


// Mock context provider hook
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

vi.mock('../../services/dashboard', () => ({
  dashboardService: {
    getOverview: vi.fn().mockResolvedValue({}),
  },
}));

describe('Phase 10: SaaS Organization Onboarding Flow', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('1. Dashboard Onboarding Redirect', () => {
    it('redirects to launchpad if onboarding is incomplete (canCreateOrganization = true)', () => {
      vi.mocked(AuthContext.useAuth).mockReturnValue({
        user: {
          id: 1,
          email: 'owner@test.com',
          firstName: 'Owner',
          lastName: 'User',
          isSuperuser: false,
          canCreateOrganization: true,
        },
        hasEmployeeProfile: false,
        loading: false,
        error: null,
      } as any);

      render(
        <MemoryRouter initialEntries={['/dashboard']}>
          <Routes>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/admin/organization-launchpad" element={<div data-testid="launchpad" />} />
          </Routes>
        </MemoryRouter>
      );

      // It should navigate away from dashboard and hit the launchpad dummy element
      expect(screen.getByTestId('launchpad')).toBeInTheDocument();
      expect(screen.queryByText(/Check In/i)).not.toBeInTheDocument();
    });

    it('stays on dashboard if onboarding is complete (canCreateOrganization = false)', async () => {
      vi.mocked(AuthContext.useAuth).mockReturnValue({
        user: {
          id: 1,
          email: 'owner@test.com',
          firstName: 'Owner',
          lastName: 'User',
          isSuperuser: false,
          canCreateOrganization: false,
        },
        hasEmployeeProfile: true,
        loading: false,
        error: null,
      } as any);

      render(
        <MemoryRouter initialEntries={['/dashboard']}>
          <Routes>
            <Route path="/dashboard" element={<DashboardPage />} />
          </Routes>
        </MemoryRouter>
      );

      expect(screen.getByText(/Owner/)).toBeInTheDocument();
      // It should render dashboard skeleton/layout
      expect(screen.getByText(/BeyondSure HRMS Workspace/i)).toBeInTheDocument();
    });
  });

  describe('2. Registration Page UX', () => {
    it('displays the correct copy regarding password creation (happens during activation)', () => {
      render(
        <MemoryRouter>
          <RegisterOrganizationPage />
        </MemoryRouter>
      );
      
      expect(screen.getByText(/email to activate your account and set a password/i)).toBeInTheDocument();
    });
  });

  describe('3. Activation Page Validations', () => {
    it('prevents submission with weak password', async () => {
      render(
        <MemoryRouter initialEntries={['/activate/MQ/token']}>
          <Routes>
            <Route path="/activate/:uid/:token" element={<ActivateAccountPage />} />
          </Routes>
        </MemoryRouter>
      );

      const passInput = screen.getByPlaceholderText('Enter your password');
      const confirmInput = screen.getByPlaceholderText('Confirm your password');
      const submitBtn = screen.getByRole('button', { name: /activate account/i });

      // Missing numbers
      fireEvent.change(passInput, { target: { value: 'Password' } });
      fireEvent.change(confirmInput, { target: { value: 'Password' } });
      
      expect(submitBtn).toBeDisabled();
      
      // Missing letters
      fireEvent.change(passInput, { target: { value: '12345678' } });
      fireEvent.change(confirmInput, { target: { value: '12345678' } });
      
      expect(submitBtn).toBeDisabled();
      
      // Passwords do not match
      fireEvent.change(passInput, { target: { value: 'ValidPass1' } });
      fireEvent.change(confirmInput, { target: { value: 'ValidPass2' } });
      
      expect(submitBtn).toBeDisabled();

      // Valid
      fireEvent.change(passInput, { target: { value: 'ValidPass1' } });
      fireEvent.change(confirmInput, { target: { value: 'ValidPass1' } });
      
      expect(submitBtn).not.toBeDisabled();
    });
    
    it('handles invalid token from API', async () => {
      vi.spyOn(authService, 'activateAccount').mockRejectedValueOnce(
        new Error('Invalid activation token')
      );

      render(
        <MemoryRouter initialEntries={['/activate/MQ/badtoken']}>
          <Routes>
            <Route path="/activate/:uid/:token" element={<ActivateAccountPage />} />
          </Routes>
        </MemoryRouter>
      );

      fireEvent.change(screen.getByPlaceholderText('Enter your password'), { target: { value: 'ValidPass1' } });
      fireEvent.change(screen.getByPlaceholderText('Confirm your password'), { target: { value: 'ValidPass1' } });
      
      fireEvent.click(screen.getByRole('button', { name: /activate account/i }));

      await waitFor(() => {
        expect(screen.getByText(/Invalid activation token/i)).toBeInTheDocument();
      });
    });
  });
});
