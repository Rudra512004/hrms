import React from 'react';
import { CheckCircle2, Lock } from 'lucide-react';
import { WIZARD_STEPS } from '../types';

interface WizardStepperProps {
  currentStage: number;
  completedStages: number[];
  onSelectStage: (stage: number) => void;
}

export const WizardStepper: React.FC<WizardStepperProps> = ({
  currentStage,
  completedStages,
  onSelectStage,
}) => {
  return (
    <nav
      aria-label="Setup Progress"
      style={{
        background: 'var(--color-bg-card, #ffffff)',
        border: '1px solid var(--color-border, #e2e8f0)',
        borderRadius: 'var(--radius-lg, 12px)',
        padding: '16px 20px',
        marginBottom: '24px',
        boxShadow: 'var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.05))',
      }}
    >
      {/* Desktop Stepper */}
      <ol
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${WIZARD_STEPS.length}, minmax(0, 1fr))`,
          gap: '8px',
          listStyle: 'none',
          margin: 0,
          padding: 0,
        }}
      >
        {WIZARD_STEPS.map((step) => {
          const isCompleted = completedStages.includes(step.number);
          const isCurrent = currentStage === step.number;
          const isAccessible = isCompleted || step.number <= (Math.max(...completedStages, 0) + 1);
          const IconComponent = step.icon;

          return (
            <li key={step.number} style={{ position: 'relative' }}>
              <button
                type="button"
                onClick={() => {
                  if (isAccessible) {
                    onSelectStage(step.number);
                  }
                }}
                disabled={!isAccessible}
                title={
                  !isAccessible
                    ? `Complete prior stages to unlock ${step.title}`
                    : `Go to ${step.title}`
                }
                style={{
                  width: '100%',
                  background: isCurrent
                    ? 'var(--color-primary-light, rgba(59, 130, 246, 0.08))'
                    : 'transparent',
                  border: isCurrent
                    ? '1.5px solid var(--color-primary, #3b82f6)'
                    : '1px solid transparent',
                  borderRadius: 'var(--radius-md, 8px)',
                  padding: '10px 8px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  textAlign: 'center',
                  gap: '6px',
                  cursor: isAccessible ? 'pointer' : 'not-allowed',
                  opacity: isAccessible ? 1 : 0.45,
                  transition: 'all 0.2s ease',
                  outline: 'none',
                }}
              >
                {/* Step indicator circle */}
                <div
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 700,
                    fontSize: '0.85rem',
                    background: isCompleted
                      ? 'var(--color-status-success, #10b981)'
                      : isCurrent
                      ? 'var(--color-primary, #3b82f6)'
                      : 'var(--surface-control-bg, #f1f5f9)',
                    color: isCompleted || isCurrent ? '#ffffff' : 'var(--color-text-muted, #64748b)',
                    boxShadow: isCurrent
                      ? '0 0 0 3px rgba(59, 130, 246, 0.25)'
                      : 'none',
                    transition: 'all 0.2s ease',
                  }}
                >
                  {isCompleted ? (
                    <CheckCircle2 size={18} />
                  ) : isAccessible ? (
                    <IconComponent size={16} />
                  ) : (
                    <Lock size={14} />
                  )}
                </div>

                {/* Step labels */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', width: '100%' }}>
                  <span
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: isCurrent ? 700 : 600,
                      color: isCurrent
                        ? 'var(--color-primary, #3b82f6)'
                        : isCompleted
                        ? 'var(--color-text-main, #0f172a)'
                        : 'var(--color-text-muted, #64748b)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {step.shortTitle}
                  </span>
                  <span
                    style={{
                      fontSize: '0.65rem',
                      color: 'var(--color-text-muted, #94a3b8)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    Step {step.number}
                  </span>
                </div>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
};
