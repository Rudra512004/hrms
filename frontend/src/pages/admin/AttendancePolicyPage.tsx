import React, { useState, useEffect, useCallback, useRef } from 'react';
import { attendancePolicyService, type AttendancePolicy, type UpdateAttendancePolicyPayload } from '../../services/attendancePolicy';
import { Card } from '../../components/Card';
import { PageHeader } from '../../components/PageHeader';
import { AlertBanner } from '../../components/AlertBanner';
import { ShieldAlert, Loader2, Save, MapPin, Wifi, Laptop, ShieldCheck } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useBranchContext } from '../../contexts/BranchContext';

export const AttendancePolicyPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const { branchId, selectedBranch } = useBranchContext();

  const [policy, setPolicy] = useState<AttendancePolicy | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Policy form fields
  const [formData, setFormData] = useState<{
    is_office_gps_enabled: boolean;
    is_office_ip_enabled: boolean;
    is_wfh_enabled: boolean;
    wfh_bypasses_office_restrictions: boolean;
  }>({
    is_office_gps_enabled: true,
    is_office_ip_enabled: false,
    is_wfh_enabled: false,
    wfh_bypasses_office_restrictions: true,
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  const canView = hasPermission('branch.view');
  const canManage = hasPermission('branch.manage');
  const isAllLocations = branchId === null;

  const loadPolicy = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    if (branchId === null) {
      setPolicy(null);
      setError(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setSuccessMessage(null);

      const data = await attendancePolicyService.getAttendancePolicy(branchId, { signal: controller.signal });

      if (abortControllerRef.current === controller) {
        setPolicy(data);
        setFormData({
          is_office_gps_enabled: Boolean(data.is_office_gps_enabled),
          is_office_ip_enabled: Boolean(data.is_office_ip_enabled),
          is_wfh_enabled: Boolean(data.is_wfh_enabled),
          wfh_bypasses_office_restrictions: Boolean(data.wfh_bypasses_office_restrictions),
        });
      }
    } catch (err: any) {
      if (err.name === 'AbortError') return;
      if (abortControllerRef.current === controller) {
        if (err?.status === 403 || err?.response?.status === 403) {
          setError('403 Forbidden: You do not have permission to view attendance policy.');
        } else if (err?.errorData?.detail) {
          setError(err.errorData.detail);
        } else {
          setError('Failed to load attendance policy.');
        }
        setPolicy(null);
      }
    } finally {
      if (abortControllerRef.current === controller) {
        setLoading(false);
      }
    }
  }, [branchId]);

  useEffect(() => {
    setPolicy(null);
    loadPolicy();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [loadPolicy]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManage || !branchId) return;

    setSaving(true);
    setError(null);
    setSuccessMessage(null);

    const payload: UpdateAttendancePolicyPayload = {
      is_office_gps_enabled: formData.is_office_gps_enabled,
      is_office_ip_enabled: formData.is_office_ip_enabled,
      is_wfh_enabled: formData.is_wfh_enabled,
      wfh_bypasses_office_restrictions: formData.wfh_bypasses_office_restrictions,
    };

    try {
      const updated = await attendancePolicyService.updateAttendancePolicy(branchId, payload);
      setPolicy(updated);
      setSuccessMessage('Attendance policy updated successfully.');
    } catch (err: any) {
      if (err?.status === 403 || err?.response?.status === 403) {
        setError('403 Forbidden: You do not have permission to manage attendance policy.');
      } else if (err?.errorData?.detail) {
        setError(err.errorData.detail);
      } else {
        setError('Failed to save attendance policy.');
      }
    } finally {
      setSaving(false);
    }
  };

  if (!canView) {
    return (
      <div className="animate-fade-in">
        <PageHeader title="Attendance Policy" subtitle="Branch attendance policy configuration." />
        <AlertBanner type="error" message="You do not have permission to access attendance policy." />
      </div>
    );
  }

  const branchName = selectedBranch.type === 'branch' && selectedBranch.branch?.name
    ? selectedBranch.branch.name
    : 'Unknown Branch';

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      <PageHeader
        title="Attendance Policy"
        subtitle="Configure verification rules, geofencing, and remote work policies for this branch."
      />

      {isAllLocations && (
        <AlertBanner
          type="info"
          message="Select a branch from the header to manage this configuration."
        />
      )}

      {error && <AlertBanner type="error" message={error} />}
      {successMessage && <AlertBanner type="success" message={successMessage} />}

      {!canManage && !isAllLocations && (
        <AlertBanner
          type="info"
          message="You have read-only access (branch.view). Contact an administrator with branch.manage to modify attendance policy."
        />
      )}

      {!isAllLocations && (
        <Card>
          {loading ? (
            <div className="loading-center" style={{ padding: 'var(--spacing-2xl)' }}>
              <Loader2 size={28} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
              <span style={{ marginTop: '8px' }}>Loading attendance policy…</span>
            </div>
          ) : policy ? (
            <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-xl)' }}>
              <div>
                <h3 style={{ margin: '0 0 4px 0', fontSize: '1.1rem', color: 'var(--color-text-main)' }}>
                  Branch: {branchName}
                </h3>
                <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                  These rules govern check-in validation and fraud prevention for all employees in this branch.
                </p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
                {/* Office GPS Geofencing */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 'var(--spacing-md)',
                    padding: 'var(--spacing-md)',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--color-bg-body)',
                    border: '1px solid var(--color-border)',
                  }}
                >
                  <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(59, 130, 246, 0.1)', color: 'var(--color-primary)' }}>
                    <MapPin size={20} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label htmlFor="policy-gps" style={{ fontWeight: 600, color: 'var(--color-text-main)', cursor: canManage ? 'pointer' : 'default' }}>
                      Require Office GPS Geofencing
                    </label>
                    <p style={{ margin: '4px 0 0 0', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                      When enabled, employees must be physically within the branch geofence radius to clock in or out.
                    </p>
                  </div>
                  <input
                    id="policy-gps"
                    type="checkbox"
                    checked={formData.is_office_gps_enabled}
                    onChange={(e) => setFormData({ ...formData, is_office_gps_enabled: e.target.checked })}
                    disabled={!canManage || saving}
                    style={{ width: '18px', height: '18px', cursor: canManage ? 'pointer' : 'default', marginTop: '2px' }}
                  />
                </div>

                {/* Office IP/Network */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 'var(--spacing-md)',
                    padding: 'var(--spacing-md)',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--color-bg-body)',
                    border: '1px solid var(--color-border)',
                  }}
                >
                  <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(16, 185, 129, 0.1)', color: 'var(--color-status-success)' }}>
                    <Wifi size={20} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label htmlFor="policy-ip" style={{ fontWeight: 600, color: 'var(--color-text-main)', cursor: canManage ? 'pointer' : 'default' }}>
                      Require Office Network IP Verification
                    </label>
                    <p style={{ margin: '4px 0 0 0', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                      When enabled, employee requests must originate from an authorized branch CIDR network.
                    </p>
                  </div>
                  <input
                    id="policy-ip"
                    type="checkbox"
                    checked={formData.is_office_ip_enabled}
                    onChange={(e) => setFormData({ ...formData, is_office_ip_enabled: e.target.checked })}
                    disabled={!canManage || saving}
                    style={{ width: '18px', height: '18px', cursor: canManage ? 'pointer' : 'default', marginTop: '2px' }}
                  />
                </div>

                {/* Work From Home Allowed */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 'var(--spacing-md)',
                    padding: 'var(--spacing-md)',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--color-bg-body)',
                    border: '1px solid var(--color-border)',
                  }}
                >
                  <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(245, 158, 11, 0.1)', color: 'var(--color-status-warning)' }}>
                    <Laptop size={20} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label htmlFor="policy-wfh" style={{ fontWeight: 600, color: 'var(--color-text-main)', cursor: canManage ? 'pointer' : 'default' }}>
                      Allow Work From Home (WFH)
                    </label>
                    <p style={{ margin: '4px 0 0 0', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                      Enables employees in this branch to submit WFH requests for remote attendance approval.
                    </p>
                  </div>
                  <input
                    id="policy-wfh"
                    type="checkbox"
                    checked={formData.is_wfh_enabled}
                    onChange={(e) => setFormData({ ...formData, is_wfh_enabled: e.target.checked })}
                    disabled={!canManage || saving}
                    style={{ width: '18px', height: '18px', cursor: canManage ? 'pointer' : 'default', marginTop: '2px' }}
                  />
                </div>

                {/* WFH Bypasses Restrictions */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 'var(--spacing-md)',
                    padding: 'var(--spacing-md)',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--color-bg-body)',
                    border: '1px solid var(--color-border)',
                  }}
                >
                  <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(139, 92, 246, 0.1)', color: '#8b5cf6' }}>
                    <ShieldCheck size={20} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label htmlFor="policy-bypass" style={{ fontWeight: 600, color: 'var(--color-text-main)', cursor: canManage ? 'pointer' : 'default' }}>
                      Approved WFH Bypasses Office Restrictions
                    </label>
                    <p style={{ margin: '4px 0 0 0', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                      If an employee has an approved WFH request for the date, office GPS and IP restrictions are bypassed.
                    </p>
                  </div>
                  <input
                    id="policy-bypass"
                    type="checkbox"
                    checked={formData.wfh_bypasses_office_restrictions}
                    onChange={(e) => setFormData({ ...formData, wfh_bypasses_office_restrictions: e.target.checked })}
                    disabled={!canManage || saving}
                    style={{ width: '18px', height: '18px', cursor: canManage ? 'pointer' : 'default', marginTop: '2px' }}
                  />
                </div>
              </div>

              {canManage && (
                <div style={{ display: 'flex', justifyContent: 'flex-start', paddingTop: 'var(--spacing-md)', borderTop: '1px solid var(--color-border)' }}>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={saving}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
                  >
                    {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                    <span>{saving ? 'Saving Policy…' : 'Save Attendance Policy'}</span>
                  </button>
                </div>
              )}
            </form>
          ) : (
            <div style={{ textAlign: 'center', padding: 'var(--spacing-xl)', color: 'var(--color-text-muted)' }}>
              <ShieldAlert size={36} style={{ margin: '0 auto 8px auto', opacity: 0.5 }} />
              <p>No attendance policy found for this branch.</p>
            </div>
          )}
        </Card>
      )}
    </div>
  );
};
