import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  organizationService,
  type Team,
  type Department,
  type Branch,
} from '../../../services/organization';
import {
  employeeManagementService,
} from '../../../services/employeeManagement';
import { type EmployeeProfile } from '../../../services/employee';
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
    maxWidth: '520px',
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
  },
  filterBar: {
    display: 'flex',
    gap: '12px',
    marginBottom: 'var(--spacing-md)',
  }
};

export const TeamsPage: React.FC = () => {
  const [teams, setTeams] = useState<Team[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [eligibleManagers, setEligibleManagers] = useState<EmployeeProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTeam, setEditingTeam] = useState<Team | null>(null);
  const [modalBranchId, setModalBranchId] = useState<number>(0);
  const [formData, setFormData] = useState({
    name: '',
    department: 0,
    description: '',
    manager: 0,
    is_active: true,
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Department filter state
  const [departmentFilter, setDepartmentFilter] = useState<string>('all');

  const { hasPermission } = useAuth();
  const { branchId, branches: contextBranches } = useBranchContext();

  const canManage = hasPermission('team.manage');

  // Lookups
  const branchMap = useMemo(() => {
    const map = new Map<number, string>();
    branches.forEach(b => map.set(b.id, b.name));
    return map;
  }, [branches]);

  const departmentMap = useMemo(() => {
    const map = new Map<number, Department>();
    departments.forEach(d => map.set(d.id, d));
    return map;
  }, [departments]);

  const managerMap = useMemo(() => {
    const map = new Map<number, string>();
    eligibleManagers.forEach(m => {
      const name = `${m.first_name || ''} ${m.last_name || ''}`.trim() || m.email || `EMP #${m.id}`;
      map.set(m.id, name);
    });
    return map;
  }, [eligibleManagers]);

  // Load all master data based on branch context
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [branchList, deptList] = await Promise.all([
        organizationService.listBranches().catch(() => contextBranches || []),
        branchId ? organizationService.listDepartments(branchId) : organizationService.listDepartments()
      ]);

      const resolvedBranches = Array.isArray(branchList) && branchList.length > 0 ? branchList : (contextBranches || []);
      const resolvedDepts = Array.isArray(deptList) ? deptList : [];
      setBranches(resolvedBranches);
      setDepartments(resolvedDepts);

      // Load all teams
      const teamList = await organizationService.listTeams();
      setTeams(Array.isArray(teamList) ? teamList : []);

      // Load employees for manager resolution
      const empParams = branchId ? { branch_id: branchId, status: 'active' } : { status: 'active' };
      const emps = await employeeManagementService.listEmployees(empParams).catch(() => []);
      setEligibleManagers(Array.isArray(emps) ? emps : []);

      setError(null);
    } catch (err: any) {
      if (err.response?.status === 403) {
        setError("403 Forbidden: You do not have permission to view teams.");
      } else {
        setError("Failed to load teams. Backend might be unavailable.");
      }
    } finally {
      setLoading(false);
    }
  }, [branchId, contextBranches]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Modal branch change: fetch/filter eligible managers for the branch
  const handleModalBranchChange = useCallback(async (newBranchId: number) => {
    setModalBranchId(newBranchId);
    setFormData(prev => ({ ...prev, department: 0, manager: 0 }));

    if (newBranchId > 0) {
      try {
        const branchEmps = await employeeManagementService.listEmployees({
          branch_id: newBranchId,
          status: 'active',
        }).catch(() => []);
        setEligibleManagers(Array.isArray(branchEmps) ? branchEmps : []);
      } catch {
        // Gracefully keep current eligible managers
      }
    }
  }, []);

  const openCreateModal = () => {
    setEditingTeam(null);
    const initialBranch = branchId || (branches.length > 0 ? branches[0].id : 0);
    setModalBranchId(initialBranch);

    // Filter depts for initial branch
    const availableDepts = departments.filter(d => !initialBranch || d.branch === initialBranch);
    const initialDept = availableDepts.length > 0 ? availableDepts[0].id : 0;

    setFormData({
      name: '',
      department: initialDept,
      description: '',
      manager: 0,
      is_active: true,
    });
    setFormError(null);
    setIsModalOpen(true);

    if (initialBranch > 0) {
      handleModalBranchChange(initialBranch);
    }
  };

  const openEditModal = (team: Team) => {
    setEditingTeam(team);
    const dept = departmentMap.get(team.department);
    const currentBranch = dept?.branch || 0;
    setModalBranchId(currentBranch);

    setFormData({
      name: team.name,
      department: team.department,
      description: team.description || '',
      manager: team.manager || 0,
      is_active: team.is_active,
    });
    setFormError(null);
    setIsModalOpen(true);

    if (currentBranch > 0) {
      employeeManagementService.listEmployees({ branch_id: currentBranch, status: 'active' })
        .then(emps => setEligibleManagers(Array.isArray(emps) ? emps : []))
        .catch(() => {});
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      setFormError("Team name is required.");
      return;
    }
    if (!editingTeam && (!formData.department || formData.department === 0)) {
      setFormError("Department is required.");
      return;
    }

    setSaving(true);
    setFormError(null);

    try {
      if (editingTeam) {
        // In TeamSerializer, department is read_only
        await organizationService.updateTeam(editingTeam.id, {
          name: formData.name.trim(),
          description: formData.description,
          manager: formData.manager > 0 ? formData.manager : null,
          is_active: formData.is_active,
        });
      } else {
        await organizationService.createTeam({
          name: formData.name.trim(),
          department: formData.department,
          description: formData.description,
          manager: formData.manager > 0 ? formData.manager : null,
          is_active: formData.is_active,
        });
      }
      setIsModalOpen(false);
      loadData();
    } catch (err: any) {
      if (err.errorData?.name) {
        setFormError(Array.isArray(err.errorData.name) ? err.errorData.name[0] : err.errorData.name);
      } else if (err.errorData?.department) {
        setFormError(Array.isArray(err.errorData.department) ? err.errorData.department[0] : err.errorData.department);
      } else if (err.errorData?.manager) {
        setFormError(Array.isArray(err.errorData.manager) ? err.errorData.manager[0] : err.errorData.manager);
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

  const toggleActive = async (team: Team) => {
    try {
      await organizationService.updateTeam(team.id, { is_active: !team.is_active });
      loadData();
    } catch {
      alert("Failed to toggle status.");
    }
  };

  const handleDelete = async (team: Team) => {
    if (!window.confirm(`Are you sure you want to delete the team "${team.name}"?`)) return;
    try {
      await organizationService.deleteTeam(team.id);
      loadData();
    } catch (err: any) {
      if (err.response?.status === 400 || err.response?.status === 409) {
        alert(err.errorData?.detail || "Cannot delete team while active employees are assigned to it.");
      } else {
        alert("Failed to delete team.");
      }
    }
  };

  // Filter teams by branch context and department filter
  const filteredTeams = useMemo(() => {
    return teams.filter(team => {
      const dept = departmentMap.get(team.department);
      // Branch context filter
      if (branchId !== null && dept && dept.branch !== branchId) {
        return false;
      }
      // Local department dropdown filter
      if (departmentFilter !== 'all' && String(team.department) !== departmentFilter) {
        return false;
      }
      return true;
    });
  }, [teams, departmentMap, branchId, departmentFilter]);

  // Departments available in modal based on modal branch selection
  const modalAvailableDepartments = useMemo(() => {
    if (modalBranchId > 0) {
      return departments.filter(d => d.branch === modalBranchId);
    }
    return departments;
  }, [departments, modalBranchId]);

  const columns = [
    { key: 'id', title: 'ID' },
    { key: 'name', title: 'Team Name' },
    {
      key: 'department',
      title: 'Department',
      render: (t: Team) => {
        const dept = departmentMap.get(t.department);
        return dept ? dept.name : t.department_name || `Dept #${t.department}`;
      }
    },
    {
      key: 'branch',
      title: 'Branch',
      render: (t: Team) => {
        const dept = departmentMap.get(t.department);
        if (dept) {
          return branchMap.get(dept.branch) || dept.branch_name || `Branch #${dept.branch}`;
        }
        return '—';
      }
    },
    {
      key: 'manager',
      title: 'Manager',
      render: (t: Team) => {
        if (!t.manager) return '—';
        return managerMap.get(t.manager) || `EMP #${t.manager}`;
      }
    },
    {
      key: 'is_active',
      title: 'Status',
      render: (t: Team) => (
        <StatusBadge status={t.is_active ? 'active' : 'inactive'} />
      )
    }
  ];

  if (canManage) {
    columns.push({
      key: 'actions',
      title: 'Actions',
      render: (t: Team) => (
        <div>
          <button
            style={styles.actionBtn}
            onClick={() => openEditModal(t)}
            title="Edit"
            data-testid={`edit-team-${t.id}`}
          >
            <Edit2 size={18} />
          </button>
          <button
            style={styles.actionBtn}
            onClick={() => toggleActive(t)}
            title={t.is_active ? "Deactivate" : "Activate"}
            data-testid={`toggle-team-${t.id}`}
          >
            <Power size={18} color={t.is_active ? "var(--color-status-success)" : "var(--color-text-muted)"} />
          </button>
          <button
            style={styles.actionBtn}
            onClick={() => handleDelete(t)}
            title="Delete"
            data-testid={`delete-team-${t.id}`}
          >
            <Trash2 size={18} color="var(--color-status-danger)" />
          </button>
        </div>
      )
    });
  }

  if (loading && teams.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  if (error && teams.length === 0) {
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
        <h1 style={styles.title}>Teams</h1>
        {canManage && (
          <button style={styles.button} onClick={openCreateModal} data-testid="add-team-btn">
            <Plus size={18} /> Add Team
          </button>
        )}
      </div>

      <div style={styles.filterBar}>
        <select
          style={{ ...styles.input, maxWidth: '240px' }}
          value={departmentFilter}
          onChange={(e) => setDepartmentFilter(e.target.value)}
          data-testid="department-filter"
        >
          <option value="all">All Departments</option>
          {departments.map(d => (
            <option key={d.id} value={String(d.id)}>{d.name}</option>
          ))}
        </select>
      </div>

      <Card>
        {filteredTeams.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-muted)' }}>
            No teams found.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <Table data={filteredTeams} columns={columns} keyExtractor={(t) => t.id} />
          </div>
        )}
      </Card>

      {isModalOpen && (
        <div style={styles.modalOverlay} data-testid="team-modal">
          <div style={styles.modalContent}>
            <h2 style={{ marginTop: 0 }}>{editingTeam ? 'Edit Team' : 'Add Team'}</h2>

            {formError && (
              <div style={styles.errorBox} data-testid="team-form-error">
                <AlertCircle size={18} /> {formError}
              </div>
            )}

            <form onSubmit={handleSave}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Team Name</label>
                <input
                  style={styles.input}
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                  data-testid="team-name-input"
                  placeholder="e.g. Frontend Core"
                />
              </div>

              {!editingTeam && branchId === null && (
                <div style={styles.formGroup}>
                  <label style={styles.label}>Branch</label>
                  <select
                    style={styles.input}
                    value={modalBranchId}
                    onChange={(e) => handleModalBranchChange(parseInt(e.target.value, 10))}
                    data-testid="team-branch-select"
                  >
                    <option value={0} disabled>Select a branch</option>
                    {branches.map(b => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </select>
                </div>
              )}

              <div style={styles.formGroup}>
                <label style={styles.label}>Department</label>
                <select
                  style={styles.input}
                  value={formData.department}
                  onChange={(e) => setFormData({ ...formData, department: parseInt(e.target.value, 10) })}
                  required
                  disabled={!!editingTeam}
                  data-testid="team-department-select"
                >
                  <option value={0} disabled>Select a department</option>
                  {modalAvailableDepartments.map(d => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
                {editingTeam && (
                  <div style={styles.helperText}>Department cannot be changed once a team is created.</div>
                )}
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>Team Manager</label>
                <select
                  style={styles.input}
                  value={formData.manager}
                  onChange={(e) => setFormData({ ...formData, manager: parseInt(e.target.value, 10) })}
                  data-testid="team-manager-select"
                >
                  <option value={0}>None (No Manager)</option>
                  {eligibleManagers.map(m => (
                    <option key={m.id} value={m.id}>
                      {m.first_name} {m.last_name} ({m.employee_code || m.email})
                    </option>
                  ))}
                </select>
                <div style={styles.helperText}>
                  Only active employees in the team's branch can be assigned as manager.
                </div>
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>Description</label>
                <input
                  style={styles.input}
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  data-testid="team-desc-input"
                  placeholder="Optional description"
                />
              </div>

              <div style={styles.modalActions}>
                <button
                  type="button"
                  style={styles.cancelBtn}
                  onClick={() => setIsModalOpen(false)}
                  data-testid="team-cancel-btn"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={styles.button}
                  disabled={saving}
                  data-testid="team-save-btn"
                >
                  {saving ? <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} /> : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
