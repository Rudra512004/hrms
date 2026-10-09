import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { MyPayslipsPage } from '../MyPayslipsPage';
import { payrollService, type PayslipSummary, type PayslipDetail } from '../../services/payroll';

vi.mock('../../services/payroll', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/payroll')>();
  return {
    ...actual,
    payrollService: {
      ...actual.payrollService,
      getMyPayslips: vi.fn(),
      getPayslipDetail: vi.fn(),
      downloadPayslipPdf: vi.fn(),
      getFinalSettlements: vi.fn(),
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
    verification_token: 'uuid-token-101',
  },
  {
    id: 100,
    payslip_number: 'PAY-202608-EMP001',
    status: 'issued',
    issued_at: '2026-09-01T10:00:00Z',
    period_label: '2026/08',
    year: 2026,
    month: 8,
    start_date: '2026-08-01',
    end_date: '2026-08-31',
    gross_earnings: '55000.00',
    total_deductions: '10000.00',
    net_salary: '45000.00',
    net_pay: '45000.00',
    employee_code: 'EMP-001',
    employee_name: 'John Doe',
    verification_token: 'uuid-token-100',
  },
];

const mockPayslipDetail: PayslipDetail = {
  id: 101,
  payslip_number: 'PAY-202609-EMP001',
  status: 'issued',
  issued_at: '2026-10-01T10:00:00Z',
  period_label: '2026/09',
  verification_token: 'uuid-token-101',
  integrity_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  net_pay_in_words: 'Rupees Forty-Five Thousand Only',
  organization: {
    name: 'BeyondSure Corp',
    legal_name: 'BeyondSure Technologies Pvt Ltd',
    address: 'Tech Park, Bangalore, India',
    cin: 'U72200KA2026PTC123456',
    branch: 'Headquarters',
  },
  employee: {
    id: 42,
    code: 'EMP-001',
    name: 'John Doe',
    email: 'john.doe@beyondsure.com',
    department: 'Engineering',
    designation: 'Senior Backend Engineer',
    joining_date: '2024-01-15',
    bank_name: 'HDFC Bank',
    masked_bank_account: '••••5678',
    bank_ifsc: 'HDFC0001234',
    payment_mode: 'Bank Transfer',
    masked_pan: '••••1234F',
    uan: '100987654321',
    esic_number: '3100987654321',
  },
  period: {
    id: 5,
    year: 2026,
    month: 9,
    label: '2026/09',
    start_date: '2026-09-01',
    end_date: '2026-09-30',
  },
  attendance: {
    calendar_days: 30,
    working_days: 22,
    present_days: 20,
    half_days: 0,
    leave_days: 2,
    absent_days: 0,
    effective_days: '22.0',
    lop_days: '0.0',
  },
  financials: {
    basic_salary: '35000.00',
    gross_salary: '55000.00',
    deductions: '10000.00',
    net_salary: '45000.00',
    net_pay_in_words: 'Rupees Forty-Five Thousand Only',
  },
  lines: [
    {
      id: 1,
      category: 'earning',
      component_code: 'BASIC',
      name: 'Basic Salary',
      amount: '35000.00',
      order: 1,
    },
    {
      id: 2,
      category: 'earning',
      component_code: 'HRA',
      name: 'House Rent Allowance',
      amount: '14000.00',
      order: 2,
    },
    {
      id: 3,
      category: 'earning',
      component_code: 'SPECIAL_ALLOWANCE',
      name: 'Special Allowance',
      amount: '6000.00',
      order: 3,
    },
    {
      id: 4,
      category: 'deduction',
      component_code: 'STAT_EPF',
      name: 'Provident Fund (EPF)',
      amount: '4200.00',
      order: 4,
    },
    {
      id: 5,
      category: 'deduction',
      component_code: 'STAT_PT',
      name: 'Professional Tax (PT)',
      amount: '200.00',
      order: 5,
    },
    {
      id: 6,
      category: 'deduction',
      component_code: 'TAX_TDS',
      name: 'Tax Deducted at Source (TDS)',
      amount: '5600.00',
      order: 6,
    },
  ],
};

describe('MyPayslipsPage — Employee Portal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(payrollService.getMyPayslips).mockResolvedValue(mockPayslips);
    vi.mocked(payrollService.getPayslipDetail).mockResolvedValue(mockPayslipDetail);
    vi.mocked(payrollService.getFinalSettlements).mockResolvedValue([]);
  });

  it('1. renders issued payslips list with authoritative figures', async () => {
    render(
      <MemoryRouter>
        <MyPayslipsPage />
      </MemoryRouter>
    );

    expect(screen.getByText('Employee Payroll Portal')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('PAY-202609-EMP001')).toBeInTheDocument();
      expect(screen.getByText('PAY-202608-EMP001')).toBeInTheDocument();
    });

    // Check KPI strip
    expect(screen.getByText('Latest Pay Period')).toBeInTheDocument();
    expect(screen.getByText('Latest Take-Home Pay')).toBeInTheDocument();
    expect(screen.getByText('Total Issued Payslips')).toBeInTheDocument();

    // Check row data
    expect(screen.getAllByText('Issued')[0]).toBeInTheDocument();
    expect(screen.getAllByText('View')[0]).toBeInTheDocument();
    expect(screen.getAllByText('PDF')[0]).toBeInTheDocument();
  });

  it('2. renders empty state when employee has no finalized payslips', async () => {
    vi.mocked(payrollService.getMyPayslips).mockResolvedValue([]);

    render(
      <MemoryRouter>
        <MyPayslipsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('No Issued Payslips')).toBeInTheDocument();
    });

    expect(
      screen.getByText(/You don't have any finalized payslips yet/i)
    ).toBeInTheDocument();
  });

  it('3. surfaces API errors properly', async () => {
    vi.mocked(payrollService.getMyPayslips).mockRejectedValue({
      errorData: { detail: 'Unable to connect to payroll database.' },
    });

    render(
      <MemoryRouter>
        <MyPayslipsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Unable to connect to payroll database.')).toBeInTheDocument();
    });
  });

  it('4. opens detailed modal and renders immutable snapshot data and masked sensitive fields', async () => {
    render(
      <MemoryRouter>
        <MyPayslipsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('PAY-202609-EMP001')).toBeInTheDocument();
    });

    // Click "View" button for first payslip
    const viewButtons = screen.getAllByRole('button', { name: /view/i });
    fireEvent.click(viewButtons[0]);

    await waitFor(() => {
      expect(payrollService.getPayslipDetail).toHaveBeenCalledWith(101);
    });

    // Check organization header
    await waitFor(() => {
      expect(screen.getByText('BeyondSure Technologies Pvt Ltd')).toBeInTheDocument();
      expect(screen.getByText(/Tech Park, Bangalore/)).toBeInTheDocument();
      expect(screen.getByText('CIN: U72200KA2026PTC123456')).toBeInTheDocument();
    });

    // Check employee & masked details
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('ID: EMP-001')).toBeInTheDocument();
    expect(screen.getByText('Senior Backend Engineer')).toBeInTheDocument();
    expect(screen.getByText(/••••5678/)).toBeInTheDocument();
    expect(screen.getByText(/••••1234F/)).toBeInTheDocument();
    expect(screen.getByText(/HDFC0001234/)).toBeInTheDocument();

    // Check attendance values
    expect(screen.getByText('22.0')).toBeInTheDocument(); // paid days

    // Check itemized earnings lines
    expect(screen.getByText('Basic Salary')).toBeInTheDocument();
    expect(screen.getByText('House Rent Allowance')).toBeInTheDocument();
    expect(screen.getByText('Special Allowance')).toBeInTheDocument();

    // Check itemized deductions lines
    expect(screen.getByText('Provident Fund (EPF)')).toBeInTheDocument();
    expect(screen.getByText('Professional Tax (PT)')).toBeInTheDocument();
    expect(screen.getByText('Tax Deducted at Source (TDS)')).toBeInTheDocument();

    // Check net pay in words & integrity hash
    expect(screen.getByText('Rupees Forty-Five Thousand Only')).toBeInTheDocument();
    expect(screen.getByText('Immutable Verification')).toBeInTheDocument();
    expect(screen.getByText(/e3b0c44298fc1c14/)).toBeInTheDocument();
  });

  it('5. triggers authoritative PDF download on action click', async () => {
    const mockBlob = new Blob(['%PDF-1.4 test'], { type: 'application/pdf' });
    vi.mocked(payrollService.downloadPayslipPdf).mockResolvedValue({
      blob: mockBlob,
      filename: 'Payslip_PAY-202609-EMP001.pdf',
    });

    // Mock URL.createObjectURL and revokeObjectURL
    const mockCreateObjectURL = vi.fn().mockReturnValue('blob:mock-url');
    const mockRevokeObjectURL = vi.fn();
    window.URL.createObjectURL = mockCreateObjectURL;
    window.URL.revokeObjectURL = mockRevokeObjectURL;

    render(
      <MemoryRouter>
        <MyPayslipsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('PAY-202609-EMP001')).toBeInTheDocument();
    });

    const pdfButtons = screen.getAllByRole('button', { name: /pdf/i });
    fireEvent.click(pdfButtons[0]);

    await waitFor(() => {
      expect(payrollService.downloadPayslipPdf).toHaveBeenCalledWith(101);
      expect(mockCreateObjectURL).toHaveBeenCalledWith(mockBlob);
    });
  });

  it('6. navigates to Income Tax tab and displays authoritative tax notice', async () => {
    render(
      <MemoryRouter>
        <MyPayslipsPage />
      </MemoryRouter>
    );

    const taxTabButton = screen.getByRole('button', { name: /income tax & deductions/i });
    fireEvent.click(taxTabButton);

    expect(screen.getByText('Active Tax Regime')).toBeInTheDocument();
    expect(screen.getByText('New Tax Regime (Default)')).toBeInTheDocument();
    expect(screen.getByText('Tax Declaration & Proof Verification Notice')).toBeInTheDocument();
    expect(
      screen.getByText(/The frontend does not fabricate or simulate client-side tax estimations/i)
    ).toBeInTheDocument();
  });

  it('7. navigates to FnF tab and handles self-service visibility / permission boundary safely', async () => {
    vi.mocked(payrollService.getFinalSettlements).mockRejectedValue({
      response: { status: 403 },
      errorData: { detail: 'Permission denied.' },
    });

    render(
      <MemoryRouter>
        <MyPayslipsPage />
      </MemoryRouter>
    );

    const fnfTabButton = screen.getByRole('button', { name: /full & final settlement/i });
    fireEvent.click(fnfTabButton);

    await waitFor(() => {
      expect(payrollService.getFinalSettlements).toHaveBeenCalled();
      expect(
        screen.getByText(/Full & Final Settlement records are restricted to HR\/Payroll Operations administrators/i)
      ).toBeInTheDocument();
    });
  });
});
