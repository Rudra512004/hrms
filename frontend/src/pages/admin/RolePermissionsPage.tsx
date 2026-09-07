import React, { useState, useEffect } from 'react';
import { Card } from '../../components/Card';
import { Loader2, AlertCircle, ArrowLeft } from 'lucide-react';
import { authorizationManagementService } from '../../services/authorizationManagement';
import type { Role, Permission, RolePermission } from '../../services/authorizationManagement';
import { useParams, useNavigate } from 'react-router-dom';

const styles = {
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    marginBottom: '24px',
  },
  title: {
    margin: 0,
    color: 'var(--color-text-main)',
    fontSize: '1.75rem',
  },
  backBtn: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: 'var(--color-text-main)',
    padding: '8px',
    borderRadius: '50%',
    backgroundColor: 'var(--color-bg-secondary)',
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
    gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
    gap: '16px',
    marginTop: '16px',
  },
  permCard: {
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-md)',
    padding: '16px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: 'var(--color-bg-main)',
  },
  permInfo: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '4px',
  },
  permName: {
    fontWeight: 600,
    color: 'var(--color-text-main)',
  },
  permDesc: {
    fontSize: '0.85rem',
    color: 'var(--color-text-muted)',
  },
  toggle: {
    cursor: 'pointer',
    width: '40px',
    height: '24px',
    borderRadius: '12px',
    position: 'relative' as const,
    transition: 'background-color 0.2s',
  },
  toggleKnob: {
    width: '20px',
    height: '20px',
    backgroundColor: 'white',
    borderRadius: '50%',
    position: 'absolute' as const,
    top: '2px',
    transition: 'transform 0.2s',
    boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
  }
};

export const RolePermissionsPage: React.FC = () => {
  const { roleId } = useParams<{ roleId: string }>();
  const navigate = useNavigate();
  
  const [role, setRole] = useState<Role | null>(null);
  const [allPermissions, setAllPermissions] = useState<Permission[]>([]);
  const [rolePermissions, setRolePermissions] = useState<RolePermission[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (roleId) {
      loadData(parseInt(roleId));
    }
  }, [roleId]);

  const loadData = async (id: number) => {
    setLoading(true);
    try {
      const [roles, perms, rPerms] = await Promise.all([
        authorizationManagementService.listRoles(),
        authorizationManagementService.listPermissions(),
        authorizationManagementService.listRolePermissions(id)
      ]);
      
      const currentRole = roles.find(r => r.id === id);
      if (currentRole) setRole(currentRole);
      
      setAllPermissions(perms);
      setRolePermissions(rPerms);
      setError(null);
    } catch (err: any) {
      if (err.response?.status === 403) {
        setError("403 Forbidden: You do not have permission to view this.");
      } else {
        setError("Failed to load permissions.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (permission: Permission) => {
    if (!roleId) return;
    
    const existing = rolePermissions.find(rp => rp.permission === permission.id);
    
    try {
      if (existing) {
        await authorizationManagementService.revokePermissionFromRole(existing.id);
      } else {
        await authorizationManagementService.assignPermissionToRole(parseInt(roleId), permission.id);
      }
      // Reload just the role permissions
      const rPerms = await authorizationManagementService.listRolePermissions(parseInt(roleId));
      setRolePermissions(rPerms);
    } catch (err: any) {
      alert(err.errorData?.detail || "Failed to update permission.");
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <div style={styles.errorBox}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
        <button style={styles.backBtn} onClick={() => navigate('/admin/roles')}>
          <ArrowLeft size={18} /> Back to Roles
        </button>
      </Card>
    );
  }

  return (
    <div>
      <div style={styles.header}>
        <button style={styles.backBtn} onClick={() => navigate('/admin/roles')} title="Back to Roles">
          <ArrowLeft size={20} />
        </button>
        <h1 style={styles.title}>
          Permissions for: {role?.name || 'Unknown Role'}
        </h1>
      </div>

      <Card>
        <p style={{ margin: '0 0 16px 0', color: 'var(--color-text-muted)' }}>
          Enable or disable specific permissions for this role.
        </p>
        
        <div style={styles.grid}>
          {allPermissions.map(perm => {
            const hasPerm = rolePermissions.some(rp => rp.permission === perm.id);
            return (
              <div key={perm.id} style={styles.permCard}>
                <div style={styles.permInfo}>
                  <span style={styles.permName}>{perm.codename}</span>
                  <span style={styles.permDesc}>{perm.description || `${perm.action} on ${perm.resource}`}</span>
                </div>
                <div 
                  style={{
                    ...styles.toggle,
                    backgroundColor: hasPerm ? 'var(--color-status-success)' : 'var(--color-border)'
                  }}
                  onClick={() => handleToggle(perm)}
                >
                  <div style={{
                    ...styles.toggleKnob,
                    transform: hasPerm ? 'translateX(18px)' : 'translateX(2px)'
                  }} />
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
};
