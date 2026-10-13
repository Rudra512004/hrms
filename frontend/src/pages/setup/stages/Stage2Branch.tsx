import React, { useState } from 'react';
import { MapPin, ArrowRight, ArrowLeft, Navigation, ShieldAlert } from 'lucide-react';
import type { Stage2Payload } from '../../../services/onboardingService';

interface Stage2BranchProps {
  initialData?: Partial<Stage2Payload>;
  isSubmitting: boolean;
  onBack: () => void;
  onSubmit: (data: Stage2Payload) => void;
  fieldErrors?: Record<string, string[]>;
}

export const Stage2Branch: React.FC<Stage2BranchProps> = ({
  initialData,
  isSubmitting,
  onBack,
  onSubmit,
  fieldErrors = {},
}) => {
  const [formData, setFormData] = useState<Stage2Payload>({
    name: initialData?.name || 'Headquarters Bengaluru',
    code: initialData?.code || 'HQ-BLR',
    address_line1: initialData?.address_line1 || '',
    address_line2: initialData?.address_line2 || '',
    city: initialData?.city || 'Bengaluru',
    state: initialData?.state || 'Karnataka',
    country: initialData?.country || 'India',
    postal_code: initialData?.postal_code || '',
    timezone: initialData?.timezone || 'Asia/Kolkata',
    latitude: initialData?.latitude ?? 12.9716,
    longitude: initialData?.longitude ?? 77.5946,
    radius: initialData?.radius ?? 200.0,
  });

  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const errors: Record<string, string> = {};
    if (!formData.name || !formData.name.trim()) {
      errors.name = 'Branch name is required.';
    }

    if (formData.radius !== undefined && formData.radius !== null) {
      const numRadius = Number(formData.radius);
      if (isNaN(numRadius) || numRadius < 100.0) {
        errors.radius = 'Geofence radius must be at least 100.0 meters.';
      }
    }

    if (formData.latitude !== undefined && formData.latitude !== null) {
      const lat = Number(formData.latitude);
      if (isNaN(lat) || lat < -90 || lat > 90) {
        errors.latitude = 'Latitude must be between -90 and +90 degrees.';
      }
    }

    if (formData.longitude !== undefined && formData.longitude !== null) {
      const lng = Number(formData.longitude);
      if (isNaN(lng) || lng < -180 || lng > 180) {
        errors.longitude = 'Longitude must be between -180 and +180 degrees.';
      }
    }

    setClientErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validate()) {
      onSubmit({
        ...formData,
        name: formData.name.trim(),
        code: formData.code?.trim() || undefined,
        radius: formData.radius ? Number(formData.radius) : 100.0,
        latitude: formData.latitude !== null && formData.latitude !== undefined ? Number(formData.latitude) : null,
        longitude: formData.longitude !== null && formData.longitude !== undefined ? Number(formData.longitude) : null,
      });
    }
  };

  return (
    <form noValidate onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Intro Banner */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(59, 130, 246, 0.04) 100%)',
          border: '1px solid rgba(16, 185, 129, 0.2)',
          borderRadius: 'var(--radius-md, 8px)',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '12px',
        }}
      >
        <MapPin size={24} style={{ color: 'var(--color-status-success, #10b981)', flexShrink: 0, marginTop: '2px' }} />
        <div>
          <h3 style={{ margin: '0 0 4px', fontSize: '0.95rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
            Head Office (Primary Branch)
          </h3>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--color-text-sub, #475569)', lineHeight: 1.5 }}>
            Every organization requires an operational Head Office. Signals will automatically provision an initial Working Calendar and Attendance Policy tied to this location.
          </p>
        </div>
      </div>

      {/* Basic Branch Information */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label htmlFor="branch-name" style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
            Branch Name <span style={{ color: 'var(--color-status-danger, #ef4444)' }}>*</span>
          </label>
          <input
            id="branch-name"
            type="text"
            required
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="e.g. Headquarters Bengaluru"
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
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label htmlFor="branch-code" style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
            Branch Code
          </label>
          <input
            id="branch-code"
            type="text"
            value={formData.code || ''}
            onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
            placeholder="e.g. HQ-BLR"
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-md, 8px)',
              border: '1px solid var(--color-border, #cbd5e1)',
              background: 'var(--surface-control-bg, #ffffff)',
              color: 'var(--color-text-main, #0f172a)',
              fontSize: '0.9375rem',
            }}
          />
        </div>
      </div>

      {/* Address Information */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <h4 style={{ margin: '8px 0 0', fontSize: '0.875rem', fontWeight: 700, color: 'var(--color-text-main, #0f172a)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Physical Location
        </h4>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="address-1" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>
              Street Address Line 1
            </label>
            <input
              id="address-1"
              type="text"
              value={formData.address_line1 || ''}
              onChange={(e) => setFormData({ ...formData, address_line1: e.target.value })}
              placeholder="e.g. 100 Tech Park Way, Whitefield"
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                border: '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--surface-control-bg, #ffffff)',
                color: 'var(--color-text-main, #0f172a)',
                fontSize: '0.9375rem',
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="address-2" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>
              Street Address Line 2
            </label>
            <input
              id="address-2"
              type="text"
              value={formData.address_line2 || ''}
              onChange={(e) => setFormData({ ...formData, address_line2: e.target.value })}
              placeholder="e.g. Tower B, 4th Floor"
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                border: '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--surface-control-bg, #ffffff)',
                color: 'var(--color-text-main, #0f172a)',
                fontSize: '0.9375rem',
              }}
            />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="city" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>City</label>
            <input
              id="city"
              type="text"
              value={formData.city || ''}
              onChange={(e) => setFormData({ ...formData, city: e.target.value })}
              placeholder="Bengaluru"
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                border: '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--surface-control-bg, #ffffff)',
                color: 'var(--color-text-main, #0f172a)',
                fontSize: '0.9375rem',
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="state" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>State / Province</label>
            <input
              id="state"
              type="text"
              value={formData.state || ''}
              onChange={(e) => setFormData({ ...formData, state: e.target.value })}
              placeholder="Karnataka"
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                border: '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--surface-control-bg, #ffffff)',
                color: 'var(--color-text-main, #0f172a)',
                fontSize: '0.9375rem',
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="country" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>Country</label>
            <input
              id="country"
              type="text"
              value={formData.country || ''}
              onChange={(e) => setFormData({ ...formData, country: e.target.value })}
              placeholder="India"
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                border: '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--surface-control-bg, #ffffff)',
                color: 'var(--color-text-main, #0f172a)',
                fontSize: '0.9375rem',
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="postal-code" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>Postal Code</label>
            <input
              id="postal-code"
              type="text"
              value={formData.postal_code || ''}
              onChange={(e) => setFormData({ ...formData, postal_code: e.target.value })}
              placeholder="560100"
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                border: '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--surface-control-bg, #ffffff)',
                color: 'var(--color-text-main, #0f172a)',
                fontSize: '0.9375rem',
              }}
            />
          </div>
        </div>
      </div>

      {/* Geofence & Coordinates */}
      <div
        style={{
          borderTop: '1px solid var(--color-border-subtle, #f1f5f9)',
          paddingTop: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Navigation size={18} style={{ color: 'var(--color-primary, #3b82f6)' }} />
          <h4 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--color-text-main, #0f172a)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Attendance Geofence Boundary
          </h4>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="latitude" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>Latitude (-90 to +90)</label>
            <input
              id="latitude"
              type="number"
              step="any"
              value={formData.latitude ?? ''}
              onChange={(e) => setFormData({ ...formData, latitude: e.target.value ? parseFloat(e.target.value) : null })}
              placeholder="12.9716"
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                border: clientErrors.latitude || fieldErrors.latitude ? '1px solid var(--color-status-danger, #ef4444)' : '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--surface-control-bg, #ffffff)',
                color: 'var(--color-text-main, #0f172a)',
                fontSize: '0.9375rem',
              }}
            />
            {(clientErrors.latitude || fieldErrors.latitude) && (
              <span style={{ fontSize: '0.75rem', color: 'var(--color-status-danger, #ef4444)' }}>
                {clientErrors.latitude || fieldErrors.latitude?.[0]}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="longitude" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>Longitude (-180 to +180)</label>
            <input
              id="longitude"
              type="number"
              step="any"
              value={formData.longitude ?? ''}
              onChange={(e) => setFormData({ ...formData, longitude: e.target.value ? parseFloat(e.target.value) : null })}
              placeholder="77.5946"
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                border: clientErrors.longitude || fieldErrors.longitude ? '1px solid var(--color-status-danger, #ef4444)' : '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--surface-control-bg, #ffffff)',
                color: 'var(--color-text-main, #0f172a)',
                fontSize: '0.9375rem',
              }}
            />
            {(clientErrors.longitude || fieldErrors.longitude) && (
              <span style={{ fontSize: '0.75rem', color: 'var(--color-status-danger, #ef4444)' }}>
                {clientErrors.longitude || fieldErrors.longitude?.[0]}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="radius" style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-sub, #475569)' }}>
              Radius in Meters <span style={{ color: 'var(--color-status-danger, #ef4444)' }}>* (Min 100m)</span>
            </label>
            <input
              id="radius"
              type="number"
              min="100"
              step="10"
              value={formData.radius ?? 100}
              onChange={(e) => setFormData({ ...formData, radius: parseFloat(e.target.value) || 0 })}
              placeholder="200"
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                border: clientErrors.radius || fieldErrors.radius ? '1px solid var(--color-status-danger, #ef4444)' : '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--surface-control-bg, #ffffff)',
                color: 'var(--color-text-main, #0f172a)',
                fontSize: '0.9375rem',
              }}
            />
            {(clientErrors.radius || fieldErrors.radius) && (
              <span style={{ fontSize: '0.75rem', color: 'var(--color-status-danger, #ef4444)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <ShieldAlert size={12} />
                {clientErrors.radius || fieldErrors.radius?.[0]}
              </span>
            )}
          </div>
        </div>
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
          Back to Details
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
          {isSubmitting ? 'Configuring Branch...' : 'Continue to Structure'}
          <ArrowRight size={18} />
        </button>
      </div>
    </form>
  );
};
