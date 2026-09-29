import React, { useState, useEffect } from 'react';
import { organizationService, type Organization } from '../../../services/organization';
import { Card } from '../../../components/Card';
import { Table } from '../../../components/Table';
import { StatusBadge } from '../../../components/StatusBadge';
import { Plus, Edit2, Trash2, Power, AlertCircle, Loader2 } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';

const styles = {
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 'var(--spacing-lg)',
  },
  title: {
    margin: 0,
    fontSize: '1.25rem',
    color: 'var(--color-text-main)',
  },
  button: {
    backgroundColor: 'var(--color-primary)',
    color: '#fff',
    border: 'none',
    padding: '8px 16px',
    borderRadius: 'var(--radius-md)',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontWeight: 500,
    transition: 'opacity 0.2s',
  },
  actionBtn: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: '4px',
    color: 'var(--color-text-muted)',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: '8px',
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
    backgroundColor: 'var(--color-bg-card)',
    padding: 'var(--spacing-xl)',
    borderRadius: 'var(--radius-lg)',
    width: '100%',
    maxWidth: '500px',
    boxShadow: 'var(--shadow-lg)',
  },
  formGroup: {
    marginBottom: 'var(--spacing-md)',
  },
  label: {
    display: 'block',
    marginBottom: '8px',
    fontWeight: 500,
    fontSize: '0.9rem',
    color: 'var(--color-text-main)',
  },
  input: {
    width: '100%',
    padding: '10px 12px',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-md)',
    backgroundColor: 'var(--color-bg-body)',
    color: 'var(--color-text-main)',
    fontSize: '0.95rem',
  },
  modalActions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
    marginTop: 'var(--spacing-xl)',
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

export const OrganizationsPage: React.FC = () => {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingOrg, setEditingOrg] = useState<Organization | null>(null);
  const [formData, setFormData] = useState<{ name: string; status: string }>({ name: '', status: 'active' });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const { hasPermission } = useAuth();
  
  const canManage = hasPermission('organization.manage');

  useEffect(() => {
    loadOrganizations();
  }, []);

  const loadOrganizations = async () => {
    setLoading(true);
    try {
      const data = await organizationService.listOrganizations();
      setOrganizations(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err: any) {
      if (err.response?.status === 403) {
        setError("403 Forbidden: You do not have permission to view organizations.");
      } else {
        setError("Failed to load organizations. Backend might be unavailable.");
      }
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = () => {
    setEditingOrg(null);
    setFormData({ name: '', status: 'active' });
    setFormError(null);
    setIsModalOpen(true);
  };

  const openEditModal = (org: Organization) => {
    setEditingOrg(org);
    setFormData({ 
      name: org.name, 
      status: org.status || (org.is_active ? 'active' : 'inactive'),
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      setFormError("Organization name is required.");
      return;
    }

    setSaving(true);
    setFormError(null);

    try {
      const payload = {
        name: formData.name.trim(),
        status: formData.status,
      };
      
      if (editingOrg) {
        await organizationService.updateOrganization(editingOrg.id, payload);
      } else {
        await organizationService.createOrganization(payload);
      }
      setIsModalOpen(false);
      loadOrganizations();
    } catch (err: any) {
      if (err.errorData && err.errorData.name) {
        setFormError(Array.isArray(err.errorData.name) ? err.errorData.name[0] : err.errorData.name);
      } else if (err.response?.status === 403) {
        setFormError("Permission denied.");
      } else if (err.errorData && typeof err.errorData === 'object') {
        const errorMsgs = Object.entries(err.errorData)
          .map(([key, val]) => `${key}: ${Array.isArray(val) ? val.join(', ') : val}`)
          .join(' | ');
        setFormError(errorMsgs || "Validation error.");
      } else {
        setFormError("An error occurred while saving.");
      }
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (org: Organization) => {
    try {
      const currentStatus = org.status || (org.is_active ? 'active' : 'inactive');
      const newStatus = currentStatus === 'active' ? 'inactive' : 'active';
      await organizationService.updateOrganization(org.id, { status: newStatus });
      loadOrganizations();
    } catch {
      alert("Failed to toggle status.");
    }
  };

  const handleDelete = async (org: Organization) => {
    if (!window.confirm(`Are you sure you want to delete the organization "${org.name}"?`)) return;
    try {
      await organizationService.deleteOrganization(org.id);
      loadOrganizations();
    } catch (err: any) {
      if (err.response?.status === 409 || err.response?.status === 400) {
        alert(err.errorData?.detail || "Cannot delete organization that is in use.");
      } else {
        alert("Failed to delete organization.");
      }
    }
  };

  const columns = [
    { key: 'id', title: 'ID' },
    { key: 'name', title: 'Name' },
    { 
      key: 'status', 
      title: 'Status', 
      render: (n: Organization) => (
        <StatusBadge status={n.status || (n.is_active ? 'active' : 'inactive')} />
      ) 
    }
  ];

  if (canManage) {
    columns.push({ 
      key: 'actions', 
      title: 'Actions', 
      render: (n: Organization) => (
        <div>
          <button 
            style={styles.actionBtn} 
            onClick={() => openEditModal(n)} 
            title="Edit"
            data-testid={`edit-org-${n.id}`}
          >
            <Edit2 size={18} />
          </button>
          <button 
            style={styles.actionBtn} 
            onClick={() => toggleActive(n)} 
            title={(n.status || (n.is_active ? 'active' : 'inactive')) === 'active' ? "Deactivate" : "Activate"}
            data-testid={`toggle-org-${n.id}`}
          >
            <Power 
              size={18} 
              color={(n.status || (n.is_active ? 'active' : 'inactive')) === 'active' ? "var(--color-status-success)" : "var(--color-text-muted)"} 
            />
          </button>
          <button 
            style={styles.actionBtn} 
            onClick={() => handleDelete(n)} 
            title="Delete"
            data-testid={`delete-org-${n.id}`}
          >
            <Trash2 size={18} color="var(--color-status-danger)" />
          </button>
        </div>
      ) 
    });
  }

  if (loading && organizations.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  if (error && organizations.length === 0) {
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
        <h1 style={styles.title}>Organizations</h1>
        {canManage && (
          <button style={styles.button} onClick={openCreateModal} data-testid="add-organization-btn">
            <Plus size={18} /> Add Organization
          </button>
        )}
      </div>

      <Card>
        {organizations.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-muted)' }}>
            No organizations found.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <Table data={organizations} columns={columns} keyExtractor={(n) => n.id} />
          </div>
        )}
      </Card>

      {isModalOpen && (
        <div style={styles.modalOverlay} data-testid="organization-modal">
          <div style={styles.modalContent}>
            <h2 style={{ marginTop: 0 }}>{editingOrg ? 'Edit Organization' : 'Add Organization'}</h2>
            
            {formError && (
              <div style={styles.errorBox} data-testid="org-form-error">
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
                  data-testid="org-name-input"
                  placeholder="e.g. Acme Corp"
                />
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>Status</label>
                <select
                  style={styles.input}
                  value={formData.status}
                  onChange={(e) => setFormData({...formData, status: e.target.value})}
                  data-testid="org-status-select"
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </div>
              
              <div style={styles.modalActions}>
                <button 
                  type="button" 
                  style={styles.cancelBtn} 
                  onClick={() => setIsModalOpen(false)}
                  data-testid="org-cancel-btn"
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  style={styles.button} 
                  disabled={saving}
                  data-testid="org-save-btn"
                >
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
