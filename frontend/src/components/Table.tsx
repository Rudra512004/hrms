import React from 'react';
import { FileText } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface Column<T> {
  key: string | keyof T;
  title: string;
  render?: (item: T) => React.ReactNode;
  className?: string;
}

interface TableProps<T> {
  data: T[];
  columns: Column<T>[];
  keyExtractor: (item: T) => string | number;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyIcon?: LucideIcon;
}

export function Table<T>({
  data,
  columns,
  keyExtractor,
  emptyTitle = 'No data',
  emptyDescription = 'No records to display.',
  emptyIcon: EmptyIcon = FileText,
}: TableProps<T>) {
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
          {data.length === 0 ? (
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
    </div>
  );
}
