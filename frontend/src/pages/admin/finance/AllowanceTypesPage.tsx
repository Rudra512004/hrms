import React, { useState, useEffect } from 'react';
import { PageHeader } from '../../../components/PageHeader';
import { Table, type Column } from '../../../components/Table';
import { StatusBadge } from '../../../components/StatusBadge';
import { Card } from '../../../components/Card';
import { allowanceService } from '../../../services/allowances';
import { Plus, Edit, Trash2 } from 'lucide-react';
import { Modal } from '../../../components/Modal';

interface AllowanceType {
  id: string;
  name: string;
  code: string;
  category: string;
  calculation_type: string;
  default_amount: string;
  frequency: string;
  taxable: boolean;
  requires_approval: boolean;
  is_active: boolean;
}

export const AllowanceTypesPage: React.FC = () => {
  const [allowances, setAllowances] = useState<AllowanceType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchAllowances = async () => {
    try {
      setLoading(true);
      const data = await allowanceService.getAllowanceTypes();
      setAllowances(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch allowance types');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllowances();
  }, []);

  const columns: Column<AllowanceType>[] = [
    {
      key: 'name',
      title: 'Name',
      render: (row) => (
        <div>
          <div style={{ fontWeight: 500 }}>{row.name}</div>
          <div style={{ fontSize: '13px', color: '#6b7280' }}>{row.code}</div>
        </div>
      ),
    },
    {
      key: 'category',
      title: 'Category',
      render: (row) => <span style={{ textTransform: 'capitalize' }}>{row.category}</span>,
    },
    {
      key: 'amount',
      title: 'Amount',
      render: (row) => (
        <div>
          {row.calculation_type === 'fixed' ? `$${row.default_amount}` : `${row.calculation_type}`}
          <div style={{ fontSize: '13px', color: '#6b7280', textTransform: 'capitalize' }}>
            {row.frequency}
          </div>
        </div>
      ),
    },
    {
      key: 'taxable',
      title: 'Taxable',
      render: (row) => row.taxable ? 'Yes' : 'No',
    },
    {
      key: 'status',
      title: 'Status',
      render: (row) => (
        <StatusBadge status={row.is_active ? 'active' : 'inactive'} />
      ),
    },
    {
      key: 'actions',
      title: 'Actions',
      render: () => (
        <div style={{ display: 'flex', gap: '8px' }}>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#3b82f6' }}>
            <Edit size={18} />
          </button>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444' }}>
            <Trash2 size={18} />
          </button>
        </div>
      )
    }
  ];

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <PageHeader 
        title="Allowance Types" 
        subtitle="Manage company allowance categories and rules"
        actions={
          <button 
            className="btn-primary" 
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            onClick={() => setIsModalOpen(true)}
          >
            <Plus size={16} />
            New Allowance
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
          title="Create Allowance Type"
        >
          <div style={{ padding: '16px 0', color: '#4b5563' }}>
            Implementation for the allowance creation form will go here.
            This will use a standard form with fields for code, name, category, and calculation type.
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
