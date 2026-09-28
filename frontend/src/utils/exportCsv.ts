/**
 * Utility for exporting tabular datasets to CSV files in the browser.
 * Sanitizes formula injection characters and properly escapes quotes/commas.
 */

export interface CsvColumn<T> {
  header: string;
  accessor: (row: T) => string | number | boolean | null | undefined;
}

export function exportToCsv<T>(filename: string, columns: CsvColumn<T>[], data: T[]): void {
  if (!data || data.length === 0) {
    alert('No data available to export.');
    return;
  }

  const escapeCell = (val: string | number | boolean | null | undefined): string => {
    if (val === null || val === undefined) return '""';
    let str = String(val);

    // Prevent formula injection in Excel/Calc: prefix =, +, -, @ with an apostrophe
    if (/^[=+\-@]/.test(str)) {
      str = `'${str}`;
    }

    // Escape internal quotes by doubling them
    str = str.replace(/"/g, '""');

    return `"${str}"`;
  };

  const headerRow = columns.map((col) => escapeCell(col.header)).join(',');
  const dataRows = data.map((row) =>
    columns.map((col) => escapeCell(col.accessor(row))).join(',')
  );

  const csvContent = [headerRow, ...dataRows].join('\r\n');
  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', filename.endsWith('.csv') ? filename : `${filename}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
