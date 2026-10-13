import React, { useState, useEffect } from 'react';
import { PageHeader } from '../../components/PageHeader';
import { Modal } from '../../components/Modal';
import { AlertBanner } from '../../components/AlertBanner';
import { Plus, Loader2, Trash2, Edit3, ShieldAlert, AlertCircle } from 'lucide-react';
import { authorizationManagementService } from '../../services/authorizationManagement';
import type { Role } from '../../services/authorizationManagement';
import { useNavigate } from 'react-router-dom';

export const RolesPage: React.FC = () => {
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Role Create/Edit Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [formData, setFormData] = useState({ name: '', description: '' });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Role Delete Modal State
  const [deletingRole, setDeletingRole] = useState<Role | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

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
    setFormData({ name: '', description: '' });
    setFormError(null);
    setIsModalOpen(true);
  };

  const openEditModal = (role: Role) => {
    setEditingRole(role);
    setFormData({ name: role.name, description: role.description || '' });
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleSaveRole = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      setFormError('Role name is required.');
      return;
    }

    setSaving(true);
    setFormError(null);
    try {
      if (editingRole) {
        // Only send name if it's not a system role (system role names are immutable)
        const payload = editingRole.is_system
          ? { description: formData.description }
          : { name: formData.name.trim(), description: formData.description };
        await authorizationManagementService.updateRole(editingRole.id, payload);
      } else {
        await authorizationManagementService.createRole({
          name: formData.name.trim(),
          description: formData.description
        });
      }
      setIsModalOpen(false);
      await loadRoles();
    } catch (err: any) {
      if (err.errorData?.name) {
        setFormError(Array.isArray(err.errorData.name) ? err.errorData.name[0] : err.errorData.name);
      } else if (err.errorData?.detail) {
        setFormError(err.errorData.detail);
      } else if (err.response?.status === 403) {
        setFormError('Permission denied.');
      } else {
        setFormError('An error occurred while saving. Please try again.');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteRole = async () => {
    if (!deletingRole) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await authorizationManagementService.deleteRole(deletingRole.id);
      setDeletingRole(null);
      await loadRoles();
    } catch (err: any) {
      if (err.errorData?.detail) {
        setDeleteError(err.errorData.detail);
      } else if (err.response?.status === 403) {
        setDeleteError('Permission denied.');
      } else {
        setDeleteError('Failed to delete role. Please try again.');
      }
    } finally {
      setIsDeleting(false);
    }
  };

  if (loading && roles.length === 0) {
    return (
      <div className="loading-center" style={{ minHeight: '400px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '12px' }}>
        <Loader2 size={32} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
        <span style={{ color: 'var(--color-text-muted)' }}>Loading roles…</span>
      </div>
    );
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      <PageHeader
        title="Roles & Permissions"
        subtitle="Manage access control roles and configure system permissions."
        actions={
          <button className="btn btn-primary" onClick={openCreateModal} type="button" id="add-role-btn">
            <Plus size={16} /> Add Role
          </button>
        }
      />

      {error && <AlertBanner type="error" message={error} />}

      {roles.length === 0 && !loading && (
        <div
          style={{
            backgroundColor: 'var(--color-bg-card)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            padding: '48px 24px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '16px'
          }}
        >
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: '50%',
              backgroundColor: 'var(--color-primary-light)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--color-primary)'
            }}
          >
            <ShieldAlert size={28} />
          </div>
          <div>
            <h3 style={{ margin: '0 0 6px 0', fontSize: '1.125rem', fontWeight: 600, color: 'var(--color-text-main)' }}>
              No roles configured
            </h3>
            <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
              Create the first role to start managing access control.
            </p>
          </div>
          <button className="btn btn-primary" onClick={openCreateModal} type="button">
            <Plus size={15} /> Add Role
          </button>
        </div>
      )}

      {/* 3-Column Grid Matching Reference Screenshot */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '24px'
        }}
        data-testid="roles-grid"
      >
        {roles.map((role) => (
          <div
            key={role.id}
            data-testid={`role-card-${role.id}`}
            style={{
              backgroundColor: 'var(--color-bg-card)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-lg, 12px)',
              padding: '24px',
              boxShadow: 'var(--shadow-sm)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              minHeight: '200px',
              position: 'relative',
              transition: 'box-shadow 0.2s, border-color 0.2s'
            }}
          >
            {/* Top Row: Name, Slug, Badges & Quick Edit */}
            <div>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <h3
                      style={{
                        margin: 0,
                        fontSize: '1.125rem',
                        fontWeight: 600,
                        color: 'var(--color-text-main)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}
                      title={role.name}
                    >
                      {role.name}
                    </h3>
                    {!role.is_system && (
                      <button
                        type="button"
                        onClick={() => openEditModal(role)}
                        title="Edit role details"
                        style={{
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          color: 'var(--color-text-muted)',
                          padding: '2px',
                          display: 'inline-flex',
                          alignItems: 'center'
                        }}
                      >
                        <Edit3 size={13} />
                      </button>
                    )}
                  </div>
                  <div
                    style={{
                      fontSize: '0.875rem',
                      color: 'var(--color-text-muted)',
                      marginTop: '3px',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}
                    title={role.slug}
                  >
                    {role.slug}
                  </div>
                </div>

                {/* Badge (e.g. 'Full access' for Super Admin) */}
                {role.badge && (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      padding: '3px 10px',
                      borderRadius: '9999px',
                      fontSize: '0.75rem',
                      fontWeight: 500,
                      backgroundColor: 'var(--color-primary-light, #EAF2FF)',
                      color: 'var(--color-primary, #2563EB)',
                      border: '1px solid var(--color-primary-border, #BFDBFE)',
                      whiteSpace: 'nowrap'
                    }}
                  >
                    {role.badge}
                  </span>
                )}
              </div>

              {/* Metrics Section: USERS & PERMISSIONS */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '48px',
                  marginTop: '22px',
                  marginBottom: '22px'
                }}
              >
                <div>
                  <div
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      color: 'var(--color-text-muted)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      marginBottom: '4px'
                    }}
                  >
                    USERS
                  </div>
                  <div
                    style={{
                      fontSize: '1.625rem',
                      fontWeight: 700,
                      color: 'var(--color-text-main)',
                      lineHeight: 1
                    }}
                    data-testid={`users-count-${role.id}`}
                  >
                    {role.users_count ?? 0}
                  </div>
                </div>

                <div>
                  <div
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      color: 'var(--color-text-muted)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      marginBottom: '4px'
                    }}
                  >
                    PERMISSIONS
                  </div>
                  <div
                    style={{
                      fontSize: '1.625rem',
                      fontWeight: 700,
                      color: 'var(--color-text-main)',
                      lineHeight: 1
                    }}
                    data-testid={`permissions-count-${role.id}`}
                  >
                    {role.permissions_count ?? 0}
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Actions Row: Edit permissions & Delete */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                marginTop: 'auto',
                paddingTop: '12px',
                borderTop: '1px solid var(--color-border-subtle, #f1f5f9)'
              }}
            >
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => navigate(`/admin/roles/${role.id}/permissions`)}
                style={{
                  flex: 1,
                  textAlign: 'center',
                  justifyContent: 'center',
                  padding: '8px 16px',
                  fontSize: '0.875rem',
                  fontWeight: 500,
                  borderRadius: 'var(--radius-md, 8px)'
                }}
                id={`edit-permissions-btn-${role.id}`}
              >
                Edit permissions
              </button>

              {/* Delete button only rendered if can_delete is true */}
              {role.can_delete && (
                <button
                  type="button"
                  onClick={() => {
                    setDeleteError(null);
                    setDeletingRole(role);
                  }}
                  title="Delete role"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 14px',
                    fontSize: '0.875rem',
                    fontWeight: 500,
                    borderRadius: 'var(--radius-md, 8px)',
                    border: '1px solid var(--color-status-danger-border, #fecaca)',
                    backgroundColor: 'var(--color-status-danger-bg, #fef2f2)',
                    color: 'var(--color-status-danger, #dc2626)',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    transition: 'opacity 0.2s'
                  }}
                  id={`delete-role-btn-${role.id}`}
                >
                  <Trash2 size={14} /> Delete
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Create / Edit Role Modal */}
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
                id="submit-role-btn"
              >
                {saving && <Loader2 size={15} className="animate-spin" />}
                {editingRole ? 'Save Changes' : 'Create Role'}
              </button>
            </>
          }
        >
          {formError && (
            <AlertBanner type="error" message={formError} style={{ marginBottom: 'var(--spacing-md)' }} />
          )}

          <form id="role-form" onSubmit={handleSaveRole}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="role-name">
                  Role Name <span aria-hidden>*</span>
                </label>
                <input
                  id="role-name"
                  className="input-field"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. Floor Supervisor"
                  required
                  autoFocus
                  disabled={editingRole?.is_system}
                />
                {editingRole?.is_system && (
                  <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '4px', display: 'block' }}>
                    System role name cannot be modified.
                  </span>
                )}
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="role-description">
                  Description
                </label>
                <textarea
                  id="role-description"
                  className="input-field"
                  style={{ minHeight: 80, resize: 'vertical' }}
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Describe the scope and responsibilities of this role…"
                />
              </div>
            </div>
          </form>
        </Modal>
      )}

      {/* Delete Confirmation Modal */}
      {deletingRole && (
        <Modal
          title="Delete Role"
          onClose={() => setDeletingRole(null)}
          size="sm"
          footer={
            <>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setDeletingRole(null)}
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleDeleteRole}
                disabled={isDeleting}
                id="confirm-delete-role-btn"
              >
                {isDeleting && <Loader2 size={15} className="animate-spin" />}
                Delete Role
              </button>
            </>
          }
        >
          {deleteError && (
            <AlertBanner type="error" message={deleteError} style={{ marginBottom: 'var(--spacing-md)' }} />
          )}

          <div style={{ display: 'flex', gap: '14px', alignItems: 'flex-start' }}>
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: '50%',
                backgroundColor: 'var(--color-status-danger-bg, #fef2f2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--color-status-danger, #dc2626)',
                flexShrink: 0
              }}
            >
              <AlertCircle size={20} />
            </div>
            <div>
              <p style={{ margin: '0 0 8px 0', fontSize: '0.9375rem', fontWeight: 500, color: 'var(--color-text-main)' }}>
                Are you sure you want to delete role <strong>{deletingRole.name}</strong>?
              </p>
              <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                This action cannot be undone. All role metadata will be permanently removed.
              </p>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
