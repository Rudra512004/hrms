import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Loader2,
  AlertCircle,
  CheckCircle2,
  ArrowRight,
} from 'lucide-react';
import {
  onboardingService,
  OnboardingApiError,
  type WizardStatusResponse,
} from '../../services/onboardingService';
import { WizardHeader } from './stages/WizardHeader';
import { WizardStepper } from './stages/WizardStepper';
import { WIZARD_STEPS } from './types';
import { Stage1OrgDetails } from './stages/Stage1OrgDetails';
import { Stage2Branch } from './stages/Stage2Branch';
import { Stage3Structure } from './stages/Stage3Structure';
import { Stage4Calendar } from './stages/Stage4Calendar';
import { Stage5ShiftsPolicy } from './stages/Stage5ShiftsPolicy';
import { Stage6AdminRbac } from './stages/Stage6AdminRbac';
import { Stage7ReviewComplete } from './stages/Stage7ReviewComplete';

export const OrganizationSetupWizardPage: React.FC = () => {
  const { stageNumber: urlStageParam } = useParams<{ stageNumber?: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [draftSavedTime, setDraftSavedTime] = useState<string | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [statusData, setStatusData] = useState<WizardStatusResponse | null>(null);
  const [completedCelebration, setCompletedCelebration] = useState(false);

  // Active stage derived from route or onboarding status
  const currentStage = Math.max(
    1,
    Math.min(7, urlStageParam ? parseInt(urlStageParam, 10) || 1 : statusData?.current_stage || 1)
  );

  const completedStages = useMemo(() => statusData?.completed_stages || [], [statusData?.completed_stages]);

  // Load status on mount
  const loadStatus = useCallback(async () => {
    setLoading(true);
    setGlobalError(null);
    try {
      const data = await onboardingService.getStatus();
      setStatusData(data);

      if (data.status === 'completed') {
        // If already completed, set celebration flag
        setCompletedCelebration(true);
      } else if (!urlStageParam) {
        // If navigating to base /setup, route to current incomplete stage
        navigate(`/setup/${data.current_stage || 1}`, { replace: true });
      }
    } catch (err: any) {
      if (err.status === 400 || err.status === 404) {
        // No onboarding session yet — ready to start Stage 1
        if (!urlStageParam) {
          navigate('/setup/1', { replace: true });
        }
      } else {
        setGlobalError(err.message || 'Failed to query onboarding state.');
      }
    } finally {
      setLoading(false);
    }
  }, [navigate, urlStageParam]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  // Stage route guard: ensure user doesn't skip uncompleted stages
  useEffect(() => {
    if (!loading && statusData && statusData.status !== 'completed') {
      const maxAllowed = Math.max(...completedStages, 0) + 1;
      if (currentStage > maxAllowed) {
        setGlobalError(
          `Cannot jump to Stage ${currentStage}. Please complete preceding stage ${maxAllowed} first.`
        );
        navigate(`/setup/${maxAllowed}`, { replace: true });
      }
    }
  }, [currentStage, completedStages, loading, statusData, navigate]);

  const handleStageNavigation = (targetStage: number) => {
    setGlobalError(null);
    setFieldErrors({});
    navigate(`/setup/${targetStage}`);
  };

  // Draft saving
  const handleSaveDraft = async () => {
    setIsSavingDraft(true);
    setGlobalError(null);
    try {
      await onboardingService.saveDraft(currentStage, {
        saved_at: new Date().toISOString(),
        stage: currentStage,
      });
      setDraftSavedTime(new Date().toLocaleTimeString());
    } catch (err: any) {
      setGlobalError(err.message || 'Failed to save draft progress.');
    } finally {
      setIsSavingDraft(false);
    }
  };

  const handleExit = () => {
    if (window.confirm('Do you want to save draft progress and exit setup? You can resume anytime.')) {
      navigate('/dashboard');
    }
  };

  // Stage 1 submit
  const handleStage1Submit = async (data: any) => {
    setIsSubmitting(true);
    setGlobalError(null);
    setFieldErrors({});
    try {
      let resp: WizardStatusResponse;
      if (!statusData || statusData.status === 'not_started') {
        resp = await onboardingService.startWizard(data);
      } else {
        resp = await onboardingService.submitStage(1, data);
      }
      setStatusData(resp);
      navigate('/setup/2');
    } catch (err: any) {
      if (err instanceof OnboardingApiError && err.data) {
        setFieldErrors(err.data);
      }
      setGlobalError(err.message || 'Failed to initialize organization.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Stage 2 submit
  const handleStage2Submit = async (data: any) => {
    setIsSubmitting(true);
    setGlobalError(null);
    setFieldErrors({});
    try {
      const resp = await onboardingService.submitStage2Branch(data);
      setStatusData(resp);
      navigate('/setup/3');
    } catch (err: any) {
      if (err instanceof OnboardingApiError && err.data) {
        setFieldErrors(err.data);
      }
      setGlobalError(err.message || 'Failed to configure Head Office branch.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Stage 3 submit
  const handleStage3Submit = async (data: any) => {
    setIsSubmitting(true);
    setGlobalError(null);
    setFieldErrors({});
    try {
      const resp = await onboardingService.submitStage3Structure(data);
      setStatusData(resp);
      navigate('/setup/4');
    } catch (err: any) {
      if (err instanceof OnboardingApiError && err.data) {
        setFieldErrors(err.data);
      }
      setGlobalError(err.message || 'Failed to save organizational structure.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Stage 4 submit
  const handleStage4Submit = async (data: any) => {
    setIsSubmitting(true);
    setGlobalError(null);
    setFieldErrors({});
    try {
      const resp = await onboardingService.submitStage4Calendar(data);
      setStatusData(resp);
      navigate('/setup/5');
    } catch (err: any) {
      if (err instanceof OnboardingApiError && err.data) {
        setFieldErrors(err.data);
      }
      setGlobalError(err.message || 'Failed to save working calendar.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Stage 5 submit
  const handleStage5Submit = async (data: any) => {
    setIsSubmitting(true);
    setGlobalError(null);
    setFieldErrors({});
    try {
      const resp = await onboardingService.submitStage5ShiftsPolicy(data);
      setStatusData(resp);
      navigate('/setup/6');
    } catch (err: any) {
      if (err instanceof OnboardingApiError && err.data) {
        setFieldErrors(err.data);
      }
      setGlobalError(err.message || 'Failed to save shift and attendance policies.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Stage 6 submit
  const handleStage6Submit = async (data: any) => {
    setIsSubmitting(true);
    setGlobalError(null);
    setFieldErrors({});
    try {
      const resp = await onboardingService.submitStage6AdminRbac(data);
      setStatusData(resp);
      navigate('/setup/7');
    } catch (err: any) {
      if (err instanceof OnboardingApiError && err.data) {
        setFieldErrors(err.data);
      }
      setGlobalError(err.message || 'Failed to provision administrator role.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Stage 7 completion
  const handleCompleteWizard = async () => {
    setIsSubmitting(true);
    setGlobalError(null);
    try {
      const resp = await onboardingService.completeWizard(statusData?.organization_id);
      setCompletedCelebration(true);
      // Wait 1.5 seconds so user can see success animation, then redirect to dashboard
      setTimeout(() => {
        navigate(resp.redirect_url || '/dashboard', { replace: true });
      }, 1500);
    } catch (err: any) {
      setGlobalError(err.message || 'Prerequisites incomplete: Failed to activate organization.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          background: 'var(--color-bg-body, #f8fafc)',
        }}
      >
        <Loader2 size={40} className="animate-spin" style={{ color: 'var(--color-primary, #3b82f6)', marginBottom: '16px' }} />
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)', margin: '0 0 6px' }}>
          Loading Setup Wizard...
        </h2>
        <p style={{ color: 'var(--color-text-muted, #64748b)', margin: 0, fontSize: '0.875rem' }}>
          Querying organization state and verification prerequisites
        </p>
      </div>
    );
  }

  // Completed celebration screen
  if (completedCelebration) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          background: 'radial-gradient(circle at center, rgba(59, 130, 246, 0.1) 0%, #f8fafc 100%)',
          padding: '24px',
        }}
      >
        <div
          style={{
            maxWidth: '540px',
            width: '100%',
            background: '#ffffff',
            borderRadius: 'var(--radius-lg, 16px)',
            border: '1px solid var(--color-border, #e2e8f0)',
            padding: '40px 32px',
            textAlign: 'center',
            boxShadow: '0 20px 40px rgba(0,0,0,0.08)',
          }}
        >
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 20px',
              boxShadow: '0 10px 20px rgba(16, 185, 129, 0.3)',
            }}
          >
            <CheckCircle2 size={36} />
          </div>

          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--color-text-main, #0f172a)', margin: '0 0 10px' }}>
            Organization Successfully Launched!
          </h2>
          <p style={{ color: 'var(--color-text-sub, #475569)', fontSize: '0.9375rem', lineHeight: 1.6, margin: '0 0 28px' }}>
            Your organization setup is complete. Operational barriers, branch geofences, working shifts, and dynamic Super Admin permissions have been activated.
          </p>

          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '12px 28px',
              borderRadius: 'var(--radius-md, 8px)',
              background: 'var(--color-primary, #3b82f6)',
              color: '#ffffff',
              border: 'none',
              fontSize: '1rem',
              fontWeight: 700,
              cursor: 'pointer',
              boxShadow: '0 4px 14px rgba(59, 130, 246, 0.35)',
            }}
          >
            Proceed to Dashboard
            <ArrowRight size={18} />
          </button>
        </div>
      </div>
    );
  }

  const currentStepInfo = WIZARD_STEPS[currentStage - 1] || WIZARD_STEPS[0];
  const metadata = statusData?.metadata || {};

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'var(--color-bg-body, #f8fafc)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Sticky Header */}
      <WizardHeader
        currentStage={currentStage}
        totalStages={7}
        stageTitle={currentStepInfo.title}
        isSavingDraft={isSavingDraft}
        draftSavedTime={draftSavedTime}
        onSaveDraft={handleSaveDraft}
        onExit={handleExit}
      />

      {/* Main Wizard Form Container */}
      <main
        style={{
          flex: 1,
          maxWidth: '1040px',
          width: '100%',
          margin: '0 auto',
          padding: '28px 20px 60px',
        }}
      >
        {/* Stepper Navigation */}
        <WizardStepper
          currentStage={currentStage}
          completedStages={completedStages}
          onSelectStage={handleStageNavigation}
        />

        {/* Global Error Notice */}
        {globalError && (
          <div
            style={{
              padding: '14px 18px',
              borderRadius: 'var(--radius-md, 8px)',
              background: 'var(--color-status-danger-bg, #fef2f2)',
              color: 'var(--color-status-danger, #ef4444)',
              border: '1px solid var(--color-status-danger-border, #fecaca)',
              fontSize: '0.875rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '20px',
              boxShadow: 'var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.05))',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <AlertCircle size={18} />
              <span>{globalError}</span>
            </div>
            <button
              type="button"
              onClick={() => setGlobalError(null)}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--color-status-danger, #ef4444)',
                cursor: 'pointer',
                fontWeight: 700,
                fontSize: '1rem',
              }}
            >
              ✕
            </button>
          </div>
        )}

        {/* Stage Content Card */}
        <div
          style={{
            background: 'var(--color-bg-card, #ffffff)',
            border: '1px solid var(--color-border, #e2e8f0)',
            borderRadius: 'var(--radius-lg, 12px)',
            padding: '32px',
            boxShadow: 'var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.05))',
          }}
        >
          {currentStage === 1 && (
            <Stage1OrgDetails
              initialData={{
                name: statusData?.organization_name || metadata['stage_1']?.name || '',
                code: statusData?.organization_code || metadata['stage_1']?.code || '',
                currency_code: metadata['stage_1']?.currency_code || 'INR',
                date_format: metadata['stage_1']?.date_format || 'DD/MM/YYYY',
                timezone: metadata['stage_1']?.timezone || 'Asia/Kolkata',
              }}
              isSubmitting={isSubmitting}
              onSubmit={handleStage1Submit}
              fieldErrors={fieldErrors}
            />
          )}

          {currentStage === 2 && (
            <Stage2Branch
              initialData={metadata['stage_2'] || {}}
              isSubmitting={isSubmitting}
              onBack={() => handleStageNavigation(1)}
              onSubmit={handleStage2Submit}
              fieldErrors={fieldErrors}
            />
          )}

          {currentStage === 3 && (
            <Stage3Structure
              initialData={metadata['stage_3'] || {}}
              isSubmitting={isSubmitting}
              onBack={() => handleStageNavigation(2)}
              onSubmit={handleStage3Submit}
              fieldErrors={fieldErrors}
            />
          )}

          {currentStage === 4 && (
            <Stage4Calendar
              initialData={metadata['stage_4'] || {}}
              isSubmitting={isSubmitting}
              onBack={() => handleStageNavigation(3)}
              onSubmit={handleStage4Submit}
              fieldErrors={fieldErrors}
            />
          )}

          {currentStage === 5 && (
            <Stage5ShiftsPolicy
              initialData={metadata['stage_5'] || {}}
              isSubmitting={isSubmitting}
              onBack={() => handleStageNavigation(4)}
              onSubmit={handleStage5Submit}
              fieldErrors={fieldErrors}
            />
          )}

          {currentStage === 6 && (
            <Stage6AdminRbac
              initialData={metadata['stage_6'] || {}}
              isSubmitting={isSubmitting}
              onBack={() => handleStageNavigation(5)}
              onSubmit={handleStage6Submit}
              fieldErrors={fieldErrors}
            />
          )}

          {currentStage === 7 && (
            <Stage7ReviewComplete
              statusData={statusData}
              isCompleting={isSubmitting}
              onBack={() => handleStageNavigation(6)}
              onJumpToStage={handleStageNavigation}
              onComplete={handleCompleteWizard}
            />
          )}
        </div>
      </main>
    </div>
  );
};
