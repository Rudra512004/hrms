import React from 'react';
import { Sparkles, Save, LogOut, Check } from 'lucide-react';

interface WizardHeaderProps {
  currentStage: number;
  totalStages: number;
  stageTitle: string;
  isSavingDraft: boolean;
  draftSavedTime: string | null;
  onSaveDraft: () => void;
  onExit: () => void;
}

export const WizardHeader: React.FC<WizardHeaderProps> = ({
  currentStage,
  totalStages,
  stageTitle,
  isSavingDraft,
  draftSavedTime,
  onSaveDraft,
  onExit,
}) => {
  return (
    <header
      style={{
        background: 'var(--color-bg-card, #ffffff)',
        borderBottom: '1px solid var(--color-border, #e2e8f0)',
        padding: '16px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        position: 'sticky',
        top: 0,
        zIndex: 40,
        boxShadow: 'var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.05))',
      }}
    >
      {/* Brand & Stage info */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div
          style={{
            width: '40px',
            height: '40px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, var(--color-primary, #3b82f6) 0%, #1d4ed8 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ffffff',
            boxShadow: '0 4px 10px rgba(59, 130, 246, 0.3)',
          }}
        >
          <Sparkles size={22} />
        </div>

        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                color: 'var(--color-primary, #3b82f6)',
              }}
            >
              BeyondSure HRMS
            </span>
            <span
              style={{
                fontSize: '0.7rem',
                fontWeight: 600,
                padding: '2px 8px',
                borderRadius: '12px',
                background: 'var(--color-primary-light, rgba(59, 130, 246, 0.1))',
                color: 'var(--color-primary-hover, #1d4ed8)',
              }}
            >
              Stage {currentStage} of {totalStages}
            </span>
          </div>

          <h1
            style={{
              margin: '2px 0 0',
              fontSize: 'var(--font-size-lg, 1.125rem)',
              fontWeight: 700,
              color: 'var(--color-text-main, #0f172a)',
            }}
          >
            {stageTitle}
          </h1>
        </div>
      </div>

      {/* Draft status & Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {draftSavedTime && (
          <span
            style={{
              fontSize: '0.75rem',
              color: 'var(--color-text-muted, #64748b)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <Check size={14} color="var(--color-status-success, #10b981)" />
            Draft saved at {draftSavedTime}
          </span>
        )}

        <button
          type="button"
          onClick={onSaveDraft}
          disabled={isSavingDraft}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 14px',
            borderRadius: 'var(--radius-md, 8px)',
            border: '1px solid var(--color-border, #cbd5e1)',
            background: 'var(--color-bg-card, #ffffff)',
            color: 'var(--color-text-main, #0f172a)',
            fontSize: '0.8125rem',
            fontWeight: 600,
            cursor: isSavingDraft ? 'wait' : 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <Save size={15} />
          {isSavingDraft ? 'Saving Draft...' : 'Save Draft'}
        </button>

        <button
          type="button"
          onClick={onExit}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 14px',
            borderRadius: 'var(--radius-md, 8px)',
            border: '1px solid transparent',
            background: 'var(--surface-control-bg, #f1f5f9)',
            color: 'var(--color-text-sub, #475569)',
            fontSize: '0.8125rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <LogOut size={15} />
          Exit Setup
        </button>
      </div>
    </header>
  );
};
