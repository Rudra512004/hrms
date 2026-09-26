import React from 'react';
import { FileText, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface Column<T> {
  key: string | keyof T;
  title: string;
  render?: (item: T) => React.ReactNode;
  className?: string;
}

export interface TableProps<T> {
  data: T[];
  columns: Column<T>[];
  keyExtractor: (item: T) => string | number;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyIcon?: LucideIcon;
  pagination?: boolean;
  count?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  loading?: boolean;
}

export function Table<T>({
  data,
  columns,
  keyExtractor,
  emptyTitle = 'No data',
  emptyDescription = 'No records to display.',
  emptyIcon: EmptyIcon = FileText,
  pagination = false,
  count,
  page = 1,
  pageSize = 20,
  onPageChange,
  loading = false,
}: TableProps<T>) {
  const totalRecords = count !== undefined ? count : data.length;
  const currentPage = Math.max(1, page);
  const currentPageSize = Math.max(1, pageSize);
  const totalPages = Math.max(1, Math.ceil(totalRecords / currentPageSize));
  const isFirstPage = currentPage <= 1;
  const isLastPage = currentPage >= totalPages;

  const startRecord = totalRecords === 0 ? 0 : (currentPage - 1) * currentPageSize + 1;
  const endRecord = Math.min(currentPage * currentPageSize, totalRecords);

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key.toString()} className={col.className}>
                {col.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading && data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="table-empty-cell">
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '32px 16px', gap: '8px' }}>
                  <Loader2 size={24} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
                  <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>Loading data...</span>
                </div>
              </td>
            </tr>
          ) : data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="table-empty-cell">
                <div className="empty-state" style={{ padding: '32px 16px' }}>
                  <EmptyIcon size={32} className="empty-state-icon" />
                  <p className="empty-state-title">{emptyTitle}</p>
                  <p className="empty-state-description">{emptyDescription}</p>
                </div>
              </td>
            </tr>
          ) : (
            data.map((item) => (
              <tr key={keyExtractor(item)}>
                {columns.map((col) => (
                  <td key={col.key.toString()} className={col.className}>
                    {col.render
                      ? col.render(item)
                      : (item[col.key as keyof T] as React.ReactNode)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>

      {pagination && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 16px',
            borderTop: '1px solid var(--color-border)',
            backgroundColor: 'var(--color-bg-card, #ffffff)',
            fontSize: 'var(--font-size-sm, 14px)',
            color: 'var(--color-text-muted, #64748b)',
            flexWrap: 'wrap',
            gap: '12px',
          }}
          data-testid="table-pagination"
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>
              Showing {startRecord} to {endRecord} of {totalRecords} records
            </span>
            {loading && data.length > 0 && (
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '12px',
                  color: 'var(--color-primary)',
                }}
              >
                <Loader2 size={13} className="animate-spin" />
                Updating...
              </span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span>
              Page {currentPage} of {totalPages}
            </span>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => onPageChange?.(currentPage - 1)}
                disabled={isFirstPage || loading}
                aria-label="Previous page"
                data-testid="pagination-prev"
              >
                <ChevronLeft size={16} />
                Previous
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => onPageChange?.(currentPage + 1)}
                disabled={isLastPage || loading}
                aria-label="Next page"
                data-testid="pagination-next"
              >
                Next
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
