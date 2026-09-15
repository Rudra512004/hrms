import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ActivateAccountPage } from '../ActivateAccountPage';
import { ResetPasswordPage } from '../ResetPasswordPage';
import { authService } from '../../services/auth';

describe('Authentication Activation and Password Reset Routes & Flows', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('ActivateAccountPage', () => {
    it('renders activation form with path parameters and submits successfully', async () => {
      const activateSpy = vi.spyOn(authService, 'activateAccount').mockResolvedValueOnce(
        'Account activated successfully. You may now log in.'
      );

      render(
        <MemoryRouter initialEntries={['/activate/MQ/valid-token-123']}>
          <Routes>
            <Route path="/activate/:uid/:token" element={<ActivateAccountPage />} />
          </Routes>
        </MemoryRouter>
      );

      expect(screen.getByRole('heading', { name: 'Activate Your Account' })).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Enter your password')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Confirm your password')).toBeInTheDocument();

      fireEvent.change(screen.getByPlaceholderText('Enter your password'), {
        target: { value: 'ValidPass123!' },
      });
      fireEvent.change(screen.getByPlaceholderText('Confirm your password'), {
        target: { value: 'ValidPass123!' },
      });

      fireEvent.click(screen.getByRole('button', { name: /activate account/i }));

      await waitFor(() => {
        expect(activateSpy).toHaveBeenCalledWith('MQ', 'valid-token-123', 'ValidPass123!');
        expect(screen.getByText(/account activated successfully/i)).toBeInTheDocument();
      });
    });

    it('renders activation form with query parameters', () => {
      render(
        <MemoryRouter initialEntries={['/activate?uid=QUERY_UID&token=QUERY_TOKEN']}>
          <Routes>
            <Route path="/activate" element={<ActivateAccountPage />} />
          </Routes>
        </MemoryRouter>
      );

      expect(screen.getByRole('heading', { name: 'Activate Your Account' })).toBeInTheDocument();
      expect(screen.queryByText(/missing token parameters/i)).not.toBeInTheDocument();
    });

    it('displays error message when submitting without activation token/uid', async () => {
      render(
        <MemoryRouter initialEntries={['/activate']}>
          <Routes>
            <Route path="/activate" element={<ActivateAccountPage />} />
          </Routes>
        </MemoryRouter>
      );

      fireEvent.change(screen.getByPlaceholderText('Enter your password'), {
        target: { value: 'ValidPass123!' },
      });
      fireEvent.change(screen.getByPlaceholderText('Confirm your password'), {
        target: { value: 'ValidPass123!' },
      });

      fireEvent.click(screen.getByRole('button', { name: /activate account/i }));

      await waitFor(() => {
        expect(screen.getByText(/missing token parameters/i)).toBeInTheDocument();
      });
    });

    it('validates password mismatch before calling API', async () => {
      const activateSpy = vi.spyOn(authService, 'activateAccount');

      render(
        <MemoryRouter initialEntries={['/activate/MQ/token']}>
          <Routes>
            <Route path="/activate/:uid/:token" element={<ActivateAccountPage />} />
          </Routes>
        </MemoryRouter>
      );

      fireEvent.change(screen.getByPlaceholderText('Enter your password'), {
        target: { value: 'PasswordA' },
      });
      fireEvent.change(screen.getByPlaceholderText('Confirm your password'), {
        target: { value: 'PasswordB' },
      });

      fireEvent.click(screen.getByRole('button', { name: /activate account/i }));

      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
      expect(activateSpy).not.toHaveBeenCalled();
    });
  });

  describe('ResetPasswordPage', () => {
    it('renders reset form with path parameters and submits successfully', async () => {
      const resetSpy = vi.spyOn(authService, 'confirmPasswordReset').mockResolvedValueOnce(
        'Password has been reset successfully.'
      );

      render(
        <MemoryRouter initialEntries={['/reset-password/MQ/valid-token-123']}>
          <Routes>
            <Route path="/reset-password/:uid/:token" element={<ResetPasswordPage />} />
          </Routes>
        </MemoryRouter>
      );

      expect(screen.getByRole('heading', { name: 'Reset Password' })).toBeInTheDocument();

      const inputs = screen.getAllByPlaceholderText('********');
      fireEvent.change(inputs[0], {
        target: { value: 'NewSecret123!' },
      });
      fireEvent.change(inputs[1], {
        target: { value: 'NewSecret123!' },
      });

      fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }));

      await waitFor(() => {
        expect(resetSpy).toHaveBeenCalledWith('MQ', 'valid-token-123', 'NewSecret123!', 'NewSecret123!');
        expect(screen.getByText(/password has been reset successfully/i)).toBeInTheDocument();
      });
    });

    it('renders reset form with query parameters', () => {
      render(
        <MemoryRouter initialEntries={['/reset-password?uid=QUERY_UID&token=QUERY_TOKEN']}>
          <Routes>
            <Route path="/reset-password" element={<ResetPasswordPage />} />
          </Routes>
        </MemoryRouter>
      );

      expect(screen.getByRole('heading', { name: 'Reset Password' })).toBeInTheDocument();
      expect(screen.queryByText(/missing token parameters/i)).not.toBeInTheDocument();
    });

    it('displays error message when submitting without reset token/uid', async () => {
      render(
        <MemoryRouter initialEntries={['/reset-password']}>
          <Routes>
            <Route path="/reset-password" element={<ResetPasswordPage />} />
          </Routes>
        </MemoryRouter>
      );

      const inputs = screen.getAllByPlaceholderText('********');
      fireEvent.change(inputs[0], {
        target: { value: 'NewSecret123!' },
      });
      fireEvent.change(inputs[1], {
        target: { value: 'NewSecret123!' },
      });

      fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }));

      await waitFor(() => {
        expect(screen.getByText(/missing token parameters/i)).toBeInTheDocument();
      });
    });
  });
});
