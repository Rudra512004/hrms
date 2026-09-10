import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Bell,
  BellOff,
  X,
  CheckCheck,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { notificationService, type Notification } from '../services/notifications';

// ── Helpers ───────────────────────────────────────────────────────────────

/** Format ISO timestamp as compact relative string */
function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return 'just now';
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/**
 * DEV1_CONTRACT: Map provisional notification_type values to UI accent colours.
 * Update keys once Dev1 confirms the exact type string values.
 */
const TYPE_COLOR: Record<string, string> = {
  leave_approved:      'var(--color-status-success)',
  leave_rejected:      'var(--color-status-danger)',
  leave_pending:       'var(--color-status-warning)',
  payroll_processed:   'var(--color-status-info)',
  payslip_generated:   'var(--color-status-info)',
  asset_assigned:      'var(--color-primary)',
  asset_returned:      'var(--color-text-muted)',
  lifecycle_promotion: 'var(--color-primary)',
  lifecycle_transfer:  'var(--color-primary)',
  lifecycle_exit:      'var(--color-status-danger)',
  document_uploaded:   'var(--color-status-info)',
  system:              'var(--color-text-muted)',
};

function accentForType(type: string): string {
  return TYPE_COLOR[type] ?? 'var(--color-primary)';
}

// ── Component ─────────────────────────────────────────────────────────────

/**
 * NotificationBell
 *
 * Self-contained header notification widget:
 * - Bell icon button with unread-count badge
 * - Keyboard accessible (Escape closes, focus returns to button)
 * - Panel renders all UX states: loading, empty, error, populated
 * - Individual mark-as-read + mark-all-read
 *
 * API wiring is provisional (see services/notifications.ts).
 * When Dev1 finalises the backend contract, only the service layer needs
 * to change; this component requires no modification.
 */
