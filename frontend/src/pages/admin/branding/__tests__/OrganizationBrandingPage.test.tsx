import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { OrganizationBrandingPage } from '../OrganizationBrandingPage';

const mockBranding = {
  branding_mode: 'default',
  logo_url: 'https://example.com/logo.png',
  primary_color: '#166534',
  secondary_color: '#15803D',
  accent_color: '#4ADE80',
  sidebar_bg_color: '#FFFFFF',
  selected_palette: 'vibrant',
  palette_suggestions: [
    {
      id: 'vibrant',
      name: 'Brand Vibrant',
      description: 'Lively and bold',
      primary_color: '#166534',
      secondary_color: '#15803D',
      accent_color: '#4ADE80',
      sidebar_bg_color: '#F0FDF4',
    },
    {
      id: 'professional',
      name: 'Modern Professional',
      description: 'Balanced, refined tones',
      primary_color: '#1E3A8A',
      secondary_color: '#1D4ED8',
      accent_color: '#60A5FA',
      sidebar_bg_color: '#F8FAFC',
    },
    {
      id: 'deep',
      name: 'Deep Focus',
      description: 'Rich deep primary shade',
      primary_color: '#064E3B',
      secondary_color: '#047857',
      accent_color: '#34D399',
      sidebar_bg_color: '#022C22',
    },
  ],
  manual_overrides: {},
};

const mockUpdateBranding = vi.fn().mockResolvedValue(mockBranding);
const mockUploadLogo = vi.fn().mockResolvedValue({
  ...mockBranding,
  logo_url: 'https://example.com/new-logo.png',
});
const mockRemoveLogo = vi.fn().mockResolvedValue({
  ...mockBranding,
  logo_url: '',
});

vi.mock('../../../../contexts/BrandingContext', () => ({
  useBranding: () => ({
    branding: mockBranding,
    loading: false,
    error: null,
    refreshBranding: vi.fn(),
    updateBranding: mockUpdateBranding,
    uploadLogo: mockUploadLogo,
    removeLogo: mockRemoveLogo,
    orgId: 1,
  }),
}));

const mockAuth = {
  user: { id: '1', firstName: 'Rudraksha', lastName: 'Singh', email: 'rudraksha@test.com' },
  hasPermission: vi.fn().mockReturnValue(true),
};

vi.mock('../../../../contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

describe('OrganizationBrandingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuth.hasPermission.mockReturnValue(true);
  });

  const renderComponent = () =>
    render(
      <BrowserRouter>
        <OrganizationBrandingPage />
      </BrowserRouter>
    );

  it('renders the branding headline and visual layout matching reference image', () => {
    renderComponent();
    expect(screen.getByText('Personalize the look & feel')).toBeInTheDocument();
    expect(
      screen.getByText(/We take your snazzy brand color and generate a custom theme/i)
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Default Theme + Logo' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Custom Theme' })).toBeInTheDocument();
    expect(screen.getByText('Start Exploring!')).toBeInTheDocument();
  });

  it('renders desktop live preview with greeting, metrics, and brand button', () => {
    renderComponent();
    expect(screen.getByText('Hi, Rudraksha')).toBeInTheDocument();
    expect(screen.getByText('Director, Human Resources')).toBeInTheDocument();
    expect(screen.getByText('Time off')).toBeInTheDocument();
    expect(screen.getByText('Vacation')).toBeInTheDocument();
    expect(screen.getByText('Sick Leave')).toBeInTheDocument();
    expect(screen.getByText('Request Time Off')).toBeInTheDocument();
    expect(screen.getByText('Employee Community')).toBeInTheDocument();
  });

  it('allows removing active logo in Mode A', async () => {
    renderComponent();
    const removeBtn = screen.getByLabelText('Remove logo');
    expect(removeBtn).toBeInTheDocument();

    fireEvent.click(removeBtn);
    expect(screen.queryByAltText('Organization Logo')).not.toBeInTheDocument();
    expect(screen.getByText('Upload logo')).toBeInTheDocument();
  });

  it('switches between Mode A and Mode B and displays color controls', async () => {
    renderComponent();
    const customModeBtn = screen.getByRole('button', { name: 'Custom Theme' });
    fireEvent.click(customModeBtn);

    // Color section should now be visible
    expect(screen.getByText('Color')).toBeInTheDocument();
    expect(screen.getByLabelText('Brand Hue Spectrum Slider')).toBeInTheDocument();
    expect(screen.getByText('Adjust Individual Colors Manually')).toBeInTheDocument();
  });

  it('allows opening manual color overrides in Mode B', async () => {
    renderComponent();
    fireEvent.click(screen.getByRole('button', { name: 'Custom Theme' }));

    const overridesBtn = screen.getByText('Adjust Individual Colors Manually');
    fireEvent.click(overridesBtn);

    expect(screen.getByText('Primary Color')).toBeInTheDocument();
    expect(screen.getByText('Secondary Color')).toBeInTheDocument();
    expect(screen.getByText('Accent Color')).toBeInTheDocument();
    expect(screen.getByText('Sidebar Background')).toBeInTheDocument();
  });

  it('saves branding configuration successfully when Start Exploring is clicked', async () => {
    renderComponent();
    fireEvent.click(screen.getByRole('button', { name: 'Custom Theme' }));

    const saveBtn = screen.getByText('Start Exploring!');
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockUpdateBranding).toHaveBeenCalledWith(
        expect.objectContaining({
          branding_mode: 'custom',
        })
      );
      expect(
        screen.getByText('Organization branding and live theme saved successfully!')
      ).toBeInTheDocument();
    });
  });

  it('shows read-only banner when user lacks branding.manage permission', () => {
    mockAuth.hasPermission.mockReturnValue(false);
    renderComponent();

    expect(
      screen.getByText(/Read-only mode: requires/i)
    ).toBeInTheDocument();
  });
});
