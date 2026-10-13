import React, { useState } from 'react';
import { Building2, ArrowRight } from 'lucide-react';
import type { Stage1Payload } from '../../../services/onboardingService';

interface Stage1OrgDetailsProps {
  initialData?: Partial<Stage1Payload>;
  isSubmitting: boolean;
  onSubmit: (data: Stage1Payload) => void;
  fieldErrors?: Record<string, string[]>;
}

export const Stage1OrgDetails: React.FC<Stage1OrgDetailsProps> = ({
  initialData,
  isSubmitting,
  onSubmit,
  fieldErrors = {},
}) => {
  const [formData, setFormData] = useState<Stage1Payload>({
    name: initialData?.name || '',
    code: initialData?.code || '',
    currency_code: initialData?.currency_code || 'INR',
    date_format: initialData?.date_format || 'DD/MM/YYYY',
    timezone: initialData?.timezone || 'Asia/Kolkata',
  });

  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const errors: Record<string, string> = {};
    if (!formData.name || !formData.name.trim()) {
      errors.name = 'Organization name is required.';
    } else if (formData.name.trim().length > 255) {
      errors.name = 'Organization name cannot exceed 255 characters.';
    }

    if (formData.code && formData.code.trim().length > 50) {
      errors.code = 'Organization code cannot exceed 50 characters.';
    }

    setClientErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validate()) {
      onSubmit({
        name: formData.name.trim(),
        code: formData.code?.trim() || undefined,
        currency_code: formData.currency_code || 'INR',
        date_format: formData.date_format || 'DD/MM/YYYY',
        timezone: formData.timezone || 'Asia/Kolkata',
      });
    }
  };

  return (
    <form noValidate onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Intro Banner */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(99, 102, 241, 0.04) 100%)',
          border: '1px solid var(--color-primary-alpha, rgba(59, 130, 246, 0.2))',
          borderRadius: 'var(--radius-md, 8px)',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '12px',
        }}
      >
        <Building2 size={24} style={{ color: 'var(--color-primary, #3b82f6)', flexShrink: 0, marginTop: '2px' }} />
        <div>
          <h3 style={{ margin: '0 0 4px', fontSize: '0.95rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
            Welcome to BeyondSure HRMS Setup
          </h3>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--color-text-sub, #475569)', lineHeight: 1.5 }}>
            Establish your organization identity. This step initializes your tenant boundary, provisions default branding, and registers your durable setup state machine.
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
        {/* Organization Name */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label htmlFor="org-name" style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
            Organization Legal Name <span style={{ color: 'var(--color-status-danger, #ef4444)' }}>*</span>
          </label>
          <input
            id="org-name"
            type="text"
            required
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="e.g. Apex Global Technologies Pvt Ltd"
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-md, 8px)',
              border: clientErrors.name || fieldErrors.name ? '1px solid var(--color-status-danger, #ef4444)' : '1px solid var(--color-border, #cbd5e1)',
              background: 'var(--surface-control-bg, #ffffff)',
              color: 'var(--color-text-main, #0f172a)',
              fontSize: '0.9375rem',
            }}
          />
          {(clientErrors.name || fieldErrors.name) && (
            <span style={{ fontSize: '0.75rem', color: 'var(--color-status-danger, #ef4444)' }}>
              {clientErrors.name || fieldErrors.name?.[0]}
            </span>
          )}
          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #64748b)' }}>
            This name appears across pay slips, employee offer letters, and reports.
          </span>
        </div>

        {/* Organization Code */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label htmlFor="org-code" style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
            Organization Code <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #94a3b8)' }}>(Optional)</span>
          </label>
          <input
            id="org-code"
            type="text"
            value={formData.code}
            onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
            placeholder="e.g. APEX"
            maxLength={50}
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-md, 8px)',
              border: clientErrors.code || fieldErrors.code ? '1px solid var(--color-status-danger, #ef4444)' : '1px solid var(--color-border, #cbd5e1)',
              background: 'var(--surface-control-bg, #ffffff)',
              color: 'var(--color-text-main, #0f172a)',
              fontSize: '0.9375rem',
              letterSpacing: '0.05em',
            }}
          />
          {(clientErrors.code || fieldErrors.code) && (
            <span style={{ fontSize: '0.75rem', color: 'var(--color-status-danger, #ef4444)' }}>
              {clientErrors.code || fieldErrors.code?.[0]}
            </span>
          )}
          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #64748b)' }}>
            Short identifier used for employee IDs and asset tags.
          </span>
        </div>
      </div>

      {/* Regional & Financial Preferences */}
      <div
        style={{
          borderTop: '1px solid var(--color-border-subtle, #f1f5f9)',
          paddingTop: '20px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '20px',
        }}
      >
        {/* Currency Code */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label htmlFor="currency-code" style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
            Base Currency
          </label>
          <select
            id="currency-code"
            value={formData.currency_code}
            onChange={(e) => setFormData({ ...formData, currency_code: e.target.value })}
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-md, 8px)',
              border: '1px solid var(--color-border, #cbd5e1)',
              background: 'var(--surface-control-bg, #ffffff)',
              color: 'var(--color-text-main, #0f172a)',
              fontSize: '0.9375rem',
            }}
          >
            <option value="INR">INR — Indian Rupee (₹)</option>
            <option value="USD">USD — US Dollar ($)</option>
            <option value="EUR">EUR — Euro (€)</option>
            <option value="GBP">GBP — British Pound (£)</option>
            <option value="SGD">SGD — Singapore Dollar (S$)</option>
            <option value="AED">AED — UAE Dirham (د.إ)</option>
          </select>
        </div>

        {/* Date Format */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label htmlFor="date-format" style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
            Date Format
          </label>
          <select
            id="date-format"
            value={formData.date_format}
            onChange={(e) => setFormData({ ...formData, date_format: e.target.value })}
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-md, 8px)',
              border: '1px solid var(--color-border, #cbd5e1)',
              background: 'var(--surface-control-bg, #ffffff)',
              color: 'var(--color-text-main, #0f172a)',
              fontSize: '0.9375rem',
            }}
          >
            <option value="DD/MM/YYYY">DD/MM/YYYY (e.g. 13/10/2026)</option>
            <option value="MM/DD/YYYY">MM/DD/YYYY (e.g. 10/13/2026)</option>
            <option value="YYYY-MM-DD">YYYY-MM-DD (e.g. 2026-10-13)</option>
          </select>
        </div>

        {/* Timezone */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label htmlFor="org-timezone" style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
            Organization Timezone
          </label>
          <select
            id="org-timezone"
            value={formData.timezone}
            onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-md, 8px)',
              border: '1px solid var(--color-border, #cbd5e1)',
              background: 'var(--surface-control-bg, #ffffff)',
              color: 'var(--color-text-main, #0f172a)',
              fontSize: '0.9375rem',
            }}
          >
            <option value="Asia/Kolkata">Asia/Kolkata (IST +05:30)</option>
            <option value="UTC">UTC (Coordinated Universal Time)</option>
            <option value="America/New_York">America/New_York (EST/EDT)</option>
            <option value="Europe/London">Europe/London (GMT/BST)</option>
            <option value="Asia/Dubai">Asia/Dubai (GST +04:00)</option>
            <option value="Asia/Singapore">Asia/Singapore (SGT +08:00)</option>
          </select>
        </div>
      </div>

      {/* Form Action Footer */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          borderTop: '1px solid var(--color-border, #e2e8f0)',
          paddingTop: '20px',
        }}
      >
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
            transition: 'all 0.15s ease',
          }}
        >
          {isSubmitting ? 'Initializing Organization...' : 'Continue to Head Office'}
          <ArrowRight size={18} />
        </button>
      </div>
    </form>
  );
};
