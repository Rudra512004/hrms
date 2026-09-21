import React, { useState, useEffect, useCallback, useRef } from 'react';
import { workingCalendarService, type WorkingCalendar } from '../../services/workingCalendar';
import { Card } from '../../components/Card';
import { PageHeader } from '../../components/PageHeader';
import { AlertBanner } from '../../components/AlertBanner';
import { CalendarDays, Loader2, Save } from 'lucide-react';
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
        } else {
          setCalendar(null);
          setSelectedDays([]);
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
      });
      setCalendar(updated);
      setSelectedDays(parseWorkDays(updated.work_days));
      setSuccessMessage('Working calendar configuration updated successfully.');
    } catch (err: any) {
      if (err?.status === 403 || err?.response?.status === 403) {
        setError('403 Forbidden: You do not have permission to update the working calendar.');
      } else if (err?.errorData?.work_days) {
        setError(err.errorData.work_days[0]);
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

  const branchName = selectedBranch.type === 'branch' && selectedBranch.branch?.name
    ? selectedBranch.branch.name
    : 'Unknown Branch';

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      <PageHeader
        title="Working Calendar"
        subtitle="Configure the standard work days for the selected branch."
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
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
              <div>
                <h3 style={{ margin: '0 0 4px 0', fontSize: '1.1rem', color: 'var(--color-text-main)' }}>
                  Branch: {branchName}
                </h3>
                <p style={{ margin: 0, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                  Select the normal operational work days for this location. Unselected days are treated as non-working days.
                </p>
              </div>

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
