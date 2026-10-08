import React, { useState, useEffect } from 'react';
import { PageHeader } from '../../components/PageHeader';
import { Table, type Column } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { Card } from '../../components/Card';
import { allowanceService } from '../../services/allowances';

interface MyAllowance {
  id: string;
  allowance_type_name: string;
  allowance_type_category: string;
  amount: string;
  frequency: string;
  effective_from: string;
  is_active: boolean;
}

export const MyAllowancesPage: React.FC = () => {
  const [allowances, setAllowances] = useState<MyAllowance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAllowances = async () => {
    try {
      setLoading(true);
      const data = await allowanceService.getMyAllowances();
      setAllowances(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch your allowances');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllowances();
  }, []);

  const columns: Column<MyAllowance>[] = [
    {
      key: 'allowance',
      title: 'Allowance',
      render: (row) => (
        <div>
          <div style={{ fontWeight: 500 }}>{row.allowance_type_name}</div>
          <div style={{ fontSize: '13px', color: '#6b7280', textTransform: 'capitalize' }}>
            {row.allowance_type_category}
          </div>
        </div>
      ),
    },
    {
      key: 'amount',
      title: 'Amount',
      render: (row) => `$${row.amount} / ${row.frequency}`,
    },
    {
      key: 'effective_from',
      title: 'Effective From',
      render: (row) => new Date(row.effective_from).toLocaleDateString(),
    },
    {
      key: 'status',
      title: 'Status',
      render: (row) => (
        <StatusBadge status={row.is_active ? 'active' : 'inactive'} />
      ),
    }
  ];

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <PageHeader 
        title="My Allowances" 
        subtitle="View your active allowances and benefits"
      />
      
      {error && (
        <div style={{ padding: '12px', backgroundColor: '#fef2f2', color: '#991b1b', borderRadius: '6px', marginBottom: '16px' }}>
          {error}
        </div>
      )}

      <Card>
        <Table 
          columns={columns} 
          data={allowances} 
          loading={loading}
          keyExtractor={(item) => item.id}
        />
      </Card>
    </div>
  );
};
