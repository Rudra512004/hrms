import React, { useState, useEffect } from 'react';
import { branchService, type Branch } from '../../../services/branch';
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
    maxHeight: '90vh',
    overflowY: 'auto' as const,
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

export const BranchesPage: React.FC = () => {
  const [branches, setBranches] = useState<Branch[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingBranch, setEditingBranch] = useState<Branch | null>(null);
  const [formData, setFormData] = useState({ name: '', address: '', latitude: '', longitude: '', radius: '100', organization: 0, is_active: true });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const { hasPermission } = useAuth();
  
  const canManage = hasPermission('branch.manage');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [branchData, orgData] = await Promise.all([
        branchService.getAll(),
        organizationService.listOrganizations().catch(() => [])
      ]);
      setBranches(branchData);
      setOrganizations(orgData);
      setError(null);
    } catch (err: any) {
      if (err.response?.status === 403) {
        setError("403 Forbidden: You do not have permission to view branches.");
      } else {
        setError("Failed to load branches.");
      }
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = () => {
    setEditingBranch(null);
    setFormData({ name: '', address: '', latitude: '', longitude: '', radius: '100', organization: organizations[0]?.id || 0, is_active: true });
    setFormError(null);
    setIsModalOpen(true);
  };

  const openEditModal = (branch: Branch) => {
    setEditingBranch(branch);
    setFormData({ 
      name: branch.name, 
      address: branch.address || '', 
      latitude: branch.latitude?.toString() || '', 
      longitude: branch.longitude?.toString() || '',
      radius: branch.radius?.toString() || '100',
      organization: branch.organization,
      is_active: branch.is_active 
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.organization) {
        setFormError("Organization is required.");
        return;
    }

    setSaving(true);
    setFormError(null);

    try {
      const payload: Partial<Branch> = { 
          name: formData.name,
          address: formData.address,
          latitude: formData.latitude ? parseFloat(formData.latitude) : null,
          longitude: formData.longitude ? parseFloat(formData.longitude) : null,
          radius: parseFloat(formData.radius),
          organization: formData.organization,
          is_active: formData.is_active
      };
      
      if (editingBranch) {
        await branchService.update(editingBranch.id, payload);
      } else {
        await branchService.create(payload);
      }
      setIsModalOpen(false);
      loadData();
    } catch (err: any) {
      if (err.errorData && err.errorData.name) {
        setFormError(err.errorData.name[0]);
      } else if (err.response?.status === 403) {
        setFormError("Permission denied.");
      } else if (err.errorData && typeof err.errorData === 'object') {
        const errorMsgs = Object.entries(err.errorData).map(([key, val]) => `${key}: ${val}`).join(' | ');
        setFormError(errorMsgs || "Validation error.");
      } else {
        setFormError("An error occurred while saving.");
      }
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (branch: Branch) => {
    try {
      await branchService.update(branch.id, { is_active: !branch.is_active });
      loadData();
    } catch {
      alert("Failed to toggle status.");
    }
  };

  const handleDelete = async (branch: Branch) => {
    if (!window.confirm(`Are you sure you want to delete the branch "${branch.name}"?`)) return;
    try {
      await branchService.delete(branch.id);
      loadData();
    } catch (err: any) {
      if (err.response?.status === 409) {
        alert(err.errorData?.detail || "Cannot delete branch that is in use.");
      } else {
        alert("Failed to delete branch.");
      }
    }
  };

  const columns = [
    { key: 'id', title: 'ID' },
    { key: 'name', title: 'Name' },
    { key: 'address', title: 'Address' },
    { key: 'coordinates', title: 'Lat/Long', render: (n: Branch) => (n.latitude && n.longitude ? `${n.latitude}, ${n.longitude}` : 'N/A') },
    { key: 'radius', title: 'Radius (m)', render: (n: Branch) => n.radius },
    { 
      key: 'is_active', 
      title: 'Status', 
      render: (n: Branch) => (
        <StatusBadge status={n.is_active ? 'active' : 'inactive'} />
      ) 
    }
  ];

  if (canManage) {
    columns.push({ 
      key: 'actions', 
      title: 'Actions', 
      render: (n: Branch) => (
        <div>
          <button style={styles.actionBtn} onClick={() => openEditModal(n)} title="Edit">
            <Edit2 size={18} />
          </button>
          <button style={styles.actionBtn} onClick={() => toggleActive(n)} title={n.is_active ? "Deactivate" : "Activate"}>
            <Power size={18} color={n.is_active ? "var(--color-status-success)" : "var(--color-text-muted)"} />
          </button>
          <button style={styles.actionBtn} onClick={() => handleDelete(n)} title="Delete">
            <Trash2 size={18} color="var(--color-status-danger)" />
          </button>
        </div>
      ) 
    });
  }

  if (loading && branches.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  if (error && branches.length === 0) {
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
        <h1 style={styles.title}>Branches</h1>
        {canManage && (
          <button style={styles.button} onClick={openCreateModal}>
            <Plus size={18} /> Add Branch
          </button>
        )}
      </div>

      <Card>
        {branches.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-muted)' }}>
            No branches found.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <Table data={branches} columns={columns} keyExtractor={(n) => n.id} />
          </div>
        )}
      </Card>

      {isModalOpen && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <h2 style={{ marginTop: 0 }}>{editingBranch ? 'Edit Branch' : 'Add Branch'}</h2>
            
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
                <label style={styles.label}>Organization</label>
                <select
                  style={styles.input}
                  value={formData.organization}
                  onChange={(e) => setFormData({...formData, organization: parseInt(e.target.value)})}
                  required
                >
                  <option value={0} disabled>Select an organization</option>
                  {organizations.map(org => (
                    <option key={org.id} value={org.id}>{org.name}</option>
                  ))}
                </select>
              </div>
              <div style={styles.formGroup}>
                <label style={styles.label}>Address</label>
                <textarea 
                  style={{...styles.input, minHeight: '60px'}} 
                  value={formData.address}
                  onChange={(e) => setFormData({...formData, address: e.target.value})}
                />
              </div>
              <div style={{ display: 'flex', gap: '16px' }}>
                <div style={{...styles.formGroup, flex: 1}}>
                  <label style={styles.label}>Latitude</label>
                  <input 
                    type="number"
                    step="0.000001"
                    style={styles.input} 
                    value={formData.latitude}
                    onChange={(e) => setFormData({...formData, latitude: e.target.value})}
                  />
                </div>
                <div style={{...styles.formGroup, flex: 1}}>
                  <label style={styles.label}>Longitude</label>
                  <input 
                    type="number"
                    step="0.000001"
                    style={styles.input} 
                    value={formData.longitude}
                    onChange={(e) => setFormData({...formData, longitude: e.target.value})}
                  />
                </div>
              </div>
              <div style={styles.formGroup}>
                <label style={styles.label}>Radius (meters)</label>
                <input 
                  type="number"
                  step="0.1"
                  style={styles.input} 
                  value={formData.radius}
                  onChange={(e) => setFormData({...formData, radius: e.target.value})}
                  required
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
