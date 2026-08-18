import React, { useState, useEffect } from 'react';
import { Card } from '../components/Card';
import { StatusBadge } from '../components/StatusBadge';
import { User as UserIcon, Mail, Hash, ChevronRight, AlertCircle, Loader2 } from 'lucide-react';
import { authService, type User as AuthUser } from '../services/auth';
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
  infoCard: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 'var(--spacing-md)',
  },
  iconBox: {
    width: '48px',
    height: '48px',
    borderRadius: 'var(--radius-md)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  infoContent: {
    flex: 1,
  },
  infoLabel: {
    fontSize: '0.85rem',
    color: 'var(--color-text-muted)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
    margin: '0 0 4px 0',
    fontWeight: 600,
  },
  infoValue: {
    fontSize: '1.1rem',
    fontWeight: 600,
    color: 'var(--color-text-main)',
    margin: 0,
    wordBreak: 'break-word' as const,
  },
  profileBanner: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 'var(--spacing-lg)',
    backgroundColor: 'var(--color-primary)',
    borderRadius: 'var(--radius-lg)',
    color: '#fff',
    cursor: 'pointer',
    transition: 'transform 0.2s',
  },
  profileBannerText: {
    margin: 0,
    fontSize: '1.1rem',
    fontWeight: 600,
  },
  profileBannerSubtext: {
    margin: '4px 0 0 0',
    fontSize: '0.9rem',
    opacity: 0.9,
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

const InfoCard = ({ label, value, icon, color, isStatus = false }: { label: string, value: string, icon: React.ReactNode, color: string, isStatus?: boolean }) => (
  <Card>
    <div style={styles.infoCard}>
      <div style={{ ...styles.iconBox, backgroundColor: `${color}15`, color }}>
        {icon}
      </div>
      <div style={styles.infoContent}>
        <p style={styles.infoLabel}>{label}</p>
        {isStatus ? (
          <div style={{ marginTop: '4px' }}>
            <StatusBadge status={value as any} />
          </div>
        ) : (
          <h3 style={styles.infoValue}>{value}</h3>
        )}
      </div>
    </div>
  </Card>
);

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    authService.getCurrentUser()
      .then(u => {
        if (!u) throw new Error("Could not load user data. Please log in again.");
        setUser(u);
      })
      .catch(err => {
        setError(err.message || "An unexpected error occurred while fetching your data.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div style={styles.centerState}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite', marginBottom: 'var(--spacing-md)' }} />
        <p>Loading your dashboard...</p>
      </div>
    );
  }

  if (error || !user) {
    return (
      <div style={styles.centerState}>
        <AlertCircle size={48} color="var(--color-status-danger)" style={{ marginBottom: 'var(--spacing-md)' }} />
        <h3 style={{ color: 'var(--color-text-main)', marginBottom: 'var(--spacing-xs)' }}>Unable to load dashboard</h3>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.welcomeSection}>
        <h1 style={styles.welcomeTitle}>Welcome back, {user.firstName}!</h1>
        <p style={styles.welcomeSubtitle}>Here is an overview of your account information.</p>
      </div>

      <div style={styles.grid}>
        <InfoCard 
          label="Account Status" 
          value={user.status || 'unknown'} 
          icon={<UserIcon size={24} />} 
          color="var(--color-primary)"
          isStatus={true}
        />
        <InfoCard 
          label="Employee Code" 
          value={user.hrmsId || 'Not Assigned'} 
          icon={<Hash size={24} />} 
          color="var(--color-status-info)" 
        />
        <InfoCard 
          label="Company Email" 
          value={user.email} 
          icon={<Mail size={24} />} 
          color="var(--color-status-warning)" 
        />
      </div>

      <div 
        style={styles.profileBanner} 
        onClick={() => navigate('/profile')}
        onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateY(-2px)')}
        onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
      >
        <div>
          <h3 style={styles.profileBannerText}>Complete your profile</h3>
          <p style={styles.profileBannerSubtext}>Make sure your personal and contact information is up to date.</p>
        </div>
        <ChevronRight size={28} />
      </div>
    </div>
  );
};
