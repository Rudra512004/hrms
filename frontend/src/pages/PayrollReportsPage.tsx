import React, { useState, useEffect, useCallback } from 'react';
import {
  DollarSign,
  Users,
  Calendar,
  AlertTriangle,
  TrendingDown,
  Layers,
  Search,
  Building2,
  GitBranch,
  RefreshCw,
  FileSpreadsheet,
} from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { Card } from '../components/Card';
import { StatCard } from '../components/StatCard';
import { Table } from '../components/Table';
import { StatusBadge } from '../components/StatusBadge';
import { AlertBanner } from '../components/AlertBanner';
import { EmptyState } from '../components/EmptyState';
import { useAuth } from '../contexts/AuthContext';
import {
  payrollService,
  type PayrollPeriod,
  MONTH_NAMES,
  formatCurrency,
  extractApiError,
} from '../services/payroll';
import {
  getPeriodSummary,
  getReconciliationRecords,
  getOrganizationBreakdown,
  getPayrollExceptions,
  type PeriodSummaryResponse,
  type ReconciliationRecord,
  type OrganizationBreakdownResponse,
  type PayrollExceptionItem,
} from '../services/payrollReporting';
import { branchService, type Branch } from '../services/branch';
import { organizationService, type Department } from '../services/organization';

export const PayrollReportsPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const hasSensitive = hasPermission('payroll.view_sensitive');

  // Periods state
  const [periods, setPeriods] = useState<PayrollPeriod[]>([]);
  const [selectedPeriodId, setSelectedPeriodId] = useState<number | null>(null);

  // Active Tab
  const [activeTab, setActiveTab] = useState<'reconciliation' | 'breakdown' | 'exceptions'>('reconciliation');

  // Filter options
  const [branches, setBranches] = useState<Branch[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [selectedDepartment, setSelectedDepartment] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Report Data
  const [summaryData, setSummaryData] = useState<PeriodSummaryResponse | null>(null);
  const [reconciliationRecords, setReconciliationRecords] = useState<ReconciliationRecord[]>([]);
  const [breakdownData, setBreakdownData] = useState<OrganizationBreakdownResponse | null>(null);
  const [exceptions, setExceptions] = useState<PayrollExceptionItem[]>([]);

  // Loading & Error states
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [loadingRecords, setLoadingRecords] = useState(false);
  const [loadingBreakdown, setLoadingBreakdown] = useState(false);
  const [loadingExceptions, setLoadingExceptions] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load initial periods, branches, and departments
  useEffect(() => {
    const loadInitialMeta = async () => {
      try {
        const [periodList, branchList, deptList] = await Promise.all([
          payrollService.getPeriods(),
          branchService.getAll().catch(() => []),
          organizationService.listDepartments().catch(() => []),
        ]);

        setPeriods(periodList);
        setBranches(branchList);
        setDepartments(deptList);

        if (periodList.length > 0) {
          // Select newest period by default
          setSelectedPeriodId(periodList[0].id);
        }
      } catch (err) {
        setError(extractApiError(err));
      }
    };

    loadInitialMeta();
  }, []);

  // Fetch Summary when selected period changes
  const fetchSummary = useCallback(async (periodId: number) => {
    setLoadingSummary(true);
    setError(null);
    try {
      const data = await getPeriodSummary(periodId);
      setSummaryData(data);
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLoadingSummary(false);
    }
  }, []);

  // Fetch Reconciliation when period or filters change
  const fetchReconciliation = useCallback(async (periodId: number) => {
    setLoadingRecords(true);
    try {
      const records = await getReconciliationRecords({
        period: periodId,
        branch: selectedBranch || undefined,
        department: selectedDepartment || undefined,
        search: searchTerm || undefined,
      });
      setReconciliationRecords(records);
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLoadingRecords(false);
    }
  }, [selectedBranch, selectedDepartment, searchTerm]);

  // Fetch Breakdown when tab is active
  const fetchBreakdown = useCallback(async (periodId: number) => {
    setLoadingBreakdown(true);
    try {
      const data = await getOrganizationBreakdown(periodId);
      setBreakdownData(data);
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLoadingBreakdown(false);
    }
  }, []);

  // Fetch Exceptions when tab is active
  const fetchExceptions = useCallback(async (periodId: number) => {
    setLoadingExceptions(true);
    try {
      const items = await getPayrollExceptions(periodId);
      setExceptions(items);
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLoadingExceptions(false);
    }
  }, []);

  // Effect to load summary on period change
  useEffect(() => {
    if (selectedPeriodId) {
      fetchSummary(selectedPeriodId);
      if (activeTab === 'reconciliation') {
        fetchReconciliation(selectedPeriodId);
      } else if (activeTab === 'breakdown') {
        fetchBreakdown(selectedPeriodId);
      } else if (activeTab === 'exceptions') {
        fetchExceptions(selectedPeriodId);
      }
    }
  }, [selectedPeriodId, activeTab, fetchSummary, fetchReconciliation, fetchBreakdown, fetchExceptions]);

  const handleRefreshAll = () => {
    if (!selectedPeriodId) return;
    fetchSummary(selectedPeriodId);
    if (activeTab === 'reconciliation') fetchReconciliation(selectedPeriodId);
    if (activeTab === 'breakdown') fetchBreakdown(selectedPeriodId);
    if (activeTab === 'exceptions') fetchExceptions(selectedPeriodId);
  };

  const selectedPeriod = periods.find((p) => p.id === selectedPeriodId);

  // Reconciliation Table Columns
  const reconciliationColumns = [
    {
      key: 'employee',
      title: 'Employee',
      render: (r: ReconciliationRecord) => (
        <div>
          <div style={{ fontWeight: 600 }}>{r.employee_name}</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
            {r.employee_code}
          </div>
        </div>
      ),
    },
    { key: 'department_name', title: 'Department' },
    { key: 'branch_name', title: 'Branch' },
    { key: 'working_days', title: 'Working' },
    { key: 'present_days', title: 'Present' },
    { key: 'half_days', title: 'Half' },
    { key: 'leave_days', title: 'Leave' },
    { key: 'absent_days', title: 'Absent' },
    {
      key: 'effective_days',
      title: 'Effective',
      render: (r: ReconciliationRecord) => (
        <span style={{ fontWeight: 600, color: 'var(--color-primary)' }}>
          {r.effective_days}
        </span>
      ),
    },
    {
      key: 'basic_salary',
      title: 'Basic Salary',
      render: (r: ReconciliationRecord) => (
        <span>{r.basic_salary !== null ? formatCurrency(r.basic_salary) : '—'}</span>
      ),
    },
    {
      key: 'gross_salary',
      title: 'Gross Salary',
      render: (r: ReconciliationRecord) => (
        <span>{r.gross_salary !== null ? formatCurrency(r.gross_salary) : '—'}</span>
      ),
    },
    {
      key: 'net_salary',
      title: 'Net Salary',
      render: (r: ReconciliationRecord) => (
        <span style={{ fontWeight: 600 }}>
          {r.net_salary !== null ? formatCurrency(r.net_salary) : '—'}
        </span>
      ),
    },
    {
      key: 'loss_of_pay_amount',
      title: 'LOP Amount',
      render: (r: ReconciliationRecord) => (
        <span style={{ color: Number(r.loss_of_pay_amount || 0) > 0 ? 'var(--color-status-danger)' : undefined }}>
          {r.loss_of_pay_amount !== null ? formatCurrency(r.loss_of_pay_amount) : '—'}
        </span>
      ),
    },
    {
      key: 'status',
      title: 'Status',
      render: (r: ReconciliationRecord) => (
        <StatusBadge
          status={r.status === 'approved' ? 'approved' : 'pending'}
          label={r.status === 'approved' ? 'Approved' : 'Draft'}
        />
      ),
    },
  ];

  // Helper for exception severity badge
  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'high':
        return <StatusBadge status="rejected" label="High" />;
      case 'medium':
        return <StatusBadge status="warning" label="Medium" />;
      case 'low':
      default:
        return <StatusBadge status="info" label="Low" />;
    }
  };

  const getExceptionTypeLabel = (type: string) => {
    switch (type) {
      case 'MISSING_COMPENSATION':
        return 'Missing Compensation';
      case 'MISSING_RECORD':
        return 'Missing Payroll Record';
      case 'FULL_ABSENCE':
        return 'Full Absence (0 Effective Days)';
      case 'PENDING_LEAVE':
        return 'Overlapping Pending Leave';
      case 'ATTENDANCE_INCOMPLETE':
        return 'Incomplete Attendance Event';
      default:
        return type;
    }
  };

  const maxBranchCount = Math.max(...(breakdownData?.by_branch.map((b) => b.headcount) || [1]), 1);
  const maxDeptCount = Math.max(...(breakdownData?.by_department.map((d) => d.headcount) || [1]), 1);

  return (
    <div className="page-container" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header with Period Selector */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <PageHeader
          title="Payroll Reconciliation & Reports"
          subtitle="Audit payroll records, detect attendance and leave discrepancies, and review organizational financial breakdowns."
        />

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <label style={{ fontSize: '0.9rem', fontWeight: 500, color: 'var(--color-text-secondary)' }}>
            Payroll Period:
          </label>
          <select
            className="input-select"
            value={selectedPeriodId ?? ''}
            onChange={(e) => setSelectedPeriodId(Number(e.target.value))}
            style={{ minWidth: '220px', padding: '8px 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}
          >
            {periods.map((p) => (
              <option key={p.id} value={p.id}>
                {MONTH_NAMES[p.month]} {p.year} ({p.status.toUpperCase()})
              </option>
            ))}
          </select>
          <button
            onClick={handleRefreshAll}
            className="btn btn-secondary"
            title="Refresh Report Data"
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <RefreshCw size={16} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Sensitive Data Notice */}
      {!hasSensitive && (
        <AlertBanner
          type="info"
          message="Salary data is protected. Salary and loss-of-pay monetary amounts are masked because your account does not have the 'payroll.view_sensitive' permission."
        />
      )}

      {error && <AlertBanner type="error" message={error} />}

      {loadingSummary && !summaryData && (
        <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--color-text-muted)' }}>
          Loading period metrics...
        </div>
      )}

      {/* KPI Cards Row */}
      {summaryData && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
          <StatCard
            title="Total Net Payout"
            value={summaryData.summary.total_net_salary !== null ? formatCurrency(summaryData.summary.total_net_salary) : 'Confidential'}
            icon={DollarSign}
            color="var(--color-primary)"
          />
          <StatCard
            title="Reconciled Headcount"
            value={summaryData.summary.total_employees}
            icon={Users}
            color="var(--color-status-info)"
          />
          <StatCard
            title="Loss of Pay"
            value={
              summaryData.summary.total_loss_of_pay !== null
                ? formatCurrency(summaryData.summary.total_loss_of_pay)
                : `${summaryData.summary.total_absent_days} Absent Days`
            }
            icon={TrendingDown}
            color="var(--color-status-danger)"
          />
          <StatCard
            title="Total Paid Effective Days"
            value={summaryData.summary.total_effective_paid_days}
            icon={Calendar}
            color="var(--color-status-success)"
          />
        </div>
      )}

      {/* Period Metadata Card */}
      {selectedPeriod && (
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
                {MONTH_NAMES[selectedPeriod.month]} {selectedPeriod.year} Period Overview
              </h3>
              <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                Coverage: {selectedPeriod.start_date} to {selectedPeriod.end_date} • {selectedPeriod.record_count} total generated payroll records
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>Status:</span>
              <StatusBadge
                status={selectedPeriod.status === 'approved' ? 'approved' : 'pending'}
                label={selectedPeriod.status === 'approved' ? 'Approved & Locked' : 'Draft Pending Approval'}
              />
            </div>
          </div>
        </Card>
      )}

      {/* Tab Controls */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--color-border)', gap: '1.5rem', marginBottom: '-0.5rem' }}>
        <button
          onClick={() => setActiveTab('reconciliation')}
          style={{
            background: 'none',
            border: 'none',
            padding: '12px 4px',
            fontSize: '0.95rem',
            fontWeight: activeTab === 'reconciliation' ? 600 : 400,
            color: activeTab === 'reconciliation' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            borderBottom: activeTab === 'reconciliation' ? '2px solid var(--color-primary)' : '2px solid transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <FileSpreadsheet size={18} />
          <span>Reconciliation Ledger</span>
          {reconciliationRecords.length > 0 && (
            <span style={{ fontSize: '0.75rem', background: 'var(--color-bg-subtle)', padding: '2px 8px', borderRadius: '12px' }}>
              {reconciliationRecords.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('breakdown')}
          style={{
            background: 'none',
            border: 'none',
            padding: '12px 4px',
            fontSize: '0.95rem',
            fontWeight: activeTab === 'breakdown' ? 600 : 400,
            color: activeTab === 'breakdown' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            borderBottom: activeTab === 'breakdown' ? '2px solid var(--color-primary)' : '2px solid transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Layers size={18} />
          <span>Organization Breakdown</span>
        </button>

        <button
          onClick={() => setActiveTab('exceptions')}
          style={{
            background: 'none',
            border: 'none',
            padding: '12px 4px',
            fontSize: '0.95rem',
            fontWeight: activeTab === 'exceptions' ? 600 : 400,
            color: activeTab === 'exceptions' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            borderBottom: activeTab === 'exceptions' ? '2px solid var(--color-primary)' : '2px solid transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <AlertTriangle size={18} />
          <span>Discrepancies & Exceptions</span>
          {exceptions.length > 0 && (
            <span style={{ fontSize: '0.75rem', background: 'var(--color-danger)', color: '#fff', padding: '2px 8px', borderRadius: '12px' }}>
              {exceptions.length}
            </span>
          )}
        </button>
      </div>

      {/* Tab 1: Reconciliation Ledger */}
      {activeTab === 'reconciliation' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Filters Bar */}
          <Card>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center' }}>
              <div style={{ flex: '1 1 200px', position: 'relative' }}>
                <Search size={16} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-muted)' }} />
                <input
                  type="text"
                  placeholder="Search employee name or code..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  style={{ width: '100%', paddingLeft: '34px', paddingRight: '12px', height: '38px', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}
                />
              </div>

              <div style={{ flex: '1 1 180px' }}>
                <select
                  value={selectedBranch}
                  onChange={(e) => setSelectedBranch(e.target.value)}
                  style={{ width: '100%', height: '38px', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', padding: '0 12px' }}
                >
                  <option value="">All Branches</option>
                  {branches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ flex: '1 1 180px' }}>
                <select
                  value={selectedDepartment}
                  onChange={(e) => setSelectedDepartment(e.target.value)}
                  style={{ width: '100%', height: '38px', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', padding: '0 12px' }}
                >
                  <option value="">All Departments</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>

              {(selectedBranch || selectedDepartment || searchTerm) && (
                <button
                  onClick={() => {
                    setSelectedBranch('');
                    setSelectedDepartment('');
                    setSearchTerm('');
                  }}
                  className="btn btn-secondary"
                  style={{ height: '38px' }}
                >
                  Reset Filters
                </button>
              )}
            </div>
          </Card>

          {/* Reconciliation Table */}
          <Card>
            {loadingRecords ? (
              <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-text-muted)' }}>
                Loading reconciliation records...
              </div>
            ) : reconciliationRecords.length === 0 ? (
              <EmptyState
                title="No Reconciliation Records"
                description="No payroll records match the selected filters or period."
              />
            ) : (
              <Table
                data={reconciliationRecords}
                columns={reconciliationColumns}
                keyExtractor={(r) => r.id}
              />
            )}
          </Card>
        </div>
      )}

      {/* Tab 2: Organization Breakdown */}
      {activeTab === 'breakdown' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {loadingBreakdown ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-text-muted)' }}>
              Loading organizational breakdown...
            </div>
          ) : !breakdownData ? (
            <EmptyState
              title="No Breakdown Data"
              description="Organizational breakdown is unavailable for this period."
            />
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.5rem' }}>
              {/* Branch Breakdown */}
              <Card>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem' }}>
                  <Building2 size={20} color="var(--color-primary)" />
                  <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>Branch Cost Distribution</h3>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {breakdownData.by_branch.map((b) => {
                    const pct = Math.round((b.headcount / maxBranchCount) * 100);
                    return (
                      <div key={b.branch_id ?? 'unassigned'} style={{ borderBottom: '1px solid var(--color-border)', paddingBottom: '0.75rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <span style={{ fontWeight: 600 }}>{b.branch_name}</span>
                          <span style={{ fontSize: '0.9rem', color: 'var(--color-text-secondary)' }}>
                            {b.headcount} employee{b.headcount !== 1 ? 's' : ''}
                          </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--color-text-muted)', marginBottom: '6px' }}>
                          <span>Total Payout: {b.total_net_salary !== null ? formatCurrency(b.total_net_salary) : '—'}</span>
                          <span>Avg Payout: {b.average_net_salary !== null ? formatCurrency(b.average_net_salary) : '—'}</span>
                        </div>
                        <div style={{ height: '6px', width: '100%', background: 'var(--color-bg-subtle)', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${pct}%`, background: 'var(--color-primary)', borderRadius: '3px' }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>

              {/* Department Breakdown */}
              <Card>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem' }}>
                  <GitBranch size={20} color="var(--color-primary)" />
                  <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>Department Cost Distribution</h3>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {breakdownData.by_department.map((d) => {
                    const pct = Math.round((d.headcount / maxDeptCount) * 100);
                    return (
                      <div key={d.department_id ?? 'unassigned'} style={{ borderBottom: '1px solid var(--color-border)', paddingBottom: '0.75rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <span style={{ fontWeight: 600 }}>{d.department_name}</span>
                          <span style={{ fontSize: '0.9rem', color: 'var(--color-text-secondary)' }}>
                            {d.headcount} employee{d.headcount !== 1 ? 's' : ''}
                          </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--color-text-muted)', marginBottom: '6px' }}>
                          <span>Total Payout: {d.total_net_salary !== null ? formatCurrency(d.total_net_salary) : '—'}</span>
                          <span>Avg Payout: {d.average_net_salary !== null ? formatCurrency(d.average_net_salary) : '—'}</span>
                        </div>
                        <div style={{ height: '6px', width: '100%', background: 'var(--color-bg-subtle)', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${pct}%`, background: 'var(--color-info)', borderRadius: '3px' }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Discrepancies & Exceptions */}
      {activeTab === 'exceptions' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <AlertBanner
            type="info"
            message="Automated exception detector identifies compensation configuration issues, missing payroll records for active personnel, full unexcused absences, and unapproved leave overlaps."
          />

          <Card>
            {loadingExceptions ? (
              <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-text-muted)' }}>
                Auditing payroll records and detecting discrepancies...
              </div>
            ) : exceptions.length === 0 ? (
              <EmptyState
                title="No Exceptions Detected"
                description="All active employees have valid compensation, complete attendance records, and reconciled payroll for this period."
              />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {exceptions.map((ex, idx) => (
                  <div
                    key={`${ex.type}-${ex.employee_id}-${idx}`}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      justifyContent: 'space-between',
                      padding: '12px 16px',
                      background: ex.severity === 'high' ? 'rgba(239, 68, 68, 0.05)' : 'var(--color-bg-subtle)',
                      border: `1px solid ${ex.severity === 'high' ? 'rgba(239, 68, 68, 0.2)' : 'var(--color-border)'}`,
                      borderRadius: 'var(--radius-md)',
                      gap: '1rem',
                      flexWrap: 'wrap',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                      <AlertTriangle
                        size={20}
                        color={ex.severity === 'high' ? 'var(--color-danger)' : 'var(--color-warning)'}
                        style={{ marginTop: '2px', flexShrink: 0 }}
                      />
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                            {getExceptionTypeLabel(ex.type)}
                          </span>
                          {getSeverityBadge(ex.severity)}
                        </div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                          Employee: <strong>{ex.employee_name}</strong> ({ex.employee_code})
                        </div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                          {ex.message}
                        </div>
                      </div>
                    </div>

                    <div style={{ alignSelf: 'center' }}>
                      <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', fontStyle: 'italic' }}>
                        Action required before final settlement
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
};
