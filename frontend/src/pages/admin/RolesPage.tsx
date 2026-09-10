import React, { useState, useEffect } from 'react';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { PageHeader } from '../../components/PageHeader';
import { Modal } from '../../components/Modal';
import { AlertBanner } from '../../components/AlertBanner';
import { Edit2, Plus, Loader2, Power, Shield, ShieldAlert } from 'lucide-react';
import { authorizationManagementService } from '../../services/authorizationManagement';
import type { Role } from '../../services/authorizationManagement';
import { useNavigate } from 'react-router-dom';

export const RolesPage: React.FC = () => {
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [formData, setFormData] = useState({ name: '', description: '', is_active: true });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    loadRoles();
  }, []);

  const loadRoles = async () => {
    setLoading(true);
    try {
      const data = await authorizationManagementService.listRoles();
      setRoles(data);
      setError(null);
    } catch (err: any) {
      if (err.response?.status === 403) {
        setError('You do not have permission to view roles.');
      } else {
        setError('Failed to load roles. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = () => {
    setEditingRole(null);
    setFormData({ name: '', description: '', is_active: true });
    setFormError(null);
    setIsModalOpen(true);
  };

  const openEditModal = (role: Role) => {
    setEditingRole(role);
    setFormData({ name: role.name, description: role.description, is_active: role.is_active });
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFormError(null);
    try {
      if (editingRole) {
        await authorizationManagementService.updateRole(editingRole.id, formData);
      } else {
        await authorizationManagementService.createRole(formData);
      }
      setIsModalOpen(false);
      loadRoles();
    } catch (err: any) {
      if (err.errorData?.name) {
        setFormError(err.errorData.name[0]);
      } else if (err.response?.status === 403) {
        setFormError('Permission denied.');
      } else {
        setFormError('An error occurred while saving. Please try again.');
      }
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (role: Role) => {
    try {
      await authorizationManagementService.updateRole(role.id, { is_active: !role.is_active });
      loadRoles();
    } catch {
      alert('Failed to toggle status.');
    }
  };

  const columns = [
    {
      key: 'name',
      title: 'Role Name',
      render: (r: Role) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--color-primary-light)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <ShieldAlert size={15} color="var(--color-primary)" />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 'var(--font-size-sm)' }}>{r.name}</div>
          </div>
        </div>
      ),
    },
    {
      key: 'description',
      title: 'Description',
      render: (r: Role) => (
        <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
          {r.description || '—'}
        </span>
      ),
    },
    {
      key: 'is_active',
      title: 'Status',
      render: (r: Role) => <StatusBadge status={r.is_active ? 'active' : 'inactive'} />,
    },
    {
      key: 'actions',
      title: 'Actions',
      render: (r: Role) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <button
            className="btn btn-sm btn-secondary btn-icon"
            onClick={() => openEditModal(r)}
            title="Edit role"
            type="button"
          >
            <Edit2 size={14} />
          </button>
          <button
            className="btn btn-sm btn-secondary btn-icon"
            onClick={() => navigate(`/admin/roles/${r.id}/permissions`)}
            title="Manage permissions"
            type="button"
            style={{ color: 'var(--color-primary)' }}
          >
            <Shield size={14} />
          </button>
          <button
            className="btn btn-sm btn-secondary btn-icon"
            onClick={() => toggleActive(r)}
            title={r.is_active ? 'Deactivate role' : 'Activate role'}
            type="button"
            style={{ color: r.is_active ? 'var(--color-status-success)' : 'var(--color-text-muted)' }}
          >
            <Power size={14} />
          </button>
        </div>
      ),
    },
  ];

  if (loading && roles.length === 0) {
    return (
      <div className="loading-center">
        <Loader2 size={28} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
        <span>Loading roles…</span>
      </div>
    );
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      <PageHeader
        title="Roles & Permissions"
        subtitle="Manage access control roles for your organization."
        actions={
          <button className="btn btn-primary" onClick={openCreateModal} type="button">
            <Plus size={16} /> Add Role
          </button>
        }
      />

      {error && <AlertBanner type="error" message={error} />}

      <Card noPadding>
        <Table
          data={roles}
          columns={columns}
          keyExtractor={(r) => r.id}
          emptyIcon={ShieldAlert}
          emptyTitle="No roles configured"
          emptyDescription="Create the first role to start managing access control."
        />
      </Card>

      {isModalOpen && (
        <Modal
          title={editingRole ? 'Edit Role' : 'New Role'}
          onClose={() => setIsModalOpen(false)}
          size="sm"
          footer={
            <>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setIsModalOpen(false)}
              >
                Cancel
              </button>
              <button
                type="submit"
                form="role-form"
                className="btn btn-primary"
                disabled={saving}
              >
                {saving ? <Loader2 size={15} className="animate-spin" /> : null}
                {editingRole ? 'Save Changes' : 'Create Role'}
              </button>
            </>
          }
        >
          {formError && (
            <AlertBanner type="error" message={formError} style={{ marginBottom: 'var(--spacing-md)' }} />
          )}

          <form id="role-form" onSubmit={handleSave}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="role-name">Role Name <span aria-hidden>*</span></label>
                <input
                  id="role-name"
                  className="input-field"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. HR Manager"
                  required
                  autoFocus
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="role-description">Description</label>
                <textarea
                  id="role-description"
                  className="input-field"
                  style={{ minHeight: 80 }}
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Optional description…"
                />
              </div>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
