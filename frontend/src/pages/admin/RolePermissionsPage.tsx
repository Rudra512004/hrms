import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Loader2, ArrowLeft, Check, Info } from 'lucide-react';
import { AlertBanner } from '../../components/AlertBanner';
import { authorizationManagementService } from '../../services/authorizationManagement';
import type { Role, PermissionMatrixResponse } from '../../services/authorizationManagement';
import { useParams, useNavigate } from 'react-router-dom';

export const RolePermissionsPage: React.FC = () => {
  const { roleId } = useParams<{ roleId: string }>();
  const navigate = useNavigate();

  const [role, setRole] = useState<Role | null>(null);
  const [matrix, setMatrix] = useState<PermissionMatrixResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [initialIds, setInitialIds] = useState<Set<number>>(new Set());

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);

  const isSuperAdmin = useMemo(() => {
    return role?.slug === 'super-admin' || role?.badge === 'Full access';
  }, [role]);

  // Check if selections have changed compared to original initial IDs
  const isDirty = useMemo(() => {
    if (isSuperAdmin) return false;
    if (selectedIds.size !== initialIds.size) return true;
    for (const id of selectedIds) {
      if (!initialIds.has(id)) return true;
    }
    return false;
  }, [selectedIds, initialIds, isSuperAdmin]);

  // Unload warning for unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  const loadData = useCallback(async (id: number) => {
    setLoading(true);
    setError(null);
    setSaveSuccess(null);
    try {
      const [roleData, matrixData] = await Promise.all([
        authorizationManagementService.getRole(id),
        authorizationManagementService.getPermissionMatrix()
      ]);

      setRole(roleData);
      setMatrix(matrixData);

      // Collect permission IDs
      let initialPermIds = new Set<number>();
      if (roleData.slug === 'super-admin' || roleData.badge === 'Full access') {
        // Super admin holds all visible matrix controls
        const allVisibleIds = new Set<number>();
        Object.values(matrixData.columns).forEach(columnGroups => {
          columnGroups.forEach(group => {
            group.actions.forEach(action => {
              allVisibleIds.add(action.id);
            });
          });
        });
        initialPermIds = allVisibleIds;
      } else {
        initialPermIds = new Set<number>(roleData.permission_ids || []);
      }

      setSelectedIds(new Set(initialPermIds));
      setInitialIds(new Set(initialPermIds));
    } catch (err: any) {
      if (err.response?.status === 404) {
        setError('Role not found or you do not have permission to access it.');
      } else if (err.response?.status === 403) {
        setError('403 Forbidden: You do not have permission to view this role.');
      } else {
        setError('Failed to load role permissions. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (roleId) {
      loadData(parseInt(roleId, 10));
    }
  }, [roleId, loadData]);

  const handleToggle = (permissionId: number) => {
    if (isSuperAdmin) return; // Super admin cannot be narrowed

    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(permissionId)) {
        next.delete(permissionId);
      } else {
        next.add(permissionId);
      }
      return next;
    });
    setSaveSuccess(null);
  };

  const handleSave = async () => {
    if (!role || isSuperAdmin || saving) return;

    setSaving(true);
    setError(null);
    setSaveSuccess(null);

    const idsToSave = Array.from(selectedIds);
    try {
      const res = await authorizationManagementService.updateRolePermissions(role.id, idsToSave);
      setSaveSuccess(`Permissions updated successfully (${res.permissions_count} permissions).`);
      setInitialIds(new Set(selectedIds));

      // Update role permissions count in local state
      setRole(prev => prev ? {
        ...prev,
        permissions_count: res.permissions_count,
        effective_permissions_count: res.effective_permissions_count,
        permission_ids: idsToSave
      } : null);
    } catch (err: any) {
      // Preserve unsaved selections upon failure
      if (err.errorData?.detail) {
        setError(err.errorData.detail);
      } else if (err.response?.status === 403) {
        setError('403 Forbidden: You do not have permission to update role permissions.');
      } else {
        setError('Failed to update permissions. Please try again.');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleBack = () => {
    if (isDirty) {
      const confirmLeave = window.confirm('You have unsaved permission changes. Are you sure you want to discard them?');
      if (!confirmLeave) return;
    }
    navigate('/admin/roles');
  };

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '400px',
          gap: '12px'
        }}
      >
        <Loader2 size={32} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
        <span style={{ color: 'var(--color-text-muted)' }}>Loading permissions matrix…</span>
      </div>
    );
  }

  if (error && !matrix && !role) {
    return (
      <div style={{ maxWidth: '800px', margin: '40px auto', padding: '24px' }}>
        <AlertBanner type="error" message={error} style={{ marginBottom: '16px' }} />
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => navigate('/admin/roles')}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
        >
          <ArrowLeft size={16} /> Back to Roles
        </button>
      </div>
    );
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px', paddingBottom: '80px' }}>
      {/* Top Header Matching Reference Video */}
      <div>
        <button
          type="button"
          onClick={handleBack}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            color: 'var(--color-text-sub, #5F6B7A)',
            fontSize: '0.875rem',
            fontWeight: 500,
            padding: 0,
            marginBottom: '12px'
          }}
          id="back-to-roles-btn"
        >
          <ArrowLeft size={15} /> Back
        </button>

        <h1
          style={{
            margin: '0 0 4px 0',
            fontSize: '1.75rem',
            fontWeight: 700,
            color: 'var(--color-text-main)'
          }}
          data-testid="role-editor-title"
        >
          {role?.name || 'Role'}
        </h1>
        <p
          style={{
            margin: 0,
            fontSize: '0.875rem',
            color: 'var(--color-text-muted)'
          }}
        >
          Permissions granted by the {role?.slug || 'selected'} role
        </p>
      </div>

      {/* Notifications / Alerts */}
      {saveSuccess && <AlertBanner type="success" message={saveSuccess} />}
      {error && <AlertBanner type="error" message={error} />}

      {/* Super Admin Full Access Banner (Matching Reference Video Frame 00:00) */}
      {isSuperAdmin && (
        <div
          data-testid="super-admin-banner"
          style={{
            backgroundColor: '#EFF6FF',
            border: '1px solid #BFDBFE',
            borderRadius: 'var(--radius-md, 8px)',
            padding: '16px 20px',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '12px',
            color: '#1E40AF'
          }}
        >
          <div
            style={{
              width: 24,
              height: 24,
              borderRadius: '50%',
              backgroundColor: '#DBEAFE',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#1D4ED8',
              flexShrink: 0,
              marginTop: '1px'
            }}
          >
            <Info size={15} />
          </div>
          <div style={{ fontSize: '0.9375rem', lineHeight: 1.5, fontWeight: 500 }}>
            The super admin role always holds every permission, including any added later. Its permission list cannot be narrowed.
          </div>
        </div>
      )}

      {/* 3-Column Permission Matrix Layout (Matching Reference Video Frame 00:01 - 00:05) */}
      {matrix && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
            gap: '24px',
            alignItems: 'start'
          }}
          data-testid="permissions-matrix"
        >
          {['1', '2', '3'].map((colKey) => {
            const categoryGroups = matrix.columns[colKey] || [];
            return (
              <div
                key={`col-${colKey}`}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '24px'
                }}
                data-testid={`column-${colKey}`}
              >
                {categoryGroups.map((group) => {
                  const totalCount = group.actions.length;
                  const selectedCount = group.actions.filter(a => selectedIds.has(a.id)).length;

                  return (
                    <div
                      key={group.category}
                      style={{
                        backgroundColor: 'var(--color-bg-card)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-lg, 12px)',
                        padding: '20px',
                        boxShadow: 'var(--shadow-sm)'
                      }}
                      data-testid={`category-block-${group.category.toLowerCase().replace(/\s+/g, '-')}`}
                    >
                      {/* Category Header with Counter (e.g. Dashboard 2/2, Attendance 4/4) */}
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          marginBottom: '16px',
                          paddingBottom: '10px',
                          borderBottom: '1px solid var(--color-border-subtle, #f1f5f9)'
                        }}
                      >
                        <h3
                          style={{
                            margin: 0,
                            fontSize: '1rem',
                            fontWeight: 600,
                            color: 'var(--color-text-main)'
                          }}
                        >
                          {group.category}
                        </h3>
                        <span
                          style={{
                            fontSize: '0.8125rem',
                            fontWeight: 600,
                            color: selectedCount === totalCount ? 'var(--color-primary)' : 'var(--color-text-muted)',
                            backgroundColor: selectedCount > 0 ? 'var(--color-primary-light, #EAF2FF)' : 'var(--color-bg-secondary, #f1f5f9)',
                            padding: '2px 8px',
                            borderRadius: '9999px'
                          }}
                          data-testid={`count-${group.category.toLowerCase().replace(/\s+/g, '-')}`}
                        >
                          {selectedCount}/{totalCount}
                        </span>
                      </div>

                      {/* Actions Checkboxes List */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {group.actions.map((action) => {
                          const isChecked = selectedIds.has(action.id);
                          const checkboxId = `perm-checkbox-${action.id}`;

                          return (
                            <label
                              key={action.id}
                              htmlFor={checkboxId}
                              style={{
                                display: 'flex',
                                alignItems: 'flex-start',
                                gap: '10px',
                                cursor: isSuperAdmin ? 'default' : 'pointer',
                                fontSize: '0.875rem',
                                color: isChecked ? 'var(--color-text-main)' : 'var(--color-text-sub)',
                                userSelect: 'none',
                                lineHeight: 1.4
                              }}
                            >
                              <input
                                type="checkbox"
                                id={checkboxId}
                                checked={isChecked}
                                disabled={isSuperAdmin}
                                onChange={() => handleToggle(action.id)}
                                style={{
                                  marginTop: '2px',
                                  width: '16px',
                                  height: '16px',
                                  cursor: isSuperAdmin ? 'default' : 'pointer',
                                  accentColor: 'var(--color-primary, #3B82F6)',
                                  flexShrink: 0
                                }}
                                data-testid={`action-checkbox-${action.codename}`}
                              />
                              <span
                                style={{
                                  fontWeight: isChecked ? 500 : 400
                                }}
                              >
                                {action.label || action.name}
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}

      {/* Bottom Sticky Action Bar (Matching Reference Video Frame 00:05) */}
      <div
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          backgroundColor: 'var(--color-bg-card)',
          borderTop: '1px solid var(--color-border)',
          padding: '14px 28px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-start',
          gap: '12px',
          boxShadow: '0 -4px 16px rgba(0, 0, 0, 0.06)',
          zIndex: 40
        }}
      >
        <div style={{ maxWidth: '1440px', width: '100%', margin: '0 auto', display: 'flex', alignItems: 'center', gap: '12px' }}>
          {!isSuperAdmin ? (
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleSave}
              disabled={saving}
              style={{
                backgroundColor: 'var(--color-status-success, #16A34A)',
                borderColor: 'var(--color-status-success, #16A34A)',
                color: '#ffffff',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '9px 20px',
                fontWeight: 600,
                borderRadius: 'var(--radius-md, 8px)'
              }}
              id="save-permissions-btn"
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
              Save permissions
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-secondary"
              disabled
              style={{
                opacity: 0.6,
                cursor: 'not-allowed',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '9px 20px'
              }}
              title="Super Admin permissions cannot be modified"
              id="save-permissions-disabled-btn"
            >
              <Check size={16} /> Save permissions
            </button>
          )}

          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleBack}
            disabled={saving}
            style={{
              padding: '9px 18px',
              borderRadius: 'var(--radius-md, 8px)'
            }}
            id="cancel-permissions-btn"
          >
            Cancel
          </button>

          {isDirty && (
            <span style={{ fontSize: '0.8125rem', color: 'var(--color-status-warning, #d97706)', fontWeight: 500, marginLeft: '8px' }}>
              • Unsaved changes
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
