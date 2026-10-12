import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { NotificationBell } from '../NotificationBell';
import { notificationService } from '../../services/notifications';

const mockedNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockedNavigate,
  };
});

vi.mock('../../services/notifications', () => ({
  notificationService: {
    getUnreadCount: vi.fn(),
    getNotifications: vi.fn(),
    markAsRead: vi.fn(),
    markAllAsRead: vi.fn(),
  },
}));

describe('NotificationBell Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders bell button with unread count badge when count > 0', async () => {
    vi.mocked(notificationService.getUnreadCount).mockResolvedValue({ unread_count: 3 });

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('3')).toBeInTheDocument();
    });

    const bellBtn = screen.getByRole('button', { name: /Notifications, 3 unread/i });
    expect(bellBtn).toBeInTheDocument();
    expect(bellBtn).toHaveAttribute('aria-expanded', 'false');
  });

  it('hides badge when unread count is 0', async () => {
    vi.mocked(notificationService.getUnreadCount).mockResolvedValue({ unread_count: 0 });

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(notificationService.getUnreadCount).toHaveBeenCalled();
    });

    const bellBtn = screen.getByRole('button', { name: 'Notifications' });
    expect(bellBtn).toBeInTheDocument();
    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });

  it('formats badge label with 99+ when unread count exceeds 99', async () => {
    vi.mocked(notificationService.getUnreadCount).mockResolvedValue({ unread_count: 120 });

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('99+')).toBeInTheDocument();
    });
  });

  it('opens dropdown and renders populated notification items', async () => {
    vi.mocked(notificationService.getUnreadCount).mockResolvedValue({ unread_count: 2 });
    vi.mocked(notificationService.getNotifications).mockResolvedValue([
      {
        id: 101,
        title: 'Leave Approved',
        message: 'Your annual leave request has been approved by your manager.',
        notification_type: 'leave_approved',
        is_read: false,
        created_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
      },
      {
        id: 102,
        title: 'Payslip Ready',
        message: 'Your payslip for September 2026 is available.',
        notification_type: 'payslip_generated',
        is_read: true,
        created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      },
    ]);

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    const bellBtn = screen.getByRole('button', { name: /Notifications/i });
    fireEvent.click(bellBtn);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Loading notifications...')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Leave Approved')).toBeInTheDocument();
      expect(screen.getByText('Payslip Ready')).toBeInTheDocument();
      expect(screen.getByText(/Your annual leave request has been approved/i)).toBeInTheDocument();
    });
  });

  it('displays empty state when there are no notifications', async () => {
    vi.mocked(notificationService.getUnreadCount).mockResolvedValue({ unread_count: 0 });
    vi.mocked(notificationService.getNotifications).mockResolvedValue([]);

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    const bellBtn = screen.getByRole('button', { name: 'Notifications' });
    fireEvent.click(bellBtn);

    await waitFor(() => {
      expect(screen.getByText('All caught up')).toBeInTheDocument();
      expect(screen.getByText('No notifications yet.')).toBeInTheDocument();
    });
  });

  it('displays error state and retries successfully', async () => {
    vi.mocked(notificationService.getUnreadCount).mockResolvedValue({ unread_count: 0 });
    vi.mocked(notificationService.getNotifications)
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce([
        {
          id: 201,
          title: 'System Notice',
          message: 'Maintenance scheduled.',
          notification_type: 'system',
          is_read: true,
          created_at: new Date().toISOString(),
        },
      ]);

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Notifications' }));

    await waitFor(() => {
      expect(screen.getByText(/Failed to load notifications/i)).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole('button', { name: /Retry/i });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByText('System Notice')).toBeInTheDocument();
    });
  });

  it('marks a single notification as read on action button click', async () => {
    vi.mocked(notificationService.getUnreadCount).mockResolvedValue({ unread_count: 1 });
    vi.mocked(notificationService.getNotifications).mockResolvedValue([
      {
        id: 301,
        title: 'New Policy Update',
        message: 'Review our updated travel policy.',
        notification_type: 'system',
        is_read: false,
        created_at: new Date().toISOString(),
      },
    ]);
    vi.mocked(notificationService.markAsRead).mockResolvedValue({ id: 301, is_read: true } as any);

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /Notifications/i }));

    await waitFor(() => {
      expect(screen.getByText('New Policy Update')).toBeInTheDocument();
    });

    const markReadBtn = screen.getByRole('button', { name: /Mark "New Policy Update" as read/i });
    fireEvent.click(markReadBtn);

    await waitFor(() => {
      expect(notificationService.markAsRead).toHaveBeenCalledWith(301);
    });
  });

  it('marks all notifications as read when clicking Mark all read', async () => {
    vi.mocked(notificationService.getUnreadCount).mockResolvedValue({ unread_count: 2 });
    vi.mocked(notificationService.getNotifications).mockResolvedValue([
      {
        id: 401,
        title: 'Leave Approved',
        message: 'Leave approved',
        notification_type: 'leave_approved',
        is_read: false,
        created_at: new Date().toISOString(),
      },
      {
        id: 402,
        title: 'Asset Assigned',
        message: 'Laptop assigned',
        notification_type: 'asset_assigned',
        is_read: false,
        created_at: new Date().toISOString(),
      },
    ]);
    vi.mocked(notificationService.markAllAsRead).mockResolvedValue({ status: 'success' } as any);

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /Notifications/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Mark all notifications as read/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Mark all notifications as read/i }));

    await waitFor(() => {
      expect(notificationService.markAllAsRead).toHaveBeenCalledTimes(1);
    });
  });

  it('closes dropdown and restores focus to bell button on Escape key', async () => {
    vi.mocked(notificationService.getUnreadCount).mockResolvedValue({ unread_count: 0 });
    vi.mocked(notificationService.getNotifications).mockResolvedValue([]);

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    const bellBtn = screen.getByRole('button', { name: 'Notifications' });
    fireEvent.click(bellBtn);

    expect(screen.getByRole('dialog')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('navigates to destination route when a notification item is clicked', async () => {
    vi.mocked(notificationService.getUnreadCount).mockResolvedValue({ unread_count: 1 });
    vi.mocked(notificationService.getNotifications).mockResolvedValue([
      {
        id: 501,
        title: 'Leave Request Approved',
        message: 'Check your approved leave',
        notification_type: 'leave_approved',
        is_read: false,
        created_at: new Date().toISOString(),
      },
    ]);
    vi.mocked(notificationService.markAsRead).mockResolvedValue({ id: 501, is_read: true } as any);

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /Notifications/i }));

    await waitFor(() => {
      expect(screen.getByText('Leave Request Approved')).toBeInTheDocument();
    });

    const notifItem = screen.getByRole('button', { name: /Leave Request Approved, click to navigate/i });
    fireEvent.click(notifItem);

    await waitFor(() => {
      expect(notificationService.markAsRead).toHaveBeenCalledWith(501);
      expect(mockedNavigate).toHaveBeenCalledWith('/leaves');
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('routes asset and wfh notifications to valid routes /my-assets and /admin/wfh', async () => {
    vi.mocked(notificationService.getUnreadCount).mockResolvedValue({ unread_count: 2 });
    vi.mocked(notificationService.getNotifications).mockResolvedValue([
      {
        id: 601,
        title: 'New Laptop Assigned',
        message: 'MacBook Pro M3 assigned to you',
        notification_type: 'asset_assigned',
        is_read: false,
        created_at: new Date().toISOString(),
      },
      {
        id: 602,
        title: 'WFH Request Approved',
        message: 'Work from home request approved',
        notification_type: 'wfh_approved',
        is_read: true,
        created_at: new Date().toISOString(),
      },
    ]);
    vi.mocked(notificationService.markAsRead).mockResolvedValue({ id: 601, is_read: true } as any);

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /Notifications/i }));

    await waitFor(() => {
      expect(screen.getByText('New Laptop Assigned')).toBeInTheDocument();
    });

    // Test asset notification routes to /my-assets
    const assetItem = screen.getByRole('button', { name: /New Laptop Assigned, click to navigate/i });
    fireEvent.click(assetItem);

    await waitFor(() => {
      expect(mockedNavigate).toHaveBeenCalledWith('/my-assets');
    });

    // Reopen and test WFH notification routes to /admin/wfh
    fireEvent.click(screen.getByRole('button', { name: /Notifications/i }));
    await waitFor(() => {
      expect(screen.getByText('WFH Request Approved')).toBeInTheDocument();
    });
    const wfhItem = screen.getByRole('button', { name: /WFH Request Approved, click to navigate/i });
    fireEvent.click(wfhItem);

    await waitFor(() => {
      expect(mockedNavigate).toHaveBeenCalledWith('/admin/wfh');
    });
  });

  it('handles non-navigable notifications safely without navigating or erroring', async () => {
    vi.mocked(notificationService.getUnreadCount).mockResolvedValue({ unread_count: 0 });
    vi.mocked(notificationService.getNotifications).mockResolvedValue([
      {
        id: 701,
        title: 'General Maintenance Alert',
        message: 'Scheduled maintenance this Sunday at 2 AM UTC.',
        notification_type: 'system',
        is_read: true,
        created_at: new Date().toISOString(),
      },
    ]);

    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /Notifications/i }));

    await waitFor(() => {
      expect(screen.getByText('General Maintenance Alert')).toBeInTheDocument();
    });

    // Item should not have role="button" or click navigation
    expect(screen.queryByRole('button', { name: /General Maintenance Alert, click to navigate/i })).not.toBeInTheDocument();
  });
});
