import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { OrganizationsPage } from '../OrganizationsPage';
import { organizationService, type Organization } from '../../../../services/organization';
import * as AuthContextModule from '../../../../contexts/AuthContext';

vi.mock('../../../../services/organization', () => ({
  organizationService: {
    listOrganizations: vi.fn(),
    createOrganization: vi.fn(),
    updateOrganization: vi.fn(),
    deleteOrganization: vi.fn(),
  },
}));

const mockOrganizations: Organization[] = [
  {
    id: 1,
    name: 'BeyondSure Corp',
    status: 'active',
    is_active: true,
  },
  {
    id: 2,
    name: 'Legacy Subsidiary',
    status: 'inactive',
    is_active: false,
  },
];

describe('OrganizationsPage — No Description & Status Alignment', () => {
  let mockAuthContext: any;

  beforeEach(() => {
    vi.clearAllMocks();

    mockAuthContext = {
      user: { id: 1, email: 'admin@beyondsure.com' },
      hasPermission: vi.fn((p: string) => ['organization.view', 'organization.manage'].includes(p)),
      loading: false,
      error: null,
      refreshAuth: vi.fn(),
      logout: vi.fn(),
    };

    vi.spyOn(AuthContextModule, 'useAuth').mockImplementation(() => mockAuthContext);
    vi.mocked(organizationService.listOrganizations).mockResolvedValue(mockOrganizations);
  });

  const renderComponent = () =>
    render(
      <MemoryRouter>
        <OrganizationsPage />
      </MemoryRouter>
    );

  it('1. Renders organization list with Name and Status, WITHOUT Description column', async () => {
    renderComponent();

    expect(await screen.findByText('BeyondSure Corp')).toBeInTheDocument();
    expect(screen.getByText('Legacy Subsidiary')).toBeInTheDocument();

    // Verify table headers contain Name and Status, but NOT Description
    const headers = screen.getAllByRole('columnheader').map(th => th.textContent);
    expect(headers).toContain('Name');
    expect(headers).toContain('Status');
    expect(headers).not.toContain('Description');
  });

  it('2. Add Organization modal contains Name and Status, but NO Description field', async () => {
    renderComponent();

    const addBtn = await screen.findByTestId('add-organization-btn');
    fireEvent.click(addBtn);

    expect(await screen.findByTestId('organization-modal')).toBeInTheDocument();
    expect(screen.getByTestId('org-name-input')).toBeInTheDocument();
    expect(screen.getByTestId('org-status-select')).toBeInTheDocument();

    // Verify no Description label or input exists
    expect(screen.queryByLabelText(/description/i)).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/description/i)).not.toBeInTheDocument();
  });

  it('3. Successfully creates an organization with Name and Status', async () => {
    vi.mocked(organizationService.createOrganization).mockResolvedValue({
      id: 3,
      name: 'Alpha Holdings',
      status: 'active',
      is_active: true,
    });

    renderComponent();

    fireEvent.click(await screen.findByTestId('add-organization-btn'));

    const nameInput = screen.getByTestId('org-name-input');
    const statusSelect = screen.getByTestId('org-status-select');
    const saveBtn = screen.getByTestId('org-save-btn');

    fireEvent.change(nameInput, { target: { value: 'Alpha Holdings' } });
    fireEvent.change(statusSelect, { target: { value: 'active' } });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(organizationService.createOrganization).toHaveBeenCalledWith({
        name: 'Alpha Holdings',
        status: 'active',
      });
    });
  });

  it('4. Successfully edits an organization Name and Status', async () => {
    vi.mocked(organizationService.updateOrganization).mockResolvedValue({
      id: 1,
      name: 'BeyondSure Global',
      status: 'active',
      is_active: true,
    });

    renderComponent();

    const editBtn = await screen.findByTestId('edit-org-1');
    fireEvent.click(editBtn);

    expect(await screen.findByText('Edit Organization')).toBeInTheDocument();

    // Verify no Description input in Edit modal either
    expect(screen.queryByLabelText(/description/i)).not.toBeInTheDocument();

    const nameInput = screen.getByTestId('org-name-input');
    fireEvent.change(nameInput, { target: { value: 'BeyondSure Global' } });

    const saveBtn = screen.getByTestId('org-save-btn');
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(organizationService.updateOrganization).toHaveBeenCalledWith(1, {
        name: 'BeyondSure Global',
        status: 'active',
      });
    });
  });

  it('5. Permission gating: hides Add Organization and Action buttons when lacking organization.manage', async () => {
    mockAuthContext.hasPermission.mockImplementation((p: string) => p === 'organization.view');

    renderComponent();

    await screen.findByText('BeyondSure Corp');
    expect(screen.queryByTestId('add-organization-btn')).not.toBeInTheDocument();
    expect(screen.queryByTestId('edit-org-1')).not.toBeInTheDocument();
  });
});
