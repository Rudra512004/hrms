import React, { useState, useEffect } from 'react';
import { Modal } from '../Modal';
import { organizationService, type Team } from '../../services/organization';
import {
  employeeManagementService,
  type UpdateEmployeePayload,
  ApiError,
} from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import { Loader2, AlertCircle, Phone, MapPin, User, Calendar, Users, Info } from 'lucide-react';

interface EditEmployeeModalProps {
  employee: EmployeeProfile;
  onClose: () => void;
  onSuccess: (updated: EmployeeProfile) => void;
}

export const EditEmployeeModal: React.FC<EditEmployeeModalProps> = ({
  employee,
  onClose,
  onSuccess,
}) => {
  const [teams, setTeams] = useState<Team[]>([]);
  const [managers, setManagers] = useState<EmployeeProfile[]>([]);

  const [phoneNumber, setPhoneNumber] = useState(employee.phone_number || '');
  const [address, setAddress] = useState(employee.address || '');
  const [emergencyContactName, setEmergencyContactName] = useState(employee.emergency_contact_name || '');
  const [emergencyContactPhone, setEmergencyContactPhone] = useState(employee.emergency_contact_phone || '');
  const [joiningDate, setJoiningDate] = useState(employee.joining_date || '');
  const [reportingManagerId, setReportingManagerId] = useState<number | ''>(employee.reporting_manager || '');
  const [selectedTeamId, setSelectedTeamId] = useState<number | ''>(employee.team || '');

  const [loadingInitial, setLoadingInitial] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    let isMounted = true;
    const loadFormData = async () => {
      setLoadingInitial(true);
      try {
        const [teamList, empList] = await Promise.all([
          employee.department
            ? organizationService.listTeams(employee.department).catch(() => [])
            : Promise.resolve([]),
          Promise.resolve(employeeManagementService.listEmployees?.() || []).catch(() => []),
        ]);

        if (!isMounted) return;
        setTeams(teamList || []);
        // Filter active employees except current employee for reporting manager list
        const eligibleManagers = (empList || []).filter(
          e => e.id !== employee.id && (e.employment_status === 'active' || e.status === 'active')
        );
        setManagers(eligibleManagers);
      } finally {
        if (isMounted) setLoadingInitial(false);
      }
    };

    loadFormData();
    return () => {
      isMounted = false;
    };
  }, [employee.id, employee.department]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setFieldErrors({});
    setSubmitting(true);

    const payload: UpdateEmployeePayload = {
      phone_number: phoneNumber,
      address,
      emergency_contact_name: emergencyContactName,
      emergency_contact_phone: emergencyContactPhone,
      joining_date: joiningDate || null,
      reporting_manager: reportingManagerId ? Number(reportingManagerId) : null,
      team: selectedTeamId ? Number(selectedTeamId) : null,
    };

    try {
      const updated = await employeeManagementService.updateEmployee(employee.id, payload);
      onSuccess(updated);
    } catch (err: any) {
      if (err instanceof ApiError || err.status || err.response?.status) {
        const status = err.status || err.response?.status;
        const errorData = err.errorData || {};

        if (status === 403) {
          setErrorMessage(errorData.detail || 'Permission denied: You do not have permission to edit this employee.');
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
              setErrorMessage('Validation error occurred.');
            }
          } else {
            setErrorMessage(String(errorData) || 'Invalid data submitted.');
          }
        } else if (status === 404) {
          setErrorMessage('Employee not found.');
        } else {
          setErrorMessage(err.message || 'Failed to update employee details.');
        }
      } else {
        setErrorMessage(err?.message || 'Network error occurred. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="Edit Employee Details"
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
            data-testid="submit-edit-btn"
          >
            {submitting ? (
              <>
                <Loader2 size={16} className="animate-spin" /> Saving...
              </>
            ) : (
              'Save Changes'
            )}
          </button>
        </div>
      }
    >
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Notice about Transfer */}
        <div style={{
          padding: '10px 14px',
          backgroundColor: 'var(--color-bg-secondary, #f1f5f9)',
          borderRadius: 'var(--radius-md, 8px)',
          border: '1px solid var(--color-border)',
          fontSize: '0.8rem',
          color: 'var(--color-text-muted)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          <Info size={16} color="var(--color-secondary)" style={{ flexShrink: 0 }} />
          <span>
            Branch (<strong>{employee.branch_name || '—'}</strong>) and Department (<strong>{employee.department_name || '—'}</strong>) transfers require the dedicated <strong>Transfer</strong> action.
          </span>
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
            data-testid="edit-error-box"
          >
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Contact Info */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
              <Phone size={14} color="var(--color-text-muted)" /> Phone Number
            </label>
            <input
              type="text"
              className="input-field"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              disabled={submitting}
              data-testid="edit-phone-input"
            />
            {fieldErrors.phone_number && (
              <span style={{ color: 'var(--color-status-danger, #dc2626)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
                {fieldErrors.phone_number}
              </span>
            )}
          </div>

          <div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
              <Calendar size={14} color="var(--color-text-muted)" /> Joining Date
            </label>
            <input
              type="date"
              className="input-field"
              value={joiningDate}
              onChange={(e) => setJoiningDate(e.target.value)}
              disabled={submitting}
              data-testid="edit-joining-date-input"
            />
            {fieldErrors.joining_date && (
              <span style={{ color: 'var(--color-status-danger, #dc2626)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
                {fieldErrors.joining_date}
              </span>
            )}
          </div>
        </div>

        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <MapPin size={14} color="var(--color-text-muted)" /> Address
          </label>
          <textarea
            className="input-field"
            rows={2}
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            disabled={submitting}
            data-testid="edit-address-input"
            style={{ resize: 'vertical' }}
          />
        </div>

        {/* Emergency Contact */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
              Emergency Contact Name
            </label>
            <input
              type="text"
              className="input-field"
              value={emergencyContactName}
              onChange={(e) => setEmergencyContactName(e.target.value)}
              disabled={submitting}
              data-testid="edit-emergency-name-input"
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
              Emergency Contact Phone
            </label>
            <input
              type="text"
              className="input-field"
              value={emergencyContactPhone}
              onChange={(e) => setEmergencyContactPhone(e.target.value)}
              disabled={submitting}
              data-testid="edit-emergency-phone-input"
            />
          </div>
        </div>

        {/* Team Assignment (same department) */}
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <Users size={14} color="var(--color-text-muted)" /> Team (Same Department)
          </label>
          <select
            className="input-field"
            value={selectedTeamId}
            onChange={(e) => setSelectedTeamId(e.target.value ? Number(e.target.value) : '')}
            disabled={submitting || loadingInitial || teams.length === 0}
            data-testid="edit-team-select"
          >
            <option value="">-- No Team Assigned --</option>
            {teams.map(t => (
              <option key={t.id} value={t.id}>
                {t.name} {!t.is_active ? '(Inactive)' : ''}
              </option>
            ))}
          </select>
          {teams.length === 0 && (
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '4px', display: 'block' }}>
              No teams available in this employee's department.
            </span>
          )}
        </div>

        {/* Reporting Manager */}
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
            <User size={14} color="var(--color-text-muted)" /> Reporting Manager
          </label>
          <select
            className="input-field"
            value={reportingManagerId}
            onChange={(e) => setReportingManagerId(e.target.value ? Number(e.target.value) : '')}
            disabled={submitting || loadingInitial}
            data-testid="edit-manager-select"
          >
            <option value="">-- No Reporting Manager --</option>
            {managers.map(m => (
              <option key={m.id} value={m.id}>
                {m.first_name} {m.last_name} ({m.employee_code})
              </option>
            ))}
          </select>
          {fieldErrors.reporting_manager && (
            <span style={{ color: 'var(--color-status-danger, #dc2626)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
              {fieldErrors.reporting_manager}
            </span>
          )}
        </div>
      </form>
    </Modal>
  );
};
