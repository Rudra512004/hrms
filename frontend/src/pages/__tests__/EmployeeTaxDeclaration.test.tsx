import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EmployeeTaxDeclarationView } from '../../components/tax/EmployeeTaxDeclarationView';
import {
  payrollService,
  type FinancialYear,
  type TaxDeclarationCategory,
  type TaxDeclarationSummary,
  type TaxDeclarationDetail,
  type InvestmentDeclaration,
  type InvestmentProof,
} from '../../services/payroll';

vi.mock('../../services/payroll', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/payroll')>();
  return {
    ...actual,
    payrollService: {
      ...actual.payrollService,
      getFinancialYears: vi.fn(),
      getTaxCategories: vi.fn(),
      getMyTaxDeclarations: vi.fn(),
      getTaxDeclarationDetail: vi.fn(),
      createTaxDeclaration: vi.fn(),
      updateTaxDeclaration: vi.fn(),
      submitTaxDeclaration: vi.fn(),
      addInvestmentItem: vi.fn(),
      updateInvestmentItem: vi.fn(),
      deleteInvestmentItem: vi.fn(),
      uploadInvestmentProof: vi.fn(),
      downloadInvestmentProof: vi.fn(),
    },
  };
});

// Mock Fixtures
const mockFinancialYears: FinancialYear[] = [
  {
    id: 1,
    name: 'FY 2025-26',
    start_date: '2025-04-01',
    end_date: '2026-03-31',
    is_active: true,
    is_locked: false,
    created_at: '2025-04-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'FY 2024-25',
    start_date: '2024-04-01',
    end_date: '2025-03-31',
    is_active: false,
    is_locked: true,
    created_at: '2024-04-01T00:00:00Z',
  },
];

const mockCategories: TaxDeclarationCategory[] = [
  {
    id: 10,
    code: '80C',
    name: 'Life Insurance, PPF, ELSS, EPF',
    description: 'Deduction under Section 80C',
    max_limit: '150000.00',
    regime_applicability: 'old',
    is_active: true,
  },
  {
    id: 11,
    code: '80D',
    name: 'Medical Insurance Premium',
    description: 'Deduction under Section 80D',
    max_limit: '50000.00',
    regime_applicability: 'old',
    is_active: true,
  },
];

const mockProof: InvestmentProof = {
  id: 501,
  declaration_item: 201,
  proof_type: 'RECEIPT',
  document_name: 'lic_receipt_2025.pdf',
  file_size: 102400,
  mime_type: 'application/pdf',
  status: 'submitted',
  rejection_reason: null,
  reviewed_by_email: null,
  reviewed_at: null,
  submitted_at: '2025-07-01T10:00:00Z',
};

const mockItem: InvestmentDeclaration = {
  id: 201,
  declaration: 101,
  category: 10,
  category_code: '80C',
  description: 'LIC Premium Policy 987654',
  declared_amount: '45000.00',
  verified_amount: '0.00',
  status: 'pending',
  rejection_reason: null,
  metadata: {},
  proofs: [mockProof],
  created_at: '2025-06-01T00:00:00Z',
  updated_at: '2025-06-01T00:00:00Z',
};

const mockDeclarationSummary: TaxDeclarationSummary = {
  id: 101,
  employee: 42,
  employee_code: 'EMP-001',
  employee_name: 'John Doe',
  financial_year: 1,
  financial_year_name: 'FY 2025-26',
  financial_year_start: '2025-04-01',
  financial_year_end: '2026-03-31',
  tax_regime: 'NEW',
  status: 'draft',
  total_declared_amount: '45000.00',
  total_verified_amount: '0.00',
  items_count: 1,
  submission_date: null,
  verification_date: null,
  created_at: '2025-05-01T00:00:00Z',
};

