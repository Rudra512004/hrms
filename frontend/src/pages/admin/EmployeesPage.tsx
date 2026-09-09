import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { employeeManagementService } from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import { organizationService, type Organization, type Department, type Designation } from '../../services/organization';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { Plus, Edit2, Shield, Power, AlertCircle, Loader2, Search, Eye } from 'lucide-react';
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
    maxWidth: '600px',
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
  },
  sectionTitle: {
    marginTop: '24px',
    marginBottom: '16px',
    fontSize: '1.1rem',
    paddingBottom: '8px',
    borderBottom: '1px solid var(--color-border)'
  },
  filterGroup: {
    display: 'flex',
    gap: '12px',
    marginBottom: 'var(--spacing-md)',
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

  const [isStatusModalOpen, setIsStatusModalOpen] = useState(false);
  const [statusEmployee, setStatusEmployee] = useState<EmployeeProfile | null>(null);
  const [newStatus, setNewStatus] = useState('');

  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [designations, setDesignations] = useState<Designation[]>([]);
  const [managers, setManagers] = useState<EmployeeProfile[]>([]);

  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('all');

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
    reporting_manager: 0,
    joining_date: '',
    exit_date: ''
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
        const orgManagers = employees.filter(e => e.organization === orgId && (e.employment_status === 'active' || e.status === 'active'));
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
      phone_number: '', address: '', organization: 0, department: 0, designation: 0, reporting_manager: 0,
      joining_date: '', exit_date: ''
    });
    setFormError(null);
    setIsModalOpen(true);
    loadOrgData();
  };

  const openEditModal = (emp: EmployeeProfile) => {
    setEditingEmployee(emp);
    setFormData({
      email: emp.email,
      personal_email: emp.personal_email || '',
      first_name: emp.first_name,
      last_name: emp.last_name,
      employee_code: emp.employee_code,
      phone_number: emp.phone_number || '',
      address: emp.address || '',
      organization: emp.organization || 0,
      department: emp.department || 0,
      designation: emp.designation || 0,
      reporting_manager: emp.reporting_manager || 0,
      joining_date: emp.joining_date || '',
      exit_date: emp.exit_date || ''
    });
    setFormError(null);
    setIsModalOpen(true);
    if (emp.organization) {
      loadOrgData(emp.organization);
    } else {
      loadOrgData();
    }
  };

  const openStatusModal = (emp: EmployeeProfile) => {
    setStatusEmployee(emp);
    setNewStatus(emp.employment_status || emp.status);
    setFormError(null);
    setIsStatusModalOpen(true);
  };

  const handleStatusChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!statusEmployee) return;

    setSaving(true);
    setFormError(null);
    try {
      await employeeManagementService.changeEmploymentStatus(statusEmployee.id, newStatus);
      setSuccessMessage(`Status updated to ${newStatus}.`);
      setTimeout(() => setSuccessMessage(null), 5000);
      setIsStatusModalOpen(false);
      loadEmployees();
    } catch (err: any) {
      if (err.errorData?.detail) {
        setFormError(err.errorData.detail);
      } else if (err.errorData) {
        const errorMsgs = Object.entries(err.errorData).map(([key, val]) => `${key}: ${val}`).join(' | ');
        setFormError(errorMsgs || "Validation error.");
      } else if (err.response?.status === 403) {
        setFormError("Permission denied.");
      } else {
        setFormError("Failed to update status.");
      }
    } finally {
      setSaving(false);
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
      if (formData.joining_date) payload.joining_date = formData.joining_date;
      if (formData.exit_date) payload.exit_date = formData.exit_date;

      if (editingEmployee) {
        // Only include sensitive fields if they were exposed by the backend
        if (editingEmployee.phone_number !== undefined) payload.phone_number = formData.phone_number;
        if (editingEmployee.address !== undefined) payload.address = formData.address;

        await employeeManagementService.updateEmployee(editingEmployee.id, payload);
        setSuccessMessage("Employee updated successfully.");
      } else {
        const result = await employeeManagementService.createEmployee({
          email: formData.email,
          personal_email: formData.personal_email,
          first_name: formData.first_name,
          last_name: formData.last_name,
          ...payload
        });

        let msg = `Employee created successfully.\n\nEmployee ID: ${result.employee.employee_code}`;
        if (result.onboarding_email_status === 'sent') {
          msg += "\nOnboarding email sent.";
        } else if (result.onboarding_email_status === 'queued') {
          msg += "\nOnboarding email queued.";
        } else if (result.onboarding_email_status === 'failed') {
          msg += "\nWarning: Onboarding email could not be sent.";
        }
        setSuccessMessage(msg);
      }
      setTimeout(() => setSuccessMessage(null), 10000);
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

  const filteredEmployees = useMemo(() => {
    return employees.filter(e => {
      const matchStatus = statusFilter === 'all' || (e.employment_status || e.status) === statusFilter;
      const matchDept = departmentFilter === 'all' || e.department_name === departmentFilter;
      const q = searchQuery.toLowerCase();
      const matchSearch = q === '' || 
        e.first_name.toLowerCase().includes(q) || 
        e.last_name.toLowerCase().includes(q) || 
        e.employee_code.toLowerCase().includes(q) ||
        (e.email && e.email.toLowerCase().includes(q));
      
      return matchStatus && matchDept && matchSearch;
    });
  }, [employees, statusFilter, departmentFilter, searchQuery]);

  const uniqueDepartments = useMemo(() => {
    const depts = new Set(employees.map(e => e.department_name).filter(Boolean));
    return Array.from(depts);
  }, [employees]);

  const columns = [
    {
      key: 'name',
      title: 'Employee',
      render: (e: EmployeeProfile) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%)',
              color: 'var(--color-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: '0.85rem',
              flexShrink: 0,
              boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            }}
          >
            {e.first_name?.[0] || ''}{e.last_name?.[0] || ''}
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 600, color: 'var(--color-text-main)', fontSize: 'var(--font-size-sm)' }}>
              {e.first_name} {e.last_name}
            </div>
            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
              {e.email || e.employee_code}
            </div>
          </div>
        </div>
      ),
    },
    {
      key: 'employee_code',
      title: 'Employee ID',
      render: (e: EmployeeProfile) => (
        <span style={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums', color: 'var(--color-text-sub)' }}>
          {e.employee_code}
        </span>
      ),
    },
    {
      key: 'department',
      title: 'Department',
      render: (e: EmployeeProfile) => (
        <span style={{ display: 'inline-flex', padding: '2px 8px', borderRadius: '4px', backgroundColor: 'var(--color-bg-page)', fontSize: 'var(--font-size-xs)', fontWeight: 500 }}>
          {e.department_name || '—'}
        </span>
      ),
    },
    { key: 'designation', title: 'Designation', render: (e: EmployeeProfile) => e.designation_name || '—' },
    { key: 'joining_date', title: 'Joining Date', render: (e: EmployeeProfile) => e.joining_date || '—' },
    {
      key: 'status',
      title: 'Status',
      render: (e: EmployeeProfile) => (
        <StatusBadge status={(e.employment_status || e.status) as any} />
      ),
    },
    {
      key: 'actions',
      title: 'Actions',
      render: (e: EmployeeProfile) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <button
            style={{ ...styles.actionBtn, padding: '5px', borderRadius: '6px', backgroundColor: 'rgba(112, 38, 227, 0.08)' }}
            onClick={() => navigate(`/admin/employees/${e.id}`)}
            title="View Profile"
          >
            <Eye size={16} color="var(--color-primary)" />
          </button>

          {hasPermission('employee.update') && (
            <button
              style={{ ...styles.actionBtn, padding: '5px', borderRadius: '6px', backgroundColor: 'var(--color-bg-secondary)' }}
              onClick={() => openEditModal(e)}
              title="Edit Employee"
            >
              <Edit2 size={16} color="var(--color-text-sub)" />
            </button>
          )}

          {hasPermission('employee.manage_status') && (
            <button
              style={{ ...styles.actionBtn, padding: '5px', borderRadius: '6px', backgroundColor: 'rgba(217, 119, 6, 0.08)' }}
              onClick={() => openStatusModal(e)}
              title="Change Lifecycle Status"
            >
              <Power size={16} color="#d97706" />
            </button>
          )}

          {(hasPermission('role.assign') || hasPermission('permission.assign')) && (
            <button
              style={{ ...styles.actionBtn, padding: '5px', borderRadius: '6px', backgroundColor: 'rgba(14, 165, 233, 0.08)' }}
              onClick={() => navigate(`/admin/employees/${e.id}/access`)}
              title="RBAC Access"
            >
              <Shield size={16} color="#0284c7" />
            </button>
          )}
        </div>
      ),
    },
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
        {hasPermission('employee.create') && (
          <button className="btn btn-primary" onClick={openCreateModal}>
            <Plus size={18} /> Add Employee
          </button>
        )}
      </div>

      {successMessage && (
        <Card className="mb-4">
          <div style={{...styles.errorBox, backgroundColor: 'rgba(34, 197, 94, 0.1)', color: 'var(--color-status-success)'}}>
            <Shield size={20} />
            <span style={{ whiteSpace: 'pre-wrap' }}>{successMessage}</span>
          </div>
        </Card>
      )}

      <Card>
        <div style={{ display: 'flex', gap: 'var(--spacing-md)', marginBottom: 'var(--spacing-lg)', flexWrap: 'wrap' }}>
          <div style={{ flex: '1', minWidth: '250px', position: 'relative' }}>
            <div style={{ position: 'absolute', top: '10px', left: '12px', color: 'var(--color-text-muted)' }}>
              <Search size={18} />
            </div>
            <input 
              style={{...styles.input, paddingLeft: '38px'}} 
              placeholder="Search by name, code, or email..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <select
            style={{...styles.input, width: '200px'}}
            value={departmentFilter}
            onChange={(e) => setDepartmentFilter(e.target.value)}
          >
            <option value="all">All Departments</option>
            {uniqueDepartments.map(dept => (
              <option key={dept} value={dept}>{dept}</option>
            ))}
          </select>
          <select
            style={{...styles.input, width: '200px'}}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Statuses</option>
            <option value="onboarding">Onboarding</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="exited">Exited</option>
          </select>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <Table data={filteredEmployees} columns={columns} keyExtractor={(e) => e.id} />
        </div>
      </Card>

      {/* Status Modal */}
      {isStatusModalOpen && statusEmployee && (
        <div style={styles.modalOverlay}>
          <div style={{...styles.modalContent, maxWidth: '400px'}}>
            <h2 style={{ marginTop: 0 }}>Change Employment Status</h2>
            <div style={{ marginBottom: '16px', color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>
              Updating lifecycle status for {statusEmployee.first_name} {statusEmployee.last_name}.
            </div>

            {formError && (
              <div style={styles.errorBox}>
                <AlertCircle size={18} /> {formError}
              </div>
            )}

            <form onSubmit={handleStatusChange}>
              <div style={styles.formGroup}>
                <label style={styles.label}>New Status</label>
                <select
                  style={styles.input}
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                  required
                >
                  <option value="onboarding">Onboarding</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="exited">Exited</option>
                </select>
              </div>
              <div style={styles.modalActions}>
                <button type="button" style={styles.cancelBtn} onClick={() => setIsStatusModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }}/> : 'Confirm'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create / Edit Modal */}
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

              <h3 style={styles.sectionTitle}>Basic Information</h3>
              {editingEmployee && (
                <div style={{ marginBottom: '16px', padding: '12px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                    Email, name, and employee code cannot be changed.
                  </div>
                </div>
              )}

              {!editingEmployee && (
                <>
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Employee ID</label>
                    <div style={{ padding: '10px 12px', backgroundColor: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '4px', color: '#6b7280', fontSize: '0.95rem' }}>
                      Employee ID will be generated automatically.
                    </div>
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
                </>
              )}

              <h3 style={styles.sectionTitle}>Contact Information</h3>
              {!editingEmployee && (
                <>
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Work Email</label>
                    <input
                      style={styles.input}
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({...formData, email: e.target.value})}
                      required
                    />
                  </div>
                  {hasPermission('employee.view_sensitive') ? (
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
                  ) : (
                    <div style={{ fontSize: '0.9rem', color: 'var(--color-text-muted)', fontStyle: 'italic', marginBottom: '16px' }}>
                      Sensitive contact fields are hidden due to permissions.
                    </div>
                  )}
                </>
              )}

              {editingEmployee && editingEmployee.personal_email === undefined && (
                <div style={{ fontSize: '0.9rem', color: 'var(--color-text-muted)', fontStyle: 'italic', marginBottom: '16px' }}>
                  Sensitive contact fields are hidden due to permissions.
                </div>
              )}

              {editingEmployee && editingEmployee.phone_number !== undefined && (
                <>
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
                </>
              )}

              <h3 style={styles.sectionTitle}>Employment</h3>

              <div style={{ display: 'flex', gap: 'var(--spacing-md)' }}>
                <div style={{ ...styles.formGroup, flex: 1 }}>
                  <label style={styles.label}>Joining Date</label>
                  <input
                    type="date"
                    style={styles.input}
                    value={formData.joining_date}
                    onChange={(e) => setFormData({...formData, joining_date: e.target.value})}
                  />
                </div>
                <div style={{ ...styles.formGroup, flex: 1 }}>
                  <label style={styles.label}>Exit Date</label>
                  <input
                    type="date"
                    style={styles.input}
                    value={formData.exit_date}
                    onChange={(e) => setFormData({...formData, exit_date: e.target.value})}
                  />
                </div>
              </div>

              <h3 style={styles.sectionTitle}>Organization & Reporting</h3>

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
