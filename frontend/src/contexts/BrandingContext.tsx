import React, { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { organizationService, type BrandingConfig } from '../services/organization';
import { useAuth } from './AuthContext';
import { applyThemeTokens, clearThemeTokens } from '../utils/themeTokens';

export type { BrandingConfig };

interface BrandingContextType {
  branding: BrandingConfig | null;
  orgId: number | null;
  loading: boolean;
  error: string | null;
  refreshBranding: () => Promise<void>;
  updateBranding: (data: Partial<BrandingConfig>) => Promise<BrandingConfig>;
  uploadLogo: (file: File) => Promise<BrandingConfig>;
  removeLogo: () => Promise<BrandingConfig>;
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
      return config;
    } catch (err: any) {
      console.error('Failed to load branding:', err);
      setError('Unable to load branding configuration');
      return null;
    } finally {
      setLoading(false);
    }
  };

  const { user } = useAuth();

  useEffect(() => {
    const init = async () => {
      if (!user) {
        setBranding(null);
        setOrgId(null);
        clearThemeTokens();
        setLoading(false);
        return;
      }

      try {
        const orgs = await organizationService.listOrganizations();
        if (orgs.length > 0) {
          const currentOrgId = orgs[0].id;
          setOrgId(currentOrgId);
          await fetchBranding(currentOrgId);
        } else {
          setBranding(null);
          clearThemeTokens();
          setLoading(false);
        }
      } catch {
        setLoading(false);
      }
    };
    init();
  }, [user]);

  useEffect(() => {
    applyThemeTokens(branding);
  }, [branding]);

  const refreshBranding = async () => {
    if (orgId) {
      await fetchBranding(orgId);
    }
  };

  const updateBranding = async (data: Partial<BrandingConfig>): Promise<BrandingConfig> => {
    if (!orgId) throw new Error('No active organization found to update branding.');
    const updated = await organizationService.updateBranding(orgId, data);
    setBranding(updated);
    return updated;
  };

  const uploadLogo = async (file: File): Promise<BrandingConfig> => {
    if (!orgId) throw new Error('No active organization found to upload logo.');
    const updated = await organizationService.uploadLogo(orgId, file);
    setBranding(updated);
    return updated;
  };

  const removeLogo = async (): Promise<BrandingConfig> => {
    if (!orgId) throw new Error('No active organization found to remove logo.');
    const updated = await organizationService.removeLogo(orgId);
    setBranding(updated);
    return updated;
  };

  return (
    <BrandingContext.Provider
      value={{
        branding,
        orgId,
        loading,
        error,
        refreshBranding,
        updateBranding,
        uploadLogo,
        removeLogo,
      }}
    >
      {children}
    </BrandingContext.Provider>
  );
};

const defaultBrandingContext: BrandingContextType = {
  branding: null,
  orgId: null,
  loading: false,
  error: null,
  refreshBranding: async () => {},
  updateBranding: async () => { throw new Error('Branding provider uninitialized'); },
  uploadLogo: async () => { throw new Error('Branding provider uninitialized'); },
  removeLogo: async () => { throw new Error('Branding provider uninitialized'); },
};

export const useBranding = () => {
  const context = useContext(BrandingContext);
  return context || defaultBrandingContext;
};
