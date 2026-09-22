import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  shiftAssignmentService,
  type EmployeeShiftAssignment,
  type CreateShiftAssignmentPayload,
  type UpdateShiftAssignmentPayload,
  ApiError,
} from '../../services/shiftAssignment';
import { shiftService, type Shift } from '../../services/shift';
import { employeeManagementService } from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { PageHeader } from '../../components/PageHeader';
import { AlertBanner } from '../../components/AlertBanner';
import {
  Plus,
  Edit2,
  Trash2,
  Clock,
  Loader2,
  AlertCircle,
  Search,
  CalendarOff,
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useBranchContext } from '../../contexts/BranchContext';

const getAssignmentStatus = (
  item: EmployeeShiftAssignment,
  todayStr: string
): { status: 'active' | 'upcoming' | 'expired'; label: string; badgeStatus: 'active' | 'pending' | 'inactive' } => {
  if (item.effective_from > todayStr) {
    return { status: 'upcoming', label: 'Upcoming', badgeStatus: 'pending' };
  }
  if (item.effective_to && item.effective_to < todayStr) {
    return { status: 'expired', label: 'Expired', badgeStatus: 'inactive' };
  }
  return { status: 'active', label: 'Active', badgeStatus: 'active' };
};

export const ShiftAssignmentsPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const { branchId, selectedBranch } = useBranchContext();

  const [assignments, setAssignments] = useState<EmployeeShiftAssignment[]>([]);
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [employees, setEmployees] = useState<EmployeeProfile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [shiftFilter, setShiftFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'upcoming' | 'expired'>('all');

  // Assign / Edit Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingAssignment, setEditingAssignment] = useState<EmployeeShiftAssignment | null>(null);
  const [modalFormData, setModalFormData] = useState<{
    employee: number | '';
    shift: number | '';
    effective_from: string;
    isOngoing: boolean;
    effective_to: string;
  }>({
    employee: '',
    shift: '',
    effective_from: '',
    isOngoing: true,
    effective_to: '',
  });
  const [modalError, setModalError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // End Assignment Modal State
  const [endItem, setEndItem] = useState<EmployeeShiftAssignment | null>(null);
  const [endDate, setEndDate] = useState('');
  const [endError, setEndError] = useState<string | null>(null);
  const [ending, setEnding] = useState(false);

  // Delete Modal State
  const [deleteConfirmItem, setDeleteConfirmItem] = useState<EmployeeShiftAssignment | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  const canManage = hasPermission('shift_assignment.manage');
  const isAllLocations = branchId === null || branchId === undefined;

  const todayStr = useMemo(() => {
    const d = new Date();
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }, []);

  const employeeMap = useMemo(() => {
    const map = new Map<number, EmployeeProfile>();
    for (const emp of employees) {
      map.set(emp.id, emp);
    }
    return map;
  }, [employees]);

  const shiftMap = useMemo(() => {
    const map = new Map<number, Shift>();
    for (const s of shifts) {
      map.set(s.id, s);
    }
    return map;
  }, [shifts]);

  const loadData = useCallback(async () => {
    if (!hasPermission('shift_assignment.view')) {
      setAssignments([]);
      setShifts([]);
      setEmployees([]);
      setLoading(false);
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    if (branchId === null || branchId === undefined) {
      setAssignments([]);
      setShifts([]);
      setEmployees([]);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      setLoading(true);
      setError(null);

      const [assignmentsData, shiftsData, employeesData] = await Promise.all([
        shiftAssignmentService.listAssignments({ branch_id: branchId }, { signal: controller.signal }),
        shiftService.listShifts({ branch_id: branchId }, { signal: controller.signal }),
        employeeManagementService.listEmployees({ branch_id: branchId, status: 'active' }, { signal: controller.signal }),
      ]);

      if (abortControllerRef.current === controller) {
        setAssignments(Array.isArray(assignmentsData) ? assignmentsData : []);
        setShifts(Array.isArray(shiftsData) ? shiftsData : []);
        setEmployees(Array.isArray(employeesData) ? employeesData : []);
      }
    } catch (err: any) {
      if (err.name === 'AbortError') return;
      if (abortControllerRef.current === controller) {
        if (err?.status === 403 || err?.response?.status === 403) {
          setError('403 Forbidden: You do not have permission to view shift assignments.');
        } else if (err instanceof ApiError && err.errorData?.detail) {
          setError(err.errorData.detail);
        } else {
          setError('Failed to load shift assignments. Backend might be unavailable.');
        }
        setAssignments([]);
        setShifts([]);
        setEmployees([]);
      }
    } finally {
      if (abortControllerRef.current === controller) {
        setLoading(false);
      }
    }
  }, [branchId, hasPermission]);

  useEffect(() => {
    setAssignments([]);
    setShifts([]);
    setEmployees([]);
    setSearchQuery('');
    setShiftFilter('all');
    setStatusFilter('all');
    setError(null);
    setSuccessMessage(null);
    loadData();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [loadData]);

  // Client-side filtering
  const filteredAssignments = useMemo(() => {
    return assignments.filter((item) => {
      if (shiftFilter !== 'all' && String(item.shift) !== shiftFilter) {
        return false;
      }
      const { status } = getAssignmentStatus(item, todayStr);
      if (statusFilter !== 'all' && status !== statusFilter) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const emp = employeeMap.get(item.employee);
        const name = emp ? `${emp.first_name} ${emp.last_name}`.toLowerCase() : '';
        const code = emp?.employee_code ? emp.employee_code.toLowerCase() : '';
        if (!name.includes(q) && !code.includes(q)) {
          return false;
        }
      }
      return true;
    });
  }, [assignments, shiftFilter, statusFilter, searchQuery, employeeMap, todayStr]);

  const openCreateModal = () => {
    if (isAllLocations || !canManage) return;
    setEditingAssignment(null);
    setModalFormData({
      employee: employees.length > 0 ? employees[0].id : '',
      shift: shifts.length > 0 ? shifts[0].id : '',
      effective_from: todayStr,
      isOngoing: true,
      effective_to: '',
    });
    setModalError(null);
    setIsModalOpen(true);
  };

  const openEditModal = (item: EmployeeShiftAssignment) => {
    if (isAllLocations || !canManage) return;
    setEditingAssignment(item);
    setModalFormData({
      employee: item.employee,
      shift: item.shift,
      effective_from: item.effective_from,
      isOngoing: !item.effective_to,
      effective_to: item.effective_to || '',
    });
    setModalError(null);
    setIsModalOpen(true);
  };

  const openEndModal = (item: EmployeeShiftAssignment) => {
    if (isAllLocations || !canManage) return;
    setEndItem(item);
    // Default end date to today (or effective_from if effective_from is in future)
    const defaultDate = item.effective_from > todayStr ? item.effective_from : todayStr;
    setEndDate(defaultDate);
    setEndError(null);
  };

  const handleSaveModal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modalFormData.employee) {
      setModalError('Please select an employee.');
      return;
    }
    if (!modalFormData.shift) {
      setModalError('Please select a shift.');
      return;
    }
    if (!modalFormData.effective_from) {
      setModalError('Effective from date is required.');
      return;
    }
    if (!modalFormData.isOngoing && !modalFormData.effective_to) {
      setModalError('Please specify an effective to date or mark as ongoing.');
      return;
    }
    if (!modalFormData.isOngoing && modalFormData.effective_to < modalFormData.effective_from) {
      setModalError('Effective to date cannot be earlier than effective from date.');
      return;
    }

    setSaving(true);
    setModalError(null);

    const effectiveToPayload = modalFormData.isOngoing ? null : modalFormData.effective_to;

    try {
      if (editingAssignment) {
        const payload: UpdateShiftAssignmentPayload = {
          shift: Number(modalFormData.shift),
          effective_from: modalFormData.effective_from,
          effective_to: effectiveToPayload,
        };
        await shiftAssignmentService.update(editingAssignment.id, payload);
        setSuccessMessage('Shift assignment updated successfully.');
      } else {
        const payload: CreateShiftAssignmentPayload = {
          employee: Number(modalFormData.employee),
          shift: Number(modalFormData.shift),
          effective_from: modalFormData.effective_from,
          effective_to: effectiveToPayload,
        };
        await shiftAssignmentService.create(payload);
        setSuccessMessage('Shift assignment created successfully.');
      }
      setIsModalOpen(false);
      loadData();
    } catch (err: any) {
      if (err?.errorData) {
        if (err.errorData.effective_from) {
          const msg = Array.isArray(err.errorData.effective_from)
            ? err.errorData.effective_from[0]
            : err.errorData.effective_from;
          setModalError(msg);
        } else if (err.errorData.effective_to) {
          const msg = Array.isArray(err.errorData.effective_to)
            ? err.errorData.effective_to[0]
            : err.errorData.effective_to;
          setModalError(msg);
        } else if (err.errorData.employee) {
          const msg = Array.isArray(err.errorData.employee)
            ? err.errorData.employee[0]
            : err.errorData.employee;
          setModalError(msg);
        } else if (err.errorData.shift) {
          const msg = Array.isArray(err.errorData.shift)
            ? err.errorData.shift[0]
            : err.errorData.shift;
          setModalError(msg);
        } else if (err.errorData.detail) {
          setModalError(err.errorData.detail);
        } else if (err.errorData.non_field_errors) {
          setModalError(err.errorData.non_field_errors[0]);
        } else {
          setModalError('Failed to save shift assignment. Please check input values.');
        }
      } else if (err.status === 403 || err.response?.status === 403) {
        setModalError('403 Forbidden: You do not have permission to manage shift assignments.');
      } else {
        setModalError('Failed to save shift assignment.');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleEndAssignment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!endItem) return;

    if (!endDate) {
      setEndError('End date is required.');
      return;
    }
    if (endDate < endItem.effective_from) {
      setEndError('End date cannot be earlier than assignment effective from date.');
      return;
    }

    setEnding(true);
    setEndError(null);

    try {
      await shiftAssignmentService.update(endItem.id, { effective_to: endDate });
      setSuccessMessage('Shift assignment ended successfully.');
      setEndItem(null);
      loadData();
    } catch (err: any) {
      if (err instanceof ApiError && err.errorData?.effective_to) {
        const msg = Array.isArray(err.errorData.effective_to)
          ? err.errorData.effective_to[0]
          : err.errorData.effective_to;
        setEndError(msg);
      } else if (err.errorData?.detail) {
        setEndError(err.errorData.detail);
      } else {
        setEndError('Failed to end shift assignment.');
      }
    } finally {
      setEnding(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirmItem) return;
    setDeleting(true);
    setDeleteError(null);

    try {
      await shiftAssignmentService.delete(deleteConfirmItem.id);
      setSuccessMessage('Shift assignment deleted successfully.');
      setDeleteConfirmItem(null);
      loadData();
    } catch (err: any) {
      if (err.status === 403 || err.response?.status === 403) {
        setDeleteError('403 Forbidden: You do not have permission to delete shift assignments.');
      } else if (err.errorData?.detail) {
        setDeleteError(err.errorData.detail);
      } else {
        setDeleteError('Failed to delete shift assignment.');
      }
    } finally {
      setDeleting(false);
    }
  };

  if (!hasPermission('shift_assignment.view')) {
    return (
      <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
        <PageHeader title="Shift Assignments" subtitle="Manage employee shift assignments." />
        <AlertBanner type="error" message="403 Forbidden: You do not have permission to view shift assignments." />
      </div>
    );
  }

  const branchTitle = selectedBranch.type === 'branch' && selectedBranch.branch?.name
    ? `Branch: ${selectedBranch.branch.name}`
    : 'All Locations';

  const columns = [
    {
      key: 'employee',
      title: 'Employee',
      render: (item: EmployeeShiftAssignment) => {
        const emp = employeeMap.get(item.employee);
        return (
          <div>
            <div style={{ fontWeight: 600, color: 'var(--color-text-main)' }}>
              {emp ? `${emp.first_name} ${emp.last_name}` : `Employee #${item.employee}`}
            </div>
            {emp?.department_name && (
              <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                {emp.department_name} {emp.team_name ? `• ${emp.team_name}` : ''}
              </span>
            )}
          </div>
        );
      },
    },
    {
      key: 'employee_code',
      title: 'Employee Code',
      render: (item: EmployeeShiftAssignment) => {
        const emp = employeeMap.get(item.employee);
        return (
          <span style={{ fontVariantNumeric: 'tabular-nums', fontSize: '0.875rem' }}>
            {emp?.employee_code || '—'}
          </span>
        );
      },
    },
    {
      key: 'shift',
      title: 'Shift',
      render: (item: EmployeeShiftAssignment) => {
        const s = shiftMap.get(item.shift);
        return (
          <span style={{ fontWeight: 500 }}>
            {s ? s.name : `Shift #${item.shift}`}
          </span>
        );
      },
    },
    {
      key: 'timing',
      title: 'Timing',
      render: (item: EmployeeShiftAssignment) => {
        const s = shiftMap.get(item.shift);
        if (!s) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>;
        return (
          <span style={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', fontSize: '0.875rem' }}>
            {s.start_time?.slice(0, 5)} – {s.end_time?.slice(0, 5)}
          </span>
        );
      },
    },
    {
      key: 'effective_from',
      title: 'Effective From',
      render: (item: EmployeeShiftAssignment) => (
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>{item.effective_from}</span>
      ),
    },
    {
      key: 'effective_to',
      title: 'Effective To',
      render: (item: EmployeeShiftAssignment) => (
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>
          {item.effective_to ? (
            item.effective_to
          ) : (
            <span style={{ color: 'var(--color-text-muted)', fontStyle: 'italic' }}>Ongoing</span>
          )}
        </span>
      ),
    },
    {
      key: 'status',
      title: 'Status',
      render: (item: EmployeeShiftAssignment) => {
        const { label, badgeStatus } = getAssignmentStatus(item, todayStr);
        return <StatusBadge status={badgeStatus} label={label} />;
      },
    },
    ...(canManage && !isAllLocations
      ? [
          {
            key: 'actions',
            title: 'Actions',
            render: (item: EmployeeShiftAssignment) => {
              const { status } = getAssignmentStatus(item, todayStr);
              const isEndable = status === 'active' || !item.effective_to;
              const emp = employeeMap.get(item.employee);
              const empName = emp ? `${emp.first_name} ${emp.last_name}` : `Employee #${item.employee}`;

              return (
                <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  {isEndable && (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => openEndModal(item)}
                      title="End Assignment"
                      aria-label={`End assignment for ${empName}`}
                      type="button"
                      style={{ padding: '4px 8px', fontSize: 'var(--font-size-xs)' }}
                    >
                      <CalendarOff size={13} style={{ marginRight: '4px' }} />
                      <span>End</span>
                    </button>
                  )}
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => openEditModal(item)}
                    title="Edit Assignment"
                    aria-label={`Edit assignment for ${empName}`}
                    type="button"
                    style={{ padding: '4px 8px' }}
                  >
                    <Edit2 size={13} />
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      setDeleteConfirmItem(item);
                      setDeleteError(null);
                    }}
                    title="Delete Assignment"
                    aria-label={`Delete assignment for ${empName}`}
                    type="button"
                    style={{ padding: '4px 8px', color: 'var(--color-status-danger)' }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              );
            },
          },
        ]
      : []),
  ];

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      {/* Header section */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--spacing-md)' }}>
        <PageHeader
          title="Shift Assignments"
          subtitle={`Manage employee work schedules and shift assignments for ${branchTitle}.`}
        />
        {canManage && !isAllLocations && (
          <button
            className="btn btn-primary"
            onClick={openCreateModal}
            type="button"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
          >
            <Plus size={16} />
            <span>Assign Shift</span>
          </button>
        )}
      </div>

      {/* All Locations Warning */}
      {isAllLocations && (
        <AlertBanner
          type="info"
          message="Select a specific branch from the header to view and manage shift assignments."
        />
      )}

      {error && <AlertBanner type="error" message={error} />}
      {successMessage && <AlertBanner type="success" message={successMessage} />}

      {/* Main Content (Branch Mode) */}
      {!isAllLocations && (
        <>
          {/* Filter Bar */}
          <div
            style={{
              display: 'flex',
              gap: 'var(--spacing-md)',
              alignItems: 'center',
              flexWrap: 'wrap',
              backgroundColor: 'var(--color-bg-card)',
              padding: 'var(--spacing-md)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border)',
            }}
          >
            {/* Search */}
            <div style={{ position: 'relative', flex: '1 1 240px', minWidth: '200px' }}>
              <Search
                size={16}
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--color-text-muted)',
                }}
              />
              <input
                type="text"
                className="form-input"
                placeholder="Search by employee name or code…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ paddingLeft: '36px', width: '100%' }}
                aria-label="Search by employee name or code"
              />
            </div>

            {/* Shift Filter */}
            <div style={{ minWidth: '180px' }}>
              <select
                className="form-select"
                value={shiftFilter}
                onChange={(e) => setShiftFilter(e.target.value)}
                aria-label="Filter by shift"
                style={{ width: '100%' }}
              >
                <option value="all">All Shifts</option>
                {shifts.map((s) => (
                  <option key={s.id} value={String(s.id)}>
                    {s.name} ({s.start_time?.slice(0, 5)} - {s.end_time?.slice(0, 5)})
                  </option>
                ))}
              </select>
            </div>

            {/* Status Filter */}
            <div style={{ minWidth: '140px' }}>
              <select
                className="form-select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as any)}
                aria-label="Filter by status"
                style={{ width: '100%' }}
              >
                <option value="all">All Statuses</option>
                <option value="active">Active</option>
                <option value="upcoming">Upcoming</option>
                <option value="expired">Expired</option>
              </select>
            </div>
          </div>

          {/* Table Card */}
          <Card noPadding>
            {loading ? (
              <div className="loading-center" style={{ padding: 'var(--spacing-2xl)' }}>
                <Loader2 size={28} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
                <span style={{ marginTop: '8px' }}>Loading shift assignments…</span>
              </div>
            ) : (
              <Table
                columns={columns}
                data={filteredAssignments}
                keyExtractor={(item) => item.id.toString()}
                emptyIcon={Clock}
                emptyTitle="No shift assignments found"
                emptyDescription={
                  assignments.length === 0
                    ? 'No employees have been assigned to shifts in this branch yet.'
                    : 'No assignments match the selected filters.'
                }
              />
            )}
          </Card>
        </>
      )}

      {/* Assign / Edit Shift Modal */}
      {isModalOpen && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="shift-assignment-modal-title">
          <div className="modal-content" style={{ maxWidth: '520px' }}>
            <h2 id="shift-assignment-modal-title" style={{ margin: '0 0 var(--spacing-md) 0', fontSize: '1.25rem' }}>
              {editingAssignment ? 'Edit Shift Assignment' : 'Assign Employee Shift'}
            </h2>

            {modalError && (
              <AlertBanner type="error" message={modalError} style={{ marginBottom: 'var(--spacing-md)' }} />
            )}

            <form onSubmit={handleSaveModal} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
              {/* Employee Selector */}
              <div className="form-group">
                <label className="form-label" htmlFor="assignment-employee-select">
                  Employee <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                </label>
                {editingAssignment ? (
                  <input
                    type="text"
                    id="assignment-employee-select"
                    className="form-input"
                    disabled
                    value={(() => {
                      const emp = employeeMap.get(editingAssignment.employee);
                      return emp ? `${emp.first_name} ${emp.last_name} (${emp.employee_code})` : `Employee #${editingAssignment.employee}`;
                    })()}
                  />
                ) : (
                  <select
                    id="assignment-employee-select"
                    className="form-select"
                    value={modalFormData.employee}
                    onChange={(e) => setModalFormData({ ...modalFormData, employee: Number(e.target.value) || '' })}
                    required
                  >
                    <option value="" disabled>Select an employee…</option>
                    {employees.map((emp) => (
                      <option key={emp.id} value={emp.id}>
                        {emp.first_name} {emp.last_name} ({emp.employee_code})
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* Shift Selector */}
              <div className="form-group">
                <label className="form-label" htmlFor="assignment-shift-select">
                  Shift <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                </label>
                <select
                  id="assignment-shift-select"
                  className="form-select"
                  value={modalFormData.shift}
                  onChange={(e) => setModalFormData({ ...modalFormData, shift: Number(e.target.value) || '' })}
                  required
                >
                  <option value="" disabled>Select a shift…</option>
                  {shifts
                    .filter((s) => s.is_active)
                    .map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({s.start_time?.slice(0, 5)} - {s.end_time?.slice(0, 5)})
                      </option>
                    ))}
                </select>
              </div>

              {/* Effective From */}
              <div className="form-group">
                <label className="form-label" htmlFor="assignment-from-input">
                  Effective From <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                </label>
                <input
                  type="date"
                  id="assignment-from-input"
                  className="form-input"
                  value={modalFormData.effective_from}
                  onChange={(e) => setModalFormData({ ...modalFormData, effective_from: e.target.value })}
                  required
                />
              </div>

              {/* Ongoing Toggle */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input
                  type="checkbox"
                  id="assignment-ongoing-toggle"
                  checked={modalFormData.isOngoing}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    setModalFormData({
                      ...modalFormData,
                      isOngoing: checked,
                      effective_to: checked ? '' : modalFormData.effective_to || modalFormData.effective_from,
                    });
                  }}
                />
                <label htmlFor="assignment-ongoing-toggle" style={{ cursor: 'pointer', fontSize: '0.9rem' }}>
                  Ongoing assignment (no end date)
                </label>
              </div>

              {/* Effective To */}
              {!modalFormData.isOngoing && (
                <div className="form-group">
                  <label className="form-label" htmlFor="assignment-to-input">
                    Effective To <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                  </label>
                  <input
                    type="date"
                    id="assignment-to-input"
                    className="form-input"
                    value={modalFormData.effective_to}
                    onChange={(e) => setModalFormData({ ...modalFormData, effective_to: e.target.value })}
                    required={!modalFormData.isOngoing}
                    min={modalFormData.effective_from}
                  />
                </div>
              )}

              {/* Inclusive date helper notice */}
              <div
                style={{
                  backgroundColor: 'var(--color-bg-body)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '10px 12px',
                  fontSize: '0.8rem',
                  color: 'var(--color-text-muted)',
                  lineHeight: 1.4,
                }}
              >
                <strong>Date Policy:</strong> Assignment dates are inclusive. If one assignment ends on September 30, the next assignment can begin on October 1.
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: 'var(--spacing-md)' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsModalOpen(false)}
                  disabled={saving}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={saving}
                  aria-label={editingAssignment ? 'Update Assignment' : 'Save Shift Assignment'}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                >
                  {saving && <Loader2 size={14} className="animate-spin" />}
                  <span>{saving ? 'Saving…' : editingAssignment ? 'Update Assignment' : 'Assign Shift'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* End Assignment Quick Modal */}
      {endItem !== null && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="end-assignment-title">
          <div className="modal-content" style={{ maxWidth: '460px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: 'var(--spacing-md)' }}>
              <div style={{ padding: '8px', borderRadius: '50%', backgroundColor: 'rgba(234, 134, 0, 0.1)', color: 'var(--color-status-warning, #f59e0b)' }}>
                <CalendarOff size={22} />
              </div>
              <h2 id="end-assignment-title" style={{ margin: 0, fontSize: '1.15rem' }}>
                End Shift Assignment
              </h2>
            </div>

            {endError && (
              <AlertBanner type="error" message={endError} style={{ marginBottom: 'var(--spacing-md)' }} />
            )}

            <form onSubmit={handleEndAssignment} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
              <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', margin: 0 }}>
                Specify the final active date for this shift assignment for{' '}
                <strong style={{ color: 'var(--color-text-main)' }}>
                  {(() => {
                    const emp = employeeMap.get(endItem.employee);
                    return emp ? `${emp.first_name} ${emp.last_name}` : `Employee #${endItem.employee}`;
                  })()}
                </strong>.
              </p>

              <div className="form-group">
                <label className="form-label" htmlFor="end-assignment-date-input">
                  Effective End Date <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                </label>
                <input
                  type="date"
                  id="end-assignment-date-input"
                  className="form-input"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  min={endItem.effective_from}
                  required
                />
              </div>

              <div
                style={{
                  backgroundColor: 'var(--color-bg-body)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '8px 12px',
                  fontSize: '0.8rem',
                  color: 'var(--color-text-muted)',
                  lineHeight: 1.4,
                }}
              >
                Assignment dates are inclusive. If ended on <strong>{endDate || 'this date'}</strong>, a new assignment for this employee can begin on the next calendar day.
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: 'var(--spacing-md)' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setEndItem(null)}
                  disabled={ending}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={ending}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                >
                  {ending && <Loader2 size={14} className="animate-spin" />}
                  <span>{ending ? 'Ending…' : 'Confirm End Date'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmItem !== null && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="delete-shift-assignment-title">
          <div className="modal-content" style={{ maxWidth: '440px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: 'var(--spacing-md)' }}>
              <div style={{ padding: '8px', borderRadius: '50%', backgroundColor: 'rgba(234, 84, 85, 0.1)', color: 'var(--color-status-danger)' }}>
                <AlertCircle size={22} />
              </div>
              <h2 id="delete-shift-assignment-title" style={{ margin: 0, fontSize: '1.15rem' }}>
                Confirm Assignment Deletion
              </h2>
            </div>

            {deleteError && (
              <AlertBanner type="error" message={deleteError} style={{ marginBottom: 'var(--spacing-md)' }} />
            )}

            <div style={{ fontSize: '0.9rem', color: 'var(--color-text-muted)', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: 'var(--spacing-lg)' }}>
              <p style={{ margin: 0 }}>
                Are you sure you want to permanently delete this shift assignment?
              </p>
              <div
                style={{
                  backgroundColor: 'var(--color-bg-body)',
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                  fontSize: '0.85rem',
                }}
              >
                <div>
                  <strong>Employee:</strong>{' '}
                  {(() => {
                    const emp = employeeMap.get(deleteConfirmItem.employee);
                    return emp ? `${emp.first_name} ${emp.last_name} (${emp.employee_code})` : `Employee #${deleteConfirmItem.employee}`;
                  })()}
                </div>
                <div>
                  <strong>Shift:</strong>{' '}
                  {(() => {
                    const s = shiftMap.get(deleteConfirmItem.shift);
                    return s ? `${s.name} (${s.start_time?.slice(0, 5)} - ${s.end_time?.slice(0, 5)})` : `Shift #${deleteConfirmItem.shift}`;
                  })()}
                </div>
                <div>
                  <strong>Effective:</strong> {deleteConfirmItem.effective_from} to{' '}
                  {deleteConfirmItem.effective_to || 'Ongoing'}
                </div>
              </div>
              <p style={{ margin: 0, color: 'var(--color-status-danger)', fontSize: '0.8rem', fontWeight: 500 }}>
                Warning: Deletion is permanent. Attendance calculations for days during this period will raise configuration errors if no other assignment covers them.
              </p>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setDeleteConfirmItem(null)}
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                style={{ backgroundColor: 'var(--color-status-danger)', borderColor: 'var(--color-status-danger)' }}
                onClick={handleDelete}
                disabled={deleting}
              >
                {deleting ? 'Deleting…' : 'Delete Assignment'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
