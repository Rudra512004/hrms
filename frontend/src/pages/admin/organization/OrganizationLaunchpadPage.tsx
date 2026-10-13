import React, { useMemo, useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Building2, CheckCircle2, ChevronRight, Circle, Loader2,
  ShieldCheck, Users, CalendarDays, Wifi, AlertCircle, Sparkles, ArrowRight,
} from 'lucide-react';
import { Card } from '../../../components/Card';
import { organizationService, type OrganizationSetupPayload } from '../../../services/organization';
import { onboardingService, type WizardStatusResponse } from '../../../services/onboardingService';
import { useAuth } from '../../../contexts/AuthContext';
import { useBranding } from '../../../contexts/BrandingContext';

const STAGE_NAMES: Record<number, string> = {
  1: 'Organization Details',
  2: 'Initial Branch & Location',
  3: 'Organizational Structure',
  4: 'Working Calendar & Holidays',
  5: 'Shift & Attendance Policy',
  6: 'Initial Administrator & RBAC',
  7: 'Review & Complete Launch',
};

type Tab = 'setup' | 'branding';

type SetupForm = {
  organizationName: string;
  branchName: string;
  address: string;
  latitude: string;
  longitude: string;
  radius: string;
  workDays: string[];
  gpsEnabled: boolean;
  ipEnabled: boolean;
  wfhEnabled: boolean;
  networkName: string;
  networkCidr: string;
};

const weekdayOptions = [
  ['0', 'Mon'], ['1', 'Tue'], ['2', 'Wed'], ['3', 'Thu'], ['4', 'Fri'], ['5', 'Sat'], ['6', 'Sun'],
] as const;

const initialForm: SetupForm = {
  organizationName: '', branchName: '', address: '', latitude: '', longitude: '', radius: '100',
  workDays: ['0', '1', '2', '3', '4'], gpsEnabled: true, ipEnabled: false, wfhEnabled: false,
  networkName: '', networkCidr: '',
};

const styles: Record<string, React.CSSProperties> = {
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--spacing-md)', flexWrap: 'wrap', marginBottom: 'var(--spacing-lg)' },
  title: { margin: 0, fontSize: 'var(--font-size-2xl)' },
  subtitle: { margin: 'var(--spacing-xs) 0 0', color: 'var(--color-text-sub)', maxWidth: 720 },
  grid: { display: 'grid', gridTemplateColumns: 'minmax(0, 1.6fr) minmax(280px, 0.9fr)', gap: 'var(--spacing-lg)', alignItems: 'start' },
  sectionTitle: { display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)', margin: 0, fontSize: 'var(--font-size-lg)' },
  sectionHelp: { margin: 'var(--spacing-xs) 0 var(--spacing-lg)', color: 'var(--color-text-sub)', fontSize: 'var(--font-size-sm)' },
  fieldGrid: { display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 'var(--spacing-md)' },
  field: { display: 'flex', flexDirection: 'column', gap: 6 },
  full: { gridColumn: '1 / -1' },
  label: { fontWeight: 600, fontSize: 'var(--font-size-sm)' },
  input: { width: '100%', minHeight: 40, padding: '9px 11px', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', background: 'var(--surface-control-bg)', color: 'var(--color-text-main)' },
  divider: { border: 0, borderTop: '1px solid var(--color-border-subtle)', margin: 'var(--spacing-xl) 0' },
  toggleRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--spacing-md)', padding: '10px 0', borderBottom: '1px solid var(--color-border-subtle)' },
  toggleLabel: { display: 'flex', flexDirection: 'column', gap: 2 },
  toggleHelp: { color: 'var(--color-text-muted)', fontSize: 'var(--font-size-xs)' },
  days: { display: 'flex', flexWrap: 'wrap', gap: 'var(--spacing-xs)' },
  day: { minWidth: 44, padding: '7px 8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)', background: 'var(--color-bg-card)', color: 'var(--color-text-sub)', fontSize: 'var(--font-size-xs)', fontWeight: 600 },
  daySelected: { borderColor: 'var(--color-primary)', background: 'var(--color-primary-light)', color: 'var(--color-primary-hover)' },
  primary: { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 'var(--spacing-xl)', padding: '10px 16px', border: 0, borderRadius: 'var(--radius-md)', background: 'var(--color-primary)', color: '#fff', fontWeight: 600, boxShadow: 'var(--shadow-primary)' },
  error: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 'var(--spacing-md)', padding: 12, borderRadius: 'var(--radius-md)', background: 'var(--color-status-danger-bg)', color: 'var(--color-status-danger)', border: '1px solid var(--color-status-danger-border)', fontSize: 'var(--font-size-sm)' },
  progressItem: { display: 'flex', gap: 'var(--spacing-sm)', alignItems: 'flex-start', padding: '10px 0', borderBottom: '1px solid var(--color-border-subtle)' },
  progressText: { display: 'flex', flexDirection: 'column', gap: 2 },
  progressHelp: { color: 'var(--color-text-muted)', fontSize: 'var(--font-size-xs)' },
  shortcut: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '11px 0', borderBottom: '1px solid var(--color-border-subtle)', color: 'var(--color-text-main)' },
};

