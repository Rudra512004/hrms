import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import {
  BranchProvider,
  useBranchContext,
  BRANCH_STORAGE_KEY,
} from '../BranchContext';
import { Header } from '../../components/Header';
import { organizationService, type Branch } from '../../services/organization';
import * as AuthContextModule from '../AuthContext';

// Mock organizationService
vi.mock('../../services/organization', () => ({
  organizationService: {
    listBranches: vi.fn(),
  },
}));

// Mock NotificationBell to avoid child noise in Header tests
vi.mock('../../components/NotificationBell', () => ({
  NotificationBell: () => <div data-testid="notification-bell" />,
}));

const mockBranches: Branch[] = [
  {
    id: 1,
    organization: 1,
    name: 'Mumbai HQ',
    address: 'Nariman Point',
    latitude: '18.92',
    longitude: '72.82',
    radius: 100,
    is_active: true,
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  },
  {
    id: 2,
    organization: 1,
    name: 'Pune Tech Park',
    address: 'Hinjawadi',
    latitude: '18.59',
    longitude: '73.74',
    radius: 100,
    is_active: true,
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  },
];

describe('C5.2 BranchContext & Header Integration Suite', () => {
  const mockUser = {
    id: 1,
    email: 'admin@company.com',
    firstName: 'Admin',
    lastName: 'User',
    status: 'active',
  };

  const mockAuthContext = {
    user: mockUser,
    roles: ['HR Admin'],
    permissions: ['employee.view', 'branch.view'],
    loading: false,
    error: null,
    hasPermission: vi.fn((perm: string) => ['employee.view', 'branch.view'].includes(perm)),
    refreshAuth: vi.fn(),
    logout: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('auth_token', 'test-valid-token');
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue(mockAuthContext as any);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  // Test Consumer Component for direct context assertion
  const TestConsumer: React.FC = () => {
    const { selectedBranch, branchId, branches, isLoading, error, selectBranch } = useBranchContext();
    return (
      <div>
        <div data-testid="loading-state">{isLoading ? 'loading' : 'idle'}</div>
        <div data-testid="error-state">{error || 'none'}</div>
        <div data-testid="selected-type">{selectedBranch.type}</div>
        <div data-testid="selected-branch-id">{branchId !== null ? String(branchId) : 'null'}</div>
        <div data-testid="branch-count">{branches.length}</div>
        <button data-testid="select-branch-2" onClick={() => selectBranch(2)}>
          Select Branch 2
        </button>
        <button data-testid="select-branch-unauthorized" onClick={() => selectBranch(999)}>
          Select Branch 999
        </button>
        <button data-testid="select-all" onClick={() => selectBranch('all')}>
          Select All
        </button>
      </div>
    );
  };

  // 1. Loads authorized branches
  it('1. loads authorized branches dynamically from organizationService', async () => {
    vi.mocked(organizationService.listBranches).mockResolvedValueOnce(mockBranches);

    render(
      <BranchProvider>
        <TestConsumer />
      </BranchProvider>
    );

    expect(screen.getByTestId('loading-state')).toHaveTextContent('loading');

    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toHaveTextContent('idle');
    });

    expect(organizationService.listBranches).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('branch-count')).toHaveTextContent('2');
  });

  // 2. Displays All Locations & 3. Displays dynamically returned branch names in Header
  it('2 & 3. renders All Locations and dynamic branch names in Header selector', async () => {
    vi.mocked(organizationService.listBranches).mockResolvedValueOnce(mockBranches);

    render(
      <MemoryRouter>
        <BranchProvider>
          <Header toggleSidebar={vi.fn()} isSidebarOpen={true} />
        </BranchProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /select branch location/i })).not.toBeDisabled();
    });

    const select = screen.getByRole('combobox', { name: /select branch location/i }) as HTMLSelectElement;
    expect(select.options.length).toBe(3);
    expect(select.options[0].text).toBe('All Locations');
    expect(select.options[0].value).toBe('all');
    expect(select.options[1].text).toBe('Mumbai HQ');
    expect(select.options[1].value).toBe('1');
    expect(select.options[2].text).toBe('Pune Tech Park');
    expect(select.options[2].value).toBe('2');
  });

  // 4. Defaults safely to All Locations
  it('4. defaults safely to All Locations when no stored branch exists', async () => {
    vi.mocked(organizationService.listBranches).mockResolvedValueOnce(mockBranches);

    render(
      <BranchProvider>
        <TestConsumer />
      </BranchProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toHaveTextContent('idle');
    });

    expect(screen.getByTestId('selected-type')).toHaveTextContent('all');
    expect(screen.getByTestId('selected-branch-id')).toHaveTextContent('null');
  });

  // 5. Selects a specific branch
  it('5. selects a specific branch and updates branchId without page reload', async () => {
    vi.mocked(organizationService.listBranches).mockResolvedValueOnce(mockBranches);

    render(
      <BranchProvider>
        <TestConsumer />
      </BranchProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toHaveTextContent('idle');
    });

    fireEvent.click(screen.getByTestId('select-branch-2'));

    expect(screen.getByTestId('selected-type')).toHaveTextContent('branch');
    expect(screen.getByTestId('selected-branch-id')).toHaveTextContent('2');
  });

  // 6. Persists selection according to chosen persistence strategy
  it('6. persists selection into localStorage using dedicated key', async () => {
    vi.mocked(organizationService.listBranches).mockResolvedValueOnce(mockBranches);

    render(
      <BranchProvider>
        <TestConsumer />
      </BranchProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toHaveTextContent('idle');
    });

    fireEvent.click(screen.getByTestId('select-branch-2'));
    expect(localStorage.getItem(BRANCH_STORAGE_KEY)).toBe('2');

    fireEvent.click(screen.getByTestId('select-all'));
    expect(localStorage.getItem(BRANCH_STORAGE_KEY)).toBe('all');
  });

  // 7. Restores a valid persisted branch
  it('7. restores a valid persisted branch from localStorage', async () => {
    localStorage.setItem(BRANCH_STORAGE_KEY, '2');
    vi.mocked(organizationService.listBranches).mockResolvedValueOnce(mockBranches);

    render(
      <BranchProvider>
        <TestConsumer />
      </BranchProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toHaveTextContent('idle');
    });

    expect(screen.getByTestId('selected-type')).toHaveTextContent('branch');
    expect(screen.getByTestId('selected-branch-id')).toHaveTextContent('2');
  });

  // 8. Rejects/falls back from unauthorized persisted branch
  it('8. rejects unauthorized persisted branch ID and falls back to All Locations', async () => {
    // Attack / tampering simulation: stored ID 999 not in authorized branches
    localStorage.setItem(BRANCH_STORAGE_KEY, '999');
    vi.mocked(organizationService.listBranches).mockResolvedValueOnce(mockBranches);

    render(
      <BranchProvider>
        <TestConsumer />
      </BranchProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toHaveTextContent('idle');
    });

    // Automatically fell back to 'all' and updated storage to 'all'
    expect(screen.getByTestId('selected-type')).toHaveTextContent('all');
    expect(screen.getByTestId('selected-branch-id')).toHaveTextContent('null');
    expect(localStorage.getItem(BRANCH_STORAGE_KEY)).toBe('all');
  });

  // 9. Changing branch does not reload the page
  it('9. changing branch in Header dropdown triggers immediate state reaction without reload', async () => {
    vi.mocked(organizationService.listBranches).mockResolvedValueOnce(mockBranches);

    render(
      <MemoryRouter>
        <BranchProvider>
          <Header toggleSidebar={vi.fn()} isSidebarOpen={true} />
          <TestConsumer />
        </BranchProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /select branch location/i })).not.toBeDisabled();
    });

    const select = screen.getByRole('combobox', { name: /select branch location/i });
    fireEvent.change(select, { target: { value: '1' } });

    expect(screen.getByTestId('selected-type')).toHaveTextContent('branch');
    expect(screen.getByTestId('selected-branch-id')).toHaveTextContent('1');
    expect(localStorage.getItem(BRANCH_STORAGE_KEY)).toBe('1');
  });

  // 10. Branch context does not modify auth permissions
  it('10. branch selection does not mutate or modify auth permissions or user roles', async () => {
    vi.mocked(organizationService.listBranches).mockResolvedValueOnce(mockBranches);

    render(
      <BranchProvider>
        <TestConsumer />
      </BranchProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toHaveTextContent('idle');
    });

    fireEvent.click(screen.getByTestId('select-branch-2'));

    expect(mockAuthContext.permissions).toEqual(['employee.view', 'branch.view']);
    expect(mockAuthContext.roles).toEqual(['HR Admin']);
    expect(mockAuthContext.hasPermission('branch.view')).toBe(true);
  });

  // 11. Branch API 403 is handled gracefully
  it('11. handles branch API 403 gracefully without crash', async () => {
    const error403 = {
      status: 403,
      errorData: { detail: 'You do not have permission to view branches.' },
      message: 'Permission denied',
    };
    vi.mocked(organizationService.listBranches).mockRejectedValueOnce(error403);

    render(
      <BranchProvider>
        <TestConsumer />
      </BranchProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toHaveTextContent('idle');
    });

    expect(screen.getByTestId('error-state')).toHaveTextContent(
      'You do not have permission to view branches.'
    );
    expect(screen.getByTestId('selected-type')).toHaveTextContent('all');
    expect(screen.getByTestId('branch-count')).toHaveTextContent('0');
  });

  // 12. Empty branch response is handled gracefully
  it('12. handles empty branch list response gracefully', async () => {
    vi.mocked(organizationService.listBranches).mockResolvedValueOnce([]);

    render(
      <BranchProvider>
        <TestConsumer />
      </BranchProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toHaveTextContent('idle');
    });

    expect(screen.getByTestId('error-state')).toHaveTextContent('none');
    expect(screen.getByTestId('selected-type')).toHaveTextContent('all');
    expect(screen.getByTestId('branch-count')).toHaveTextContent('0');
  });
});
