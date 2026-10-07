import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AdminDocumentVaultPage } from '../AdminDocumentVaultPage';
import { BrowserRouter } from 'react-router-dom';

vi.mock('../../../services/documents', () => ({
  documentService: {
    listIssuedDocuments: vi.fn().mockResolvedValue([]),
    listTemplates: vi.fn().mockResolvedValue([]),
    generateDocument: vi.fn(),
  }
}));

vi.mock('../../../services/employeeManagement', () => ({
  employeeManagementService: {
    listEmployees: vi.fn().mockResolvedValue([]),
  }
}));

const mockAuthContext = {
  user: { id: 1, email: 'admin@test.com' },
  hasPermission: vi.fn().mockReturnValue(true),
  hasEmployeeProfile: true,
} as any;

vi.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => mockAuthContext
}));

describe('AdminDocumentVaultPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing and shows empty state', async () => {
    render(
      <BrowserRouter>
        <AdminDocumentVaultPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Document Vault')).toBeInTheDocument();
      expect(screen.getByText('No documents found in the vault.')).toBeInTheDocument();
    });
  });
});
