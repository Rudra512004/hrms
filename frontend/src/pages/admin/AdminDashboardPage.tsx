import React, { useState, useEffect } from 'react';
import { Card } from '../../components/Card';
import { Network, FileText, AlertCircle, Loader2, Settings } from 'lucide-react';
import { authService, type User as AuthUser } from '../../services/auth';
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
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    authService.getCurrentUser()
      .then(u => {
        if (!u) throw new Error("Could not load user data.");
        if (!u.isStaff) throw new Error("You do not have permission to view the admin control plane.");
        setUser(u);
      })
      .catch(err => {
        setError(err.message || "An unexpected error occurred.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div style={styles.centerState}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite', marginBottom: 'var(--spacing-md)' }} />
        <p>Loading control plane...</p>
      </div>
    );
  }

  if (error || !user) {
    return (
      <div style={styles.centerState}>
        <AlertCircle size={48} color="var(--color-status-danger)" style={{ marginBottom: 'var(--spacing-md)' }} />
        <h3 style={{ color: 'var(--color-text-main)', marginBottom: 'var(--spacing-xs)' }}>Access Denied</h3>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.welcomeSection}>
        <h1 style={styles.welcomeTitle}>Superadmin Control Plane</h1>
        <p style={styles.welcomeSubtitle}>Manage organization configurations and review employee requests.</p>
      </div>

      <div style={styles.grid}>
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
