import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, type ReactNode } from 'react';
import { organizationService, type Branch } from '../services/organization';
import { useAuth } from './AuthContext';

export type BranchSelection =
  | { type: 'all' }
  | { type: 'branch'; branchId: number; branch?: Branch };

export interface BranchContextType {
  selectedBranch: BranchSelection;
  branchId: number | null;
  branches: Branch[];
  isLoading: boolean;
  error: string | null;
  selectBranch: (selection: BranchSelection | number | 'all') => void;
  refreshBranches: () => Promise<void>;
}

const BranchContext = createContext<BranchContextType | undefined>(undefined);

export const BRANCH_STORAGE_KEY = 'hrms_selected_branch_id';

export const BranchProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<BranchSelection>({ type: 'all' });
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadBranches = useCallback(async () => {
    // If no authenticated user session, reset branch context
    const token = localStorage.getItem('auth_token');
    if (!token || !user) {
      setBranches([]);
      setSelectedBranch({ type: 'all' });
      setIsLoading(false);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const authorizedBranches = await organizationService.listBranches();
      const branchList = Array.isArray(authorizedBranches) ? authorizedBranches : [];
      setBranches(branchList);

      // Validate persisted branch against freshly loaded authorized branches
      const persisted = localStorage.getItem(BRANCH_STORAGE_KEY);
      if (persisted && persisted !== 'all') {
        const parsedId = parseInt(persisted, 10);
        if (!isNaN(parsedId)) {
          const matchedBranch = branchList.find((b) => b.id === parsedId);
          if (matchedBranch) {
            setSelectedBranch({
              type: 'branch',
              branchId: matchedBranch.id,
              branch: matchedBranch,
            });
            return;
          }
        }
      }

      // Safe fallback to 'all' if no valid persisted branch or if persisted branch is unauthorized
      setSelectedBranch({ type: 'all' });
      localStorage.setItem(BRANCH_STORAGE_KEY, 'all');
    } catch (err: any) {
      // Graceful error handling for 403 or network failure without crashing
      const message = err?.errorData?.detail || err?.message || 'Failed to load authorized branches';
      setError(message);
      setBranches([]);
      setSelectedBranch({ type: 'all' });
      localStorage.setItem(BRANCH_STORAGE_KEY, 'all');
    } finally {
      setIsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadBranches();
  }, [loadBranches]);

  const selectBranch = useCallback(
    (selection: BranchSelection | number | 'all') => {
      if (selection === 'all') {
        setSelectedBranch({ type: 'all' });
        localStorage.setItem(BRANCH_STORAGE_KEY, 'all');
        return;
      }

      const targetId = typeof selection === 'number' ? selection : selection.type === 'branch' ? selection.branchId : null;

      if (targetId === null) {
        setSelectedBranch({ type: 'all' });
        localStorage.setItem(BRANCH_STORAGE_KEY, 'all');
        return;
      }

      // Security check: Never trust arbitrary branch IDs without validation
      const matched = branches.find((b) => b.id === targetId);
      if (matched) {
        setSelectedBranch({
          type: 'branch',
          branchId: matched.id,
          branch: matched,
        });
        localStorage.setItem(BRANCH_STORAGE_KEY, String(matched.id));
      } else {
        // Unauthorized or invalid branch ID -> safely fall back to 'all'
        setSelectedBranch({ type: 'all' });
        localStorage.setItem(BRANCH_STORAGE_KEY, 'all');
      }
    },
    [branches]
  );

  const branchId = useMemo(() => {
    return selectedBranch.type === 'branch' ? selectedBranch.branchId : null;
  }, [selectedBranch]);

  const contextValue = useMemo<BranchContextType>(
    () => ({
      selectedBranch,
      branchId,
      branches,
      isLoading,
      error,
      selectBranch,
      refreshBranches: loadBranches,
    }),
    [selectedBranch, branchId, branches, isLoading, error, selectBranch, loadBranches]
  );

  return <BranchContext.Provider value={contextValue}>{children}</BranchContext.Provider>;
};

export const useBranchContext = (): BranchContextType => {
  const context = useContext(BranchContext);
  if (!context) {
    throw new Error('useBranchContext must be used within a BranchProvider');
  }
  return context;
};
