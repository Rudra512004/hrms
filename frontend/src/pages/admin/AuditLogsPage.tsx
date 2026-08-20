import React, { useState, useEffect } from 'react';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { ShieldAlert, Search, Loader2 } from 'lucide-react';
import { auditService, type AuditLog } from '../../services/audit';

const styles = {
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 'var(--spacing-lg)',
  },
  titleContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-sm)',
  },
  title: {
    margin: 0,
    fontSize: '1.25rem',
    color: 'var(--color-text-main)',
  },
  searchContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-sm)',
    position: 'relative' as const,
    width: '300px',
  },
  searchIcon: {
    position: 'absolute' as const,
    left: '10px',
    color: 'var(--color-text-muted)',
  },
  searchInput: {
    paddingLeft: '36px',
    width: '100%',
  },
  errorBox: {
    padding: 'var(--spacing-lg)',
    backgroundColor: 'var(--color-status-rejected)15',
    color: 'var(--color-status-rejected)',
    borderRadius: 'var(--radius-md)',
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-md)',
    border: '1px solid var(--color-status-rejected)30',
  },
  emptyState: {
    padding: 'var(--spacing-xl)',
    textAlign: 'center' as const,
    color: 'var(--color-text-muted)',
    backgroundColor: 'var(--color-bg-secondary)',
    borderRadius: 'var(--radius-md)',
  }
};

export const AuditLogsPage: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadLogs();
  }, []);

  const loadLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await auditService.getLogs();
      setLogs(data);
    } catch (err: any) {
      if (err.message && err.message.includes('403')) {
        setError('403 / Access Denied. You do not have permission to view audit logs.');
      } else if (err.message && err.message.includes('401')) {
        setError('401 / Unauthorized. Please log in again.');
      } else {
        setError('A server error occurred while fetching audit logs.');
      }
    } finally {
      setLoading(false);
    }
  };

  const filteredLogs = logs.filter(log => {
    const term = searchTerm.toLowerCase();
    return (
      (log.actor_email && log.actor_email.toLowerCase().includes(term)) ||
      (log.action && log.action.toLowerCase().includes(term)) ||
      (log.target_resource && log.target_resource.toLowerCase().includes(term))
    );
  });

  const columns = [
    { key: 'timestamp', title: 'Timestamp', render: (log: AuditLog) => new Date(log.timestamp).toLocaleString() },
    { key: 'actor_email', title: 'Actor Email', render: (log: AuditLog) => log.actor_email || 'System' },
    { key: 'action', title: 'Action' },
    { key: 'target_resource', title: 'Target' },
    { key: 'status', title: 'Status', render: (log: AuditLog) => <StatusBadge status={log.status === 'success' || log.status === '200' || log.status === '201' ? 'active' : 'rejected'} label={log.status || 'unknown'} /> }
  ];

  return (
    <div>
      <div style={styles.header}>
        <div style={styles.titleContainer}>
          <ShieldAlert size={24} color="var(--color-primary)" />
          <h1 style={styles.title}>System Audit Logs</h1>
        </div>
        
        <div style={styles.searchContainer}>
          <Search size={18} style={styles.searchIcon} />
          <input 
            type="text" 
            placeholder="Search logs..." 
            className="input-neumorphic"
            style={styles.searchInput}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {error ? (
        <Card>
          <div style={styles.errorBox}>
            <ShieldAlert size={24} />
            <div>
              <h3 style={{ margin: '0 0 var(--spacing-sm) 0' }}>Error Loading Logs</h3>
              <p style={{ margin: 0 }}>{error}</p>
            </div>
          </div>
        </Card>
      ) : loading ? (
        <Card>
          <div style={{ padding: 'var(--spacing-xl)', display: 'flex', justifyContent: 'center' }}>
            <Loader2 size={32} style={{ animation: 'spin 1s linear infinite', color: 'var(--color-primary)' }} />
          </div>
        </Card>
      ) : filteredLogs.length === 0 ? (
        <Card>
          <div style={styles.emptyState}>
            {searchTerm ? "No audit activity found matching your search." : "No audit activity found."}
          </div>
        </Card>
      ) : (
        <Card>
          <Table data={filteredLogs} columns={columns} keyExtractor={(log) => log.id.toString()} />
        </Card>
      )}
    </div>
  );
};
