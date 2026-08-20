import React, { useState } from 'react';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { ShieldAlert, Search } from 'lucide-react';

const mockLogs = [
  { id: 1, timestamp: '2026-08-20T09:00:00Z', user: 'admin@company.com', action: 'CREATE_EMPLOYEE', target: 'John Doe', status: 'success' },
  { id: 2, timestamp: '2026-08-20T09:15:00Z', user: 'admin@company.com', action: 'ASSIGN_ROLE', target: 'John Doe (HR Admin)', status: 'success' },
  { id: 3, timestamp: '2026-08-20T09:30:00Z', user: 'admin@company.com', action: 'REVOKE_PERMISSION', target: 'Jane Smith (payroll.view)', status: 'success' },
  { id: 4, timestamp: '2026-08-20T10:00:00Z', user: 'system', action: 'SYNC_LDAP', target: 'Global Directory', status: 'failed' },
];

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
  alert: {
    padding: 'var(--spacing-md)',
    borderRadius: 'var(--radius-md)',
    backgroundColor: 'var(--color-status-info)15',
    color: 'var(--color-status-info)',
    border: '1px solid var(--color-status-info)30',
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-sm)',
    marginBottom: 'var(--spacing-lg)',
  }
};

export const AuditLogsPage: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredLogs = mockLogs.filter(log => 
    log.user.toLowerCase().includes(searchTerm.toLowerCase()) || 
    log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
    log.target.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const columns = [
    { key: 'timestamp', title: 'Timestamp', render: (log: any) => new Date(log.timestamp).toLocaleString() },
    { key: 'user', title: 'User / Actor' },
    { key: 'action', title: 'Action' },
    { key: 'target', title: 'Target' },
    { key: 'status', title: 'Status', render: (log: any) => <StatusBadge status={log.status === 'success' ? 'active' : 'rejected'} label={log.status} /> }
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

      <div style={styles.alert}>
        <ShieldAlert size={20} />
        <span>Audit Logs are currently simulated. Integration with the backend logging service is pending.</span>
      </div>

      <Card>
        <Table data={filteredLogs} columns={columns} keyExtractor={(log) => log.id.toString()} />
      </Card>
    </div>
  );
};
