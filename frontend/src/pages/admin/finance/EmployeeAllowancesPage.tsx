import React, { useState, useEffect } from 'react';
import { PageHeader } from '../../../components/PageHeader';
import { Table, type Column } from '../../../components/Table';
import { StatusBadge } from '../../../components/StatusBadge';
import { Card } from '../../../components/Card';
import { allowanceService } from '../../../services/allowances';
import { Plus } from 'lucide-react';
import { Modal } from '../../../components/Modal';

interface EmployeeAllowance {
  id: string;
  employee: string;
  allowance_type_name: string;
  allowance_type_category: string;
  amount: string;
  frequency: string;
  effective_from: string;
  is_active: boolean;
}

export const EmployeeAllowancesPage: React.FC = () => {
  const [allowances, setAllowances] = useState<EmployeeAllowance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchAllowances = async () => {
    try {
      setLoading(true);
      const data = await allowanceService.getEmployeeAllowances();
      setAllowances(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch employee allowances');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllowances();
  }, []);

  const columns: Column<EmployeeAllowance>[] = [
    {
      key: 'employee',
      title: 'Employee ID',
      render: (row) => row.employee,
    },
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
        title="Employee Allowances" 
        subtitle="Manage active allowance assignments for employees"
        actions={
          <button 
            className="btn-primary" 
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            onClick={() => setIsModalOpen(true)}
          >
            <Plus size={16} />
            Assign Allowance
          </button>
        }
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

      {isModalOpen && (
        <Modal
          onClose={() => setIsModalOpen(false)}
          title="Assign Allowance"
        >
          <div style={{ padding: '16px 0', color: '#4b5563' }}>
            Form for assigning an allowance to an employee will go here.
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
            <button className="btn-secondary" onClick={() => setIsModalOpen(false)}>Cancel</button>
            <button className="btn-primary" onClick={() => setIsModalOpen(false)}>Save</button>
          </div>
        </Modal>
      )}
    </div>
  );
};
