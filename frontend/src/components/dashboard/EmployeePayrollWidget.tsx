import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Download, Loader2, ArrowRight, Calendar, FileText } from 'lucide-react';
import { Card } from '../Card';
import { StatusBadge } from '../StatusBadge';
import {
  type PayslipSummary,
  payrollService,
  formatCurrency,
  extractApiError,
} from '../../services/payroll';

interface EmployeePayrollWidgetProps {
  payslips?: PayslipSummary[];
  loading?: boolean;
}

export const EmployeePayrollWidget: React.FC<EmployeePayrollWidgetProps> = ({
  payslips = [],
  loading = false,
}) => {
  const navigate = useNavigate();
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const latest = payslips.length > 0 ? payslips[0] : null;

  const handleDownloadPdf = async (id: number) => {
    setDownloadingId(id);
    setDownloadError(null);
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
      setDownloadError(extractApiError(err));
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <Card
      title="My Payroll & Payslips"
      actions={
        <button
          className="btn btn-ghost"
          style={{ padding: '4px 8px', fontSize: 'var(--font-size-xs)' }}
          onClick={() => navigate('/payslips')}
        >
          View All <ArrowRight size={13} style={{ marginLeft: 4 }} />
        </button>
      }
    >
      {loading ? (
        <div className="loading-center" style={{ padding: '28px' }}>
          <Loader2 size={24} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
        </div>
      ) : latest ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {/* Header row: Period and Status */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div
                style={{
                  padding: '6px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'var(--color-bg-body)',
                  color: 'var(--color-primary)',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <Calendar size={16} />
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-main)' }}>
                  Period {latest.period_label}
                </div>
                <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                  {latest.payslip_number}
                </div>
              </div>
            </div>
            <StatusBadge status="present" label="Issued" />
          </div>

          {/* Prominent Salary Callout */}
          <div
            style={{
              padding: '12px 16px',
              backgroundColor: 'var(--color-bg-body)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
                Net Take-Home Pay
              </div>
              <div
                style={{
                  fontSize: '1.35rem',
                  fontWeight: 800,
                  color: 'var(--color-status-success)',
                  marginTop: 2,
                }}
              >
                {formatCurrency(latest.net_pay || latest.net_salary)}
              </div>
            </div>

            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                Gross: <strong>{formatCurrency(latest.gross_earnings)}</strong>
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
                Deductions: <strong>{formatCurrency(latest.total_deductions)}</strong>
              </div>
            </div>
          </div>

          {downloadError && (
            <div style={{ fontSize: '0.75rem', color: 'var(--color-status-danger)' }}>
              {downloadError}
            </div>
          )}

          {/* Quick Action Button */}
          <div style={{ display: 'flex', gap: '8px', marginTop: '2px' }}>
            <button
              className="btn btn-secondary"
              style={{ flex: 1, padding: '7px 12px', fontSize: 'var(--font-size-xs)' }}
              onClick={() => handleDownloadPdf(latest.id)}
              disabled={downloadingId === latest.id}
            >
              {downloadingId === latest.id ? (
                <Loader2 size={14} className="animate-spin" style={{ marginRight: 6 }} />
              ) : (
                <Download size={14} style={{ marginRight: 6 }} />
              )}
              Download Official PDF
            </button>
            <button
              className="btn btn-ghost"
              style={{ padding: '7px 12px', fontSize: 'var(--font-size-xs)' }}
              onClick={() => navigate('/payslips')}
            >
              View Statement
            </button>
          </div>
        </div>
      ) : (
        <div style={{ padding: '20px 0', textAlign: 'center' }}>
          <FileText size={32} style={{ color: 'var(--color-text-muted)', margin: '0 auto 8px auto' }} />
          <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-main)' }}>
            No Payslips Issued Yet
          </div>
          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: 4 }}>
            Finalized monthly payslips will be published here once approved by Finance & HR.
          </div>
        </div>
      )}
    </Card>
  );
};
