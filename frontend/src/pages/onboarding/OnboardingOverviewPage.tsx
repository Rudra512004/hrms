/**
 * Candidate onboarding portal — Overview / Status dashboard.
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle, Upload, FileText, ChevronRight, Send, XCircle } from 'lucide-react';
import { candidatePortalService, type CandidatePortalProfile } from '../../services/candidates';

const STEPS = [
  { status: 'offered',    label: 'Offer Received',     desc: 'Your offer letter has been sent.' },
  { status: 'onboarding', label: 'Documents Upload',   desc: 'Upload required onboarding documents.' },
  { status: 'submitted',  label: 'Submitted for Review', desc: 'HR is reviewing your submission.' },
  { status: 'verifying',  label: 'Under Verification', desc: 'Your documents are being verified.' },
  { status: 'approved',   label: 'Approved',           desc: 'Congratulations! Your application is approved.' },
  { status: 'converted',  label: 'Employee Onboarded', desc: 'You are now a member of our team.' },
];

function StepItem({ step, current, idx }: { step: typeof STEPS[0]; current: string; idx: number }) {
  const allStatuses = STEPS.map(s => s.status);
  const currentIdx  = allStatuses.indexOf(current);
  const isDone   = idx < currentIdx;
  const isActive = idx === currentIdx;
  const color    = isDone || isActive ? 'var(--color-primary)' : 'var(--color-text-muted)';

  return (
    <div style={{ display: 'flex', gap: '14px', marginBottom: '16px', opacity: (!isDone && !isActive) ? 0.5 : 1 }}>
      <div style={{
        width: '32px', height: '32px', borderRadius: '50%',
        border: `2px solid ${color}`, display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: color, flexShrink: 0,
        background: isDone ? 'var(--color-primary)' : 'transparent',
      }}>
        {isDone ? <CheckCircle size={16} color="#fff" /> : <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>{idx + 1}</span>}
      </div>
      <div>
        <div style={{ fontWeight: isActive ? 700 : 500, color: 'var(--color-text-main)', fontSize: '0.9rem' }}>
          {step.label}
          {isActive && <span style={{ marginLeft: '8px', fontSize: '0.75rem', background: 'var(--color-primary)', color: '#fff', padding: '2px 8px', borderRadius: '99px' }}>Current</span>}
        </div>
        <div style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem', marginTop: '2px' }}>
          {step.desc}
        </div>
      </div>
    </div>
  );
}

export const OnboardingOverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<CandidatePortalProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [submitSuccess, setSubmitSuccess] = useState('');

  useEffect(() => {
    candidatePortalService.getProfile()
      .then(setProfile)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleSubmit = async () => {
    setSubmitError('');
    setSubmitSuccess('');
    setSubmitLoading(true);
    try {
      const res = await candidatePortalService.submitOnboarding();
      setSubmitSuccess(res.detail);
      setProfile(p => p ? { ...p, status: 'submitted' as any } : p);
    } catch (err: any) {
      setSubmitError(err.message || 'Submission failed.');
    } finally {
      setSubmitLoading(false);
    }
  };

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '60px', color: 'var(--color-text-muted)' }}>Loading…</div>;
  }

  if (!profile) {
    return <div style={{ textAlign: 'center', padding: '60px', color: '#ef4444' }}>Failed to load profile.</div>;
  }

  if (profile.status === 'rejected') {
    return (
      <div style={{ textAlign: 'center', padding: '60px' }}>
        <XCircle size={48} style={{ color: '#ef4444', marginBottom: '16px' }} />
        <h2 style={{ color: '#ef4444', margin: '0 0 8px' }}>Application Not Successful</h2>
        <p style={{ color: 'var(--color-text-muted)' }}>Please contact HR for further information.</p>
      </div>
    );
  }

  const showSubmitBtn = profile.status === 'onboarding';

  return (
    <div style={{ maxWidth: '700px' }}>
      <h1 style={{ margin: '0 0 4px', fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
        Welcome, {profile.first_name}!
      </h1>
      <p style={{ margin: '0 0 28px', color: 'var(--color-text-muted)' }}>
        Here's your onboarding progress.
      </p>

      {/* Progress card */}
      <div style={{
        background: 'var(--color-bg-card)', borderRadius: '12px',
        border: '1px solid var(--color-border)', padding: '24px',
        marginBottom: '20px',
      }}>
        <h2 style={{ margin: '0 0 20px', fontSize: '1rem', fontWeight: 700 }}>Onboarding Progress</h2>
        {STEPS.map((step, idx) => (
          <StepItem key={step.status} step={step} current={profile.status} idx={idx} />
        ))}
      </div>

      {/* Quick actions */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px', marginBottom: '20px' }}>
        {[
          { icon: Upload, label: 'Upload Documents', path: '/onboarding/documents', enabled: ['offered','onboarding','submitted'].includes(profile.status) },
          { icon: FileText, label: 'View My Letters', path: '/onboarding/letters', enabled: true },
        ].map(card => (
          <button
            key={card.path}
            onClick={() => card.enabled && navigate(card.path)}
            disabled={!card.enabled}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '16px', border: '1px solid var(--color-border)',
              borderRadius: '10px', background: 'var(--color-bg-card)',
              cursor: card.enabled ? 'pointer' : 'not-allowed',
              opacity: card.enabled ? 1 : 0.5, transition: 'all 0.15s',
              textAlign: 'left',
            }}
            onMouseEnter={e => card.enabled && (e.currentTarget.style.borderColor = 'var(--color-primary)')}
            onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <card.icon size={20} style={{ color: 'var(--color-primary)' }} />
              <span style={{ fontWeight: 500, fontSize: '0.875rem', color: 'var(--color-text-main)' }}>
                {card.label}
              </span>
            </div>
            <ChevronRight size={14} style={{ color: 'var(--color-text-muted)' }} />
          </button>
        ))}
      </div>

      {/* Submit button */}
      {showSubmitBtn && (
        <div style={{
          background: 'var(--color-bg-card)', borderRadius: '10px',
          border: '1px solid var(--color-border)', padding: '20px',
        }}>
          <h3 style={{ margin: '0 0 8px', fontSize: '0.95rem' }}>Ready to Submit?</h3>
          <p style={{ margin: '0 0 14px', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
            Once you've uploaded all required documents, submit your onboarding for HR review.
          </p>
          {submitError && <div style={{ color: '#ef4444', marginBottom: '10px', fontSize: '0.875rem' }}>{submitError}</div>}
          {submitSuccess && <div style={{ color: 'var(--color-beyondsure-green)', marginBottom: '10px', fontSize: '0.875rem' }}>{submitSuccess}</div>}
          <button
            onClick={handleSubmit}
            disabled={submitLoading}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '10px 20px', border: 'none', borderRadius: '8px',
              background: 'var(--color-primary)', color: '#fff',
              cursor: submitLoading ? 'not-allowed' : 'pointer', fontWeight: 600,
              opacity: submitLoading ? 0.7 : 1,
            }}
          >
            <Send size={14} />
            {submitLoading ? 'Submitting…' : 'Submit Onboarding'}
          </button>
        </div>
      )}
    </div>
  );
};
