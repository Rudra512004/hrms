import React, { useState } from 'react';
import {
  CalendarDays,
  Plus,
  Trash2,
  ArrowRight,
  ArrowLeft,
  Calendar,
  AlertCircle,
} from 'lucide-react';
import type { Stage4Payload, HolidayItem, RecurringRuleItem } from '../../../services/onboardingService';

interface Stage4CalendarProps {
  initialData?: Partial<Stage4Payload>;
  isSubmitting: boolean;
  onBack: () => void;
  onSubmit: (data: Stage4Payload) => void;
  fieldErrors?: Record<string, string[]>;
}

const WEEKDAYS = [
  { id: '0', label: 'Mon', fullName: 'Monday' },
  { id: '1', label: 'Tue', fullName: 'Tuesday' },
  { id: '2', label: 'Wed', fullName: 'Wednesday' },
  { id: '3', label: 'Thu', fullName: 'Thursday' },
  { id: '4', label: 'Fri', fullName: 'Friday' },
  { id: '5', label: 'Sat', fullName: 'Saturday' },
  { id: '6', label: 'Sun', fullName: 'Sunday' },
];

export const Stage4Calendar: React.FC<Stage4CalendarProps> = ({
  initialData,
  isSubmitting,
  onBack,
  onSubmit,
  fieldErrors: _fieldErrors = {},
}) => {
  // Parse work days into selected array
  const initialDays = initialData?.work_days
    ? initialData.work_days.split(',').filter(Boolean)
    : ['0', '1', '2', '3', '4'];

  const [selectedDays, setSelectedDays] = useState<string[]>(initialDays);
  const [alternateSaturdaysOff, setAlternateSaturdaysOff] = useState<boolean>(
    initialData?.recurring_rules?.some(
      (r) => r.weekday === 5 && (r.occurrence === 2 || r.occurrence === 4) && !r.is_working
    ) || false
  );

  const [holidays, setHolidays] = useState<HolidayItem[]>(
    initialData?.holidays || [
      { name: 'Republic Day', date: '2026-01-26', holiday_type: 'public' },
      { name: 'Independence Day', date: '2026-08-15', holiday_type: 'public' },
      { name: 'Gandhi Jayanti', date: '2026-10-02', holiday_type: 'public' },
    ]
  );

  const [clientError, setClientError] = useState<string | null>(null);

  const toggleDay = (dayId: string) => {
    if (selectedDays.includes(dayId)) {
      if (selectedDays.length <= 1) {
        setClientError('At least one working day must be selected.');
        return;
      }
      setSelectedDays(selectedDays.filter((d) => d !== dayId));
    } else {
      setSelectedDays([...selectedDays, dayId].sort());
    }
    setClientError(null);
  };

  const handleAddHoliday = () => {
    setHolidays([
      ...holidays,
      { name: '', date: new Date().toISOString().split('T')[0], holiday_type: 'public' },
    ]);
  };

  const handleUpdateHoliday = (index: number, field: keyof HolidayItem, value: string) => {
    const updated = [...holidays];
    updated[index] = { ...updated[index], [field]: value };
    setHolidays(updated);
  };

  const handleRemoveHoliday = (index: number) => {
    setHolidays(holidays.filter((_, i) => i !== index));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedDays.length === 0) {
      setClientError('Please select at least one base working day.');
      return;
    }

    // Build recurring rules
    const recurringRules: RecurringRuleItem[] = [];
    if (alternateSaturdaysOff) {
      recurringRules.push(
        { weekday: 5, occurrence: 2, is_working: false },
        { weekday: 5, occurrence: 4, is_working: false }
      );
    }

    // Filter valid holidays
    const validHolidays = holidays
      .filter((h) => h.name.trim() && h.date)
      .map((h) => ({
        name: h.name.trim(),
        date: h.date,
        holiday_type: h.holiday_type || 'public',
      }));

    onSubmit({
      work_days: selectedDays.sort().join(','),
      recurring_rules: recurringRules.length > 0 ? recurringRules : undefined,
      holidays: validHolidays.length > 0 ? validHolidays : undefined,
    });
  };

  return (
    <form noValidate onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* Intro Banner */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(234, 88, 12, 0.04) 100%)',
          border: '1px solid rgba(245, 158, 11, 0.2)',
          borderRadius: 'var(--radius-md, 8px)',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '12px',
        }}
      >
        <CalendarDays size={24} style={{ color: 'var(--color-status-warning, #f59e0b)', flexShrink: 0, marginTop: '2px' }} />
        <div>
          <h3 style={{ margin: '0 0 4px', fontSize: '0.95rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
            Working Calendar & Statutory Holidays
          </h3>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--color-text-sub, #475569)', lineHeight: 1.5 }}>
            Defines working days and holidays. Evaluated by attendance and payroll with locked precedence: <strong>Explicit Holiday &gt; Recurring Rule &gt; Base Work Days</strong>.
          </p>
        </div>
      </div>

      {clientError && (
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
          {clientError}
        </div>
      )}

      {/* Base Working Days Selector */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <div>
          <h4 style={{ margin: '0 0 4px', fontSize: '1rem', fontWeight: 700, color: 'var(--color-text-main, #0f172a)' }}>
            Base Working Days
          </h4>
          <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--color-text-muted, #64748b)' }}>
            Select the days your organization is routinely active.
          </p>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
          {WEEKDAYS.map((day) => {
            const isSelected = selectedDays.includes(day.id);
            return (
              <button
                key={day.id}
                type="button"
                onClick={() => toggleDay(day.id)}
                style={{
                  minWidth: '70px',
                  padding: '12px 16px',
                  borderRadius: 'var(--radius-md, 8px)',
                  border: isSelected ? '2px solid var(--color-primary, #3b82f6)' : '1px solid var(--color-border, #cbd5e1)',
                  background: isSelected ? 'var(--color-primary-light, rgba(59, 130, 246, 0.1))' : 'var(--surface-control-bg, #ffffff)',
                  color: isSelected ? 'var(--color-primary-hover, #1d4ed8)' : 'var(--color-text-sub, #475569)',
                  fontSize: '0.9375rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '4px',
                  transition: 'all 0.15s ease',
                }}
              >
                <span>{day.label}</span>
                <span style={{ fontSize: '0.65rem', fontWeight: 500, color: 'var(--color-text-muted, #94a3b8)' }}>
                  {isSelected ? 'Working' : 'Off'}
                </span>
              </button>
            );
          })}
        </div>

        {/* Quick presets */}
        <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
          <button
            type="button"
            onClick={() => setSelectedDays(['0', '1', '2', '3', '4'])}
            style={{
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm, 6px)',
              background: 'var(--surface-control-bg, #f1f5f9)',
              border: '1px solid var(--color-border, #cbd5e1)',
              fontSize: '0.75rem',
              fontWeight: 600,
              color: 'var(--color-text-sub, #475569)',
              cursor: 'pointer',
            }}
          >
            5-Day Week (Mon-Fri)
          </button>
          <button
            type="button"
            onClick={() => setSelectedDays(['0', '1', '2', '3', '4', '5'])}
            style={{
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm, 6px)',
              background: 'var(--surface-control-bg, #f1f5f9)',
              border: '1px solid var(--color-border, #cbd5e1)',
              fontSize: '0.75rem',
              fontWeight: 600,
              color: 'var(--color-text-sub, #475569)',
              cursor: 'pointer',
            }}
          >
            6-Day Week (Mon-Sat)
          </button>
        </div>
      </div>

      {/* Recurring Rule: Alternate Saturday Off */}
      <div
        style={{
          borderTop: '1px solid var(--color-border-subtle, #f1f5f9)',
          paddingTop: '20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
        }}
      >
        <div>
          <h4 style={{ margin: '0 0 2px', fontSize: '0.9375rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
            Alternate Saturday Off Rule
          </h4>
          <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--color-text-muted, #64748b)' }}>
            Automatically declare the 2nd and 4th Saturday of each month as non-working holidays.
          </p>
        </div>

        <label style={{ display: 'inline-flex', alignItems: 'center', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={alternateSaturdaysOff}
            onChange={(e) => setAlternateSaturdaysOff(e.target.checked)}
            style={{ width: '20px', height: '20px', accentColor: 'var(--color-primary, #3b82f6)', cursor: 'pointer' }}
          />
        </label>
      </div>

      {/* Statutory / Branch Holidays */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', borderTop: '1px solid var(--color-border-subtle, #f1f5f9)', paddingTop: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Calendar size={18} style={{ color: 'var(--color-primary, #3b82f6)' }} />
            <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: 'var(--color-text-main, #0f172a)' }}>
              Initial Public Holidays ({holidays.length})
            </h4>
          </div>

          <button
            type="button"
            onClick={handleAddHoliday}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 12px',
              borderRadius: 'var(--radius-md, 8px)',
              background: 'var(--surface-control-bg, #f1f5f9)',
              border: '1px solid var(--color-border, #cbd5e1)',
              color: 'var(--color-text-main, #0f172a)',
              fontSize: '0.8125rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <Plus size={14} />
            Add Holiday
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {holidays.map((h, idx) => (
            <div
              key={`hol-${idx}`}
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(200px, 2fr) minmax(160px, 1fr) minmax(120px, 1fr) 40px',
                gap: '10px',
                alignItems: 'center',
                padding: '10px 12px',
                borderRadius: 'var(--radius-md, 8px)',
                background: 'var(--surface-control-bg, #f8fafc)',
                border: '1px solid var(--color-border-subtle, #e2e8f0)',
              }}
            >
              <input
                type="text"
                required
                value={h.name}
                onChange={(e) => handleUpdateHoliday(idx, 'name', e.target.value)}
                placeholder="Holiday Name (e.g. Republic Day)"
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm, 6px)',
                  border: '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--color-bg-card, #ffffff)',
                  fontSize: '0.875rem',
                }}
              />
              <input
                type="date"
                required
                value={h.date}
                onChange={(e) => handleUpdateHoliday(idx, 'date', e.target.value)}
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm, 6px)',
                  border: '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--color-bg-card, #ffffff)',
                  fontSize: '0.875rem',
                }}
              />
              <select
                value={h.holiday_type || 'public'}
                onChange={(e) => handleUpdateHoliday(idx, 'holiday_type', e.target.value)}
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm, 6px)',
                  border: '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--color-bg-card, #ffffff)',
                  fontSize: '0.875rem',
                }}
              >
                <option value="public">Public Holiday</option>
                <option value="optional">Optional / Restricted</option>
                <option value="company">Company Holiday</option>
              </select>
              <button
                type="button"
                onClick={() => handleRemoveHoliday(idx)}
                title="Remove holiday"
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: 'var(--radius-sm, 6px)',
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--color-status-danger, #ef4444)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      </div>

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
            cursor: 'pointer',
          }}
        >
          <ArrowLeft size={18} />
          Back to Structure
        </button>

        <button
          type="submit"
          disabled={isSubmitting}
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
            cursor: isSubmitting ? 'wait' : 'pointer',
            boxShadow: '0 4px 12px rgba(59, 130, 246, 0.25)',
          }}
        >
          {isSubmitting ? 'Saving Calendar...' : 'Continue to Shifts & Policy'}
          <ArrowRight size={18} />
        </button>
      </div>
    </form>
  );
};