const mockDeclarationDetailDraft: TaxDeclarationDetail = {
  id: 101,
  employee: 42,
  employee_code: 'EMP-001',
  employee_name: 'John Doe',
  financial_year: 1,
  financial_year_name: 'FY 2025-26',
  financial_year_start: '2025-04-01',
  financial_year_end: '2026-03-31',
  financial_year_locked: false,
  tax_regime: 'NEW',
  status: 'draft',
  total_declared_amount: '45000.00',
  total_verified_amount: '0.00',
  submission_date: null,
  verification_date: null,
  verified_by_email: null,
  rejection_reason: null,
  notes: 'Draft declaration for FY 25-26',
  items: [mockItem],
  created_at: '2025-05-01T00:00:00Z',
  updated_at: '2025-05-01T00:00:00Z',
};

describe('P6.9B Employee Tax Declaration UI Integration Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(payrollService.getFinancialYears).mockResolvedValue(mockFinancialYears);
    vi.mocked(payrollService.getTaxCategories).mockResolvedValue(mockCategories);
    vi.mocked(payrollService.getMyTaxDeclarations).mockResolvedValue([mockDeclarationSummary]);
    vi.mocked(payrollService.getTaxDeclarationDetail).mockResolvedValue(mockDeclarationDetailDraft);
  });

  it('1. loads financial years and tax categories on mount', async () => {
    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(payrollService.getFinancialYears).toHaveBeenCalled();
      expect(payrollService.getTaxCategories).toHaveBeenCalled();
      expect(payrollService.getMyTaxDeclarations).toHaveBeenCalledWith(1);
      expect(payrollService.getTaxDeclarationDetail).toHaveBeenCalledWith(101);
    });

    expect(screen.getByDisplayValue(/FY 2025-26/i)).toBeInTheDocument();
    expect(screen.getByText('Period: 2025-04-01 to 2026-03-31')).toBeInTheDocument();
  });

  it('2. handles empty declaration state when no declaration exists for financial year', async () => {
    vi.mocked(payrollService.getMyTaxDeclarations).mockResolvedValue([]);

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByText(/No Tax Declaration for FY 2025-26/i)).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /create tax declaration/i })).toBeInTheDocument();
  });

  it('3. allows creating a draft declaration when none exists', async () => {
    vi.mocked(payrollService.getMyTaxDeclarations).mockResolvedValue([]);
    vi.mocked(payrollService.createTaxDeclaration).mockResolvedValue(mockDeclarationDetailDraft);

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByText(/No Tax Declaration for FY 2025-26/i)).toBeInTheDocument();
    });

    const createBtn = screen.getByRole('button', { name: /create tax declaration/i });
    fireEvent.click(createBtn);

    expect(screen.getByText(/Start Tax Declaration — FY 2025-26/i)).toBeInTheDocument();

    const submitCreateBtn = screen.getByRole('button', { name: /create draft declaration/i });
    fireEvent.click(submitCreateBtn);

    await waitFor(() => {
      expect(payrollService.createTaxDeclaration).toHaveBeenCalledWith({
        financial_year_id: 1,
        tax_regime: 'NEW',
        notes: '',
      });
      expect(screen.getByText(/Draft tax declaration successfully created/i)).toBeInTheDocument();
    });
  });

  it('4. supports regime switching while in draft state', async () => {
    const updatedOldRegime: TaxDeclarationDetail = {
      ...mockDeclarationDetailDraft,
      tax_regime: 'OLD',
    };
    vi.mocked(payrollService.updateTaxDeclaration).mockResolvedValue(updatedOldRegime);

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByLabelText(/change regime/i)).toBeInTheDocument();
    });

    const regimeSelect = screen.getByLabelText(/change regime/i);
    fireEvent.change(regimeSelect, { target: { value: 'OLD' } });

    await waitFor(() => {
      expect(payrollService.updateTaxDeclaration).toHaveBeenCalledWith(101, {
        tax_regime: 'OLD',
      });
      expect(screen.getByText(/Tax regime updated to OLD/i)).toBeInTheDocument();
    });
  });

  it('5. allows adding an investment item driven by authoritative categories', async () => {
    const newItem: InvestmentDeclaration = {
      id: 202,
      declaration: 101,
      category: 11,
      category_code: '80D',
      description: 'Mediclaim Star Health',
      declared_amount: '20000.00',
      verified_amount: '0.00',
      status: 'pending',
      proofs: [],
      created_at: '2025-06-01T00:00:00Z',
      updated_at: '2025-06-01T00:00:00Z',
    };
    vi.mocked(payrollService.addInvestmentItem).mockResolvedValue(newItem);
    vi.mocked(payrollService.getTaxDeclarationDetail).mockResolvedValueOnce(mockDeclarationDetailDraft)
      .mockResolvedValueOnce({
        ...mockDeclarationDetailDraft,
        items: [...mockDeclarationDetailDraft.items, newItem],
      });

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add investment item/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /add investment item/i }));

    expect(screen.getByText('Add Investment Declaration Item')).toBeInTheDocument();

    const descInput = screen.getByLabelText(/description/i);
    const amountInput = screen.getByLabelText(/declared amount/i);

    fireEvent.change(descInput, { target: { value: 'Mediclaim Star Health' } });
    fireEvent.change(amountInput, { target: { value: '20000.00' } });

    const saveBtn = screen.getByRole('button', { name: /^add item$/i });
    fireEvent.submit(saveBtn.closest('form')!);

    await waitFor(() => {
      expect(payrollService.addInvestmentItem).toHaveBeenCalledWith(101, {
        category_code: '80C',
        description: 'Mediclaim Star Health',
        declared_amount: '20000.00',
      });
      expect(screen.getByText('Investment item added.')).toBeInTheDocument();
    });
  });

  it('6. allows editing an existing investment item', async () => {
    const updatedItem: InvestmentDeclaration = {
      ...mockItem,
      description: 'LIC Premium Policy 987654 Updated',
      declared_amount: '50000.00',
    };
    vi.mocked(payrollService.updateInvestmentItem).mockResolvedValue(updatedItem);

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByLabelText('Edit item 80C')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText('Edit item 80C'));

    expect(screen.getByText(/Edit Investment Item \(80C\)/i)).toBeInTheDocument();

    const descInput = screen.getByLabelText(/description/i);
    fireEvent.change(descInput, { target: { value: 'LIC Premium Policy 987654 Updated' } });

    const saveBtn = screen.getByRole('button', { name: /save changes/i });
    fireEvent.submit(saveBtn.closest('form')!);

    await waitFor(() => {
      expect(payrollService.updateInvestmentItem).toHaveBeenCalledWith(101, 201, {
        description: 'LIC Premium Policy 987654 Updated',
        declared_amount: '45000.00',
      });
      expect(screen.getByText('Investment item updated.')).toBeInTheDocument();
    });
  });

  it('7. allows deleting an existing investment item', async () => {
    vi.mocked(payrollService.deleteInvestmentItem).mockResolvedValue();

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByLabelText('Delete item 80C')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText('Delete item 80C'));

    await waitFor(() => {
      expect(payrollService.deleteInvestmentItem).toHaveBeenCalledWith(101, 201);
      expect(screen.getByText('Investment item deleted.')).toBeInTheDocument();
    });
  });

  it('8. supports uploading a proof document attached to an item', async () => {
    const newUploadedProof: InvestmentProof = {
      id: 502,
      declaration_item: 201,
      proof_type: 'RECEIPT',
      document_name: 'lic_receipt_new.pdf',
      file_size: 51200,
      mime_type: 'application/pdf',
      status: 'submitted',
      submitted_at: '2025-07-02T10:00:00Z',
    };
    vi.mocked(payrollService.uploadInvestmentProof).mockResolvedValue(newUploadedProof);

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByLabelText('Upload proof for 80C')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText('Upload proof for 80C'));

    expect(screen.getByText(/Upload Proof Document \(80C\)/i)).toBeInTheDocument();

    const fileInput = screen.getByLabelText(/supporting document file/i);
    const dummyFile = new File(['proof-data'], 'lic_receipt_new.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [dummyFile] } });

    const uploadSubmitBtn = screen.getByRole('button', { name: /^upload proof$/i });
    fireEvent.submit(uploadSubmitBtn.closest('form')!);

    await waitFor(() => {
      expect(payrollService.uploadInvestmentProof).toHaveBeenCalledWith(
        101,
        201,
        expect.any(FormData)
      );
      expect(screen.getByText('Proof document uploaded successfully.')).toBeInTheDocument();
    });
  });

  it('9. supports downloading a proof document with authenticated stream', async () => {
    const mockBlob = new Blob(['pdf-binary-data'], { type: 'application/pdf' });
    vi.mocked(payrollService.downloadInvestmentProof).mockResolvedValue({
      blob: mockBlob,
      filename: 'lic_receipt_2025.pdf',
    });

    const mockCreateObjectURL = vi.fn().mockReturnValue('blob:http://localhost/dummy');
    const mockRevokeObjectURL = vi.fn();
    window.URL.createObjectURL = mockCreateObjectURL;
    window.URL.revokeObjectURL = mockRevokeObjectURL;

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByLabelText('Download proof lic_receipt_2025.pdf')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText('Download proof lic_receipt_2025.pdf'));

    await waitFor(() => {
      expect(payrollService.downloadInvestmentProof).toHaveBeenCalledWith(101, 201, 501);
      expect(mockCreateObjectURL).toHaveBeenCalledWith(mockBlob);
    });
  });

  it('10. submitted state enforces read-only controls', async () => {
    const submittedDeclaration: TaxDeclarationDetail = {
      ...mockDeclarationDetailDraft,
      status: 'submitted',
      submission_date: '2025-07-10',
    };
    vi.mocked(payrollService.getTaxDeclarationDetail).mockResolvedValue(submittedDeclaration);

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByText(/Submitted & Awaiting Review/i)).toBeInTheDocument();
    });

    // Mutating controls should NOT exist
    expect(screen.queryByRole('button', { name: /submit declaration/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /add investment item/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Edit item 80C')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Delete item 80C')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Upload proof for 80C')).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/change regime/i)).not.toBeInTheDocument();
  });

  it('11. under_review state is strictly read-only', async () => {
    const underReviewDeclaration: TaxDeclarationDetail = {
      ...mockDeclarationDetailDraft,
      status: 'under_review',
      submission_date: '2025-07-10',
    };
    vi.mocked(payrollService.getTaxDeclarationDetail).mockResolvedValue(underReviewDeclaration);

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByText(/Under Review:/i)).toBeInTheDocument();
      expect(screen.getByText(/This declaration is strictly read-only/i)).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /submit declaration/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /add investment item/i })).not.toBeInTheDocument();
  });

  it('12. verified state displays verified totals and verification metadata', async () => {
    const verifiedDeclaration: TaxDeclarationDetail = {
      ...mockDeclarationDetailDraft,
      status: 'verified',
      submission_date: '2025-07-10',
      verification_date: '2025-07-15',
      verified_by_email: 'payroll.admin@beyondsure.com',
      total_verified_amount: '45000.00',
      items: [
        {
          ...mockItem,
          status: 'verified',
          verified_amount: '45000.00',
        },
      ],
    };
    vi.mocked(payrollService.getTaxDeclarationDetail).mockResolvedValue(verifiedDeclaration);

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByText(/Declaration Verified:/i)).toBeInTheDocument();
      expect(screen.getByText(/payroll.admin@beyondsure.com/i)).toBeInTheDocument();
      expect(screen.getByText(/2025-07-15/i)).toBeInTheDocument();
    });

    // Verification amounts should be visible
    expect(screen.getAllByText('₹45,000.00').length).toBeGreaterThan(0);
    // Editing controls must be absent
    expect(screen.queryByRole('button', { name: /submit declaration/i })).not.toBeInTheDocument();
  });

  it('13. rejected state displays rejection reason and allows resubmission', async () => {
    const rejectedDeclaration: TaxDeclarationDetail = {
      ...mockDeclarationDetailDraft,
      status: 'rejected',
      rejection_reason: 'Term insurance premium receipt date does not fall within FY 2025-26.',
    };
    vi.mocked(payrollService.getTaxDeclarationDetail).mockResolvedValue(rejectedDeclaration);

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByText(/Declaration Returned \/ Rejected:/i)).toBeInTheDocument();
      expect(
        screen.getByText(/Term insurance premium receipt date does not fall within FY 2025-26/i)
      ).toBeInTheDocument();
    });

    // In rejected state, employee can edit items and resubmit
    expect(screen.getByRole('button', { name: /resubmit declaration/i })).toBeInTheDocument();
    expect(screen.getByLabelText('Edit item 80C')).toBeInTheDocument();
  });

  it('14. locked financial year disables creation and editing', async () => {
    const lockedFy = mockFinancialYears[1]; // FY 2024-25 is locked
    vi.mocked(payrollService.getMyTaxDeclarations).mockResolvedValue([]);

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByDisplayValue(/FY 2025-26/i)).toBeInTheDocument();
    });

    const fySelect = screen.getByLabelText(/financial year/i);
    fireEvent.change(fySelect, { target: { value: String(lockedFy.id) } });

    await waitFor(() => {
      expect(screen.getByText(/Declarations Locked for FY 2024-25/i)).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /create tax declaration/i })).not.toBeInTheDocument();
  });

  it('15. displays backend validation error clearly', async () => {
    vi.mocked(payrollService.addInvestmentItem).mockRejectedValue({
      errorData: {
        detail: 'Cannot exceed configured category limit of 150000.00.',
        code: 'CATEGORY_LIMIT_EXCEEDED',
      },
    });

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add investment item/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /add investment item/i }));

    const descInput = screen.getByLabelText(/description/i);
    const amountInput = screen.getByLabelText(/declared amount/i);
    fireEvent.change(descInput, { target: { value: 'Excessive 80C' } });
    fireEvent.change(amountInput, { target: { value: '200000.00' } });

    const saveBtn = screen.getByRole('button', { name: /^add item$/i });
    fireEvent.submit(saveBtn.closest('form')!);

    await waitFor(() => {
      expect(
        screen.getByText('Cannot exceed configured category limit of 150000.00.')
      ).toBeInTheDocument();
    });
  });

  it('16. handles API 403 Forbidden without crashing', async () => {
    vi.mocked(payrollService.getMyTaxDeclarations).mockRejectedValue({
      response: { status: 403 },
      errorData: { detail: 'An active employee profile is required to access tax declarations.' },
    });

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(
        screen.getByText('An active employee profile is required to access tax declarations.')
      ).toBeInTheDocument();
    });
  });

  it('17. submission confirmation modal flow and status refresh', async () => {
    const submittedDeclaration: TaxDeclarationDetail = {
      ...mockDeclarationDetailDraft,
      status: 'submitted',
      submission_date: '2025-07-15',
    };
    vi.mocked(payrollService.submitTaxDeclaration).mockResolvedValue(submittedDeclaration);

    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /submit declaration/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /submit declaration/i }));

    expect(screen.getByText(/Submit Tax Declaration — FY 2025-26/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Are you sure you want to submit your tax declaration for review\?/i)
    ).toBeInTheDocument();

    const confirmSubmitBtn = screen.getByRole('button', { name: /confirm & submit declaration/i });
    fireEvent.click(confirmSubmitBtn);

    await waitFor(() => {
      expect(payrollService.submitTaxDeclaration).toHaveBeenCalledWith(101);
      expect(
        screen.getByText('Your tax declaration has been submitted for review.')
      ).toBeInTheDocument();
      expect(screen.getByText(/Submitted & Awaiting Review/i)).toBeInTheDocument();
    });
  });

  it('18. reviewer operations (start-review, verify, reject) are NEVER rendered', async () => {
    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByText(/Draft Declaration/i)).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /start review/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /verify declaration/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /reject declaration/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /verify proof/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /reject proof/i })).not.toBeInTheDocument();
  });

  it('19. zero client-side tax calculations or fake savings formulas exist in the rendered output', async () => {
    render(<EmployeeTaxDeclarationView />);

    await waitFor(() => {
      expect(screen.getByText('Total Declared:')).toBeInTheDocument();
    });

    // Ensure forbidden client-side calculations and comparison text are absent
    expect(screen.queryByText(/tax saved/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/better regime/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/estimated tax/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/taxable income after deduction/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/standard deduction of/i)).not.toBeInTheDocument();
  });
});
