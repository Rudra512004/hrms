export interface AuditLog {
  id: number;
  actor_email: string;
  action: string;
  target_resource: string;
  status: string;
  ip_address: string;
  timestamp: string;
  details: any;
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
