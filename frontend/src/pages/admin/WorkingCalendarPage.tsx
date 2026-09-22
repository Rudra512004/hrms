import React, { useState, useEffect, useCallback, useRef } from 'react';
import { workingCalendarService, type WorkingCalendar, type WorkingCalendarRule } from '../../services/workingCalendar';
import { Card } from '../../components/Card';
import { PageHeader } from '../../components/PageHeader';
import { AlertBanner } from '../../components/AlertBanner';
import { CalendarDays, Loader2, Save, X, Calendar as CalendarIcon } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useBranchContext } from '../../contexts/BranchContext';

const DAYS_OF_WEEK = [
  { id: 0, label: 'Mon', fullLabel: 'Monday' },
  { id: 1, label: 'Tue', fullLabel: 'Tuesday' },
  { id: 2, label: 'Wed', fullLabel: 'Wednesday' },
  { id: 3, label: 'Thu', fullLabel: 'Thursday' },
  { id: 4, label: 'Fri', fullLabel: 'Friday' },
  { id: 5, label: 'Sat', fullLabel: 'Saturday' },
  { id: 6, label: 'Sun', fullLabel: 'Sunday' },
];

const OCCURRENCES = [
  { id: 1, label: '1st', fullLabel: '1st' },
  { id: 2, label: '2nd', fullLabel: '2nd' },
  { id: 3, label: '3rd', fullLabel: '3rd' },
  { id: 4, label: '4th', fullLabel: '4th' },
  { id: 5, label: '5th', fullLabel: '5th' },
];

const parseWorkDays = (str: string | undefined): number[] => {
  if (!str || !str.trim()) return [];
  return str
    .split(',')
    .map((d) => parseInt(d.trim(), 10))
    .filter((d) => !isNaN(d) && d >= 0 && d <= 6);
};

