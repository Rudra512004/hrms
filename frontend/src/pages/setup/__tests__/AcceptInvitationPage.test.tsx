import '@testing-library/jest-dom/vitest';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AcceptInvitationPage } from '../AcceptInvitationPage';
import { onboardingService } from '../../../services/onboardingService';
import * as AuthContextModule from '../../../contexts/AuthContext';

vi.mock('../../../services/onboardingService', () => ({
  onboardingService: {
    verifyInvitation: vi.fn(),
    acceptInvitation: vi.fn(),
  },
}));

describe('Phase 3E — AcceptInvitationPage UI Component Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders error state when no token is present in the URL', async () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: null,
      roles: [],
      permissions: [],
      loading: false,
      error: null,
      hasPermission: vi.fn(() => false),
      hasEmployeeProfile: false,
      refreshAuth: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/invite/accept']}>
        <Routes>
          <Route path="/invite/accept" element={<AcceptInvitationPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Invitation Invalid or Expired/i)).toBeInTheDocument();
      expect(screen.getByText(/No invitation token found in the URL/i)).toBeInTheDocument();
    });
  });

  it('verifies token and renders acceptance UI for authenticated user with matching email', async () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: {
        id: '10',
        email: 'sarah.connor@example.com',
        firstName: 'Sarah',
        lastName: 'Connor',
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

    vi.mocked(onboardingService.verifyInvitation).mockResolvedValue({
      valid: true,
      organization_name: 'Apex Global Corp',
      organization_code: 'APEX',
      email: 'sarah.connor@example.com',
      first_name: 'Sarah',
      last_name: 'Connor',
      expires_at: '2026-10-20T10:00:00Z',
    });

    vi.mocked(onboardingService.acceptInvitation).mockResolvedValue({
      detail: 'Invitation accepted successfully.',
      organization_id: 1,
      organization_name: 'Apex Global Corp',
      role: 'super-admin',
      status: 'accepted',
    });

    render(
      <MemoryRouter initialEntries={['/invite/accept?token=valid-secret-token']}>
        <Routes>
          <Route path="/invite/accept" element={<AcceptInvitationPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText(/Apex Global Corp/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Ready to accept administrator privileges/i)).toBeInTheDocument();
      expect(screen.getByText(/Accept Invitation & Join Organization/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/Accept Invitation & Join Organization/i));

    await waitFor(() => {
      expect(onboardingService.acceptInvitation).toHaveBeenCalledWith({ token: 'valid-secret-token' });
      expect(screen.getByRole('heading', { name: /Invitation Accepted!/i })).toBeInTheDocument();
    });
  });

  it('warns authenticated user when signed in under a different email account', async () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: {
        id: '99',
        email: 'other.person@example.com',
        firstName: 'Other',
        lastName: 'Person',
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

    vi.mocked(onboardingService.verifyInvitation).mockResolvedValue({
      valid: true,
      organization_name: 'Apex Global Corp',
      organization_code: 'APEX',
      email: 'sarah.connor@example.com',
      first_name: 'Sarah',
      last_name: 'Connor',
      expires_at: '2026-10-20T10:00:00Z',
    });

    render(
      <MemoryRouter initialEntries={['/invite/accept?token=valid-secret-token']}>
        <Routes>
          <Route path="/invite/accept" element={<AcceptInvitationPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/You are currently signed in as/i)).toBeInTheDocument();
      expect(screen.getByText(/Sign Out & Switch Account/i)).toBeInTheDocument();
    });
  });

  it('allows unauthenticated new user to set password and accept invitation', async () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: null,
      roles: [],
      permissions: [],
      loading: false,
      error: null,
      hasPermission: vi.fn(() => false),
      hasEmployeeProfile: false,
      refreshAuth: vi.fn(),
      logout: vi.fn(),
    });

    vi.mocked(onboardingService.verifyInvitation).mockResolvedValue({
      valid: true,
      organization_name: 'Apex Global Corp',
      organization_code: 'APEX',
      email: 'new.admin@example.com',
      first_name: 'New',
      last_name: 'Admin',
      expires_at: '2026-10-20T10:00:00Z',
    });

    vi.mocked(onboardingService.acceptInvitation).mockResolvedValue({
      detail: 'Account activated and invitation accepted!',
      organization_id: 1,
      organization_name: 'Apex Global Corp',
      role: 'super-admin',
      status: 'accepted',
    });

    render(
      <MemoryRouter initialEntries={['/invite/accept?token=new-user-token']}>
        <Routes>
          <Route path="/invite/accept" element={<AcceptInvitationPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Set Password \(New User\)/i)).toBeInTheDocument();
    });

    const passwordInputs = screen.getAllByPlaceholderText('••••••••');
    fireEvent.change(passwordInputs[0], { target: { value: 'SecurePass123!' } });
    fireEvent.change(passwordInputs[1], { target: { value: 'SecurePass123!' } });

    fireEvent.click(screen.getByRole('button', { name: /Create Password & Accept/i }));

    await waitFor(() => {
      expect(onboardingService.acceptInvitation).toHaveBeenCalledWith({
        token: 'new-user-token',
        password: 'SecurePass123!',
        first_name: 'New',
        last_name: 'Admin',
      });
      expect(screen.getByRole('heading', { name: /Invitation Accepted!/i })).toBeInTheDocument();
    });
  });
});
