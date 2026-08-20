import React, { useState, useEffect } from 'react';
import { leaveService, type LeaveType } from '../../services/leaves';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { Plus, Edit2, Trash2, Power, AlertCircle, Loader2 } from 'lucide-react';
import { authService } from '../../services/auth';

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

export const AdminLeaveTypesPage: React.FC = () => {
  const [leaveTypes, setLeaveTypes] = useState<LeaveType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingType, setEditingType] = useState<LeaveType | null>(null);
  const [formData, setFormData] = useState({ name: '', description: '', annual_allocation: 0, is_active: true });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    authService.getCurrentUser().then(u => {
      // Typically, permissions should be checked explicitly via roles/permissions.
      // Assuming isStaff handles basic admin interface access as in OfficeNetworksPage.
      if (u?.isStaff) {
        loadLeaveTypes();
      } else {
        setError("You do not have permission to view leave types.");
        setLoading(false);
      }
    }).catch(() => {
      setError("Authentication error.");
      setLoading(false);
    });
  }, []);

  const loadLeaveTypes = async () => {
    setLoading(true);
    try {
      const data = await leaveService.getAdminLeaveTypes();
      setLeaveTypes(data);
      setError(null);
    } catch (err: any) {
      if (err.response?.status === 403) {
        setError("403 Forbidden: You do not have permission to view leave types.");
      } else {
        setError("Failed to load leave types. Backend might be unavailable.");
      }
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = () => {
    setEditingType(null);
    setFormData({ name: '', description: '', annual_allocation: 10, is_active: true });
    setFormError(null);
    setIsModalOpen(true);
  };

  const openEditModal = (leaveType: LeaveType) => {
    setEditingType(leaveType);
    setFormData({ 
      name: leaveType.name, 
      description: leaveType.description, 
      annual_allocation: leaveType.annual_allocation, 
      is_active: leaveType.is_active 
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
      
      if (editingType) {
        await leaveService.updateLeaveType(editingType.id, payload);
      } else {
        await leaveService.createLeaveType(payload);
      }
      setIsModalOpen(false);
      loadLeaveTypes();
    } catch (err: any) {
      if (err.errorData && err.errorData.name) {
        setFormError(err.errorData.name[0]);
      } else if (err.errorData && err.errorData.annual_allocation) {
        setFormError(err.errorData.annual_allocation[0]);
      } else if (err.response?.status === 403) {
        setFormError("Permission denied.");
      } else {
        setFormError("An error occurred while saving.");
      }
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (leaveType: LeaveType) => {
    try {
      await leaveService.updateLeaveType(leaveType.id, { is_active: !leaveType.is_active });
      loadLeaveTypes();
    } catch {
      alert("Failed to toggle status.");
    }
  };

  const handleDelete = async (leaveType: LeaveType) => {
    if (!window.confirm(`Are you sure you want to delete the leave type "${leaveType.name}"?`)) return;
    try {
      await leaveService.deleteLeaveType(leaveType.id);
      loadLeaveTypes();
    } catch (err: any) {
      if (err.response?.status === 409) {
        alert(err.errorData?.detail || "Cannot delete leave type that is in use by balances or requests.");
      } else {
        alert("Failed to delete leave type.");
      }
    }
  };

  const columns = [
    { key: 'name', title: 'Name' },
    { key: 'description', title: 'Description' },
    { key: 'annual_allocation', title: 'Annual Allocation (Days)' },
    { 
      key: 'is_active', 
      title: 'Status', 
      render: (n: LeaveType) => (
        <StatusBadge status={n.is_active ? 'active' : 'inactive'} />
      ) 
    },
    { 
      key: 'actions', 
      title: 'Actions', 
      render: (n: LeaveType) => (
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
    }
  ];

  if (loading && leaveTypes.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  if (error && leaveTypes.length === 0) {
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
        <h1 style={styles.title}>Leave Types Configuration</h1>
        <button style={styles.button} onClick={openCreateModal}>
          <Plus size={18} /> Add Leave Type
        </button>
      </div>

      <Card>
        <Table data={leaveTypes} columns={columns} keyExtractor={(n) => n.id} />
      </Card>

      {isModalOpen && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <h2 style={{ marginTop: 0 }}>{editingType ? 'Edit Leave Type' : 'Add Leave Type'}</h2>
            
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
              <div style={styles.formGroup}>
                <label style={styles.label}>Annual Allocation (Days)</label>
                <input 
                  type="number"
                  min="0"
                  style={styles.input} 
                  value={formData.annual_allocation}
                  onChange={(e) => setFormData({...formData, annual_allocation: parseInt(e.target.value) || 0})}
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
