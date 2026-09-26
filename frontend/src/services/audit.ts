import type { PaginatedResponse } from '../types/pagination';

export interface AuditLog {
  id: number;
  actor: number;
  actor_email: string;
  action: string;
  target_type: string;
  target_id: number | string | null;
  timestamp: string;
  metadata: Record<string, unknown>;
  ip_address: string | null;
}

export interface ListAuditLogsParams {
  paginate?: boolean;
  page?: number;
  page_size?: number;
  actor?: string;
  action?: string;
  target?: string | number;
  search?: string;
}

export const auditService = {
  getLogs: (async (
    params?: ListAuditLogsParams,
    options?: { signal?: AbortSignal }
  ): Promise<any> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');

    let url = '/api/v1/audit-logs/';
    if (params) {
      const query = new URLSearchParams();
      if (params.paginate) query.set('paginate', 'true');
      if (params.page !== undefined && params.page !== null) query.set('page', String(params.page));
      if (params.page_size !== undefined && params.page_size !== null) query.set('page_size', String(params.page_size));
      if (params.actor) query.set('actor', params.actor);
      if (params.action) query.set('action', params.action);
      if (params.target !== undefined && params.target !== null && params.target !== '') query.set('target', String(params.target));
      const qs = query.toString();
      if (qs) url += `?${qs}`;
    }

    const response = await fetch(url, {
      headers: {
        'Authorization': `Token ${token}`,
        'Accept': 'application/json'
      },
      signal: options?.signal,
    });

    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        throw new Error(`Authorization failed: ${response.status}`);
      }
      throw new Error('Failed to fetch audit logs');
    }

    const data = await response.json();
    if (params?.paginate) {
      if (Array.isArray(data)) {
        return {
          count: data.length,
          next: null,
          previous: null,
          results: data,
        };
      }
      return data;
    }
    return data;
  }) as {
    (params: ListAuditLogsParams & { paginate: true }, options?: { signal?: AbortSignal }): Promise<PaginatedResponse<AuditLog>>;
    (params?: ListAuditLogsParams & { paginate?: false }, options?: { signal?: AbortSignal }): Promise<AuditLog[]>;
    (params?: ListAuditLogsParams, options?: { signal?: AbortSignal }): Promise<PaginatedResponse<AuditLog> | AuditLog[]>;
  }
};
