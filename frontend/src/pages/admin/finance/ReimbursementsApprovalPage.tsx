import React, { useState, useEffect } from 'react';
import { PageHeader } from '../../../components/PageHeader';
import { Table, type Column } from '../../../components/Table';
import { StatusBadge } from '../../../components/StatusBadge';
import { Card } from '../../../components/Card';
import { allowanceService } from '../../../services/allowances';
import { CheckCircle } from 'lucide-react';
import { Modal } from '../../../components/Modal';

interface ReimbursementClaim {
  id: string;
  employee_name: string;
  allowance_type_name: string;
  allowance_type_category: string;
  amount_claimed: string;
  amount_approved: string;
  expense_date: string;
  status: string;
  description: string;
}

export const ReimbursementsApprovalPage: React.FC = () => {
  const [claims, setClaims] = useState<ReimbursementClaim[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedClaim, setSelectedClaim] = useState<ReimbursementClaim | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchClaims = async () => {
    try {
      setLoading(true);
      const data = await allowanceService.getReimbursementClaims();
      setClaims(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch reimbursements');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClaims();
  }, []);

  const handleAction = async (id: string, action: 'approve' | 'reject') => {
    try {
      if (action === 'approve') {
        await allowanceService.approveReimbursement(id, `${action}d from UI`);
      } else {
        await allowanceService.rejectReimbursement(id, `${action}d from UI`);
      }
      fetchClaims();
      setIsModalOpen(false);
    } catch (err: any) {
      setError(err.message || `Failed to ${action} claim`);
    }
  };

  const columns: Column<ReimbursementClaim>[] = [
    {
      key: 'employee',
      title: 'Employee',
      render: (row) => row.employee_name,
    },
    {
      key: 'allowance_type',
      title: 'Allowance Type',
      render: (row) => (
        <div>
          <div style={{ fontWeight: 500 }}>{row.allowance_type_name}</div>
          <div style={{ fontSize: '13px', color: '#6b7280' }}>
            {new Date(row.expense_date).toLocaleDateString()}
          </div>
        </div>
      ),
    },
    {
      key: 'amount',
      title: 'Amount',
      render: (row) => `$${row.amount_claimed}`,
    },
    {
      key: 'status',
      title: 'Status',
      render: (row) => (
        <StatusBadge status={row.status === 'submitted' ? 'pending' : row.status} />
      ),
    },
    {
      key: 'actions',
      title: 'Actions',
      render: (row) => row.status === 'submitted' ? (
        <div style={{ display: 'flex', gap: '8px' }}>
          <button 
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#10b981' }}
            onClick={() => { setSelectedClaim(row); setIsModalOpen(true); }}
            title="Review"
          >
            <CheckCircle size={18} />
          </button>
        </div>
      ) : null
    }
  ];

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <PageHeader 
        title="Reimbursement Claims" 
        subtitle="Review and approve employee reimbursement claims"
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

      {isModalOpen && selectedClaim && (
        <Modal
          onClose={() => setIsModalOpen(false)}
          title="Review Claim"
        >
          <div>
            <div style={{ marginBottom: '16px' }}>
              <strong>Employee:</strong> {selectedClaim.employee_name}
            </div>
            <div style={{ marginBottom: '16px' }}>
              <strong>Type:</strong> {selectedClaim.allowance_type_name}
            </div>
            <div style={{ marginBottom: '16px' }}>
              <strong>Amount Claimed:</strong> ${selectedClaim.amount_claimed}
            </div>
            <div style={{ marginBottom: '16px' }}>
              <strong>Description:</strong>
              <p>{selectedClaim.description}</p>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
              <button className="btn-secondary" onClick={() => setIsModalOpen(false)}>Cancel</button>
              <button 
                style={{ padding: '8px 16px', backgroundColor: '#ef4444', color: 'white', borderRadius: '6px', border: 'none', cursor: 'pointer' }}
                onClick={() => handleAction(selectedClaim.id, 'reject')}
              >
                Reject
              </button>
              <button 
                className="btn-primary" 
                onClick={() => handleAction(selectedClaim.id, 'approve')}
              >
                Approve
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
