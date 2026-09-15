import React, { useState } from 'react';
import { Calendar, Laptop, CheckCircle, ChevronRight, AlertCircle, ArrowUpRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../Card';
import { EmptyState } from '../EmptyState';
import {
  type TeamDashboardData,
  type OrganizationPendingApprovals,
  type PersonalDashboardData,
} from '../../services/dashboard';

interface PendingApprovalsWidgetProps {
  teamApprovals?: TeamDashboardData['pending_approvals'];
  orgApprovals?: OrganizationPendingApprovals;
  personalPending?: PersonalDashboardData['my_pending_requests'];
}

export const PendingApprovalsWidget: React.FC<PendingApprovalsWidgetProps> = ({
  teamApprovals,
  orgApprovals,
  personalPending,
}) => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'leaves' | 'wfh'>('leaves');

  // Case 1: Manager has direct reports with pending approval queue
  if (teamApprovals && (teamApprovals.leaves_count > 0 || teamApprovals.wfh_count > 0)) {
    const totalCount = teamApprovals.leaves_count + teamApprovals.wfh_count;
    return (
      <Card
        title="Approval Command Center"
        actions={
          <span
            style={{
              fontSize: 'var(--font-size-xs)',
              color: '#b45309',
              backgroundColor: '#fef3c7',
              padding: '3px 10px',
              borderRadius: 'var(--radius-full)',
              fontWeight: 700,
              border: '1px solid #fde68a',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <AlertCircle size={12} /> {totalCount} Action Required
          </span>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* Tab Switcher */}
          <div
            style={{
              display: 'flex',
              padding: '3px',
              backgroundColor: 'var(--color-bg-page)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
              gap: '4px',
            }}
          >
            <button
              type="button"
              onClick={() => setActiveTab('leaves')}
              style={{
                flex: 1,
                padding: '7px 10px',
                borderRadius: 'var(--radius-xs)',
                border: 'none',
                backgroundColor: activeTab === 'leaves' ? 'var(--color-bg-card)' : 'transparent',
                boxShadow: activeTab === 'leaves' ? 'var(--shadow-xs)' : 'none',
                color: activeTab === 'leaves' ? 'var(--color-primary)' : 'var(--color-text-muted)',
                fontWeight: 600,
                fontSize: 'var(--font-size-xs)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                transition: 'all 0.15s ease',
              }}
            >
              <Calendar size={13} /> Leaves ({teamApprovals.leaves_count})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('wfh')}
              style={{
                flex: 1,
                padding: '7px 10px',
                borderRadius: 'var(--radius-xs)',
                border: 'none',
                backgroundColor: activeTab === 'wfh' ? 'var(--color-bg-card)' : 'transparent',
                boxShadow: activeTab === 'wfh' ? 'var(--shadow-xs)' : 'none',
                color: activeTab === 'wfh' ? 'var(--color-secondary-hover)' : 'var(--color-text-muted)',
                fontWeight: 600,
                fontSize: 'var(--font-size-xs)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                transition: 'all 0.15s ease',
              }}
            >
              <Laptop size={13} /> WFH ({teamApprovals.wfh_count})
            </button>
          </div>

          {/* List Content */}
          {activeTab === 'leaves' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {teamApprovals.leaves.length > 0 ? (
                teamApprovals.leaves.map((item) => (
                  <div
                    key={item.id}
                    style={{
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--color-bg-page)',
                      border: '1px solid var(--color-border)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 600, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-main)' }}>
                        {item.employee_name}
                      </span>
                      <span
                        style={{
                          fontSize: 'var(--font-size-xs)',
                          padding: '2px 8px',
                          borderRadius: 'var(--radius-full)',
                          backgroundColor: 'var(--color-primary-light)',
                          color: 'var(--color-primary)',
                          fontWeight: 600,
                        }}
                      >
                        {item.leave_type} · {item.duration_days}d
                      </span>
                    </div>
                    <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                      {item.start_date} to {item.end_date}
                      {item.reason && ` • "${item.reason}"`}
                    </div>
                  </div>
                ))
              ) : (
                <EmptyState title="Queue Clear" description="No pending team leave requests." icon={CheckCircle} />
              )}
            </div>
          )}

          {activeTab === 'wfh' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {teamApprovals.wfh.length > 0 ? (
                teamApprovals.wfh.map((item) => (
                  <div
                    key={item.id}
                    style={{
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--color-bg-page)',
                      border: '1px solid var(--color-border)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 600, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-main)' }}>
                        {item.employee_name}
                      </span>
                      <span
                        style={{
                          fontSize: 'var(--font-size-xs)',
                          padding: '2px 8px',
                          borderRadius: 'var(--radius-full)',
                          backgroundColor: 'var(--color-secondary-light)',
                          color: 'var(--color-secondary-hover)',
                          fontWeight: 600,
                        }}
                      >
                        Remote WFH
                      </span>
                    </div>
                    <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                      {new Date(item.start_at).toLocaleDateString()}
                      {item.reason && ` • "${item.reason}"`}
                    </div>
                  </div>
                ))
              ) : (
                <EmptyState title="Queue Clear" description="No pending team WFH requests." icon={CheckCircle} />
              )}
            </div>
          )}

          <button
            className="btn btn-secondary"
            onClick={() => navigate('/leaves')}
            style={{ width: '100%', fontSize: 'var(--font-size-xs)', paddingTop: 8, paddingBottom: 8 }}
            type="button"
          >
            Review Requests in Approvals Hub <ArrowUpRight size={13} />
          </button>
        </div>
      </Card>
    );
  }

  // Case 2: Org-wide pending approvals (HR / Admin)
  if (orgApprovals && (orgApprovals.leaves_count !== undefined || orgApprovals.wfh_count !== undefined)) {
    const leavesCount = orgApprovals.leaves_count || 0;
    const wfhCount = orgApprovals.wfh_count || 0;
    const totalOrg = leavesCount + wfhCount;

    return (
      <Card
        title="Organization Approvals"
        actions={
          <span
            style={{
              fontSize: 'var(--font-size-xs)',
              color: totalOrg > 0 ? '#b45309' : 'var(--color-status-success)',
              backgroundColor: totalOrg > 0 ? '#fef3c7' : 'var(--color-status-success-bg)',
              padding: '3px 10px',
              borderRadius: 'var(--radius-full)',
              fontWeight: 700,
              border: totalOrg > 0 ? '1px solid #fde68a' : '1px solid var(--color-status-success-border)',
            }}
          >
            {totalOrg} Pending Organization-wide
          </span>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div
              style={{
                padding: '14px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--color-bg-page)',
                border: '1px solid var(--color-border)',
                cursor: 'pointer',
                transition: 'border-color 0.15s ease',
              }}
              onClick={() => navigate('/admin/leaves')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <Calendar size={16} color="var(--color-primary)" />
                <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 600 }}>
                  Leave Requests
                </span>
              </div>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--color-text-main)' }}>
                {leavesCount}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                Pending Review
              </div>
            </div>

            <div
              style={{
                padding: '14px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--color-bg-page)',
                border: '1px solid var(--color-border)',
                cursor: 'pointer',
                transition: 'border-color 0.15s ease',
              }}
              onClick={() => navigate('/admin/leaves')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <Laptop size={16} color="#0284c7" />
                <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 600 }}>
                  WFH Requests
                </span>
              </div>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--color-text-main)' }}>
                {wfhCount}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                Pending Review
              </div>
            </div>
          </div>

          <button
            className="btn btn-ghost"
            onClick={() => navigate('/admin/leaves')}
            style={{ width: '100%', fontSize: 'var(--font-size-xs)' }}
            type="button"
          >
            Manage Company Leave Records <ChevronRight size={13} />
          </button>
        </div>
      </Card>
    );
  }

  // Case 3: Employee view - My pending requests
  return (
    <Card title="My Request Status">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <div
            style={{
              padding: '12px 14px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--color-bg-page)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 500 }}>
              Leaves Pending
            </div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--color-text-main)', marginTop: '2px' }}>
              {personalPending?.leaves || 0}
            </div>
          </div>

          <div
            style={{
              padding: '12px 14px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--color-bg-page)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 500 }}>
              WFH Pending
            </div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--color-text-main)', marginTop: '2px' }}>
              {personalPending?.wfh || 0}
            </div>
          </div>
        </div>

        <button
          className="btn btn-ghost"
          onClick={() => navigate('/leaves')}
          style={{ width: '100%', fontSize: 'var(--font-size-xs)' }}
          type="button"
        >
          View My Leave Submissions <ChevronRight size={13} />
        </button>
      </div>
    </Card>
  );
};
