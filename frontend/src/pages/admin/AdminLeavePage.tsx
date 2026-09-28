import React, { useState, useEffect, useCallback, useRef } from 'react';
import { usePagination } from '../../hooks/usePagination';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { Modal } from '../../components/Modal';
import { leaveService, type LeaveRequest, type ListLeaveRequestsParams, type LeaveBalance } from '../../services/leaves';
import { employeeManagementService } from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import { exportToCsv } from '../../utils/exportCsv';
import { AlertCircle, FileCheck2, Loader2, Check, X, Download, Sliders } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useBranchContext } from '../../contexts/BranchContext';

const styles = {
  container: {
    padding: 'var(--spacing-xl)',
    maxWidth: '1200px',
    margin: '0 auto',
    width: '100%'
  },
  header: {
    marginBottom: 'var(--spacing-xl)'
  },
  title: {
    fontSize: '24px',
    fontWeight: 600,
    color: 'var(--color-text-main)',
    marginBottom: 'var(--spacing-xs)'
  },
  subtitle: {
    color: 'var(--color-text-muted)',
    fontSize: '14px'
  },
  alert: (type: 'error' | 'success') => ({
    padding: 'var(--spacing-md)',
    backgroundColor: type === 'error' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(34, 197, 94, 0.1)',
    color: type === 'error' ? 'var(--color-danger)' : 'var(--color-success)',
    borderRadius: '4px',
    marginBottom: 'var(--spacing-lg)',
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-sm)',
    border: `1px solid ${type === 'error' ? 'var(--color-danger)' : 'var(--color-success)'}`
  }),
  button: (variant: 'success' | 'danger' | 'secondary' = 'secondary') => ({
    padding: '6px 12px',
    backgroundColor: variant === 'success' ? 'var(--color-success)' : variant === 'danger' ? 'var(--color-danger)' : 'var(--color-bg-body)',
    color: variant === 'secondary' ? 'var(--color-text-main)' : 'white',
    border: variant === 'secondary' ? '1px solid var(--color-border)' : 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontWeight: 500,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '4px',
    fontSize: '13px',
    transition: 'opacity 0.2s',
  }),
  modal: {
    position: 'fixed' as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    padding: 'var(--spacing-xl)'
  },
  modalContent: {
    backgroundColor: 'var(--color-bg-card)',
    padding: 'var(--spacing-xl)',
    borderRadius: '8px',
    width: '100%',
    maxWidth: '500px',
    boxShadow: 'var(--shadow-lg)'
  },
  input: {
    width: '100%',
    padding: 'var(--spacing-sm)',
    border: '1px solid var(--color-border)',
    borderRadius: '4px',
    backgroundColor: 'var(--color-bg-input)',
    color: 'var(--color-text-main)',
    fontFamily: 'inherit',
    fontSize: '14px',
    marginBottom: 'var(--spacing-lg)'
  }
};

