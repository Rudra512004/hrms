import React, { useState, useEffect, useCallback, useRef } from 'react';
import { shiftService, type Shift, type CreateShiftPayload, type UpdateShiftPayload } from '../../services/shift';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { PageHeader } from '../../components/PageHeader';
import { AlertBanner } from '../../components/AlertBanner';
import { Plus, Edit2, Trash2, Clock, Loader2, AlertCircle } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useBranchContext } from '../../contexts/BranchContext';

const DAYS_OF_WEEK = [
  { id: 0, label: 'Mon', fullLabel: 'Monday' },
  { id: 1, label: 'Tue', fullLabel: 'Tuesday' },
  { id: 2, label: 'Wed', fullLabel: 'Wednesday' },
  { id: 3, label: 'Thu', fullLabel: 'Thursday' },
  { id: 4, label: 'Fri', fullLabel: 'Friday' },
  { id: 5, label: 'Sat', fullLabel: 'Saturday' },
  { id: 6, label: 'Sun', fullLabel: 'Sunday' },
];

const parseWorkDaysString = (str: string | undefined): number[] => {
  if (!str || !str.trim()) return [];
  return str
    .split(',')
    .map((d) => parseInt(d.trim(), 10))
    .filter((d) => !isNaN(d) && d >= 0 && d <= 6);
};

const formatWorkDaysDisplay = (str: string | undefined): string => {
  const days = parseWorkDaysString(str);
  if (days.length === 0) return 'None';
  if (days.length === 7) return 'All Days';
  return days
    .sort((a, b) => a - b)
    .map((d) => DAYS_OF_WEEK.find((item) => item.id === d)?.label || d)
    .join(', ');
};

