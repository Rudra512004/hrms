import React, { useEffect, useState } from 'react';
import { Plus, CheckCircle2, AlertCircle } from 'lucide-react';
import { PageHeader } from '../../components/PageHeader';
import { Table } from '../../components/Table';
import { Modal } from '../../components/Modal';
import { StatusBadge } from '../../components/StatusBadge';
import { reviews, type Review, type Cycle } from '../../services/reviews';
import { employeeManagementService } from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';

export const ManagerReviewsPage: React.FC = () => {
  const [data, setData] = useState<Review[]>([]);
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [employees, setEmployees] = useState<EmployeeProfile[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isCycleModalOpen, setIsCycleModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Form states for creating review
  const [formCycle, setFormCycle] = useState<number | ''>('');
  const [formEmployee, setFormEmployee] = useState<number | ''>('');
  const [formRating, setFormRating] = useState<number | ''>('');
  const [formSummary, setFormSummary] = useState('');
  
  // Form states for creating cycle
  const [cycleName, setCycleName] = useState('');
  const [cycleStart, setCycleStart] = useState('');
  const [cycleEnd, setCycleEnd] = useState('');

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [r, c, e] = await Promise.all([
        reviews.list(),
        reviews.cycles(),
        employeeManagementService.listEmployees({ paginate: false })
      ]);
      setData(r);
      setCycles(c);
      if (Array.isArray(e)) {
        setEmployees(e);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load reviews.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const handleCreateReview = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await reviews.create({
        cycle: Number(formCycle),
        employee: Number(formEmployee),
        rating: formRating ? Number(formRating) : undefined,
        summary: formSummary
      });
      setIsModalOpen(false);
      void loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to create review.');
    } finally {
      setSubmitting(false);
    }
  };
  
  const handleCreateCycle = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await reviews.addCycle({
        name: cycleName,
        start_date: cycleStart,
        end_date: cycleEnd
      });
      setIsCycleModalOpen(false);
      void loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to create cycle.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitReview = async (id: number) => {
    if (!window.confirm('Are you sure you want to submit this review? Once submitted, it cannot be edited.')) return;
    setError(null);
    try {
      await reviews.submit(id);
      void loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to submit review.');
    }
  };

  const columns = [
    {
      key: 'employee_name',
      title: 'Employee',
    },
    {
      key: 'cycle_name',
      title: 'Cycle',
      render: (item: Review) => {
        const c = cycles.find(x => x.id === item.cycle);
        return c ? c.name : `Cycle ${item.cycle}`;
      }
    },
    {
      key: 'rating',
      title: 'Rating',
      render: (item: Review) => item.rating ? `${item.rating}/5` : 'N/A'
    },
    {
      key: 'status',
      title: 'Status',
      render: (item: Review) => <StatusBadge status={item.status} />
    },
    {
      key: 'actions',
      title: 'Actions',
      render: (item: Review) => (
        <div style={{ display: 'flex', gap: '8px' }}>
          {item.status === 'draft' && (
            <button 
              className="btn btn-primary btn-sm"
              onClick={() => handleSubmitReview(item.id)}
            >
              <CheckCircle2 size={16} /> Submit
            </button>
          )}
        </div>
      )
    }
  ];

  return (
    <div>
      <PageHeader
        title="Performance Reviews"
        subtitle="Manage performance reviews for your direct reports"
        actions={
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="btn btn-secondary" onClick={() => setIsCycleModalOpen(true)}>
              <Plus size={16} /> New Cycle
            </button>
            <button className="btn btn-primary" onClick={() => setIsModalOpen(true)}>
              <Plus size={16} /> New Review
            </button>
          </div>
        }
      />

      {error && (
        <div className="alert alert-danger" style={{ marginBottom: 16 }}>
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <div className="card">
        <Table
          data={data}
          columns={columns}
          keyExtractor={(item) => item.id}
          loading={loading}
          emptyTitle="No Reviews Found"
          emptyDescription="You haven't created any reviews yet."
        />
      </div>

      {isModalOpen && (
        <Modal
          title="Create Performance Review"
          onClose={() => !submitting && setIsModalOpen(false)}
        >
          <form onSubmit={handleCreateReview}>
            <div className="form-group">
              <label htmlFor="reviewCycle" className="form-label">Review Cycle</label>
              <select 
                id="reviewCycle"
                className="form-control" 
                required 
                value={formCycle} 
                onChange={e => setFormCycle(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="">Select a cycle...</option>
                {cycles.map(c => (
                  <option key={c.id} value={c.id}>{c.name} ({c.start_date} to {c.end_date})</option>
                ))}
              </select>
            </div>
            
            <div className="form-group">
              <label htmlFor="reviewEmployee" className="form-label">Employee</label>
              <select 
                id="reviewEmployee"
                className="form-control" 
                required 
                value={formEmployee} 
                onChange={e => setFormEmployee(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="">Select an employee...</option>
                {employees.map(e => (
                  <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="reviewRating" className="form-label">Rating (1-5)</label>
              <input 
                id="reviewRating"
                type="number" 
                className="form-control" 
                min="1" max="5" 
                value={formRating} 
                onChange={e => setFormRating(e.target.value ? Number(e.target.value) : "")}
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="reviewSummary" className="form-label">Summary</label>
              <textarea 
                id="reviewSummary"
                className="form-control" 
                rows={4}
                value={formSummary} 
                onChange={e => setFormSummary(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 24 }}>
              <button 
                type="button" 
                className="btn btn-secondary" 
                onClick={() => setIsModalOpen(false)}
                disabled={submitting}
              >
                Cancel
              </button>
              <button 
                type="submit" 
                className="btn btn-primary"
                disabled={submitting}
              >
                {submitting ? 'Creating...' : 'Create Draft'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {isCycleModalOpen && (
        <Modal
          title="Create Review Cycle"
          onClose={() => !submitting && setIsCycleModalOpen(false)}
        >
          <form onSubmit={handleCreateCycle}>
            <div className="form-group">
              <label htmlFor="cycleName" className="form-label">Cycle Name</label>
              <input 
                id="cycleName"
                type="text" 
                className="form-control" 
                required 
                value={cycleName} 
                onChange={e => setCycleName(e.target.value)}
                placeholder="e.g. 2026 Q1 Review"
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="cycleStart" className="form-label">Start Date</label>
              <input 
                id="cycleStart"
                type="date" 
                className="form-control" 
                required 
                value={cycleStart} 
                onChange={e => setCycleStart(e.target.value)}
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="cycleEnd" className="form-label">End Date</label>
              <input 
                id="cycleEnd"
                type="date" 
                className="form-control" 
                required 
                value={cycleEnd} 
                onChange={e => setCycleEnd(e.target.value)}
              />
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 24 }}>
              <button 
                type="button" 
                className="btn btn-secondary" 
                onClick={() => setIsCycleModalOpen(false)}
                disabled={submitting}
              >
                Cancel
              </button>
              <button 
                type="submit" 
                className="btn btn-primary"
                disabled={submitting}
              >
                {submitting ? 'Creating...' : 'Create Cycle'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
