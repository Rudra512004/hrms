import React, { useState } from 'react';
import {
  Clock,
  Shield,
  Wifi,
  ArrowRight,
  ArrowLeft,
} from 'lucide-react';
import type { Stage5Payload, ShiftItem, AttendancePolicyItem, OfficeNetworkItem } from '../../../services/onboardingService';

interface Stage5ShiftsPolicyProps {
  initialData?: Partial<Stage5Payload>;
  isSubmitting: boolean;
  onBack: () => void;
  onSubmit: (data: Stage5Payload) => void;
  fieldErrors?: Record<string, string[]>;
}

export const Stage5ShiftsPolicy: React.FC<Stage5ShiftsPolicyProps> = ({
  initialData,
  isSubmitting,
  onBack,
  onSubmit,
  fieldErrors: _fieldErrors = {},
}) => {
  const [shift, setShift] = useState<ShiftItem>({
    name: initialData?.shift?.name || 'General Day Shift',
    code: initialData?.shift?.code || 'GEN-9TO6',
    start_time: initialData?.shift?.start_time || '09:00:00',
    end_time: initialData?.shift?.end_time || '18:00:00',
    grace_period_minutes: initialData?.shift?.grace_period_minutes ?? 15,
    work_days: initialData?.shift?.work_days || '0,1,2,3,4',
  });

  const [policy, setPolicy] = useState<AttendancePolicyItem>({
    is_office_gps_enabled: initialData?.attendance_policy?.is_office_gps_enabled ?? true,
    is_office_ip_enabled: initialData?.attendance_policy?.is_office_ip_enabled ?? false,
    is_wfh_enabled: initialData?.attendance_policy?.is_wfh_enabled ?? true,
    wfh_bypasses_office_restrictions: initialData?.attendance_policy?.wfh_bypasses_office_restrictions ?? true,
  });

  const [includeNetwork, setIncludeNetwork] = useState<boolean>(
    Boolean(initialData?.office_network?.network)
  );

  const [network, setNetwork] = useState<OfficeNetworkItem>({
    name: initialData?.office_network?.name || 'Headquarters Wi-Fi',
    network: initialData?.office_network?.network || '192.168.1.0/24',
    description: initialData?.office_network?.description || 'Corporate office subnet for IP clock-in',
  });

  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const errors: Record<string, string> = {};
    if (!shift.name.trim()) {
      errors.shift_name = 'Shift name is required.';
    }
    if (!shift.start_time) {
      errors.start_time = 'Shift start time is required.';
    }
    if (!shift.end_time) {
      errors.end_time = 'Shift end time is required.';
    }

    if (includeNetwork && (!network.network || !network.network.trim())) {
      errors.network = 'Office network CIDR is required when IP verification is configured.';
    }

    setClientErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validate()) {
      onSubmit({
        shift: {
          ...shift,
          name: shift.name.trim(),
          code: shift.code?.trim() || undefined,
          start_time: shift.start_time.length === 5 ? `${shift.start_time}:00` : shift.start_time,
          end_time: shift.end_time.length === 5 ? `${shift.end_time}:00` : shift.end_time,
          grace_period_minutes: Number(shift.grace_period_minutes) || 0,
        },
        attendance_policy: policy,
        office_network: includeNetwork && network.network.trim() ? {
          name: network.name.trim() || 'HQ Office Network',
          network: network.network.trim(),
          description: network.description?.trim() || undefined,
        } : undefined,
      });
    }
  };

  return (
    <form noValidate onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* Intro Banner */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(14, 165, 233, 0.08) 0%, rgba(59, 130, 246, 0.04) 100%)',
          border: '1px solid rgba(14, 165, 233, 0.2)',
          borderRadius: 'var(--radius-md, 8px)',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '12px',
        }}
      >
        <Clock size={24} style={{ color: 'var(--color-status-info, #0284c7)', flexShrink: 0, marginTop: '2px' }} />
        <div>
          <h3 style={{ margin: '0 0 4px', fontSize: '0.95rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
            Working Shift & Clock-In Policies
          </h3>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--color-text-sub, #475569)', lineHeight: 1.5 }}>
            Establishes your active branch working shift and attendance verification barriers (GPS geofencing, IP verification, and WFH privileges).
          </p>
        </div>
      </div>

      {/* Shift Configuration */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: 'var(--color-text-main, #0f172a)' }}>
            Primary Operational Shift
          </h4>
          <span
            style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              padding: '3px 8px',
              borderRadius: '12px',
              background: 'var(--color-status-success-bg, #ecfdf5)',
              color: 'var(--color-status-success, #059669)',
              border: '1px solid var(--color-status-success-border, #a7f3d0)',
            }}
          >
            Single Active Shift Invariant
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="shift-name" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>
              Shift Name <span style={{ color: 'var(--color-status-danger, #ef4444)' }}>*</span>
            </label>
            <input
              id="shift-name"
              type="text"
              required
              value={shift.name}
              onChange={(e) => setShift({ ...shift, name: e.target.value })}
              placeholder="e.g. General Day Shift"
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                border: clientErrors.shift_name ? '1px solid var(--color-status-danger, #ef4444)' : '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--surface-control-bg, #ffffff)',
                fontSize: '0.9375rem',
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="shift-code" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>Shift Code</label>
            <input
              id="shift-code"
              type="text"
              value={shift.code || ''}
              onChange={(e) => setShift({ ...shift, code: e.target.value.toUpperCase() })}
              placeholder="GEN-9TO6"
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                border: '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--surface-control-bg, #ffffff)',
                fontSize: '0.9375rem',
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="start-time" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>Start Time (24h)</label>
            <input
              id="start-time"
              type="time"
              required
              value={shift.start_time.slice(0, 5)}
              onChange={(e) => setShift({ ...shift, start_time: e.target.value })}
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                border: '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--surface-control-bg, #ffffff)',
                fontSize: '0.9375rem',
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="end-time" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>End Time (24h)</label>
            <input
              id="end-time"
              type="time"
              required
              value={shift.end_time.slice(0, 5)}
              onChange={(e) => setShift({ ...shift, end_time: e.target.value })}
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                border: '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--surface-control-bg, #ffffff)',
                fontSize: '0.9375rem',
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="grace-period" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>Grace Period (Minutes)</label>
            <input
              id="grace-period"
              type="number"
              min="0"
              max="120"
              value={shift.grace_period_minutes ?? 15}
              onChange={(e) => setShift({ ...shift, grace_period_minutes: parseInt(e.target.value) || 0 })}
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                border: '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--surface-control-bg, #ffffff)',
                fontSize: '0.9375rem',
              }}
            />
          </div>
        </div>
      </div>

      {/* Attendance Policy Security Controls */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', borderTop: '1px solid var(--color-border-subtle, #f1f5f9)', paddingTop: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Shield size={18} style={{ color: 'var(--color-primary, #3b82f6)' }} />
          <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: 'var(--color-text-main, #0f172a)' }}>
            Attendance Verification Barriers
          </h4>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
          {/* GPS Verification */}
          <div
            style={{
              padding: '14px 16px',
              borderRadius: 'var(--radius-md, 8px)',
              background: 'var(--surface-control-bg, #f8fafc)',
              border: '1px solid var(--color-border-subtle, #e2e8f0)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-main, #0f172a)' }}>
                GPS Geofence Verification
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #64748b)' }}>
                Requires clock-ins to be inside branch radius.
              </div>
            </div>
            <input
              type="checkbox"
              checked={policy.is_office_gps_enabled}
              onChange={(e) => setPolicy({ ...policy, is_office_gps_enabled: e.target.checked })}
              style={{ width: '18px', height: '18px', accentColor: 'var(--color-primary, #3b82f6)' }}
            />
          </div>

          {/* IP Subnet Verification */}
          <div
            style={{
              padding: '14px 16px',
              borderRadius: 'var(--radius-md, 8px)',
              background: 'var(--surface-control-bg, #f8fafc)',
              border: '1px solid var(--color-border-subtle, #e2e8f0)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-main, #0f172a)' }}>
                Office IP Subnet Check
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #64748b)' }}>
                Validates employee IP against office network.
              </div>
            </div>
            <input
              type="checkbox"
              checked={policy.is_office_ip_enabled}
              onChange={(e) => setPolicy({ ...policy, is_office_ip_enabled: e.target.checked })}
              style={{ width: '18px', height: '18px', accentColor: 'var(--color-primary, #3b82f6)' }}
            />
          </div>

          {/* WFH Enabled */}
          <div
            style={{
              padding: '14px 16px',
              borderRadius: 'var(--radius-md, 8px)',
              background: 'var(--surface-control-bg, #f8fafc)',
              border: '1px solid var(--color-border-subtle, #e2e8f0)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-main, #0f172a)' }}>
                Work From Home (WFH)
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #64748b)' }}>
                Allows employees to request remote punch-in.
              </div>
            </div>
            <input
              type="checkbox"
              checked={policy.is_wfh_enabled}
              onChange={(e) => setPolicy({ ...policy, is_wfh_enabled: e.target.checked })}
              style={{ width: '18px', height: '18px', accentColor: 'var(--color-primary, #3b82f6)' }}
            />
          </div>

          {/* WFH Bypasses Geofence */}
          <div
            style={{
              padding: '14px 16px',
              borderRadius: 'var(--radius-md, 8px)',
              background: 'var(--surface-control-bg, #f8fafc)',
              border: '1px solid var(--color-border-subtle, #e2e8f0)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-main, #0f172a)' }}>
                WFH Bypasses Office Geofence
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #64748b)' }}>
                Approved WFH ignores GPS distance checks.
              </div>
            </div>
            <input
              type="checkbox"
              checked={policy.wfh_bypasses_office_restrictions}
              onChange={(e) => setPolicy({ ...policy, wfh_bypasses_office_restrictions: e.target.checked })}
              style={{ width: '18px', height: '18px', accentColor: 'var(--color-primary, #3b82f6)' }}
            />
          </div>
        </div>
      </div>

      {/* Office Wi-Fi / IP Configuration (Optional) */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', borderTop: '1px solid var(--color-border-subtle, #f1f5f9)', paddingTop: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Wifi size={18} style={{ color: 'var(--color-primary, #3b82f6)' }} />
            <div>
              <h4 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
                Office Wi-Fi Subnet Network
              </h4>
              <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--color-text-muted, #64748b)' }}>
                Configure an office IP subnet (CIDR) for network-based clock-in.
              </p>
            </div>
          </div>

          <label style={{ display: 'inline-flex', alignItems: 'center', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={includeNetwork}
              onChange={(e) => setIncludeNetwork(e.target.checked)}
              style={{ width: '18px', height: '18px', accentColor: 'var(--color-primary, #3b82f6)' }}
            />
          </label>
        </div>

        {includeNetwork && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label htmlFor="network-name" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>Network Name</label>
              <input
                id="network-name"
                type="text"
                value={network.name}
                onChange={(e) => setNetwork({ ...network, name: e.target.value })}
                placeholder="Headquarters Wi-Fi"
                style={{
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-md, 8px)',
                  border: '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--surface-control-bg, #ffffff)',
                  fontSize: '0.9375rem',
                }}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label htmlFor="network-cidr" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>
                Subnet CIDR <span style={{ color: 'var(--color-status-danger, #ef4444)' }}>*</span>
              </label>
              <input
                id="network-cidr"
                type="text"
                value={network.network}
                onChange={(e) => setNetwork({ ...network, network: e.target.value })}
                placeholder="192.168.1.0/24"
                style={{
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-md, 8px)',
                  border: clientErrors.network ? '1px solid var(--color-status-danger, #ef4444)' : '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--surface-control-bg, #ffffff)',
                  fontSize: '0.9375rem',
                }}
              />
              {clientErrors.network && (
                <span style={{ fontSize: '0.75rem', color: 'var(--color-status-danger, #ef4444)' }}>
                  {clientErrors.network}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Form Action Footer */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderTop: '1px solid var(--color-border, #e2e8f0)',
          paddingTop: '20px',
        }}
      >
        <button
          type="button"
          onClick={onBack}
          disabled={isSubmitting}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 20px',
            borderRadius: 'var(--radius-md, 8px)',
            background: 'var(--surface-control-bg, #f1f5f9)',
            color: 'var(--color-text-main, #0f172a)',
            border: '1px solid var(--color-border, #cbd5e1)',
            fontSize: '0.9375rem',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          <ArrowLeft size={18} />
          Back to Calendar
        </button>

        <button
          type="submit"
          disabled={isSubmitting}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 24px',
            borderRadius: 'var(--radius-md, 8px)',
            background: 'var(--color-primary, #3b82f6)',
            color: '#ffffff',
            border: 'none',
            fontSize: '0.9375rem',
            fontWeight: 600,
            cursor: isSubmitting ? 'wait' : 'pointer',
            boxShadow: '0 4px 12px rgba(59, 130, 246, 0.25)',
          }}
        >
          {isSubmitting ? 'Saving Shifts...' : 'Continue to Administrator & RBAC'}
          <ArrowRight size={18} />
        </button>
      </div>
    </form>
  );
};
