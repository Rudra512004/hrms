/**
 * NOTIFICATION SERVICE
 *
 * DEV1_CONTRACT — PROVISIONAL
 * ─────────────────────────────────────────────────────────────────────────
 * The backend in-app notification REST API has NOT yet been finalized by
 * Dev1. All endpoint URLs, HTTP verbs, and response field names below are
 * provisional estimates.
 *
 * Search "DEV1_CONTRACT" to find every provisional item. Replace with the
 * exact contract once Dev1 provides it.
 *
 * DO NOT change the TypeScript interface names or method signatures — only
 * update the field names and endpoint strings to match Dev1's actual contract.
 * ─────────────────────────────────────────────────────────────────────────
 */

// ── Types ─────────────────────────────────────────────────────────────────

/**
 * DEV1_CONTRACT: Provisional notification object shape.
 * Confirm every field name with Dev1.
 */
export interface Notification {
  /** Unique numeric ID. */
  id: number;
  /** Short, human-readable title (e.g. "Leave Approved"). */
  title: string;
  /** Full notification body text. May be empty string but never undefined. */
  message: string;
  /**
   * Machine-readable event type (e.g. 'leave_approved', 'payroll_processed',
   * 'asset_assigned', 'lifecycle_exit').
   * DEV1_CONTRACT: Confirm exact values.
   */
  notification_type: string;
  /** Whether the current user has read this notification. */
  is_read: boolean;
  /** ISO 8601 creation timestamp. */
  created_at: string;
  /**
   * Optional deep-link data so the UI can navigate to the related object.
   * DEV1_CONTRACT: Confirm if these fields exist and their exact names.
   */
  reference_id?: number | string | null;
  reference_type?: string | null;
  reference_url?: string | null;
}

/**
 * DEV1_CONTRACT: Provisional list/paginated response shape.
 * If the backend returns a flat array, adapt the `notificationService.list`
 * normalisation block below.
 */
export interface NotificationListResponse {
  results: Notification[];
  count: number;
  unread_count: number;
}

// ── Auth helper (matches pattern in assets.ts / audit.ts) ─────────────────

const getAuthHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('auth_token');
  if (!token) throw new Error('No authentication token');
  return {
    Authorization: `Token ${token}`,
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };
};

const handleError = async (res: Response): Promise<never> => {
  const errorData = await res.json().catch(() => ({}));
  throw { status: res.status, data: errorData };
};

// ── Service ───────────────────────────────────────────────────────────────

/**
 * DEV1_CONTRACT: Base URL. Confirm with Dev1 once backend is deployed.
 */
const API_BASE = '/api/v1/notifications';

export const notificationService = {
  /**
   * List notifications for the currently authenticated user.
   *
   * DEV1_CONTRACT: GET /api/v1/notifications/
   * Normalises both paginated (`{ count, results, unread_count }`) and flat
   * array responses so the component stays stable regardless of shape.
   */
  list: async (): Promise<NotificationListResponse> => {
    const res = await fetch(`${API_BASE}/`, { headers: getAuthHeaders() });
    if (!res.ok) return handleError(res);
    const data = await res.json();

    // Normalise: accept both paginated and flat-array responses
    const results: Notification[] = Array.isArray(data)
      ? data
      : (data.results ?? []);

    const unread_count: number =
      typeof data.unread_count === 'number'
        ? data.unread_count
        : results.filter((n) => !n.is_read).length;

    const count: number =
      typeof data.count === 'number'
        ? data.count
        : results.length;

    return { results, count, unread_count };
  },

  /**
   * Retrieve the unread notification count for the bell badge.
   *
   * DEV1_CONTRACT: GET /api/v1/notifications/unread-count/
   * If Dev1 does not add a separate endpoint, falls back to deriving the
   * count from the list response.
   */
  getUnreadCount: async (): Promise<number> => {
    const res = await fetch(`${API_BASE}/unread-count/`, {
      headers: getAuthHeaders(),
    });
    if (res.ok) {
      const data = await res.json();
      // DEV1_CONTRACT: Confirm field name — may be `count` or `unread_count`
      return typeof data.unread_count === 'number'
        ? data.unread_count
        : typeof data.count === 'number'
        ? data.count
        : 0;
    }
    // Graceful fallback: derive from list
    const listData = await notificationService.list();
    return listData.unread_count;
  },

  /**
   * Mark a single notification as read.
   *
   * DEV1_CONTRACT: POST /api/v1/notifications/{id}/read/
   * If Dev1 uses PATCH instead (e.g. `{ is_read: true }`), update the
   * method and body below.
   */
  markRead: async (id: number): Promise<void> => {
    const res = await fetch(`${API_BASE}/${id}/read/`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok && res.status !== 204) return handleError(res);
  },

  /**
   * Mark all notifications as read.
   *
   * DEV1_CONTRACT: POST /api/v1/notifications/mark-all-read/
   */
  markAllRead: async (): Promise<void> => {
    const res = await fetch(`${API_BASE}/mark-all-read/`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok && res.status !== 204) return handleError(res);
  },
};
