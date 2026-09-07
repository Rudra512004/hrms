import React from 'react';
import { Card } from '../../components/Card';
import { Network, FileText, Loader2, Settings, Users, Building2, GitBranch, Briefcase, Calendar, ShieldAlert } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 'var(--spacing-xl)',
  },
  welcomeSection: {
    marginBottom: 'var(--spacing-md)',
  },
  welcomeTitle: {
    fontSize: '1.5rem',
    fontWeight: 700,
    color: 'var(--color-text-main)',
    margin: '0 0 var(--spacing-xs) 0',
  },
  welcomeSubtitle: {
    color: 'var(--color-text-muted)',
    margin: 0,
    fontSize: '0.95rem',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
    gap: 'var(--spacing-lg)',
  },
  navCard: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-md)',
    cursor: 'pointer',
    padding: 'var(--spacing-lg)',
    transition: 'transform 0.2s',
  },
  iconBox: {
    width: '56px',
    height: '56px',
    borderRadius: 'var(--radius-md)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  infoContent: {
    flex: 1,
  },
  infoTitle: {
    fontSize: '1.1rem',
    fontWeight: 600,
    color: 'var(--color-text-main)',
    margin: '0 0 4px 0',
  },
  infoDesc: {
    fontSize: '0.9rem',
    color: 'var(--color-text-muted)',
    margin: 0,
  },
  centerState: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '400px',
    color: 'var(--color-text-muted)',
  }
};

const NavCard = ({ title, desc, icon, color, onClick }: { title: string, desc: string, icon: React.ReactNode, color: string, onClick: () => void }) => (
  <div onClick={onClick} style={{ textDecoration: 'none' }}>
    <Card>
      <div 
        style={styles.navCard}
        onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateY(-2px)')}
        onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
      >
        <div style={{ ...styles.iconBox, backgroundColor: `${color}15`, color }}>
          {icon}
        </div>
        <div style={styles.infoContent}>
          <h3 style={styles.infoTitle}>{title}</h3>
          <p style={styles.infoDesc}>{desc}</p>
        </div>
      </div>
    </Card>
  </div>
);

export const AdminDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  // ProtectedRoute ensures this page is only accessible if user is loaded
  // No additional fetching needed.

  if (!user) {
    return (
      <div style={styles.centerState}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite', marginBottom: 'var(--spacing-md)' }} />
        <p>Loading control plane...</p>
      </div>
    );
  }

  // No error handling needed here as ProtectedRoute handles it



  return (
    <div style={styles.container}>
      <div style={styles.welcomeSection}>
        <h1 style={styles.welcomeTitle}>Superadmin Control Plane</h1>
        <p style={styles.welcomeSubtitle}>Manage organization configurations and review employee requests.</p>
      </div>

      <div style={styles.grid}>
        <NavCard 
          title="Employees" 
          desc="Manage employee profiles, statuses, and sensitive info"
          icon={<Users size={28} />} 
          color="var(--color-primary)" 
          onClick={() => navigate('/admin/employees')}
        />
        <NavCard 
          title="Organizations" 
          desc="Manage company structure and details"
          icon={<Building2 size={28} />} 
          color="var(--color-status-success)" 
          onClick={() => navigate('/admin/organizations')}
        />
        <NavCard 
          title="Departments" 
          desc="Manage departments and organizational units"
          icon={<GitBranch size={28} />} 
          color="var(--color-status-warning)" 
          onClick={() => navigate('/admin/departments')}
        />
        <NavCard 
          title="Designations" 
          desc="Manage job titles and roles"
          icon={<Briefcase size={28} />} 
          color="var(--color-status-info)" 
          onClick={() => navigate('/admin/designations')}
        />
        <NavCard 
          title="Office Networks" 
          desc="Manage trusted IP ranges for network access policies"
          icon={<Network size={28} />} 
          color="var(--color-primary)"
          onClick={() => navigate('/admin/office-networks')}
        />
        <NavCard 
          title="WFH Requests" 
          desc="Review and process employee work-from-home requests"
          icon={<FileText size={28} />} 
          color="var(--color-status-info)" 
          onClick={() => navigate('/admin/wfh')}
        />
        <NavCard 
          title="Leave Types" 
          desc="Manage time off policies and leave types"
          icon={<Calendar size={28} />} 
          color="var(--color-status-warning)" 
          onClick={() => navigate('/admin/leave-types')}
        />
        <NavCard 
          title="Audit Logs" 
          desc="Review system activity and security logs"
          icon={<ShieldAlert size={28} />} 
          color="var(--color-status-error)" 
          onClick={() => navigate('/admin/audit-logs')}
        />
        <NavCard 
          title="System Settings" 
          desc="Configure core HRMS parameters and behaviors"
          icon={<Settings size={28} />} 
          color="var(--color-text-muted)" 
          onClick={() => {}} // Placeholder for future
        />
      </div>
    </div>
  );
};
