import React from 'react';
import { Card } from '../components/Card';
import { StatusBadge, type StatusType } from '../components/StatusBadge';
import { Table } from '../components/Table';
import { Users, UserCheck, CalendarOff, AlertCircle } from 'lucide-react';

const styles = {
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
    gap: 'var(--spacing-lg)',
    marginBottom: 'var(--spacing-lg)',
  },
  statCard: {
    display: 'flex',
    alignItems: 'center',
  },
  statIcon: {
    width: '60px',
    height: '60px',
    borderRadius: 'var(--radius-sm)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 'var(--spacing-md)',
  },
  statContent: {
    flex: 1,
  },
  statTitle: {
    fontSize: '0.9rem',
    color: 'var(--color-text-muted)',
    margin: 0,
    fontWeight: 500,
  },
  statValue: {
    fontSize: '1.5rem',
    fontWeight: 700,
    color: 'var(--color-text-main)',
    margin: '4px 0 0 0',
  },
  sectionTitle: {
    fontSize: '1.2rem',
    fontWeight: 600,
    marginBottom: 'var(--spacing-md)',
    marginTop: 'var(--spacing-xl)',
  }
};

const StatCard = ({ title, value, icon, color }: { title: string, value: string | number, icon: React.ReactNode, color: string }) => (
  <Card>
    <div style={styles.statCard}>
      <div style={{ ...styles.statIcon, backgroundColor: `${color}15`, color }}>
        {icon}
      </div>
      <div style={styles.statContent}>
        <p style={styles.statTitle}>{title}</p>
        <h3 style={styles.statValue}>{value}</h3>
      </div>
    </div>
  </Card>
);

// Demo Data
const recentActivity = [
  { id: '1', name: 'John Doe', action: 'Requested Leave', date: 'Today, 09:30 AM', status: 'pending' as StatusType },
  { id: '2', name: 'Jane Smith', action: 'Joined Company', date: 'Yesterday', status: 'active' as StatusType },
  { id: '3', name: 'Mike Johnson', action: 'Approved Leave', date: '12 Aug 2026', status: 'approved' as StatusType },
  { id: '4', name: 'Emily Davis', action: 'Absent', date: '11 Aug 2026', status: 'absent' as StatusType },
];

export const DashboardPage: React.FC = () => {
  const tableColumns = [
    { key: 'name', title: 'Employee Name' },
    { key: 'action', title: 'Action' },
    { key: 'date', title: 'Date' },
    { 
      key: 'status', 
      title: 'Status',
      render: (item: any) => <StatusBadge status={item.status} />
    },
  ];

  return (
    <div>
      <div style={styles.grid}>
        <StatCard 
          title="Total Employees" 
          value="124" 
          icon={<Users size={28} />} 
          color="var(--color-primary)" 
        />
        <StatCard 
          title="Present Today" 
          value="112" 
          icon={<UserCheck size={28} />} 
          color="var(--color-status-success)" 
        />
        <StatCard 
          title="On Leave" 
          value="8" 
          icon={<CalendarOff size={28} />} 
          color="var(--color-status-warning)" 
        />
        <StatCard 
          title="Pending Requests" 
          value="6" 
          icon={<AlertCircle size={28} />} 
          color="var(--color-status-danger)" 
        />
      </div>

      <h3 style={styles.sectionTitle}>Recent Activity</h3>
      <Card>
        <Table 
          data={recentActivity} 
          columns={tableColumns} 
          keyExtractor={(item) => item.id} 
        />
      </Card>
    </div>
  );
};
