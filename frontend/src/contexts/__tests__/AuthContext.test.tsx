import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { AuthProvider, useAuth } from '../AuthContext';
import { authService, type AuthSession } from '../../services/auth';

vi.mock('../../services/auth', () => ({
  authService: {
    getCurrentUser: vi.fn(),
    logout: vi.fn(),
  },
}));

const TestConsumer: React.FC<{ checkPermission?: string }> = ({ checkPermission }) => {
  const { user, roles, permissions, loading, hasPermission, hasEmployeeProfile } = useAuth();
  if (loading) return <div data-testid="loading">Loading...</div>;
  return (
    <div>
      <div data-testid="user-email">{user?.email ?? 'anonymous'}</div>
      <div data-testid="roles">{roles.join(',')}</div>
      <div data-testid="permissions">{permissions.join(',')}</div>
      <div data-testid="has-employee-profile">{String(hasEmployeeProfile)}</div>
      {checkPermission && (
        <div data-testid="perm-result">
          {hasPermission(checkPermission) ? 'GRANTED' : 'DENIED'}
        </div>
      )}
    </div>
  );
};

describe('AuthContext - Permission and Security Remediation Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('throws an error when useAuth is consumed outside AuthProvider', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<TestConsumer />)).toThrow('useAuth must be used within an AuthProvider');
    consoleError.mockRestore();
  });

  it('evaluates hasPermission to false when unauthenticated', async () => {
    vi.mocked(authService.getCurrentUser).mockResolvedValueOnce(null);

    render(
      <AuthProvider>
        <TestConsumer checkPermission="employee.view" />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
    });

    expect(screen.getByTestId('user-email')).toHaveTextContent('anonymous');
    expect(screen.getByTestId('perm-result')).toHaveTextContent('DENIED');
  });

  it('grants permission when isSuperuser is true, regardless of explicit permissions', async () => {
    const superuserSession: AuthSession = {
      user: {
        id: '1',
        email: 'super@company.com',
        firstName: 'Super',
        lastName: 'Admin',
        isSuperuser: true,
        hasEmployeeProfile: false,
      },
      roles: ['Super Admin'],
      permissions: [],
    };
    vi.mocked(authService.getCurrentUser).mockResolvedValueOnce(superuserSession);

    render(
      <AuthProvider>
        <TestConsumer checkPermission="any.arbitrary.permission" />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
    });

    expect(screen.getByTestId('perm-result')).toHaveTextContent('GRANTED');
  });

  it('grants permission when requested permission is in the dynamic permissions array', async () => {
    const standardSession: AuthSession = {
      user: {
        id: '2',
        email: 'hr@company.com',
        firstName: 'HR',
        lastName: 'Manager',
        isSuperuser: false,
        hasEmployeeProfile: true,
      },
      roles: ['HR Manager'],
      permissions: ['employee.view', 'attendance.view_all'],
    };
    vi.mocked(authService.getCurrentUser).mockResolvedValueOnce(standardSession);

    render(
      <AuthProvider>
        <TestConsumer checkPermission="attendance.view_all" />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
    });

    expect(screen.getByTestId('perm-result')).toHaveTextContent('GRANTED');
  });

  it('SECURITY REGRESSION: denies permission when role name is "Super Admin" but isSuperuser is false and permission is absent', async () => {
    // Before Phase 1C remediation, session.roles?.includes('Super Admin') would bypass
    // dynamic permissions and grant access client-side even if backend did not authorize it.
    const spoofedOrMisconfiguredSession: AuthSession = {
      user: {
        id: '3',
        email: 'fake-admin@company.com',
        firstName: 'Not',
        lastName: 'Real',
        isSuperuser: false,
        hasEmployeeProfile: true,
      },
      roles: ['Super Admin'],
      permissions: ['employee.view'], // Does NOT have attendance.manage
    };
    vi.mocked(authService.getCurrentUser).mockResolvedValueOnce(spoofedOrMisconfiguredSession);

    render(
      <AuthProvider>
        <TestConsumer checkPermission="attendance.manage" />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
    });

    expect(screen.getByTestId('perm-result')).toHaveTextContent('DENIED');
  });

  it('correctly reports hasEmployeeProfile from session', async () => {
    const headlessAdminSession: AuthSession = {
      user: {
        id: '4',
        email: 'admin@company.com',
        firstName: 'Org',
        lastName: 'Admin',
        isSuperuser: false,
        hasEmployeeProfile: false,
      },
      roles: ['Org Admin'],
      permissions: ['organization.manage'],
    };
    vi.mocked(authService.getCurrentUser).mockResolvedValueOnce(headlessAdminSession);

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
    });

    expect(screen.getByTestId('has-employee-profile')).toHaveTextContent('false');
  });
});
