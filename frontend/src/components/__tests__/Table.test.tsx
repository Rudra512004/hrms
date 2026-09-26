import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Table } from '../Table';

describe('Table Component', () => {
  interface Item {
    id: number;
    name: string;
    role: string;
  }

  const columns = [
    { key: 'name', title: 'Name' },
    { key: 'role', title: 'Role' },
  ];

  const mockData: Item[] = [
    { id: 1, name: 'Alice', role: 'Engineer' },
    { id: 2, name: 'Bob', role: 'Designer' },
  ];

  it('renders unpaginated data without pagination controls by default', () => {
    render(
      <Table
        data={mockData}
        columns={columns}
        keyExtractor={(item) => item.id}
      />
    );

    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(screen.queryByTestId('table-pagination')).not.toBeInTheDocument();
  });

  it('renders empty state when data is empty and not loading', () => {
    render(
      <Table
        data={[] as Item[]}
        columns={columns}
        keyExtractor={(item) => item.id}
        emptyTitle="Custom Empty Title"
        emptyDescription="Custom Empty Description"
      />
    );

    expect(screen.getByText('Custom Empty Title')).toBeInTheDocument();
    expect(screen.getByText('Custom Empty Description')).toBeInTheDocument();
    expect(screen.queryByTestId('table-pagination')).not.toBeInTheDocument();
  });

  it('renders pagination controls when pagination is true', () => {
    const onPageChange = vi.fn();
    render(
      <Table
        data={mockData}
        columns={columns}
        keyExtractor={(item) => item.id}
        pagination
        count={50}
        page={2}
        pageSize={20}
        onPageChange={onPageChange}
      />
    );

    expect(screen.getByTestId('table-pagination')).toBeInTheDocument();
    expect(screen.getByText('Showing 21 to 40 of 50 records')).toBeInTheDocument();
    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument();

    const prevBtn = screen.getByTestId('pagination-prev');
    const nextBtn = screen.getByTestId('pagination-next');
    expect(prevBtn).not.toBeDisabled();
    expect(nextBtn).not.toBeDisabled();

    fireEvent.click(prevBtn);
    expect(onPageChange).toHaveBeenCalledWith(1);

    fireEvent.click(nextBtn);
    expect(onPageChange).toHaveBeenCalledWith(3);
  });

  it('disables previous button on first page', () => {
    render(
      <Table
        data={mockData}
        columns={columns}
        keyExtractor={(item) => item.id}
        pagination
        count={50}
        page={1}
        pageSize={20}
      />
    );

    const prevBtn = screen.getByTestId('pagination-prev');
    const nextBtn = screen.getByTestId('pagination-next');
    expect(prevBtn).toBeDisabled();
    expect(nextBtn).not.toBeDisabled();
  });

  it('disables next button on final page', () => {
    render(
      <Table
        data={mockData}
        columns={columns}
        keyExtractor={(item) => item.id}
        pagination
        count={50}
        page={3}
        pageSize={20}
      />
    );

    const prevBtn = screen.getByTestId('pagination-prev');
    const nextBtn = screen.getByTestId('pagination-next');
    expect(prevBtn).not.toBeDisabled();
    expect(nextBtn).toBeDisabled();
  });

  it('handles empty results cleanly with pagination enabled', () => {
    render(
      <Table
        data={[] as Item[]}
        columns={columns}
        keyExtractor={(item) => item.id}
        pagination
        count={0}
        page={1}
        pageSize={20}
      />
    );

    expect(screen.getByText('No data')).toBeInTheDocument();
    expect(screen.getByTestId('table-pagination')).toBeInTheDocument();
    expect(screen.getByText('Showing 0 to 0 of 0 records')).toBeInTheDocument();
    expect(screen.getByText('Page 1 of 1')).toBeInTheDocument();
    expect(screen.getByTestId('pagination-prev')).toBeDisabled();
    expect(screen.getByTestId('pagination-next')).toBeDisabled();
  });

  it('disables navigation buttons when loading is true', () => {
    render(
      <Table
        data={mockData}
        columns={columns}
        keyExtractor={(item) => item.id}
        pagination
        count={50}
        page={2}
        pageSize={20}
        loading
      />
    );

    expect(screen.getByTestId('pagination-prev')).toBeDisabled();
    expect(screen.getByTestId('pagination-next')).toBeDisabled();
    expect(screen.getByText('Updating...')).toBeInTheDocument();
  });

  it('shows loading spinner in table body when loading with empty data', () => {
    render(
      <Table
        data={[] as Item[]}
        columns={columns}
        keyExtractor={(item) => item.id}
        pagination
        count={0}
        page={1}
        pageSize={20}
        loading
      />
    );

    expect(screen.getByText('Loading data...')).toBeInTheDocument();
    expect(screen.queryByText('No data')).not.toBeInTheDocument();
  });
});
