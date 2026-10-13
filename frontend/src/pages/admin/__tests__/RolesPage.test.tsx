import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { RolesPage } from '../RolesPage';
import { authorizationManagementService } from '../../../services/authorizationManagement';
import type { Role } from '../../../services/authorizationManagement';

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
    listRoles: vi.fn(),
    createRole: vi.fn(),
    updateRole: vi.fn(),
    deleteRole: vi.fn(),
  },
}));

describe('RolesPage (Phase 2E Roles Overview)', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  const mockRoles: Role[] = [
    {
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
      permission_ids: [1, 2, 3],
    },
    {
      id: 2,
      organization: 1,
      name: 'HR Manager',
      slug: 'hr-manager',
      description: 'HR operations and employee management',
      badge: null,
      users_count: 1,
      permissions_count: 112,
      effective_permissions_count: 112,
      can_delete: false,
      is_system: true,
      is_active: true,
      permission_ids: [1, 2],
    },
    {
      id: 3,
      organization: 1,
      name: 'team-lead',
      slug: 'team-lead',
      description: 'Team lead role with custom permissions',
      badge: null,
      users_count: 0,
      permissions_count: 31,
      effective_permissions_count: 31,
      can_delete: true,
      is_system: false,
      is_active: true,
      permission_ids: [1],
    },
  ];

  it('1. Renders 3-column roles card grid with metrics and badges matching reference', async () => {
    vi.mocked(authorizationManagementService.listRoles).mockResolvedValueOnce(mockRoles);

    render(
      <MemoryRouter>
        <RolesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Roles & Permissions')).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Super Admin' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'HR Manager' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'team-lead' })).toBeInTheDocument();
    });

    // Check Full access badge for Super Admin
    expect(screen.getByText('Full access')).toBeInTheDocument();

    // Check USERS count and PERMISSIONS count
    expect(screen.getByTestId('users-count-1')).toHaveTextContent('3');
    expect(screen.getByTestId('permissions-count-1')).toHaveTextContent('127');

    expect(screen.getByTestId('users-count-2')).toHaveTextContent('1');
    expect(screen.getByTestId('permissions-count-2')).toHaveTextContent('112');

    expect(screen.getByTestId('users-count-3')).toHaveTextContent('0');
    expect(screen.getByTestId('permissions-count-3')).toHaveTextContent('31');
  });

  it('2. Navigates to permission editor when "Edit permissions" is clicked', async () => {
    vi.mocked(authorizationManagementService.listRoles).mockResolvedValueOnce(mockRoles);

    render(
      <MemoryRouter>
        <RolesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('role-card-1')).toBeInTheDocument();
    });

    const card1 = screen.getByTestId('role-card-1');
    const editPermBtn = within(card1).getByRole('button', { name: /edit permissions/i });
    fireEvent.click(editPermBtn);

    expect(mockNavigate).toHaveBeenCalledWith('/admin/roles/1/permissions');
  });

  it('3. Renders Delete button only on eligible custom roles where can_delete is true', async () => {
    vi.mocked(authorizationManagementService.listRoles).mockResolvedValueOnce(mockRoles);

    render(
      <MemoryRouter>
        <RolesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('role-card-3')).toBeInTheDocument();
    });

    // Super Admin cannot be deleted
    const card1 = screen.getByTestId('role-card-1');
    expect(within(card1).queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();

    // HR Manager has assigned users, cannot be deleted
    const card2 = screen.getByTestId('role-card-2');
    expect(within(card2).queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();

    // team-lead has can_delete: true
    const card3 = screen.getByTestId('role-card-3');
    const deleteBtn = within(card3).getByRole('button', { name: /delete/i });
    expect(deleteBtn).toBeInTheDocument();
    expect(deleteBtn).toHaveTextContent(/Delete/);
  });

  it('4. Handles role creation flow and displays server validation errors', async () => {
    vi.mocked(authorizationManagementService.listRoles).mockResolvedValueOnce(mockRoles);

    render(
      <MemoryRouter>
        <RolesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add role/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /add role/i }));
    expect(screen.getByText('New Role')).toBeInTheDocument();

    // Fill in form
    const nameInput = screen.getByLabelText(/Role Name/);
    const descInput = screen.getByLabelText(/Description/);

    fireEvent.change(nameInput, { target: { value: 'Shift Supervisor' } });
    fireEvent.change(descInput, { target: { value: 'Floor shift supervisor' } });

    // Mock API error on duplicate name
    vi.mocked(authorizationManagementService.createRole).mockRejectedValueOnce({
      errorData: { name: ['A role with this name already exists in your organization.'] },
    });

    const modal = screen.getByRole('dialog');
    const submitBtn = within(modal).getByRole('button', { name: /create role/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('A role with this name already exists in your organization.')).toBeInTheDocument();
    });

    // Now mock success
    vi.mocked(authorizationManagementService.createRole).mockResolvedValueOnce({
      id: 4,
      organization: 1,
      name: 'Shift Supervisor',
      slug: 'shift-supervisor',
      description: 'Floor shift supervisor',
      badge: null,
      users_count: 0,
      permissions_count: 0,
      can_delete: true,
      is_system: false,
      is_active: true,
      permission_ids: [],
    });
    vi.mocked(authorizationManagementService.listRoles).mockResolvedValueOnce([
      ...mockRoles,
      {
        id: 4,
        organization: 1,
        name: 'Shift Supervisor',
        slug: 'shift-supervisor',
        description: 'Floor shift supervisor',
        badge: null,
        users_count: 0,
        permissions_count: 0,
        can_delete: true,
        is_system: false,
        is_active: true,
        permission_ids: [],
      },
    ]);

    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(authorizationManagementService.createRole).toHaveBeenCalledWith({
        name: 'Shift Supervisor',
        description: 'Floor shift supervisor',
      });
    });
  });

  it('5. Handles role deletion flow and surfaces active users block', async () => {
    vi.mocked(authorizationManagementService.listRoles).mockResolvedValueOnce(mockRoles);

    render(
      <MemoryRouter>
        <RolesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('role-card-3')).toBeInTheDocument();
    });

    // Click delete on team-lead card
    const card3 = screen.getByTestId('role-card-3');
    fireEvent.click(within(card3).getByRole('button', { name: /delete/i }));

    const deleteModal = screen.getByRole('dialog');
    expect(within(deleteModal).getByText(/Are you sure you want to delete role/)).toBeInTheDocument();

    // Mock rejection if server says active users assigned
    vi.mocked(authorizationManagementService.deleteRole).mockRejectedValueOnce({
      errorData: { detail: 'Cannot delete role with active user assignments. Reassign users first.' },
    });

    const confirmDeleteBtn = within(deleteModal).getByRole('button', { name: /delete role/i });
    fireEvent.click(confirmDeleteBtn);

    await waitFor(() => {
      expect(screen.getByText('Cannot delete role with active user assignments. Reassign users first.')).toBeInTheDocument();
    });

    // Now mock clean delete
    vi.mocked(authorizationManagementService.deleteRole).mockResolvedValueOnce();
    vi.mocked(authorizationManagementService.listRoles).mockResolvedValueOnce(mockRoles.filter(r => r.id !== 3));

    fireEvent.click(confirmDeleteBtn);

    await waitFor(() => {
      expect(authorizationManagementService.deleteRole).toHaveBeenCalledWith(3);
    });
  });

  it('6. Displays loading state and empty state appropriately', async () => {
    vi.mocked(authorizationManagementService.listRoles).mockResolvedValueOnce([]);

    render(
      <MemoryRouter>
        <RolesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('No roles configured')).toBeInTheDocument();
    });
  });

  it('7. Displays error banner when listing roles fails', async () => {
    vi.mocked(authorizationManagementService.listRoles).mockRejectedValueOnce({
      response: { status: 403 },
    });

    render(
      <MemoryRouter>
        <RolesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('You do not have permission to view roles.')).toBeInTheDocument();
    });
  });
});
