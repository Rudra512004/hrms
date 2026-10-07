import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AdminDocumentTemplatesPage } from '../AdminDocumentTemplatesPage';
import { BrowserRouter } from 'react-router-dom';

vi.mock('../../../services/documents', () => ({
  documentService: {
    listTemplates: vi.fn().mockResolvedValue([]),
    listCategories: vi.fn().mockResolvedValue([]),
    getTemplate: vi.fn(),
    createTemplate: vi.fn(),
    addVersion: vi.fn(),
    previewTemplate: vi.fn(),
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

describe('AdminDocumentTemplatesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing and shows empty state', async () => {
    render(
      <BrowserRouter>
        <AdminDocumentTemplatesPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Document Templates')).toBeInTheDocument();
      expect(screen.getByText('No templates found.')).toBeInTheDocument();
    });
  });

  it('shows permission denied if missing permission', async () => {
    mockAuthContext.hasPermission.mockReturnValueOnce(false);
    render(
      <BrowserRouter>
        <AdminDocumentTemplatesPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Permission Denied.')).toBeInTheDocument();
    });
  });
});
