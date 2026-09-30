import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, CheckCircle2, ChevronRight, CircleDashed, Loader2, Settings2, ShieldCheck } from 'lucide-react';
import { Card } from '../../components/Card';
import { organizationService, type Organization, type OrganizationReadiness } from '../../services/organization';

const styles: Record<string, React.CSSProperties> = {
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--spacing-md)', marginBottom: 'var(--spacing-lg)' },
  title: { display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)', margin: 0, fontSize: 'var(--font-size-2xl)' },
  subtitle: { margin: 'var(--spacing-xs) 0 0', color: 'var(--color-text-sub)' },
  select: { minWidth: 240, minHeight: 40, padding: '8px 11px', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', background: 'var(--surface-control-bg)', color: 'var(--color-text-main)' },
  score: { display: 'flex', alignItems: 'center', gap: 'var(--spacing-lg)', padding: 'var(--spacing-xs) 0' },
  scoreNumber: { width: 86, height: 86, display: 'grid', placeItems: 'center', borderRadius: '50%', background: 'var(--color-primary-light)', color: 'var(--color-primary-hover)', border: '6px solid var(--color-primary-border)', fontSize: 'var(--font-size-xl)', fontWeight: 700 },
  check: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--spacing-md)', padding: '14px 0', borderBottom: '1px solid var(--color-border-subtle)' },
  checkContent: { display: 'flex', alignItems: 'flex-start', gap: 'var(--spacing-sm)' },
  checkText: { display: 'flex', flexDirection: 'column', gap: 2 },
  detail: { color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' },
  state: { fontSize: 'var(--font-size-xs)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' },
  error: { display: 'flex', gap: 8, alignItems: 'center', padding: 12, border: '1px solid var(--color-status-danger-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-status-danger)', background: 'var(--color-status-danger-bg)' },
};

const StateIcon: React.FC<{ state: string }> = ({ state }) => {
  if (state === 'ready') return <CheckCircle2 size={20} color="var(--color-status-success)" />;
  if (state === 'recommended') return <CircleDashed size={20} color="var(--color-status-warning)" />;
  return <AlertCircle size={20} color="var(--color-status-danger)" />;
};

export const OrganizationControlCenterPage: React.FC = () => {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [readiness, setReadiness] = useState<OrganizationReadiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    organizationService.listOrganizations()
      .then(data => {
        const values = Array.isArray(data) ? data : [];
        setOrganizations(values);
        setSelectedId(values[0]?.id ?? null);
      })
      .catch(() => setError('Unable to load organizations.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) { setReadiness(null); return; }
    setLoading(true);
    setError(null);
    organizationService.getOrganizationReadiness(selectedId)
      .then(setReadiness)
      .catch(() => setError('Unable to load this organization’s readiness assessment.'))
      .finally(() => setLoading(false));
  }, [selectedId]);

  return <div>
    <div style={styles.header}>
      <div>
        <h1 style={styles.title}><Settings2 size={25} color="var(--color-primary)" /> Organization Control Center</h1>
        <p style={styles.subtitle}>Review operational readiness, then move directly to the configuration that needs attention.</p>
      </div>
      {organizations.length > 0 && <select style={styles.select} value={selectedId ?? ''} onChange={event => setSelectedId(Number(event.target.value))} aria-label="Organization"><option value="" disabled>Select organization</option>{organizations.map(org => <option key={org.id} value={org.id}>{org.name}</option>)}</select>}
    </div>

    {error && <div style={styles.error} role="alert"><AlertCircle size={18} /> {error}</div>}
    {loading && !readiness && !error && <Card><div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--spacing-xl)' }}><Loader2 size={28} className="animate-spin" color="var(--color-primary)" /></div></Card>}
    {!loading && !error && !selectedId && <Card><div className="text-muted" style={{ padding: 'var(--spacing-lg)', textAlign: 'center' }}>No organizations are available in your current access scope.</div></Card>}
    {readiness && <div className="organization-control-grid" style={{ display: 'grid', gridTemplateColumns: 'minmax(250px, 0.75fr) minmax(0, 1.75fr)', gap: 'var(--spacing-lg)', alignItems: 'start' }}>
      <Card title="Operational readiness">
        <div style={styles.score}><div style={styles.scoreNumber}>{readiness.score}%</div><div><strong>{readiness.organization_name}</strong><p className="text-muted" style={{ marginTop: 4, fontSize: 'var(--font-size-sm)' }}>Required setup completion</p></div></div>
        <div style={{ marginTop: 'var(--spacing-lg)', padding: 'var(--spacing-md)', borderRadius: 'var(--radius-md)', background: 'var(--color-bg-secondary)', fontSize: 'var(--font-size-sm)', color: 'var(--color-text-sub)' }}><ShieldCheck size={17} color="var(--color-primary)" style={{ verticalAlign: 'middle', marginRight: 6 }} />This is advisory. It never changes your configuration or blocks existing workflows.</div>
      </Card>
      <Card title="Configuration checks">
        {readiness.checks.map(check => <div key={check.key} style={styles.check}>
          <div style={styles.checkContent}><StateIcon state={check.state} /><span style={styles.checkText}><strong>{check.label}</strong><span style={styles.detail}>{check.detail}</span></span></div>
          <Link to={check.path} className="btn btn-secondary btn-sm" style={{ flexShrink: 0 }}>{check.state === 'ready' ? 'Review' : 'Configure'} <ChevronRight size={15} /></Link>
        </div>)}
      </Card>
    </div>}
  </div>;
};
