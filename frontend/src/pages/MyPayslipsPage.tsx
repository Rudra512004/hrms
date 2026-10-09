import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  FileText,
  Eye,
  Download,
  Printer,
  Loader2,
  Calendar,
  User,
  Briefcase,
  ShieldCheck,
  CreditCard,
  Building2,
  Receipt,
  Info,
} from 'lucide-react';
import { Card } from '../components/Card';
import { Table } from '../components/Table';
import { StatusBadge } from '../components/StatusBadge';
import { PageHeader } from '../components/PageHeader';
import { Modal } from '../components/Modal';
import { AlertBanner } from '../components/AlertBanner';
import { EmptyState } from '../components/EmptyState';
import { EmployeeTaxDeclarationView } from '../components/tax/EmployeeTaxDeclarationView';
import {
  payrollService,
  type PayslipSummary,
  type PayslipDetail,
  type FinalSettlement,
  formatCurrency,
  extractApiError,
} from '../services/payroll';

export const MyPayslipsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'payslips' | 'tax' | 'fnf'>('payslips');

  // Payslip List State
  const [payslips, setPayslips] = useState<PayslipSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedYear, setSelectedYear] = useState<string>('all');
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Detail Modal State
  const [selectedPayslipId, setSelectedPayslipId] = useState<number | null>(null);
  const [detail, setDetail] = useState<PayslipDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // FnF Settlements State
  const [settlements, setSettlements] = useState<FinalSettlement[]>([]);
  const [fnfLoading, setFnfLoading] = useState(false);
  const [fnfNotice, setFnfNotice] = useState<string | null>(null);

  // Fetch Payslips
  const fetchPayslips = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await payrollService.getMyPayslips();
      setPayslips(data || []);
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch FnF Settlements
  const fetchSettlements = useCallback(async () => {
    setFnfLoading(true);
    setFnfNotice(null);
    try {
      const data = await payrollService.getFinalSettlements();
      setSettlements(data || []);
    } catch (err: any) {
      // If 403 Forbidden, employee does not have admin fnf permission
      if (err?.response?.status === 403 || err?.errorData?.detail?.includes('Permission denied')) {
        setFnfNotice('Full & Final Settlement records are restricted to HR/Payroll Operations administrators. Standard employee self-service FnF visibility requires administrative permission or completed separation workflow.');
      } else {
        setFnfNotice(extractApiError(err));
      }
    } finally {
      setFnfLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPayslips();
  }, [fetchPayslips]);

  useEffect(() => {
    if (activeTab === 'fnf') {
      fetchSettlements();
    }
  }, [activeTab, fetchSettlements]);

  // Open Payslip Detail
  const handleOpenDetail = async (id: number) => {
    setSelectedPayslipId(id);
    setDetail(null);
    setDetailLoading(true);
    setDetailError(null);
    try {
      const data = await payrollService.getPayslipDetail(id);
      setDetail(data);
    } catch (err) {
      setDetailError(extractApiError(err));
    } finally {
      setDetailLoading(false);
    }
  };

  const handleCloseDetail = () => {
    setSelectedPayslipId(null);
    setDetail(null);
    setDetailError(null);
  };

  // PDF Download Action
  const handleDownloadPdf = async (id: number) => {
    setDownloadingId(id);
    setActionError(null);
    try {
      const { blob, filename } = await payrollService.downloadPayslipPdf(id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setActionError(extractApiError(err));
    } finally {
      setDownloadingId(null);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  // Filtered Payslips by Year
  const availableYears = useMemo(() => {
    const years = new Set<number>();
    payslips.forEach((p) => {
      if (p.year) years.add(p.year);
    });
    return Array.from(years).sort((a, b) => b - a);
  }, [payslips]);

  const filteredPayslips = useMemo(() => {
    if (selectedYear === 'all') return payslips;
    return payslips.filter((p) => String(p.year) === selectedYear);
  }, [payslips, selectedYear]);

  // Tax and Deductions Aggregations (from authoritative payslips)
  const taxMetrics = useMemo(() => {
    let ytdTds = 0;
    let ytdEpf = 0;
    let ytdEsic = 0;
    let ytdPt = 0;
    let ytdGross = 0;
    let ytdNet = 0;

    payslips.forEach((p) => {
      if (p.gross_earnings) ytdGross += parseFloat(p.gross_earnings) || 0;
      if (p.net_pay || p.net_salary) ytdNet += parseFloat(p.net_pay || p.net_salary) || 0;
    });

    return {
      ytdTds,
      ytdEpf,
      ytdEsic,
      ytdPt,
      ytdGross,
      ytdNet,
    };
  }, [payslips]);

  // Columns for My Payslips Table
  const columns = [
    {
      key: 'period_label',
      title: 'Pay Period',
      render: (p: PayslipSummary) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              padding: '6px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--color-bg-body)',
              color: 'var(--color-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Calendar size={16} />
          </div>
          <div>
            <div style={{ fontWeight: 600, color: 'var(--color-text-main)' }}>
              {p.period_label}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
              {p.start_date} to {p.end_date}
            </div>
          </div>
        </div>
      ),
    },
    {
      key: 'payslip_number',
      title: 'Payslip Number',
      render: (p: PayslipSummary) => (
        <code
          style={{
            fontSize: '0.85rem',
            padding: '2px 6px',
            borderRadius: '4px',
            backgroundColor: 'var(--color-bg-body)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-primary)',
            fontFamily: 'monospace',
          }}
        >
          {p.payslip_number}
        </code>
      ),
    },
    {
      key: 'gross_earnings',
      title: 'Gross Earnings',
      render: (p: PayslipSummary) => (
        <span style={{ fontWeight: 500, color: 'var(--color-text-main)' }}>
          {formatCurrency(p.gross_earnings)}
        </span>
      ),
    },
    {
      key: 'total_deductions',
      title: 'Total Deductions',
      render: (p: PayslipSummary) => (
        <span style={{ fontWeight: 500, color: 'var(--color-text-muted)' }}>
          {formatCurrency(p.total_deductions)}
        </span>
      ),
    },
    {
      key: 'net_pay',
      title: 'Net Take-Home',
      render: (p: PayslipSummary) => (
        <span
          style={{
            fontWeight: 700,
            color: 'var(--color-status-success)',
            fontSize: '0.95rem',
          }}
        >
          {formatCurrency(p.net_pay || p.net_salary)}
        </span>
      ),
    },
    {
      key: 'issued_at',
      title: 'Issued Date',
      render: (p: PayslipSummary) => (
        <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
          {p.issued_at ? new Date(p.issued_at).toLocaleDateString() : '—'}
        </span>
      ),
    },
    {
      key: 'status',
      title: 'Status',
      render: (p: PayslipSummary) => (
        <StatusBadge
          status={p.status === 'issued' ? 'present' : 'absent'}
          label={p.status === 'issued' ? 'Issued' : 'Revoked'}
        />
      ),
    },
    {
      key: 'actions',
      title: 'Actions',
      render: (p: PayslipSummary) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button
            className="btn btn-ghost"
            style={{ padding: '6px 10px', fontSize: '0.85rem' }}
            onClick={() => handleOpenDetail(p.id)}
            title="View Payslip Breakdown"
          >
            <Eye size={15} style={{ marginRight: 4 }} /> View
          </button>
          <button
            className="btn btn-secondary"
            style={{ padding: '6px 10px', fontSize: '0.85rem' }}
            onClick={() => handleDownloadPdf(p.id)}
            disabled={downloadingId === p.id}
            title="Download Authoritative PDF"
          >
            {downloadingId === p.id ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Download size={15} />
            )}
            <span style={{ marginLeft: 4 }}>PDF</span>
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="page-container" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      <PageHeader
        title="Employee Payroll Portal"
        subtitle="Access your authoritative monthly earnings, statutory deductions, tax records, and official payslips."
      />

      {error && <AlertBanner type="error" message={error} />}
      {actionError && <AlertBanner type="error" message={actionError} />}

      {/* Tabs Navigation */}
      <div
        style={{
          display: 'flex',
          gap: 'var(--spacing-sm)',
          borderBottom: '1px solid var(--color-border)',
          paddingBottom: 'var(--spacing-xs)',
        }}
      >
        <button
          className={`btn ${activeTab === 'payslips' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setActiveTab('payslips')}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <FileText size={16} /> My Payslips
        </button>
        <button
          className={`btn ${activeTab === 'tax' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setActiveTab('tax')}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <Receipt size={16} /> Income Tax & Deductions
        </button>
        <button
          className={`btn ${activeTab === 'fnf' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setActiveTab('fnf')}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <ShieldCheck size={16} /> Full & Final Settlement
        </button>
      </div>

      {/* ─────────────────── TAB 1: MY PAYSLIPS ─────────────────── */}
      {activeTab === 'payslips' && (
        <>
          {/* Executive KPI Summary Cards */}
          {payslips.length > 0 && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: 'var(--spacing-md)',
              }}
            >
              <div
                className="card"
                style={{
                  padding: '16px 20px',
                  borderTop: '3px solid var(--color-primary)',
                  boxShadow: 'var(--shadow-sm)',
                }}
              >
                <div
                  style={{
                    fontSize: 'var(--font-size-xs)',
                    color: 'var(--color-text-muted)',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                  }}
                >
                  Latest Pay Period
                </div>
                <div
                  style={{
                    fontSize: '1.4rem',
                    fontWeight: 700,
                    color: 'var(--color-text-main)',
                    marginTop: 4,
                  }}
                >
                  {payslips[0]?.period_label}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
                  Issued on {payslips[0]?.issued_at ? new Date(payslips[0].issued_at).toLocaleDateString() : '—'}
                </div>
              </div>

              <div
                className="card"
                style={{
                  padding: '16px 20px',
                  borderTop: '3px solid var(--color-status-success)',
                  boxShadow: 'var(--shadow-sm)',
                }}
              >
                <div
                  style={{
                    fontSize: 'var(--font-size-xs)',
                    color: 'var(--color-text-muted)',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                  }}
                >
                  Latest Take-Home Pay
                </div>
                <div
                  style={{
                    fontSize: '1.4rem',
                    fontWeight: 800,
                    color: 'var(--color-status-success)',
                    marginTop: 4,
                  }}
                >
                  {formatCurrency(payslips[0]?.net_pay || payslips[0]?.net_salary)}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
                  Gross: {formatCurrency(payslips[0]?.gross_earnings)}
                </div>
              </div>

              <div
                className="card"
                style={{
                  padding: '16px 20px',
                  borderTop: '3px solid var(--color-secondary)',
                  boxShadow: 'var(--shadow-sm)',
                }}
              >
                <div
                  style={{
                    fontSize: 'var(--font-size-xs)',
                    color: 'var(--color-text-muted)',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                  }}
                >
                  Total Issued Payslips
                </div>
                <div
                  style={{
                    fontSize: '1.4rem',
                    fontWeight: 700,
                    color: 'var(--color-text-main)',
                    marginTop: 4,
                  }}
                >
                  {payslips.length} document{payslips.length !== 1 ? 's' : ''}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
                  Authoritative finalized records
                </div>
              </div>
            </div>
          )}

          {/* Payslips Table Card */}
          <Card
            title="Issued Payslip History"
            actions={
              availableYears.length > 1 ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>Year:</span>
                  <select
                    className="form-control"
                    style={{ padding: '4px 8px', fontSize: '0.85rem', width: 'auto' }}
                    value={selectedYear}
                    onChange={(e) => setSelectedYear(e.target.value)}
                  >
                    <option value="all">All Years</option>
                    {availableYears.map((yr) => (
                      <option key={yr} value={String(yr)}>
                        {yr}
                      </option>
                    ))}
                  </select>
                </div>
              ) : undefined
            }
            noPadding
          >
            {loading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--spacing-2xl)' }}>
                <Loader2 className="animate-spin" size={32} color="var(--color-primary)" />
              </div>
            ) : filteredPayslips.length === 0 ? (
              <EmptyState
                title="No Issued Payslips"
                description={
                  payslips.length === 0
                    ? "You don't have any finalized payslips yet. Payslips appear here once HR approves and issues the monthly payroll run."
                    : 'No payslips match the selected filter.'
                }
                icon={FileText}
              />
            ) : (
              <Table data={filteredPayslips} columns={columns} keyExtractor={(p) => p.id} />
            )}
          </Card>
        </>
      )}

      {/* ─────────────────── TAB 2: INCOME TAX & STATUTORY ─────────────────── */}
      {activeTab === 'tax' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
          {/* Statutory and Tax Regime Overview */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: 'var(--spacing-md)',
            }}
          >
            <Card title="Active Tax Regime" noPadding>
              <div style={{ padding: '16px 20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <StatusBadge status="approved" label="New Tax Regime (Default)" />
                </div>
                <p style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', margin: 0 }}>
                  Standard statutory slab under Section 115BAC applies by default. Income tax calculations are executed
                  server-side based on verified compensation and statutory declarations.
                </p>
              </div>
            </Card>

            <Card title="YTD Earnings & Deductions" noPadding>
              <div style={{ padding: '16px 20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>Cumulative Gross Earnings:</span>
                  <span style={{ fontWeight: 600 }}>{formatCurrency(String(taxMetrics.ytdGross))}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>Cumulative Net Take-Home:</span>
                  <span style={{ fontWeight: 700, color: 'var(--color-status-success)' }}>
                    {formatCurrency(String(taxMetrics.ytdNet))}
                  </span>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', borderTop: '1px solid var(--color-border)', paddingTop: '6px' }}>
                  Aggregated from {payslips.length} finalized issued payslips
                </div>
              </div>
            </Card>
          </div>

          {/* Backend Contract Gap Notice for Tax Declarations */}
          <div
            className="card"
            style={{
              padding: '20px',
              backgroundColor: 'var(--color-bg-body)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
              <div style={{ color: 'var(--color-primary)', marginTop: '2px' }}>
                <Info size={22} />
              </div>
              <div style={{ flex: 1 }}>
                <h4 style={{ margin: '0 0 6px 0', fontSize: '1rem', color: 'var(--color-text-main)' }}>
                  Tax Declaration & Proof Verification Notice
                </h4>
                <p style={{ margin: '0 0 10px 0', fontSize: '0.875rem', color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
                  Annual tax declarations (Form 12BB), investment proofs (Section 80C, 80D, HRA receipts), and employee
                  regime-switching workflows are powered by the authoritative backend payroll tax engine.
                </p>
                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', lineHeight: 1.4 }}>
                  <strong>Authoritative Principle:</strong> The frontend does not fabricate or simulate client-side tax
                  estimations. All current income tax (TDS) and statutory deductions (EPF, ESIC, PT) are calculated
                  exclusively by the backend payroll engine and displayed in your finalized monthly payslips.
                </div>
              </div>
            </div>
          </div>

          {/* ─── P6.9B Authoritative Tax Declarations & Proofs View ─── */}
          <EmployeeTaxDeclarationView />
        </div>
      )}


      {/* ─────────────────── TAB 3: FULL & FINAL SETTLEMENT (FnF) ─────────────────── */}
      {activeTab === 'fnf' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
          {fnfLoading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--spacing-2xl)' }}>
              <Loader2 className="animate-spin" size={32} color="var(--color-primary)" />
            </div>
          ) : settlements.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
              {settlements.map((st) => (
                <Card
                  key={st.id}
                  title={`Settlement ${st.settlement_number} (${st.status.toUpperCase()})`}
                  noPadding
                >
                  <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                        gap: '12px',
                        padding: '12px',
                        backgroundColor: 'var(--color-bg-body)',
                        borderRadius: 'var(--radius-sm)',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Exit Date (LWD)</div>
                        <div style={{ fontWeight: 600 }}>{st.exit_date}</div>
                      </div>
                      <div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Total Earnings</div>
                        <div style={{ fontWeight: 600 }}>{formatCurrency(st.total_earnings)}</div>
                      </div>
                      <div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Total Deductions</div>
                        <div style={{ fontWeight: 600, color: 'var(--color-text-muted)' }}>
                          {formatCurrency(st.total_deductions)}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Total Recoveries</div>
                        <div style={{ fontWeight: 600, color: 'var(--color-status-danger)' }}>
                          {formatCurrency(st.total_recoveries)}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Net Payable</div>
                        <div style={{ fontWeight: 800, color: 'var(--color-status-success)', fontSize: '1.1rem' }}>
                          {formatCurrency(st.net_settlement_amount)}
                        </div>
                      </div>
                    </div>

                    {st.integrity_hash && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                        Integrity Hash: {st.integrity_hash}
                      </div>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <div
              className="card"
              style={{
                padding: '24px',
                backgroundColor: 'var(--color-bg-body)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-md)',
                textAlign: 'center',
              }}
            >
              <div style={{ color: 'var(--color-primary)', marginBottom: '12px' }}>
                <ShieldCheck size={36} style={{ margin: '0 auto' }} />
              </div>
              <h3 style={{ margin: '0 0 8px 0', fontSize: '1.1rem', color: 'var(--color-text-main)' }}>
                Full & Final Settlement (FnF)
              </h3>
              <p
                style={{
                  margin: '0 auto 16px auto',
                  maxWidth: '560px',
                  fontSize: '0.875rem',
                  color: 'var(--color-text-secondary)',
                  lineHeight: 1.5,
                }}
              >
                {fnfNotice ||
                  'No separation records found. Full & Final Settlement (FnF) statements are generated exclusively upon formal employee resignation or departure. Once finalized and approved by Finance, official settlement statements will be published here.'}
              </p>
              <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                Protected by Organization Isolation & Immutable Finalization (Phase 6.7)
              </div>
            </div>
          )}
        </div>
      )}

      {/* ─────────────────── PAYSLIP DETAIL MODAL ─────────────────── */}
      {selectedPayslipId !== null && (
        <Modal
          onClose={handleCloseDetail}
          title={detail ? `Payslip — ${detail.period_label}` : 'Payslip Details'}
          size="lg"
        >
          {detailLoading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--spacing-2xl)' }}>
              <Loader2 className="animate-spin" size={32} color="var(--color-primary)" />
            </div>
          ) : detailError ? (
            <AlertBanner type="error" message={detailError} />
          ) : detail ? (
            <div
              className="payslip-modal-content"
              style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}
            >
              {/* Official Corporate Header */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  padding: 'var(--spacing-md)',
                  backgroundColor: 'var(--color-bg-body)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--color-border)',
                  flexWrap: 'wrap',
                  gap: '12px',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Building2 size={16} color="var(--color-primary)" />
                    <span style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--color-text-main)' }}>
                      {detail.organization.legal_name || detail.organization.name}
                    </span>
                  </div>
                  {detail.organization.address && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
                      {detail.organization.address}
                    </div>
                  )}
                  {detail.organization.cin && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                      CIN: {detail.organization.cin}
                    </div>
                  )}
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
                    Payslip Number
                  </div>
                  <code style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--color-primary)', fontFamily: 'monospace' }}>
                    {detail.payslip_number}
                  </code>
                  <div style={{ marginTop: 4 }}>
                    <StatusBadge status="present" label="Official / Finalized" />
                  </div>
                </div>
              </div>

              {/* Employee & Payroll Information Grid */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: 'var(--spacing-md)',
                  padding: 'var(--spacing-md)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <User size={13} /> Employee Details
                  </div>
                  <div style={{ fontWeight: 600, color: 'var(--color-text-main)', marginTop: 2 }}>{detail.employee.name}</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>ID: {detail.employee.code}</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>{detail.employee.email}</div>
                  {detail.employee.joining_date && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
                      Joined: {detail.employee.joining_date}
                    </div>
                  )}
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Briefcase size={13} /> Department & Role
                  </div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-main)', marginTop: 2 }}>
                    <strong>Dept:</strong> {detail.employee.department || '—'}
                  </div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-main)' }}>
                    <strong>Role:</strong> {detail.employee.designation || '—'}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <CreditCard size={13} /> Payment & Statutory
                  </div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-main)', marginTop: 2 }}>
                    <strong>Bank:</strong> {detail.employee.bank_name || 'Bank Transfer'}
                  </div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-main)' }}>
                    <strong>A/C:</strong> {detail.employee.masked_bank_account || '••••••••'}
                  </div>
                  {detail.employee.bank_ifsc && (
                    <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                      IFSC: {detail.employee.bank_ifsc}
                    </div>
                  )}
                  {detail.employee.masked_pan && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                      PAN: {detail.employee.masked_pan}
                    </div>
                  )}
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Calendar size={13} /> Pay Period
                  </div>
                  <div style={{ fontWeight: 600, color: 'var(--color-text-main)', marginTop: 2 }}>{detail.period.label}</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                    {detail.period.start_date} to {detail.period.end_date}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
                    Issued: {new Date(detail.issued_at).toLocaleDateString()}
                  </div>
                </div>
              </div>

              {/* Attendance Breakdown Strip */}
              <div>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-main)', marginBottom: '6px' }}>
                  Attendance Summary
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(90px, 1fr))',
                    gap: 'var(--spacing-xs)',
                    textAlign: 'center',
                  }}
                >
                  <div style={{ padding: '6px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>Working Days</div>
                    <div style={{ fontWeight: 700, fontSize: '1rem' }}>{detail.attendance.working_days}</div>
                  </div>
                  <div style={{ padding: '6px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>Present</div>
                    <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--color-status-success)' }}>
                      {detail.attendance.present_days}
                    </div>
                  </div>
                  <div style={{ padding: '6px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>Half Days</div>
                    <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--color-status-warning)' }}>
                      {detail.attendance.half_days}
                    </div>
                  </div>
                  <div style={{ padding: '6px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>Paid Leave</div>
                    <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--color-primary)' }}>
                      {detail.attendance.leave_days}
                    </div>
                  </div>
                  <div style={{ padding: '6px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>Absent / LOP</div>
                    <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--color-status-danger)' }}>
                      {detail.attendance.absent_days || detail.attendance.lop_days || 0}
                    </div>
                  </div>
                  <div
                    style={{
                      padding: '6px',
                      backgroundColor: 'var(--color-bg-body)',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--color-primary)',
                    }}
                  >
                    <div style={{ fontSize: '0.7rem', color: 'var(--color-primary)', fontWeight: 600 }}>Paid Days</div>
                    <div style={{ fontWeight: 800, fontSize: '1rem', color: 'var(--color-primary)' }}>
                      {detail.attendance.effective_days}
                    </div>
                  </div>
                </div>
              </div>

              {/* Side-by-Side Itemized Earnings and Deductions */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                  gap: 'var(--spacing-md)',
                }}
              >
                {/* Earnings Column */}
                <div style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
                  <div
                    style={{
                      padding: '10px 14px',
                      backgroundColor: 'var(--color-bg-body)',
                      borderBottom: '1px solid var(--color-border)',
                      fontWeight: 600,
                      fontSize: '0.9rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                    }}
                  >
                    <span>Earnings</span>
                    <span>Amount</span>
                  </div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                    <tbody>
                      {detail.lines && detail.lines.filter((l) => l.category === 'earning').length > 0 ? (
                        detail.lines
                          .filter((l) => l.category === 'earning')
                          .map((l) => (
                            <tr key={l.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                              <td style={{ padding: '8px 14px', color: 'var(--color-text-main)' }}>
                                {l.name}
                                <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginLeft: 6 }}>
                                  ({l.component_code})
                                </span>
                              </td>
                              <td style={{ padding: '8px 14px', textAlign: 'right', fontWeight: 500 }}>
                                {formatCurrency(l.amount)}
                              </td>
                            </tr>
                          ))
                      ) : (
                        <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                          <td style={{ padding: '8px 14px', color: 'var(--color-text-main)' }}>Basic Salary</td>
                          <td style={{ padding: '8px 14px', textAlign: 'right', fontWeight: 500 }}>
                            {formatCurrency(detail.financials.basic_salary ?? undefined)}
                          </td>
                        </tr>
                      )}
                    </tbody>
                    <tfoot>
                      <tr style={{ backgroundColor: 'var(--color-bg-body)', fontWeight: 700 }}>
                        <td style={{ padding: '10px 14px' }}>Gross Earnings</td>
                        <td style={{ padding: '10px 14px', textAlign: 'right', color: 'var(--color-text-main)' }}>
                          {formatCurrency(detail.financials.gross_salary ?? undefined)}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>

                {/* Deductions Column */}
                <div style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
                  <div
                    style={{
                      padding: '10px 14px',
                      backgroundColor: 'var(--color-bg-body)',
                      borderBottom: '1px solid var(--color-border)',
                      fontWeight: 600,
                      fontSize: '0.9rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                    }}
                  >
                    <span>Deductions</span>
                    <span>Amount</span>
                  </div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                    <tbody>
                      {detail.lines && detail.lines.filter((l) => l.category === 'deduction').length > 0 ? (
                        detail.lines
                          .filter((l) => l.category === 'deduction')
                          .map((l) => (
                            <tr key={l.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                              <td style={{ padding: '8px 14px', color: 'var(--color-text-muted)' }}>
                                {l.name}
                                <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginLeft: 6 }}>
                                  ({l.component_code})
                                </span>
                              </td>
                              <td style={{ padding: '8px 14px', textAlign: 'right', color: 'var(--color-text-muted)' }}>
                                {formatCurrency(l.amount)}
                              </td>
                            </tr>
                          ))
                      ) : (
                        <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                          <td style={{ padding: '8px 14px', color: 'var(--color-text-muted)' }}>Statutory Deductions</td>
                          <td style={{ padding: '8px 14px', textAlign: 'right', color: 'var(--color-text-muted)' }}>
                            {formatCurrency(detail.financials.deductions ?? undefined)}
                          </td>
                        </tr>
                      )}
                    </tbody>
                    <tfoot>
                      <tr style={{ backgroundColor: 'var(--color-bg-body)', fontWeight: 700 }}>
                        <td style={{ padding: '10px 14px' }}>Total Deductions</td>
                        <td style={{ padding: '10px 14px', textAlign: 'right', color: 'var(--color-text-muted)' }}>
                          {formatCurrency(detail.financials.deductions ?? undefined)}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>

              {/* Net Payable Highlight Banner */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '14px 20px',
                  backgroundColor: 'var(--color-bg-body)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-md)',
                  flexWrap: 'wrap',
                  gap: '8px',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
                    Net Salary Payable
                  </div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--color-status-success)' }}>
                    {formatCurrency(detail.financials.net_salary ?? undefined)}
                  </div>
                  {detail.net_pay_in_words && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
                      {detail.net_pay_in_words}
                    </div>
                  )}
                </div>

                {detail.integrity_hash && (
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'flex-end' }}>
                      <ShieldCheck size={14} color="var(--color-status-success)" /> Immutable Verification
                    </div>
                    <code style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                      {detail.integrity_hash.slice(0, 16)}...
                    </code>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--spacing-sm)', marginTop: '4px' }}>
                <button className="btn btn-secondary" onClick={handlePrint}>
                  <Printer size={16} style={{ marginRight: 6 }} /> Print
                </button>
                <button
                  className="btn btn-primary"
                  onClick={() => handleDownloadPdf(detail.id)}
                  disabled={downloadingId === detail.id}
                >
                  {downloadingId === detail.id ? (
                    <Loader2 size={16} className="animate-spin" style={{ marginRight: 6 }} />
                  ) : (
                    <Download size={16} style={{ marginRight: 6 }} />
                  )}
                  Download Authoritative PDF
                </button>
                <button className="btn btn-ghost" onClick={handleCloseDetail}>
                  Close
                </button>
              </div>
            </div>
          ) : null}
        </Modal>
      )}
    </div>
  );
};
