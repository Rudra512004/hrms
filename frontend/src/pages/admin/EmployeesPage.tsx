import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { employeeManagementService } from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import { organizationService, type Organization, type Department, type Designation } from '../../services/organization';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { Plus, Edit2, Shield, Power, AlertCircle, Loader2 } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';


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
    padding: 'var(--spacing-md)',
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

export const EmployeesPage: React.FC = () => {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [employees, setEmployees] = useState<EmployeeProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState<EmployeeProfile | null>(null);

  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [designations, setDesignations] = useState<Designation[]>([]);
  const [managers, setManagers] = useState<EmployeeProfile[]>([]);

  const [formData, setFormData] = useState({
    email: '',
    personal_email: '',
    first_name: '',
    last_name: '',
    employee_code: '',
    phone_number: '',
    address: '',
    organization: 0,
    department: 0,
    designation: 0,
    reporting_manager: 0
  });

  const [formError, setFormError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadEmployees();
  }, []);

  const loadEmployees = async () => {
    setLoading(true);
    try {
      const data = await employeeManagementService.listEmployees();
      setEmployees(data);
      setError(null);
    } catch (err: any) {
      if (err.message?.includes('403')) {
        setError("403 Forbidden: Access Denied.");
      } else {
        setError("Failed to load employees. Backend might be unavailable.");
      }
    } finally {
      setLoading(false);
    }
  };

  const loadOrgData = async (orgId?: number) => {
    try {
      if (!organizations.length) {
        const orgs = await organizationService.listOrganizations().catch(() => []);
        setOrganizations(orgs);
      }
      if (orgId) {
        const [depts, desigs] = await Promise.all([
          organizationService.listDepartments(orgId).catch(() => []),
          organizationService.listDesignations(orgId).catch(() => [])
        ]);
        setDepartments(depts);
        setDesignations(desigs);
        
        // Filter managers to those in the same organization
        const orgManagers = employees.filter(e => e.organization === orgId && e.status === 'active');
        setManagers(orgManagers);
      } else {
        setDepartments([]);
        setDesignations([]);
        setManagers([]);
      }
    } catch (e) {
      console.error("Failed to load organizational data", e);
    }
  };

  const handleOrgChange = (orgId: number) => {
    setFormData(prev => ({ ...prev, organization: orgId, department: 0, designation: 0, reporting_manager: 0 }));
    loadOrgData(orgId);
  };

  const openCreateModal = () => {
    setEditingEmployee(null);
    setFormData({ 
      email: '', personal_email: '', first_name: '', last_name: '', employee_code: '', 
      phone_number: '', address: '', organization: 0, department: 0, designation: 0, reporting_manager: 0 
    });
    setFormError(null);
    setIsModalOpen(true);
    loadOrgData();
  };

  const openEditModal = (emp: EmployeeProfile) => {
    setEditingEmployee(emp);
    setFormData({
      email: emp.email,
      personal_email: '',
      first_name: emp.first_name,
      last_name: emp.last_name,
      employee_code: emp.employee_code,
      phone_number: emp.phone_number || '',
      address: emp.address || '',
      organization: emp.organization || 0,
      department: emp.department || 0,
      designation: emp.designation || 0,
      reporting_manager: emp.reporting_manager || 0
    });
    setFormError(null);
    setIsModalOpen(true);
    if (emp.organization) {
      loadOrgData(emp.organization);
    } else {
      loadOrgData();
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFormError(null);

    try {
      const payload: any = {};
      if (formData.organization) payload.organization = formData.organization;
      if (formData.department) payload.department = formData.department;
      if (formData.designation) payload.designation = formData.designation;
      if (formData.reporting_manager) payload.reporting_manager = formData.reporting_manager;

      if (editingEmployee) {
        payload.phone_number = formData.phone_number;
        payload.address = formData.address;
        await employeeManagementService.updateEmployee(editingEmployee.id, payload);
      } else {
        const result = await employeeManagementService.createEmployee({
          email: formData.email,
          personal_email: formData.personal_email,
          first_name: formData.first_name,
          last_name: formData.last_name,
          employee_code: formData.employee_code,
          ...payload
        });

        let msg = `Employee created.`;
        if (result.onboarding_email_status === 'sent') {
          msg = "Employee created. Onboarding email sent.";
        } else if (result.onboarding_email_status === 'queued') {
          msg = "Employee created. Onboarding email queued.";
        } else if (result.onboarding_email_status === 'failed') {
          msg = "Employee created, but the onboarding email could not be sent.";
        }
        setSuccessMessage(msg);
        setTimeout(() => setSuccessMessage(null), 10000);
      }
      setIsModalOpen(false);
      loadEmployees();
    } catch (err: any) {
      if (err.errorData) {
        const errorMsgs = Object.entries(err.errorData).map(([key, val]) => `${key}: ${val}`).join(' | ');
        setFormError(errorMsgs || "Validation error.");
      } else if (err.response?.status === 403) {
        setFormError("Permission denied.");
      } else {
        setFormError("An error occurred while saving.");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDeactivate = async (emp: EmployeeProfile) => {
    if (!window.confirm(`Deactivate employee ${emp.first_name} ${emp.last_name}?`)) return;
    try {
      await employeeManagementService.deactivateEmployee(emp.id);
      loadEmployees();
    } catch (err: any) {
      if (err.errorData?.detail) {
        alert(err.errorData.detail);
      } else if (err.response?.status === 403) {
        alert("Permission denied to deactivate.");
      } else {
        alert("Failed to deactivate employee.");
      }
    }
  };

  const handleActivate = async (emp: EmployeeProfile) => {
    if (!window.confirm(`Reactivate employee ${emp.first_name} ${emp.last_name}?`)) return;
    try {
      await employeeManagementService.activateEmployee(emp.id);
      loadEmployees();
    } catch (err: any) {
      if (err.errorData?.detail) {
        alert(err.errorData.detail);
      } else if (err.response?.status === 403) {
        alert("Permission denied to activate.");
      } else {
        alert("Failed to activate employee.");
      }
    }
  };

  const columns = [
    { key: 'employee_code', title: 'Code' },
    { key: 'name', title: 'Name', render: (e: EmployeeProfile) => `${e.first_name} ${e.last_name}` },
    { key: 'department', title: 'Department', render: (e: EmployeeProfile) => e.department_name || '-' },
    { key: 'designation', title: 'Designation', render: (e: EmployeeProfile) => e.designation_name || '-' },
    {
      key: 'status',
      title: 'Status',
      render: (e: EmployeeProfile) => (
        <StatusBadge status={e.status as any} />
      )
    },
    {
      key: 'actions',
      title: 'Actions',
      render: (e: EmployeeProfile) => (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
          <button style={styles.actionBtn} onClick={() => openEditModal(e)} title="Edit">
            <Edit2 size={18} />
          </button>
          <button style={styles.actionBtn} onClick={() => navigate(`/admin/employees/${e.id}/access`)} title="RBAC Access">
            <Shield size={18} color="var(--color-primary)" />
          </button>
          <button
            style={styles.actionBtn}
            onClick={() => e.status === 'active' ? handleDeactivate(e) : handleActivate(e)}
            title={e.status === 'active' ? "Deactivate" : "Activate"}
          >
            <Power size={18} color={e.status === 'active' ? "var(--color-status-danger)" : "var(--color-status-success)"} />
          </button>
        </div>
      )
    }
  ];

  if (loading && employees.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  if (error && employees.length === 0) {
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
        <h1 style={styles.title}>Employee Management</h1>
        <button className="btn btn-primary" onClick={openCreateModal}>
          <Plus size={18} /> Add Employee
        </button>
      </div>

      {successMessage && (
        <Card className="mb-4">
          <div style={{...styles.errorBox, backgroundColor: 'rgba(34, 197, 94, 0.1)', color: 'var(--color-status-success)'}}>
            <Shield size={20} />
            <span>{successMessage}</span>
          </div>
        </Card>
      )}

      <Card>
        <div style={{ overflowX: 'auto' }}>
          <Table data={employees} columns={columns} keyExtractor={(e) => e.id} />
        </div>
      </Card>

      {isModalOpen && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <h2 style={{ marginTop: 0 }}>{editingEmployee ? 'Edit Employee Info' : 'Provision Employee'}</h2>

            {formError && (
              <div style={styles.errorBox}>
                <AlertCircle size={18} /> {formError}
              </div>
            )}

            <form onSubmit={handleSave}>
              {editingEmployee && (
                <div style={{ marginBottom: '16px', padding: '12px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-md)' }}>
                  <strong>HR Controlled Fields</strong>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                    Email, name, and employee code cannot be changed.
                  </div>
                </div>
              )}

              {!editingEmployee && (
                <>
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Email</label>
                    <input
                      style={styles.input}
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({...formData, email: e.target.value})}
                      required
                    />
                  </div>
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Personal Email</label>
                    <input
                      style={styles.input}
                      type="email"
                      value={formData.personal_email}
                      onChange={(e) => setFormData({...formData, personal_email: e.target.value})}
                      required
                    />
                  </div>
                  <div style={{ display: 'flex', gap: 'var(--spacing-md)' }}>
                    <div style={{ ...styles.formGroup, flex: 1 }}>
                      <label style={styles.label}>First Name</label>
                      <input
                        style={styles.input}
                        value={formData.first_name}
                        onChange={(e) => setFormData({...formData, first_name: e.target.value})}
                        required
                      />
                    </div>
                    <div style={{ ...styles.formGroup, flex: 1 }}>
                      <label style={styles.label}>Last Name</label>
                      <input
                        style={styles.input}
                        value={formData.last_name}
                        onChange={(e) => setFormData({...formData, last_name: e.target.value})}
                        required
                      />
                    </div>
                  </div>
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Employee Code</label>
                    <input
                      style={styles.input}
                      value={formData.employee_code}
                      onChange={(e) => setFormData({...formData, employee_code: e.target.value})}
                      required
                    />
                  </div>
                </>
              )}

              {/* Organization Assignment Section */}
              <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid var(--color-border)' }}>
                <h3 style={{ marginTop: 0, marginBottom: '16px', fontSize: '1.1rem' }}>Organization Assignment</h3>
                
                <div style={styles.formGroup}>
                  <label style={styles.label}>Organization</label>
                  <select 
                    style={styles.input}
                    value={formData.organization}
                    onChange={(e) => handleOrgChange(parseInt(e.target.value))}
                  >
                    <option value={0}>None</option>
                    {organizations.map(org => (
                      <option key={org.id} value={org.id}>{org.name}</option>
                    ))}
                  </select>
                </div>

                <div style={styles.formGroup}>
                  <label style={styles.label}>Department</label>
                  <select 
                    style={styles.input}
                    value={formData.department}
                    onChange={(e) => setFormData({...formData, department: parseInt(e.target.value)})}
                    disabled={!formData.organization}
                  >
                    <option value={0}>None</option>
                    {departments.map(dept => (
                      <option key={dept.id} value={dept.id}>{dept.name}</option>
                    ))}
                  </select>
                </div>

                <div style={styles.formGroup}>
                  <label style={styles.label}>Designation</label>
                  <select 
                    style={styles.input}
                    value={formData.designation}
                    onChange={(e) => setFormData({...formData, designation: parseInt(e.target.value)})}
                    disabled={!formData.organization}
                  >
                    <option value={0}>None</option>
                    {designations.map(desig => (
                      <option key={desig.id} value={desig.id}>{desig.name}</option>
                    ))}
                  </select>
                </div>

                {hasPermission('hierarchy.manage') && (
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Reporting Manager</label>
                    <select 
                      style={styles.input}
                      value={formData.reporting_manager}
                      onChange={(e) => setFormData({...formData, reporting_manager: parseInt(e.target.value)})}
                      disabled={!formData.organization}
                    >
                      <option value={0}>None</option>
                      {managers
                        .filter(m => m.id !== editingEmployee?.id) // Cannot report to self
                        .map(m => (
                        <option key={m.id} value={m.id}>{m.first_name} {m.last_name} ({m.employee_code})</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              {editingEmployee && (
                <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid var(--color-border)' }}>
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Phone Number</label>
                    <input
                      style={styles.input}
                      value={formData.phone_number}
                      onChange={(e) => setFormData({...formData, phone_number: e.target.value})}
                    />
                  </div>
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Address</label>
                    <input
                      style={styles.input}
                      value={formData.address}
                      onChange={(e) => setFormData({...formData, address: e.target.value})}
                    />
                  </div>
                </div>
              )}

              <div style={styles.modalActions}>
                <button type="button" style={styles.cancelBtn} onClick={() => setIsModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
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
