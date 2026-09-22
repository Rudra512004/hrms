import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { organizationService, type Department, type Branch } from '../../../services/organization';
import { Card } from '../../../components/Card';
import { Table } from '../../../components/Table';
import { StatusBadge } from '../../../components/StatusBadge';
import { Plus, Edit2, Trash2, Power, AlertCircle, Loader2 } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import { useBranchContext } from '../../../contexts/BranchContext';

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
  },
  helperText: {
    fontSize: '0.8rem',
    color: 'var(--color-text-muted)',
    marginTop: '4px',
  }
};

export const DepartmentsPage: React.FC = () => {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingDept, setEditingDept] = useState<Department | null>(null);
  const [formData, setFormData] = useState({ name: '', description: '', branch: 0, is_active: true });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const { hasPermission } = useAuth();
  const { branchId, branches: contextBranches } = useBranchContext();

  const canManage = hasPermission('department.manage');

  const branchMap = useMemo(() => {
    const map = new Map<number, string>();
    branches.forEach(b => map.set(b.id, b.name));
    return map;
  }, [branches]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [deptData, branchData] = await Promise.all([
        branchId ? organizationService.listDepartments(branchId) : organizationService.listDepartments(),
        organizationService.listBranches().catch(() => contextBranches || [])
      ]);
      setDepartments(Array.isArray(deptData) ? deptData : []);
      const resolvedBranches = Array.isArray(branchData) && branchData.length > 0 ? branchData : (contextBranches || []);
      setBranches(resolvedBranches);
      setError(null);
    } catch (err: any) {
      if (err.response?.status === 403) {
        setError("403 Forbidden: You do not have permission to view departments.");
      } else {
        setError("Failed to load departments. Backend might be unavailable.");
      }
    } finally {
      setLoading(false);
    }
  }, [branchId, contextBranches]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const openCreateModal = () => {
    setEditingDept(null);
    // Preselect active branch from header if available, else first branch
    const defaultBranch = branchId || (branches.length > 0 ? branches[0].id : 0);
    setFormData({ name: '', description: '', branch: defaultBranch, is_active: true });
    setFormError(null);
    setIsModalOpen(true);
  };

  const openEditModal = (dept: Department) => {
    setEditingDept(dept);
    setFormData({ 
      name: dept.name, 
      description: dept.description || '', 
      branch: dept.branch || 0,
      is_active: dept.is_active 
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      setFormError("Department name is required.");
      return;
    }
    if (!formData.branch || formData.branch === 0) {
      setFormError("Branch is required.");
      return;
    }

    setSaving(true);
    setFormError(null);

    try {
      if (editingDept) {
        // Backend DepartmentSerializer has branch as read-only on update
        await organizationService.updateDepartment(editingDept.id, {
          name: formData.name.trim(),
          description: formData.description,
          is_active: formData.is_active,
        });
      } else {
        await organizationService.createDepartment({
          name: formData.name.trim(),
          branch: formData.branch,
          description: formData.description,
          is_active: formData.is_active,
        });
      }
      setIsModalOpen(false);
      loadData();
    } catch (err: any) {
      if (err.errorData?.branch) {
        setFormError(Array.isArray(err.errorData.branch) ? err.errorData.branch[0] : err.errorData.branch);
      } else if (err.errorData?.name) {
        setFormError(Array.isArray(err.errorData.name) ? err.errorData.name[0] : err.errorData.name);
      } else if (err.errorData?.detail) {
        setFormError(err.errorData.detail);
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

  const toggleActive = async (dept: Department) => {
    try {
      await organizationService.updateDepartment(dept.id, { is_active: !dept.is_active });
      loadData();
    } catch {
      alert("Failed to toggle status.");
    }
  };

  const handleDelete = async (dept: Department) => {
    if (!window.confirm(`Are you sure you want to delete the department "${dept.name}"?`)) return;
    try {
      await organizationService.deleteDepartment(dept.id);
      loadData();
    } catch (err: any) {
      if (err.response?.status === 409 || err.response?.status === 400) {
        alert(err.errorData?.detail || "Cannot delete department that is in use.");
      } else {
        alert("Failed to delete department.");
      }
    }
  };

  const columns = [
    { key: 'id', title: 'ID' },
    { key: 'name', title: 'Name' },
    { key: 'description', title: 'Description' },
    { 
      key: 'branch', 
      title: 'Branch', 
      render: (n: Department) => branchMap.get(n.branch) || n.branch_name || `Branch #${n.branch}` 
    },
    { 
      key: 'is_active', 
      title: 'Status', 
      render: (n: Department) => (
        <StatusBadge status={n.is_active ? 'active' : 'inactive'} />
      ) 
    }
  ];

  if (canManage) {
    columns.push({ 
      key: 'actions', 
      title: 'Actions', 
      render: (n: Department) => (
        <div>
          <button 
            style={styles.actionBtn} 
            onClick={() => openEditModal(n)} 
            title="Edit"
            data-testid={`edit-dept-${n.id}`}
          >
            <Edit2 size={18} />
          </button>
          <button 
            style={styles.actionBtn} 
            onClick={() => toggleActive(n)} 
            title={n.is_active ? "Deactivate" : "Activate"}
            data-testid={`toggle-dept-${n.id}`}
          >
            <Power size={18} color={n.is_active ? "var(--color-status-success)" : "var(--color-text-muted)"} />
          </button>
          <button 
            style={styles.actionBtn} 
            onClick={() => handleDelete(n)} 
            title="Delete"
            data-testid={`delete-dept-${n.id}`}
          >
            <Trash2 size={18} color="var(--color-status-danger)" />
          </button>
        </div>
      ) 
    });
  }

  if (loading && departments.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  if (error && departments.length === 0) {
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
        <h1 style={styles.title}>Departments</h1>
        {canManage && (
          <button style={styles.button} onClick={openCreateModal} data-testid="add-department-btn">
            <Plus size={18} /> Add Department
          </button>
        )}
      </div>

      <Card>
        {departments.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-muted)' }}>
            No departments found.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <Table data={departments} columns={columns} keyExtractor={(n) => n.id} />
          </div>
        )}
      </Card>

      {isModalOpen && (
        <div style={styles.modalOverlay} data-testid="department-modal">
          <div style={styles.modalContent}>
            <h2 style={{ marginTop: 0 }}>{editingDept ? 'Edit Department' : 'Add Department'}</h2>
            
            {formError && (
              <div style={styles.errorBox} data-testid="department-form-error">
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
                  data-testid="department-name-input"
                  placeholder="e.g. Engineering"
                />
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>Branch</label>
                <select
                  style={styles.input}
                  value={formData.branch}
                  onChange={(e) => setFormData({...formData, branch: parseInt(e.target.value, 10)})}
                  required
                  disabled={!!editingDept}
                  data-testid="department-branch-select"
                >
                  <option value={0} disabled>Select a branch</option>
                  {branches.map(b => (
                    <option key={b.id} value={b.id}>{b.name}</option>
                  ))}
                </select>
                {editingDept && (
                  <div style={styles.helperText}>Branch cannot be changed once a department is created.</div>
                )}
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>Description</label>
                <input 
                  style={styles.input} 
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                  data-testid="department-desc-input"
                  placeholder="Optional description"
                />
              </div>
              
              <div style={styles.modalActions}>
                <button 
                  type="button" 
                  style={styles.cancelBtn} 
                  onClick={() => setIsModalOpen(false)}
                  data-testid="department-cancel-btn"
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  style={styles.button} 
                  disabled={saving}
                  data-testid="department-save-btn"
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
