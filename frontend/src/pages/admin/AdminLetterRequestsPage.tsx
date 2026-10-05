import React, { useState, useEffect, useMemo } from 'react';
import {
  FileText,
  CheckCircle,
  XCircle,
  Search,
  Loader2,
  AlertCircle,
  Download,
  User,
  RefreshCw,
} from 'lucide-react';
import { Card } from '../../components/Card';
import { StatusBadge } from '../../components/StatusBadge';
import {
  letterRequestService,
  type LetterRequest,
  type LetterRequestStatus,
} from '../../services/letterRequests';
import { useAuth } from '../../contexts/AuthContext';

export const AdminLetterRequestsPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const canManage = hasPermission('employee.manage');

  const [requests, setRequests] = useState<LetterRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | LetterRequestStatus>('ALL');
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  const fetchRequests = () => {
    setLoading(true);
    setError(null);
    letterRequestService
      .list()
      .then((data) => {
        setRequests(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        console.error('Failed to fetch letter requests:', err);
        setError('Unable to load employee letter requests.');
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchRequests();
  }, []);

  const handleUpdateStatus = async (id: number, status: 'APPROVED' | 'REJECTED') => {
    setUpdatingId(id);
    setError(null);
    try {
      const updated = await letterRequestService.updateStatus(id, status);
      setRequests((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } catch (err: any) {
      console.error(`Failed to ${status.toLowerCase()} letter request:`, err);
      setError(err?.message || `Failed to update letter request status.`);
    } finally {
      setUpdatingId(null);
    }
  };

  const filteredRequests = useMemo(() => {
    return requests.filter((req) => {
      const matchesStatus = statusFilter === 'ALL' || req.status === statusFilter;
      const q = searchQuery.toLowerCase();
      const matchesQuery =
        !searchQuery.trim() ||
        req.employee_name.toLowerCase().includes(q) ||
        req.letter_type.toLowerCase().includes(q) ||
        req.reason.toLowerCase().includes(q);
      return matchesStatus && matchesQuery;
    });
  }, [requests, statusFilter, searchQuery]);

  const pendingCount = useMemo(
    () => requests.filter((r) => r.status === 'PENDING').length,
    [requests]
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      {/* Header bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <h1
            style={{
              margin: 0,
              fontSize: 'var(--font-size-2xl)',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <FileText size={26} color="var(--color-primary)" />
            Employee Letter Requests
          </h1>
          <p className="text-muted" style={{ margin: '4px 0 0 0' }}>
            Review, approve, or reject official verification and certificate requests from employees.
          </p>
        </div>

        <button className="btn btn-secondary" onClick={fetchRequests} type="button">
          <RefreshCw size={15} /> Refresh
        </button>
      </div>

      {error && (
        <Card>
          <div
            style={{
              padding: 14,
              color: 'var(--color-status-danger)',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        </Card>
      )}

      {/* Filter and search bar */}
      <Card>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <div style={{ position: 'relative', flex: 1, minWidth: 240, maxWidth: 380 }}>
            <Search
              size={16}
              style={{
                position: 'absolute',
                left: 12,
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--color-text-muted)',
              }}
            />
            <input
              type="text"
              placeholder="Search by employee, letter type, purpose..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-neumorphic"
              style={{ paddingLeft: 36, width: '100%', height: 38 }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', gap: 4 }}>
              {(['ALL', 'PENDING', 'APPROVED', 'ISSUED', 'REJECTED'] as const).map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setStatusFilter(st)}
                  className={`btn ${statusFilter === st ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ fontSize: '0.82rem', padding: '6px 12px' }}
                >
                  {st === 'ALL' ? 'All' : st}
                  {st === 'PENDING' && pendingCount > 0 && ` (${pendingCount})`}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {/* Content area */}
      {loading ? (
        <Card>
          <div style={{ padding: 48, textAlign: 'center' }}>
            <Loader2 size={32} className="animate-spin" color="var(--color-primary)" />
            <p className="text-muted" style={{ marginTop: 12 }}>
              Loading letter requests...
            </p>
          </div>
        </Card>
      ) : filteredRequests.length === 0 ? (
        <Card>
          <div style={{ padding: 40, textAlign: 'center' }}>
            <FileText size={38} color="var(--color-text-muted)" style={{ margin: '0 auto 10px' }} />
            <h3 style={{ margin: 0 }}>No Letter Requests</h3>
            <p className="text-muted" style={{ margin: '6px 0 0' }}>
              {statusFilter !== 'ALL' || searchQuery
                ? 'No requests match your current filters.'
                : 'There are no active employee letter requests.'}
            </p>
          </div>
        </Card>
      ) : (
        <div style={{ display: 'grid', gap: 'var(--spacing-md)' }}>
          {filteredRequests.map((req) => {
            const isPending = req.status === 'PENDING';
            const isUpdating = updatingId === req.id;

            return (
              <Card key={req.id}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    flexWrap: 'wrap',
                    gap: 16,
                  }}
                >
                  <div style={{ display: 'flex', gap: 14, minWidth: 0, flex: 1 }}>
                    <div
                      style={{
                        width: 42,
                        height: 42,
                        borderRadius: '10px',
                        background: 'var(--color-primary-light, rgba(2, 132, 199, 0.1))',
                        color: 'var(--color-primary, #0284c7)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        marginTop: 2,
                      }}
                    >
                      <User size={20} />
                    </div>

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <strong style={{ fontSize: '1.05rem', color: 'var(--color-text-main)' }}>
                          {req.employee_name}
                        </strong>
                        <span
                          style={{
                            fontSize: '0.78rem',
                            fontWeight: 600,
                            padding: '2px 8px',
                            borderRadius: '6px',
                            background: 'var(--color-bg-subtle, #f1f5f9)',
                            color: 'var(--color-text-muted, #475569)',
                          }}
                        >
                          {req.letter_type}
                        </span>
                        <StatusBadge
                          status={
                            req.status === 'APPROVED' || req.status === 'ISSUED'
                              ? 'approved'
                              : req.status === 'REJECTED'
                              ? 'rejected'
                              : 'pending'
                          }
                          label={req.status}
                        />
                      </div>

                      <p style={{ margin: '8px 0 10px', color: 'var(--color-text-sub)', fontSize: '0.92rem' }}>
                        <strong>Reason:</strong> {req.reason}
                      </p>

                      <div style={{ display: 'flex', gap: 16, fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                        <span>Requested: {new Date(req.created_at).toLocaleString()}</span>
                        {req.approved_by_name && <span>Reviewed by: {req.approved_by_name}</span>}
                      </div>
                    </div>
                  </div>

                  {/* Actions Area */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                    {req.issued_document && (
                      <a
                        href={req.issued_document}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-secondary"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, textDecoration: 'none' }}
                      >
                        <Download size={14} /> Download Document
                      </a>
                    )}

                    {canManage && isPending && (
                      <>
                        <button
                          type="button"
                          className="btn btn-primary"
                          disabled={isUpdating}
                          onClick={() => handleUpdateStatus(req.id, 'APPROVED')}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            backgroundColor: '#059669',
                            borderColor: '#059669',
                          }}
                        >
                          {isUpdating ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
                          Approve & Issue
                        </button>

                        <button
                          type="button"
                          className="btn btn-secondary"
                          disabled={isUpdating}
                          onClick={() => handleUpdateStatus(req.id, 'REJECTED')}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            color: 'var(--color-status-danger, #ef4444)',
                          }}
                        >
                          {isUpdating ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />}
                          Reject
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};
