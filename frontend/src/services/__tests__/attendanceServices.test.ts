import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { attendanceService, ApiError } from '../attendance';
import { holidayService } from '../holiday';
import { shiftService } from '../shift';
import { workingCalendarService } from '../workingCalendar';
import { attendancePolicyService } from '../attendancePolicy';

describe('C5.5.3 Frontend Attendance Services & API Contract Suite', () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', mockFetch);
    localStorage.setItem('auth_token', 'test-auth-token-123');
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  // ==========================================
  // 1. ATTENDANCE SERVICE (SELF & MANAGEMENT)
  // ==========================================
  describe('1. Attendance Service', () => {
    it('checkIn sends POST to /api/v1/attendance/check-in/ with location data and auth token', async () => {
      const mockRecord = {
        id: 101,
        employee: 5,
        date: '2026-09-21',
        check_in: '2026-09-21T09:02:00Z',
        check_out: null,
        status: 'present',
        is_late: false,
        total_break_duration: null,
        productive_work_duration: null,
        is_on_break: false,
        breaks: [],
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => mockRecord,
      });

      const location = { latitude: 12.9716, longitude: 77.5946, accuracy: 15.0 };
      const res = await attendanceService.checkIn(location);

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/attendance/check-in/');
      expect(opts.method).toBe('POST');
      expect(opts.headers).toMatchObject({
        'Authorization': 'Token test-auth-token-123',
        'Content-Type': 'application/json',
      });
      expect(JSON.parse(opts.body)).toEqual(location);
      expect(res).toEqual(mockRecord);
    });

    it('checkOut sends POST to /api/v1/attendance/check-out/', async () => {
      const mockRecord = {
        id: 101,
        employee: 5,
        date: '2026-09-21',
        check_in: '2026-09-21T09:00:00Z',
        check_out: '2026-09-21T17:00:00Z',
        status: 'present',
        is_late: false,
        total_break_duration: '00:30:00',
        productive_work_duration: '07:30:00',
        is_on_break: false,
        breaks: [],
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockRecord,
      });

      const res = await attendanceService.checkOut();
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/attendance/check-out/');
      expect(opts.method).toBe('POST');
      expect(res).toEqual(mockRecord);
    });

    it('startBreak sends POST to /api/v1/attendance/start-break/', async () => {
      const mockRecord = {
        id: 101,
        is_on_break: true,
        breaks: [{ id: 1, started_at: '2026-09-21T13:00:00Z', ended_at: null }],
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockRecord,
      });

      const res = await attendanceService.startBreak();
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/attendance/start-break/');
      expect(opts.method).toBe('POST');
      expect(res.is_on_break).toBe(true);
    });

    it('endBreak sends POST to /api/v1/attendance/end-break/', async () => {
      const mockRecord = {
        id: 101,
        is_on_break: false,
        breaks: [{ id: 1, started_at: '2026-09-21T13:00:00Z', ended_at: '2026-09-21T13:30:00Z' }],
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockRecord,
      });

      const res = await attendanceService.endBreak();
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/attendance/end-break/');
      expect(opts.method).toBe('POST');
      expect(res.is_on_break).toBe(false);
    });

    it('getHistory sends GET to /api/v1/attendance/ and passes AbortSignal', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      });

      const controller = new AbortController();
      const res = await attendanceService.getHistory({ signal: controller.signal });

      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/attendance/');
      expect(opts.signal).toBe(controller.signal);
      expect(res).toEqual([]);
    });

    it('getManagementHistory without params requests organization-wide aggregate', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      });

      await attendanceService.getManagementHistory();
      const [url] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/attendance/management/');
    });

    it('getManagementHistory correctly appends branch_id, team_id, and date query parameters', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      });

      const controller = new AbortController();
      await attendanceService.getManagementHistory(
        { branch_id: 3, team_id: 7, date: '2026-09-21' },
        { signal: controller.signal }
      );

      const [url, opts] = mockFetch.mock.calls[0];
      const parsedUrl = new URL(url, 'http://localhost');
      expect(parsedUrl.pathname).toBe('/api/v1/attendance/management/');
      expect(parsedUrl.searchParams.get('branch_id')).toBe('3');
      expect(parsedUrl.searchParams.get('team_id')).toBe('7');
      expect(parsedUrl.searchParams.get('date')).toBe('2026-09-21');
      expect(opts.signal).toBe(controller.signal);
    });

    it('getManagementHistory omits branch_id when branch selection is "all"', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      });

      await attendanceService.getManagementHistory({ branch_id: 'all', date: '2026-09-21' });
      const [url] = mockFetch.mock.calls[0];
      const parsedUrl = new URL(url, 'http://localhost');
      expect(parsedUrl.searchParams.has('branch_id')).toBe(false);
      expect(parsedUrl.searchParams.get('date')).toBe('2026-09-21');
    });

    it('propagates C5.5.2.1 missing WorkingCalendar configuration error as ApiError', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({
          detail: 'Working calendar is not configured for branch 3.',
        }),
      });

      try {
        await attendanceService.checkIn();
        expect.unreachable('Should have thrown ApiError');
      } catch (err: any) {
        expect(err).toBeInstanceOf(ApiError);
        expect(err.status).toBe(400);
        expect(err.message).toBe('Working calendar is not configured for branch 3.');
        expect(err.errorData.detail).toBe('Working calendar is not configured for branch 3.');
      }
    });

    it('propagates C5.5.2.1 missing shift assignment configuration error as ApiError', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({
          detail: 'No effective shift assignment for employee 5 on 2026-09-21.',
        }),
      });

      try {
        await attendanceService.checkIn();
        expect.unreachable('Should have thrown ApiError');
      } catch (err: any) {
        expect(err).toBeInstanceOf(ApiError);
        expect(err.status).toBe(400);
        expect(err.message).toBe('No effective shift assignment for employee 5 on 2026-09-21.');
      }
    });

    it('propagates 403 Forbidden on management history without silent failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({
          detail: 'You do not have permission to view attendance.',
        }),
      });

      try {
        await attendanceService.getManagementHistory();
        expect.unreachable('Should have thrown ApiError');
      } catch (err: any) {
        expect(err).toBeInstanceOf(ApiError);
        expect(err.status).toBe(403);
      }
    });
  });

  // ==========================================
  // 2. HOLIDAY SERVICE
  // ==========================================
  describe('2. Holiday Service', () => {
    it('listHolidays filters by branch_id and passes AbortSignal', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [{ id: 1, branch: 2, name: 'National Day', date: '2026-10-02', is_active: true }],
      });

      const controller = new AbortController();
      const res = await holidayService.listHolidays({ branch_id: 2 }, { signal: controller.signal });

      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/attendance/holidays/?branch_id=2');
      expect(opts.signal).toBe(controller.signal);
      expect(res.length).toBe(1);
      expect(res[0].branch).toBe(2);
    });

    it('create sends POST to /api/v1/attendance/holidays/', async () => {
      const payload = { branch: 2, name: 'New Year', date: '2027-01-01', is_active: true };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => ({ id: 2, ...payload, created_at: '', updated_at: '' }),
      });

      const res = await holidayService.create(payload);
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/attendance/holidays/');
      expect(opts.method).toBe('POST');
      expect(JSON.parse(opts.body)).toEqual(payload);
      expect(res.name).toBe('New Year');
    });

    it('update sends PATCH to /api/v1/attendance/holidays/:id/', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 2, name: 'Updated Holiday', branch: 2, date: '2027-01-01', is_active: false }),
      });

      const res = await holidayService.update(2, { is_active: false });
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/attendance/holidays/2/');
      expect(opts.method).toBe('PATCH');
      expect(res.is_active).toBe(false);
    });

    it('delete sends DELETE to /api/v1/attendance/holidays/:id/', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await holidayService.delete(2);
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/attendance/holidays/2/');
      expect(opts.method).toBe('DELETE');
    });

    it('propagates ApiError on holiday creation failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ branch: ['You do not have permission to manage holidays for this branch.'] }),
      });

      try {
        await holidayService.create({ branch: 99, name: 'Test', date: '2026-10-01' });
        expect.unreachable('Should have thrown ApiError');
      } catch (err: any) {
        expect(err).toBeInstanceOf(ApiError);
        expect(err.status).toBe(400);
      }
    });
  });

  // ==========================================
  // 3. SHIFT SERVICE
  // ==========================================
  describe('3. Shift Service', () => {
    it('listShifts filters by branch_id and passes AbortSignal', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      });

      const controller = new AbortController();
      await shiftService.listShifts({ branch_id: 4 }, { signal: controller.signal });

      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/attendance/shifts/?branch_id=4');
      expect(opts.signal).toBe(controller.signal);
    });

    it('create sends full C5.5.2 shift parameters in payload', async () => {
      const payload = {
        branch: 4,
        name: 'Morning Shift',
        start_time: '08:00',
        end_time: '16:00',
        grace_period: '00:15:00',
        full_day_hours: '08:00:00',
        half_day_hours: '04:00:00',
        work_days: '0,1,2,3,4',
        is_active: true,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => ({ id: 10, ...payload, created_at: '', updated_at: '' }),
      });

      const res = await shiftService.create(payload);
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/attendance/shifts/');
      expect(opts.method).toBe('POST');
      expect(JSON.parse(opts.body)).toEqual(payload);
      expect(res.id).toBe(10);
      expect(res.work_days).toBe('0,1,2,3,4');
    });

    it('update sends PATCH to /api/v1/attendance/shifts/:id/', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 10, grace_period: '00:20:00' }),
      });

      await shiftService.update(10, { grace_period: '00:20:00' });
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/attendance/shifts/10/');
      expect(opts.method).toBe('PATCH');
      expect(JSON.parse(opts.body)).toEqual({ grace_period: '00:20:00' });
    });

    it('delete sends DELETE to /api/v1/attendance/shifts/:id/', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await shiftService.delete(10);
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/attendance/shifts/10/');
      expect(opts.method).toBe('DELETE');
    });
  });

  // ==========================================
  // 4. WORKING CALENDAR SERVICE
  // ==========================================
  describe('4. Working Calendar Service', () => {
    it('listWorkingCalendars fetches from /api/v1/organization/working-calendars/', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [{ id: 1, branch: 2, work_days: '0,1,2,3,4' }],
      });

      const controller = new AbortController();
      const res = await workingCalendarService.listWorkingCalendars({ signal: controller.signal });
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/working-calendars/');
      expect(opts.signal).toBe(controller.signal);
      expect(res.length).toBe(1);
    });

    it('getWorkingCalendar fetches calendar by ID', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 1, branch: 2, work_days: '0,1,2,3,4' }),
      });

      const res = await workingCalendarService.getWorkingCalendar(1);
      const [url] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/working-calendars/1/');
      expect(res.work_days).toBe('0,1,2,3,4');
    });

    it('updateWorkingCalendar sends PATCH with new work_days', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 1, branch: 2, work_days: '6,0,1,2,3' }),
      });

      const res = await workingCalendarService.updateWorkingCalendar(1, { work_days: '6,0,1,2,3' });
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/working-calendars/1/');
      expect(opts.method).toBe('PATCH');
      expect(JSON.parse(opts.body)).toEqual({ work_days: '6,0,1,2,3' });
      expect(res.work_days).toBe('6,0,1,2,3');
    });

    it('getWorkDaysList parses work_days without fallback and throws on missing configuration', () => {
      expect(workingCalendarService.getWorkDaysList({ work_days: '0,1,2,3,4' })).toEqual([0, 1, 2, 3, 4]);
      expect(workingCalendarService.getWorkDaysList({ work_days: '6,0,1,2,3' })).toEqual([6, 0, 1, 2, 3]);

      // Strict enforcement: throws rather than falling back to Mon-Fri
      expect(() => workingCalendarService.getWorkDaysList({ work_days: '' })).toThrow(
        'Working calendar has unconfigured work days.'
      );
      expect(() => workingCalendarService.getWorkDaysList({ work_days: null as any })).toThrow(
        'Working calendar has unconfigured work days.'
      );
      expect(() => workingCalendarService.getWorkDaysList({ work_days: '0,M,2' })).toThrow(
        "Invalid work day 'M'."
      );
    });

    it('propagates 400 ApiError on invalid work_days format', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ work_days: ['Invalid format. Use comma separated integers.'] }),
      });

      try {
        await workingCalendarService.updateWorkingCalendar(1, { work_days: 'invalid' });
        expect.unreachable('Should have thrown ApiError');
      } catch (err: any) {
        expect(err).toBeInstanceOf(ApiError);
        expect(err.status).toBe(400);
      }
    });
  });

  // ==========================================
  // 6. ATTENDANCE POLICY SERVICE
  // ==========================================
  describe('6. Attendance Policy Service', () => {
    it('getAttendancePolicy fetches from branch endpoint', async () => {
      const mockPolicy = {
        id: 2,
        branch: 5,
        is_office_gps_enabled: true,
        is_office_ip_enabled: false,
        is_wfh_enabled: true,
        wfh_bypasses_office_restrictions: true,
        created_at: '',
        updated_at: '',
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockPolicy,
      });

      const controller = new AbortController();
      const res = await attendancePolicyService.getAttendancePolicy(5, { signal: controller.signal });

      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/branches/5/attendance-policy/');
      expect(opts.signal).toBe(controller.signal);
      expect(res).toEqual(mockPolicy);
    });

    it('updateAttendancePolicy sends PATCH to branch attendance-policy endpoint', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 2, branch: 5, is_office_gps_enabled: false }),
      });

      await attendancePolicyService.updateAttendancePolicy(5, { is_office_gps_enabled: false });
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/branches/5/attendance-policy/');
      expect(opts.method).toBe('PATCH');
      expect(JSON.parse(opts.body)).toEqual({ is_office_gps_enabled: false });
    });

    it('propagates 403 Forbidden when user lacks branch.manage', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({
          detail: 'You do not have permission to manage attendance policy for this branch.',
        }),
      });

      try {
        await attendancePolicyService.updateAttendancePolicy(5, { is_office_gps_enabled: true });
        expect.unreachable('Should have thrown ApiError');
      } catch (err: any) {
        expect(err).toBeInstanceOf(ApiError);
        expect(err.status).toBe(403);
        expect(err.message).toBe('You do not have permission to manage attendance policy for this branch.');
      }
    });
  });
});
