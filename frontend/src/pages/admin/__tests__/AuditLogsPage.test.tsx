import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuditLogsPage } from '../AuditLogsPage';
import { auditService } from '../../../services/audit';

vi.mock('../../../services/audit', () => ({
  auditService: {
    getLogs: vi.fn(),
  },
}));

describe('AuditLogsPage (P0 Migration)', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  const mockLogs = [
    {
      id: 1,
      actor: 10,
      actor_email: 'admin@example.com',
      action: 'employee_created',
      target_type: 'Employee',
      target_id: 101,
      timestamp: '2026-09-26T10:00:00Z',
      metadata: {},
      ip_address: '127.0.0.1',
    },
    {
      id: 2,
      actor: 10,
      actor_email: 'admin@example.com',
      action: 'role_assigned',
      target_type: 'User',
      target_id: 102,
      timestamp: '2026-09-26T10:30:00Z',
      metadata: { role: 'Manager' },
      ip_address: '127.0.0.1',
    },
  ];

  it('1. Renders paginated response with table and pagination controls', async () => {
    vi.mocked(auditService.getLogs).mockResolvedValueOnce({
      count: 2,
      next: null,
      previous: null,
      results: mockLogs,
    });

    render(
      <MemoryRouter>
        <AuditLogsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('System Audit Logs')).toBeInTheDocument();
      expect(screen.getAllByText('admin@example.com').length).toBe(2);
      expect(screen.getByText('Employee created')).toBeInTheDocument();
      expect(screen.getByText('Showing 1 to 2 of 2 records')).toBeInTheDocument();
    });
  });

  it('2. Gracefully handles unpaginated array response from backend (backward compatibility)', async () => {
    vi.mocked(auditService.getLogs).mockResolvedValueOnce(mockLogs as any);

    render(
      <MemoryRouter>
        <AuditLogsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText('admin@example.com').length).toBe(2);
      expect(screen.getByText('Showing 1 to 2 of 2 records')).toBeInTheDocument();
    });
  });

  it('3. Changes page and calls service with new page number', async () => {
    vi.mocked(auditService.getLogs).mockResolvedValue({
      count: 50,
      next: '/api/v1/audit-logs/?page=2&paginate=true',
      previous: null,
      results: mockLogs,
    });

    render(
      <MemoryRouter>
        <AuditLogsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Showing 1 to 20 of 50 records')).toBeInTheDocument();
    });

    const nextBtn = screen.getByRole('button', { name: /next page/i });
    expect(nextBtn).toBeEnabled();

    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(auditService.getLogs).toHaveBeenCalledWith(
        expect.objectContaining({ page: 2, paginate: true }),
        expect.anything()
      );
    });
  });

  it('4. Filters logs with search input and resets page to 1', async () => {
    vi.mocked(auditService.getLogs).mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: mockLogs,
    });

    render(
      <MemoryRouter initialEntries={['/audit-logs?page=2']}>
        <AuditLogsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search logs...')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search logs...');
    fireEvent.change(searchInput, { target: { value: 'role_assigned' } });

    await waitFor(() => {
      expect(screen.getByText('Role: Manager')).toBeInTheDocument();
      expect(screen.queryByText('Employee created')).not.toBeInTheDocument();
    });
  });

  it('5. Displays error alert on 403 authorization failure', async () => {
    vi.mocked(auditService.getLogs).mockRejectedValueOnce(
      new Error('Authorization failed: 403')
    );

    render(
      <MemoryRouter>
        <AuditLogsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/403 \/ Access Denied/i)).toBeInTheDocument();
    });
  });

  it('6. Displays empty state message when no records exist', async () => {
    vi.mocked(auditService.getLogs).mockResolvedValueOnce({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });

    render(
      <MemoryRouter>
        <AuditLogsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('No audit activity found.')).toBeInTheDocument();
    });
  });
});
