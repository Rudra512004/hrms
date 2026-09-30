import '@testing-library/jest-dom/vitest';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { OrganizationLaunchpadPage } from '../OrganizationLaunchpadPage';
import { organizationService } from '../../../../services/organization';
import * as AuthContextModule from '../../../../contexts/AuthContext';

vi.mock('../../../../services/organization', () => ({
  organizationService: { createOrganizationSetup: vi.fn() },
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
  });

  it('provisions the first branch and safe policy defaults atomically', async () => {
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
});