export const NotificationBell: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  // Notification data
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  // Per-fetch state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Optimistic action states
  const [markingId, setMarkingId] = useState<number | null>(null);
  const [markingAll, setMarkingAll] = useState(false);

  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // ── Data fetching ──────────────────────────────────────────────────────

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await notificationService.list();
      setNotifications(data.results);
      setUnreadCount(data.unread_count);
    } catch (err: any) {
      const status: number = err?.status ?? 0;
      if (status === 404) {
        setError('Notifications are not yet available.');
      } else if (status === 401 || status === 403) {
        setError('You do not have permission to view notifications.');
      } else {
        setError('Failed to load notifications. Please try again.');
      }
      setNotifications([]);
      setUnreadCount(0);
    } finally {
      setLoading(false);
    }
  }, []);

  // Reload whenever panel is opened
  useEffect(() => {
    if (isOpen) {
      fetchNotifications();
    }
  }, [isOpen, fetchNotifications]);

  // ── Keyboard & outside-click ───────────────────────────────────────────

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
        buttonRef.current?.focus();
      }
    };

    const handleMouseDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        panelRef.current && !panelRef.current.contains(target) &&
        buttonRef.current && !buttonRef.current.contains(target)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handleMouseDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleMouseDown);
    };
  }, [isOpen]);

  // ── Actions ────────────────────────────────────────────────────────────

  const handleMarkRead = async (notif: Notification) => {
    if (notif.is_read || markingId === notif.id) return;
    setMarkingId(notif.id);
    try {
      await notificationService.markRead(notif.id);
      // Optimistic update
      setNotifications(prev =>
        prev.map(n => n.id === notif.id ? { ...n, is_read: true } : n)
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch {
      // Silent fail for individual mark-read — data reloads on next panel open
    } finally {
      setMarkingId(null);
    }
  };

  const handleMarkAllRead = async () => {
    if (markingAll || unreadCount === 0) return;
    setMarkingAll(true);
    try {
      await notificationService.markAllRead();
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // Could surface a toast once a toast system is implemented
    } finally {
      setMarkingAll(false);
    }
  };

  // ── Derived display ────────────────────────────────────────────────────

  const badgeLabel = unreadCount > 99 ? '99+' : unreadCount > 9 ? '9+' : String(unreadCount);
  const ariaLabel = unreadCount > 0
    ? `Notifications, ${unreadCount} unread`
    : 'Notifications';

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div style={{ position: 'relative', flexShrink: 0 }}>

      {/* ── Bell button ── */}
      <button
        ref={buttonRef}
        id="notification-bell-btn"
        className="header-toggle notif-bell-btn"
        type="button"
        aria-label={ariaLabel}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        onClick={() => setIsOpen(prev => !prev)}
      >
        <Bell size={18} aria-hidden="true" />
        {unreadCount > 0 && (
          <span className="notif-badge" aria-hidden="true">
            {badgeLabel}
          </span>
        )}
      </button>

      {/* ── Dropdown panel ── */}
      {isOpen && (
        <div
          ref={panelRef}
          className="notif-panel animate-fade-in"
          role="dialog"
          aria-labelledby="notif-panel-heading"
          aria-modal="false"
        >
          {/* Panel header */}
          <div className="notif-panel-hd">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 id="notif-panel-heading" className="notif-panel-title">
                Notifications
              </h2>
              {unreadCount > 0 && (
                <span className="notif-count-pill" aria-live="polite">
                  {unreadCount} unread
                </span>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
              {unreadCount > 0 && !loading && !error && (
                <button
                  className="btn btn-ghost btn-sm"
                  type="button"
                  onClick={handleMarkAllRead}
                  disabled={markingAll}
                  aria-label="Mark all notifications as read"
                  title="Mark all as read"
                  style={{ fontSize: 'var(--font-size-xs)', gap: '4px' }}
                >
                  {markingAll
                    ? <Loader2 size={13} className="animate-spin" aria-hidden="true" />
                    : <CheckCheck size={13} aria-hidden="true" />}
                  <span className="notif-mark-all-label">Mark all read</span>
                </button>
              )}
              <button
                className="btn btn-ghost btn-sm"
                type="button"
                onClick={() => setIsOpen(false)}
                aria-label="Close notifications panel"
                style={{ padding: '4px 6px' }}
              >
                <X size={16} aria-hidden="true" />
              </button>
            </div>
          </div>

          {/* Panel body */}
          <div
            className="notif-panel-body"
            role="log"
            aria-live="polite"
            aria-label="Notification items"
          >

            {/* Loading */}
            {loading && (
              <div className="notif-state">
                <Loader2
                  size={26}
                  className="animate-spin"
                  style={{ color: 'var(--color-primary)', marginBottom: '10px' }}
                  aria-hidden="true"
                />
                <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                  Loading notifications…
                </span>
              </div>
            )}

            {/* Error */}
            {!loading && error && (
              <div className="notif-state">
                <AlertCircle
                  size={26}
                  style={{ color: 'var(--color-status-warning)', marginBottom: '10px' }}
                  aria-hidden="true"
                />
                <p style={{
                  fontSize: 'var(--font-size-sm)',
                  color: 'var(--color-text-muted)',
                  textAlign: 'center',
                  maxWidth: '210px',
                  margin: '0 0 12px 0',
                }}>
                  {error}
                </p>
                <button
                  className="btn btn-secondary btn-sm"
                  type="button"
                  onClick={fetchNotifications}
                >
                  Retry
                </button>
              </div>
            )}

            {/* Empty */}
            {!loading && !error && notifications.length === 0 && (
              <div className="notif-state">
                <BellOff
                  size={30}
                  style={{
                    opacity: 0.3,
                    color: 'var(--color-text-muted)',
                    marginBottom: '10px',
                  }}
                  aria-hidden="true"
                />
                <p style={{
                  fontSize: 'var(--font-size-sm)',
                  fontWeight: 600,
                  color: 'var(--color-text-main)',
                  margin: '0 0 4px 0',
                }}>
                  All caught up
                </p>
                <p style={{
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--color-text-muted)',
                  margin: 0,
                }}>
                  No notifications yet.
                </p>
              </div>
            )}

            {/* Notification list */}
            {!loading && !error && notifications.length > 0 && (
              <ul className="notif-list" role="list">
                {notifications.map(notif => (
                  <li
                    key={notif.id}
                    className={`notif-item${notif.is_read ? '' : ' notif-item--unread'}`}
                  >
                    {/* Unread accent bar */}
                    {!notif.is_read && (
                      <span
                        className="notif-accent"
                        aria-hidden="true"
                        style={{ backgroundColor: accentForType(notif.notification_type) }}
                      />
                    )}

                    {/* Content */}
                    <div className="notif-item-content">
                      <p className="notif-item-title" title={notif.title}>
                        {notif.title}
                      </p>
                      {notif.message && (
                        <p className="notif-item-msg" title={notif.message}>
                          {notif.message}
                        </p>
                      )}
                      <time
                        className="notif-item-time"
                        dateTime={notif.created_at}
                        title={new Date(notif.created_at).toLocaleString()}
                      >
                        {relativeTime(notif.created_at)}
                      </time>
                    </div>

                    {/* Mark read action */}
                    {!notif.is_read && (
                      <button
                        className="notif-markread-btn"
                        type="button"
                        onClick={() => handleMarkRead(notif)}
                        disabled={markingId === notif.id}
                        aria-label={`Mark "${notif.title}" as read`}
                        title="Mark as read"
                      >
                        {markingId === notif.id
                          ? <Loader2 size={12} className="animate-spin" aria-hidden="true" />
                          : <CheckCheck size={12} aria-hidden="true" />}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
