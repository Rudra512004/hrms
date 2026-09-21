import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  employeeManagementService,
  ApiError,
  type ProvisionEmployeeData,
  type EmployeeTransferPayload,
  type EmployeePromotionPayload,
  type EmployeeExitPayload
} from '../employeeManagement';
import { organizationService } from '../organization';
import { branchService } from '../branch';

describe('C5.1 Frontend Service / API Contract Implementation Suite', () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', mockFetch);
    localStorage.setItem('auth_token', 'test-token-xyz');
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  // 1. Employee list request (with and without query params)
  describe('1. Employee List Request', () => {
    it('fetches employee list from GET /api/v1/employees/management/ with auth headers', async () => {
      const mockEmployees = [
        { id: 1, first_name: 'Alice', last_name: 'Smith', email: 'alice@company.com' }
      ];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockEmployees
      });

      const result = await employeeManagementService.listEmployees();

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/employees/management/');
      expect(options.headers).toMatchObject({
        'Authorization': 'Token test-token-xyz',
        'Accept': 'application/json'
      });
      expect(result).toEqual(mockEmployees);
    });

    it('correctly appends branch_id, search, and status query parameters', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => []
      });

      await employeeManagementService.listEmployees({
        branch_id: 2,
        search: 'developer',
        status: 'active'
      });

      const [url] = mockFetch.mock.calls[0];
      const parsedUrl = new URL(url, 'http://localhost');
      expect(parsedUrl.pathname).toBe('/api/v1/employees/management/');
      expect(parsedUrl.searchParams.get('branch_id')).toBe('2');
      expect(parsedUrl.searchParams.get('search')).toBe('developer');
      expect(parsedUrl.searchParams.get('status')).toBe('active');
    });
  });

  // 2. Employee create payload
  describe('2. Employee Create Payload', () => {
    it('sends POST to /api/v1/employees/management/ with full hierarchical data', async () => {
      const payload: ProvisionEmployeeData = {
        email: 'bob@company.com',
        first_name: 'Bob',
        last_name: 'Jones',
        personal_email: 'bob.personal@gmail.com',
        employee_code: 'EMP100',
        branch: 1,
        department: 2,
        team: 3,
        designation: 4,
        reporting_manager: 5,
        role: 2
      };

      const mockResponse = {
        detail: 'Employee provisioned successfully.',
        employee: { id: 10, ...payload }
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => mockResponse
      });

      const result = await employeeManagementService.createEmployee(payload);

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/employees/management/');
      expect(options.method).toBe('POST');
      expect(options.headers).toMatchObject({
        'Authorization': 'Token test-token-xyz',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      });
      expect(JSON.parse(options.body)).toEqual(payload);
      expect(result).toEqual(mockResponse);
    });

    it('allows omitting parent branch/department when team is supplied', async () => {
      const payload: ProvisionEmployeeData = {
        email: 'charlie@company.com',
        first_name: 'Charlie',
        last_name: 'Brown',
        team: 5
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => ({ detail: 'Created', employee: { id: 11, ...payload } })
      });

      await employeeManagementService.createEmployee(payload);

      const [, options] = mockFetch.mock.calls[0];
      const sentBody = JSON.parse(options.body);
      expect(sentBody.team).toBe(5);
      expect(sentBody.branch).toBeUndefined();
      expect(sentBody.department).toBeUndefined();
    });
  });

  // 3. Employee update payload
  describe('3. Employee Update Payload', () => {
    it('sends PATCH to /api/v1/employees/management/{id}/', async () => {
      const updateData = {
        phone_number: '+15551234567',
        address: '456 Tech Ave',
        team: 7
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 12, ...updateData })
      });

      const result = await employeeManagementService.updateEmployee(12, updateData);

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/employees/management/12/');
      expect(options.method).toBe('PATCH');
      expect(JSON.parse(options.body)).toEqual(updateData);
      expect(result).toMatchObject({ id: 12, phone_number: '+15551234567' });
    });
  });

  // 4. Transfer endpoint/method
  describe('4. Transfer Endpoint / Method', () => {
    it('strictly uses POST to /api/v1/employees/management/{id}/transfer/', async () => {
      const transferPayload: EmployeeTransferPayload = {
        branch: 2,
        department: 4,
        team: 8,
        effective_date: '2026-10-01',
        reason: 'Relocation to London office'
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 15, branch: 2, department: 4, team: 8 })
      });

      const result = await employeeManagementService.transferEmployee(15, transferPayload);

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/employees/management/15/transfer/');
      expect(options.method).toBe('POST');
      expect(options.headers).toMatchObject({
        'Authorization': 'Token test-token-xyz',
        'Content-Type': 'application/json'
      });
      expect(JSON.parse(options.body)).toEqual(transferPayload);
      expect(result.branch).toBe(2);
    });

    it('supports omitting branch and department when team is provided', async () => {
      const payload: EmployeeTransferPayload = {
        team: 12,
        effective_date: '2026-10-15'
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 15, team: 12 })
      });

      await employeeManagementService.transferEmployee(15, payload);

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/employees/management/15/transfer/');
      expect(JSON.parse(options.body)).toEqual(payload);
    });
  });

  // 5. Promote endpoint/method
  describe('5. Promote Endpoint / Method', () => {
    it('strictly uses POST to /api/v1/employees/management/{id}/promote/', async () => {
      const promotionPayload: EmployeePromotionPayload = {
        designation: 6,
        effective_date: '2026-11-01',
        reason: 'Exceeded performance targets',
        new_basic_salary: '85000.00'
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 18, designation: 6 })
      });

      const result = await employeeManagementService.promoteEmployee(18, promotionPayload);

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/employees/management/18/promote/');
      expect(options.method).toBe('POST');
      expect(JSON.parse(options.body)).toEqual(promotionPayload);
      expect(result.designation).toBe(6);
    });
  });

  // 6. Exit endpoint/method
  describe('6. Exit Endpoint / Method', () => {
    it('strictly uses POST to /api/v1/employees/management/{id}/exit/', async () => {
      const exitPayload: EmployeeExitPayload = {
        exit_type: 'resignation',
        exit_date: '2026-11-30',
        exit_reason: 'Accepted offer at university',
        resignation_date: '2026-10-31',
        notice_period_start: '2026-11-01',
        notice_period_end: '2026-11-30',
        set_notice_status: true
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 20, employment_status: 'on_notice' })
      });

      const result = await employeeManagementService.exitEmployee(20, exitPayload);

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/employees/management/20/exit/');
      expect(options.method).toBe('POST');
      expect(JSON.parse(options.body)).toEqual(exitPayload);
      expect(result.employment_status).toBe('on_notice');
    });
  });

  // 7. Activate / deactivate / reactivate / lifecycle endpoints
  describe('7. Activate / Deactivate / Reactivate Endpoints', () => {
    it('activateEmployee uses POST to /api/v1/employees/management/{id}/activate/', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 22, status: 'active' })
      });

      const result = await employeeManagementService.activateEmployee(22);

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/employees/management/22/activate/');
      expect(options.method).toBe('POST');
      expect(result.status).toBe('active');
    });

    it('deactivateEmployee uses POST to /api/v1/employees/management/{id}/deactivate/', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 22, status: 'inactive' })
      });

      const result = await employeeManagementService.deactivateEmployee(22);

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/employees/management/22/deactivate/');
      expect(options.method).toBe('POST');
      expect(result.status).toBe('inactive');
    });

    it('reactivateEmployee uses POST to /api/v1/employees/management/{id}/reactivate/', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 22, employment_status: 'active' })
      });

      const result = await employeeManagementService.reactivateEmployee(22, {
        reason: 'Rehired on new contract'
      });

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/employees/management/22/reactivate/');
      expect(options.method).toBe('POST');
      expect(JSON.parse(options.body)).toEqual({ reason: 'Rehired on new contract' });
      expect(result.employment_status).toBe('active');
    });

    it('changeEmploymentStatus uses POST to /api/v1/employees/management/{id}/change_employment_status/', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 22, employment_status: 'probation' })
      });

      const result = await employeeManagementService.changeEmploymentStatus(22, {
        employment_status: 'probation',
        reason: 'Contract extension'
      });

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/employees/management/22/change_employment_status/');
      expect(options.method).toBe('POST');
      expect(JSON.parse(options.body)).toEqual({
        employment_status: 'probation',
        reason: 'Contract extension'
      });
      expect(result.employment_status).toBe('probation');
    });

    it('getLifecycleHistory uses GET to /api/v1/employees/management/{id}/lifecycle_history/', async () => {
      const mockHistory = [
        { id: 1, event_type: 'transfer', effective_date: '2026-09-01' }
      ];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockHistory
      });

      const result = await employeeManagementService.getLifecycleHistory(22);

      const [url] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/employees/management/22/lifecycle_history/');
      expect(result).toEqual(mockHistory);
    });
  });

  // 8. Branch selector request
  describe('8. Branch Selector Request', () => {
    it('organizationService.listBranches fetches from /api/v1/organization/branches/', async () => {
      const mockBranches = [{ id: 1, name: 'Headquarters' }];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockBranches
      });

      const result = await organizationService.listBranches();

      const [url] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/branches/');
      expect(result).toEqual(mockBranches);
    });

    it('branchService.listBranches also routes to /api/v1/organization/branches/', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [{ id: 2, name: 'London Branch' }]
      });

      const result = await branchService.listBranches();

      const [url] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/branches/');
      expect(result[0].name).toBe('London Branch');
    });
  });

  // 9. Department selector request with branch filter
  describe('9. Department Selector Request with Branch Filter', () => {
    it('appends ?branch=<id> cascade filter parameter', async () => {
      const mockDepartments = [
        { id: 10, branch: 3, name: 'Engineering', description: 'Tech', is_active: true, organization: 1 }
      ];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockDepartments
      });

      const result = await organizationService.listDepartments(3);

      const [url] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/departments/?branch=3');
      expect(result).toEqual(mockDepartments);
    });

    it('omits branch query param when branchId is not provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => []
      });

      await organizationService.listDepartments();

      const [url] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/departments/');
    });
  });

  // 10. Team selector request with department filter
  describe('10. Team Selector Request with Department Filter', () => {
    it('appends ?department=<id> cascade filter parameter', async () => {
      const mockTeams = [
        { id: 100, department: 10, name: 'Backend Platform', description: 'API', is_active: true }
      ];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTeams
      });

      const result = await organizationService.listTeams(10);

      const [url] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/teams/?department=10');
      expect(result).toEqual(mockTeams);
    });

    it('supports team creation via POST /api/v1/organization/teams/', async () => {
      const teamData = { department: 10, name: 'Frontend Guild', description: 'UI', is_active: true };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => ({ id: 101, ...teamData })
      });

      const result = await organizationService.createTeam(teamData);

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/v1/organization/teams/');
      expect(options.method).toBe('POST');
      expect(JSON.parse(options.body)).toEqual(teamData);
      expect(result.id).toBe(101);
    });
  });

  // 11. 403 Forbidden propagation
  describe('11. 403 Forbidden Propagation', () => {
    it('propagates 403 with response and errorData intact without converting to 400', async () => {
      const forbiddenErrorBody = {
        detail: 'You do not have permission to transfer employees into this organizational unit.'
      };
      const responseMock = {
        ok: false,
        status: 403,
        json: async () => forbiddenErrorBody
      } as unknown as Response;

      mockFetch.mockResolvedValueOnce(responseMock);

      await expect(
        employeeManagementService.transferEmployee(10, {
          branch: 99,
          effective_date: '2026-10-01'
        })
      ).rejects.toMatchObject({
        status: 403,
        errorData: forbiddenErrorBody,
        response: expect.objectContaining({ status: 403 })
      });
    });

    it('retains ApiError instance properties for 403', async () => {
      const forbiddenErrorBody = { detail: 'Permission denied.' };
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => forbiddenErrorBody
      });

      try {
        await employeeManagementService.promoteEmployee(10, {
          designation: 99,
          effective_date: '2026-10-01'
        });
        expect.unreachable('Should have thrown ApiError');
      } catch (err: any) {
        expect(err).toBeInstanceOf(ApiError);
        expect(err.status).toBe(403);
        expect(err.errorData.detail).toBe('Permission denied.');
        expect(err.message).toContain('Permission denied');
      }
    });
  });

  // 12. Validation error (400) propagation
  describe('12. Validation-Error Propagation (400)', () => {
    it('preserves field-level validation errors in errorData', async () => {
      const validationErrors = {
        team: ['Team must belong to the same department as the employee.'],
        reporting_manager: ['Reporting manager must be an active employee.']
      };

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => validationErrors
      });

      try {
        await employeeManagementService.createEmployee({
          email: 'invalid@example.com',
          first_name: 'Invalid',
          last_name: 'Test',
          team: 99
        });
        expect.unreachable('Should have thrown ApiError');
      } catch (err: any) {
        expect(err).toBeInstanceOf(ApiError);
        expect(err.status).toBe(400);
        expect(err.errorData.team).toEqual(['Team must belong to the same department as the employee.']);
        expect(err.errorData.reporting_manager).toEqual(['Reporting manager must be an active employee.']);
      }
    });

    it('preserves 405 Method Not Allowed when delete is attempted', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 405,
        json: async () => ({ detail: 'Method "DELETE" not allowed.' })
      });

      // Simulating a raw call or handler response
      const response = await fetch('/api/v1/employees/management/1/', { method: 'DELETE' });
      expect(response.status).toBe(405);
    });
  });
});
