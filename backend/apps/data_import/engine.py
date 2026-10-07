import csv
from django.db import transaction
from django.utils import timezone
from apps.data_import.models import ImportJob, ImportJobError
from apps.data_import.validators import validate_csv_structure, parse_and_resolve_row
from apps.data_import.executors import EXECUTOR_MAP
from apps.data_import.exceptions import ImportValidationError, RowValidationError

class ImportEngine:
    """
    Universal CSV Import Engine.
    Handles the validation, preview generation, and execution of import jobs.
    """
    
    def __init__(self, job):
        self.job = job
        self.organization = job.organization
        self.template_key = job.template_key

    def validate_and_preview(self):
        """
        Phase 1: Structure validation and preview generation.
        Returns stats but does not save the file state to 'validated' - the caller should do that.
        """
        if self.job.status != 'pending':
            raise ImportValidationError(f"Cannot validate job in {self.job.status} state.")
            
        self.job.status = 'validating'
        self.job.save(update_fields=['status'])

        try:
            with self.job.file.open('r') as f:
                headers, raw_rows = validate_csv_structure(f, self.template_key)

            self.job.total_rows = len(raw_rows)
            preview_data = []

            # Generate preview (first 5 rows parsed without executing)
            for i, row in enumerate(raw_rows[:5]):
                try:
                    parsed = parse_and_resolve_row(i + 1, row, headers, self.template_key, self.organization)
                    # Convert objects to string representations for JSON preview
                    serializable = {}
                    for k, v in parsed.items():
                        if k == 'components' and isinstance(v, dict):
                            serializable[k] = {ck: str(cv) for ck, cv in v.items()}
                        elif hasattr(v, 'pk'):
                            serializable[k] = str(v)
                        else:
                            serializable[k] = str(v) if v is not None else None
                    preview_data.append({'row': i + 1, 'data': serializable, 'status': 'ok'})
                except RowValidationError as e:
                    preview_data.append({'row': i + 1, 'error': str(e), 'status': 'error'})
                except Exception as e:
                    preview_data.append({'row': i + 1, 'error': str(e), 'status': 'error'})

            self.job.preview_data = preview_data
            self.job.status = 'validated'
            self.job.save(update_fields=['total_rows', 'preview_data', 'status'])
            
            return True

        except Exception as e:
            self.job.status = 'failed'
            self.job.save(update_fields=['status'])
            raise e

    def execute(self):
        """
        Phase 2: Row-isolated execution.
        """
        if self.job.status != 'validated':
            raise ImportValidationError(f"Cannot execute job in {self.job.status} state. Must be 'validated'.")

        self.job.status = 'executing'
        self.job.started_at = timezone.now()
        self.job.save(update_fields=['status', 'started_at'])

        try:
            with self.job.file.open('r') as f:
                headers, raw_rows = validate_csv_structure(f, self.template_key)

            executor = EXECUTOR_MAP[self.template_key]
            
            created_count = 0
            updated_count = 0
            error_count = 0
            
            for i, row in enumerate(raw_rows):
                row_num = i + 1
                try:
                    # Isolate each row transaction
                    with transaction.atomic():
                        parsed = parse_and_resolve_row(row_num, row, headers, self.template_key, self.organization)
                        action = executor(parsed, self.organization)
                        if action == 'created':
                            created_count += 1
                        elif action == 'updated':
                            updated_count += 1
                            
                except RowValidationError as e:
                    error_count += 1
                    ImportJobError.objects.create(
                        job=self.job,
                        row_number=row_num,
                        field=e.field,
                        error_type=e.error_type,
                        message=e.message,
                        row_data=dict(zip(headers, row))
                    )
                except Exception as e:
                    error_count += 1
                    ImportJobError.objects.create(
                        job=self.job,
                        row_number=row_num,
                        field='unknown',
                        error_type='system_error',
                        message=str(e),
                        row_data=dict(zip(headers, row))
                    )

            self.job.created_count = created_count
            self.job.updated_count = updated_count
            self.job.error_count = error_count
            self.job.valid_rows = created_count + updated_count
            
            if error_count > 0:
                self.job.status = 'completed_with_errors'
            else:
                self.job.status = 'completed'
                
            self.job.completed_at = timezone.now()
            self.job.save()

        except Exception as e:
            self.job.status = 'failed'
            self.job.completed_at = timezone.now()
            self.job.save(update_fields=['status', 'completed_at'])
            raise e
