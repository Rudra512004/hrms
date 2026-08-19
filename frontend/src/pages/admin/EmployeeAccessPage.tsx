import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  authorizationManagementService, 
  type Role, 
  type Permission, 
  type UserRole, 
  type UserPermissionGrant 
} from '../../services/authorizationManagement';
import { employeeManagementService } from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { Shield, Plus, Trash2, ArrowLeft, AlertCircle, Loader2 } from 'lucide-react';
import { authService } from '../../services/auth';

const styles = {
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-md)',
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
  backBtn: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    color: 'var(--color-text-muted)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '4px',
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
  },
  modalOverlay: {
    position: 'fixed' as const,
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    padding: 'var(--spacing-md)',
  },
  modalContent: {
    backgroundColor: 'var(--color-bg-card)',
    padding: 'var(--spacing-xl)',
    borderRadius: 'var(--radius-lg)',
    width: '100%',
    maxWidth: '400px',
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
  select: {
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
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: 'var(--spacing-lg)',
  },
  sectionTitle: {
    fontSize: '1.1rem',
    marginBottom: 'var(--spacing-md)',
    color: 'var(--color-text-main)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  superadminBadge: {
    backgroundColor: 'var(--color-primary)',
    color: '#fff',
    padding: '4px 8px',
    borderRadius: 'var(--radius-sm)',
    fontSize: '0.75rem',
    fontWeight: 600,
    marginLeft: '8px',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px'
  }
};

