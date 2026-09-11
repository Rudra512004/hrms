export type Notification = {
  id: number;
  notification_type: string;
  title: string;
  message: string;
  reference_id: string;
  is_read: boolean;
  created_at: string;
};

const getHeaders = () => {
  const token = localStorage.getItem('auth_token');
  if (!token) throw new Error('No authentication token');
  return {
    'Authorization': `Token ${token}`,
    'Content-Type': 'application/json'
  };
};

export const notificationService = {
  async getNotifications(): Promise<Notification[]> {
    const response = await fetch('/api/v1/notifications/', {
      headers: getHeaders()
    });
    if (!response.ok) throw new Error('Failed to fetch notifications');
    return response.json();
  },

  async getUnreadCount(): Promise<{ unread_count: number }> {
    const response = await fetch('/api/v1/notifications/unread-count/', {
      headers: getHeaders()
    });
    if (!response.ok) throw new Error('Failed to fetch unread count');
    return response.json();
  },

  async markAsRead(id: number): Promise<void> {
    const response = await fetch(`/api/v1/notifications/${id}/read/`, {
      method: 'POST',
      headers: getHeaders()
    });
    if (!response.ok) throw new Error('Failed to mark notification as read');
  },

  async markAllAsRead(): Promise<{ updated_count: number }> {
    const response = await fetch('/api/v1/notifications/read-all/', {
      method: 'POST',
      headers: getHeaders()
    });
    if (!response.ok) throw new Error('Failed to mark all as read');
    return response.json();
  }
};
