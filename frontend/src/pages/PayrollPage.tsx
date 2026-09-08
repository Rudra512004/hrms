import React, { useState, useEffect, useCallback } from 'react';
import { DollarSign, PlusCircle, Loader2, Play, CheckCircle, FileText, Lock } from 'lucide-react';
import { Card } from '../components/Card';
import { Table } from '../components/Table';
import { StatusBadge } from '../components/StatusBadge';
import { PageHeader } from '../components/PageHeader';
import { Modal } from '../components/Modal';
import { AlertBanner } from '../components/AlertBanner';
import { EmptyState } from '../components/EmptyState';
import { useAuth } from '../contexts/AuthContext';
import {
  payrollService,
  type PayrollPeriod,
  type PayrollRecord,
  MONTH_NAMES,
  formatCurrency,
  extractApiError,
} from '../services/payroll';

// ─── Month helpers ─────────────────────────────────────────────────────────────

function getCurrentYearMonth(): { year: number; month: number } {
  const d = new Date();
  return { year: d.getFullYear(), month: d.getMonth() + 1 };
}

function monthStartEnd(year: number, month: number): { start: string; end: string } {
  const pad = (n: number) => String(n).padStart(2, '0');
  const last = new Date(year, month, 0).getDate();
  return {
    start: `${year}-${pad(month)}-01`,
    end:   `${year}-${pad(month)}-${last}`,
  };
}

// ─── Status-badge shim (draft isn't a known status) ───────────────────────────

function PeriodStatusBadge({ status }: { status: 'draft' | 'approved' }) {
  return <StatusBadge status={status} label={status === 'draft' ? 'Draft' : 'Approved'} />;
}


// ─── Create Period Modal ───────────────────────────────────────────────────────

interface CreatePeriodModalProps {
  onCreated: () => void;
  onClose: () => void;
}

function CreatePeriodModal({ onCreated, onClose }: CreatePeriodModalProps) {
  const now = getCurrentYearMonth();
  const [year, setYear] = useState(now.year);
  const [month, setMonth] = useState(now.month);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const { start, end } = monthStartEnd(year, month);
      await payrollService.createPeriod({ year, month, start_date: start, end_date: end });
      onCreated();
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setSubmitting(false);
    }
  };

  const yearOptions = Array.from({ length: 5 }, (_, i) => now.year - 2 + i);

  return (
    <Modal
      title="Create Payroll Period"
      onClose={onClose}
      size="sm"
      footer={
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={onClose} disabled={submitting} type="button">Cancel</button>
          <button className="btn btn-primary" form="create-period-form" disabled={submitting} type="submit">
            {submitting ? <Loader2 size={14} className="spin" style={{ marginRight: 6 }} /> : null}
            Create Period
          </button>
        </div>
      }
    >
      <form id="create-period-form" onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {error && <AlertBanner type="error" message={error} />}
        <div className="form-group">
          <label className="form-label">Year</label>
          <select
            className="form-input"
            value={year}
            onChange={e => setYear(Number(e.target.value))}
            required
          >
            {yearOptions.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Month</label>
          <select
            className="form-input"
            value={month}
            onChange={e => setMonth(Number(e.target.value))}
            required
          >
            {MONTH_NAMES.slice(1).map((name, i) => (
              <option key={i + 1} value={i + 1}>{name}</option>
            ))}
          </select>
        </div>
        <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
          Period: <strong>{monthStartEnd(year, month).start}</strong> → <strong>{monthStartEnd(year, month).end}</strong>
        </p>
      </form>
    </Modal>
  );
}

// ─── Records Panel ─────────────────────────────────────────────────────────────

interface RecordsPanelProps {
  period: PayrollPeriod;
  canViewSensitive: boolean;
  onClose: () => void;
}

