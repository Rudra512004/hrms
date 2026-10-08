import React, { useState, useEffect } from 'react';
import { PageHeader } from '../../components/PageHeader';
import { Table, type Column } from '../../components/Table';
import { StatusBadge } from '../../components/StatusBadge';
import { Card } from '../../components/Card';
import { allowanceService } from '../../services/allowances';
import { Plus } from 'lucide-react';
import { Modal } from '../../components/Modal';

interface MyReimbursement {
  id: string;
  allowance_type_name: string;
  allowance_type_category: string;
  amount_claimed: string;
  amount_approved: string | null;
  expense_date: string;
  status: string;
}

export const MyReimbursementsPage: React.FC = () => {
  const [claims, setClaims] = useState<MyReimbursement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchClaims = async () => {
    try {
      setLoading(true);
      const data = await allowanceService.getMyReimbursements();
      setClaims(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch your reimbursement claims');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClaims();
  }, []);

  const columns: Column<MyReimbursement>[] = [
    {
      key: 'allowance_type',
      title: 'Allowance Type',
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
      key: 'expense_date',
      title: 'Expense Date',
      render: (row) => new Date(row.expense_date).toLocaleDateString(),
    },
    {
      key: 'amount_claimed',
      title: 'Amount Claimed',
      render: (row) => `$${row.amount_claimed}`,
    },
    {
      key: 'amount_approved',
      title: 'Amount Approved',
      render: (row) => row.amount_approved ? `$${row.amount_approved}` : '-',
    },
    {
      key: 'status',
      title: 'Status',
      render: (row) => (
        <StatusBadge status={row.status === 'submitted' ? 'pending' : row.status} />
      ),
    }
  ];

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <PageHeader 
        title="My Reimbursements" 
        subtitle="Submit and track your expense reimbursement claims"
        actions={
          <button 
            className="btn-primary" 
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            onClick={() => setIsModalOpen(true)}
          >
            <Plus size={16} />
            Submit Claim
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
          data={claims} 
          loading={loading}
          keyExtractor={(item) => item.id}
        />
      </Card>

      {isModalOpen && (
        <Modal
          onClose={() => setIsModalOpen(false)}
          title="Submit Reimbursement Claim"
        >
          <div style={{ padding: '16px 0', color: '#4b5563' }}>
            Form for submitting a new reimbursement claim will go here.
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
            <button className="btn-secondary" onClick={() => setIsModalOpen(false)}>Cancel</button>
            <button className="btn-primary" onClick={() => setIsModalOpen(false)}>Submit</button>
          </div>
        </Modal>
      )}
    </div>
  );
};
