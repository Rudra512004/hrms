import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePagination } from '../../hooks/usePagination';
import { employeeManagementService, type ListEmployeesParams } from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import {
  organizationService,
  type Branch,
  type Department,
  type Team,
  type Designation,
} from '../../services/organization';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { Plus, Edit2, Shield, Power, AlertCircle, Loader2, Search, Eye } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useBranchContext } from '../../contexts/BranchContext';

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
  fieldError: {
    display: 'block',
    color: 'var(--color-status-danger, #ef4444)',
    fontSize: '0.8rem',
    marginTop: '4px',
    fontWeight: 500,
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
  const { branchId } = useBranchContext();

  const [employees, setEmployees] = useState<EmployeeProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState<EmployeeProfile | null>(null);

  const [isStatusModalOpen, setIsStatusModalOpen] = useState(false);
  const [statusEmployee, setStatusEmployee] = useState<EmployeeProfile | null>(null);
  const [newStatus, setNewStatus] = useState('');

  // Selector datasets
  const [branches, setBranches] = useState<Branch[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [designations, setDesignations] = useState<Designation[]>([]);
  const [managers, setManagers] = useState<EmployeeProfile[]>([]);

  // Loading states for cascading selectors
  const [branchesLoading, setBranchesLoading] = useState(false);
  const [departmentsLoading, setDepartmentsLoading] = useState(false);
  const [teamsLoading, setTeamsLoading] = useState(false);
  const [designationsLoading, setDesignationsLoading] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('all');

  // Pagination state with URL synchronization
  const {
    page,
    pageSize,
    totalCount,
    setTotalCount,
    handlePageChange,
    resetPage,
  } = usePagination({ defaultPageSize: 20 });

  // Reset page to 1 if branch changes
  const prevBranchIdRef = useRef(branchId);
  useEffect(() => {
    if (prevBranchIdRef.current !== branchId) {
      prevBranchIdRef.current = branchId;
      resetPage();
    }
  }, [branchId, resetPage]);

  // Form State
  const [formData, setFormData] = useState({
    email: '',
    personal_email: '',
    first_name: '',
    last_name: '',
    employee_code: '',
    phone_number: '',
    address: '',
    branch: 0,
    department: 0,
    team: 0,
    designation: 0,
    reporting_manager: 0,
    joining_date: '',
    exit_date: '',
  });

  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Stale request protection refs
  const employeeAbortRef = useRef<AbortController | null>(null);
  const deptAbortRef = useRef<AbortController | null>(null);
  const teamAbortRef = useRef<AbortController | null>(null);

  const loadEmployees = useCallback(async () => {
    if (employeeAbortRef.current) {
      employeeAbortRef.current.abort();
    }
    const controller = new AbortController();
    employeeAbortRef.current = controller;

    setLoading(true);
    try {
      const params: ListEmployeesParams = {
        paginate: true,
        page,
        page_size: pageSize,
      };
      if (branchId !== null && branchId !== undefined) {
        params.branch_id = branchId;
      }
      if (searchQuery.trim()) {
        params.search = searchQuery.trim();
      }
      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }

      const data = await employeeManagementService.listEmployees(params, { signal: controller.signal });
      if (employeeAbortRef.current === controller) {
        if (Array.isArray(data)) {
          setEmployees(data);
          setTotalCount(data.length);
        } else if (data && Array.isArray(data.results)) {
          setEmployees(data.results);
          setTotalCount(data.count);
        } else {
          setEmployees([]);
          setTotalCount(0);
        }
        setError(null);
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        return;
      }
      if (err.status === 403 || err.message?.includes('403')) {
        setError("403 Forbidden: Access Denied.");
      } else {
        setError("Failed to load employees. Backend might be unavailable.");
      }
    } finally {
      if (employeeAbortRef.current === controller) {
        setLoading(false);
      }
    }
  }, [branchId, searchQuery, statusFilter, page, pageSize, setTotalCount]);

  useEffect(() => {
    loadEmployees();
    return () => {
      employeeAbortRef.current?.abort();
    };
  }, [loadEmployees]);

  const loadInitialData = async () => {
    setBranchesLoading(true);
    setDesignationsLoading(true);
    try {
      const [branchList, desigList] = await Promise.all([
        organizationService.listBranches().catch(() => []),
        organizationService.listDesignations().catch(() => []),
      ]);
      setBranches(branchList || []);
      setDesignations(desigList || []);

      // Managers list: active employees
      const activeEmps = employees.filter(
        e => e.employment_status === 'active' || e.status === 'active'
      );
      setManagers(activeEmps);
    } catch (e) {
      console.error("Failed to load initial form data", e);
    } finally {
      setBranchesLoading(false);
      setDesignationsLoading(false);
    }
  };

  const handleBranchChange = async (selectedBranchId: number) => {
    setFormData(prev => ({
      ...prev,
      branch: selectedBranchId,
      department: 0,
      team: 0,
    }));
    setFieldErrors(prev => ({ ...prev, branch: '', department: '', team: '' }));
    setTeams([]);

    if (deptAbortRef.current) {
      deptAbortRef.current.abort();
    }
    if (teamAbortRef.current) {
      teamAbortRef.current.abort();
    }

    if (!selectedBranchId) {
      setDepartments([]);
      setDepartmentsLoading(false);
      return;
    }

    const controller = new AbortController();
    deptAbortRef.current = controller;
    setDepartmentsLoading(true);

    try {
      const depts = await organizationService.listDepartments(selectedBranchId, { signal: controller.signal });
      if (deptAbortRef.current === controller) {
        setDepartments(depts || []);
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error("Failed to load departments", err);
        setDepartments([]);
      }
    } finally {
      if (deptAbortRef.current === controller) {
        setDepartmentsLoading(false);
      }
    }
  };

  const handleDepartmentChange = async (selectedDeptId: number) => {
    setFormData(prev => ({
      ...prev,
      department: selectedDeptId,
      team: 0,
    }));
    setFieldErrors(prev => ({ ...prev, department: '', team: '' }));

    if (teamAbortRef.current) {
      teamAbortRef.current.abort();
    }

    if (!selectedDeptId) {
      setTeams([]);
      setTeamsLoading(false);
      return;
    }

    const controller = new AbortController();
    teamAbortRef.current = controller;
    setTeamsLoading(true);

    try {
      const teamList = await organizationService.listTeams(selectedDeptId, { signal: controller.signal });
      if (teamAbortRef.current === controller) {
        setTeams(teamList || []);
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error("Failed to load teams", err);
        setTeams([]);
      }
    } finally {
      if (teamAbortRef.current === controller) {
        setTeamsLoading(false);
      }
    }
  };

  const handleTeamChange = (selectedTeamId: number) => {
    setFormData(prev => ({ ...prev, team: selectedTeamId }));
    setFieldErrors(prev => ({ ...prev, team: '' }));
    if (selectedTeamId) {
      const matched = teams.find(t => t.id === selectedTeamId);
      if (matched && matched.department) {
        setFormData(prev => ({ ...prev, department: matched.department }));
      }
    }
  };

  const openCreateModal = () => {
    setEditingEmployee(null);
    const initialBranch = branchId || 0;
    setFormData({
      email: '',
      personal_email: '',
      first_name: '',
      last_name: '',
      employee_code: '',
      phone_number: '',
      address: '',
      branch: initialBranch,
      department: 0,
      team: 0,
      designation: 0,
      reporting_manager: 0,
      joining_date: '',
      exit_date: '',
    });
    setFormError(null);
    setFieldErrors({});
    setIsModalOpen(true);
    loadInitialData();

    if (initialBranch) {
      handleBranchChange(initialBranch);
    } else {
      setDepartments([]);
      setTeams([]);
    }
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
      branch: emp.branch || 0,
      department: emp.department || 0,
      team: emp.team || 0,
      designation: emp.designation || 0,
      reporting_manager: emp.reporting_manager || 0,
      joining_date: emp.joining_date || '',
      exit_date: emp.exit_date || '',
    });
    setFormError(null);
    setFieldErrors({});
    setIsModalOpen(true);
    loadInitialData();

    if (emp.department) {
      // Load teams for current department to allow same-department team reassignment
      setTeamsLoading(true);
      organizationService
        .listTeams(emp.department)
        .then(teamList => setTeams(teamList || []))
        .catch(() => setTeams([]))
        .finally(() => setTeamsLoading(false));
    } else {
      setTeams([]);
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
    setFieldErrors({});

    try {
      if (editingEmployee) {
        // Ordinary update via PATCH:
        // Do NOT allow changing branch or department through ordinary edit.
        const payload: Record<string, any> = {};
        if (editingEmployee.phone_number !== undefined) payload.phone_number = formData.phone_number;
        if (editingEmployee.address !== undefined) payload.address = formData.address;
        if (formData.designation) payload.designation = formData.designation > 0 ? formData.designation : null;
        if (formData.reporting_manager) payload.reporting_manager = formData.reporting_manager > 0 ? formData.reporting_manager : null;
        if (formData.joining_date) payload.joining_date = formData.joining_date;
        if (formData.exit_date) payload.exit_date = formData.exit_date;

        // Same-department team reassignment
        if (formData.team !== undefined) {
          payload.team = formData.team > 0 ? formData.team : null;
        }

        await employeeManagementService.updateEmployee(editingEmployee.id, payload);
        setSuccessMessage("Employee updated successfully.");
      } else {
        // Provisioning Employee via POST
        const payload: any = {
          email: formData.email.trim(),
          first_name: formData.first_name.trim(),
          last_name: formData.last_name.trim(),
        };

        if (formData.personal_email?.trim()) payload.personal_email = formData.personal_email.trim();
        if (formData.employee_code?.trim()) payload.employee_code = formData.employee_code.trim();
        if (formData.branch) payload.branch = formData.branch;
        if (formData.department) payload.department = formData.department;
        if (formData.team) payload.team = formData.team;
        if (formData.designation) payload.designation = formData.designation;
        if (formData.reporting_manager) payload.reporting_manager = formData.reporting_manager;
        if (formData.joining_date) payload.joining_date = formData.joining_date;
        if (formData.exit_date) payload.exit_date = formData.exit_date;

        const result = await employeeManagementService.createEmployee(payload);

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
      const status = err.status || err.response?.status;
      const errorData = err.errorData || {};

      if (status === 403) {
        const msg = errorData.detail || errorData.message || "Permission denied: Destination unit is outside your authorized scope.";
        setFormError(msg);
      } else if (status === 400 && errorData && typeof errorData === 'object') {
        const newFieldErrors: Record<string, string> = {};
        const nonField: string[] = [];

        for (const [key, val] of Object.entries(errorData)) {
          const msg = Array.isArray(val) ? val.join(' ') : String(val);
          if (key === 'non_field_errors' || key === 'detail') {
            nonField.push(msg);
          } else {
            newFieldErrors[key] = msg;
          }
        }

        setFieldErrors(newFieldErrors);
        if (nonField.length > 0) {
          setFormError(nonField.join(' | '));
        } else if (Object.keys(newFieldErrors).length > 0) {
          setFormError("Please correct the errors indicated below.");
        } else {
          setFormError("Validation error occurred.");
        }
      } else if (status === 404) {
        setFormError("Resource not found.");
      } else {
        setFormError(err.message || "An unexpected error occurred while saving.");
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
            data-testid={`view-profile-${e.id}`}
          >
            <Eye size={16} color="var(--color-primary)" />
          </button>

          {hasPermission('employee.update') && (
            <button
              style={{ ...styles.actionBtn, padding: '5px', borderRadius: '6px', backgroundColor: 'var(--color-bg-secondary)' }}
              onClick={() => openEditModal(e)}
              title="Edit Employee"
              data-testid={`edit-employee-${e.id}`}
            >
              <Edit2 size={16} color="var(--color-text-sub)" />
            </button>
          )}

          {hasPermission('employee.manage_status') && (
            <button
              style={{ ...styles.actionBtn, padding: '5px', borderRadius: '6px', backgroundColor: 'rgba(217, 119, 6, 0.08)' }}
              onClick={() => openStatusModal(e)}
              title="Change Lifecycle Status"
              data-testid={`status-employee-${e.id}`}
            >
              <Power size={16} color="#d97706" />
            </button>
          )}

          {(hasPermission('role.assign') || hasPermission('permission.assign')) && (
            <button
              style={{ ...styles.actionBtn, padding: '5px', borderRadius: '6px', backgroundColor: 'rgba(14, 165, 233, 0.08)' }}
              onClick={() => navigate(`/admin/employees/${e.id}/access`)}
              title="RBAC Access"
              data-testid={`rbac-employee-${e.id}`}
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
          <button className="btn btn-primary" onClick={openCreateModal} data-testid="add-employee-btn">
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
              onChange={(e) => {
                setSearchQuery(e.target.value);
                resetPage();
              }}
              data-testid="search-input"
            />
          </div>
          <select
            style={{...styles.input, width: '200px'}}
            value={departmentFilter}
            onChange={(e) => {
              setDepartmentFilter(e.target.value);
              resetPage();
            }}
            data-testid="department-filter"
          >
            <option value="all">All Departments</option>
            {uniqueDepartments.map(dept => (
              <option key={dept} value={dept}>{dept}</option>
            ))}
          </select>
          <select
            style={{...styles.input, width: '200px'}}
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              resetPage();
            }}
            data-testid="status-filter"
          >
            <option value="all">All Statuses</option>
            <option value="onboarding">Onboarding</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="exited">Exited</option>
          </select>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <Table
            data={filteredEmployees}
            columns={columns}
            keyExtractor={(e) => e.id}
            pagination
            count={totalCount}
            page={page}
            pageSize={pageSize}
            onPageChange={handlePageChange}
            loading={loading}
          />
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
              <div style={styles.errorBox} data-testid="form-error-alert">
                <AlertCircle size={18} /> {formError}
              </div>
            )}

            <form onSubmit={handleSave}>
              <h3 style={styles.sectionTitle}>Basic Information</h3>
              {editingEmployee && (
                <div style={{ marginBottom: '16px', padding: '12px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                    Email, name, and employee code cannot be changed through ordinary profile edits.
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
                        onChange={(e) => {
                          setFormData({ ...formData, first_name: e.target.value });
                          setFieldErrors(prev => ({ ...prev, first_name: '' }));
                        }}
                        required
                        data-testid="input-first-name"
                      />
                      {fieldErrors.first_name && (
                        <span style={styles.fieldError} data-testid="error-first-name">{fieldErrors.first_name}</span>
                      )}
                    </div>
                    <div style={{ ...styles.formGroup, flex: 1 }}>
                      <label style={styles.label}>Last Name</label>
                      <input
                        style={styles.input}
                        value={formData.last_name}
                        onChange={(e) => {
                          setFormData({ ...formData, last_name: e.target.value });
                          setFieldErrors(prev => ({ ...prev, last_name: '' }));
                        }}
                        required
                        data-testid="input-last-name"
                      />
                      {fieldErrors.last_name && (
                        <span style={styles.fieldError} data-testid="error-last-name">{fieldErrors.last_name}</span>
                      )}
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
                      onChange={(e) => {
                        setFormData({ ...formData, email: e.target.value });
                        setFieldErrors(prev => ({ ...prev, email: '' }));
                      }}
                      required
                      data-testid="input-email"
                    />
                    {fieldErrors.email && (
                      <span style={styles.fieldError} data-testid="error-email">{fieldErrors.email}</span>
                    )}
                  </div>
                  {hasPermission('employee.view_sensitive') ? (
                    <div style={styles.formGroup}>
                      <label style={styles.label}>Personal Email</label>
                      <input
                        style={styles.input}
                        type="email"
                        value={formData.personal_email}
                        onChange={(e) => {
                          setFormData({ ...formData, personal_email: e.target.value });
                          setFieldErrors(prev => ({ ...prev, personal_email: '' }));
                        }}
                        data-testid="input-personal-email"
                      />
                      {fieldErrors.personal_email && (
                        <span style={styles.fieldError} data-testid="error-personal-email">{fieldErrors.personal_email}</span>
                      )}
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
                      onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                      data-testid="input-phone-number"
                    />
                  </div>
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Address</label>
                    <input
                      style={styles.input}
                      value={formData.address}
                      onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                      data-testid="input-address"
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
                    onChange={(e) => setFormData({ ...formData, joining_date: e.target.value })}
                    data-testid="input-joining-date"
                  />
                  {fieldErrors.joining_date && (
                    <span style={styles.fieldError} data-testid="error-joining-date">{fieldErrors.joining_date}</span>
                  )}
                </div>
                <div style={{ ...styles.formGroup, flex: 1 }}>
                  <label style={styles.label}>Exit Date</label>
                  <input
                    type="date"
                    style={styles.input}
                    value={formData.exit_date}
                    onChange={(e) => setFormData({ ...formData, exit_date: e.target.value })}
                    data-testid="input-exit-date"
                  />
                  {fieldErrors.exit_date && (
                    <span style={styles.fieldError} data-testid="error-exit-date">{fieldErrors.exit_date}</span>
                  )}
                </div>
              </div>

              <h3 style={styles.sectionTitle}>Organizational Placement</h3>

              {editingEmployee ? (
                <>
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Branch</label>
                    <input
                      style={{ ...styles.input, backgroundColor: 'var(--color-bg-page, #f3f4f6)', cursor: 'not-allowed' }}
                      value={editingEmployee.branch_name || 'No Branch'}
                      disabled
                      readOnly
                      data-testid="disabled-edit-branch"
                    />
                    <small style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem', display: 'block', marginTop: '4px' }}>
                      Branch transfer must be performed through the dedicated transfer workflow.
                    </small>
                  </div>

                  <div style={styles.formGroup}>
                    <label style={styles.label}>Department</label>
                    <input
                      style={{ ...styles.input, backgroundColor: 'var(--color-bg-page, #f3f4f6)', cursor: 'not-allowed' }}
                      value={editingEmployee.department_name || 'No Department'}
                      disabled
                      readOnly
                      data-testid="disabled-edit-department"
                    />
                    <small style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem', display: 'block', marginTop: '4px' }}>
                      Department transfer must be performed through the dedicated transfer workflow.
                    </small>
                  </div>

                  <div style={styles.formGroup}>
                    <label style={styles.label}>Team (Same-Department)</label>
                    <select
                      style={styles.input}
                      value={formData.team}
                      onChange={(e) => {
                        const val = parseInt(e.target.value, 10);
                        setFormData(prev => ({ ...prev, team: val }));
                        setFieldErrors(prev => ({ ...prev, team: '' }));
                      }}
                      disabled={!editingEmployee.department || teamsLoading}
                      data-testid="select-edit-team"
                    >
                      <option value={0}>{teamsLoading ? 'Loading teams...' : 'None'}</option>
                      {teams.map(t => (
                        <option key={t.id} value={t.id}>{t.name}</option>
                      ))}
                    </select>
                    {fieldErrors.team && (
                      <span style={styles.fieldError} data-testid="error-team">{fieldErrors.team}</span>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Branch</label>
                    <select
                      style={styles.input}
                      value={formData.branch}
                      onChange={(e) => handleBranchChange(parseInt(e.target.value, 10))}
                      disabled={branchesLoading}
                      data-testid="select-branch"
                    >
                      <option value={0}>{branchesLoading ? 'Loading branches...' : 'Select Branch'}</option>
                      {branches.map(b => (
                        <option key={b.id} value={b.id}>{b.name}</option>
                      ))}
                    </select>
                    {fieldErrors.branch && (
                      <span style={styles.fieldError} data-testid="error-branch">{fieldErrors.branch}</span>
                    )}
                  </div>

                  <div style={styles.formGroup}>
                    <label style={styles.label}>Department</label>
                    <select
                      style={styles.input}
                      value={formData.department}
                      onChange={(e) => handleDepartmentChange(parseInt(e.target.value, 10))}
                      disabled={!formData.branch || departmentsLoading}
                      data-testid="select-department"
                    >
                      <option value={0}>
                        {departmentsLoading
                          ? 'Loading departments...'
                          : !formData.branch
                          ? 'Select a branch first'
                          : departments.length === 0
                          ? 'No departments found'
                          : 'Select Department'}
                      </option>
                      {departments.map(d => (
                        <option key={d.id} value={d.id}>{d.name}</option>
                      ))}
                    </select>
                    {fieldErrors.department && (
                      <span style={styles.fieldError} data-testid="error-department">{fieldErrors.department}</span>
                    )}
                  </div>

                  <div style={styles.formGroup}>
                    <label style={styles.label}>Team</label>
                    <select
                      style={styles.input}
                      value={formData.team}
                      onChange={(e) => handleTeamChange(parseInt(e.target.value, 10))}
                      disabled={!formData.department || teamsLoading}
                      data-testid="select-team"
                    >
                      <option value={0}>
                        {teamsLoading
                          ? 'Loading teams...'
                          : !formData.department
                          ? 'Select a department first'
                          : teams.length === 0
                          ? 'No teams found'
                          : 'Select Team (Optional)'}
                      </option>
                      {teams.map(t => (
                        <option key={t.id} value={t.id}>{t.name}</option>
                      ))}
                    </select>
                    {fieldErrors.team && (
                      <span style={styles.fieldError} data-testid="error-team">{fieldErrors.team}</span>
                    )}
                  </div>
                </>
              )}

              <div style={styles.formGroup}>
                <label style={styles.label}>Designation</label>
                <select
                  style={styles.input}
                  value={formData.designation}
                  onChange={(e) => {
                    setFormData(prev => ({ ...prev, designation: parseInt(e.target.value, 10) }));
                    setFieldErrors(prev => ({ ...prev, designation: '' }));
                  }}
                  disabled={designationsLoading}
                  data-testid="select-designation"
                >
                  <option value={0}>{designationsLoading ? 'Loading designations...' : 'None'}</option>
                  {designations.map(desig => (
                    <option key={desig.id} value={desig.id}>{desig.name}</option>
                  ))}
                </select>
                {fieldErrors.designation && (
                  <span style={styles.fieldError} data-testid="error-designation">{fieldErrors.designation}</span>
                )}
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>Reporting Manager</label>
                <select
                  style={styles.input}
                  value={formData.reporting_manager}
                  onChange={(e) => {
                    setFormData(prev => ({ ...prev, reporting_manager: parseInt(e.target.value, 10) }));
                    setFieldErrors(prev => ({ ...prev, reporting_manager: '' }));
                  }}
                  data-testid="select-reporting-manager"
                >
                  <option value={0}>None</option>
                  {managers
                    .filter(m => m.id !== editingEmployee?.id)
                    .map(m => (
                      <option key={m.id} value={m.id}>
                        {m.first_name} {m.last_name} ({m.employee_code})
                      </option>
                    ))}
                </select>
                {fieldErrors.reporting_manager && (
                  <span style={styles.fieldError} data-testid="error-reporting-manager">{fieldErrors.reporting_manager}</span>
                )}
              </div>

              <div style={styles.modalActions}>
                <button type="button" style={styles.cancelBtn} onClick={() => setIsModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={saving} data-testid="save-employee-btn">
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
