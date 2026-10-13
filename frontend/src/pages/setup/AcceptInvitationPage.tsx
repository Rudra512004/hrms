import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import {
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Loader2,
  KeyRound,
  Building2,
  Mail,
  Eye,
  EyeOff,
  ArrowRight,
  LogOut,
  UserCheck,
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import {
  onboardingService,
  type InvitationVerifyResponse,
} from '../../services/onboardingService';

export const AcceptInvitationPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const isAuthenticated = Boolean(user);

  // Verification state
  const [isVerifying, setIsVerifying] = useState(true);
  const [verifyData, setVerifyData] = useState<InvitationVerifyResponse | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  // Acceptance submission state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [acceptSuccess, setAcceptSuccess] = useState<string | null>(null);
  const [acceptError, setAcceptError] = useState<string | null>(null);

  // New account form state
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');

  // Mode tab for unauthenticated user: 'new_account' vs 'existing_account'
  const [unauthMode, setUnauthMode] = useState<'new_account' | 'existing_account'>('new_account');

  // Verify token on mount
  const verifyToken = useCallback(async () => {
    if (!token) {
      setIsVerifying(false);
      setVerifyError('No invitation token found in the URL. Please verify you clicked the complete link sent to your email.');
      return;
    }

    setIsVerifying(true);
    setVerifyError(null);
    try {
      const data = await onboardingService.verifyInvitation(token);
      setVerifyData(data);
      setFirstName(data.first_name || '');
      setLastName(data.last_name || '');
    } catch (err: any) {
      setVerifyError(err.message || 'Invalid, revoked, or expired invitation token.');
    } finally {
      setIsVerifying(false);
    }
  }, [token]);

  useEffect(() => {
    verifyToken();
  }, [verifyToken]);

  // Handle acceptance for authenticated user with matching email
  const handleAuthenticatedAccept = async () => {
    setIsSubmitting(true);
    setAcceptError(null);
    try {
      const resp = await onboardingService.acceptInvitation({ token });
      setAcceptSuccess(resp.detail || 'Invitation accepted successfully! Organization Super Admin role provisioned.');
    } catch (err: any) {
      setAcceptError(err.message || 'Failed to accept invitation.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle acceptance for new user (setting password)
  const handleNewAccountAccept = async (e: React.FormEvent) => {
    e.preventDefault();
    setAcceptError(null);

    if (!password) {
      setAcceptError('Please enter a password.');
      return;
    }
    if (password.length < 8) {
      setAcceptError('Password must be at least 8 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setAcceptError('Passwords do not match.');
      return;
    }

    setIsSubmitting(true);
    try {
      const resp = await onboardingService.acceptInvitation({
        token,
        password,
        first_name: firstName.trim() || undefined,
        last_name: lastName.trim() || undefined,
      });
      setAcceptSuccess(
        resp.detail || 'Account activated and invitation accepted! Please sign in to access your organization.'
      );
    } catch (err: any) {
      if (err.status === 401 || (err.message && err.message.toLowerCase().includes('already exists'))) {
        setUnauthMode('existing_account');
        setAcceptError('An account for this email already exists. Please sign in below to accept this invitation.');
      } else {
        setAcceptError(err.message || 'Failed to activate account.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // Loading Screen
  if (isVerifying) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '80vh',
          padding: '24px',
        }}
      >
        <Loader2 size={44} className="animate-spin" style={{ color: 'var(--color-primary, #3b82f6)', marginBottom: '16px' }} />
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)', margin: '0 0 6px' }}>
          Verifying Invitation...
        </h2>
        <p style={{ color: 'var(--color-text-muted, #64748b)', margin: 0, fontSize: '0.875rem' }}>
          Validating cryptographic token and organization governance prerequisites
        </p>
      </div>
    );
  }

  // Verification Failure Screen
  if (verifyError || !verifyData) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '80vh',
          padding: '24px',
        }}
      >
        <div
          style={{
            maxWidth: '480px',
            width: '100%',
            background: 'var(--color-bg-card, #ffffff)',
            borderRadius: 'var(--radius-lg, 16px)',
            border: '1px solid var(--color-border, #e2e8f0)',
            padding: '36px 32px',
            textAlign: 'center',
            boxShadow: '0 10px 30px rgba(0,0,0,0.06)',
          }}
        >
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: '#fee2e2',
              color: '#ef4444',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 18px',
            }}
          >
            <AlertCircle size={30} />
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-text-main, #0f172a)', margin: '0 0 8px' }}>
            Invitation Invalid or Expired
          </h2>
          <p style={{ color: 'var(--color-text-muted, #64748b)', fontSize: '0.875rem', lineHeight: 1.5, marginBottom: '24px' }}>
            {verifyError || 'This invitation link is not valid or has expired. If you believe this is an error, please request a new invitation from your organization administrator.'}
          </p>
          <Link
            to="/login"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              width: '100%',
              padding: '12px 20px',
              borderRadius: 'var(--radius-md, 8px)',
              background: 'var(--color-primary, #3b82f6)',
              color: '#ffffff',
              fontWeight: 600,
              textDecoration: 'none',
              fontSize: '0.9375rem',
            }}
          >
            Return to Login
          </Link>
        </div>
      </div>
    );
  }

  // Acceptance Success Screen
  if (acceptSuccess) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '80vh',
          padding: '24px',
        }}
      >
        <div
          style={{
            maxWidth: '500px',
            width: '100%',
            background: 'var(--color-bg-card, #ffffff)',
            borderRadius: 'var(--radius-lg, 16px)',
            border: '1px solid var(--color-border, #e2e8f0)',
            padding: '40px 32px',
            textAlign: 'center',
            boxShadow: '0 12px 36px rgba(0,0,0,0.08)',
          }}
        >
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              background: '#dcfce7',
              color: '#16a34a',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 20px',
            }}
          >
            <CheckCircle2 size={36} />
          </div>

          <h2 style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--color-text-main, #0f172a)', margin: '0 0 8px' }}>
            Invitation Accepted!
          </h2>
          <p style={{ color: 'var(--color-text-muted, #64748b)', fontSize: '0.9rem', lineHeight: 1.5, marginBottom: '28px' }}>
            {acceptSuccess}
          </p>

          <button
            type="button"
            onClick={() => navigate(isAuthenticated ? '/dashboard' : '/login')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              width: '100%',
              padding: '12px 20px',
              borderRadius: 'var(--radius-md, 8px)',
              background: 'var(--color-primary, #3b82f6)',
              color: '#ffffff',
              fontWeight: 600,
              fontSize: '0.95rem',
              border: 'none',
              cursor: 'pointer',
              boxShadow: '0 4px 12px rgba(59, 130, 246, 0.25)',
            }}
          >
            {isAuthenticated ? 'Go to Dashboard' : 'Sign In Now'}
            <ArrowRight size={18} />
          </button>
        </div>
      </div>
    );
  }

  // Active Invitation Display & Acceptance Shell
  const isEmailMatch =
    isAuthenticated && user?.email && user.email.toLowerCase() === verifyData.email.toLowerCase();

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '85vh',
        padding: '24px',
      }}
    >
      <div
        style={{
          maxWidth: '520px',
          width: '100%',
          background: 'var(--color-bg-card, #ffffff)',
          borderRadius: 'var(--radius-lg, 16px)',
          border: '1px solid var(--color-border, #e2e8f0)',
          padding: '36px 32px',
          boxShadow: '0 12px 36px rgba(0,0,0,0.06)',
          display: 'flex',
          flexDirection: 'column',
          gap: '24px',
        }}
      >
        {/* Header */}
        <div style={{ textAlign: 'center' }}>
          <div
            style={{
              width: '52px',
              height: '52px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(16, 185, 129, 0.1) 100%)',
              color: 'var(--color-primary, #3b82f6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 14px',
              border: '1px solid rgba(59, 130, 246, 0.2)',
            }}
          >
            <ShieldCheck size={28} />
          </div>

          <h2 style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--color-text-main, #0f172a)', margin: '0 0 6px' }}>
            Administrator Invitation
          </h2>
          <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--color-text-muted, #64748b)' }}>
            You have been invited to govern <strong>{verifyData.organization_name}</strong>
          </p>
        </div>

        {/* Invitation Summary Card */}
        <div
          style={{
            background: 'var(--surface-control-bg, #f8fafc)',
            border: '1px solid var(--color-border, #e2e8f0)',
            borderRadius: 'var(--radius-md, 8px)',
            padding: '16px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            fontSize: '0.85rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Building2 size={18} style={{ color: 'var(--color-primary, #3b82f6)', flexShrink: 0 }} />
            <div>
              <span style={{ color: 'var(--color-text-muted, #64748b)', fontSize: '0.75rem' }}>Organization</span>
              <div style={{ fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
                {verifyData.organization_name} {verifyData.organization_code ? `(${verifyData.organization_code})` : ''}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <KeyRound size={18} style={{ color: 'var(--color-status-success, #10b981)', flexShrink: 0 }} />
            <div>
              <span style={{ color: 'var(--color-text-muted, #64748b)', fontSize: '0.75rem' }}>Role Authority</span>
              <div style={{ fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
                Super Admin (Tenant Scoped Dynamic RBAC)
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Mail size={18} style={{ color: 'var(--color-text-sub, #64748b)', flexShrink: 0 }} />
            <div>
              <span style={{ color: 'var(--color-text-muted, #64748b)', fontSize: '0.75rem' }}>Invited Recipient</span>
              <div style={{ fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
                {verifyData.first_name} {verifyData.last_name} ({verifyData.email})
              </div>
            </div>
          </div>
        </div>

        {/* Global Error Banner */}
        {acceptError && (
          <div
            style={{
              padding: '12px 16px',
              borderRadius: 'var(--radius-md, 8px)',
              background: 'var(--color-status-danger-bg, #fef2f2)',
              color: 'var(--color-status-danger, #ef4444)',
              border: '1px solid var(--color-status-danger-border, #fecaca)',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <AlertCircle size={16} />
            {acceptError}
          </div>
        )}

        {/* Scenario 1: User is Authenticated */}
        {isAuthenticated ? (
          <div>
            {isEmailMatch ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div
                  style={{
                    padding: '12px 16px',
                    borderRadius: 'var(--radius-md, 8px)',
                    background: '#f0fdf4',
                    border: '1px solid #bbf7d0',
                    color: '#166534',
                    fontSize: '0.85rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                  }}
                >
                  <UserCheck size={18} />
                  <span>
                    Authenticated as <strong>{user?.email}</strong>. Ready to accept administrator privileges.
                  </span>
                </div>

                <button
                  type="button"
                  onClick={handleAuthenticatedAccept}
                  disabled={isSubmitting}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    width: '100%',
                    padding: '12px 20px',
                    borderRadius: 'var(--radius-md, 8px)',
                    background: 'var(--color-primary, #3b82f6)',
                    color: '#ffffff',
                    fontWeight: 600,
                    fontSize: '0.95rem',
                    border: 'none',
                    cursor: isSubmitting ? 'not-allowed' : 'pointer',
                    boxShadow: '0 4px 12px rgba(59, 130, 246, 0.25)',
                  }}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 size={18} className="animate-spin" />
                      Provisioning Super Admin Role...
                    </>
                  ) : (
                    <>
                      Accept Invitation & Join Organization
                      <ArrowRight size={18} />
                    </>
                  )}
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div
                  style={{
                    padding: '14px 16px',
                    borderRadius: 'var(--radius-md, 8px)',
                    background: '#fffbeb',
                    border: '1px solid #fef3c7',
                    color: '#92400e',
                    fontSize: '0.85rem',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '10px',
                    lineHeight: 1.45,
                  }}
                >
                  <AlertCircle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    You are currently signed in as <strong>{user?.email}</strong>, but this invitation was sent to{' '}
                    <strong>{verifyData.email}</strong>. Please switch accounts to accept.
                  </div>
                </div>

                <button
                  type="button"
                  onClick={async () => {
                    await logout();
                    window.location.reload();
                  }}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    width: '100%',
                    padding: '12px 20px',
                    borderRadius: 'var(--radius-md, 8px)',
                    background: 'var(--surface-control-bg, #f1f5f9)',
                    color: 'var(--color-text-main, #0f172a)',
                    border: '1px solid var(--color-border, #cbd5e1)',
                    fontWeight: 600,
                    fontSize: '0.9rem',
                    cursor: 'pointer',
                  }}
                >
                  <LogOut size={16} />
                  Sign Out & Switch Account
                </button>
              </div>
            )}
          </div>
        ) : (
          /* Scenario 2: User is Unauthenticated */
          <div>
            {/* Tabs / Switcher between New Account & Existing Account */}
            <div
              style={{
                display: 'flex',
                background: 'var(--surface-control-bg, #f1f5f9)',
                padding: '4px',
                borderRadius: 'var(--radius-md, 8px)',
                marginBottom: '20px',
              }}
            >
              <button
                type="button"
                onClick={() => setUnauthMode('new_account')}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  fontSize: '0.8125rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: unauthMode === 'new_account' ? '#ffffff' : 'transparent',
                  color: unauthMode === 'new_account' ? 'var(--color-text-main, #0f172a)' : 'var(--color-text-muted, #64748b)',
                  boxShadow: unauthMode === 'new_account' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                }}
              >
                Set Password (New User)
              </button>
              <button
                type="button"
                onClick={() => setUnauthMode('existing_account')}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  fontSize: '0.8125rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: unauthMode === 'existing_account' ? '#ffffff' : 'transparent',
                  color: unauthMode === 'existing_account' ? 'var(--color-text-main, #0f172a)' : 'var(--color-text-muted, #64748b)',
                  boxShadow: unauthMode === 'existing_account' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                }}
              >
                Sign In (Existing User)
              </button>
            </div>

            {unauthMode === 'existing_account' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', textAlign: 'center' }}>
                <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--color-text-sub, #475569)', lineHeight: 1.5 }}>
                  If you already have an active account for <strong>{verifyData.email}</strong>, please sign in through our canonical login flow to verify your identity before accepting.
                </p>

                <button
                  type="button"
                  onClick={() => {
                    const redirectUrl = encodeURIComponent(`/invite/accept?token=${token}`);
                    navigate(`/login?redirect=${redirectUrl}`);
                  }}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    width: '100%',
                    padding: '12px 20px',
                    borderRadius: 'var(--radius-md, 8px)',
                    background: 'var(--color-primary, #3b82f6)',
                    color: '#ffffff',
                    fontWeight: 600,
                    fontSize: '0.95rem',
                    border: 'none',
                    cursor: 'pointer',
                    boxShadow: '0 4px 12px rgba(59, 130, 246, 0.25)',
                  }}
                >
                  Sign In with Existing Account
                  <ArrowRight size={18} />
                </button>
              </div>
            ) : (
              <form noValidate onSubmit={handleNewAccountAccept} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--color-text-muted, #64748b)' }}>
                  Create your password to activate your account and claim your Super Admin role.
                </p>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '4px' }}>
                      First Name
                    </label>
                    <input
                      type="text"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      className="input-neumorphic"
                      style={{ width: '100%', boxSizing: 'border-box' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '4px' }}>
                      Last Name
                    </label>
                    <input
                      type="text"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      className="input-neumorphic"
                      style={{ width: '100%', boxSizing: 'border-box' }}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '4px' }}>
                    Password (min. 8 characters) <span style={{ color: 'var(--color-status-danger, #ef4444)' }}>*</span>
                  </label>
                  <div style={{ position: 'relative' }}>
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      className="input-neumorphic"
                      style={{ width: '100%', paddingRight: '40px', boxSizing: 'border-box' }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      style={{
                        position: 'absolute',
                        right: '10px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        color: 'var(--color-text-muted, #94a3b8)',
                        cursor: 'pointer',
                      }}
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '4px' }}>
                    Confirm Password <span style={{ color: 'var(--color-status-danger, #ef4444)' }}>*</span>
                  </label>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••"
                    className="input-neumorphic"
                    style={{ width: '100%', boxSizing: 'border-box' }}
                  />
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    width: '100%',
                    padding: '12px 20px',
                    borderRadius: 'var(--radius-md, 8px)',
                    background: 'var(--color-primary, #3b82f6)',
                    color: '#ffffff',
                    fontWeight: 600,
                    fontSize: '0.95rem',
                    border: 'none',
                    cursor: isSubmitting ? 'not-allowed' : 'pointer',
                    boxShadow: '0 4px 12px rgba(59, 130, 246, 0.25)',
                    marginTop: '8px',
                  }}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 size={18} className="animate-spin" />
                      Activating Account & Accepting...
                    </>
                  ) : (
                    <>
                      Create Password & Accept
                      <ArrowRight size={18} />
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
