import '@testing-library/jest-dom/vitest';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Stage6AdminRbac } from '../stages/Stage6AdminRbac';
import { onboardingService } from '../../../services/onboardingService';
import * as AuthContextModule from '../../../contexts/AuthContext';

vi.mock('../../../services/onboardingService', () => ({
  onboardingService: {
    resendStage6Invitation: vi.fn(),
    revokeStage6Invitation: vi.fn(),
  },
}));

describe('Phase 3E — Stage 6 Admin RBAC Component Suite', () => {
  const mockOnBack = vi.fn();
  const mockOnSubmit = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: {
        id: '1',
        email: 'creator@beyondsure.com',
        firstName: 'Alex',
        lastName: 'Creator',
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

  it('renders Option A by default with target administrator profile and requires confirmation checkbox', () => {
    render(
      <Stage6AdminRbac
        isSubmitting={false}
        onBack={mockOnBack}
        onSubmit={mockOnSubmit}
      />
    );

    expect(screen.getByText('Option A: Assign Myself')).toBeInTheDocument();
    expect(screen.getByText('Option B: Invite Administrator')).toBeInTheDocument();
    expect(screen.getByText(/Alex Creator \(creator@beyondsure\.com\)/i)).toBeInTheDocument();

    const submitBtn = screen.getByRole('button', { name: /Continue to Final Review/i });
    expect(submitBtn).toBeEnabled();

    // Uncheck confirmation
    const checkbox = screen.getByLabelText(/I confirm and authorize provisioning/i);
    fireEvent.click(checkbox);
    expect(submitBtn).toBeDisabled();

    // Re-check and submit
    fireEvent.click(checkbox);
    fireEvent.click(submitBtn);
    expect(mockOnSubmit).toHaveBeenCalledWith({ confirm: true });
  });

  it('switches to Option B and allows inviting an administrator by email', () => {
    render(
      <Stage6AdminRbac
        isSubmitting={false}
        onBack={mockOnBack}
        onSubmit={mockOnSubmit}
      />
    );

    // Switch to Option B
    fireEvent.click(screen.getByText('Option B: Invite Administrator'));
    expect(screen.getByLabelText(/First Name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Work Email Address/i)).toBeInTheDocument();

    // Try submitting with own email -> should reject
    fireEvent.change(screen.getByLabelText(/First Name/i), { target: { value: 'Alex' } });
    fireEvent.change(screen.getByLabelText(/Work Email Address/i), { target: { value: 'creator@beyondsure.com' } });
    fireEvent.click(screen.getByRole('button', { name: /Send Invitation & Continue to Final Review/i }));

    expect(screen.getByText(/You cannot invite your own email address/i)).toBeInTheDocument();
    expect(mockOnSubmit).not.toHaveBeenCalled();

    // Provide valid email
    fireEvent.change(screen.getByLabelText(/Work Email Address/i), { target: { value: 'sarah.connor@example.com' } });
    fireEvent.change(screen.getByLabelText(/Last Name/i), { target: { value: 'Connor' } });
    fireEvent.click(screen.getByRole('button', { name: /Send Invitation & Continue to Final Review/i }));

    expect(mockOnSubmit).toHaveBeenCalledWith({
      assignment_type: 'invite',
      first_name: 'Alex',
      last_name: 'Connor',
      email: 'sarah.connor@example.com',
    });
  });

  it('displays pending invitation details with resend and revoke actions', async () => {
    vi.mocked(onboardingService.resendStage6Invitation).mockResolvedValue({
      detail: 'Invitation resent successfully.',
      invitation_id: 42,
      email: 'sarah.connor@example.com',
      status: 'pending',
      email_delivery_status: 'sent',
      resend_count: 1,
      expires_at: '2026-10-20T10:00:00Z',
    });

    vi.mocked(onboardingService.revokeStage6Invitation).mockResolvedValue({
      detail: 'Invitation revoked successfully.',
      invitation_id: 42,
      status: 'revoked',
    });

    window.confirm = vi.fn(() => true);

    render(
      <Stage6AdminRbac
        initialData={{
          assignment_type: 'invite',
          invitation_id: 42,
          invitee_email: 'sarah.connor@example.com',
          invitee_name: 'Sarah Connor',
          invitation_status: 'pending',
          email_delivery_status: 'sent',
          expires_at: '2026-10-20T10:00:00Z',
          resend_count: 0,
        }}
        isSubmitting={false}
        onBack={mockOnBack}
        onSubmit={mockOnSubmit}
      />
    );

    expect(screen.getByText(/Pending Administrator Invitation/i)).toBeInTheDocument();
    expect(screen.getByText(/sarah\.connor@example\.com/i)).toBeInTheDocument();
    expect(screen.getByText('Email Dispatched')).toBeInTheDocument();

    // Test Resend button
    const resendBtn = screen.getByRole('button', { name: /Resend Invitation Email/i });
    fireEvent.click(resendBtn);

    await waitFor(() => {
      expect(onboardingService.resendStage6Invitation).toHaveBeenCalledTimes(1);
      expect(screen.getByText(/Invitation resent successfully to sarah\.connor@example\.com/i)).toBeInTheDocument();
    });

    // Test Revoke button
    const revokeBtn = screen.getByRole('button', { name: /Revoke Invitation/i });
    fireEvent.click(revokeBtn);

    await waitFor(() => {
      expect(onboardingService.revokeStage6Invitation).toHaveBeenCalledTimes(1);
      expect(screen.getByText(/Invitation has been revoked/i)).toBeInTheDocument();
    });
  });
});