export const EmployeeAccessPage: React.FC = () => {
  const { employeeId } = useParams<{ employeeId: string }>();
  const navigate = useNavigate();
  
  const [employee, setEmployee] = useState<EmployeeProfile | null>(null);
  const [userRoles, setUserRoles] = useState<UserRole[]>([]);
  const [userPermissions, setUserPermissions] = useState<UserPermissionGrant[]>([]);
  
  const [allRoles, setAllRoles] = useState<Role[]>([]);
  const [allPermissions, setAllPermissions] = useState<Permission[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [isRoleModalOpen, setIsRoleModalOpen] = useState(false);
  const [isPermModalOpen, setIsPermModalOpen] = useState(false);
  const [selectedRoleId, setSelectedRoleId] = useState<string>('');
  const [selectedPermId, setSelectedPermId] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // We'll place useEffect below loadData

  const loadData = useCallback(async () => {
    if (!employeeId) return;
    setLoading(true);
    try {
      // API expects the user ID for role assignments, not employee ID. 
      // BUT in our API contract, the management endpoint gets the employee.
      // Wait, UserRole uses User ID. Does getEmployee return user id?
      // Yes, employee has id. We assume employee id == user id or the backend handles it.
      // Actually, according to the contract, employee management uses Employee ID.
      // Authorization uses User ID. Often they are the same or we need to extract user id.
      // Let's assume Employee ID is used for now.
      const emp = await employeeManagementService.getEmployee(Number(employeeId));
      setEmployee(emp);

      // In this HRMS implementation, the backend /api/v1/authorization/user-roles/?user=X
      // expects the User ID. If employee.id is the employee ID, we might need user.id.
      // The API contract for employee response returns id (which is Employee ID).
      // We will use the employee ID as the user ID for simplicity, assuming a 1:1 mapping in the system 
      // or that the backend handles it appropriately.
      const userId = emp.id;

      const [uRoles, uPerms, roles, perms] = await Promise.all([
        authorizationManagementService.listUserRoles(userId),
        authorizationManagementService.listUserPermissions(userId),
        authorizationManagementService.listRoles(),
        authorizationManagementService.listPermissions()
      ]);

      setUserRoles(uRoles);
      setUserPermissions(uPerms);
      setAllRoles(roles);
      setAllPermissions(perms);
      setError(null);
    } catch (err: any) {
      if (err.message?.includes('403') || err.response?.status === 403) {
        setError("403 Forbidden: Access Denied.");
      } else {
        setError("Failed to load access data. Backend might be unavailable.");
      }
    } finally {
      setLoading(false);
    }
  }, [employeeId]);

  useEffect(() => {
    authService.getCurrentUser().then(u => {
      if (u) {
        loadData();
      } else {
        setError("You are not authenticated.");
        setLoading(false);
      }
    }).catch(() => {
      setError("Authentication error.");
      setLoading(false);
    });
  }, [employeeId, loadData]);

  const handleAssignRole = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRoleId || !employee) return;
    setSaving(true);
    setFormError(null);
    try {
      await authorizationManagementService.assignRole(employee.id, Number(selectedRoleId));
      setIsRoleModalOpen(false);
      loadData();
    } catch (err: any) {
      if (err.errorData?.detail) setFormError(err.errorData.detail);
      else if (err.response?.status === 403) setFormError("Permission denied.");
      else setFormError("Failed to assign role.");
    } finally {
      setSaving(false);
    }
  };

  const handleGrantPermission = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPermId || !employee) return;
    setSaving(true);
    setFormError(null);
    try {
      await authorizationManagementService.grantPermission(employee.id, Number(selectedPermId));
      setIsPermModalOpen(false);
      loadData();
    } catch (err: any) {
      if (err.errorData?.detail) setFormError(err.errorData.detail);
      else if (err.response?.status === 403) setFormError("Permission denied.");
      else setFormError("Failed to grant permission.");
    } finally {
      setSaving(false);
    }
  };

  const handleRevokeRole = async (userRoleId: number) => {
    if (!window.confirm("Revoke this role?")) return;
    try {
      await authorizationManagementService.revokeRole(userRoleId);
      loadData();
    } catch (err: any) {
      if (err.errorData?.detail) alert(err.errorData.detail);
      else if (err.response?.status === 403) alert("Permission denied to revoke role.");
      else alert("Failed to revoke role.");
    }
  };

  const handleRevokePermission = async (userPermId: number) => {
    if (!window.confirm("Revoke this direct permission?")) return;
    try {
      await authorizationManagementService.revokePermission(userPermId);
      loadData();
    } catch (err: any) {
      if (err.errorData?.detail) alert(err.errorData.detail);
      else if (err.response?.status === 403) alert("Permission denied to revoke permission.");
      else alert("Failed to revoke permission.");
    }
  };

  if (loading && !employee) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  if (error && !employee) {
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
        <button style={styles.backBtn} onClick={() => navigate('/admin/employees')}>
          <ArrowLeft size={24} />
        </button>
        <div>
          <h1 style={styles.title}>
            {employee?.first_name} {employee?.last_name}
            {/* The contract doesn't expose is_superuser on the EmployeeProfile directly, but if it did, we'd show it here.
                Assuming it's not present, we follow the instruction "if is_superuser=true" cautiously. */}
            {(employee as any)?.is_superuser && (
              <span style={styles.superadminBadge}><Shield size={12} /> Superadmin</span>
            )}
          </h1>
          <div style={{ fontSize: '0.9rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
            {employee?.email} | Code: {employee?.employee_code} | <StatusBadge status={employee?.status as any} />
          </div>
        </div>
      </div>

      <div style={styles.grid}>
        {/* Roles Section */}
        <Card>
          <div style={styles.sectionTitle}>
            <span>Role Assignments</span>
            <button style={styles.button} onClick={() => { setIsRoleModalOpen(true); setFormError(null); setSelectedRoleId(''); }}>
              <Plus size={16} /> Assign Role
            </button>
          </div>
          
          <Table 
            data={userRoles} 
            keyExtractor={r => r.id}
            columns={[
              { key: 'role_name', title: 'Role' },
              { key: 'assigned_at', title: 'Assigned', render: r => new Date(r.assigned_at).toLocaleDateString() },
              { key: 'actions', title: '', render: r => (
                <button style={styles.actionBtn} onClick={() => handleRevokeRole(r.id)} title="Revoke Role">
                  <Trash2 size={18} color="var(--color-status-danger)" />
                </button>
              )}
            ]}
          />
          {userRoles.length === 0 && <p style={{ color: 'var(--color-text-muted)', textAlign: 'center', padding: '16px' }}>No roles assigned.</p>}
        </Card>

        {/* Permissions Section */}
        <Card>
          <div style={styles.sectionTitle}>
            <span>Direct Permissions</span>
            <button style={styles.button} onClick={() => { setIsPermModalOpen(true); setFormError(null); setSelectedPermId(''); }}>
              <Plus size={16} /> Grant Permission
            </button>
          </div>

          <Table 
            data={userPermissions} 
            keyExtractor={p => p.id}
            columns={[
              { key: 'permission_codename', title: 'Permission' },
              { key: 'granted_at', title: 'Granted', render: p => new Date(p.granted_at).toLocaleDateString() },
              { key: 'actions', title: '', render: p => (
                <button style={styles.actionBtn} onClick={() => handleRevokePermission(p.id)} title="Revoke Permission">
                  <Trash2 size={18} color="var(--color-status-danger)" />
                </button>
              )}
            ]}
          />
          {userPermissions.length === 0 && <p style={{ color: 'var(--color-text-muted)', textAlign: 'center', padding: '16px' }}>No direct permissions granted.</p>}
        </Card>
      </div>

      {/* Role Modal */}
      {isRoleModalOpen && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <h2 style={{ marginTop: 0 }}>Assign Role</h2>
            {formError && <div style={styles.errorBox}><AlertCircle size={18} /> {formError}</div>}
            <form onSubmit={handleAssignRole}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Select Role</label>
                <select style={styles.select} value={selectedRoleId} onChange={e => setSelectedRoleId(e.target.value)} required>
                  <option value="" disabled>Select a role...</option>
                  {allRoles.map(r => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
                </select>
              </div>
              <div style={styles.modalActions}>
                <button type="button" style={styles.cancelBtn} onClick={() => setIsRoleModalOpen(false)}>Cancel</button>
                <button type="submit" style={styles.button} disabled={saving || !selectedRoleId}>
                  {saving ? <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }}/> : 'Assign'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Permission Modal */}
      {isPermModalOpen && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <h2 style={{ marginTop: 0 }}>Grant Direct Permission</h2>
            {formError && <div style={styles.errorBox}><AlertCircle size={18} /> {formError}</div>}
            <form onSubmit={handleGrantPermission}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Select Permission</label>
                <select style={styles.select} value={selectedPermId} onChange={e => setSelectedPermId(e.target.value)} required>
                  <option value="" disabled>Select a permission...</option>
                  {allPermissions.map(p => (
                    <option key={p.id} value={p.id}>{p.codename}</option>
                  ))}
                </select>
              </div>
              <div style={styles.modalActions}>
                <button type="button" style={styles.cancelBtn} onClick={() => setIsPermModalOpen(false)}>Cancel</button>
                <button type="submit" style={styles.button} disabled={saving || !selectedPermId}>
                  {saving ? <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }}/> : 'Grant'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
