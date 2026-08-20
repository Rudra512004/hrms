import React from 'react';

interface Column<T> {
  key: string | keyof T;
  title: string;
  render?: (item: T) => React.ReactNode;
}

interface TableProps<T> {
  data: T[];
  columns: Column<T>[];
  keyExtractor: (item: T) => string | number;
}

const styles = {
  container: {
    width: '100%',
    overflowX: 'auto' as const,
    boxShadow: 'var(--shadow-inset)',
    borderRadius: 'var(--radius-md)',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
    textAlign: 'left' as const,
  },
  th: {
    padding: 'var(--spacing-md)',
    backgroundColor: 'var(--color-bg-body)',
    color: 'var(--color-text-main)',
    fontWeight: 600,
    borderBottom: '1px solid rgba(0,0,0,0.05)',
    whiteSpace: 'nowrap' as const,
  },
  td: {
    padding: 'var(--spacing-md)',
    borderBottom: '1px solid rgba(0,0,0,0.03)',
    color: 'var(--color-text-main)',
  },
  row: {
    transition: 'background-color 0.2s',
  }
};

export function Table<T>({ data, columns, keyExtractor }: TableProps<T>) {
  return (
    <div style={styles.container}>
      <table style={styles.table}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key.toString()} style={styles.th}>
                {col.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} style={{ ...styles.td, textAlign: 'center' }}>
                No data available
              </td>
            </tr>
          ) : (
            data.map((item) => (
              <tr key={keyExtractor(item)} className="table-row" style={styles.row}>
                {columns.map((col) => (
                  <td key={col.key.toString()} style={styles.td}>
                    {col.render ? col.render(item) : (item[col.key as keyof T] as React.ReactNode)}
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
