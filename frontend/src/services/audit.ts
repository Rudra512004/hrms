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

export const auditService = {
  getLogs: async (): Promise<AuditLog[]> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch('/api/v1/audit-logs/', {
      headers: {
        'Authorization': `Token ${token}`,
        'Accept': 'application/json'
      }
    });

    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        throw new Error(`Authorization failed: ${response.status}`);
      }
      throw new Error('Failed to fetch audit logs');
    }

    return await response.json();
  }
};
