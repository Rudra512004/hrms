import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { RolePermissionsPage } from '../RolePermissionsPage';
import { authorizationManagementService } from '../../../services/authorizationManagement';
import type { Role, PermissionMatrixResponse } from '../../../services/authorizationManagement';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('../../../services/authorizationManagement', () => ({
  authorizationManagementService: {
    getRole: vi.fn(),
    getPermissionMatrix: vi.fn(),
    updateRolePermissions: vi.fn(),
  },
}));

describe('RolePermissionsPage (Phase 2E Permission Editor)', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  const mockMatrix: PermissionMatrixResponse = {
    total_visible_count: 5,
    columns: {
      '1': [
        {
          category: 'Dashboard',
          actions: [
            {
              id: 1,
              codename: 'dashboard.view',
              label: 'View dashboard',
              name: 'View Dashboard',
              description: 'Operational metrics',
              column: 1,
              category: 'Dashboard',
            },
            {
              id: 2,
              codename: 'dashboard.view_org_stats',
              label: 'View organisation-wide statistics',
              name: 'View Organisation-wide Statistics',
              description: 'Company charts',
              column: 1,
              category: 'Dashboard',
            },
          ],
        },
      ],
      '2': [
        {
          category: 'Attendance',
          actions: [
            {
              id: 39,
              codename: 'attendance.clock_in_out',
              label: 'Check in and check out',
              name: 'Check in and check out',
              description: 'Clock in out',
              column: 2,
              category: 'Attendance',
            },
            {
              id: 40,
              codename: 'attendance.view_team',
              label: 'View team attendance',
              name: 'View Team Attendance',
              description: 'Team attendance records',
              column: 2,
              category: 'Attendance',
            },
          ],
        },
      ],
      '3': [
        {
          category: 'Payslips',
          actions: [
            {
              id: 90,
              codename: 'payslip.view',
              label: 'View own payslips',
              name: 'View Own Payslips',
              description: 'Self payslips',
              column: 3,
              category: 'Payslips',
            },
          ],
        },
      ],
    },
  };

  const mockCustomRole: Role = {
    id: 8,
    organization: 1,
    name: 'Shift Supervisor',
    slug: 'shift-supervisor',
    description: 'Floor shift supervisor',
    badge: null,
    users_count: 0,
    permissions_count: 2,
    effective_permissions_count: 2,
    can_delete: true,
    is_system: false,
    is_active: true,
    permission_ids: [1, 39],
  };

  const mockSuperAdminRole: Role = {
    id: 1,
    organization: 1,
    name: 'Super Admin',
    slug: 'super-admin',
    description: 'Full access to all system modules',
    badge: 'Full access',
    users_count: 3,
    permissions_count: 127,
    effective_permissions_count: 144,
    can_delete: false,
    is_system: true,
    is_active: true,
    permission_ids: [1, 2, 39, 40, 90],
  };

  it('1. Renders 3-column permission matrix with categories, counters, and checkboxes', async () => {
    vi.mocked(authorizationManagementService.getRole).mockResolvedValueOnce(mockCustomRole);
    vi.mocked(authorizationManagementService.getPermissionMatrix).mockResolvedValueOnce(mockMatrix);

    render(
      <MemoryRouter initialEntries={['/admin/roles/8/permissions']}>
        <Routes>
          <Route path="/admin/roles/:roleId/permissions" element={<RolePermissionsPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('role-editor-title')).toHaveTextContent('Shift Supervisor');
      expect(screen.getByText('Permissions granted by the shift-supervisor role')).toBeInTheDocument();
    });

    // Check categories
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Attendance')).toBeInTheDocument();
    expect(screen.getByText('Payslips')).toBeInTheDocument();

    // Check counters: Dashboard has 1/2 checked (id: 1 checked, id: 2 unchecked)
    expect(screen.getByTestId('count-dashboard')).toHaveTextContent('1/2');
    expect(screen.getByTestId('count-attendance')).toHaveTextContent('1/2');
    expect(screen.getByTestId('count-payslips')).toHaveTextContent('0/1');

    // Check action checkbox labels
    expect(screen.getByText('View dashboard')).toBeInTheDocument();
    expect(screen.getByText('View organisation-wide statistics')).toBeInTheDocument();
    expect(screen.getByText('Check in and check out')).toBeInTheDocument();
    expect(screen.getByText('View own payslips')).toBeInTheDocument();

    // Check initial checked states
    const dashboardCheck = screen.getByTestId('action-checkbox-dashboard.view') as HTMLInputElement;
    const statsCheck = screen.getByTestId('action-checkbox-dashboard.view_org_stats') as HTMLInputElement;
    expect(dashboardCheck.checked).toBe(true);
    expect(statsCheck.checked).toBe(false);
  });

  it('2. Super Admin role displays non-narrowing banner, disables checkboxes and save button', async () => {
    vi.mocked(authorizationManagementService.getRole).mockResolvedValueOnce(mockSuperAdminRole);
    vi.mocked(authorizationManagementService.getPermissionMatrix).mockResolvedValueOnce(mockMatrix);

    render(
      <MemoryRouter initialEntries={['/admin/roles/1/permissions']}>
        <Routes>
          <Route path="/admin/roles/:roleId/permissions" element={<RolePermissionsPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('super-admin-banner')).toBeInTheDocument();
      expect(screen.getByText(/The super admin role always holds every permission/)).toBeInTheDocument();
    });

    // Check that checkboxes are disabled
    const dashboardCheck = screen.getByTestId('action-checkbox-dashboard.view') as HTMLInputElement;
    expect(dashboardCheck.disabled).toBe(true);

    // Check that save button is disabled
    const saveBtn = screen.getByRole('button', { name: /save permissions/i });
    expect(saveBtn).toBeDisabled();
  });

  it('3. Toggles permissions and performs atomic full-replacement save', async () => {
    vi.mocked(authorizationManagementService.getRole).mockResolvedValueOnce(mockCustomRole);
    vi.mocked(authorizationManagementService.getPermissionMatrix).mockResolvedValueOnce(mockMatrix);

    render(
      <MemoryRouter initialEntries={['/admin/roles/8/permissions']}>
        <Routes>
          <Route path="/admin/roles/:roleId/permissions" element={<RolePermissionsPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('count-dashboard')).toHaveTextContent('1/2');
    });

    // Toggle id: 2 ('dashboard.view_org_stats') to ON
    const statsCheck = screen.getByTestId('action-checkbox-dashboard.view_org_stats');
    fireEvent.click(statsCheck);

    // Counter should update to 2/2
    expect(screen.getByTestId('count-dashboard')).toHaveTextContent('2/2');

    // Mock API save response
    vi.mocked(authorizationManagementService.updateRolePermissions).mockResolvedValueOnce({
      role_id: 8,
      role_name: 'Shift Supervisor',
      permissions_count: 3,
      effective_permissions_count: 3,
      updated_at: '2026-10-12T12:00:00Z',
    });

    const saveBtn = screen.getByRole('button', { name: /save permissions/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      // Must send full replacement array: [1, 39, 2]
      expect(authorizationManagementService.updateRolePermissions).toHaveBeenCalledWith(
        8,
        expect.arrayContaining([1, 2, 39])
      );
      expect(screen.getByText(/Permissions updated successfully/)).toBeInTheDocument();
    });
  });

  it('4. Preserves unsaved selections upon save failure and surfaces error banner', async () => {
    vi.mocked(authorizationManagementService.getRole).mockResolvedValueOnce(mockCustomRole);
    vi.mocked(authorizationManagementService.getPermissionMatrix).mockResolvedValueOnce(mockMatrix);

    render(
      <MemoryRouter initialEntries={['/admin/roles/8/permissions']}>
        <Routes>
          <Route path="/admin/roles/:roleId/permissions" element={<RolePermissionsPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('count-dashboard')).toHaveTextContent('1/2');
    });

    // Toggle id: 2 to ON
    fireEvent.click(screen.getByTestId('action-checkbox-dashboard.view_org_stats'));
    expect(screen.getByTestId('count-dashboard')).toHaveTextContent('2/2');

    // Mock save rejection
    vi.mocked(authorizationManagementService.updateRolePermissions).mockRejectedValueOnce({
      errorData: { detail: 'Inactive permissions cannot be assigned: [2]' },
    });

    const saveBtn = screen.getByRole('button', { name: /save permissions/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.getByText('Inactive permissions cannot be assigned: [2]')).toBeInTheDocument();
    });

    // Selections should remain intact (2/2 still checked, not reset)
    expect(screen.getByTestId('count-dashboard')).toHaveTextContent('2/2');
  });

  it('5. Handles 404 role not found', async () => {
    vi.mocked(authorizationManagementService.getRole).mockRejectedValueOnce({
      response: { status: 404 },
    });
    vi.mocked(authorizationManagementService.getPermissionMatrix).mockResolvedValueOnce(mockMatrix);

    render(
      <MemoryRouter initialEntries={['/admin/roles/999/permissions']}>
        <Routes>
          <Route path="/admin/roles/:roleId/permissions" element={<RolePermissionsPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Role not found or you do not have permission to access it.')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /back to roles/i })).toBeInTheDocument();
    });
  });
});
