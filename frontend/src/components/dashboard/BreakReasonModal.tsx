import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  Utensils,
  Coffee,
  Briefcase,
  Building2,
  PhoneCall,
  Phone,
  Users,
  GraduationCap,
  FileText,
  MoreHorizontal,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import type { BreakReasonKey, BreakReasonOption } from '../../types/attendance';

export const BREAK_REASON_OPTIONS: (BreakReasonOption & { icon: React.FC<{ size?: number; className?: string }> })[] = [
  {
    key: 'lunch',
    label: 'Lunch',
    description: 'The midday break.',
    limitLabel: '40 min',
    countsAsWorkedTime: false,
    durationMinutes: 40,
    icon: Utensils,
  },
  {
    key: 'tea_coffee',
    label: 'Tea or coffee',
    description: 'A short break away from the desk.',
    limitLabel: '10 min',
    countsAsWorkedTime: false,
    durationMinutes: 10,
    icon: Coffee,
  },
  {
    key: 'outside_meeting',
    label: 'Outside meeting',
    description: 'A meeting away from the office.',
    limitLabel: 'No limit',
    countsAsWorkedTime: true,
    durationMinutes: null,
    icon: Briefcase,
  },
  {
    key: 'client_visit',
    label: 'Client visit',
    description: 'At a client’s premises.',
    limitLabel: 'No limit',
    countsAsWorkedTime: true,
    durationMinutes: null,
    icon: Building2,
  },
  {
    key: 'client_call',
    label: 'Client — telephonic call',
    description: 'On a call with a client.',
    limitLabel: '30 min',
    countsAsWorkedTime: true,
    durationMinutes: 30,
    icon: PhoneCall,
  },
  {
    key: 'personal_call',
    label: 'Personal telephonic call',
    description: 'A personal call.',
    limitLabel: '10 min',
    countsAsWorkedTime: false,
    durationMinutes: 10,
    icon: Phone,
  },
  {
    key: 'team_meeting',
    label: 'Team meeting',
    description: 'An internal meeting.',
    limitLabel: 'No limit',
    countsAsWorkedTime: true,
    durationMinutes: null,
    icon: Users,
  },
  {
    key: 'training',
    label: 'Product training',
    description: 'Learning or delivering training.',
    limitLabel: 'No limit',
    countsAsWorkedTime: true,
    durationMinutes: null,
    icon: GraduationCap,
  },
  {
    key: 'paperwork',
    label: 'Paperwork',
    description: 'Away from the system doing paperwork.',
    limitLabel: 'No limit',
    countsAsWorkedTime: true,
    durationMinutes: null,
    icon: FileText,
  },
  {
    key: 'other',
    label: 'Other',
    description: 'Anything else — say what in the comment.',
    limitLabel: '15 min',
    countsAsWorkedTime: false,
    durationMinutes: 15,
    icon: MoreHorizontal,
  },
];

interface BreakReasonModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (reason: BreakReasonKey, comment?: string) => Promise<void>;
  loading?: boolean;
  error?: string | null;
}