function RecordsPanel({ period, canViewSensitive, onClose }: RecordsPanelProps) {
  const [records, setRecords] = useState<PayrollRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    payrollService.getRecords(period.id).then(data => {
      if (!cancelled) { setRecords(data); setLoading(false); }
    }).catch(err => {
      if (!cancelled) { setError(extractApiError(err)); setLoading(false); }
    });
    return () => { cancelled = true; };
  }, [period.id]);

  const columns = [
    { key: 'employee_code', title: 'Code' },
    { key: 'employee_name', title: 'Employee' },
    { key: 'working_days',  title: 'Working Days' },
    { key: 'present_days',  title: 'Present' },
    { key: 'absent_days',   title: 'Absent' },
    { key: 'leave_days',    title: 'On Leave' },
    { key: 'effective_days', title: 'Effective Days',
      render: (r: PayrollRecord) => parseFloat(r.effective_days).toFixed(1) },
    ...(canViewSensitive ? [
      { key: 'basic_salary', title: 'Basic Salary',
        render: (r: PayrollRecord) => formatCurrency(r.basic_salary) },
      { key: 'gross_salary', title: 'Gross Salary',
        render: (r: PayrollRecord) => (
          <strong style={{ color: 'var(--color-primary)' }}>{formatCurrency(r.gross_salary)}</strong>
        )},
    ] : [
      { key: 'salary_hidden', title: 'Salary',
        render: () => (
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
            <Lock size={12} /> Hidden
          </span>
        )},
    ]),
    { key: 'status', title: 'Status',
      render: (r: PayrollRecord) => <PeriodStatusBadge status={r.status} /> },
  ];

  return (
    <Modal
      title={`Payroll Records — ${MONTH_NAMES[period.month]} ${period.year}`}
      onClose={onClose}
      size="lg"
    >
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
          <Loader2 size={32} className="spin" style={{ color: 'var(--color-primary)' }} />
        </div>
      ) : error ? (
        <AlertBanner type="error" message={error} />
      ) : (
        <>
          {!canViewSensitive && (
            <AlertBanner
              type="info"
              message="Salary amounts are hidden. Contact your administrator to grant payroll.view_sensitive permission."
              style={{ marginBottom: 16 }}
            />
          )}
          <Table<PayrollRecord>
            data={records}
            columns={columns as any}
            keyExtractor={r => r.id}
            emptyTitle="No payroll records"
            emptyDescription="Generate payroll for this period to see employee records."
            emptyIcon={FileText}
          />
        </>
      )}
    </Modal>
  );
}

// ─── Main PayrollPage ──────────────────────────────────────────────────────────