export function AdminLeavePage() {
  const { user, hasPermission } = useAuth();
  const { branchId } = useBranchContext();

  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDenied, setIsDenied] = useState(false);

  // Filter state
  const [statusFilter, setStatusFilter] = useState('all');

  // Pagination state with URL synchronization
  const {
    page,
    pageSize,
    totalCount,
    setTotalCount,
    handlePageChange,
    resetPage,
  } = usePagination({ defaultPageSize: 20 });

  // Reset page to 1 if branch changes
  const prevBranchIdRef = useRef(branchId);
  useEffect(() => {
    if (prevBranchIdRef.current !== branchId) {
      prevBranchIdRef.current = branchId;
      resetPage();
    }
  }, [branchId, resetPage]);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Review Modal State
  const [reviewModal, setReviewModal] = useState<{ isOpen: boolean; request: LeaveRequest | null; action: 'approve' | 'reject' | null }>({
    isOpen: false,
    request: null,
    action: null
  });
  const [reviewComment, setReviewComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Leave Balance Adjustment Modal State
  const [showAdjustModal, setShowAdjustModal] = useState(false);
  const [employees, setEmployees] = useState<EmployeeProfile[]>([]);
  const [employeesLoading, setEmployeesLoading] = useState(false);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string>('');
  const [employeeBalances, setEmployeeBalances] = useState<LeaveBalance[]>([]);
  const [balancesLoading, setBalancesLoading] = useState(false);
  const [selectedBalanceId, setSelectedBalanceId] = useState<number | null>(null);
  const [adjustAmount, setAdjustAmount] = useState<string>('');
  const [adjustReason, setAdjustReason] = useState<string>('');
  const [isAdjusting, setIsAdjusting] = useState(false);
  const [adjustError, setAdjustError] = useState<string | null>(null);
  const [adjustSuccess, setAdjustSuccess] = useState<string | null>(null);

  const loadRequests = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      setLoading(true);
      setError(null);
      setIsDenied(false);

      const params: ListLeaveRequestsParams = {
        paginate: true,
        page,
        page_size: pageSize,
      };
      if (branchId !== null && branchId !== undefined) {
        params.branch_id = branchId;
      }
      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }

      const data = await leaveService.getRequests(params, { signal: controller.signal });
      if (abortControllerRef.current === controller) {
        if (Array.isArray(data)) {
          setRequests(data);
          setTotalCount(data.length);
        } else if (data && Array.isArray(data.results)) {
          setRequests(data.results);
          setTotalCount(data.count);
        } else {
          setRequests([]);
          setTotalCount(0);
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        return;
      }
      if (abortControllerRef.current === controller) {
        if (err.response?.status === 403 || err.status === 403) {
          setIsDenied(true);
        } else {
          setError("Failed to load leave requests.");
        }
        setRequests([]);
        setTotalCount(0);
      }
    } finally {
      if (abortControllerRef.current === controller) {
        setLoading(false);
      }
    }
  }, [branchId, statusFilter, page, pageSize, setTotalCount]);

  useEffect(() => {
    loadRequests();
    return () => {
      abortControllerRef.current?.abort();
    };
  }, [loadRequests]);

  const openReviewModal = (request: LeaveRequest, action: 'approve' | 'reject') => {
    setReviewModal({ isOpen: true, request, action });
    setReviewComment('');
  };

  const handleReviewSubmit = async () => {
    if (!reviewModal.request || !reviewModal.action) return;

    try {
      setIsSubmitting(true);
      setError(null);
      if (reviewModal.action === 'approve') {
        await leaveService.approveRequest(reviewModal.request.id, reviewComment);
      } else {
        await leaveService.rejectRequest(reviewModal.request.id, reviewComment);
      }
      setReviewModal({ isOpen: false, request: null, action: null });
      await loadRequests();
    } catch (err: any) {
      setReviewModal({ isOpen: false, request: null, action: null });
      const msgs = err.errorData ? Object.values(err.errorData).flat().join(" ") : `Failed to ${reviewModal.action} request.`;
      setError(msgs);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleExportCsv = () => {
    if (!requests.length) return;
    exportToCsv(
      `leave_requests_${new Date().toISOString().split('T')[0]}`,
      [
        { header: 'ID', accessor: (r) => `#${r.id}` },
        { header: 'Employee', accessor: (r) => r.employee_name || `Employee #${r.employee}` },
        { header: 'Employee Code', accessor: (r) => r.employee_code || '' },
        { header: 'Leave Type', accessor: (r) => r.leave_type_name || '' },
        { header: 'Start Date', accessor: (r) => r.start_date },
        { header: 'End Date', accessor: (r) => r.end_date },
        {
          header: 'Duration (Days)',
          accessor: (r) => (r.is_half_day ? 0.5 : (r.duration_days ?? '')),
        },
        {
          header: 'Half Day',
          accessor: (r) =>
            r.is_half_day
              ? r.half_day_period === 'second_half'
                ? '2nd Half'
                : '1st Half'
              : 'No',
        },
        { header: 'Reason', accessor: (r) => r.reason },
        { header: 'Status', accessor: (r) => r.status },
        { header: 'Reviewer Comment', accessor: (r) => r.reviewer_comment || '' },
      ],
      requests
    );
  };

  const openAdjustModal = async () => {
    setShowAdjustModal(true);
    setSelectedEmployeeId('');
    setEmployeeBalances([]);
    setSelectedBalanceId(null);
    setAdjustAmount('');
    setAdjustReason('');
    setAdjustError(null);
    setAdjustSuccess(null);

    if (employees.length === 0) {
      setEmployeesLoading(true);
      try {
        const res = await employeeManagementService.listEmployees({ paginate: false });
        const list = Array.isArray(res) ? res : (res as any)?.results || [];
        setEmployees(list);
      } catch {
        // fallback
      } finally {
        setEmployeesLoading(false);
      }
    }
  };

  const handleEmployeeChange = async (empId: string) => {
    setSelectedEmployeeId(empId);
    setSelectedBalanceId(null);
    setEmployeeBalances([]);
    setAdjustError(null);
    setAdjustSuccess(null);

    if (!empId) return;

    setBalancesLoading(true);
    try {
      const balances = await leaveService.getBalances({ employee_id: empId });
      setEmployeeBalances(balances);
      if (balances.length > 0) {
        setSelectedBalanceId(balances[0].id);
      }
    } catch {
      setAdjustError('Failed to load leave balances for selected employee.');
    } finally {
      setBalancesLoading(false);
    }
  };

  const handleAdjustSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBalanceId) {
      setAdjustError('Please select a leave balance to adjust.');
      return;
    }
    const parsedAmount = parseFloat(adjustAmount);
    if (isNaN(parsedAmount) || parsedAmount === 0) {
      setAdjustError('Please enter a valid non-zero adjustment amount.');
      return;
    }
    if (!adjustReason.trim()) {
      setAdjustError('Please provide an adjustment reason.');
      return;
    }

    setIsAdjusting(true);
    setAdjustError(null);
    setAdjustSuccess(null);
    try {
      await leaveService.adjustBalance(selectedBalanceId, parsedAmount, adjustReason.trim());
      setAdjustSuccess('Leave balance adjusted successfully.');
      setAdjustAmount('');
      setAdjustReason('');
      // Refresh balances
      if (selectedEmployeeId) {
        const updated = await leaveService.getBalances({ employee_id: selectedEmployeeId });
        setEmployeeBalances(updated);
      }
    } catch (err: any) {
      const msgs = err.errorData ? Object.values(err.errorData).flat().join(' ') : 'Failed to adjust leave balance.';
      setAdjustError(msgs);
    } finally {
      setIsAdjusting(false);
    }
  };

  if (isDenied) {
    return (
      <div style={styles.container}>
        <div style={{ textAlign: 'center', padding: '40px 20px' }}>
          <AlertCircle size={48} style={{ color: 'var(--color-danger)', margin: '0 auto 16px' }} />
          <h2 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--color-text-main)', marginBottom: '8px' }}>Access Denied</h2>
          <p style={{ color: 'var(--color-text-muted)' }}>You do not have permission to view or manage leave requests.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: '300px' }}>
        <Loader2 size={32} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
      </div>
    );
  }

  const columns = [
    { key: 'id', title: 'ID', render: (r: LeaveRequest) => `#${r.id}` },
    {
      key: 'employee',
      title: 'Employee',
      render: (r: LeaveRequest) => (
        <div>
          <div style={{ fontWeight: 500 }}>{r.employee_name || `Employee #${r.employee}`}</div>
          {r.employee_code && (
            <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>{r.employee_code}</div>
          )}
        </div>
      ),
    },
    { key: 'leave_type_name', title: 'Leave Type' },
    { key: 'start_date', title: 'Start' },
    { key: 'end_date', title: 'End' },
    {
      key: 'duration_days',
      title: 'Duration',
      render: (r: LeaveRequest) => (
        <span style={{ fontSize: '13px', whiteSpace: 'nowrap' }}>
          {r.is_half_day ? (
            <span style={{ color: 'var(--color-primary)', fontWeight: 600 }}>
              0.5d ({r.half_day_period === 'second_half' ? '2nd Half' : '1st Half'})
            </span>
          ) : r.duration_days !== null && r.duration_days !== undefined ? (
            `${r.duration_days}d`
          ) : (
            '—'
          )}
        </span>
      ),
    },
    {
      key: 'reason',
      title: 'Reason & Docs',
      render: (r: LeaveRequest) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
          <span style={{ maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {r.reason}
          </span>
          {r.supporting_document && (
            <a
              href={r.supporting_document}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '12px',
                color: 'var(--color-primary)',
                textDecoration: 'underline',
              }}
            >
              <FileCheck2 size={13} /> View Attached Document
            </a>
          )}
        </div>
      ),
    },
    {
      key: 'status',
      title: 'Status',
      render: (r: LeaveRequest) => <StatusBadge status={r.status} />
    },
    {
      key: 'actions',
      title: 'Actions',
      render: (r: LeaveRequest) => {
        const isSelf = user?.id === r.employee.toString(); // Employee cannot approve own request
        return r.status === 'pending' ? (
          <div style={{ display: 'flex', gap: '8px' }}>
            {hasPermission('leave.approve') && (
              <button
                onClick={() => openReviewModal(r, 'approve')}
                style={{...styles.button('success'), opacity: isSelf ? 0.5 : 1}}
                disabled={isSelf}
                title={isSelf ? "Cannot approve your own request" : "Approve Request"}
              >
                <Check size={14} /> Approve
              </button>
            )}
            {hasPermission('leave.reject') && (
              <button
                onClick={() => openReviewModal(r, 'reject')}
                style={styles.button('danger')}
              >
                <X size={14} /> Reject
              </button>
            )}
          </div>
        ) : <span style={{ fontSize: '13px', color: 'var(--color-text-muted)' }}>{r.reviewer_comment || '-'}</span>;
      }
    }
  ];

  return (
    <div style={styles.container}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: '16px',
          marginBottom: 'var(--spacing-xl)',
        }}
      >
        <div>
          <h1 style={styles.title}>Leave Management</h1>
          <p style={styles.subtitle}>Review and manage employee leave requests and balances.</p>
        </div>
        {(hasPermission('leave_type.manage') || user?.isSuperuser) && (
          <button
            onClick={openAdjustModal}
            style={{
              ...styles.button('secondary'),
              backgroundColor: 'var(--color-primary)',
              color: '#fff',
              padding: '8px 16px',
              border: 'none',
              boxShadow: 'var(--shadow-sm)',
            }}
            title="Adjust Employee Leave Balance"
            data-testid="adjust-balance-btn"
          >
            <Sliders size={15} /> Adjust Leave Balance
          </button>
        )}
      </div>

      {error && (
        <div style={styles.alert('error')}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      <Card>
        <div style={{ padding: 'var(--spacing-lg)' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 'var(--spacing-lg)',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
              <FileCheck2 size={20} style={{ color: 'var(--color-primary)' }} />
              <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-text-main)', margin: 0 }}>
                All Leave Requests
              </h2>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <select
                style={{
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-md, 4px)',
                  border: '1px solid var(--color-border)',
                  backgroundColor: 'var(--color-bg-body)',
                  color: 'var(--color-text-main)',
                  fontSize: '14px',
                }}
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  resetPage();
                }}
                aria-label="Filter by status"
                data-testid="leave-status-filter"
              >
                <option value="all">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
                <option value="cancelled">Cancelled</option>
              </select>

              <button
                onClick={handleExportCsv}
                style={{
                  ...styles.button('secondary'),
                  padding: '6px 12px',
                }}
                disabled={requests.length === 0}
                title="Export Leave Requests to CSV"
                data-testid="export-leave-csv-btn"
              >
                <Download size={14} /> Export CSV
              </button>
            </div>
          </div>
          <Table
            columns={columns}
            data={requests}
            keyExtractor={(r) => r.id.toString()}
            pagination
            count={totalCount}
            page={page}
            pageSize={pageSize}
            onPageChange={handlePageChange}
            loading={loading}
          />
        </div>
      </Card>

      {reviewModal.isOpen && (
        <div style={styles.modal}>
          <div style={styles.modalContent}>
            <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-text-main)', marginBottom: '16px' }}>
              {reviewModal.action === 'approve' ? 'Approve' : 'Reject'} Leave Request
            </h2>
            <p style={{ color: 'var(--color-text-muted)', marginBottom: '16px', fontSize: '14px' }}>
              You are about to {reviewModal.action} request #{reviewModal.request?.id}. You may provide an optional comment.
            </p>

            <label style={{ display: 'block', marginBottom: '8px', color: 'var(--color-text-main)', fontSize: '14px', fontWeight: 500 }}>
              Reviewer Comment (Optional)
            </label>
            <textarea
              style={{...styles.input, minHeight: '80px', resize: 'vertical'}}
              value={reviewComment}
              onChange={e => setReviewComment(e.target.value)}
              placeholder="Enter your comment here..."
            />

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                style={styles.button('secondary')}
                onClick={() => setReviewModal({ isOpen: false, request: null, action: null })}
                disabled={isSubmitting}
              >
                Cancel
              </button>
              <button
                style={reviewModal.action === 'approve' ? styles.button('success') : styles.button('danger')}
                onClick={handleReviewSubmit}
                disabled={isSubmitting}
              >
                {isSubmitting ? <Loader2 size={14} className="animate-spin" /> : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showAdjustModal && (
        <Modal
          title="Adjust Employee Leave Balance"
          onClose={() => setShowAdjustModal(false)}
          size="md"
          footer={
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowAdjustModal(false)}
                disabled={isAdjusting}
              >
                Close
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleAdjustSubmit}
                disabled={isAdjusting || !selectedBalanceId || !adjustAmount || !adjustReason}
              >
                {isAdjusting ? <Loader2 size={14} className="animate-spin" /> : 'Save Adjustment'}
              </button>
            </div>
          }
        >
          {adjustError && (
            <div style={styles.alert('error')}>
              <AlertCircle size={18} />
              <span>{adjustError}</span>
            </div>
          )}
          {adjustSuccess && (
            <div style={styles.alert('success')}>
              <Check size={18} />
              <span>{adjustSuccess}</span>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', fontWeight: 600 }}>
                Select Employee *
              </label>
              <select
                style={styles.input}
                value={selectedEmployeeId}
                onChange={(e) => handleEmployeeChange(e.target.value)}
                disabled={employeesLoading}
              >
                <option value="">-- Choose an employee --</option>
                {employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {`${emp.first_name || ''} ${emp.last_name || ''}`.trim() || emp.email} ({emp.employee_code})
                  </option>
                ))}
              </select>
            </div>

            {balancesLoading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '16px 0' }}>
                <Loader2 size={24} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
              </div>
            ) : selectedEmployeeId ? (
              employeeBalances.length === 0 ? (
                <div style={{ fontSize: '13px', color: 'var(--color-text-muted)', fontStyle: 'italic', padding: '8px 0' }}>
                  No leave balances found for this employee in the current active cycle.
                </div>
              ) : (
                <>
                  <div>
                    <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', fontWeight: 600 }}>
                      Select Leave Balance *
                    </label>
                    <select
                      style={styles.input}
                      value={selectedBalanceId ?? ''}
                      onChange={(e) => setSelectedBalanceId(Number(e.target.value))}
                    >
                      <option value="">-- Select leave type balance --</option>
                      {employeeBalances.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.leave_type_name} (Remaining: {b.remaining}d | Allocated: {b.allocated}d | Used: {b.used}d | Adj: {b.adjustment}d)
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', fontWeight: 600 }}>
                      Adjustment Amount (Days) *
                    </label>
                    <input
                      type="number"
                      step="0.5"
                      style={styles.input}
                      placeholder="e.g. 2.0 (credit) or -1.0 (debit)"
                      value={adjustAmount}
                      onChange={(e) => setAdjustAmount(e.target.value)}
                    />
                    <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                      Positive values credit leaves; negative values debit leaves.
                    </span>
                  </div>

                  <div>
                    <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', fontWeight: 600 }}>
                      Adjustment Reason *
                    </label>
                    <input
                      type="text"
                      style={styles.input}
                      placeholder="e.g. Compensatory off granted for weekend production deployment"
                      value={adjustReason}
                      onChange={(e) => setAdjustReason(e.target.value)}
                    />
                  </div>
                </>
              )
            ) : null}
          </div>
        </Modal>
      )}
    </div>
  );
}
