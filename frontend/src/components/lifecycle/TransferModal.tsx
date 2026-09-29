import React, { useState, useEffect, useRef } from 'react';
import { Modal } from '../Modal';
import {
  organizationService,
  type Branch,
  type Department,
  type Team,
} from '../../services/organization';
import {
  employeeManagementService,
  type EmployeeTransferPayload,
  ApiError,
} from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import { Loader2, AlertCircle, ArrowRight, Building, MapPin, Users, Calendar, FileText } from 'lucide-react';

interface TransferModalProps {
  employee: EmployeeProfile;
  onClose: () => void;
  onSuccess: (updated: EmployeeProfile) => void;
}

export const TransferModal: React.FC<TransferModalProps> = ({
  employee,
  onClose,
  onSuccess,
}) => {
  const [branches, setBranches] = useState<Branch[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);

  const [selectedBranchId, setSelectedBranchId] = useState<number | ''>(employee.branch || '');
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<number | ''>(employee.department || '');
  const [selectedTeamId, setSelectedTeamId] = useState<number | ''>(employee.team || '');
  const [effectiveDate, setEffectiveDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [reason, setReason] = useState<string>('');

  const [loadingInitial, setLoadingInitial] = useState(true);
  const [loadingDepts, setLoadingDepts] = useState(false);
  const [loadingTeams, setLoadingTeams] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const deptAbortRef = useRef<AbortController | null>(null);
  const teamAbortRef = useRef<AbortController | null>(null);

  // Load initial branches and current department's teams
  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
      setLoadingInitial(true);
      try {
        const branchList = await organizationService.listBranches().catch(() => []);
        if (!isMounted) return;
        setBranches(branchList || []);

        if (employee.branch) {
          const depts = await organizationService.listDepartments(employee.branch).catch(() => []);
          if (!isMounted) return;
          setDepartments(depts || []);
        }

        if (employee.department) {
          const teamList = await organizationService.listTeams(employee.department).catch(() => []);
          if (!isMounted) return;
          setTeams(teamList || []);
        }
      } finally {
        if (isMounted) setLoadingInitial(false);
      }
    };

    loadData();
    return () => {
      isMounted = false;
      deptAbortRef.current?.abort();
      teamAbortRef.current?.abort();
    };
  }, [employee.branch, employee.department]);

  const handleBranchChange = async (branchIdStr: string) => {
    const branchId = branchIdStr ? Number(branchIdStr) : '';
    setSelectedBranchId(branchId);
    setSelectedDepartmentId('');
    setSelectedTeamId('');
    setDepartments([]);
    setTeams([]);
    setFieldErrors(prev => ({ ...prev, branch: '', department: '', team: '' }));

    if (deptAbortRef.current) deptAbortRef.current.abort();
    if (teamAbortRef.current) teamAbortRef.current.abort();

    if (!branchId) return;

    const controller = new AbortController();
    deptAbortRef.current = controller;
    setLoadingDepts(true);

    try {
      const depts = await organizationService.listDepartments(branchId, { signal: controller.signal });
      if (deptAbortRef.current === controller) {
        setDepartments(depts || []);
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setDepartments([]);
      }
    } finally {
      if (deptAbortRef.current === controller) {
        setLoadingDepts(false);
      }
    }
  };

  const handleDepartmentChange = async (deptIdStr: string) => {
    const deptId = deptIdStr ? Number(deptIdStr) : '';
    setSelectedDepartmentId(deptId);
    setSelectedTeamId('');
    setTeams([]);
    setFieldErrors(prev => ({ ...prev, department: '', team: '' }));

    if (teamAbortRef.current) teamAbortRef.current.abort();

    if (!deptId) return;

    const controller = new AbortController();
    teamAbortRef.current = controller;
    setLoadingTeams(true);

    try {
      const teamList = await organizationService.listTeams(deptId, { signal: controller.signal });
      if (teamAbortRef.current === controller) {
        setTeams(teamList || []);
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setTeams([]);
      }
    } finally {
      if (teamAbortRef.current === controller) {
        setLoadingTeams(false);
      }
    }
  };

  const handleTeamChange = (teamIdStr: string) => {
    const teamId = teamIdStr ? Number(teamIdStr) : '';
    setSelectedTeamId(teamId);
    setFieldErrors(prev => ({ ...prev, team: '' }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setFieldErrors({});

    if (!effectiveDate) {
      setFieldErrors(prev => ({ ...prev, effective_date: 'Effective date is required.' }));
      return;
    }

    if (!selectedBranchId && !selectedDepartmentId && !selectedTeamId) {
      setErrorMessage('At least one of branch, department, or team must be specified for transfer.');
      return;
    }

    setSubmitting(true);

    const payload: EmployeeTransferPayload = {
      effective_date: effectiveDate,
    };

    if (selectedBranchId) payload.branch = Number(selectedBranchId);
    if (selectedDepartmentId) payload.department = Number(selectedDepartmentId);
    if (selectedTeamId) payload.team = Number(selectedTeamId);
    if (reason.trim()) payload.reason = reason.trim();

    try {
      const updated = await employeeManagementService.transferEmployee(employee.id, payload);
      onSuccess(updated);
    } catch (err: any) {
      if (err instanceof ApiError || err.status || err.response?.status) {
        const status = err.status || err.response?.status;
        const errorData = err.errorData || {};

        if (status === 403) {
          setErrorMessage(
            errorData.detail || 'You do not have permission to transfer employees into this organizational unit.'
          );
        } else if (status === 400) {
          if (typeof errorData === 'object' && errorData !== null) {
            const nextErrors: Record<string, string> = {};
            const nonFieldMsgs: string[] = [];

            for (const [k, v] of Object.entries(errorData)) {
              const msg = Array.isArray(v) ? v.join(' ') : String(v);
              if (k === 'detail' || k === 'non_field_errors') {
                nonFieldMsgs.push(msg);
              } else {
                nextErrors[k] = msg;
              }
            }

            setFieldErrors(nextErrors);
            if (nonFieldMsgs.length > 0) {
              setErrorMessage(nonFieldMsgs.join(' | '));
            } else if (Object.keys(nextErrors).length > 0) {
              setErrorMessage('Please resolve the validation errors below.');
            } else {
              setErrorMessage('Validation error occurred while transferring employee.');
            }
          } else {
            setErrorMessage(String(errorData) || 'Invalid transfer request.');
          }
        } else if (status === 404) {
          setErrorMessage('Employee or target organizational unit not found.');
        } else if (status === 405) {
          setErrorMessage('Method not allowed.');
        } else {
          setErrorMessage(err.message || 'Failed to complete transfer.');
        }
      } else {
        setErrorMessage(err?.message || 'Network error occurred. Please check your connection.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="Transfer Employee"
      onClose={onClose}
      size="md"
      footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', width: '100%' }}>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={onClose}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={submitting || loadingInitial}
            data-testid="submit-transfer-btn"
          >
            {submitting ? (
              <>
                <Loader2 size={16} className="animate-spin" /> Transferring...
              </>
            ) : (
              'Confirm Transfer'
            )}
          </button>
        </div>
      }
    >
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Current Placement Summary */}
        <div style={{
          padding: '12px 16px',
          backgroundColor: 'var(--color-bg-secondary, #f1f5f9)',
          borderRadius: 'var(--radius-md, 8px)',
          border: '1px solid var(--color-border)',
        }}>
          <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--color-text-muted)', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
            Current Assignment
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', fontSize: '0.9rem', color: 'var(--color-text-main)' }}>
            <span style={{ fontWeight: 600 }}>{employee.branch_name || 'No Branch'}</span>
            <ArrowRight size={14} color="var(--color-text-muted)" />
            <span>{employee.department_name || 'No Department'}</span>
            {employee.team_name && (
              <>
                <ArrowRight size={14} color="var(--color-text-muted)" />
                <span style={{ color: 'var(--color-primary)' }}>{employee.team_name}</span>
              </>
            )}
          </div>
        </div>

        {errorMessage && (
          <div
            style={{
              padding: '12px 14px',
              backgroundColor: 'var(--color-status-danger-bg, #fef2f2)',
              border: '1px solid var(--color-status-danger-border, #fecaca)',
              borderRadius: 'var(--radius-md, 8px)',
              color: 'var(--color-status-danger, #dc2626)',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '8px',
            }}
            data-testid="transfer-error-box"
          >
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Branch Selector */}
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <MapPin size={14} color="var(--color-text-muted)" /> Destination Branch *
          </label>
          <select
            className="input-field"
            value={selectedBranchId}
            onChange={(e) => handleBranchChange(e.target.value)}
            disabled={submitting || loadingInitial}
            data-testid="transfer-branch-select"
          >
            <option value="">-- Select Destination Branch --</option>
            {branches.map(b => (
              <option key={b.id} value={b.id}>
                {b.name} {!b.is_active ? '(Inactive)' : ''}
              </option>
            ))}
          </select>
          {fieldErrors.branch && (
            <span style={{ color: 'var(--color-status-danger, #dc2626)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
              {fieldErrors.branch}
            </span>
          )}
        </div>

        {/* Department Selector */}
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <Building size={14} color="var(--color-text-muted)" /> Destination Department
            {loadingDepts && <Loader2 size={12} className="animate-spin" />}
          </label>
          <select
            className="input-field"
            value={selectedDepartmentId}
            onChange={(e) => handleDepartmentChange(e.target.value)}
            disabled={submitting || loadingInitial || loadingDepts || !selectedBranchId}
            data-testid="transfer-department-select"
          >
            <option value="">-- Optional / Select Department --</option>
            {departments.map(d => (
              <option key={d.id} value={d.id}>
                {d.name} {!d.is_active ? '(Inactive)' : ''}
              </option>
            ))}
          </select>
          {fieldErrors.department && (
            <span style={{ color: 'var(--color-status-danger, #dc2626)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
              {fieldErrors.department}
            </span>
          )}
        </div>

        {/* Team Selector */}
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <Users size={14} color="var(--color-text-muted)" /> Destination Team
            {loadingTeams && <Loader2 size={12} className="animate-spin" />}
          </label>
          <select
            className="input-field"
            value={selectedTeamId}
            onChange={(e) => handleTeamChange(e.target.value)}
            disabled={submitting || loadingInitial || loadingTeams || !selectedDepartmentId}
            data-testid="transfer-team-select"
          >
            <option value="">-- Optional / Select Team --</option>
            {teams.map(t => (
              <option key={t.id} value={t.id}>
                {t.name} {!t.is_active ? '(Inactive)' : ''}
              </option>
            ))}
          </select>
          {fieldErrors.team && (
            <span style={{ color: 'var(--color-status-danger, #dc2626)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
              {fieldErrors.team}
            </span>
          )}
        </div>

        {/* Effective Date */}
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <Calendar size={14} color="var(--color-text-muted)" /> Effective Date *
          </label>
          <input
            type="date"
            className="input-field"
            value={effectiveDate}
            onChange={(e) => {
              setEffectiveDate(e.target.value);
              setFieldErrors(prev => ({ ...prev, effective_date: '' }));
            }}
            disabled={submitting}
            required
            data-testid="transfer-effective-date"
          />
          {fieldErrors.effective_date && (
            <span style={{ color: 'var(--color-status-danger, #dc2626)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
              {fieldErrors.effective_date}
            </span>
          )}
        </div>

        {/* Reason */}
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <FileText size={14} color="var(--color-text-muted)" /> Reason (Optional)
          </label>
          <textarea
            className="input-field"
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={submitting}
            placeholder="e.g. Relocation, business reorganization, team restructuring"
            data-testid="transfer-reason"
            style={{ resize: 'vertical' }}
          />
        </div>
      </form>
    </Modal>
  );
};
