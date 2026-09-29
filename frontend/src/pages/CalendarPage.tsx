import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight,
  Briefcase,
  Sparkles,
  Coffee,
  Moon,
  Users,
  Loader2,
} from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { Card } from '../components/Card';
import { StatCard } from '../components/StatCard';
import { AlertBanner } from '../components/AlertBanner';
import { Modal } from '../components/Modal';
import { useAuth } from '../contexts/AuthContext';
import { leaveService, type CalendarDay, type EmployeeCalendarResponse } from '../services/leaves';
import { employeeManagementService } from '../services/employeeManagement';
import { type EmployeeProfile } from '../services/employee';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export const CalendarPage: React.FC = () => {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const canViewOthers = hasPermission('leave.view');

  // Month state (defaults to today)
  const [currentDate, setCurrentDate] = useState<Date>(() => new Date());
  const [calendarData, setCalendarData] = useState<EmployeeCalendarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Employee switcher for managers/HR
  const [employees, setEmployees] = useState<EmployeeProfile[]>([]);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string>('self');
  const [loadingEmployees, setLoadingEmployees] = useState(false);

  // Day detail modal
  const [selectedDay, setSelectedDay] = useState<CalendarDay | null>(null);

  // Abort controller to prevent race conditions
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load employee list for manager selector if authorized
  useEffect(() => {
    if (!canViewOthers) return;

    let isMounted = true;
    setLoadingEmployees(true);
    employeeManagementService.listEmployees({ status: 'active', paginate: false })
      .then((data) => {
        if (!isMounted) return;
        if (Array.isArray(data)) {
          setEmployees(data);
        } else if (data && Array.isArray((data as any).results)) {
          setEmployees((data as any).results);
        }
      })
      .catch((err) => {
        console.error('Failed to load employee directory for calendar:', err);
      })
      .finally(() => {
        if (isMounted) setLoadingEmployees(false);
      });

    return () => {
      isMounted = false;
    };
  }, [canViewOthers]);

  // Format YYYY-MM-DD
  const formatISO = (d: Date): string => {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  // Fetch calendar data for the selected month and employee
  const fetchCalendar = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      setLoading(true);
      setError(null);

      const year = currentDate.getFullYear();
      const month = currentDate.getMonth();

      // First day of month
      const startDate = new Date(year, month, 1);
      // Last day of month
      const endDate = new Date(year, month + 1, 0);

      const start_date = formatISO(startDate);
      const end_date = formatISO(endDate);

      const employee_id = selectedEmployeeId === 'self' ? undefined : selectedEmployeeId;

      const data = await leaveService.getCalendar(
        { start_date, end_date, employee_id },
        { signal: controller.signal }
      );

      if (abortControllerRef.current === controller) {
        setCalendarData(data);
      }
    } catch (err: any) {
      if (err.name === 'AbortError') return;
      const detail = err.errorData?.detail || err.errorData?.message || err.message || 'Failed to load calendar data.';
      setError(detail);
    } finally {
      setLoading(false);
    }
  }, [currentDate, selectedEmployeeId]);

  useEffect(() => {
    fetchCalendar();
  }, [fetchCalendar]);

  // Month navigation handlers
  const handlePrevMonth = () => {
    setCurrentDate((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1));
  };

  const handleNextMonth = () => {
    setCurrentDate((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1));
  };

  const handleToday = () => {
    setCurrentDate(new Date());
  };

  // Compute summary metrics from calendar days
  const days = calendarData?.days || [];
  const totalDays = days.length;
  const holidaysCount = days.filter((d) => d.holiday !== null).length;
  const leavesCount = days.filter((d) => d.leave !== null).length;
  const workingDaysCount = days.filter((d) => d.is_working_day && !d.leave).length;
  const weekendDaysCount = days.filter((d) => !d.is_working_day && !d.holiday).length;

  // Calendar grid calculations
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const firstDayOfMonth = new Date(year, month, 1).getDay(); // 0 = Sun, 1 = Mon ...
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  // Map calendarData days by date string for O(1) cell lookup
  const dayDataMap = new Map<string, CalendarDay>();
  days.forEach((day) => {
    dayDataMap.set(day.date, day);
  });

  const monthName = currentDate.toLocaleString('default', { month: 'long' });
  const todayStr = formatISO(new Date());

  // Selected employee label
  const selectedEmpObj = employees.find((e) => String(e.id) === selectedEmployeeId);
  const employeeDisplay = selectedEmployeeId === 'self'
    ? 'My Calendar'
    : selectedEmpObj
      ? `${selectedEmpObj.first_name} ${selectedEmpObj.last_name} (${selectedEmpObj.employee_code})`
      : `Employee #${selectedEmployeeId}`;

  return (
    <div className="container" style={{ paddingBottom: '3rem' }}>
      <PageHeader
        title="Employee Calendar"
        subtitle="View work schedule, branch holidays, and approved leaves."
      />

      {error && (
        <AlertBanner
          type="error"
          message={error}
        />
      )}

      {/* Top Controls Bar: Month Switcher & Employee Selector */}
      <div
        className="card"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          padding: '1rem 1.5rem',
          marginBottom: '1.5rem',
        }}
      >
        {/* Month Navigation */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handlePrevMonth}
            aria-label="Previous Month"
            style={{ padding: '0.5rem 0.75rem', display: 'flex', alignItems: 'center' }}
          >
            <ChevronLeft size={18} />
          </button>

          <div style={{ minWidth: '180px', textAlign: 'center' }}>
            <h2
              style={{
                margin: 0,
                fontSize: '1.25rem',
                fontWeight: 700,
                color: 'var(--color-text-main)',
              }}
            >
              {monthName} {year}
            </h2>
          </div>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleNextMonth}
            aria-label="Next Month"
            style={{ padding: '0.5rem 0.75rem', display: 'flex', alignItems: 'center' }}
          >
            <ChevronRight size={18} />
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleToday}
            style={{ padding: '0.5rem 0.875rem', fontSize: '0.875rem' }}
          >
            Today
          </button>
        </div>

        {/* Manager/HR Employee Selector */}
        {canViewOthers && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <label
              htmlFor="calendar-employee-select"
              style={{
                fontSize: '0.875rem',
                fontWeight: 500,
                color: 'var(--color-text-sub)',
                display: 'flex',
                alignItems: 'center',
                gap: '0.375rem',
              }}
            >
              <Users size={16} /> Employee:
            </label>
            <select
              id="calendar-employee-select"
              className="form-control"
              value={selectedEmployeeId}
              onChange={(e) => setSelectedEmployeeId(e.target.value)}
              disabled={loadingEmployees}
              style={{
                minWidth: '220px',
                padding: '0.45rem 0.75rem',
                fontSize: '0.875rem',
                borderRadius: '8px',
              }}
            >
              <option value="self">My Calendar</option>
              {employees.map((emp) => (
                <option key={emp.id} value={String(emp.id)}>
                  {emp.first_name} {emp.last_name} ({emp.employee_code})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* KPI Stats Overview */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <StatCard
          title="Total Days"
          value={totalDays}
          icon={CalendarIcon}
          color="var(--color-secondary)"
        />
        <StatCard
          title="Scheduled Work Days"
          value={workingDaysCount}
          icon={Briefcase}
          color="var(--color-status-success)"
        />
        <StatCard
          title="Branch Holidays"
          value={holidaysCount}
          icon={Sparkles}
          color="var(--color-primary)"
        />
        <StatCard
          title="Approved Leaves"
          value={leavesCount}
          icon={Coffee}
          color="var(--color-status-warning)"
        />
        <StatCard
          title="Weekends & Off Days"
          value={weekendDaysCount}
          icon={Moon}
          color="var(--color-status-neutral)"
        />
      </div>

      {/* Main Calendar Card */}
      <Card
        title={`${employeeDisplay} — ${monthName} ${year}`}
      >
        {/* Legend */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: '1.25rem',
            padding: '0.75rem 1rem',
            backgroundColor: 'var(--color-bg-subtle, #f8fafc)',
            borderRadius: '8px',
            marginBottom: '1.25rem',
            fontSize: '0.8125rem',
            color: 'var(--color-text-sub)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
            <span
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '3px',
                backgroundColor: 'var(--color-status-success-bg, #ecfdf5)',
                border: '1px solid var(--color-status-success-border, #a7f3d0)',
              }}
            />
            <span>Scheduled Working Day</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
            <span
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '3px',
                backgroundColor: 'var(--color-primary-light, #f5f3ff)',
                border: '1px solid var(--color-primary-border, #ddd6fe)',
              }}
            />
            <span>Public Holiday</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
            <span
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '3px',
                backgroundColor: 'var(--color-status-warning-bg, #fffbeb)',
                border: '1px solid var(--color-status-warning-border, #fde68a)',
              }}
            />
            <span>Approved Leave</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
            <span
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '3px',
                backgroundColor: '#f1f5f9',
                border: '1px solid #e2e8f0',
              }}
            />
            <span>Weekend / Rest Day</span>
          </div>
        </div>

        {/* Loading overlay or Calendar Grid */}
        {loading ? (
          <div
            style={{
              padding: '4rem 1rem',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '1rem',
            }}
          >
            <Loader2 size={32} className="spin" style={{ color: 'var(--color-primary)' }} />
            <p style={{ margin: 0, color: 'var(--color-text-muted)' }}>
              Loading calendar schedule...
            </p>
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(7, minmax(0, 1fr))',
              gap: '6px',
              width: '100%',
            }}
          >
            {/* Weekday headers */}
            {WEEKDAYS.map((day) => (
              <div
                key={day}
                style={{
                  padding: '0.625rem 0.25rem',
                  textAlign: 'center',
                  fontWeight: 600,
                  fontSize: '0.8125rem',
                  color: 'var(--color-text-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  borderBottom: '1px solid var(--color-border)',
                }}
              >
                {day}
              </div>
            ))}

            {/* Empty offset padding for days before month start */}
            {Array.from({ length: firstDayOfMonth }).map((_, idx) => (
              <div
                key={`empty-${idx}`}
                style={{
                  minHeight: '96px',
                  backgroundColor: 'transparent',
                  borderRadius: '8px',
                  border: '1px dashed transparent',
                }}
              />
            ))}

            {/* Day Cells */}
            {Array.from({ length: daysInMonth }).map((_, idx) => {
              const dayNum = idx + 1;
              const dateObj = new Date(year, month, dayNum);
              const dateStr = formatISO(dateObj);
              const dayData = dayDataMap.get(dateStr);
              const isToday = dateStr === todayStr;

              const isWorkingDay = dayData ? dayData.is_working_day : false;
              const holiday = dayData?.holiday || null;
              const leave = dayData?.leave || null;

              // Determine visual styling
              let cellBg = 'var(--color-bg-card, #ffffff)';
              let borderColor = 'var(--color-border, #e2e8f0)';

              if (holiday) {
                cellBg = 'var(--color-primary-light, #f5f3ff)';
                borderColor = 'var(--color-primary-border, #ddd6fe)';
              } else if (leave) {
                cellBg = 'var(--color-status-warning-bg, #fffbeb)';
                borderColor = 'var(--color-status-warning-border, #fde68a)';
              } else if (isWorkingDay) {
                cellBg = '#ffffff';
                borderColor = 'var(--color-border, #e2e8f0)';
              } else {
                // Weekend / Off Day
                cellBg = 'var(--color-bg-subtle, #f8fafc)';
                borderColor = '#edf2f7';
              }

              if (isToday) {
                borderColor = 'var(--color-primary, var(--color-primary))';
              }

              return (
                <div
                  key={dateStr}
                  onClick={() => dayData && setSelectedDay(dayData)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      if (dayData) setSelectedDay(dayData);
                    }
                  }}
                  style={{
                    minHeight: '100px',
                    padding: '0.5rem',
                    borderRadius: '8px',
                    backgroundColor: cellBg,
                    border: `1.5px solid ${borderColor}`,
                    boxShadow: isToday ? '0 0 0 2px var(--color-primary-glow)' : 'none',
                    cursor: dayData ? 'pointer' : 'default',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    transition: 'all 0.15s ease-in-out',
                    position: 'relative',
                  }}
                >
                  {/* Cell Header: Day number & Today Badge */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '0.375rem',
                    }}
                  >
                    <span
                      style={{
                        fontWeight: isToday ? 700 : 600,
                        fontSize: '0.875rem',
                        color: isToday
                          ? 'var(--color-primary)'
                          : isWorkingDay
                            ? 'var(--color-text-main)'
                            : 'var(--color-text-muted)',
                      }}
                    >
                      {dayNum}
                    </span>

                    {isToday && (
                      <span
                        style={{
                          fontSize: '0.6875rem',
                          fontWeight: 700,
                          backgroundColor: 'var(--color-primary)',
                          color: '#ffffff',
                          padding: '1px 6px',
                          borderRadius: '10px',
                        }}
                      >
                        Today
                      </span>
                    )}
                  </div>

                  {/* Day Badges / Indicators */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                    {holiday && (
                      <div
                        style={{
                          fontSize: '0.6875rem',
                          fontWeight: 600,
                          backgroundColor: 'var(--color-primary)',
                          color: '#ffffff',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '3px',
                        }}
                        title={`Holiday: ${holiday.name}`}
                      >
                        <Sparkles size={10} />
                        <span>{holiday.name}</span>
                      </div>
                    )}

                    {leave && (
                      <div
                        style={{
                          fontSize: '0.6875rem',
                          fontWeight: 600,
                          backgroundColor: 'var(--color-status-warning)',
                          color: '#ffffff',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '3px',
                        }}
                        title={`Leave: ${leave.leave_type_name} (${leave.duration_days}d)`}
                      >
                        <Coffee size={10} />
                        <span>
                          {leave.leave_type_name} {leave.is_half_day ? '(Half)' : ''}
                        </span>
                      </div>
                    )}

                    {!holiday && !leave && !isWorkingDay && (
                      <div
                        style={{
                          fontSize: '0.6875rem',
                          fontWeight: 500,
                          color: 'var(--color-text-muted)',
                          padding: '2px 4px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '3px',
                        }}
                      >
                        <Moon size={10} />
                        <span>Off</span>
                      </div>
                    )}

                    {!holiday && !leave && isWorkingDay && (
                      <div
                        style={{
                          fontSize: '0.6875rem',
                          color: 'var(--color-status-success)',
                          fontWeight: 500,
                          padding: '2px 4px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '3px',
                        }}
                      >
                        <span
                          style={{
                            width: '6px',
                            height: '6px',
                            borderRadius: '50%',
                            backgroundColor: 'var(--color-status-success)',
                          }}
                        />
                        <span>Work</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Day Details Modal */}
      {selectedDay && (
        <Modal
          title={`Schedule Details — ${selectedDay.date}`}
          onClose={() => setSelectedDay(null)}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div
              style={{
                padding: '1rem',
                backgroundColor: 'var(--color-bg-subtle, #f8fafc)',
                borderRadius: '8px',
                border: '1px solid var(--color-border)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '0.75rem',
                }}
              >
                <span style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                  Date:
                </span>
                <span style={{ fontWeight: 600, color: 'var(--color-text-main)' }}>
                  {new Date(selectedDay.date + 'T00:00:00').toLocaleDateString(undefined, {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                  })}
                </span>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '0.75rem',
                }}
              >
                <span style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                  Work Day Status:
                </span>
                <span
                  style={{
                    fontWeight: 600,
                    color: selectedDay.is_working_day
                      ? 'var(--color-status-success)'
                      : 'var(--color-status-neutral)',
                  }}
                >
                  {selectedDay.is_working_day ? 'Working Day' : 'Non-Working Day / Rest Day'}
                </span>
              </div>

              {selectedDay.holiday && (
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '0.75rem',
                  }}
                >
                  <span style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                    Public Holiday:
                  </span>
                  <span
                    style={{
                      fontWeight: 600,
                      color: 'var(--color-primary)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <Sparkles size={14} />
                    {selectedDay.holiday.name}
                  </span>
                </div>
              )}

              {selectedDay.leave && (
                <>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '0.75rem',
                    }}
                  >
                    <span style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                      Approved Leave:
                    </span>
                    <span
                      style={{
                        fontWeight: 600,
                        color: 'var(--color-status-warning)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                      }}
                    >
                      <Coffee size={14} />
                      {selectedDay.leave.leave_type_name}
                    </span>
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <span style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                      Duration:
                    </span>
                    <span style={{ fontWeight: 500, color: 'var(--color-text-main)' }}>
                      {selectedDay.leave.is_half_day ? 'Half Day' : `${selectedDay.leave.duration_days} Day(s)`}
                    </span>
                  </div>
                </>
              )}
            </div>

            {/* Quick Actions in Modal */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setSelectedDay(null)}
              >
                Close
              </button>

              {selectedDay.is_working_day && !selectedDay.leave && !selectedDay.holiday && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    setSelectedDay(null);
                    navigate('/leaves');
                  }}
                >
                  Apply For Leave
                </button>
              )}
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