export const BreakReasonModal: React.FC<BreakReasonModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  loading = false,
  error = null,
}) => {
  const [selectedReason, setSelectedReason] = useState<BreakReasonKey>('lunch');
  const [comment, setComment] = useState<string>('');
  const [localError, setLocalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const commentInputRef = useRef<HTMLTextAreaElement>(null);

  // Sync external error into local error
  useEffect(() => {
    if (error) {
      setLocalError(error);
    }
  }, [error]);

  // Reset local state whenever modal opens
  useEffect(() => {
    if (isOpen) {
      setSelectedReason('lunch');
      setComment('');
      setLocalError(null);
      setIsSubmitting(false);
    }
  }, [isOpen]);

  // Focus comment textarea when 'other' is selected
  useEffect(() => {
    if (selectedReason === 'other') {
      setTimeout(() => {
        commentInputRef.current?.focus();
      }, 50);
    }
  }, [selectedReason]);

  // Handle escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isSubmitting && !loading) {
        onClose();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, isSubmitting, loading, onClose]);

  if (!isOpen) return null;

  const trimmedComment = comment.trim();
  const isOther = selectedReason === 'other';
  const isCommentValid = !isOther || (trimmedComment.length >= 3 && trimmedComment.length <= 255);
  const canSubmit = Boolean(selectedReason) && isCommentValid && !isSubmitting && !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    if (isOther && trimmedComment.length < 3) {
      setLocalError('Please enter a comment with at least 3 characters.');
      return;
    }

    setLocalError(null);
    setIsSubmitting(true);
    try {
      await onSubmit(selectedReason, isOther ? trimmedComment : undefined);
      // On success, parent will close modal and refresh state
    } catch (err: any) {
      const msg = err?.errorData?.detail || err?.message || 'Failed to start break. Please try again.';
      setLocalError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="modal-overlay"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting && !loading) {
          onClose();
        }
      }}
      style={{
        zIndex: 1050,
        backgroundColor: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
        position: 'fixed',
        inset: 0,
      }}
    >
      <div
        className="modal-dialog modal-break-reason"
        role="dialog"
        aria-modal="true"
        aria-labelledby="break-reason-modal-title"
        ref={dialogRef}
        style={{
          width: '100%',
          maxWidth: '780px',
          maxHeight: '90vh',
          backgroundColor: '#FFFFFF',
          borderRadius: '16px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          border: '1px solid var(--color-border)',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '24px 28px 18px',
            borderBottom: '1px solid var(--color-border-subtle, #E2E8F0)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: '16px',
          }}
        >
          <div>
            <h2
              id="break-reason-modal-title"
              style={{
                margin: 0,
                fontSize: '1.25rem',
                fontWeight: 700,
                color: 'var(--color-text-main, #0F172A)',
                letterSpacing: '-0.02em',
              }}
            >
              What is the break for?
            </h2>
            <p
              style={{
                margin: '6px 0 0',
                fontSize: '0.875rem',
                color: 'var(--color-text-muted, #64748B)',
              }}
            >
              Choose the reason that best matches your time away.
            </p>
          </div>

          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            disabled={isSubmitting || loading}
            aria-label="Close dialog"
            style={{
              padding: '6px',
              borderRadius: '8px',
              border: 'none',
              background: 'transparent',
              color: 'var(--color-text-muted, #64748B)',
              cursor: isSubmitting || loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Form Body */}
        <form
          onSubmit={handleSubmit}
          style={{
            display: 'flex',
            flexDirection: 'column',
            flex: 1,
            minHeight: 0,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              padding: '20px 28px',
              overflowY: 'auto',
              flex: 1,
            }}
          >
            {/* Error Notification */}
            {localError && (
              <div
                role="alert"
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '10px',
                  padding: '12px 14px',
                  borderRadius: '10px',
                  backgroundColor: '#FEF2F2',
                  border: '1px solid #FCA5A5',
                  color: '#991B1B',
                  fontSize: '0.875rem',
                  marginBottom: '18px',
                }}
              >
                <AlertCircle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
                <span style={{ flex: 1, lineHeight: 1.4 }}>{localError}</span>
              </div>
            )}

            {/* Reason Grid: 2 columns on desktop, 1 on mobile */}
            <div
              role="radiogroup"
              aria-label="Break reasons"
              className="break-reason-grid"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(310px, 1fr))',
                gap: '12px',
              }}
            >
              {BREAK_REASON_OPTIONS.map((option) => {
                const isSelected = selectedReason === option.key;
                const IconComponent = option.icon;

                return (
                  <div
                    key={option.key}
                    role="radio"
                    aria-checked={isSelected}
                    tabIndex={0}
                    onClick={() => {
                      if (!isSubmitting && !loading) {
                        setSelectedReason(option.key);
                        setLocalError(null);
                      }
                    }}
                    onKeyDown={(e) => {
                      if (e.key === ' ' || e.key === 'Enter') {
                        e.preventDefault();
                        if (!isSubmitting && !loading) {
                          setSelectedReason(option.key);
                          setLocalError(null);
                        }
                      }
                    }}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      padding: '14px 16px',
                      borderRadius: '12px',
                      border: isSelected
                        ? '2px solid var(--color-primary, #1E40AF)'
                        : '1.5px solid var(--color-border-subtle, #E2E8F0)',
                      backgroundColor: isSelected
                        ? 'rgba(30, 64, 175, 0.04)'
                        : '#FFFFFF',
                      cursor: isSubmitting || loading ? 'not-allowed' : 'pointer',
                      transition: 'all 0.15s ease',
                      boxShadow: isSelected
                        ? '0 2px 8px rgba(30, 64, 175, 0.12)'
                        : 'none',
                      userSelect: 'none',
                    }}
                  >
                    {/* Header: Radio + Icon + Title */}
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                      {/* Radio Indicator */}
                      <div
                        style={{
                          width: '18px',
                          height: '18px',
                          borderRadius: '50%',
                          border: isSelected
                            ? '5px solid var(--color-primary, #1E40AF)'
                            : '2px solid #CBD5E1',
                          backgroundColor: '#FFFFFF',
                          marginTop: '3px',
                          flexShrink: 0,
                          transition: 'border 0.15s ease',
                        }}
                      />

                      {/* Icon */}
                      <div
                        style={{
                          width: '32px',
                          height: '32px',
                          borderRadius: '8px',
                          backgroundColor: isSelected
                            ? 'rgba(30, 64, 175, 0.12)'
                            : '#F1F5F9',
                          color: isSelected
                            ? 'var(--color-primary, #1E40AF)'
                            : '#64748B',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}
                      >
                        <IconComponent size={17} />
                      </div>

                      {/* Text */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div
                          style={{
                            fontWeight: 600,
                            fontSize: '0.9375rem',
                            color: isSelected
                              ? 'var(--color-primary, #1E40AF)'
                              : 'var(--color-text-main, #0F172A)',
                            lineHeight: 1.25,
                            marginBottom: '4px',
                          }}
                        >
                          {option.label}
                        </div>
                        <div
                          style={{
                            fontSize: '0.8125rem',
                            color: 'var(--color-text-muted, #64748B)',
                            lineHeight: 1.35,
                          }}
                        >
                          {option.description}
                        </div>
                      </div>
                    </div>

                    {/* Footer Pills: Limit & Worked Time */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        flexWrap: 'wrap',
                        marginTop: '12px',
                        paddingLeft: '30px',
                      }}
                    >
                      {/* Limit Pill */}
                      <span
                        style={{
                          fontSize: '0.75rem',
                          fontWeight: 500,
                          padding: '3px 8px',
                          borderRadius: '6px',
                          backgroundColor: '#F1F5F9',
                          color: '#475569',
                        }}
                      >
                        {option.limitLabel}
                      </span>

                      {/* Counts as Worked Time Indicator */}
                      {option.countsAsWorkedTime && (
                        <span
                          style={{
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            padding: '3px 8px',
                            borderRadius: '6px',
                            backgroundColor: '#ECFDF5',
                            color: '#065F46',
                            border: '1px solid #A7F3D0',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                          }}
                        >
                          <CheckCircle2 size={12} />
                          Counts as worked time
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Comment Section for 'Other' */}
            {isOther && (
              <div
                style={{
                  marginTop: '18px',
                  padding: '16px',
                  backgroundColor: '#F8FAFC',
                  borderRadius: '12px',
                  border: '1px solid var(--color-border-subtle, #E2E8F0)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '8px',
                  }}
                >
                  <label
                    htmlFor="break-other-comment"
                    style={{
                      fontSize: '0.875rem',
                      fontWeight: 600,
                      color: 'var(--color-text-main, #0F172A)',
                    }}
                  >
                    Specify break reason <span style={{ color: '#DC2626' }}>*</span>
                  </label>
                  <span
                    style={{
                      fontSize: '0.75rem',
                      color: trimmedComment.length > 255 ? '#DC2626' : '#64748B',
                    }}
                  >
                    {trimmedComment.length}/255
                  </span>
                </div>

                <textarea
                  id="break-other-comment"
                  ref={commentInputRef}
                  value={comment}
                  onChange={(e) => {
                    setComment(e.target.value);
                    if (localError) setLocalError(null);
                  }}
                  disabled={isSubmitting || loading}
                  placeholder="Say what the break is for (e.g. Doctor appointment, errands)..."
                  rows={2}
                  maxLength={255}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    border: '1px solid #CBD5E1',
                    fontSize: '0.875rem',
                    fontFamily: 'inherit',
                    resize: 'none',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />

                {trimmedComment.length > 0 && trimmedComment.length < 3 && (
                  <p
                    style={{
                      margin: '4px 0 0',
                      fontSize: '0.75rem',
                      color: '#DC2626',
                    }}
                  >
                    Comment must be at least 3 characters.
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Modal Footer */}
          <div
            style={{
              padding: '16px 28px',
              borderTop: '1px solid var(--color-border-subtle, #E2E8F0)',
              backgroundColor: '#F8FAFC',
              display: 'flex',
              justifyContent: 'flex-end',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={isSubmitting || loading}
              style={{
                padding: '10px 18px',
                fontWeight: 600,
                fontSize: '0.875rem',
              }}
            >
              Cancel
            </button>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={!canSubmit}
              style={{
                padding: '10px 22px',
                fontWeight: 600,
                fontSize: '0.875rem',
                minWidth: '140px',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                cursor: !canSubmit ? 'not-allowed' : 'pointer',
                opacity: !canSubmit ? 0.6 : 1,
              }}
            >
              {isSubmitting || loading ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Starting...
                </>
              ) : (
                'Start the break'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
