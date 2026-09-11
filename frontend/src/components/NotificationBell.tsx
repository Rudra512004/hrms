import React, { useState, useEffect, useRef } from 'react';
import { Bell, Check, Inbox, RefreshCw, AlertCircle } from 'lucide-react';
import { notificationService, type Notification } from '../services/notifications';

export const NotificationBell: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchUnreadCount();
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (isOpen) {
      fetchNotifications();
      fetchUnreadCount();
    }
  }, [isOpen]);

  const fetchUnreadCount = async () => {
    try {
      const data = await notificationService.getUnreadCount();
      setUnreadCount(data.unread_count);
    } catch (err) {
      console.error('Failed to fetch unread count', err);
    }
  };

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await notificationService.getNotifications();
      setNotifications(Array.isArray(data) ? data : []);
    } catch {
      setError('Failed to load notifications.');
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAsRead = async (id: number) => {
    try {
      await notificationService.markAsRead(id);
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (err) {
      console.error('Failed to mark notification as read', err);
    }
  };

  const handleMarkAllAsRead = async () => {
    try {
      await notificationService.markAllAsRead();
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error('Failed to mark all as read', err);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: 'numeric',
    }).format(date);
  };

  return (
    <div className="notification-wrapper" ref={dropdownRef} style={{ position: 'relative' }}>
      <button
        className="header-toggle"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Notifications"
        type="button"
        style={{ position: 'relative' }}
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span
            style={{
              position: 'absolute',
              top: '4px',
              right: '4px',
              backgroundColor: '#ef4444',
              color: 'white',
              fontSize: '0.65rem',
              fontWeight: 700,
              borderRadius: '9999px',
              minWidth: '16px',
              height: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '0 4px',
            }}
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          className="notification-dropdown"
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            right: 0,
            width: '360px',
            backgroundColor: '#ffffff',
            borderRadius: '12px',
            boxShadow: '0 10px 40px rgba(0,0,0,0.1)',
            border: '1px solid var(--color-border)',
            zIndex: 1000,
            display: 'flex',
            flexDirection: 'column',
            maxHeight: '480px',
            overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '16px 20px',
            borderBottom: '1px solid var(--color-border)',
            backgroundColor: '#f8fafc'
          }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--color-text-main)' }}>
              Notifications
            </h3>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllAsRead}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--color-primary)',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                <Check size={14} /> Mark all read
              </button>
            )}
          </div>

          {/* Body */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '0' }}>
            {loading && notifications.length === 0 ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
                <RefreshCw size={24} color="var(--color-text-muted)" className="spin" />
              </div>
            ) : error ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '40px', color: '#ef4444' }}>
                <AlertCircle size={32} style={{ marginBottom: '12px' }} />
                <span style={{ fontSize: '0.9rem' }}>{error}</span>
                <button 
                  onClick={fetchNotifications}
                  style={{ marginTop: '12px', background: 'none', border: '1px solid currentColor', borderRadius: '4px', padding: '4px 12px', color: 'inherit', cursor: 'pointer' }}
                >
                  Retry
                </button>
              </div>
            ) : notifications.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '60px 20px', color: 'var(--color-text-muted)' }}>
                <Inbox size={48} style={{ marginBottom: '16px', opacity: 0.5 }} />
                <span style={{ fontSize: '0.95rem', fontWeight: 500 }}>No notifications yet</span>
                <span style={{ fontSize: '0.85rem', marginTop: '4px' }}>When you get notifications, they'll show up here.</span>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {notifications.map(notif => (
                  <div
                    key={notif.id}
                    onClick={() => !notif.is_read && handleMarkAsRead(notif.id)}
                    style={{
                      padding: '16px 20px',
                      borderBottom: '1px solid var(--color-border)',
                      backgroundColor: notif.is_read ? '#ffffff' : '#f0f9ff',
                      cursor: notif.is_read ? 'default' : 'pointer',
                      transition: 'background-color 0.2s ease',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                      <span style={{ 
                        fontSize: '0.9rem', 
                        fontWeight: notif.is_read ? 500 : 600, 
                        color: 'var(--color-text-main)' 
                      }}>
                        {notif.title}
                      </span>
                      {!notif.is_read && (
                        <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#0ea5e9', flexShrink: 0, marginTop: '6px' }} />
                      )}
                    </div>
                    <p style={{ 
                      margin: 0, 
                      fontSize: '0.85rem', 
                      color: 'var(--color-text-muted)',
                      lineHeight: 1.4 
                    }}>
                      {notif.message}
                    </p>
                    <span style={{ 
                      fontSize: '0.75rem', 
                      color: '#94a3b8', 
                      marginTop: '4px' 
                    }}>
                      {formatDate(notif.created_at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
