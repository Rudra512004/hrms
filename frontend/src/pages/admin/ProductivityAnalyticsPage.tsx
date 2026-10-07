import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useBranchContext } from '../../contexts/BranchContext';
import { PageHeader } from '../../components/PageHeader';
import { Card } from '../../components/Card';
import { Table } from '../../components/Table';
import { AlertBanner } from '../../components/AlertBanner';
import { Loader2, MousePointerClick, Keyboard, Clock, Activity } from 'lucide-react';
import {
  productivityService,
  type ProductivityOverview,
  type ProductivityTrend,
  type TeamBreakdown,
  type EmployeeBreakdown
} from '../../services/productivity';
import { organizationService, type Team } from '../../services/organization';



export const ProductivityAnalyticsPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const { branchId } = useBranchContext();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Date range (default to last 7 days)
  const today = new Date();
  const lastWeek = new Date(today);
  lastWeek.setDate(today.getDate() - 6);

  const [startDate, setStartDate] = useState(lastWeek.toISOString().split('T')[0]);
  const [endDate, setEndDate] = useState(today.toISOString().split('T')[0]);

  // Filters
  const [teamId, setTeamId] = useState<string>('all');
  const [teams, setTeams] = useState<Team[]>([]);

  // Data
  const [overview, setOverview] = useState<ProductivityOverview | null>(null);
  const [trends, setTrends] = useState<ProductivityTrend[]>([]);
  const [teamBreakdown, setTeamBreakdown] = useState<TeamBreakdown[]>([]);
  const [employeeBreakdown, setEmployeeBreakdown] = useState<EmployeeBreakdown[]>([]);

  // Fetch filters
  useEffect(() => {
    let active = true;
    const fetchFilters = async () => {
      try {
        const tms = await organizationService.listTeams();
        if (active) setTeams(tms);
      } catch (err) {
        console.error('Error fetching teams', err);
      }
    };
    fetchFilters();
    return () => { active = false; };
  }, [branchId]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = { start_date: startDate, end_date: endDate };
      if (branchId) params.branch_id = branchId;
      if (teamId !== 'all') params.team_id = teamId;

      const [ov, tr, tb, eb] = await Promise.all([
        productivityService.getOverview(params),
        productivityService.getTrends(params),
        productivityService.getTeamBreakdown(params),
        productivityService.getEmployeeBreakdown(params),
      ]);

      setOverview(ov);
      setTrends(tr);
      setTeamBreakdown(tb);
      setEmployeeBreakdown(eb);
    } catch (err: any) {
      setError(err?.errorData?.detail || err?.message || 'Failed to load analytics.');
    } finally {
      setLoading(false);
    }
  }, [branchId, teamId, startDate, endDate]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (!hasPermission('attendance.view_all')) {
    return (
      <div style={{ padding: '20px' }}>
        <AlertBanner type="error" message="You do not have permission to view productivity analytics." />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <PageHeader 
        title="Workforce Intelligence & Productivity" 
        subtitle="Analyze team and employee performance, active durations, and system engagement."
      />

      {/* Filters */}
      <Card>
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: 'var(--font-size-xs)', fontWeight: 500, color: 'var(--color-text-muted)' }}>Start Date</label>
            <input 
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              style={{ padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--color-bg-page)' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: 'var(--font-size-xs)', fontWeight: 500, color: 'var(--color-text-muted)' }}>End Date</label>
            <input 
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              style={{ padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--color-bg-page)' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: 'var(--font-size-xs)', fontWeight: 500, color: 'var(--color-text-muted)' }}>Team</label>
            <select
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              style={{ padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--color-bg-page)' }}
            >
              <option value="all">All Teams</option>
              {teams.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      {error && <AlertBanner type="error" message={error} />}

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
          <Loader2 size={32} className="spin" style={{ color: 'var(--color-primary)' }} />
        </div>
      ) : (
        <>
          {/* Overview Metrics */}
          {overview && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
              <MetricCard title="Total Active" value={overview.total_active_duration} icon={<Activity size={20} />} />
              <MetricCard title="Total Idle" value={overview.total_idle_duration} icon={<Clock size={20} />} />
              <MetricCard title="Avg Active %" value={`${overview.average_active_percent?.toFixed(1) || 0}%`} icon={<Activity size={20} />} />
              <MetricCard title="Total Clicks" value={overview.total_mouse_clicks?.toLocaleString() || '0'} icon={<MousePointerClick size={20} />} />
              <MetricCard title="Total Keystrokes" value={overview.total_key_presses?.toLocaleString() || '0'} icon={<Keyboard size={20} />} />
            </div>
          )}

          {/* Simple Trends Chart */}
          <Card title="Productivity Trends (Active %)">
            {trends.length === 0 ? (
              <p style={{ color: 'var(--color-text-muted)' }}>No trend data available.</p>
            ) : (
              <div style={{ display: 'flex', alignItems: 'flex-end', height: '200px', gap: '8px', padding: '16px 0', borderBottom: '1px solid var(--color-border)' }}>
                {trends.map(t => (
                  <div key={t.date} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', height: '100%' }}>
                    <div style={{ flex: 1, width: '100%', display: 'flex', alignItems: 'flex-end', justifyContent: 'center' }}>
                      <div 
                        style={{ 
                          width: '40px', 
                          height: `${t.average_active_percent}%`, 
                          backgroundColor: 'var(--color-primary)',
                          borderRadius: '4px 4px 0 0',
                          opacity: 0.8,
                          transition: 'height 0.3s ease'
                        }}
                        title={`${t.date}: ${t.average_active_percent}%`}
                      />
                    </div>
                    <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                      {new Date(t.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Breakdowns */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '20px' }}>
            <Card title="Team Breakdown">
              <Table 
                columns={[
                  { key: 'team_name', title: 'Team' },
                  { key: 'attendance_count', title: 'Records' },
                  { key: 'total_active_duration', title: 'Active Time' },
                  { key: 'total_idle_duration', title: 'Idle Time' },
                  { key: 'average_active_percent', title: 'Avg Active %', render: (val) => `${Number(val).toFixed(1)}%` },
                ]}
                data={teamBreakdown}
                keyExtractor={(item) => item.team_id.toString()}
              />
            </Card>

            <Card title="Employee Breakdown">
              <Table 
                columns={[
                  { key: 'employee_name', title: 'Employee' },
                  { key: 'attendance_count', title: 'Records' },
                  { key: 'total_active_duration', title: 'Active Time' },
                  { key: 'total_idle_duration', title: 'Idle Time' },
                  { key: 'average_active_percent', title: 'Avg Active %', render: (val) => `${Number(val).toFixed(1)}%` },
                ]}
                data={employeeBreakdown}
                keyExtractor={(item) => item.employee_id.toString()}
              />
            </Card>
          </div>
        </>
      )}
    </div>
  );
};

const MetricCard = ({ title, value, icon }: { title: string, value: string | number, icon: React.ReactNode }) => (
  <div style={{ 
    backgroundColor: 'var(--color-bg-card)', 
    border: '1px solid var(--color-border)', 
    borderRadius: 'var(--radius-lg)', 
    padding: '20px',
    display: 'flex',
    alignItems: 'center',
    gap: '16px'
  }}>
    <div style={{ 
      backgroundColor: 'var(--color-bg-page)', 
      color: 'var(--color-primary)',
      padding: '12px',
      borderRadius: 'var(--radius-md)'
    }}>
      {icon}
    </div>
    <div>
      <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)', marginBottom: '4px' }}>{title}</div>
      <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 600, color: 'var(--color-text)' }}>{value}</div>
    </div>
  </div>
);
