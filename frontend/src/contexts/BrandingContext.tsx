import React, { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { organizationService } from '../services/organization';
import { useAuth } from './AuthContext';

export interface BrandingConfig {
  logo_url?: string;
  favicon_url?: string;
  login_banner_url?: string;
  watermark_url?: string;
  watermark_opacity?: string;
  primary_color?: string;
  secondary_color?: string;
  accent_color?: string;
  sidebar_bg_color?: string;
  default_theme_mode?: 'light' | 'dark' | 'system';
  font_family?: string;
  currency_code?: string;
  date_format?: string;
  custom_fields_schema?: any[];
}

interface BrandingContextType {
  branding: BrandingConfig | null;
  loading: boolean;
  error: string | null;
  refreshBranding: () => Promise<void>;
  updateBranding: (data: Partial<BrandingConfig>) => Promise<void>;
}

const BrandingContext = createContext<BrandingContextType | undefined>(undefined);

export const BrandingProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [branding, setBranding] = useState<BrandingConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [orgId, setOrgId] = useState<number | null>(null);

  const fetchBranding = async (organizationId: number) => {
    setLoading(true);
    try {
      const config = await organizationService.getBranding(organizationId);
      setBranding(config);
      setError(null);
    } catch (err: any) {
      console.error('Failed to load branding:', err);
      setError('Unable to load branding configuration');
    } finally {
      setLoading(false);
    }
  };

  const { user } = useAuth();

  useEffect(() => {
    const init = async () => {
      if (!user) {
        setLoading(false);
        return;
      }
      
      // Find the first available organization since user org payload doesn't contain the explicit organizationId
      try {
        const orgs = await organizationService.listOrganizations();
        if (orgs.length > 0) {
          setOrgId(orgs[0].id);
          fetchBranding(orgs[0].id);
        } else {
          setLoading(false);
        }
      } catch (e) {
        setLoading(false);
      }
    };
    init();
  }, [user]);

  useEffect(() => {
    if (branding) {
      const root = document.documentElement;
      if (branding.primary_color) root.style.setProperty('--color-primary', branding.primary_color);
      if (branding.secondary_color) root.style.setProperty('--color-secondary', branding.secondary_color);
      if (branding.accent_color) root.style.setProperty('--color-accent', branding.accent_color);
      if (branding.sidebar_bg_color) root.style.setProperty('--sidebar-bg', branding.sidebar_bg_color);
      if (branding.font_family) root.style.setProperty('--font-family', branding.font_family);
    }
  }, [branding]);

  const refreshBranding = async () => {
    if (orgId) {
      await fetchBranding(orgId);
    }
  };

  const updateBranding = async (data: Partial<BrandingConfig>) => {
    if (orgId) {
      const updated = await organizationService.updateBranding(orgId, data);
      setBranding(updated);
    }
  };

  return (
    <BrandingContext.Provider value={{ branding, loading, error, refreshBranding, updateBranding }}>
      {children}
    </BrandingContext.Provider>
  );
};

const defaultBrandingContext: BrandingContextType = {
  branding: null,
  loading: false,
  error: null,
  refreshBranding: async () => {},
  updateBranding: async () => {},
};

export const useBranding = () => {
  const context = useContext(BrandingContext);
  return context || defaultBrandingContext;
};
