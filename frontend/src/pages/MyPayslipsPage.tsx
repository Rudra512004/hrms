import React, { useState, useEffect, useCallback } from 'react';
import { FileText, Eye, Printer, Loader2, Calendar, User, Briefcase } from 'lucide-react';
import { Card } from '../components/Card';
import { Table } from '../components/Table';
import { StatusBadge } from '../components/StatusBadge';
import { PageHeader } from '../components/PageHeader';
import { Modal } from '../components/Modal';
import { AlertBanner } from '../components/AlertBanner';
import { EmptyState } from '../components/EmptyState';
import {
  payrollService,
  type PayslipSummary,
  type PayslipDetail,
  formatCurrency,
  extractApiError,
} from '../services/payroll';

export const MyPayslipsPage: React.FC = () => {
  const [payslips, setPayslips] = useState<PayslipSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Detail Modal State
  const [selectedPayslipId, setSelectedPayslipId] = useState<number | null>(null);
  const [detail, setDetail] = useState<PayslipDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const fetchPayslips = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await payrollService.getMyPayslips();
      setPayslips(data);
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPayslips();
  }, [fetchPayslips]);

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

  const handlePrint = () => {
    window.print();
  };

  const columns = [
    {
      key: 'period_label',
      title: 'Period',
      render: (p: PayslipSummary) => (
        <span style={{ fontWeight: 600, color: 'var(--color-text-main)' }}>
          {p.period_label}
        </span>
      ),
    },
    {
      key: 'payslip_number',
      title: 'Payslip Number',
      render: (p: PayslipSummary) => (
        <code style={{ fontSize: '0.85rem', color: 'var(--color-primary)' }}>
          {p.payslip_number}
        </code>
      ),
    },
    {
      key: 'issued_at',
      title: 'Issued Date',
      render: (p: PayslipSummary) =>
        p.issued_at ? new Date(p.issued_at).toLocaleDateString() : '—',
    },
    {
      key: 'net_salary',
      title: 'Net Salary',
      render: (p: PayslipSummary) => (
        <span style={{ fontWeight: 600, color: 'var(--color-status-success)' }}>
          {formatCurrency(p.net_salary)}
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
      title: 'Action',
      render: (p: PayslipSummary) => (
        <button
          className="btn btn-ghost"
          style={{ padding: '6px 12px', fontSize: '0.85rem' }}
          onClick={() => handleOpenDetail(p.id)}
          title="View Payslip"
        >
          <Eye size={15} style={{ marginRight: 6 }} /> View
        </button>
      ),
    },
  ];

  return (
    <div className="page-container" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      <PageHeader
        title="My Payslips"
        subtitle="Review and download your finalized monthly earnings and attendance breakdown."
      />

      {error && <AlertBanner type="error" message={error} />}

      {payslips.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 'var(--spacing-md)' }}>
          <div className="card" style={{ padding: '16px 20px', borderTop: '3px solid var(--color-primary)', boxShadow: 'var(--shadow-sm)' }}>
            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Latest Issued Period</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--color-text-main)', marginTop: 4 }}>{payslips[0]?.period_label}</div>
          </div>
          <div className="card" style={{ padding: '16px 20px', borderTop: '3px solid var(--color-status-success)', boxShadow: 'var(--shadow-sm)' }}>
            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Latest Net Take-Home</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--color-status-success)', marginTop: 4 }}>{formatCurrency(payslips[0]?.net_salary)}</div>
          </div>
          <div className="card" style={{ padding: '16px 20px', borderTop: '3px solid var(--color-secondary)', boxShadow: 'var(--shadow-sm)' }}>
            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Total Payslips Available</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--color-text-main)', marginTop: 4 }}>{payslips.length} document{payslips.length !== 1 ? 's' : ''}</div>
          </div>
        </div>
      )}

      <Card title="Finalized Payslips History" noPadding>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--spacing-2xl)' }}>
            <Loader2 className="animate-spin" size={32} color="var(--color-primary)" />
          </div>
        ) : payslips.length === 0 ? (
          <EmptyState
            title="No Payslips Issued"
            description="You don't have any finalized payslips yet. Payslips appear here once HR approves the monthly payroll."
            icon={FileText}
          />
        ) : (
          <Table data={payslips} columns={columns} keyExtractor={(p) => p.id} />
        )}
      </Card>

      {/* Payslip Detail Modal */}
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
            <div className="payslip-modal-content" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
              {/* Header Box */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: 'var(--spacing-md)',
                  backgroundColor: 'var(--color-bg-body)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--color-border)',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
                    Payslip Number
                  </div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--color-primary)', fontFamily: 'monospace' }}>
                    {detail.payslip_number}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                    Issued On: {new Date(detail.issued_at).toLocaleDateString()}
                  </div>
                  <StatusBadge status="present" label="Official / Finalized" />
                </div>
              </div>

              {/* Employee & Period Information */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                  gap: 'var(--spacing-md)',
                  padding: 'var(--spacing-md)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <User size={13} /> Employee
                  </div>
                  <div style={{ fontWeight: 600, color: 'var(--color-text-main)' }}>{detail.employee.name}</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>ID: {detail.employee.code}</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>{detail.employee.email}</div>
                </div>

                <div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Briefcase size={13} /> Organization Details
                  </div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-main)' }}>
                    <strong>Dept:</strong> {detail.employee.department || '—'}
                  </div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-main)' }}>
                    <strong>Role:</strong> {detail.employee.designation || '—'}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Calendar size={13} /> Pay Period
                  </div>
                  <div style={{ fontWeight: 600, color: 'var(--color-text-main)' }}>{detail.period.label}</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                    {detail.period.start_date} to {detail.period.end_date}
                  </div>
                </div>
              </div>

              {/* Attendance Breakdown */}
              <div>
                <h4 style={{ margin: '0 0 var(--spacing-xs) 0', fontSize: '0.95rem', color: 'var(--color-text-main)' }}>
                  Attendance Summary
                </h4>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))',
                    gap: 'var(--spacing-sm)',
                    textAlign: 'center',
                  }}
                >
                  <div style={{ padding: '8px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Working Days</div>
                    <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{detail.attendance.working_days}</div>
                  </div>
                  <div style={{ padding: '8px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Present</div>
                    <div style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--color-status-success)' }}>{detail.attendance.present_days}</div>
                  </div>
                  <div style={{ padding: '8px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Half Days</div>
                    <div style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--color-status-warning)' }}>{detail.attendance.half_days}</div>
                  </div>
                  <div style={{ padding: '8px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Leave (Paid)</div>
                    <div style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--color-primary)' }}>{detail.attendance.leave_days}</div>
                  </div>
                  <div style={{ padding: '8px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Absent</div>
                    <div style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--color-status-danger)' }}>{detail.attendance.absent_days}</div>
                  </div>
                  <div style={{ padding: '8px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-primary)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-primary)', fontWeight: 600 }}>Paid Days</div>
                    <div style={{ fontWeight: 800, fontSize: '1.1rem', color: 'var(--color-primary)' }}>{detail.attendance.effective_days}</div>
                  </div>
                </div>
              </div>

              {/* Financial Breakdown Table */}
              <div>
                <h4 style={{ margin: '0 0 var(--spacing-xs) 0', fontSize: '0.95rem', color: 'var(--color-text-main)' }}>
                  Salary Computation
                </h4>
                <div style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                    <tbody>
                      <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                        <td style={{ padding: '10px 14px', color: 'var(--color-text-muted)' }}>Monthly Basic Salary</td>
                        <td style={{ padding: '10px 14px', textAlign: 'right', fontWeight: 500 }}>
                          {formatCurrency(detail.financials.basic_salary ?? undefined)}
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                        <td style={{ padding: '10px 14px', color: 'var(--color-text-muted)' }}>Gross Calculated Earnings</td>
                        <td style={{ padding: '10px 14px', textAlign: 'right', fontWeight: 500 }}>
                          {formatCurrency(detail.financials.gross_salary ?? undefined)}
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                        <td style={{ padding: '10px 14px', color: 'var(--color-text-muted)' }}>Statutory Deductions</td>
                        <td style={{ padding: '10px 14px', textAlign: 'right', color: 'var(--color-text-muted)' }}>
                          {formatCurrency(detail.financials.deductions ?? undefined)}
                        </td>
                      </tr>
                      <tr style={{ backgroundColor: 'var(--color-bg-body)' }}>
                        <td style={{ padding: '14px', fontWeight: 700, fontSize: '1rem', color: 'var(--color-text-main)' }}>
                          Net Payable Salary
                        </td>
                        <td
                          style={{
                            padding: '14px',
                            textAlign: 'right',
                            fontWeight: 800,
                            fontSize: '1.2rem',
                            color: 'var(--color-status-success)',
                          }}
                        >
                          {formatCurrency(detail.financials.net_salary ?? undefined)}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--spacing-sm)', marginTop: 'var(--spacing-sm)' }}>
                <button className="btn btn-secondary" onClick={handlePrint}>
                  <Printer size={16} style={{ marginRight: 6 }} /> Print / PDF
                </button>
                <button className="btn btn-primary" onClick={handleCloseDetail}>
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
