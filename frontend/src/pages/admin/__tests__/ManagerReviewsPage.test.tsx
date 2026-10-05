import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ManagerReviewsPage } from '../ManagerReviewsPage';
import { reviews } from '../../../services/reviews';
import { employeeManagementService } from '../../../services/employeeManagement';
import * as AuthContextModule from '../../../contexts/AuthContext';

vi.mock('../../../services/reviews', () => ({
  reviews: {
    list: vi.fn(),
    cycles: vi.fn(),
    create: vi.fn(),
    addCycle: vi.fn(),
    submit: vi.fn(),
  },
}));

vi.mock('../../../services/employeeManagement', () => ({
  employeeManagementService: {
    listEmployees: vi.fn(),
  },
}));

const mockReviews = [
  { id: 1, employee: 10, employee_name: 'John Doe', reviewer: 1, reviewer_name: 'Admin User', rating: 4, summary: 'Good job', status: 'draft', cycle: 1 },
  { id: 2, employee: 11, employee_name: 'Jane Smith', reviewer: 1, reviewer_name: 'Admin User', rating: 5, summary: 'Excellent', status: 'submitted', cycle: 1 },
];

const mockCycles = [
  { id: 1, name: '2025 Q1', start_date: '2025-01-01', end_date: '2025-03-31', is_active: true }
];

const mockEmployees = [
  { id: 10, first_name: 'John', last_name: 'Doe' },
  { id: 11, first_name: 'Jane', last_name: 'Smith' },
];

describe('ManagerReviewsPage', () => {
  let mockAuthContextValue: any;

  beforeEach(() => {
    mockAuthContextValue = {
      user: { id: 1, email: 'admin@beyondsure.com', role: 'Admin' },
      isAuthenticated: true,
      hasPermission: vi.fn((p: string) => p === 'employee.update'),
      loading: false,
      error: null,
    };
    vi.spyOn(AuthContextModule, 'useAuth').mockImplementation(() => mockAuthContextValue);

    (reviews.list as any).mockResolvedValue(mockReviews);
    (reviews.cycles as any).mockResolvedValue(mockCycles);
    (employeeManagementService.listEmployees as any).mockResolvedValue(mockEmployees);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('1. Renders reviews list with cycles and allows draft submission', async () => {
    render(
      <MemoryRouter>
        <ManagerReviewsPage />
      </MemoryRouter>
    );

    // Wait for the data to load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
      expect(screen.getAllByText('2025 Q1')).toHaveLength(2); // cycle name displayed twice in the table
    });

    // John Doe's review is draft, so it should have a submit button
    const submitBtns = screen.getAllByRole('button', { name: /Submit/i });
    expect(submitBtns.length).toBeGreaterThan(0);
    
    // We mock window.confirm
    window.confirm = vi.fn().mockReturnValue(true);
    
    (reviews.submit as any).mockResolvedValue({ ...mockReviews[0], status: 'submitted' });

    fireEvent.click(submitBtns[0]);

    await waitFor(() => {
      expect(reviews.submit).toHaveBeenCalledWith(1);
    });
  });

  it('2. Opens create review modal and creates review successfully', async () => {
    (reviews.create as any).mockResolvedValue({ id: 3, employee: 10, rating: 3, summary: 'Okay', status: 'draft', cycle: 1 });
    
    render(
      <MemoryRouter>
        <ManagerReviewsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    const newReviewBtn = screen.getByRole('button', { name: /New Review/i });
    fireEvent.click(newReviewBtn);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Create Performance Review')).toBeInTheDocument();

    const selectCycle = screen.getByLabelText(/Review Cycle/i);
    const selectEmp = screen.getByLabelText(/Employee/i);
    const inputRating = screen.getByLabelText(/Rating \(1-5\)/i);
    const inputSummary = screen.getByLabelText(/Summary/i);

    fireEvent.change(selectCycle, { target: { value: '1' } });
    fireEvent.change(selectEmp, { target: { value: '10' } });
    fireEvent.change(inputRating, { target: { value: '3' } });
    fireEvent.change(inputSummary, { target: { value: 'Okay' } });

    fireEvent.click(screen.getByRole('button', { name: /Create Draft/i }));

    await waitFor(() => {
      expect(reviews.create).toHaveBeenCalledWith({
        cycle: 1,
        employee: 10,
        rating: 3,
        summary: 'Okay'
      });
      expect(reviews.list).toHaveBeenCalledTimes(2); // Reloaded
    });
  });

  it('3. Creates a new cycle successfully', async () => {
    (reviews.addCycle as any).mockResolvedValue({ id: 2, name: '2025 Q2', start_date: '2025-04-01', end_date: '2025-06-30' });
    
    render(
      <MemoryRouter>
        <ManagerReviewsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    const newCycleBtn = screen.getByRole('button', { name: /New Cycle/i });
    fireEvent.click(newCycleBtn);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Create Review Cycle')).toBeInTheDocument();

    const nameInput = screen.getByLabelText(/Cycle Name/i);
    const startInput = screen.getByLabelText(/Start Date/i);
    const endInput = screen.getByLabelText(/End Date/i);

    fireEvent.change(nameInput, { target: { value: '2025 Q2' } });
    fireEvent.change(startInput, { target: { value: '2025-04-01' } });
    fireEvent.change(endInput, { target: { value: '2025-06-30' } });

    fireEvent.click(screen.getByRole('button', { name: /Create Cycle/i }));

    await waitFor(() => {
      expect(reviews.addCycle).toHaveBeenCalledWith({
        name: '2025 Q2',
        start_date: '2025-04-01',
        end_date: '2025-06-30'
      });
    });
  });

  it('4. Handles API error when creating review', async () => {
    (reviews.create as any).mockRejectedValue(new Error('Cross tenant not allowed'));

    render(
      <MemoryRouter>
        <ManagerReviewsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /New Review/i }));
    
    fireEvent.change(screen.getByLabelText(/Review Cycle/i), { target: { value: '1' } });
    fireEvent.change(screen.getByLabelText(/Employee/i), { target: { value: '10' } });
    fireEvent.click(screen.getByRole('button', { name: /Create Draft/i }));

    await waitFor(() => {
      expect(screen.getByText('Cross tenant not allowed')).toBeInTheDocument();
    });
  });
});
