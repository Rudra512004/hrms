import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AttendancePolicyPage } from '../AttendancePolicyPage';
import { attendancePolicyService, type AttendancePolicy } from '../../../services/attendancePolicy';
import * as AuthContextModule from '../../../contexts/AuthContext';
import * as BranchContextModule from '../../../contexts/BranchContext';

vi.mock('../../../services/attendancePolicy', () => ({
  attendancePolicyService: {
    getAttendancePolicy: vi.fn(),
    updateAttendancePolicy: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number;
    errorData: any;
    constructor(response: any, errorData: any) {
      super(errorData?.detail || 'API Error');
      this.status = response?.status || 500;
      this.errorData = errorData;
    }
  },
}));

const mockPolicy: AttendancePolicy = {
  id: 1,
  branch: 1,
  is_office_gps_enabled: true,
  is_office_ip_enabled: false,
  is_wfh_enabled: false,
  wfh_bypasses_office_restrictions: true,
  created_at: '2026-01-01',
  updated_at: '2026-01-01',
};

describe('AttendancePolicyPage (C5.5.4)', () => {
  let mockAuthContextValue: any;
  let mockBranchContextValue: any;

  beforeEach(() => {
    mockAuthContextValue = {
      user: { id: 1, email: 'admin@beyondsure.com', role: 'Branch Manager' },
      isAuthenticated: true,
      hasPermission: vi.fn((p: string) => ['branch.view', 'branch.manage'].includes(p)),
      loading: false,
      error: null,
      refreshAuth: vi.fn(),
      logout: vi.fn(),
    };

    mockBranchContextValue = {
      selectedBranch: { type: 'branch', branchId: 1, branch: { id: 1, name: 'Mumbai HQ' } },
      branchId: 1,
      branches: [
        { id: 1, organization: 1, name: 'Mumbai HQ', address: 'Nariman Point', is_active: true },
      ],
      isLoading: false,
      error: null,
      selectBranch: vi.fn(),
      refreshBranches: vi.fn(),
    };

    vi.spyOn(AuthContextModule, 'useAuth').mockImplementation(() => mockAuthContextValue);
    vi.spyOn(BranchContextModule, 'useBranchContext').mockImplementation(() => mockBranchContextValue);

    (attendancePolicyService.getAttendancePolicy as any).mockResolvedValue(mockPolicy);
    (attendancePolicyService.updateAttendancePolicy as any).mockResolvedValue({
      ...mockPolicy,
      is_office_ip_enabled: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('1. When All Locations is selected, prompts to select a branch and hides form', async () => {
    mockBranchContextValue.branchId = null;
    mockBranchContextValue.selectedBranch = { type: 'all' };

    render(
      <MemoryRouter>
        <AttendancePolicyPage />
      </MemoryRouter>
    );

    expect(
      screen.getByText(/Select a branch from the header to manage this configuration/i)
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/Require Office GPS Geofencing/i)).toBeNull();
  });

  it('2. User with branch.view can view policy settings', async () => {
    render(
      <MemoryRouter>
        <AttendancePolicyPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Branch: Mumbai HQ/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Require Office GPS Geofencing/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Require Office Network IP Verification/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Allow Work From Home \(WFH\)/i)).toBeInTheDocument();
    });

    expect(screen.getByLabelText(/Require Office GPS Geofencing/i)).toBeChecked();
    expect(screen.getByLabelText(/Require Office Network IP Verification/i)).not.toBeChecked();
  });

  it('3. User without branch.manage has read-only controls and cannot save', async () => {
    mockAuthContextValue.hasPermission = vi.fn((p: string) => p === 'branch.view');

    render(
      <MemoryRouter>
        <AttendancePolicyPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/You have read-only access \(branch.view\)/i)).toBeInTheDocument();
    });

    // Checkboxes should be disabled
    expect(screen.getByLabelText(/Require Office GPS Geofencing/i)).toBeDisabled();
    expect(screen.getByLabelText(/Require Office Network IP Verification/i)).toBeDisabled();

    // Save button should not be present
    expect(screen.queryByRole('button', { name: /save attendance policy/i })).toBeNull();
  });

  it('4. User with branch.manage can toggle settings and save updated policy', async () => {
    render(
      <MemoryRouter>
        <AttendancePolicyPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /save attendance policy/i })).toBeInTheDocument();
    });

    const ipCheckbox = screen.getByLabelText(/Require Office Network IP Verification/i);
    fireEvent.click(ipCheckbox);

    const saveBtn = screen.getByRole('button', { name: /save attendance policy/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(attendancePolicyService.updateAttendancePolicy).toHaveBeenCalledWith(1, {
        is_office_gps_enabled: true,
        is_office_ip_enabled: true,
        is_wfh_enabled: false,
        wfh_bypasses_office_restrictions: true,
      });
    });
  });

  it('5. Surfaces backend 403 error properly', async () => {
    (attendancePolicyService.getAttendancePolicy as any).mockRejectedValue({
      status: 403,
      errorData: { detail: '403 Forbidden: You do not have permission to view attendance policy.' },
    });

    render(
      <MemoryRouter>
        <AttendancePolicyPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText(/You do not have permission to view attendance policy/i)
      ).toBeInTheDocument();
    });
  });
});