export const WorkingCalendarPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const { branchId, selectedBranch } = useBranchContext();

  const [calendar, setCalendar] = useState<WorkingCalendar | null>(null);
  const [selectedDays, setSelectedDays] = useState<number[]>([]);
  const [recurringRules, setRecurringRules] = useState<WorkingCalendarRule[]>([]);
  const [selectedRuleWeekday, setSelectedRuleWeekday] = useState<number>(5); // default Saturday
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [configMissing, setConfigMissing] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  const isAllLocations = branchId === null;
  const canManage = hasPermission('organization.update');

  const loadCalendar = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    if (branchId === null) {
      setCalendar(null);
      setSelectedDays([]);
      setRecurringRules([]);
      setConfigMissing(false);
      setError(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setConfigMissing(false);
      setSuccessMessage(null);

      const calendars = await workingCalendarService.listWorkingCalendars({ signal: controller.signal });

      if (abortControllerRef.current === controller) {
        const branchCal = Array.isArray(calendars)
          ? calendars.find((c) => c.branch === branchId)
          : null;

        if (branchCal) {
          setCalendar(branchCal);
          setSelectedDays(parseWorkDays(branchCal.work_days));
          setRecurringRules(branchCal.recurring_rules || []);
        } else {
          setCalendar(null);
          setSelectedDays([]);
          setRecurringRules([]);
          // Authoritative backend configuration problem - no Mon-Fri fallback!
          setConfigMissing(true);
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') return;
      if (abortControllerRef.current === controller) {
        if (err?.status === 403 || err?.response?.status === 403) {
          setError('403 Forbidden: You do not have permission to view or manage working calendar.');
        } else if (err?.errorData?.detail) {
          setError(err.errorData.detail);
        } else {
          setError('Failed to load working calendar.');
        }
        setCalendar(null);
        setSelectedDays([]);
        setRecurringRules([]);
      }
    } finally {
      if (abortControllerRef.current === controller) {
        setLoading(false);
      }
    }
  }, [branchId]);

  useEffect(() => {
    setCalendar(null);
    setSelectedDays([]);
    setRecurringRules([]);
    loadCalendar();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [loadCalendar]);

  const toggleDay = (dayId: number) => {
    if (!canManage || isAllLocations) return;
    setSelectedDays((prev) => {
      const exists = prev.includes(dayId);
      const updated = exists ? prev.filter((d) => d !== dayId) : [...prev, dayId].sort((a, b) => a - b);
      return updated;
    });
  };

  const getRuleForOccurrence = (weekday: number, occurrence: number): WorkingCalendarRule | undefined => {
    return recurringRules.find((r) => r.weekday === weekday && r.occurrence === occurrence);
  };

  const setOccurrenceRuleState = (
    weekday: number,
    occurrence: number,
    state: 'default' | 'working' | 'non_working'
  ) => {
    if (!canManage || isAllLocations) return;

    setRecurringRules((prev) => {
      // Remove any existing rule for this (weekday, occurrence)
      const filtered = prev.filter((r) => !(r.weekday === weekday && r.occurrence === occurrence));
      if (state === 'default') {
        return filtered;
      }
      return [
        ...filtered,
        {
          weekday,
          occurrence,
          is_working: state === 'working',
        },
      ].sort((a, b) => (a.weekday !== b.weekday ? a.weekday - b.weekday : a.occurrence - b.occurrence));
    });
  };

  const handleSave = async () => {
    if (!canManage || !calendar || !branchId) return;

    if (selectedDays.length === 0) {
      setError('A working calendar must have at least one working day configured.');
      return;
    }

    setSaving(true);
    setError(null);
    setSuccessMessage(null);

    const serializedDays = selectedDays.sort((a, b) => a - b).join(',');

    try {
      const updated = await workingCalendarService.updateWorkingCalendar(calendar.id, {
        work_days: serializedDays,
        recurring_rules: recurringRules.map((r) => ({
          weekday: r.weekday,
          occurrence: r.occurrence,
          is_working: r.is_working,
        })),
      });
      setCalendar(updated);
      setSelectedDays(parseWorkDays(updated.work_days));
      setRecurringRules(updated.recurring_rules || []);
      setSuccessMessage('Working calendar configuration updated successfully.');
    } catch (err: any) {
      if (err?.status === 403 || err?.response?.status === 403) {
        setError('403 Forbidden: You do not have permission to update the working calendar.');
      } else if (err?.errorData?.work_days) {
        setError(err.errorData.work_days[0]);
      } else if (err?.errorData?.recurring_rules) {
        setError(
          typeof err.errorData.recurring_rules === 'string'
            ? err.errorData.recurring_rules
            : err.errorData.recurring_rules[0]
        );
      } else if (err?.errorData?.detail) {
        setError(err.errorData.detail);
      } else {
        setError('Failed to save working calendar configuration.');
      }
    } finally {
      setSaving(false);
    }
  };

  if (!hasPermission('organization.update')) {
    return (
      <div className="animate-fade-in">
        <PageHeader title="Working Calendar" subtitle="Branch working days configuration." />
        <AlertBanner type="error" message="You do not have permission to access working calendar configuration." />
      </div>
    );
  }

  const branchName =
    selectedBranch.type === 'branch' && selectedBranch.branch?.name
      ? selectedBranch.branch.name
      : 'Unknown Branch';

  const baseWeekdayIsWorking = selectedDays.includes(selectedRuleWeekday);
  const selectedWeekdayObj = DAYS_OF_WEEK.find((d) => d.id === selectedRuleWeekday) || DAYS_OF_WEEK[5];

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      <PageHeader
        title="Working Calendar"
        subtitle="Configure standard work days and recurring monthly rules for the selected branch."
      />

      {isAllLocations && (
        <AlertBanner
          type="info"
          message="Select a branch from the header to manage this configuration."
        />
      )}

      {error && <AlertBanner type="error" message={error} />}
      {successMessage && <AlertBanner type="success" message={successMessage} />}

      {configMissing && !isAllLocations && (
        <AlertBanner
          type="warning"
          message={`Working calendar is not configured for branch ${branchId}. Automatic attendance calculations will be halted until configured.`}
        />
      )}

      {!isAllLocations && (
        <Card>
          {loading ? (
            <div className="loading-center" style={{ padding: 'var(--spacing-2xl)' }}>
              <Loader2 size={28} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
              <span style={{ marginTop: '8px' }}>Loading working calendar…</span>
            </div>
          ) : calendar ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-xl)' }}>
              <div>
                <h3 style={{ margin: '0 0 4px 0', fontSize: '1.1rem', color: 'var(--color-text-main)' }}>
                  Branch: {branchName}
                </h3>
                <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                  Select the normal operational work days for this location. Unselected days are treated as non-working days.
                </p>
              </div>

              {/* Weekly Working Days */}
              <div>
                <label className="input-label" style={{ marginBottom: '8px', display: 'block' }}>
                  Weekly Working Days
                </label>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }} role="group" aria-label="Working Days">
                  {DAYS_OF_WEEK.map((day) => {
                    const isSelected = selectedDays.includes(day.id);
                    return (
                      <button
                        key={day.id}
                        type="button"
                        onClick={() => toggleDay(day.id)}
                        disabled={!canManage || saving}
                        className={`btn ${isSelected ? 'btn-primary' : 'btn-secondary'}`}
                        style={{
                          minWidth: '54px',
                          padding: '10px 16px',
                          fontWeight: isSelected ? 600 : 500,
                          borderRadius: 'var(--radius-md)',
                        }}
                        aria-pressed={isSelected}
                        title={day.fullLabel}
                      >
                        {day.label}
                      </button>
                    );
                  })}
                </div>
                <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: '8px' }}>
                  {selectedDays.length} day{selectedDays.length === 1 ? '' : 's'} configured:{' '}
                  {selectedDays.length > 0
                    ? selectedDays
                        .sort((a, b) => a - b)
                        .map((d) => DAYS_OF_WEEK.find((item) => item.id === d)?.fullLabel)
                        .join(', ')
                    : 'None'}
                </div>
              </div>

              {/* Recurring Monthly Rules */}
              <div
                style={{
                  borderTop: '1px solid var(--color-border)',
                  paddingTop: 'var(--spacing-lg)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 'var(--spacing-md)',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <CalendarIcon size={18} style={{ color: 'var(--color-primary)' }} />
                    <h4 style={{ margin: 0, fontSize: '1rem', color: 'var(--color-text-main)' }}>
                      Recurring Monthly Rules
                    </h4>
                  </div>
                  <p style={{ margin: '4px 0 0 0', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                    Configure monthly occurrence overrides (e.g. 1st & 3rd Saturday off). Occurrences without an explicit rule inherit the base weekly day behavior above.
                  </p>
                </div>

                {/* Day selector for recurring rules */}
                <div>
                  <label className="input-label" style={{ marginBottom: '6px', display: 'block', fontSize: 'var(--font-size-xs)' }}>
                    Select Weekday to Configure:
                  </label>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }} role="tablist" aria-label="Rule Weekdays">
                    {DAYS_OF_WEEK.map((day) => {
                      const hasRule = recurringRules.some((r) => r.weekday === day.id);
                      const isTabSelected = selectedRuleWeekday === day.id;
                      return (
                        <button
                          key={day.id}
                          type="button"
                          data-testid={`rule-tab-${day.id}`}
                          onClick={() => setSelectedRuleWeekday(day.id)}
                          className={`btn ${isTabSelected ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            fontWeight: isTabSelected ? 600 : 400,
                          }}
                        >
                          <span>{day.label}</span>
                          {hasRule && (
                            <span
                              style={{
                                width: '6px',
                                height: '6px',
                                borderRadius: '50%',
                                backgroundColor: isTabSelected ? '#ffffff' : 'var(--color-primary)',
                                display: 'inline-block',
                              }}
                            />
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Occurrence overrides for selected weekday */}
                <div
                  style={{
                    backgroundColor: 'var(--color-bg-body)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-md)',
                    padding: 'var(--spacing-md)',
                  }}
                >
                  <div style={{ marginBottom: '12px', fontSize: 'var(--font-size-sm)', fontWeight: 600 }}>
                    {selectedWeekdayObj.fullLabel} Rules{' '}
                    <span style={{ fontWeight: 400, fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                      (Base: {baseWeekdayIsWorking ? 'Working' : 'Non-working'})
                    </span>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
                    {OCCURRENCES.map((occ) => {
                      const activeRule = getRuleForOccurrence(selectedRuleWeekday, occ.id);
                      const currentState =
                        activeRule === undefined
                          ? 'default'
                          : activeRule.is_working
                          ? 'working'
                          : 'non_working';

                      return (
                        <div
                          key={occ.id}
                          style={{
                            padding: '10px 12px',
                            borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--color-border)',
                            backgroundColor: 'var(--color-bg-card)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '8px',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 600, fontSize: 'var(--font-size-sm)' }}>
                              {occ.fullLabel} {selectedWeekdayObj.label}
                            </span>
                            <span
                              style={{
                                fontSize: '11px',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                fontWeight: 500,
                                backgroundColor:
                                  currentState === 'default'
                                    ? 'var(--color-bg-body)'
                                    : currentState === 'working'
                                    ? 'rgba(16, 185, 129, 0.15)'
                                    : 'rgba(239, 68, 68, 0.15)',
                                color:
                                  currentState === 'default'
                                    ? 'var(--color-text-muted)'
                                    : currentState === 'working'
                                    ? 'var(--color-status-success)'
                                    : 'var(--color-status-danger)',
                              }}
                            >
                              {currentState === 'default'
                                ? baseWeekdayIsWorking ? 'Base: Working' : 'Base: Off'
                                : currentState === 'working'
                                ? 'Override: Working'
                                : 'Override: Off'}
                            </span>
                          </div>

                          <div style={{ display: 'flex', gap: '4px' }}>
                            <button
                              type="button"
                              onClick={() => setOccurrenceRuleState(selectedRuleWeekday, occ.id, 'default')}
                              disabled={!canManage || saving || isAllLocations}
                              className={`btn btn-sm ${currentState === 'default' ? 'btn-primary' : 'btn-secondary'}`}
                              style={{ flex: 1, padding: '4px 6px', fontSize: '12px' }}
                              data-testid={`rule-${selectedRuleWeekday}-${occ.id}-default`}
                            >
                              Default
                            </button>
                            <button
                              type="button"
                              onClick={() => setOccurrenceRuleState(selectedRuleWeekday, occ.id, 'working')}
                              disabled={!canManage || saving || isAllLocations}
                              className={`btn btn-sm ${currentState === 'working' ? 'btn-primary' : 'btn-secondary'}`}
                              style={{
                                flex: 1,
                                padding: '4px 6px',
                                fontSize: '12px',
                                backgroundColor: currentState === 'working' ? 'var(--color-status-success)' : undefined,
                                borderColor: currentState === 'working' ? 'var(--color-status-success)' : undefined,
                              }}
                              data-testid={`rule-${selectedRuleWeekday}-${occ.id}-working`}
                            >
                              Working
                            </button>
                            <button
                              type="button"
                              onClick={() => setOccurrenceRuleState(selectedRuleWeekday, occ.id, 'non_working')}
                              disabled={!canManage || saving || isAllLocations}
                              className={`btn btn-sm ${currentState === 'non_working' ? 'btn-primary' : 'btn-secondary'}`}
                              style={{
                                flex: 1,
                                padding: '4px 6px',
                                fontSize: '12px',
                                backgroundColor: currentState === 'non_working' ? 'var(--color-status-danger)' : undefined,
                                borderColor: currentState === 'non_working' ? 'var(--color-status-danger)' : undefined,
                              }}
                              data-testid={`rule-${selectedRuleWeekday}-${occ.id}-off`}
                            >
                              Off
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Configured Rules Summary List */}
                {recurringRules.length > 0 && (
                  <div>
                    <span style={{ fontSize: 'var(--font-size-xs)', fontWeight: 600, color: 'var(--color-text-main)', display: 'block', marginBottom: '6px' }}>
                      Configured Monthly Overrides ({recurringRules.length}):
                    </span>
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                      {recurringRules.map((rule) => {
                        const wkLabel = DAYS_OF_WEEK.find((d) => d.id === rule.weekday)?.fullLabel || rule.weekday;
                        const occLabel = OCCURRENCES.find((o) => o.id === rule.occurrence)?.label || `${rule.occurrence}`;
                        return (
                          <span
                            key={`${rule.weekday}-${rule.occurrence}`}
                            data-testid={`override-chip-${rule.weekday}-${rule.occurrence}`}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              padding: '4px 8px',
                              borderRadius: '4px',
                              fontSize: '12px',
                              backgroundColor: rule.is_working ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                              color: rule.is_working ? 'var(--color-status-success)' : 'var(--color-status-danger)',
                              border: `1px solid ${rule.is_working ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                            }}
                          >
                            <span>
                              {occLabel} {wkLabel}: <strong>{rule.is_working ? 'Working' : 'Off'}</strong>
                            </span>
                            {canManage && !isAllLocations && (
                              <button
                                type="button"
                                onClick={() => setOccurrenceRuleState(rule.weekday, rule.occurrence, 'default')}
                                style={{
                                  background: 'none',
                                  border: 'none',
                                  padding: 0,
                                  cursor: 'pointer',
                                  color: 'inherit',
                                  display: 'inline-flex',
                                }}
                                title="Remove override"
                                aria-label={`Remove ${occLabel} ${wkLabel} rule`}
                              >
                                <X size={12} />
                              </button>
                            )}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {/* Save Button */}
              <div style={{ display: 'flex', justifyContent: 'flex-start', paddingTop: 'var(--spacing-md)', borderTop: '1px solid var(--color-border)' }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleSave}
                  disabled={saving || !canManage}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
                >
                  {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                  <span>{saving ? 'Saving Changes…' : 'Save Working Calendar'}</span>
                </button>
              </div>
            </div>
          ) : (
            !configMissing && (
              <div style={{ textAlign: 'center', padding: 'var(--spacing-xl)', color: 'var(--color-text-muted)' }}>
                <CalendarDays size={36} style={{ margin: '0 auto 8px auto', opacity: 0.5 }} />
                <p>No working calendar found.</p>
              </div>
            )
          )}
        </Card>
      )}
    </div>
  );
};
