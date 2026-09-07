import React, { useState, useEffect } from 'react';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { Edit2, Plus, AlertCircle, Loader2, Power, Shield } from 'lucide-react';
import { authorizationManagementService, Role } from '../../services/authorizationManagement';
import { useNavigate } from 'react-router-dom';

const styles = {
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '24px',
  },
  title: {
    margin: 0,
    color: 'var(--color-text-main)',
    fontSize: '1.75rem',
  },
  button: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    backgroundColor: 'var(--color-primary)',
    color: 'white',
    border: 'none',
    padding: '10px 20px',
    borderRadius: 'var(--radius-md)',
    cursor: 'pointer',
    fontWeight: 500,
  },
  actionBtn: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: '4px',
    marginRight: '8px',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalOverlay: {
    position: 'fixed' as const,
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  modalContent: {
    backgroundColor: 'var(--color-bg-main)',
    padding: '24px',
    borderRadius: 'var(--radius-lg)',
    width: '100%',
    maxWidth: '500px',
    boxShadow: 'var(--shadow-lg)',
  },
  formGroup: {
    marginBottom: '16px',
  },
  label: {
    display: 'block',
    marginBottom: '8px',
    fontWeight: 500,
    color: 'var(--color-text-main)',
  },
  input: {
    width: '100%',
    padding: '10px',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--color-border)',
    backgroundColor: 'var(--color-bg-secondary)',
    color: 'var(--color-text-main)',
  },
  modalActions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
    marginTop: '24px',
  },
  cancelBtn: {
    backgroundColor: 'transparent',
    color: 'var(--color-text-main)',
    border: '1px solid var(--color-border)',
    padding: '8px 16px',
    borderRadius: 'var(--radius-md)',
    cursor: 'pointer',
  },
  errorBox: {
    backgroundColor: 'rgba(234, 84, 85, 0.1)',
    color: 'var(--color-status-danger)',
    padding: '12px',
    borderRadius: 'var(--radius-md)',
    marginBottom: '16px',
    fontSize: '0.9rem',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  }
};

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
        setError("403 Forbidden: You do not have permission to view roles.");
      } else {
        setError("Failed to load roles.");
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
    setFormData({ 
      name: role.name, 
      description: role.description, 
      is_active: role.is_active 
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFormError(null);

    try {
      const payload = { ...formData };
      
      if (editingRole) {
        await authorizationManagementService.updateRole(editingRole.id, payload);
      } else {
        await authorizationManagementService.createRole(payload);
      }
      setIsModalOpen(false);
      loadRoles();
    } catch (err: any) {
      if (err.errorData && err.errorData.name) {
        setFormError(err.errorData.name[0]);
      } else if (err.response?.status === 403) {
        setFormError("Permission denied.");
      } else {
        setFormError("An error occurred while saving.");
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
      alert("Failed to toggle status.");
    }
  };

  const columns = [
    { key: 'name', title: 'Name' },
    { key: 'description', title: 'Description' },
    { 
      key: 'is_active', 
      title: 'Status', 
      render: (r: Role) => (
        <StatusBadge status={r.is_active ? 'active' : 'inactive'} />
      ) 
    },
    { 
      key: 'actions', 
      title: 'Actions', 
      render: (r: Role) => (
        <div>
          <button style={styles.actionBtn} onClick={() => openEditModal(r)} title="Edit Role">
            <Edit2 size={18} />
          </button>
          <button style={styles.actionBtn} onClick={() => navigate(`/admin/roles/${r.id}/permissions`)} title="Manage Permissions">
            <Shield size={18} color="var(--color-primary)" />
          </button>
          <button style={styles.actionBtn} onClick={() => toggleActive(r)} title={r.is_active ? "Deactivate" : "Activate"}>
            <Power size={18} color={r.is_active ? "var(--color-status-success)" : "var(--color-text-muted)"} />
          </button>
        </div>
      ) 
    }
  ];

  if (loading && roles.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  if (error && roles.length === 0) {
    return (
      <Card>
        <div style={styles.errorBox}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      </Card>
    );
  }

  return (
    <div>
      <div style={styles.header}>
        <h1 style={styles.title}>Roles Management</h1>
        <button style={styles.button} onClick={openCreateModal}>
          <Plus size={18} /> Add Role
        </button>
      </div>

      <Card>
        <Table data={roles} columns={columns} keyExtractor={(r) => r.id} />
      </Card>

      {isModalOpen && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <h2 style={{ marginTop: 0 }}>{editingRole ? 'Edit Role' : 'Add Role'}</h2>
            
            {formError && (
              <div style={styles.errorBox}>
                <AlertCircle size={18} /> {formError}
              </div>
            )}

            <form onSubmit={handleSave}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Name</label>
                <input 
                  style={styles.input} 
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  required
                />
              </div>
              <div style={styles.formGroup}>
                <label style={styles.label}>Description</label>
                <input 
                  style={styles.input} 
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                />
              </div>
              
              <div style={styles.modalActions}>
                <button type="button" style={styles.cancelBtn} onClick={() => setIsModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" style={styles.button} disabled={saving}>
                  {saving ? <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }}/> : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
