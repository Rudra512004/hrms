export interface CsvTemplateField {
  csv_header: string;
  type: string;
  required: boolean;
  description: string;
}

export interface CsvTemplate {
  key: string;
  display_name: string;
  filename: string;
  description: string;
  version: string;
  headers: string[];
  fields: CsvTemplateField[];
}

export interface ImportJobPreviewRow {
  row: number;
  status: 'ok' | 'error';
  data?: Record<string, any>;
  error?: string;
}

export interface ImportJob {
  id: string;
  template_key: string;
  status: 'pending' | 'validating' | 'validated' | 'executing' | 'completed' | 'completed_with_errors' | 'failed';
  original_filename: string;
  total_rows: number;
  valid_rows: number;
  created_count: number;
  updated_count: number;
  skipped_count: number;
  error_count: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  preview_data: ImportJobPreviewRow[];
}

export interface ImportJobError {
  row_number: number;
  field: string;
  error_type: string;
  message: string;
  row_data: Record<string, any>;
}
