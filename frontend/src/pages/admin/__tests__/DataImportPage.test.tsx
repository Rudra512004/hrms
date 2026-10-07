import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DataImportPage } from '../DataImportPage';
import { dataImportService } from '../../../services/dataImport';
import type { ImportJob } from '../../../types/dataImport';
import * as AuthContextModule from '../../../contexts/AuthContext';

vi.mock('../../../services/dataImport', () => ({
  dataImportService: {
    getTemplates: vi.fn(),
    getTemplateDownloadUrl: vi.fn(),
    downloadTemplate: vi.fn(),
    createJob: vi.fn(),
    validateJob: vi.fn(),
    executeJob: vi.fn(),
    getJobErrors: vi.fn(),
  }
}));

const mockTemplates = [
  {
    key: 'employees',
    display_name: 'Employees',
    filename: 'employees_template.csv',
    description: 'Import employees',
    version: '1.0',
    headers: ['employee_code', 'first_name'],
    fields: []
  }
];

const mockJob = {
  id: 'job-123',
  template_key: 'employees',
  status: 'pending',
  original_filename: 'test.csv',
  total_rows: 0,
  valid_rows: 0,
  created_count: 0,
  updated_count: 0,
  skipped_count: 0,
  error_count: 0,
  started_at: null,
  completed_at: null,
  created_at: '2026-10-06T12:00:00Z',
  preview_data: []
} as unknown as ImportJob;

const mockValidatedJob = {
  ...mockJob,
  status: 'validated',
  total_rows: 2,
  preview_data: [
    { row: 1, status: 'ok', data: { employee_code: 'E1', first_name: 'John' } },
    { row: 2, status: 'error', error: 'Invalid name' }
  ]
} as unknown as ImportJob;

const mockExecutedJobSuccess = {
  ...mockJob,
  status: 'completed',
  total_rows: 1,
  created_count: 1,
  error_count: 0
} as unknown as ImportJob;

const mockExecutedJobError = {
  ...mockJob,
  status: 'completed_with_errors',
  total_rows: 2,
  created_count: 1,
  error_count: 1
} as unknown as ImportJob;

describe('DataImportPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: { id: 1, email: 'admin@test.com', is_superuser: false, is_staff: true },
      isAuthenticated: true,
      hasEmployeeProfile: true,
      permissions: ['data_import.view', 'data_import.execute'],
      hasPermission: (perm: string) => ['data_import.view', 'data_import.execute'].includes(perm),
      logout: vi.fn(),
    } as any);

    vi.mocked(dataImportService.getTemplates).mockResolvedValue(mockTemplates);
  });

  const renderComponent = () => {
    return render(
      <MemoryRouter>
        <DataImportPage />
      </MemoryRouter>
    );
  };

  it('renders templates on mount', async () => {
    renderComponent();
    
    expect(screen.getByText('Universal Data Import')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(screen.getByText('Employees')).toBeInTheDocument();
    });
  });

  it('progresses through the workflow to success', async () => {
    renderComponent();
    
    // Select template
    await waitFor(() => screen.getByText('Employees'));
    fireEvent.click(screen.getByText('Employees'));
    
    // Upload step
    expect(screen.getByText('Employees Import')).toBeInTheDocument();
    const file = new File(['test'], 'test.csv', { type: 'text/csv' });
    
    // Mock the create job response
    vi.mocked(dataImportService.createJob).mockResolvedValue(mockJob);
    
    const input = document.getElementById('file-upload') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    
    await waitFor(() => {
      expect(screen.getByText('test.csv')).toBeInTheDocument();
    });
    
    fireEvent.click(screen.getByText('Upload & Continue'));
    
    // Validate step
    await waitFor(() => {
      expect(screen.getByText('Validate Import File')).toBeInTheDocument();
    });
    
    vi.mocked(dataImportService.validateJob).mockResolvedValue(mockValidatedJob);
    fireEvent.click(screen.getByText('Validate Import File'));
    
    // Preview step
    await waitFor(() => {
      expect(screen.getByText('Preview Data')).toBeInTheDocument();
      expect(screen.getByText('Invalid name')).toBeInTheDocument();
    });
    
    // Execute step
    vi.mocked(dataImportService.executeJob).mockResolvedValue(mockExecutedJobSuccess);
    fireEvent.click(screen.getByText('Confirm & Execute Import'));
    
    // Result step
    await waitFor(() => {
      expect(screen.getByText('Import Successful')).toBeInTheDocument();
      expect(screen.getByText('Start Another Import')).toBeInTheDocument();
    });
  });

  it('shows error report on partial failure', async () => {
    renderComponent();
    
    // Jump straight to execute by faking state (or walking through)
    await waitFor(() => screen.getByText('Employees'));
    fireEvent.click(screen.getByText('Employees'));
    
    const file = new File(['test'], 'test.csv', { type: 'text/csv' });
    vi.mocked(dataImportService.createJob).mockResolvedValue(mockJob);
    fireEvent.change(document.getElementById('file-upload') as HTMLInputElement, { target: { files: [file] } });
    fireEvent.click(screen.getByText('Upload & Continue'));
    
    await waitFor(() => screen.getByText('Validate Import File'));
    vi.mocked(dataImportService.validateJob).mockResolvedValue(mockValidatedJob);
    fireEvent.click(screen.getByText('Validate Import File'));
    
    await waitFor(() => screen.getByText('Confirm & Execute Import'));
    
    // Execute with error
    vi.mocked(dataImportService.executeJob).mockResolvedValue(mockExecutedJobError);
    vi.mocked(dataImportService.getJobErrors).mockResolvedValue([
      { row_number: 2, field: 'first_name', error_type: 'invalid', message: 'Name is bad', row_data: {} }
    ]);
    
    fireEvent.click(screen.getByText('Confirm & Execute Import'));
    
    await waitFor(() => {
      expect(screen.getByText('Import Completed with Errors')).toBeInTheDocument();
      expect(screen.getByText('Name is bad')).toBeInTheDocument();
    });
  });

  it('denies access if no permission', async () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      hasPermission: () => false,
    } as any);

    renderComponent();
    expect(screen.getByText(/You do not have permission/)).toBeInTheDocument();
  });
});
