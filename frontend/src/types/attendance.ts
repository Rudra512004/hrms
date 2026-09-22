/**
 * Attendance & Scheduling Type Definitions
 * Aligned with backend models & serializers from C5.5.1, C5.5.2, C5.5.2.1
 */

export interface AttendanceBreak {
  id: number;
  started_at: string;
  ended_at: string | null;
}

export interface AttendanceRecord {
  id: number;
  employee: number;
  employee_name?: string;
  employee_code?: string;
  date: string;
  check_in: string | null;
  check_out: string | null;
  status: string;
  is_late: boolean;
  total_break_duration: string | null;
  productive_work_duration: string | null;
  is_on_break: boolean;
  breaks: AttendanceBreak[];
}

export interface AttendanceLocation {
  latitude: number;
  longitude: number;
  accuracy: number;
}

export interface ManagementAttendanceParams {
  branch_id?: number | string | null;
  team_id?: number | string | null;
  date?: string | null;
}

export interface Holiday {
  id: number;
  branch: number;
  organization?: any;
  name: string;
  date: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateHolidayPayload {
  branch: number;
  name: string;
  date: string;
  is_active?: boolean;
}

export interface UpdateHolidayPayload {
  branch?: number;
  name?: string;
  date?: string;
  is_active?: boolean;
}

export interface Shift {
  id: number;
  branch: number;
  organization?: any;
  name: string;
  start_time: string;
  end_time: string;
  grace_period: string | null;
  full_day_hours: string | null;
  half_day_hours: string | null;
  work_days: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateShiftPayload {
  branch: number;
  name: string;
  start_time: string;
  end_time: string;
  grace_period?: string | null;
  full_day_hours?: string | null;
  half_day_hours?: string | null;
  work_days?: string;
  is_active?: boolean;
}

export interface UpdateShiftPayload {
  branch?: number;
  name?: string;
  start_time?: string;
  end_time?: string;
  grace_period?: string | null;
  full_day_hours?: string | null;
  half_day_hours?: string | null;
  work_days?: string;
  is_active?: boolean;
}

export interface EmployeeShiftAssignment {
  id: number;
  employee: number;
  shift: number;
  effective_from: string;
  effective_to: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateShiftAssignmentPayload {
  employee: number;
  shift: number;
  effective_from: string;
  effective_to?: string | null;
}

export interface UpdateShiftAssignmentPayload {
  employee?: number;
  shift?: number;
  effective_from?: string;
  effective_to?: string | null;
}

export interface WorkingCalendarRule {
  id?: number;
  weekday: number;
  occurrence: number;
  is_working: boolean;
}

export interface WorkingCalendar {
  id: number;
  branch: number;
  work_days: string;
  recurring_rules?: WorkingCalendarRule[];
}

export interface UpdateWorkingCalendarPayload {
  work_days?: string;
  recurring_rules?: WorkingCalendarRule[];
}


export interface AttendancePolicy {
  id: number;
  branch: number;
  is_office_gps_enabled: boolean;
  is_office_ip_enabled: boolean;
  is_wfh_enabled: boolean;
  wfh_bypasses_office_restrictions: boolean;
  created_at: string;
  updated_at: string;
}

export interface UpdateAttendancePolicyPayload {
  is_office_gps_enabled?: boolean;
  is_office_ip_enabled?: boolean;
  is_wfh_enabled?: boolean;
  wfh_bypasses_office_restrictions?: boolean;
}
