import React, { useState, useEffect, useCallback, useRef } from 'react';
import { holidayService, type Holiday, type CreateHolidayPayload, type UpdateHolidayPayload } from '../../services/holiday';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { PageHeader } from '../../components/PageHeader';
import { AlertBanner } from '../../components/AlertBanner';
import { Plus, Edit2, Trash2, CalendarDays, Loader2, AlertCircle } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useBranchContext } from '../../contexts/BranchContext';

export const HolidaysPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const { branchId, selectedBranch } = useBranchContext();

  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Modal states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingHoliday, setEditingHoliday] = useState<Holiday | null>(null);
  const [formData, setFormData] = useState<{ name: string; date: string; is_active: boolean }>({
    name: '',
    date: '',
    is_active: true,
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Delete confirmation state
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Stale request controller ref
  const abortControllerRef = useRef<AbortController | null>(null);

  const canManage = hasPermission('holiday.manage');
  const isAllLocations = branchId === null;

  const loadHolidays = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      setLoading(true);
      setError(null);

      const params = isAllLocations ? {} : { branch_id: branchId };
      const data = await holidayService.listHolidays(params, { signal: controller.signal });

      if (abortControllerRef.current === controller) {
        setHolidays(Array.isArray(data) ? data : []);
      }
    } catch (err: any) {
      if (err.name === 'AbortError') return;
      if (abortControllerRef.current === controller) {
        if (err?.status === 403 || err?.response?.status === 403) {
          setError('403 Forbidden: You do not have permission to view holidays.');
        } else if (err?.errorData?.detail) {
          setError(err.errorData.detail);
        } else {
          setError('Failed to load holidays.');
        }
        setHolidays([]);
      }
    } finally {
      if (abortControllerRef.current === controller) {
        setLoading(false);
      }
    }
  }, [branchId, isAllLocations]);

  useEffect(() => {
    setHolidays([]);
    loadHolidays();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [loadHolidays]);

  const openCreateModal = () => {
    if (isAllLocations) return;
    setEditingHoliday(null);
    setFormData({ name: '', date: '', is_active: true });
    setFormError(null);
    setIsModalOpen(true);
  };

  const openEditModal = (holiday: Holiday) => {
    if (isAllLocations) return;
    setEditingHoliday(holiday);
    setFormData({
      name: holiday.name,
      date: holiday.date,
      is_active: holiday.is_active,
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      setFormError('Holiday name is required.');
      return;
    }
    if (!formData.date) {
      setFormError('Date is required.');
      return;
    }
    if (!branchId) {
      setFormError('Select a branch from the header to manage this configuration.');
      return;
    }

    setSaving(true);
    setFormError(null);

    try {
      if (editingHoliday) {
        const payload: UpdateHolidayPayload = {
          name: formData.name.trim(),
          date: formData.date,
          is_active: formData.is_active,
        };
        await holidayService.update(editingHoliday.id, payload);
        setSuccessMessage('Holiday updated successfully.');
      } else {
        const payload: CreateHolidayPayload = {
          branch: branchId,
          name: formData.name.trim(),
          date: formData.date,
          is_active: formData.is_active,
        };
        await holidayService.create(payload);
        setSuccessMessage('Holiday created successfully.');
      }
      setIsModalOpen(false);
      loadHolidays();
    } catch (err: any) {
      if (err.errorData?.name) {
        setFormError(err.errorData.name[0]);
      } else if (err.errorData?.date) {
        setFormError(err.errorData.date[0]);
      } else if (err.errorData?.non_field_errors) {
        setFormError(err.errorData.non_field_errors[0]);
      } else if (err.errorData?.detail) {
        setFormError(err.errorData.detail);
      } else if (err.status === 403 || err.response?.status === 403) {
        setFormError('403 Forbidden: You do not have permission to manage holidays.');
      } else {
        setFormError('Failed to save holiday. Please try again.');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (isAllLocations) return;
    try {
      setDeleting(true);
      await holidayService.delete(id);
      setSuccessMessage('Holiday deleted successfully.');
      setDeleteConfirmId(null);
      loadHolidays();
    } catch (err: any) {
      if (err.status === 403 || err.response?.status === 403) {
        setError('403 Forbidden: You do not have permission to delete holidays.');
      } else if (err.errorData?.detail) {
        setError(err.errorData.detail);
      } else {
        setError('Failed to delete holiday.');
      }
    } finally {
      setDeleting(false);
    }
  };

  if (!hasPermission('holiday.view')) {
    return (
      <div className="animate-fade-in">
        <PageHeader title="Holiday Management" subtitle="Branch holiday calendar." />
        <AlertBanner type="error" message="You do not have permission to view holidays." />
      </div>
    );
  }

  const branchTitle = selectedBranch.type === 'branch' && selectedBranch.branch?.name
    ? `Branch: ${selectedBranch.branch.name}`
    : 'All Locations';

  const columns = [
    {
      key: 'name',
      title: 'Holiday Name',
      render: (h: Holiday) => <span style={{ fontWeight: 600 }}>{h.name}</span>,
    },
    {
      key: 'date',
      title: 'Date',
      render: (h: Holiday) => (
        <span style={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
          {h.date}
        </span>
      ),
    },
    {
      key: 'is_active',
      title: 'Status',
      render: (h: Holiday) => (
        <StatusBadge status={h.is_active ? 'active' : 'inactive'} label={h.is_active ? 'Active' : 'Inactive'} />
      ),
    },
    ...(canManage && !isAllLocations
      ? [
          {
            key: 'actions',
            title: 'Actions',
            render: (h: Holiday) => (
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => openEditModal(h)}
                  title="Edit Holiday"
                  aria-label={`Edit ${h.name}`}
                  type="button"
                  style={{ padding: '4px 8px' }}
                >
                  <Edit2 size={14} />
                </button>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setDeleteConfirmId(h.id)}
                  title="Delete Holiday"
                  aria-label={`Delete ${h.name}`}
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
          title="Holiday Management"
          subtitle={`Manage official company holidays for ${branchTitle}.`}
        />
        {canManage && (
          <button
            className="btn btn-primary"
            onClick={openCreateModal}
            disabled={isAllLocations}
            title={isAllLocations ? 'Select a branch from the header to manage this configuration.' : 'Add a new holiday'}
            type="button"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
          >
            <Plus size={16} />
            <span>Add Holiday</span>
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
            <span style={{ marginTop: '8px' }}>Loading holidays…</span>
          </div>
        ) : (
          <Table
            columns={columns}
            data={holidays}
            keyExtractor={(h) => h.id.toString()}
            emptyIcon={CalendarDays}
            emptyTitle="No holidays configured"
            emptyDescription={
              isAllLocations
                ? 'No holidays found across authorized branches.'
                : 'No holidays configured for this branch yet.'
            }
          />
        )}
      </Card>

      {/* Add / Edit Holiday Modal */}
      {isModalOpen && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="holiday-modal-title">
          <div className="modal-content" style={{ maxWidth: '480px' }}>
            <h2 id="holiday-modal-title" style={{ margin: '0 0 var(--spacing-md) 0', fontSize: '1.25rem' }}>
              {editingHoliday ? 'Edit Holiday' : 'Add Holiday'}
            </h2>

            {formError && <AlertBanner type="error" message={formError} style={{ marginBottom: 'var(--spacing-md)' }} />}

            <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
              <div>
                <label className="input-label" htmlFor="holiday-name">
                  Holiday Name <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                </label>
                <input
                  id="holiday-name"
                  type="text"
                  className="input-field"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. Independence Day"
                  required
                />
              </div>

              <div>
                <label className="input-label" htmlFor="holiday-date">
                  Date <span style={{ color: 'var(--color-status-danger)' }}>*</span>
                </label>
                <input
                  id="holiday-date"
                  type="date"
                  className="input-field"
                  value={formData.date}
                  onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                  required
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                <input
                  id="holiday-is-active"
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                />
                <label htmlFor="holiday-is-active" style={{ cursor: 'pointer', fontSize: '0.9rem', fontWeight: 500 }}>
                  Active (observed this calendar year)
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
                  <span>{saving ? 'Saving…' : editingHoliday ? 'Update Holiday' : 'Create Holiday'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmId !== null && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="delete-confirm-title">
          <div className="modal-content" style={{ maxWidth: '420px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: 'var(--spacing-md)' }}>
              <div style={{ padding: '8px', borderRadius: '50%', backgroundColor: 'rgba(234, 84, 85, 0.1)', color: 'var(--color-status-danger)' }}>
                <AlertCircle size={22} />
              </div>
              <h2 id="delete-confirm-title" style={{ margin: 0, fontSize: '1.15rem' }}>
                Confirm Deletion
              </h2>
            </div>
            <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', marginBottom: 'var(--spacing-lg)' }}>
              Are you sure you want to delete this holiday? This action cannot be undone.
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