export function PayrollPage() {
  const { hasPermission } = useAuth();

  const canView         = hasPermission('payroll.view');
  const canGenerate     = hasPermission('payroll.generate');
  const canApprove      = hasPermission('payroll.approve');
  const canViewSensitive = hasPermission('payroll.view_sensitive');

  const [periods, setPeriods] = useState<PayrollPeriod[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [showCreate, setShowCreate] = useState(false);
  const [viewRecordsPeriod, setViewRecordsPeriod] = useState<PayrollPeriod | null>(null);

  // Generate confirmation
  const [generateTarget, setGenerateTarget] = useState<PayrollPeriod | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  // Approve confirmation
  const [approveTarget, setApproveTarget] = useState<PayrollPeriod | null>(null);
  const [approving, setApproving] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);

  // Action feedback banner
  const [actionBanner, setActionBanner] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

  const loadPeriods = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await payrollService.getPeriods();
      setPeriods(data);
    } catch (err: unknown) {
      const e = err as any;
      if (e?.response?.status === 403) {
        setError('You do not have permission to view payroll data.');
      } else {
        setError('Failed to load payroll periods. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (canView) loadPeriods(); else setLoading(false); }, [canView, loadPeriods]);

  // Clear action banner after 5s
  useEffect(() => {
    if (!actionBanner) return;
    const t = setTimeout(() => setActionBanner(null), 5000);
    return () => clearTimeout(t);
  }, [actionBanner]);

  // ── Generate ──
  const handleGenerate = async () => {
    if (!generateTarget) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      const result = await payrollService.generatePeriod(generateTarget.id);
      setGenerateTarget(null);
      setActionBanner({ type: 'success', msg: result.detail });
      await loadPeriods();
    } catch (err) {
      setGenerateError(extractApiError(err));
    } finally {
      setGenerating(false);
    }
  };

  // ── Approve ──
  const handleApprove = async () => {
    if (!approveTarget) return;
    setApproving(true);
    setApproveError(null);
    try {
      await payrollService.approvePeriod(approveTarget.id);
      setApproveTarget(null);
      setActionBanner({ type: 'success', msg: `Payroll for ${MONTH_NAMES[approveTarget.month]} ${approveTarget.year} has been approved.` });
      await loadPeriods();
    } catch (err) {
      setApproveError(extractApiError(err));
    } finally {
      setApproving(false);
    }
  };

  // ─── Summary stat cards ────────────────────────────────────────────────────

  const totalPeriods   = periods.length;
  const draftCount     = periods.filter(p => p.status === 'draft').length;
  const approvedCount  = periods.filter(p => p.status === 'approved').length;
  const totalEmployees = periods.reduce((s, p) => s + p.record_count, 0);

  // ─── Table columns ─────────────────────────────────────────────────────────

  const columns = [
    { key: 'period', title: 'Period',
      render: (p: PayrollPeriod) => (
        <span style={{ fontWeight: 600 }}>{MONTH_NAMES[p.month]} {p.year}</span>
      )},
    { key: 'status', title: 'Status',
      render: (p: PayrollPeriod) => <PeriodStatusBadge status={p.status} /> },
    { key: 'record_count', title: 'Employees',
      render: (p: PayrollPeriod) => (
        <span style={{ color: p.record_count === 0 ? 'var(--color-text-muted)' : undefined }}>
          {p.record_count === 0 ? '—' : p.record_count}
        </span>
      )},
    { key: 'generated_at', title: 'Generated',
      render: (p: PayrollPeriod) => p.generated_at
        ? new Date(p.generated_at).toLocaleDateString('en-IN')
        : <span style={{ color: 'var(--color-text-muted)' }}>Not yet</span> },
    { key: 'approved_at', title: 'Approved',
      render: (p: PayrollPeriod) => p.approved_at
        ? new Date(p.approved_at).toLocaleDateString('en-IN')
        : <span style={{ color: 'var(--color-text-muted)' }}>—</span> },
    { key: 'actions', title: '',
      render: (p: PayrollPeriod) => (
        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          {/* View records */}
          <button
            className="btn btn-secondary"
            style={{ padding: '4px 10px', fontSize: 'var(--font-size-sm)' }}
            onClick={() => setViewRecordsPeriod(p)}
            title="View employee payroll records"
            type="button"
          >
            <FileText size={13} style={{ marginRight: 4 }} />
            Records
          </button>

          {/* Generate */}
          {canGenerate && p.status === 'draft' && (
            <button
              className="btn btn-secondary"
              style={{ padding: '4px 10px', fontSize: 'var(--font-size-sm)', color: 'var(--color-primary)' }}
              onClick={() => { setGenerateError(null); setGenerateTarget(p); }}
              title="Run payroll generation"
              type="button"
            >
              <Play size={13} style={{ marginRight: 4 }} />
              Generate
            </button>
          )}

          {/* Approve */}
          {canApprove && p.status === 'draft' && p.record_count > 0 && (
            <button
              className="btn btn-primary"
              style={{ padding: '4px 10px', fontSize: 'var(--font-size-sm)' }}
              onClick={() => { setApproveError(null); setApproveTarget(p); }}
              title="Approve and lock this payroll period"
              type="button"
            >
              <CheckCircle size={13} style={{ marginRight: 4 }} />
              Approve
            </button>
          )}

          {/* Approved lock indicator */}
          {p.status === 'approved' && (
            <span
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)',
                padding: '4px 8px',
              }}
            >
              <Lock size={13} /> Locked
            </span>
          )}
        </div>
      )},
  ];

  // ─── Render ───────────────────────────────────────────────────────────────

  if (!canView) {
    return (
      <div className="page-content">
        <PageHeader title="Payroll" subtitle="Payroll periods, generation and approval" />
        <EmptyState
          icon={Lock}
          title="Access Restricted"
          description="You do not have permission to view payroll data. Contact your administrator."
        />
      </div>
    );
  }

  return (
    <div className="page-content">
      <PageHeader
        title="Payroll"
        subtitle={`Manage payroll periods · ${totalPeriods} period${totalPeriods !== 1 ? 's' : ''}`}
        actions={
          canGenerate ? (
            <button
              className="btn btn-primary"
              onClick={() => setShowCreate(true)}
              id="payroll-create-period-btn"
              type="button"
            >
              <PlusCircle size={16} style={{ marginRight: 6 }} />
              New Period
            </button>
          ) : undefined
        }
      />

      {/* Action feedback */}
      {actionBanner && (
        <AlertBanner
          type={actionBanner.type}
          message={actionBanner.msg}
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Summary Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16, marginBottom: 24 }}>
        <StatMini label="Total Periods" value={totalPeriods} icon={<DollarSign size={20} />} />
        <StatMini label="Draft"         value={draftCount}   icon={<FileText size={20} />}  color="var(--color-warning)" />
        <StatMini label="Approved"      value={approvedCount} icon={<CheckCircle size={20} />} color="var(--color-success)" />
        <StatMini label="Total Records" value={totalEmployees} icon={<DollarSign size={20} />} color="var(--color-primary)" />
      </div>

      {/* Main table */}
      {loading ? (
        <Card>
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 64, gap: 12 }}>
            <Loader2 size={28} className="spin" style={{ color: 'var(--color-primary)' }} />
            <span style={{ color: 'var(--color-text-muted)' }}>Loading payroll periods…</span>
          </div>
        </Card>
      ) : error ? (
        <AlertBanner type="error" message={error} />
      ) : (
        <Card title="Payroll Periods" noPadding>
          <Table<PayrollPeriod>
            data={periods}
            columns={columns as any}
            keyExtractor={p => p.id}
            emptyTitle="No payroll periods"
            emptyDescription={canGenerate
              ? 'Create the first payroll period using the "New Period" button above.'
              : 'No payroll periods have been created yet.'}
            emptyIcon={DollarSign}
          />
        </Card>
      )}

      {/* ── Modals ── */}

      {showCreate && (
        <CreatePeriodModal
          onCreated={async () => { setShowCreate(false); await loadPeriods(); setActionBanner({ type: 'success', msg: 'Payroll period created successfully.' }); }}
          onClose={() => setShowCreate(false)}
        />
      )}

      {viewRecordsPeriod && (
        <RecordsPanel
          period={viewRecordsPeriod}
          canViewSensitive={canViewSensitive}
          onClose={() => setViewRecordsPeriod(null)}
        />
      )}

      {/* Generate confirmation */}
      {generateTarget && (
        <Modal
          title={`Generate Payroll — ${MONTH_NAMES[generateTarget.month]} ${generateTarget.year}`}
          onClose={() => !generating && setGenerateTarget(null)}
          size="sm"
          footer={
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={() => setGenerateTarget(null)} disabled={generating} type="button">Cancel</button>
              <button className="btn btn-primary" onClick={handleGenerate} disabled={generating} type="button">
                {generating ? <Loader2 size={14} className="spin" style={{ marginRight: 6 }} /> : <Play size={14} style={{ marginRight: 6 }} />}
                Run Generation
              </button>
            </div>
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {generateError && <AlertBanner type="error" message={generateError} />}
            <p style={{ margin: 0, color: 'var(--color-text-main)', lineHeight: 1.6 }}>
              This will compute payroll for all <strong>active employees</strong> based on their attendance, approved leave,
              and configured salary for <strong>{MONTH_NAMES[generateTarget.month]} {generateTarget.year}</strong>.
            </p>
            {generateTarget.record_count > 0 && (
              <AlertBanner type="warning" message="This period already has records. Re-generating will replace all draft records." />
            )}
          </div>
        </Modal>
      )}

      {/* Approve confirmation */}
      {approveTarget && (
        <Modal
          title={`Approve Payroll — ${MONTH_NAMES[approveTarget.month]} ${approveTarget.year}`}
          onClose={() => !approving && setApproveTarget(null)}
          size="sm"
          footer={
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={() => setApproveTarget(null)} disabled={approving} type="button">Cancel</button>
              <button className="btn btn-primary" onClick={handleApprove} disabled={approving} type="button">
                {approving ? <Loader2 size={14} className="spin" style={{ marginRight: 6 }} /> : <CheckCircle size={14} style={{ marginRight: 6 }} />}
                Approve & Lock
              </button>
            </div>
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {approveError && <AlertBanner type="error" message={approveError} />}
            <p style={{ margin: 0, color: 'var(--color-text-main)', lineHeight: 1.6 }}>
              Approving will <strong>lock</strong> the payroll for{' '}
              <strong>{MONTH_NAMES[approveTarget.month]} {approveTarget.year}</strong> ({approveTarget.record_count} employee record{approveTarget.record_count !== 1 ? 's' : ''}).
              This action cannot be undone.
            </p>
            <AlertBanner type="warning" message="Once approved, payroll records cannot be modified or re-generated." />
          </div>
        </Modal>
      )}
    </div>
  );
}

// ─── Tiny stat card ────────────────────────────────────────────────────────────

function StatMini({ label, value, icon, color }: { label: string; value: number; icon: React.ReactNode; color?: string }) {
  const accentColor = color ?? 'var(--color-primary)';
  const iconBg = `color-mix(in srgb, ${accentColor} 14%, transparent)`;

  return (
    <div
      className="card"
      style={{
        padding: '18px 20px',
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        borderTop: `3px solid ${accentColor}`,
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 'var(--radius-md)',
          background: iconBg,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: accentColor,
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--color-text-main)', lineHeight: 1.1, fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.02em' }}>
          {value}
        </div>
        <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: 4, fontWeight: 500 }}>
          {label}
        </div>
      </div>
    </div>
  );
}
