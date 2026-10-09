import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { EmployeePayrollWidget } from '../EmployeePayrollWidget';
import { payrollService, type PayslipSummary } from '../../../services/payroll';

vi.mock('../../../services/payroll', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../services/payroll')>();
  return {
    ...actual,
    payrollService: {
      ...actual.payrollService,
      downloadPayslipPdf: vi.fn(),
    },
  };
});

const mockPayslips: PayslipSummary[] = [
  {
    id: 101,
    payslip_number: 'PAY-202609-EMP001',
    status: 'issued',
    issued_at: '2026-10-01T10:00:00Z',
    period_label: '2026/09',
    year: 2026,
    month: 9,
    start_date: '2026-09-01',
    end_date: '2026-09-30',
    gross_earnings: '55000.00',
    total_deductions: '10000.00',
    net_salary: '45000.00',
    net_pay: '45000.00',
    employee_code: 'EMP-001',
    employee_name: 'John Doe',
  },
];

describe('EmployeePayrollWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('1. renders latest payslip metrics and take-home pay', () => {
    render(
      <MemoryRouter>
        <EmployeePayrollWidget payslips={mockPayslips} loading={false} />
      </MemoryRouter>
    );

    expect(screen.getByText('My Payroll & Payslips')).toBeInTheDocument();
    expect(screen.getByText('Period 2026/09')).toBeInTheDocument();
    expect(screen.getByText('PAY-202609-EMP001')).toBeInTheDocument();
    expect(screen.getByText('Issued')).toBeInTheDocument();
    expect(screen.getByText('Download Official PDF')).toBeInTheDocument();
  });

  it('2. triggers authoritative PDF download on action click', async () => {
    const mockBlob = new Blob(['%PDF-1.4 test'], { type: 'application/pdf' });
    vi.mocked(payrollService.downloadPayslipPdf).mockResolvedValue({
      blob: mockBlob,
      filename: 'Payslip_101.pdf',
    });

    const mockCreateObjectURL = vi.fn().mockReturnValue('blob:mock-url');
    const mockRevokeObjectURL = vi.fn();
    window.URL.createObjectURL = mockCreateObjectURL;
    window.URL.revokeObjectURL = mockRevokeObjectURL;

    render(
      <MemoryRouter>
        <EmployeePayrollWidget payslips={mockPayslips} loading={false} />
      </MemoryRouter>
    );

    const downloadButton = screen.getByRole('button', { name: /download official pdf/i });
    fireEvent.click(downloadButton);

    await waitFor(() => {
      expect(payrollService.downloadPayslipPdf).toHaveBeenCalledWith(101);
      expect(mockCreateObjectURL).toHaveBeenCalledWith(mockBlob);
    });
  });

  it('3. renders empty state when employee has no issued payslips', () => {
    render(
      <MemoryRouter>
        <EmployeePayrollWidget payslips={[]} loading={false} />
      </MemoryRouter>
    );

    expect(screen.getByText('No Payslips Issued Yet')).toBeInTheDocument();
    expect(
      screen.getByText(/Finalized monthly payslips will be published here/i)
    ).toBeInTheDocument();
  });
});
