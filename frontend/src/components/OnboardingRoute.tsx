/**
 * OnboardingRoute — guards the /onboarding/* tree.
 *
 * Rules:
 * - Must be authenticated.
 * - User must have a candidate record (isCandidateUser returned by /portal/me/).
 * - Candidate users who go to the main app are NOT explicitly blocked here —
 *   that is handled by ProtectedRoute blocking users without employee profiles
 *   from employee-only pages.
 *
 * Loading state: show spinner while checking status.
 */
import React, { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { candidatePortalService } from '../services/candidates';

type Status = 'loading' | 'ok' | 'not-candidate' | 'not-authed';

export const OnboardingRoute: React.FC = () => {
  const { user, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<Status>('loading');

  useEffect(() => {
    if (authLoading) return;
    if (!user) { setStatus('not-authed'); return; }

    candidatePortalService.getProfile()
      .then(() => setStatus('ok'))
      .catch(() => setStatus('not-candidate'));
  }, [user, authLoading]);

  if (authLoading || status === 'loading') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', color: 'var(--color-text-muted)' }}>
        <Loader2 size={28} style={{ animation: 'spin 1s linear infinite', marginRight: '10px' }} />
        Verifying access…
      </div>
    );
  }

  if (status === 'not-authed') return <Navigate to="/login" replace />;
  if (status === 'not-candidate') return <Navigate to="/dashboard" replace />;

  return <Outlet />;
};