export const ShiftsPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const { branchId, selectedBranch } = useBranchContext();

  const [shifts, setShifts] = useState<Shift[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Modal states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingShift, setEditingShift] = useState<Shift | null>(null);
  const [formData, setFormData] = useState<{
    name: string;
    start_time: string;
    end_time: string;
    grace_period: string;
    full_day_hours: string;
    half_day_hours: string;
    selectedDays: number[];
    is_active: boolean;
  }>({
    name: '',
    start_time: '09:00',
    end_time: '18:00',
    grace_period: '00:15:00',
    full_day_hours: '08:00:00',
    half_day_hours: '04:00:00',
    selectedDays: [0, 1, 2, 3, 4],
    is_active: true,
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Delete confirmation state
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Stale request controller ref
  const abortControllerRef = useRef<AbortController | null>(null);

  const canManage = hasPermission('shift.manage');
  const isAllLocations = branchId === null;

  const loadShifts = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      setLoading(true);
      setError(null);

      const params = isAllLocations ? {} : { branch_id: branchId };
      const data = await shiftService.listShifts(params, { signal: controller.signal });

      if (abortControllerRef.current === controller) {
        setShifts(Array.isArray(data) ? data : []);
      }
    } catch (err: any) {
      if (err.name === 'AbortError') return;
      if (abortControllerRef.current === controller) {
        if (err?.status === 403 || err?.response?.status === 403) {
          setError('403 Forbidden: You do not have permission to view shifts.');
        } else if (err?.errorData?.detail) {
          setError(err.errorData.detail);
        } else {
          setError('Failed to load shifts.');
        }
        setShifts([]);
      }
    } finally {
      if (abortControllerRef.current === controller) {
        setLoading(false);
      }
    }
  }, [branchId, isAllLocations]);

  useEffect(() => {
    setShifts([]);
    loadShifts();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [loadShifts]);

  const openCreateModal = () => {
    if (isAllLocations) return;
    setEditingShift(null);
    setFormData({
      name: '',
      start_time: '09:00',
      end_time: '18:00',
      grace_period: '00:15:00',
      full_day_hours: '08:00:00',
      half_day_hours: '04:00:00',
      selectedDays: [0, 1, 2, 3, 4],
      is_active: true,
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  const openEditModal = (shift: Shift) => {
    if (isAllLocations) return;
    setEditingShift(shift);
    setFormData({
      name: shift.name,
      start_time: shift.start_time?.slice(0, 5) || '09:00',
      end_time: shift.end_time?.slice(0, 5) || '18:00',
      grace_period: shift.grace_period || '',
      full_day_hours: shift.full_day_hours || '',
      half_day_hours: shift.half_day_hours || '',
      selectedDays: parseWorkDaysString(shift.work_days),
      is_active: shift.is_active,
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  const toggleDay = (dayId: number) => {
    setFormData((prev) => {
      const exists = prev.selectedDays.includes(dayId);
      const newDays = exists
        ? prev.selectedDays.filter((d) => d !== dayId)
        : [...prev.selectedDays, dayId].sort((a, b) => a - b);
      return { ...prev, selectedDays: newDays };
    });
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      setFormError('Shift name is required.');
      return;
    }
    if (!formData.start_time || !formData.end_time) {
      setFormError('Start time and End time are required.');
      return;
    }
    if (formData.selectedDays.length === 0) {
      setFormError('Select at least one work day for this shift.');
      return;
    }
    if (!branchId) {
      setFormError('Select a branch from the header to manage this configuration.');
      return;
    }

    setSaving(true);
    setFormError(null);

    const serializedWorkDays = formData.selectedDays.sort((a, b) => a - b).join(',');

    try {
      if (editingShift) {
        const payload: UpdateShiftPayload = {
          name: formData.name.trim(),
          start_time: formData.start_time.length === 5 ? `${formData.start_time}:00` : formData.start_time,
          end_time: formData.end_time.length === 5 ? `${formData.end_time}:00` : formData.end_time,
          grace_period: formData.grace_period.trim() || null,
          full_day_hours: formData.full_day_hours.trim() || null,
          half_day_hours: formData.half_day_hours.trim() || null,
          work_days: serializedWorkDays,
          is_active: formData.is_active,
        };
        await shiftService.update(editingShift.id, payload);
        setSuccessMessage('Shift updated successfully.');
      } else {
        const payload: CreateShiftPayload = {
          branch: branchId,
          name: formData.name.trim(),
          start_time: formData.start_time.length === 5 ? `${formData.start_time}:00` : formData.start_time,
          end_time: formData.end_time.length === 5 ? `${formData.end_time}:00` : formData.end_time,
          grace_period: formData.grace_period.trim() || null,
          full_day_hours: formData.full_day_hours.trim() || null,
          half_day_hours: formData.half_day_hours.trim() || null,
          work_days: serializedWorkDays,
          is_active: formData.is_active,
        };
        await shiftService.create(payload);
        setSuccessMessage('Shift created successfully.');
      }
      setIsModalOpen(false);
      loadShifts();
    } catch (err: any) {
      if (err.errorData?.name) {
        setFormError(err.errorData.name[0]);
      } else if (err.errorData?.work_days) {
        setFormError(err.errorData.work_days[0]);
      } else if (err.errorData?.start_time) {
        setFormError(err.errorData.start_time[0]);
      } else if (err.errorData?.end_time) {
        setFormError(err.errorData.end_time[0]);
      } else if (err.errorData?.grace_period) {
        setFormError(err.errorData.grace_period[0]);
      } else if (err.errorData?.non_field_errors) {
        setFormError(err.errorData.non_field_errors[0]);
      } else if (err.errorData?.detail) {
        setFormError(err.errorData.detail);
      } else if (err.status === 403 || err.response?.status === 403) {
        setFormError('403 Forbidden: You do not have permission to manage shifts.');
      } else {
        setFormError('Failed to save shift. Please check input values.');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (isAllLocations) return;
    try {
      setDeleting(true);
      await shiftService.delete(id);
      setSuccessMessage('Shift deleted successfully.');
      setDeleteConfirmId(null);
      loadShifts();
    } catch (err: any) {
      if (err.status === 403 || err.response?.status === 403) {
        setError('403 Forbidden: You do not have permission to delete shifts.');
      } else if (err.errorData?.detail) {
        setError(err.errorData.detail);
      } else {
        setError('Failed to delete shift.');
      }
    } finally {
      setDeleting(false);
    }
  };

  if (!hasPermission('shift.view')) {
    return (
      <div className="animate-fade-in">
        <PageHeader title="Shift Management" subtitle="Branch shifts configuration." />
        <AlertBanner type="error" message="You do not have permission to view shifts." />
      </div>
    );
  }

  const branchTitle = selectedBranch.type === 'branch' && selectedBranch.branch?.name
    ? `Branch: ${selectedBranch.branch.name}`
    : 'All Locations';

  const columns = [
    {
      key: 'name',
      title: 'Shift Name',
      render: (s: Shift) => <span style={{ fontWeight: 600 }}>{s.name}</span>,
    },
    {
      key: 'timing',
      title: 'Timing',
      render: (s: Shift) => (
        <span style={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
          {s.start_time?.slice(0, 5)} – {s.end_time?.slice(0, 5)}
        </span>
      ),
    },
    {
      key: 'work_days',
      title: 'Work Days',
      render: (s: Shift) => (
        <span style={{ fontSize: 'var(--font-size-xs)' }}>{formatWorkDaysDisplay(s.work_days)}</span>
      ),
    },
    {
      key: 'grace_period',
      title: 'Grace Period',
      render: (s: Shift) => (
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>{s.grace_period || '—'}</span>
      ),
    },
    {
      key: 'durations',
      title: 'Full / Half Day',
      render: (s: Shift) => (
        <span style={{ fontVariantNumeric: 'tabular-nums', fontSize: 'var(--font-size-xs)' }}>
          {s.full_day_hours || '—'} / {s.half_day_hours || '—'}
        </span>
      ),
    },
    {
      key: 'is_active',
      title: 'Status',
      render: (s: Shift) => (
        <StatusBadge status={s.is_active ? 'active' : 'inactive'} label={s.is_active ? 'Active' : 'Inactive'} />
      ),
    },
    ...(canManage && !isAllLocations
      ? [
          {
            key: 'actions',
            title: 'Actions',
            render: (s: Shift) => (
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => openEditModal(s)}
                  title="Edit Shift"
                  aria-label={`Edit ${s.name}`}
                  type="button"
                  style={{ padding: '4px 8px' }}
                >
                  <Edit2 size={14} />
                </button>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setDeleteConfirmId(s.id)}
                  title="Delete Shift"
                  aria-label={`Delete ${s.name}`}
                  type="button"
                  style={{ padding: '4px 8px', color: 'var(--color-status-danger)' }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--spacing-md)' }}>
        <PageHeader
          title="Shift Management"
          subtitle={`Configure work shifts and schedules for ${branchTitle}.`}
        />
        {canManage && (
          <button
            className="btn btn-primary"
            onClick={openCreateModal}
            disabled={isAllLocations}
            title={isAllLocations ? 'Select a branch from the header to manage this configuration.' : 'Add a new shift'}
            type="button"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
          >
            <Plus size={16} />
            <span>Add Shift</span>
          </button>
        )}
      </div>

      {isAllLocations && (
        <AlertBanner
          type="info"
          message="Select a branch from the header to manage this configuration."
        />
      )}

      {error && <AlertBanner type="error" message={error} />}
      {successMessage && <AlertBanner type="success" message={successMessage} />}

      <Card noPadding>
        {loading ? (
          <div className="loading-center" style={{ padding: 'var(--spacing-2xl)' }}>
            <Loader2 size={28} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
            <span style={{ marginTop: '8px' }}>Loading shifts…</span>
          </div>
        ) : (
          <Table
            columns={columns}
            data={shifts}
            keyExtractor={(s) => s.id.toString()}
            emptyIcon={Clock}
            emptyTitle="No shifts configured"
            emptyDescription={
              isAllLocations
                ? 'No shifts found across authorized branches.'
                : 'No shifts configured for this branch yet.'
            }
          />
        )}
      </Card>

      {/* Add / Edit Shift Modal */}
      {isModalOpen && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="shift-modal-title">
          <div className="modal-content" style={{ maxWidth: '520px' }}>
            <h2 id="shift-modal-title" style={{ margin: '0 0 var(--spacing-md) 0', fontSize: '1.25rem' }}>
              {editingShift ? 'Edit Shift' : 'Add Shift'}
            </h2>

            {formError && <AlertBanner type="error" message={formError} style={{ marginBottom: 'var(--spacing-md)' }} />}

            <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
              <div>
                <label className="input-label" htmlFor="shift-name">
                  Shift Name <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                </label>
                <input
                  id="shift-name"
                  type="text"
                  className="input-field"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. Standard Morning Shift"
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-md)' }}>
                <div>
                  <label className="input-label" htmlFor="shift-start">
                    Start Time <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                  </label>
                  <input
                    id="shift-start"
                    type="time"
                    className="input-field"
                    value={formData.start_time}
                    onChange={(e) => setFormData({ ...formData, start_time: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="input-label" htmlFor="shift-end">
                    End Time <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                  </label>
                  <input
                    id="shift-end"
                    type="time"
                    className="input-field"
                    value={formData.end_time}
                    onChange={(e) => setFormData({ ...formData, end_time: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div>
                <label className="input-label" style={{ marginBottom: '6px' }}>
                  Work Days <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                </label>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }} role="group" aria-label="Work Days">
                  {DAYS_OF_WEEK.map((day) => {
                    const isSelected = formData.selectedDays.includes(day.id);
                    return (
                      <button
                        key={day.id}
                        type="button"
                        onClick={() => toggleDay(day.id)}
                        className={`btn btn-sm ${isSelected ? 'btn-primary' : 'btn-secondary'}`}
                        style={{
                          minWidth: '40px',
                          padding: '6px 10px',
                          fontWeight: isSelected ? 600 : 400,
                          borderRadius: 'var(--radius-full)',
                        }}
                        aria-pressed={isSelected}
                        title={day.fullLabel}
                      >
                        {day.label}
                      </button>
                    );
                  })}
                </div>
                <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                  Selected: {formatWorkDaysDisplay(formData.selectedDays.join(','))}
                </div>
              </div>

              <div>
                <label className="input-label" htmlFor="shift-grace">
                  Grace Period (e.g. 00:15:00)
                </label>
                <input
                  id="shift-grace"
                  type="text"
                  className="input-field"
                  value={formData.grace_period}
                  onChange={(e) => setFormData({ ...formData, grace_period: e.target.value })}
                  placeholder="00:15:00"
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-md)' }}>
                <div>
                  <label className="input-label" htmlFor="shift-full-day">
                    Full Day Hours
                  </label>
                  <input
                    id="shift-full-day"
                    type="text"
                    className="input-field"
                    value={formData.full_day_hours}
                    onChange={(e) => setFormData({ ...formData, full_day_hours: e.target.value })}
                    placeholder="08:00:00"
                  />
                </div>
                <div>
                  <label className="input-label" htmlFor="shift-half-day">
                    Half Day Hours
                  </label>
                  <input
                    id="shift-half-day"
                    type="text"
                    className="input-field"
                    value={formData.half_day_hours}
                    onChange={(e) => setFormData({ ...formData, half_day_hours: e.target.value })}
                    placeholder="04:00:00"
                  />
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                <input
                  id="shift-is-active"
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                />
                <label htmlFor="shift-is-active" style={{ cursor: 'pointer', fontSize: '0.9rem', fontWeight: 500 }}>
                  Active Shift
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: 'var(--spacing-lg)' }}>
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
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                >
                  {saving && <Loader2 size={14} className="animate-spin" />}
                  <span>{saving ? 'Saving…' : editingShift ? 'Update Shift' : 'Create Shift'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmId !== null && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="delete-shift-title">
          <div className="modal-content" style={{ maxWidth: '420px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: 'var(--spacing-md)' }}>
              <div style={{ padding: '8px', borderRadius: '50%', backgroundColor: 'rgba(234, 84, 85, 0.1)', color: 'var(--color-status-danger)' }}>
                <AlertCircle size={22} />
              </div>
              <h2 id="delete-shift-title" style={{ margin: 0, fontSize: '1.15rem' }}>
                Confirm Deletion
              </h2>
            </div>
            <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', marginBottom: 'var(--spacing-lg)' }}>
              Are you sure you want to delete this shift? Shifts assigned to employees cannot be safely removed.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setDeleteConfirmId(null)}
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                style={{ backgroundColor: 'var(--color-status-danger)', borderColor: 'var(--color-status-danger)' }}
                onClick={() => handleDelete(deleteConfirmId)}
                disabled={deleting}
              >
                {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