export const OrganizationLaunchpadPage: React.FC = () => {
  const navigate = useNavigate();
  const { user, hasPermission, refreshAuth } = useAuth();
  const [form, setForm] = useState<SetupForm>(initialForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('setup');
  
  const [wizardStatus, setWizardStatus] = useState<WizardStatusResponse | null>(null);
  const [activating, setActivating] = useState(false);
  const [activationSuccess, setActivationSuccess] = useState(false);

  useEffect(() => {
    let isMounted = true;
    onboardingService.getStatus()
      .then(status => {
        if (isMounted) setWizardStatus(status);
      })
      .catch(() => {
        // Safe fallback if user has no onboarding session yet
      });
    return () => { isMounted = false; };
  }, []);

  const handleLaunchpadActivate = async () => {
    if (!wizardStatus?.organization_id) return;
    setActivating(true);
    setError(null);
    try {
      await onboardingService.completeWizard(wizardStatus.organization_id);
      setActivationSuccess(true);
      await refreshAuth();
      setTimeout(() => {
        navigate('/dashboard');
      }, 1200);
    } catch (err: any) {
      setError(err?.message || 'Failed to activate organization.');
    } finally {
      setActivating(false);
    }
  };

  const { branding, updateBranding } = useBranding();
  const [brandingForm, setBrandingForm] = useState<{
    logo_url: string; favicon_url: string; watermark_url: string; watermark_opacity: string;
    primary_color: string; secondary_color: string; accent_color: string; sidebar_bg_color: string; default_theme_mode: 'light' | 'dark' | 'system';
  }>({
    logo_url: '', favicon_url: '', watermark_url: '', watermark_opacity: '0.08',
    primary_color: '', secondary_color: '', accent_color: '', sidebar_bg_color: '', default_theme_mode: 'light',
  });

  useEffect(() => {
    if (branding) {
      setBrandingForm({
        logo_url: branding.logo_url || '',
        favicon_url: branding.favicon_url || '',
        watermark_url: branding.watermark_url || '',
        watermark_opacity: branding.watermark_opacity || '0.08',
        primary_color: branding.primary_color || '',
        secondary_color: branding.secondary_color || '',
        accent_color: branding.accent_color || '',
        sidebar_bg_color: branding.sidebar_bg_color || '',
        default_theme_mode: branding.default_theme_mode || 'light',
      });
    }
  }, [branding]);

  const handleBrandingSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await updateBranding(brandingForm);
      alert('Branding updated successfully');
    } catch {
      alert('Failed to update branding');
    } finally {
      setSaving(false);
    }
  };

  const canLaunch = Boolean(user?.isSuperuser || user?.canCreateOrganization || hasPermission('organization.manage'));
  const hasCompleteCoordinates = Boolean(form.latitude) === Boolean(form.longitude);
  const hasValidNetwork = !form.ipEnabled || (Boolean(form.networkName.trim()) && Boolean(form.networkCidr.trim()));
  const hasValidRadius = Number(form.radius) >= 100;
  const canSubmit = useMemo(
    () => Boolean(form.organizationName.trim() && form.branchName.trim() && form.workDays.length > 0 && hasCompleteCoordinates && hasValidNetwork && hasValidRadius),
    [form.organizationName, form.branchName, form.workDays.length, hasCompleteCoordinates, hasValidNetwork, hasValidRadius],
  );

  const update = <K extends keyof SetupForm>(key: K, value: SetupForm[K]) => setForm(current => ({ ...current, [key]: value }));
  const toggleDay = (day: string) => update('workDays', form.workDays.includes(day)
    ? form.workDays.filter(value => value !== day)
    : [...form.workDays, day].sort());

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit || !canLaunch) {
      if (!hasCompleteCoordinates) setError('Enter both latitude and longitude, or leave both blank.');
      else if (!hasValidNetwork) setError('An office-network policy needs both a network name and CIDR range.');
      else if (!hasValidRadius) setError('The geo-fence radius must be at least 100 meters.');
      else if (!form.workDays.length) setError('Choose at least one working day.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload: OrganizationSetupPayload = {
        name: form.organizationName.trim(),
        status: 'active',
        branches: [{
          name: form.branchName.trim(),
          address: form.address.trim(),
          latitude: form.latitude ? Number(form.latitude) : null,
          longitude: form.longitude ? Number(form.longitude) : null,
          radius: Number(form.radius) || 100,
          ...(form.ipEnabled && form.networkName.trim() && form.networkCidr.trim() ? {
            network: { name: form.networkName.trim(), network: form.networkCidr.trim(), is_active: true },
          } : {}),
        }],
        working_calendar: { work_days: form.workDays.join(',') },
        attendance_policy: {
          is_office_gps_enabled: form.gpsEnabled,
          is_office_ip_enabled: form.ipEnabled,
          is_wfh_enabled: form.wfhEnabled,
          wfh_bypasses_office_restrictions: true,
        },
      };
      if (user?.isSuperuser) await organizationService.createOrganizationSetup(payload);
      else await organizationService.createTenantOrganizationSetup(payload);
      await refreshAuth();
      navigate('/admin/organizations');
    } catch (requestError: any) {
      const data = requestError?.errorData;
      if (data && typeof data === 'object') {
        setError(Object.entries(data).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`).join(' | '));
      } else {
        setError('Could not create the organization. Please review the setup details and try again.');
      }
    } finally {
      setSaving(false);
    }
  };

  const configurationShortcuts = [
    ['Departments & teams', '/admin/departments', Users],
    ['Designations', '/admin/designations', Building2],
    ['Shifts', '/admin/shifts', CalendarDays],
    ['Working calendars', '/admin/working-calendar', CalendarDays],
    ['Attendance policies', '/admin/attendance-policy', ShieldCheck],
    ['Office networks', '/admin/office-networks', Wifi],
  ] as const;

  return (
    <div>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Organization Launchpad</h1>
          <p style={styles.subtitle}>Create a company and its first location in one protected transaction. Existing organization and branch screens remain available for ongoing administration.</p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <Link to="/setup" className="btn btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <Building2 size={16} /> 7-Stage Setup Wizard
          </Link>
          <Link to="/admin/organizations" className="btn btn-secondary">View organizations</Link>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 'var(--spacing-md)', marginBottom: 'var(--spacing-lg)', borderBottom: '1px solid var(--color-border-subtle)' }}>
        <button className={`tab-btn ${activeTab === 'setup' ? 'active' : ''}`} onClick={() => setActiveTab('setup')} style={{ padding: '10px 16px', background: 'none', border: 'none', borderBottom: activeTab === 'setup' ? '2px solid var(--color-primary)' : '2px solid transparent', color: activeTab === 'setup' ? 'var(--color-primary)' : 'var(--color-text-sub)', fontWeight: activeTab === 'setup' ? 600 : 400, cursor: 'pointer' }}>Initial Setup</button>
        {user?.isSuperuser && (
          <button className={`tab-btn ${activeTab === 'branding' ? 'active' : ''}`} onClick={() => setActiveTab('branding')} style={{ padding: '10px 16px', background: 'none', border: 'none', borderBottom: activeTab === 'branding' ? '2px solid var(--color-primary)' : '2px solid transparent', color: activeTab === 'branding' ? 'var(--color-primary)' : 'var(--color-text-sub)', fontWeight: activeTab === 'branding' ? 600 : 400, cursor: 'pointer' }}>Branding & Theme</button>
        )}
      </div>

      {activeTab === 'setup' && (
        <>
      {/* Live Transition & Onboarding Orchestrator Card */}
      {wizardStatus && wizardStatus.status === 'in_progress' && (
        <div style={{
          marginBottom: 'var(--spacing-xl)',
          padding: '24px',
          borderRadius: 'var(--radius-lg, 12px)',
          background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(147, 51, 234, 0.04) 100%)',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-primary, #3b82f6)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
                <Sparkles size={14} /> Onboarding In Progress • Stage {wizardStatus.current_stage}/7
              </div>
              <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-text-main, #0f172a)' }}>
                {wizardStatus.organization_name}
              </h2>
              <p style={{ margin: '4px 0 0', fontSize: '0.875rem', color: 'var(--color-text-sub, #64748b)' }}>
                Current Step: <strong>Stage {wizardStatus.current_stage}: {STAGE_NAMES[wizardStatus.current_stage] || 'Setup'}</strong>
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '1.125rem', fontWeight: 800, color: (wizardStatus.readiness_summary?.score ?? 0) >= 80 ? 'var(--color-status-success, #10b981)' : 'var(--color-status-warning, #f59e0b)' }}>
                  {wizardStatus.readiness_summary?.score ?? 0}% Ready
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #64748b)' }}>
                  Operational Readiness
                </div>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {[1, 2, 3, 4, 5, 6].map(s => {
              const isDone = (wizardStatus.completed_stages || []).includes(s);
              const isCurrent = wizardStatus.current_stage === s;
              return (
                <Link
                  key={s}
                  to={`/setup/${s}`}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    fontSize: '0.8125rem',
                    fontWeight: 600,
                    textDecoration: 'none',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: isDone ? 'rgba(16, 185, 129, 0.12)' : isCurrent ? 'rgba(59, 130, 246, 0.15)' : 'var(--surface-control-bg, #f1f5f9)',
                    color: isDone ? '#047857' : isCurrent ? '#1d4ed8' : 'var(--color-text-muted, #64748b)',
                    border: `1px solid ${isDone ? 'rgba(16, 185, 129, 0.3)' : isCurrent ? 'rgba(59, 130, 246, 0.4)' : 'var(--color-border, #e2e8f0)'}`,
                  }}
                >
                  {isDone ? <CheckCircle2 size={13} /> : <Circle size={13} />}
                  Stage {s}: {STAGE_NAMES[s]}
                </Link>
              );
            })}
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '4px' }}>
            <Link
              to={`/setup/${wizardStatus.current_stage}`}
              className="btn btn-secondary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            >
              Resume Wizard <ArrowRight size={14} />
            </Link>
            {wizardStatus.completed_stages && [1, 2, 3, 4, 5, 6].every(s => wizardStatus.completed_stages.includes(s)) && (
              <button
                type="button"
                onClick={handleLaunchpadActivate}
                disabled={activating || activationSuccess}
                className="btn btn-primary"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              >
                {activating ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                {activationSuccess ? 'Activated!' : 'Complete Setup & Launch Organization'}
              </button>
            )}
          </div>
        </div>
      )}

      {wizardStatus && wizardStatus.status === 'completed' && (
        <div style={{
          marginBottom: 'var(--spacing-xl)',
          padding: '24px',
          borderRadius: 'var(--radius-lg, 12px)',
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(59, 130, 246, 0.04) 100%)',
          border: '1px solid rgba(16, 185, 129, 0.3)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
        }}>
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-status-success, #10b981)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
              <CheckCircle2 size={14} /> Fully Activated & Operational
            </div>
            <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-text-main, #0f172a)' }}>
              {wizardStatus.organization_name}
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: '0.875rem', color: 'var(--color-text-sub, #64748b)' }}>
              Organizational readiness evaluated (100%). System is operational with active locations, working calendars, and RBAC governance.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <Link to="/admin/branding" className="btn btn-secondary">
              Theme & Branding
            </Link>
            <Link to="/dashboard" className="btn btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
              Go to HRMS Dashboard <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      )}

      {!canLaunch && (
        <div style={styles.error} role="alert"><ShieldCheck size={18} /> Verify a tenant-owner account before launching an organization. Existing organization administrators can continue using the linked configuration screens.</div>
      )}

      <div className="organization-launchpad-grid" style={styles.grid}>
        <Card>
          <form onSubmit={handleSubmit}>
            <h2 style={styles.sectionTitle}><Building2 size={20} color="var(--color-primary)" /> Start with the essentials</h2>
            <p style={styles.sectionHelp}>The first branch receives its working calendar and attendance policy automatically.</p>
            {error && <div style={styles.error} role="alert"><AlertCircle size={18} /> {error}</div>}

            <div style={styles.fieldGrid}>
              <label style={{ ...styles.field, ...styles.full }}><span style={styles.label}>Organization name</span><input style={styles.input} value={form.organizationName} onChange={e => update('organizationName', e.target.value)} placeholder="e.g. BeyondSure India Pvt. Ltd." required disabled={!canLaunch} /></label>
              <label style={{ ...styles.field, ...styles.full }}><span style={styles.label}>First branch / location</span><input style={styles.input} value={form.branchName} onChange={e => update('branchName', e.target.value)} placeholder="e.g. Bengaluru HQ" required disabled={!canLaunch} /></label>
              <label style={{ ...styles.field, ...styles.full }}><span style={styles.label}>Address <span className="text-muted">(optional)</span></span><input style={styles.input} value={form.address} onChange={e => update('address', e.target.value)} placeholder="Office address" disabled={!canLaunch} /></label>
              <label style={styles.field}><span style={styles.label}>Latitude <span className="text-muted">(optional)</span></span><input style={styles.input} inputMode="decimal" value={form.latitude} onChange={e => update('latitude', e.target.value)} placeholder="12.9716" disabled={!canLaunch} /></label>
              <label style={styles.field}><span style={styles.label}>Longitude <span className="text-muted">(optional)</span></span><input style={styles.input} inputMode="decimal" value={form.longitude} onChange={e => update('longitude', e.target.value)} placeholder="77.5946" disabled={!canLaunch} /></label>
              <label style={styles.field}><span style={styles.label}>Geo-fence radius (meters)</span><input style={styles.input} type="number" min="100" value={form.radius} onChange={e => update('radius', e.target.value)} disabled={!canLaunch} /></label>
            </div>

            <hr style={styles.divider} />
            <h2 style={styles.sectionTitle}><CalendarDays size={20} color="var(--color-primary)" /> Working schedule</h2>
            <p style={styles.sectionHelp}>Choose standard working days. Fine-grained recurring rules can be configured after launch.</p>
            <div style={styles.days}>{weekdayOptions.map(([value, label]) => <button key={value} type="button" style={{ ...styles.day, ...(form.workDays.includes(value) ? styles.daySelected : {}) }} onClick={() => toggleDay(value)} disabled={!canLaunch} aria-pressed={form.workDays.includes(value)}>{label}</button>)}</div>

            <hr style={styles.divider} />
            <h2 style={styles.sectionTitle}><ShieldCheck size={20} color="var(--color-primary)" /> Attendance policy</h2>
            <p style={styles.sectionHelp}>Choose safe defaults for this initial branch. They remain editable per branch later.</p>
            {[
              ['gpsEnabled', 'Require office GPS', 'Validate check-in against the branch geo-fence.'],
              ['ipEnabled', 'Require office IP network', 'Allow check-in only from an approved office network.'],
              ['wfhEnabled', 'Allow work-from-home requests', 'Employees can request approved remote work.'],
            ].map(([key, title, help]) => <label key={key} style={styles.toggleRow}><span style={styles.toggleLabel}><strong>{title}</strong><span style={styles.toggleHelp}>{help}</span></span><input type="checkbox" checked={Boolean(form[key as keyof SetupForm])} onChange={e => update(key as 'gpsEnabled' | 'ipEnabled' | 'wfhEnabled', e.target.checked)} disabled={!canLaunch} /></label>)}

            {form.ipEnabled && <div style={{ ...styles.fieldGrid, marginTop: 'var(--spacing-md)' }}><label style={styles.field}><span style={styles.label}>Network name</span><input style={styles.input} value={form.networkName} onChange={e => update('networkName', e.target.value)} placeholder="HQ network" disabled={!canLaunch} /></label><label style={styles.field}><span style={styles.label}>CIDR network</span><input style={styles.input} value={form.networkCidr} onChange={e => update('networkCidr', e.target.value)} placeholder="203.0.113.0/24" disabled={!canLaunch} /></label></div>}

            <button className="btn btn-primary" style={styles.primary} type="submit" disabled={!canSubmit || !canLaunch || saving}>{saving ? <Loader2 size={18} className="animate-spin" /> : <CheckCircle2 size={18} />} Create organization and first branch</button>
          </form>
        </Card>

        <div style={{ display: 'grid', gap: 'var(--spacing-lg)' }}>
          <Card title="Launch progress">
            {[
              ['Organization', 'Company record and active status'],
              ['First location', 'Branch, calendar, and attendance policy'],
              ['Structure', 'Departments, teams, and designations'],
              ['People', 'Roles, employees, and invitations'],
            ].map(([title, help], index) => <div style={styles.progressItem} key={title}>{index === 0 && form.organizationName ? <CheckCircle2 size={19} color="var(--color-status-success)" /> : <Circle size={19} color="var(--color-text-muted)" />}<span style={styles.progressText}><strong>{title}</strong><span style={styles.progressHelp}>{help}</span></span></div>)}
          </Card>
          <Card title="Continue configuration">
            {configurationShortcuts.map(([label, path, Icon]) => <Link key={path} to={path} style={styles.shortcut}><span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><Icon size={17} color="var(--color-primary)" />{label}</span><ChevronRight size={17} color="var(--color-text-muted)" /></Link>)}
          </Card>
          <Card title="What happens next">
            <p className="text-muted" style={{ fontSize: 'var(--font-size-sm)' }}>After launch, create your organization structure, assign access, configure shifts and holidays, then provision employees. Nothing is hidden or replaced—this page only makes the safe order visible.</p>
          </Card>
        </div>
      </div>
        </>
      )}

      {activeTab === 'branding' && user?.isSuperuser && (
        <Card>
          <form onSubmit={handleBrandingSubmit}>
            <h2 style={styles.sectionTitle}>Brand Configuration</h2>
            <p style={styles.sectionHelp}>Configure your organization's logo, colors, and theme.</p>
            <div style={styles.fieldGrid}>
              <label style={styles.field}><span style={styles.label}>Logo URL</span><input style={styles.input} value={brandingForm.logo_url} onChange={e => setBrandingForm(f => ({ ...f, logo_url: e.target.value }))} placeholder="https://example.com/logo.png" /></label>
              <label style={styles.field}><span style={styles.label}>Favicon URL</span><input style={styles.input} value={brandingForm.favicon_url} onChange={e => setBrandingForm(f => ({ ...f, favicon_url: e.target.value }))} placeholder="https://example.com/favicon.png" /></label>
              <label style={styles.field}><span style={styles.label}>Primary Color</span><input type="color" style={styles.input} value={brandingForm.primary_color || '#3b82f6'} onChange={e => setBrandingForm(f => ({ ...f, primary_color: e.target.value }))} /></label>
              <label style={styles.field}><span style={styles.label}>Secondary Color</span><input type="color" style={styles.input} value={brandingForm.secondary_color || '#64748b'} onChange={e => setBrandingForm(f => ({ ...f, secondary_color: e.target.value }))} /></label>
              <label style={styles.field}><span style={styles.label}>Accent Color</span><input type="color" style={styles.input} value={brandingForm.accent_color || '#f59e0b'} onChange={e => setBrandingForm(f => ({ ...f, accent_color: e.target.value }))} /></label>
              <label style={styles.field}><span style={styles.label}>Sidebar Background</span><input type="color" style={styles.input} value={brandingForm.sidebar_bg_color || '#f8fafc'} onChange={e => setBrandingForm(f => ({ ...f, sidebar_bg_color: e.target.value }))} /></label>
              <label style={styles.field}><span style={styles.label}>Watermark URL</span><input style={styles.input} value={brandingForm.watermark_url} onChange={e => setBrandingForm(f => ({ ...f, watermark_url: e.target.value }))} placeholder="Watermark image" /></label>
              <label style={styles.field}><span style={styles.label}>Watermark Opacity</span><input type="number" step="0.01" min="0" max="1" style={styles.input} value={brandingForm.watermark_opacity} onChange={e => setBrandingForm(f => ({ ...f, watermark_opacity: e.target.value }))} /></label>
              <label style={styles.field}><span style={styles.label}>Default Theme Mode</span>
                <select style={styles.input} value={brandingForm.default_theme_mode} onChange={e => setBrandingForm(f => ({ ...f, default_theme_mode: e.target.value as 'light' | 'dark' | 'system' }))}>
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                  <option value="system">System</option>
                </select>
              </label>
            </div>
            <button className="btn btn-primary" style={styles.primary} type="submit" disabled={saving}>
              {saving ? <Loader2 size={18} className="animate-spin" /> : <CheckCircle2 size={18} />} Save Branding
            </button>
          </form>
        </Card>
      )}
    </div>
  );
};
