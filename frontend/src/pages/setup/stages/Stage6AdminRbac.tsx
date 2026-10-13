import React, { useState } from 'react';
import {
  ShieldCheck,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  AlertCircle,
  KeyRound,
  UserCheck,
  Mail,
  UserPlus,
  RefreshCw,
  XCircle,
  Clock,
  Send,
} from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import {
  onboardingService,
  type Stage6Payload,
} from '../../../services/onboardingService';

interface Stage6AdminRbacProps {
  initialData?: any;
  isSubmitting: boolean;
  onBack: () => void;
  onSubmit: (data: Stage6Payload) => void;
  fieldErrors?: Record<string, string[]>;
}

export const Stage6AdminRbac: React.FC<Stage6AdminRbacProps> = ({
  initialData,
  isSubmitting,
  onBack,
  onSubmit,
  fieldErrors = {},
}) => {
  const { user } = useAuth();

  // Mode selection: 'self' (Option A) vs 'invite' (Option B)
  const defaultMode = initialData?.assignment_type === 'invite' ? 'invite' : 'self';
  const [assignmentMode, setAssignmentMode] = useState<'self' | 'invite'>(defaultMode);

  // Option A state
  const [confirmedSelf, setConfirmedSelf] = useState<boolean>(true);

  // Option B state
  const [inviteeFirstName, setInviteeFirstName] = useState<string>(
    initialData?.invitee_first_name || initialData?.first_name || ''
  );
  const [inviteeLastName, setInviteeLastName] = useState<string>(
    initialData?.invitee_last_name || initialData?.last_name || ''
  );
  const [inviteeEmail, setInviteeEmail] = useState<string>(
    initialData?.invitee_email || initialData?.email || ''
  );

  // Pending invitation tracking (from initialData or recent actions)
  const [pendingInvitation, setPendingInvitation] = useState<any>(() => {
    if (initialData?.invitation_id || initialData?.assignment_type === 'invite') {
      return {
        id: initialData.invitation_id,
        email: initialData.invitee_email || initialData.email,
        name: initialData.invitee_name || `${initialData.first_name || ''} ${initialData.last_name || ''}`.trim(),
        status: initialData.invitation_status || 'pending',
        deliveryStatus: initialData.email_delivery_status || 'pending',
        expiresAt: initialData.expires_at,
        resendCount: initialData.resend_count || 0,
      };
    }
    return null;
  });

  const [resending, setResending] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  // Resend handler
  const handleResendInvitation = async () => {
    setResending(true);
    setActionMessage(null);
    setLocalError(null);
    try {
      const resp = await onboardingService.resendStage6Invitation();
      setPendingInvitation((prev: any) => ({
        ...prev,
        status: resp.status,
        deliveryStatus: resp.email_delivery_status,
        expiresAt: resp.expires_at,
        resendCount: resp.resend_count,
      }));
      setActionMessage({
        type: 'success',
        text: `Invitation resent successfully to ${resp.email}. A new single-use link has been dispatched.`,
      });
    } catch (err: any) {
      setActionMessage({
        type: 'error',
        text: err.message || 'Failed to resend invitation.',
      });
    } finally {
      setResending(false);
    }
  };

  // Revoke handler
  const handleRevokeInvitation = async () => {
    if (!window.confirm('Are you sure you want to revoke this administrator invitation? The link will be permanently invalidated.')) {
      return;
    }
    setRevoking(true);
    setActionMessage(null);
    setLocalError(null);
    try {
      const resp = await onboardingService.revokeStage6Invitation();
      setPendingInvitation((prev: any) => ({
        ...prev,
        status: resp.status,
      }));
      setActionMessage({
        type: 'success',
        text: 'Invitation has been revoked. You can assign yourself or invite another administrator.',
      });
    } catch (err: any) {
      setActionMessage({
        type: 'error',
        text: err.message || 'Failed to revoke invitation.',
      });
    } finally {
      setRevoking(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    setActionMessage(null);

    if (assignmentMode === 'self') {
      if (!confirmedSelf) {
        setLocalError('You must confirm administrator assignment to proceed.');
        return;
      }
      onSubmit({
        confirm: true,
      });
    } else {
      const cleanEmail = inviteeEmail.trim().toLowerCase();
      const cleanFirstName = inviteeFirstName.trim();
      const cleanLastName = inviteeLastName.trim();

      if (!cleanFirstName) {
        setLocalError('First name is required for the invited administrator.');
        return;
      }
      if (!cleanEmail) {
        setLocalError('A valid email address is required for the invited administrator.');
        return;
      }
      if (!cleanEmail.includes('@') || !cleanEmail.includes('.')) {
        setLocalError('Please enter a valid email address.');
        return;
      }
      if (user?.email && cleanEmail === user.email.toLowerCase()) {
        setLocalError('You cannot invite your own email address. Use Option A to assign yourself as Super Admin.');
        return;
      }

      onSubmit({
        assignment_type: 'invite',
        first_name: cleanFirstName,
        last_name: cleanLastName,
        email: cleanEmail,
      });
    }
  };

  const getCombinedFieldError = (field: string): string | null => {
    if (fieldErrors[field] && fieldErrors[field].length > 0) {
      return fieldErrors[field][0];
    }
    return null;
  };

  return (
    <form noValidate onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* Intro Governance Banner */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(59, 130, 246, 0.04) 100%)',
          border: '1px solid rgba(16, 185, 129, 0.2)',
          borderRadius: 'var(--radius-md, 8px)',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '12px',
        }}
      >
        <ShieldCheck size={24} style={{ color: 'var(--color-status-success, #10b981)', flexShrink: 0, marginTop: '2px' }} />
        <div>
          <h3 style={{ margin: '0 0 4px', fontSize: '0.95rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
            Initial Administrator & Dynamic RBAC Governance
          </h3>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--color-text-sub, #475569)', lineHeight: 1.5 }}>
            Every organization requires an authoritative, organization-scoped <strong>Super Admin</strong>. This role grants all 144 canonical permissions across company modules while strictly preserving multi-tenant isolation and zero global Django privilege escalation.
          </p>
        </div>
      </div>

      {/* Action Messages or Local Errors */}
      {actionMessage && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: 'var(--radius-md, 8px)',
            background: actionMessage.type === 'success' ? '#f0fdf4' : '#fef2f2',
            color: actionMessage.type === 'success' ? '#166534' : '#b91c1c',
            border: `1px solid ${actionMessage.type === 'success' ? '#bbf7d0' : '#fecaca'}`,
            fontSize: '0.875rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          {actionMessage.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
          {actionMessage.text}
        </div>
      )}

      {localError && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: 'var(--radius-md, 8px)',
            background: 'var(--color-status-danger-bg, #fef2f2)',
            color: 'var(--color-status-danger, #ef4444)',
            border: '1px solid var(--color-status-danger-border, #fecaca)',
            fontSize: '0.875rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <AlertCircle size={16} />
          {localError}
        </div>
      )}

      {/* Option Selection Radio Tiles */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        {/* Option A: Self Assignment */}
        <div
          onClick={() => setAssignmentMode('self')}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setAssignmentMode('self'); }}
          style={{
            border: assignmentMode === 'self'
              ? '2px solid var(--color-primary, #3b82f6)'
              : '1px solid var(--color-border, #e2e8f0)',
            background: assignmentMode === 'self'
              ? 'rgba(59, 130, 246, 0.04)'
              : 'var(--surface-control-bg, #f8fafc)',
            borderRadius: 'var(--radius-lg, 12px)',
            padding: '18px 20px',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <UserCheck size={20} style={{ color: assignmentMode === 'self' ? 'var(--color-primary, #3b82f6)' : 'var(--color-text-muted, #64748b)' }} />
              <span style={{ fontWeight: 700, fontSize: '0.9375rem', color: 'var(--color-text-main, #0f172a)' }}>
                Option A: Assign Myself
              </span>
            </div>
            <input
              type="radio"
              name="assignmentMode"
              checked={assignmentMode === 'self'}
              onChange={() => setAssignmentMode('self')}
              style={{ accentColor: 'var(--color-primary, #3b82f6)', cursor: 'pointer' }}
            />
          </div>
          <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--color-text-sub, #475569)', lineHeight: 1.45 }}>
            Assign your verified account ({user?.email}) as the initial organization Super Admin. Recommended if you manage this company directly.
          </p>
        </div>

        {/* Option B: Invite Administrator */}
        <div
          onClick={() => setAssignmentMode('invite')}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setAssignmentMode('invite'); }}
          style={{
            border: assignmentMode === 'invite'
              ? '2px solid var(--color-primary, #3b82f6)'
              : '1px solid var(--color-border, #e2e8f0)',
            background: assignmentMode === 'invite'
              ? 'rgba(59, 130, 246, 0.04)'
              : 'var(--surface-control-bg, #f8fafc)',
            borderRadius: 'var(--radius-lg, 12px)',
            padding: '18px 20px',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <UserPlus size={20} style={{ color: assignmentMode === 'invite' ? 'var(--color-primary, #3b82f6)' : 'var(--color-text-muted, #64748b)' }} />
              <span style={{ fontWeight: 700, fontSize: '0.9375rem', color: 'var(--color-text-main, #0f172a)' }}>
                Option B: Invite Administrator
              </span>
            </div>
            <input
              type="radio"
              name="assignmentMode"
              checked={assignmentMode === 'invite'}
              onChange={() => setAssignmentMode('invite')}
              style={{ accentColor: 'var(--color-primary, #3b82f6)', cursor: 'pointer' }}
            />
          </div>
          <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--color-text-sub, #475569)', lineHeight: 1.45 }}>
            Send an email invitation with a secure, single-use activation link to another designated administrator. You retain setup authority.
          </p>
        </div>
      </div>

      {/* Mode A: Self-Assignment Details */}
      {assignmentMode === 'self' && (
        <div
          style={{
            border: '1px solid var(--color-border, #e2e8f0)',
            borderRadius: 'var(--radius-lg, 12px)',
            background: 'var(--surface-control-bg, #f8fafc)',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
          }}
        >
          <h4 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 700, color: 'var(--color-text-main, #0f172a)' }}>
            Assigned Authority Profile
          </h4>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
            <div
              style={{
                padding: '14px 18px',
                borderRadius: 'var(--radius-md, 8px)',
                background: '#ffffff',
                border: '1px solid var(--color-border-subtle, #e2e8f0)',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
              }}
            >
              <UserCheck size={20} style={{ color: 'var(--color-primary, #3b82f6)' }} />
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #64748b)' }}>Target Administrator</div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-main, #0f172a)' }}>
                  {user?.firstName} {user?.lastName} ({user?.email})
                </div>
              </div>
            </div>

            <div
              style={{
                padding: '14px 18px',
                borderRadius: 'var(--radius-md, 8px)',
                background: '#ffffff',
                border: '1px solid var(--color-border-subtle, #e2e8f0)',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
              }}
            >
              <KeyRound size={20} style={{ color: 'var(--color-status-success, #10b981)' }} />
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #64748b)' }}>Assigned System Role</div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-main, #0f172a)' }}>
                  super-admin (Tenant Scoped)
                </div>
              </div>
            </div>
          </div>

          {/* Security Invariants Checklist */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8125rem', color: 'var(--color-text-sub, #475569)' }}>
              <CheckCircle2 size={16} color="var(--color-status-success, #10b981)" />
              <span>Dynamic RBAC: Bound strictly to this tenant organization boundary.</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8125rem', color: 'var(--color-text-sub, #475569)' }}>
              <CheckCircle2 size={16} color="var(--color-status-success, #10b981)" />
              <span>Canonical Permissions: Grants access to manage departments, shifts, attendance, leaves, and employees.</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8125rem', color: 'var(--color-text-sub, #475569)' }}>
              <CheckCircle2 size={16} color="var(--color-status-success, #10b981)" />
              <span>Zero Global Escalation: Does not grant global Django superuser access.</span>
            </div>
          </div>

          {/* Self Confirmation Checkbox */}
          <div
            style={{
              padding: '14px 18px',
              borderRadius: 'var(--radius-md, 8px)',
              border: '1.5px solid var(--color-primary-alpha, rgba(59, 130, 246, 0.3))',
              background: 'var(--color-primary-light, rgba(59, 130, 246, 0.05))',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              marginTop: '4px',
            }}
          >
            <input
              id="confirm-admin"
              type="checkbox"
              checked={confirmedSelf}
              onChange={(e) => setConfirmedSelf(e.target.checked)}
              style={{ width: '18px', height: '18px', accentColor: 'var(--color-primary, #3b82f6)', cursor: 'pointer' }}
            />
            <label htmlFor="confirm-admin" style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)', cursor: 'pointer' }}>
              I confirm and authorize provisioning of the initial organization Super Admin role to my verified account.
            </label>
          </div>
        </div>
      )}

      {/* Mode B: Email Invitation Form */}
      {assignmentMode === 'invite' && (
        <div
          style={{
            border: '1px solid var(--color-border, #e2e8f0)',
            borderRadius: 'var(--radius-lg, 12px)',
            background: 'var(--surface-control-bg, #f8fafc)',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
            <h4 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 700, color: 'var(--color-text-main, #0f172a)' }}>
              Administrator Invitation Details
            </h4>
            <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted, #64748b)' }}>
              Link validity: 7 days
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
            <div>
              <label htmlFor="invitee-first-name" style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '6px', color: 'var(--color-text-main, #0f172a)' }}>
                First Name <span style={{ color: 'var(--color-status-danger, #ef4444)' }}>*</span>
              </label>
              <input
                id="invitee-first-name"
                type="text"
                value={inviteeFirstName}
                onChange={(e) => setInviteeFirstName(e.target.value)}
                placeholder="e.g. Jane"
                className="input-neumorphic"
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
              {getCombinedFieldError('first_name') && (
                <div style={{ color: 'var(--color-status-danger, #ef4444)', fontSize: '0.75rem', marginTop: '4px' }}>
                  {getCombinedFieldError('first_name')}
                </div>
              )}
            </div>

            <div>
              <label htmlFor="invitee-last-name" style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '6px', color: 'var(--color-text-main, #0f172a)' }}>
                Last Name
              </label>
              <input
                id="invitee-last-name"
                type="text"
                value={inviteeLastName}
                onChange={(e) => setInviteeLastName(e.target.value)}
                placeholder="e.g. Smith"
                className="input-neumorphic"
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
              {getCombinedFieldError('last_name') && (
                <div style={{ color: 'var(--color-status-danger, #ef4444)', fontSize: '0.75rem', marginTop: '4px' }}>
                  {getCombinedFieldError('last_name')}
                </div>
              )}
            </div>
          </div>

          <div>
            <label htmlFor="invitee-email" style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '6px', color: 'var(--color-text-main, #0f172a)' }}>
              Work Email Address <span style={{ color: 'var(--color-status-danger, #ef4444)' }}>*</span>
            </label>
            <div style={{ position: 'relative' }}>
              <input
                id="invitee-email"
                type="email"
                value={inviteeEmail}
                onChange={(e) => setInviteeEmail(e.target.value)}
                placeholder="jane.smith@company.com"
                className="input-neumorphic"
                style={{ width: '100%', paddingLeft: '36px', boxSizing: 'border-box' }}
              />
              <Mail size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-muted, #94a3b8)' }} />
            </div>
            {getCombinedFieldError('email') && (
              <div style={{ color: 'var(--color-status-danger, #ef4444)', fontSize: '0.75rem', marginTop: '4px' }}>
                {getCombinedFieldError('email')}
              </div>
            )}
          </div>

          <div
            style={{
              padding: '12px 16px',
              borderRadius: 'var(--radius-md, 8px)',
              background: '#eff6ff',
              border: '1px solid #dbeafe',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
              fontSize: '0.8125rem',
              color: '#1e40af',
              lineHeight: 1.45,
            }}
          >
            <Send size={16} style={{ flexShrink: 0, marginTop: '2px', color: '#3b82f6' }} />
            <div>
              An invitation email containing a cryptographically secure, single-use activation link will be dispatched upon submitting this stage.
              The recipient will be granted the tenant Super Admin role once they accept the invitation.
            </div>
          </div>
        </div>
      )}

      {/* Pending Invitation Tracker Card (if an invitation is active) */}
      {pendingInvitation && pendingInvitation.status === 'pending' && (
        <div
          style={{
            border: '1px solid #bfdbfe',
            borderRadius: 'var(--radius-lg, 12px)',
            background: 'linear-gradient(180deg, #f8fafc 0%, #eff6ff 100%)',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Clock size={18} style={{ color: '#2563eb' }} />
              <h4 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 700, color: '#1e3a8a' }}>
                Pending Administrator Invitation
              </h4>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {/* Delivery Status Badge */}
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '4px 10px',
                  borderRadius: '12px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  background:
                    pendingInvitation.deliveryStatus === 'sent'
                      ? '#dcfce7'
                      : pendingInvitation.deliveryStatus === 'failed'
                      ? '#fee2e2'
                      : '#fef3c7',
                  color:
                    pendingInvitation.deliveryStatus === 'sent'
                      ? '#166534'
                      : pendingInvitation.deliveryStatus === 'failed'
                      ? '#991b1b'
                      : '#92400e',
                }}
              >
                {pendingInvitation.deliveryStatus === 'sent' ? 'Email Dispatched' : pendingInvitation.deliveryStatus === 'failed' ? 'Email Failed' : 'Queued'}
              </span>

              {/* Status Badge */}
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  padding: '4px 10px',
                  borderRadius: '12px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  background: '#dbeafe',
                  color: '#1e40af',
                }}
              >
                Pending Acceptance
              </span>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', fontSize: '0.85rem' }}>
            <div>
              <div style={{ color: 'var(--color-text-muted, #64748b)', fontSize: '0.75rem' }}>Recipient</div>
              <div style={{ fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
                {pendingInvitation.name || pendingInvitation.email} ({pendingInvitation.email})
              </div>
            </div>

            <div>
              <div style={{ color: 'var(--color-text-muted, #64748b)', fontSize: '0.75rem' }}>Expires At</div>
              <div style={{ fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
                {pendingInvitation.expiresAt ? new Date(pendingInvitation.expiresAt).toLocaleDateString(undefined, {
                  month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
                }) : 'In 7 days'}
              </div>
            </div>

            {pendingInvitation.resendCount > 0 && (
              <div>
                <div style={{ color: 'var(--color-text-muted, #64748b)', fontSize: '0.75rem' }}>Resend Count</div>
                <div style={{ fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
                  {pendingInvitation.resendCount} times
                </div>
              </div>
            )}
          </div>

          {/* Action Buttons for Pending Invitation */}
          <div style={{ display: 'flex', gap: '10px', marginTop: '6px', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={handleResendInvitation}
              disabled={resending || revoking}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                background: '#ffffff',
                border: '1px solid #93c5fd',
                color: '#1d4ed8',
                fontSize: '0.8125rem',
                fontWeight: 600,
                cursor: resending || revoking ? 'not-allowed' : 'pointer',
              }}
            >
              <RefreshCw size={14} className={resending ? 'animate-spin' : ''} />
              {resending ? 'Resending...' : 'Resend Invitation Email'}
            </button>

            <button
              type="button"
              onClick={handleRevokeInvitation}
              disabled={resending || revoking}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                background: '#ffffff',
                border: '1px solid #fca5a5',
                color: '#b91c1c',
                fontSize: '0.8125rem',
                fontWeight: 600,
                cursor: resending || revoking ? 'not-allowed' : 'pointer',
              }}
            >
              <XCircle size={14} />
              {revoking ? 'Revoking...' : 'Revoke Invitation'}
            </button>
          </div>
        </div>
      )}

      {/* Form Action Footer */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderTop: '1px solid var(--color-border, #e2e8f0)',
          paddingTop: '20px',
        }}
      >
        <button
          type="button"
          onClick={onBack}
          disabled={isSubmitting}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 20px',
            borderRadius: 'var(--radius-md, 8px)',
            background: 'var(--surface-control-bg, #f1f5f9)',
            color: 'var(--color-text-main, #0f172a)',
            border: '1px solid var(--color-border, #cbd5e1)',
            fontSize: '0.9375rem',
            fontWeight: 600,
            cursor: isSubmitting ? 'not-allowed' : 'pointer',
          }}
        >
          <ArrowLeft size={18} />
          Back to Shifts
        </button>

        <button
          type="submit"
          disabled={isSubmitting || (assignmentMode === 'self' && !confirmedSelf)}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 24px',
            borderRadius: 'var(--radius-md, 8px)',
            background: 'var(--color-primary, #3b82f6)',
            color: '#ffffff',
            border: 'none',
            fontSize: '0.9375rem',
            fontWeight: 600,
            cursor: isSubmitting ? 'not-allowed' : 'pointer',
            opacity: assignmentMode === 'self' && !confirmedSelf ? 0.6 : 1,
            boxShadow: '0 4px 12px rgba(59, 130, 246, 0.25)',
          }}
        >
          {isSubmitting
            ? assignmentMode === 'self'
              ? 'Provisioning Roles...'
              : 'Sending Invitation...'
            : assignmentMode === 'self'
            ? 'Continue to Final Review'
            : 'Send Invitation & Continue to Final Review'}
          <ArrowRight size={18} />
        </button>
      </div>
    </form>
  );
};
